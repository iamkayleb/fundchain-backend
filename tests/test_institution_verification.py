import os
import sys
import json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.models import db, InstitutionProfile, Ledger, User, VerificationRequest, TxTypeEnum


def create_test_app():
    from flask import Flask
    from backend.routes.auth import bp as auth_bp
    from backend.routes.institution import bp as inst_bp
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
    app.register_blueprint(inst_bp)

    with app.app_context():
        db.drop_all()
        db.create_all()

    return app


def test_institution_registration_and_approval():
    app = create_test_app()
    import werkzeug
    if not hasattr(werkzeug, "__version__"):
        werkzeug.__version__ = "3.0.0"

    client = app.test_client()

    # register institution (domain mismatch true)
    payload = {
        "institution_name": "Example Uni",
        "representative_name": "Rep",
        "email": "rep@otherdomain.com",
        "email_domain": "example.edu",
        "password": "pass",
        "bank_account_details": {"acct": "123"},
        "accreditation_docs": ["https://docs.example.com/doc1.pdf"],
    }
    r = client.post("/api/institution/register", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 201
    req_id = r.get_json()["request_id"]

    # signup admin and login
    admin_payload = {"email": "admin2@example.com", "password": "adminpass", "full_name": "Admin2", "role": "admin"}
    r_admin_signup = client.post("/api/signup", data=json.dumps(admin_payload), content_type="application/json")
    assert r_admin_signup.status_code == 201
    r_admin_login = client.post("/api/login", data=json.dumps({"email": "admin2@example.com", "password": "adminpass"}), content_type="application/json")
    assert r_admin_login.status_code == 200

    # admin approves
    r2 = client.post(f"/api/admin/verify/institution/{req_id}/approve")
    assert r2.status_code == 200

    # assert profile is verified and ledger exists
    with app.app_context():
        vr = db.session.get(VerificationRequest, req_id)
        profile = InstitutionProfile.query.filter_by(user_id=vr.user_id).first()
        assert profile is not None
        assert profile.verified is True
        ledger_entry = Ledger.query.first()
        assert ledger_entry is not None
        assert getattr(ledger_entry.tx_type, "value", str(ledger_entry.tx_type)) == TxTypeEnum.institution_verified.value
