"""Institution onboarding and admin verification endpoints.

Endpoints:
- POST /api/institution/register
- POST /api/admin/verify/institution/<int:request_id>/approve
- POST /api/admin/verify/institution/<int:request_id>/reject
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash

from models import (
    db,
    User,
    InstitutionProfile,
    VerificationRequest,
    VerificationRoleEnum,
    VerificationStatus,
    Ledger,
    TxTypeEnum,
    Notification,
    NotificationType,
)
from routes.auth import requires_role

bp = Blueprint("institution", __name__, url_prefix="/api")


def _extract_domain(email: str) -> str:
    try:
        return email.split("@", 1)[1].lower()
    except Exception:
        return ""


@bp.route("/institution/register", methods=["POST"])
def institution_register():
    """Register an institution and create a pending verification request.

    Expected JSON: institution_name, representative_name, email, email_domain,
    password, bank_account_details (JSON), accreditation_docs (list of URLs)
    """
    data = request.get_json() or {}
    institution_name = data.get("institution_name")
    representative_name = data.get("representative_name")
    email = data.get("email")
    email_domain = (data.get("email_domain") or "").lower()
    password = data.get("password")
    bank_account_details = data.get("bank_account_details")
    accreditation_docs = data.get("accreditation_docs")

    if not all([institution_name, representative_name, email, email_domain, password]):
        return jsonify({"msg": "Missing required fields"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"msg": "Email already registered"}), 400

    password_hash = generate_password_hash(password)
    user = User(full_name=representative_name, email=email, password_hash=password_hash, role="institution")
    db.session.add(user)
    db.session.commit()

    # create profile
    profile = InstitutionProfile(
        user_id=user.id,
        institution_name=institution_name,
        email_domain=email_domain,
        bank_account_details=bank_account_details,
        accreditation_docs=accreditation_docs,
        verified=False,
    )
    db.session.add(profile)
    db.session.commit()

    # domain check
    actual_domain = _extract_domain(email)
    domain_mismatch = actual_domain != (email_domain or "")

    # create verification request for admin review
    vr_payload = {
        "accreditation_docs": accreditation_docs,
        "bank_account_details": bank_account_details,
        "domain_mismatch": domain_mismatch,
    }
    vr = VerificationRequest(
        user_id=user.id,
        role=VerificationRoleEnum.institution,
        document_urls=vr_payload,
        status=VerificationStatus.pending,
    )
    db.session.add(vr)
    db.session.commit()

    return jsonify({"ok": True, "request_id": vr.id}), 201


@bp.route("/admin/verify/institution/<int:request_id>/approve", methods=["POST"])
@requires_role("admin")
def approve_institution(request_id: int):
    admin_id = None
    try:
        admin_id = int(get_jwt_identity())
    except Exception:
        return jsonify({"msg": "Invalid token identity"}), 401

    vr = VerificationRequest.query.get(request_id)
    if not vr or vr.role != VerificationRoleEnum.institution:
        return jsonify({"msg": "Request not found"}), 404

    vr.status = VerificationStatus.approved
    vr.reviewed_by = admin_id
    db.session.add(vr)

    # mark profile verified
    profile = InstitutionProfile.query.filter_by(user_id=vr.user_id).first()
    if profile:
        profile.verified = True
        db.session.add(profile)

    # ledger entry
    payload = {"institution_id": profile.id if profile else None, "user_id": vr.user_id}
    ledger = Ledger(tx_type=TxTypeEnum.institution_verified, payload=payload)
    db.session.add(ledger)

    # notification
    note = Notification(user_id=vr.user_id, message="Your institution has been verified.", type=NotificationType.verification, data=payload)
    db.session.add(note)

    db.session.commit()

    return jsonify({"ok": True})


@bp.route("/admin/verify/institution/<int:request_id>/reject", methods=["POST"])
@requires_role("admin")
def reject_institution(request_id: int):
    data = request.get_json() or {}
    reason = data.get("reason")
    if not reason:
        return jsonify({"msg": "Missing reason"}), 400

    admin_id = None
    try:
        admin_id = int(get_jwt_identity())
    except Exception:
        return jsonify({"msg": "Invalid token identity"}), 401

    vr = VerificationRequest.query.get(request_id)
    if not vr or vr.role != VerificationRoleEnum.institution:
        return jsonify({"msg": "Request not found"}), 404

    vr.status = VerificationStatus.rejected
    vr.reason = reason
    vr.reviewed_by = admin_id
    db.session.add(vr)

    note = Notification(user_id=vr.user_id, message=f"Your institution verification was rejected: {reason}", type=NotificationType.verification, data={"reason": reason})
    db.session.add(note)

    db.session.commit()

    return jsonify({"ok": True})
