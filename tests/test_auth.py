import json
import os
import sys
import pytest

# ensure project root is on sys.path so `import backend` works when pytest runs
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.models import db, User


def create_test_app(tmp_path, monkeypatch):
    # minimal app factory for testing
    from flask import Flask
    from backend.routes.auth import bp as auth_bp

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
    # initialize JWT for tests
    from flask_jwt_extended import JWTManager
    JWTManager(app)
    app.register_blueprint(auth_bp)

    with app.app_context():
        # ensure a clean slate for tests
        db.drop_all()
        db.create_all()

    return app


def test_signup_and_login(monkeypatch):
    app = create_test_app(None, monkeypatch)
    # some Werkzeug releases remove __version__; ensure it's present for Flask test client
    import werkzeug
    if not hasattr(werkzeug, "__version__"):
        werkzeug.__version__ = "3.0.0"

    client = app.test_client()

    # Signup
    payload = {"email": "student@example.com", "password": "pass123", "full_name": "Test Student", "role": "student"}
    r = client.post("/api/signup", data=json.dumps(payload), content_type="application/json")
    assert r.status_code == 201
    data = r.get_json()
    assert data["ok"] is True
    assert data["user"]["email"] == "student@example.com"

    # Login
    r2 = client.post("/api/login", data=json.dumps({"email": "student@example.com", "password": "pass123"}), content_type="application/json")
    assert r2.status_code == 200
    data2 = r2.get_json()
    assert data2["ok"] is True
    assert data2["role"] == "student"
