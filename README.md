# FundChain Backend API

A Flask-based REST API for educational fundraising platform with blockchain transparency, role-based authentication, and comprehensive verification workflows.

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- pip package manager
- SQLite (default) or PostgreSQL (production)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your configuration

# Initialize database
python -c "from app import create_app; from models import db; app = create_app(); app.app_context().push(); db.create_all()"

# Create admin user (optional)
python scripts/create_admin.py

# Run the application
python run.py
```

The API will be available at `http://localhost:5000`

## 📁 Project Structure

```
backend/
├── app.py                 # Flask application factory
├── run.py                 # Application entry point
├── models.py              # SQLAlchemy database models
├── ledger.py              # Blockchain ledger implementation
├── config.py              # Application configuration
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variables template
├── routes/                # API route modules
│   ├── __init__.py
│   ├── auth.py           # Authentication endpoints
│   ├── campaigns.py      # Campaign management
│   ├── donations.py      # Donation processing
│   ├── verification.py   # Verification workflows
│   ├── admin.py          # Admin-only endpoints
│   └── institution.py    # Institution management
├── scripts/               # Utility scripts
│   ├── create_admin.py   # Admin user creation
│   └── seed_data.py      # Database seeding
└── tests/                 # Unit and integration tests
    ├── test_auth.py
    ├── test_campaigns.py
    └── test_donations.py
```

## 🔐 Authentication & Authorization

### JWT Token Authentication
The API uses JWT (JSON Web Tokens) for stateless authentication with role-based access control.

**Roles Available:**
- `student` - Can create campaigns and submit verification
- `donor` - Can browse and donate to campaigns
- `institution` - Can verify students and manage rosters
- `admin` - Full system access and oversight

**Token Usage:**
```bash
# Login to get token
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Use token in subsequent requests (stored in httpOnly cookies)
curl -X GET http://localhost:5000/api/me \
  -H "Cookie: access_token_cookie=<jwt-token>"
```

### Role-Based Access Control
```python
from routes.auth import requires_role

@bp.route("/admin/users")
@requires_role("admin")  # Only admin users can access
def get_all_users():
    # Admin-only endpoint logic
    pass
```

## 📊 Database Models

### Core Models

#### User Model
```python
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    full_name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(RoleEnum), nullable=False)
    verified = db.Column(db.Boolean, default=False)
    extra = db.Column(SQLITE_JSON, default=lambda: {})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

#### Campaign Model
```python
class Campaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    goal_amount = db.Column(NumericAsDecimal(10, 2), nullable=False)
    raised_amount = db.Column(NumericAsDecimal(10, 2), default=Decimal("0.00"))
    status = db.Column(db.Enum(CampaignStatus), default=CampaignStatus.draft)
    deadline = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

#### Ledger Model (Blockchain)
```python
class Ledger(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tx_type = db.Column(db.Enum(TxTypeEnum), nullable=False)
    payload = db.Column(SQLITE_JSON, nullable=False)
    hash = db.Column(db.String(64), nullable=False, unique=True)
    prev_hash = db.Column(db.String(64))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
```

### Enums
```python
class RoleEnum(enum.Enum):
    student = "student"
    donor = "donor" 
    institution = "institution"
    admin = "admin"

class CampaignStatus(enum.Enum):
    draft = "draft"
    pending = "pending"
    active = "active"
    completed = "completed"
    failed = "failed"
```

## 🔗 API Endpoints

### Authentication (`/api/`)

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| `POST` | `/signup` | User registration | No |
| `POST` | `/login` | User authentication | No |
| `POST` | `/logout` | User logout | Yes |
| `GET` | `/me` | Get current user profile | Yes |

**Example - User Registration:**
```bash
curl -X POST http://localhost:5000/api/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "student@university.edu",
    "password": "securepassword",
    "full_name": "John Doe",
    "role": "student",
    "extra": {
      "university": "MIT",
      "major": "Computer Science"
    }
  }'
```

### Campaigns (`/api/campaigns`)

