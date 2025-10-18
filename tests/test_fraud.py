import os
import sys
import json
from time import sleep

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.models import db, Notification


def create_test_app():
    from flask import Flask
    from backend.routes.auth import bp as auth_bp
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
        FRAUD_WINDOW_MINUTES=2,
        FRAUD_THRESHOLD=3,
    )

    db.init_app(app)
    JWTManager(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(don_bp)

    with app.app_context():
        db.drop_all()
        db.create_all()

    return app


def test_fraud_detection_triggers_notification():
    app = create_test_app()
    import werkzeug
    if not hasattr(werkzeug, "__version__"):
        werkzeug.__version__ = "3.0.0"

    client = app.test_client()

    # create admin
    client.post("/api/signup", data=json.dumps({"email": "adminf@example.com", "password": "p", "full_name": "AF", "role": "admin"}), content_type="application/json")

    # create donor
    client.post("/api/signup", data=json.dumps({"email": "fraud_donor@example.com", "password": "p", "full_name": "FD", "role": "donor"}), content_type="application/json")
    client.post("/api/login", data=json.dumps({"email": "fraud_donor@example.com", "password": "p"}), content_type="application/json")

    # create a campaign under a verified student so donations accepted
    client.post("/api/signup", data=json.dumps({"email": "s4@example.com", "password": "p", "full_name": "S4", "role": "student"}), content_type="application/json")
    client.post("/api/login", data=json.dumps({"email": "s4@example.com", "password": "p"}), content_type="application/json")
    # mark student verified
    with app.app_context():
        from backend.models import User
        u = User.query.filter_by(email="s4@example.com").first()
        u.verified = True
        db.session.add(u)
        db.session.commit()
    # create campaign directly in DB (simpler for test)
    with app.app_context():
        from backend.models import Campaign
        student = User.query.filter_by(email="s4@example.com").first()
        camp = Campaign(student_id=student.id, title="CF", description="desc", goal_amount=10, raised_amount=0)
        db.session.add(camp)
        db.session.commit()
        camp_id = camp.id

    # perform FRAUD_THRESHOLD donations quickly from same donor/IP
    for i in range(4):
        r = client.post(f"/api/campaigns/{camp_id}/donate", data=json.dumps({"amount": "1", "payment_method": "paystack"}), content_type="application/json")
        assert r.status_code == 200

    # check admin notifications
    radmin_not = client.post("/api/login", data=json.dumps({"email": "adminf@example.com", "password": "p"}), content_type="application/json")
    assert radmin_not.status_code == 200
    r_get = client.get("/api/admin/notifications")
    assert r_get.status_code == 200
    notes = r_get.get_json()
    # at least one fraud alert
    assert any(n["type"] == "fraud_alert" for n in notes)
