import os
import sys
import json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.models import db, Ledger


def create_test_app():
    from flask import Flask
    from backend.routes.auth import bp as auth_bp
    from backend.routes.admin import bp as admin_bp
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
    app.register_blueprint(admin_bp)

    with app.app_context():
        db.drop_all()
        db.create_all()

    return app


def test_admin_access_control_and_ledger():
    app = create_test_app()
    import werkzeug
    if not hasattr(werkzeug, "__version__"):
        werkzeug.__version__ = "3.0.0"

    client = app.test_client()

    # create normal user
    client.post("/api/signup", data=json.dumps({"email": "normal@example.com", "password": "p", "full_name": "N", "role": "donor"}), content_type="application/json")
    r = client.get("/api/admin/ledger")
    assert r.status_code in (401, 403)

    # create admin and login
    client.post("/api/signup", data=json.dumps({"email": "adminx@example.com", "password": "p", "full_name": "AX", "role": "admin"}), content_type="application/json")
    rlogin = client.post("/api/login", data=json.dumps({"email": "adminx@example.com", "password": "p"}), content_type="application/json")
    assert rlogin.status_code == 200

    # create some ledger rows directly
    with app.app_context():
        from backend.ledger import append_tx
        append_tx('lock', {'test': 1})
        append_tx('student_verified', {'u': 2})

    r2 = client.get("/api/admin/ledger")
    assert r2.status_code == 200
    data = r2.get_json()
    assert data["total"] >= 2