| Method | Endpoint | Description | Auth Required | Role |
|--------|----------|-------------|---------------|------|
| `GET` | `/campaigns` | List all active campaigns | No | Public |
| `POST` | `/campaigns` | Create new campaign | Yes | Student |
| `GET` | `/campaigns/<id>` | Get campaign details | No | Public |
| `POST` | `/campaigns/<id>/donate` | Donate to campaign | Optional | Any |

**Example - Create Campaign:**
```bash
curl -X POST http://localhost:5000/api/campaigns \
  -H "Content-Type: application/json" \
  -H "Cookie: access_token_cookie=<jwt-token>" \
  -d '{
    "title": "Computer Science Research Fund",
    "description": "Funding for advanced AI research equipment",
    "goal_amount": 25000,
    "deadline": "2025-12-31T23:59:59"
  }'
```

### Donations (`/api/campaigns/<id>/donate`)

**Example - Make Donation:**
```bash
curl -X POST http://localhost:5000/api/campaigns/1/donate \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 100,
    "payment_method": "paystack",
    "payment_card": "****1234"
  }'
```

### Verification (`/api/student/verify-request`)

| Method | Endpoint | Description | Auth Required | Role |
|--------|----------|-------------|---------------|------|
| `POST` | `/student/verify-request` | Submit verification docs | Yes | Student |

**Example - Submit Verification:**
```bash
curl -X POST http://localhost:5000/api/student/verify-request \
  -H "Content-Type: application/json" \
  -H "Cookie: access_token_cookie=<jwt-token>" \
  -d '{
    "document_urls": [
      "data:application/pdf;base64,JVBERi0xLjQ...",
      "https://example.com/transcript.pdf"
    ]
  }'
```

### Admin Endpoints (`/api/admin/`)

| Method | Endpoint | Description | Role Required |
|--------|----------|-------------|---------------|
| `GET` | `/admin/verification-requests` | Get pending verifications | Admin |
| `POST` | `/admin/verify/student/<id>/approve` | Approve student verification | Admin |
| `POST` | `/admin/verify/student/<id>/reject` | Reject student verification | Admin |
| `GET` | `/admin/campaigns` | Get pending campaigns | Admin |
| `POST` | `/admin/campaigns/<id>/approve` | Approve campaign | Admin |
| `POST` | `/admin/campaigns/<id>/reject` | Reject campaign | Admin |
| `GET` | `/admin/ledger` | Explore blockchain ledger | Admin |
| `POST` | `/admin/finalize/<id>` | Finalize campaign | Admin |

**Example - Approve Verification:**
```bash
curl -X POST http://localhost:5000/api/admin/verify/student/1/approve \
  -H "Cookie: access_token_cookie=<admin-jwt-token>"
```

### Institution Endpoints (`/api/institution/`)

| Method | Endpoint | Description | Role Required |
|--------|----------|-------------|---------------|
| `POST` | `/institution/register` | Register institution | Public |
| `POST` | `/institution/verify/student/<id>/approve` | Approve student verification | Institution |
| `POST` | `/institution/verify/student/<id>/reject` | Reject student verification | Institution |
| `GET` | `/institution/students` | Get institution students | Institution |
| `GET` | `/institution/verification-requests` | Get pending verifications | Institution |
| `POST` | `/institution/students/<id>/add` | Add student to roster | Institution |
| `POST` | `/institution/students/<id>/remove` | Remove student from roster | Institution |

## ⛓️ Blockchain Ledger System

### Overview
FundChain implements a blockchain-inspired ledger for transaction transparency using SHA-256 hashing and immutable record keeping.

### Ledger Operations
```python
from ledger import append_tx

# Record a donation
append_tx("donation", {
    "donor_id": 123,
    "campaign_id": 456,
    "amount": "100.00",
    "timestamp": "2025-01-01T10:00:00Z"
})

# Record campaign creation
append_tx("campaign_created", {
    "student_id": 789,
    "campaign_id": 456,
    "goal_amount": "5000.00"
})
```

