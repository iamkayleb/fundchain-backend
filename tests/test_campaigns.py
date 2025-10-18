import os
import sys
import json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.models import db, User, Campaign


def create_test_app():
    from flask import Flask
    from backend.routes.auth import bp as auth_bp
    from backend.routes.campaigns import bp as camp_bp
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

    with app.app_context():
        db.drop_all()
        db.create_all()

    return app


def test_campaign_create_and_approve():
    app = create_test_app()
    import werkzeug
    if not hasattr(werkzeug, "__version__"):
        werkzeug.__version__ = "3.0.0"

    client = app.test_client()

    # create student and mark verified directly
    r = client.post("/api/signup", data=json.dumps({"email": "s3@example.com", "password": "p", "full_name": "S3", "role": "student"}), content_type="application/json")
    assert r.status_code == 201
    user_id = r.get_json()["user"]["id"]
    # mark verified
    with app.app_context():
        u = User.query.get(user_id)
        u.verified = True
        db.session.add(u)
        db.session.commit()

    # login
    r2 = client.post("/api/login", data=json.dumps({"email": "s3@example.com", "password": "p"}), content_type="application/json")
    assert r2.status_code == 200

    # create campaign
    camp_payload = {"title": "Help S3", "description": "For fees", "goal_amount": "10000", "deadline": None}
    r3 = client.post("/api/campaigns", data=json.dumps(camp_payload), content_type="application/json")
    assert r3.status_code == 201
    camp = r3.get_json()
    camp_id = camp["id"]

    # initially not in public active list
    r_list = client.get("/api/campaigns")
    assert r_list.status_code == 200
    assert all(c["id"] != camp_id for c in r_list.get_json())

    # create admin and login
    r_admin_signup = client.post("/api/signup", data=json.dumps({"email": "admin3@example.com", "password": "ap", "full_name": "A3", "role": "admin"}), content_type="application/json")
    assert r_admin_signup.status_code == 201
    r_admin_login = client.post("/api/login", data=json.dumps({"email": "admin3@example.com", "password": "ap"}), content_type="application/json")
    assert r_admin_login.status_code == 200

    # admin approve campaign
    r4 = client.post(f"/api/admin/campaigns/{camp_id}/approve")
    assert r4.status_code == 200

    # now campaign should appear in active list
    r_list2 = client.get("/api/campaigns")
    assert any(c["id"] == camp_id for c in r_list2.get_json())
