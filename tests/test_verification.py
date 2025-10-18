import os
import sys
import json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest

from backend.models import db, User, VerificationRequest, Ledger


def create_test_app():
    from flask import Flask
    from backend.routes.auth import bp as auth_bp
    from backend.routes.verification import bp as ver_bp
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
    app.register_blueprint(ver_bp)

    with app.app_context():
        db.drop_all()
        db.create_all()

    return app


def test_student_verification_flow():
    app = create_test_app()
    import werkzeug
    if not hasattr(werkzeug, "__version__"):
        werkzeug.__version__ = "3.0.0"

    client = app.test_client()

    # create student
    payload = {"email": "stud2@example.com", "password": "p", "full_name": "S2", "role": "student"}
    r = client.post("/api/signup", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 201
    user_id = r.get_json()["user"]["id"]

    # login as student to receive JWT cookie
    r2 = client.post(
        "/api/login",
        data=json.dumps({"email": "stud2@example.com", "password": "p"}),
        content_type="application/json",
    )
    assert r2.status_code == 200

    # submit verification request
    doc_payload = {"document_urls": ["https://example.com/doc1.jpg"]}
    r3 = client.post(
        "/api/student/verify-request",
        data=json.dumps(doc_payload),
        content_type="application/json",
    )
    assert r3.status_code == 201
    req_id = r3.get_json()["id"]

    # create admin via signup and login so cookie is set by the app
    admin_payload = {"email": "admin@example.com", "password": "adminpass", "full_name": "Admin", "role": "admin"}
    r_admin_signup = client.post("/api/signup", data=json.dumps(admin_payload), content_type="application/json")
    assert r_admin_signup.status_code == 201
    r_admin_login = client.post("/api/login", data=json.dumps({"email": "admin@example.com", "password": "adminpass"}), content_type="application/json")
    assert r_admin_login.status_code == 200

    # fetch pending requests as admin
    r5 = client.get("/api/admin/verification-requests?role=student")
    assert r5.status_code == 200
    arr = r5.get_json()
    assert any(r["id"] == req_id for r in arr)

    # approve the request
    r6 = client.post(f"/api/admin/verify/student/{req_id}/approve")
    assert r6.status_code == 200

    # verify user is now verified and ledger entry exists
    from backend.models import TxTypeEnum
    with app.app_context():
        user = User.query.get(user_id)
        assert user.verified is True
        ledger_entry = Ledger.query.first()
        assert ledger_entry is not None
        assert getattr(ledger_entry.tx_type, "value", str(ledger_entry.tx_type)) == TxTypeEnum.student_verified.value