### Hash Chain Verification
```python
def verify_ledger_integrity():
    """Verify the integrity of the blockchain ledger"""
    entries = Ledger.query.order_by(Ledger.id).all()
    
    for i, entry in enumerate(entries):
        expected_hash = compute_ledger_hash(
            entry.prev_hash, 
            entry.payload
        )
        
        if entry.hash != expected_hash:
            return False, f"Hash mismatch at entry {entry.id}"
    
    return True, "Ledger integrity verified"
```

## 🛡️ Security Features

### Password Security
- Werkzeug password hashing with salt
- Minimum password requirements enforced
- Account lockout after failed attempts

### CSRF Protection
```python
from flask_wtf.csrf import CSRFProtect

csrf = CSRFProtect()
csrf.init_app(app)
```

### Fraud Detection
```python
def detect_donation_fraud(donor_id, campaign_id, amount, ip_address):
    """Detect potentially fraudulent donation patterns"""
    
    # Check for rapid successive donations
    recent_donations = Contribution.query.filter(
        Contribution.donor_id == donor_id,
        Contribution.created_at > datetime.utcnow() - timedelta(minutes=5)
    ).count()
    
    if recent_donations > 3:
        return {"is_fraud": True, "reason": "Too many rapid donations"}
    
    # Check for unusually large amounts
    if amount > 10000:
        return {"is_fraud": True, "reason": "Unusually large donation amount"}
    
    return {"is_fraud": False}
```

### Input Validation
```python
from werkzeug.exceptions import BadRequest

def validate_campaign_data(data):
    """Validate campaign creation data"""
    required_fields = ['title', 'goal_amount']
    
    for field in required_fields:
        if not data.get(field):
            raise BadRequest(f"Missing required field: {field}")
    
    if data['goal_amount'] <= 0:
        raise BadRequest("Goal amount must be positive")
```

## 🔧 Configuration

### Environment Variables
Create a `.env` file in the backend directory:

```bash
# Flask Configuration
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=your-secret-key-here

# Database Configuration
DATABASE_URL=sqlite:///fundchain.db
# For PostgreSQL:
# DATABASE_URL=postgresql://username:password@localhost:5432/fundchain

# JWT Configuration
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ACCESS_TOKEN_EXPIRES=False

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:3001

# Payment Configuration (Optional)
PAYSTACK_SECRET_KEY=your-paystack-secret
STRIPE_SECRET_KEY=your-stripe-secret

# Email Configuration (Optional)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
```

### Development vs Production
```python
# config.py
import os

class DevelopmentConfig:
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///fundchain_dev.db'
    JWT_ACCESS_TOKEN_EXPIRES = False

class ProductionConfig:
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
```

## 🧪 Testing

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_auth.py

# Run specific test
pytest tests/test_auth.py::test_user_registration
```

### Test Structure
```python
# tests/test_campaigns.py
import pytest
from app import create_app
from models import db, User, Campaign

@pytest.fixture
def client():
    app = create_app('testing')
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()

def test_create_campaign(client, auth_headers):
    response = client.post('/api/campaigns', 
        json={
            'title': 'Test Campaign',
            'goal_amount': 1000
        },
        headers=auth_headers
    )
    assert response.status_code == 201
```

## 📝 Error Handling

### Custom Error Responses
```python
from flask import jsonify

@app.errorhandler(400)
def bad_request(error):
    return jsonify({
        'error': 'Bad Request',
        'message': str(error),
        'status_code': 400
    }), 400

@app.errorhandler(401)
def unauthorized(error):
    return jsonify({
        'error': 'Unauthorized',
        'message': 'Invalid or missing authentication token',
        'status_code': 401
    }), 401
