"""Authentication routes using Flask-JWT-Extended with httpOnly cookies.

Endpoints:
- POST /api/signup
- POST /api/login
- POST /api/logout
- GET  /api/me

Includes a `requires_role` decorator for role-protected endpoints.
"""
from functools import wraps
from typing import Optional

from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    create_access_token,
    set_access_cookies,
    unset_jwt_cookies,
    jwt_required,
    get_jwt_identity,
)

from models import db, User, InstitutionProfile, RoleEnum


bp = Blueprint("auth", __name__, url_prefix="/api")


def requires_role(role: str):
    """Decorator to require a specific role for the current JWT user.

    Usage: @requires_role('admin')
    """

    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            identity = get_jwt_identity()
            try:
                user_id = int(identity)
            except Exception:
                return jsonify({"msg": "Invalid identity in token"}), 401
            user = User.query.get(user_id)
            if not user:
                return jsonify({"msg": "User not found"}), 401
            if user.role.value != role:
                return jsonify({"msg": "Forbidden"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


@bp.route("/signup", methods=["POST"])
def signup():
    """Role-based signup. Accepts JSON with required fields depending on role.

    Returns 201 with user id/email/role on success.
    """
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    full_name = data.get("full_name")
    role = data.get("role")

    if not email or not password or not full_name or not role:
        return jsonify({"msg": "Missing required fields"}), 400

    try:
        role_enum = RoleEnum(role)
    except ValueError:
        return jsonify({"msg": "Invalid role"}), 400

    # SECURITY: Prevent admin registration through public signup
    if role_enum == RoleEnum.admin:
        return jsonify({"msg": "Admin accounts cannot be created through public registration"}), 403

    # unique email
    if User.query.filter_by(email=email).first():
        return jsonify({"msg": "Email already registered"}), 400

    password_hash = generate_password_hash(password)

    user = User(full_name=full_name, email=email, password_hash=password_hash, role=role_enum)
    # optional extra fields
    extra = data.get("extra")
    if extra is not None:
        user.extra = extra

    db.session.add(user)
    db.session.commit()

    # If institution, create InstitutionProfile if provided
    if role_enum.value == "institution":
        inst = data.get("institution_profile") or {}
        profile = InstitutionProfile(
            user_id=user.id,
            institution_name=inst.get("institution_name", full_name),
            email_domain=inst.get("email_domain"),
            bank_account_details=inst.get("bank_account_details"),
            accreditation_docs=inst.get("accreditation_docs"),
        )
        db.session.add(profile)
        db.session.commit()

    return (
        jsonify({"ok": True, "user": {"id": user.id, "email": user.email, "role": user.role.value}}),
        201,
    )


@bp.route("/login", methods=["POST"])
def login():
    """Authenticate and set access token as httpOnly cookie."""
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"msg": "Missing email or password"}), 400

    user: Optional[User] = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"msg": "Bad credentials"}), 401

    access_token = create_access_token(identity=str(user.id))
    resp = jsonify({"ok": True, "role": user.role.value})
    set_access_cookies(resp, access_token)
    return resp


@bp.route("/logout", methods=["POST"])
def logout():
    resp = jsonify({"ok": True})
    unset_jwt_cookies(resp)
    return resp


@bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    """Return the current user and a role-specific profile object."""
    identity = get_jwt_identity()
    try:
        user_id = int(identity)
    except Exception:
        return jsonify({"msg": "Invalid token identity"}), 401

    user = User.query.get(user_id)
    if not user:
        return jsonify({"msg": "User not found"}), 404

    profile = None
    if user.role == RoleEnum.institution and user.institution_profile:
        profile = user.institution_profile.to_dict()
    else:
        # generic extra/profile for students/donors
        profile = user.extra

    return jsonify({"user": user.to_dict(include_email=True), "profile": profile})


@bp.route("/admin/create-admin", methods=["POST"])
@requires_role("admin")
def create_admin_user():
    """Admin-only endpoint to create new admin users.
    
    Requires existing admin authentication.
    """
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    full_name = data.get("full_name")

    if not email or not password or not full_name:
        return jsonify({"msg": "Missing required fields: email, password, full_name"}), 400

    # Check if user already exists
    if User.query.filter_by(email=email).first():
        return jsonify({"msg": "Email already registered"}), 400

    # Create admin user
    password_hash = generate_password_hash(password)
    admin_user = User(
        full_name=full_name, 
        email=email, 
        password_hash=password_hash, 
        role=RoleEnum.admin
    )
    
    db.session.add(admin_user)
    db.session.commit()

    return jsonify({
        "ok": True, 
        "message": "Admin user created successfully",
        "user": {"id": admin_user.id, "email": admin_user.email, "role": admin_user.role.value}
    }), 201
