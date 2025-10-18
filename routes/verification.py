"""Verification endpoints for students and admin review.

Endpoints:
- POST /api/student/verify-request
- GET  /api/admin/verification-requests
- POST /api/admin/verify/student/<int:request_id>/approve
- POST /api/admin/verify/student/<int:request_id>/reject
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import (
    db,
    VerificationRequest,
    VerificationRoleEnum,
    VerificationStatus,
    User,
    Ledger,
    TxTypeEnum,
    Notification,
    NotificationType,
)
from routes.auth import requires_role


bp = Blueprint("verification", __name__, url_prefix="/api")


@bp.route("/student/verify-request", methods=["POST"])
@requires_role("student")
def student_verify_request():
    """Student submits verification documents. Accepts JSON or form.

    JSON: {"document_urls": [..]}
    Form: document_urls=JSON-string or single URL
    """
    # Debug: log incoming cookies and auth headers to help trace 401 issues
    try:
        from flask import request as _req
        current_app.logger.debug("verify_request headers: %s", dict(_req.headers))
        current_app.logger.debug("verify_request cookies: %s", dict(_req.cookies))
    except Exception:
        pass

    identity = get_jwt_identity()
    try:
        user_id = int(identity)
    except Exception:
        return jsonify({"msg": "Invalid token identity"}), 401

    # parse document_urls from JSON body or form
    if request.is_json:
        data = request.get_json() or {}
        document_urls = data.get("document_urls")
    else:
        document_urls = request.form.get("document_urls")
        # attempt to parse if JSON string
        import json

        try:
            document_urls = json.loads(document_urls) if document_urls else None
        except Exception:
            # treat as single URL
            document_urls = [document_urls] if document_urls else None

    if not document_urls:
        return jsonify({"msg": "Missing document_urls"}), 400

    vr = VerificationRequest(
        user_id=user_id,
        role=VerificationRoleEnum.student,
        document_urls=document_urls,
        status=VerificationStatus.pending,
    )
    db.session.add(vr)
    db.session.commit()

    return jsonify({"id": vr.id}), 201


@bp.route("/admin/verification-requests", methods=["GET"])
@requires_role("admin")
def list_verification_requests():
    role = request.args.get("role", "student")
    # return pending requests for the role
    qrole = VerificationRoleEnum(role) if role in (r.value for r in VerificationRoleEnum) else None
    if not qrole:
        return jsonify({"msg": "Invalid role"}), 400

    reqs = VerificationRequest.query.filter_by(role=qrole, status=VerificationStatus.pending).all()
    return jsonify([r.to_dict() for r in reqs])


@bp.route("/admin/verify/student/<int:request_id>/approve", methods=["POST"])
@requires_role("admin")
def approve_student(request_id: int):
    admin_id = None
    try:
        admin_id = int(get_jwt_identity())
    except Exception:
        return jsonify({"msg": "Invalid token identity"}), 401

    vr = VerificationRequest.query.get(request_id)
    if not vr or vr.role != VerificationRoleEnum.student:
        return jsonify({"msg": "Request not found"}), 404

    vr.status = VerificationStatus.approved
    vr.reviewed_by = admin_id
    db.session.add(vr)

    # mark user verified
    user = User.query.get(vr.user_id)
    if user:
        user.verified = True
        db.session.add(user)

    # create ledger entry
    payload = {"user_id": vr.user_id, "request_id": vr.id}
    ledger = Ledger(tx_type=TxTypeEnum.student_verified, payload=payload)
    db.session.add(ledger)

    # notification
    note = Notification(user_id=vr.user_id, message="Your verification was approved.", type=NotificationType.verification, data=payload)
    db.session.add(note)

    db.session.commit()

    return jsonify({"ok": True})


@bp.route("/admin/verify/student/<int:request_id>/reject", methods=["POST"])
@requires_role("admin")
def reject_student(request_id: int):
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
    if not vr or vr.role != VerificationRoleEnum.student:
        return jsonify({"msg": "Request not found"}), 404

    vr.status = VerificationStatus.rejected
    vr.reason = reason
    vr.reviewed_by = admin_id
    db.session.add(vr)

    note = Notification(user_id=vr.user_id, message=f"Your verification was rejected: {reason}", type=NotificationType.verification, data={"reason": reason})
    db.session.add(note)

    db.session.commit()

    return jsonify({"ok": True})