```

### API Error Codes

| Code | Description | Common Causes |
|------|-------------|---------------|
| `400` | Bad Request | Missing required fields, invalid data format |
| `401` | Unauthorized | Invalid or missing JWT token |
| `403` | Forbidden | Insufficient permissions for role |
| `404` | Not Found | Resource does not exist |
| `409` | Conflict | Duplicate email, campaign already exists |
| `422` | Unprocessable Entity | Validation errors |
| `500` | Internal Server Error | Database errors, unexpected exceptions |

## 📈 Performance & Monitoring

### Database Optimization
```python
# Add indexes for frequently queried fields
class Campaign(db.Model):
    # ... other fields ...
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    status = db.Column(db.Enum(CampaignStatus), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
```

### Logging
```python
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/fundchain.log'),
        logging.StreamHandler()
    ]
)

# Use in routes
@bp.route('/campaigns', methods=['POST'])
def create_campaign():
    logging.info(f"Campaign creation attempted by user {current_user.id}")
```

### Health Check Endpoint
```python
@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Test database connection
        db.session.execute('SELECT 1')
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '1.0.0'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500
```

## 🚀 Deployment

### Production Deployment

#### Using Gunicorn (Recommended)
```bash
# Install gunicorn
pip install gunicorn

# Run with gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 run:app

# With configuration file
gunicorn -c gunicorn.conf.py run:app
```

#### Gunicorn Configuration (`gunicorn.conf.py`)
```python
bind = "0.0.0.0:5000"
workers = 4
worker_class = "sync"
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 50
```

#### Docker Deployment
```dockerfile
# Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "-c", "gunicorn.conf.py", "run:app"]
```

#### Heroku Deployment
```bash
# Create Procfile
echo "web: gunicorn run:app" > Procfile

# Deploy to Heroku
heroku create fundchain-api
heroku addons:create heroku-postgresql:hobby-dev
heroku config:set FLASK_ENV=production
git push heroku main
```

### Database Migrations
```bash
# Initialize migrations (first time only)
flask db init

# Create migration
flask db migrate -m "Add new field to User model"

# Apply migration
flask db upgrade
```

## 🤝 Contributing

### Development Workflow
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make changes and add tests
4. Run tests: `pytest`
5. Commit changes: `git commit -m "Add new feature"`
6. Push to branch: `git push origin feature/new-feature`
7. Create Pull Request

### Code Style
```bash
# Install development tools
pip install black flake8 isort

# Format code
black .

# Check style
flake8 .

# Sort imports
isort .
```

### Adding New Endpoints
```python
# routes/new_module.py
from flask import Blueprint, request, jsonify
from .auth import requires_role

bp = Blueprint('new_module', __name__)

@bp.route('/new-endpoint', methods=['POST'])
@requires_role('student')
def new_endpoint():
    """Description of what this endpoint does"""
    data = request.get_json()
    
    # Validate input
    if not data.get('required_field'):
        return jsonify({'msg': 'Missing required field'}), 400
    
    # Business logic here
    
    return jsonify({'msg': 'Success'}), 201
```

## 📞 Support

### Common Issues

**Database Connection Error:**
```bash
# Reset database
rm fundchain.db
python -c "from app import create_app; from models import db; app = create_app(); app.app_context().push(); db.create_all()"
```

**JWT Token Issues:**
```bash
# Check JWT secret key is set
echo $JWT_SECRET_KEY

# Clear cookies in browser
# Check token expiration settings
```

**Import Errors:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### Getting Help
- Check the logs: `tail -f logs/fundchain.log`
- Enable debug mode: `FLASK_ENV=development`
- Use the `/health` endpoint to check system status

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🎯 Roadmap

### Planned Features
- [ ] WebSocket support for real-time notifications
- [ ] Advanced fraud detection algorithms
- [ ] Email notification system
- [ ] Payment gateway integrations (Stripe, PayPal)
- [ ] Campaign analytics and reporting
- [ ] Multi-currency support
- [ ] API rate limiting
- [ ] Advanced caching with Redis
- [ ] Microservices architecture migration

### Version History
- **v1.0.0** - Initial release with core functionality
- **v0.9.0** - Beta release with admin dashboard
- **v0.8.0** - Alpha release with basic campaign management

---

**FundChain Backend API** - Empowering educational fundraising through blockchain transparency and secure, role-based access control.