"""Application factory and blueprint registration for the backend."""
from flask import Flask
from flask_jwt_extended import JWTManager
from flask_cors import CORS

from backend.models import db


def create_app(config: dict = None):
    app = Flask(__name__)
    # default config — override by passing a dict
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite:///data.sqlite",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY="change-me",
        JWT_TOKEN_LOCATION=["cookies"],
        JWT_COOKIE_SECURE=False,
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    JWTManager(app)

    # Configure CORS for API routes (allow credentials for cookie-based auth)
    # Use environment variable CORS_ORIGINS (comma-separated) to override defaults
    import os

    default_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:3003",
    ]
    cors_env = os.environ.get("CORS_ORIGINS")
    if cors_env:
        origins = [o.strip() for o in cors_env.split(",") if o.strip()]
    else:
        origins = default_origins

    # Apply CORS only to API endpoints so static files still serve normally
    # Allow the X-CSRF-TOKEN header which our frontend sends for double-submit CSRF
    CORS(app, resources={r"/api/*": {"origins": origins, "allow_headers": ["Content-Type", "Authorization", "X-CSRF-TOKEN"]}}, supports_credentials=True)

    # Ensure preflight responses include the proper Access-Control-Allow-* headers
    # For development: echo back the Origin header (so browsers accept preflight)
    @app.after_request
    def _cors_after(response):
        from flask import request

        req_origin = request.headers.get('Origin')
        if req_origin:
            # Echo origin back so Access-Control-Allow-Origin is present for preflight
            response.headers['Access-Control-Allow-Origin'] = req_origin
            # Add Vary: Origin so caches know responses differ by Origin
            vary = response.headers.get('Vary')
            if vary:
                if 'Origin' not in vary:
                    response.headers['Vary'] = f"{vary}, Origin"
            else:
                response.headers['Vary'] = 'Origin'

            response.headers['Access-Control-Allow-Credentials'] = 'true'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization,X-CSRF-TOKEN'
            response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
        return response

    # Handle OPTIONS preflight explicitly to ensure preflight responses include CORS headers
    from flask import request, make_response

    @app.before_request
    def _handle_options():
        if request.method == 'OPTIONS':
            resp = make_response(('', 200))
            origin = request.headers.get('Origin')
            if origin:
                resp.headers['Access-Control-Allow-Origin'] = origin
                resp.headers['Access-Control-Allow-Credentials'] = 'true'
                resp.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization,X-CSRF-TOKEN'
                resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
                resp.headers['Vary'] = 'Origin'
            return resp

    # register blueprints
    from backend.routes.auth import bp as auth_bp
    from backend.routes.admin import bp as admin_bp
    from backend.routes.verification import bp as verification_bp
    from backend.routes.institution import bp as institution_bp
    from backend.routes.campaigns import bp as campaigns_bp
    from backend.routes.donations import bp as donations_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(verification_bp)
    app.register_blueprint(institution_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(donations_bp)

    return app
