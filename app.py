"""Application factory and blueprint registration for the backend."""
from flask import Flask
from flask_jwt_extended import JWTManager
from flask_cors import CORS

from models import db


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
        "https://fundchain-frontend.vercel.app",
        "https://fundchain-frontend-*.vercel.app",
        "https://*.vercel.app",
        "https://fundchain.netlify.app",
        "https://*.netlify.app",
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

    # Root endpoint
    @app.route('/')
    def root():
        """Root endpoint with API information"""
        from flask import jsonify
        return jsonify({
            'message': 'FundChain Backend API',
            'version': '1.0.0',
            'status': 'running',
            'documentation': '/api',
            'health_check': '/health',
            'endpoints': {
                'authentication': '/api/login, /api/signup, /api/logout',
                'campaigns': '/api/campaigns',
                'donations': '/api/campaigns/<id>/donate',
                'admin': '/api/admin/*',
                'verification': '/api/student/verify-request',
                'institution': '/api/institution/*'
            }
        })

    # Health check endpoint for monitoring and deployment
    @app.route('/health')
    def health_check():
        """Health check endpoint for monitoring"""
        try:
            # Test database connection
            db.session.execute('SELECT 1')
            
            from flask import jsonify
            from datetime import datetime
            
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.utcnow().isoformat(),
                'version': '1.0.0',
                'service': 'fundchain-backend'
            })
        except Exception as e:
            from flask import jsonify
            return jsonify({
                'status': 'unhealthy',
                'error': str(e),
                'service': 'fundchain-backend'
            }), 500

    # API info endpoint
    @app.route('/api')
    def api_info():
        """API information and available endpoints"""
        from flask import jsonify
        return jsonify({
            'name': 'FundChain Educational Fundraising API',
            'version': '1.0.0',
            'description': 'Blockchain-enabled educational fundraising platform with role-based access control',
            'documentation': 'https://github.com/iamkayleb/fundchain-backend/blob/main/README.md',
            'endpoints': {
                'Authentication': {
                    'POST /api/signup': 'User registration',
                    'POST /api/login': 'User authentication',
                    'POST /api/logout': 'User logout',
                    'GET /api/me': 'Get current user profile'
                },
                'Campaigns': {
                    'GET /api/campaigns': 'List all active campaigns',
                    'POST /api/campaigns': 'Create new campaign (students only)',
                    'GET /api/campaigns/<id>': 'Get campaign details'
                },
                'Donations': {
                    'POST /api/campaigns/<id>/donate': 'Donate to campaign'
                },
                'Admin': {
                    'GET /api/admin/verification-requests': 'Get pending verifications',
                    'POST /api/admin/verify/student/<id>/approve': 'Approve student verification',
                    'POST /api/admin/verify/student/<id>/reject': 'Reject student verification',
                    'GET /api/admin/campaigns': 'Get pending campaigns',
                    'GET /api/admin/ledger': 'Explore blockchain ledger'
                },
                'Institution': {
                    'POST /api/institution/register': 'Register institution'
                }
            },
            'roles': ['student', 'donor', 'institution', 'admin'],
            'features': [
                'JWT Authentication',
                'Role-based Access Control',
                'Blockchain Ledger',
                'Campaign Management',
                'Verification Workflows',
                'Fraud Detection'
            ]
        })

    # register blueprints
    from routes.auth import bp as auth_bp
    from routes.admin import bp as admin_bp
    from routes.verification import bp as verification_bp
    from routes.institution import bp as institution_bp
    from routes.campaigns import bp as campaigns_bp
    from routes.donations import bp as donations_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(verification_bp)
    app.register_blueprint(institution_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(donations_bp)

    return app
