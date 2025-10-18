"""Admin-only endpoints: ledger explorer, verification queue, campaign approvals.
"""
from flask import Blueprint, request, jsonify
from backend.models import Ledger, VerificationRequest, VerificationStatus, Campaign, CampaignStatus
from backend.routes.auth import requires_role
from backend.routes.donations import finalize_campaign as donations_finalize

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.route("/ledger", methods=["GET"])
@requires_role("admin")
def ledger_explorer():
    # pagination
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except Exception:
        return jsonify({"msg": "Invalid pagination"}), 400

    q = Ledger.query.order_by(Ledger.id.desc())
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()

    results = [
        {
            "id": it.id,
            "tx_type": getattr(it.tx_type, "value", str(it.tx_type)),
            "payload": it.payload,
            "hash": it.hash,
            "prev_hash": it.prev_hash,
            "timestamp": it.timestamp.isoformat() if it.timestamp else None,
        }
        for it in items
    ]

    return jsonify({"page": page, "per_page": per_page, "total": total, "items": results})


@bp.route("/verification-requests", methods=["GET"])
@requires_role("admin")
def admin_verification_requests():
    reqs = VerificationRequest.query.filter(VerificationRequest.status == VerificationStatus.pending).order_by(VerificationRequest.created_at.desc()).all()
    
    # Include user information in the response
    results = []
    for req in reqs:
        req_dict = req.to_dict()
        # Add user email if available
        if req.user:
            req_dict["user_email"] = req.user.email
            req_dict["user_name"] = req.user.full_name
        results.append(req_dict)
    
    return jsonify(results)


@bp.route("/campaigns", methods=["GET"])
@requires_role("admin")
def admin_campaigns():
    camps = Campaign.query.filter(Campaign.status == CampaignStatus.pending).order_by(Campaign.created_at.desc()).all()
    return jsonify([c.to_dict() for c in camps])


@bp.route("/finalize/<int:campaign_id>", methods=["POST"])
@requires_role("admin")
def admin_finalize(campaign_id: int):
    # delegate to donations.finalize_campaign which already performs finalize logic
    # donations_finalize is a Flask view function; calling it will execute the same logic
    return donations_finalize.__wrapped__(campaign_id)
