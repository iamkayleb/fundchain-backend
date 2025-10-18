import os
import sys
import json
from decimal import Decimal

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.models import db, Contribution, Ledger, Campaign


def create_test_app():
    from flask import Flask
    from backend.routes.auth import bp as auth_bp
    from backend.routes.campaigns import bp as camp_bp
    from backend.routes.donations import bp as don_bp
    from flask_jwt_extended import JWTManager

    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_TOKEN_LOCATION=["cookies"],
        JWT_COOKIE_SECURE=False,
        JWT_COOKIE_CSRF_PROTECT=False,
        JWT_SECRET_KEY="test-secret",
    )

    db.init_app(app)
    JWTManager(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(camp_bp)
    app.register_blueprint(don_bp)

    with app.app_context():
        db.drop_all()
        db.create_all()

    return app


def test_paystack_donation_flow_and_finalize():
    app = create_test_app()
    import werkzeug
    if not hasattr(werkzeug, "__version__"):
        werkzeug.__version__ = "3.0.0"

    client = app.test_client()

    # create verified student and campaign
    r = client.post("/api/signup", data=json.dumps({"email": "don_student@example.com", "password": "p", "full_name": "DS", "role": "student"}), content_type="application/json")
    assert r.status_code == 201
    student_id = r.get_json()["user"]["id"]
    with app.app_context():
        from backend.models import User
        u = User.query.get(student_id)
        u.verified = True
        db.session.add(u)
        db.session.commit()

    # create campaign
    r2 = client.post("/api/login", data=json.dumps({"email": "don_student@example.com", "password": "p"}), content_type="application/json")
    assert r2.status_code == 200
    r3 = client.post("/api/campaigns", data=json.dumps({"title": "C1", "description": "desc", "goal_amount": "50", "deadline": None}), content_type="application/json")
    assert r3.status_code == 201
    camp_id = r3.get_json()["id"]

    # create donor and login
    rdon = client.post("/api/signup", data=json.dumps({"email": "donor1@example.com", "password": "p", "full_name": "D1", "role": "donor"}), content_type="application/json")
    assert rdon.status_code == 201
    rdon_login = client.post("/api/login", data=json.dumps({"email": "donor1@example.com", "password": "p"}), content_type="application/json")
    assert rdon_login.status_code == 200

    # donate via paystack
    rdonate = client.post(f"/api/campaigns/{camp_id}/donate", data=json.dumps({"amount": "25", "payment_method": "paystack"}), content_type="application/json")
    assert rdonate.status_code == 200
    data = rdonate.get_json()
    assert "checkout_url" in data
    contrib_id = data["contribution_id"]

    # webhook verify success
    rweb = client.post("/api/donations/verify", data=json.dumps({"contribution_id": contrib_id, "success": True}), content_type="application/json")
    assert rweb.status_code == 200

    with app.app_context():
        contrib = Contribution.query.get(contrib_id)
        # status is an Enum on the model; compare to its value
        assert getattr(contrib.status, "value", str(contrib.status)) == "locked"
        lock_entry = Ledger.query.first()
        assert lock_entry is not None
        assert getattr(lock_entry.tx_type, "value", str(lock_entry.tx_type)) == "lock"

    # finalize campaign as admin: create/admin and approve campaign first
    r_admin = client.post("/api/signup", data=json.dumps({"email": "admin4@example.com", "password": "p", "full_name": "A4", "role": "admin"}), content_type="application/json")
    assert r_admin.status_code == 201
    r_admin_login = client.post("/api/login", data=json.dumps({"email": "admin4@example.com", "password": "p"}), content_type="application/json")
    assert r_admin_login.status_code == 200

    # approve campaign to active
    rapprove = client.post(f"/api/admin/campaigns/{camp_id}/approve")
    assert rapprove.status_code == 200

    # finalize disburse
    rfinal = client.post(f"/api/admin/finalize/{camp_id}", data=json.dumps({"force": True}), content_type="application/json")
    assert rfinal.status_code == 200

    with app.app_context():
        c = Contribution.query.get(contrib_id)
        assert getattr(c.status, "value", str(c.status)) == "disbursed"
        disb = Ledger.query.order_by(Ledger.id.desc()).first()
        assert disb is not None
        assert getattr(disb.tx_type, "value", str(disb.tx_type)) == "disburse"
