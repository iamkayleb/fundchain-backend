"""Campaign endpoints: creation by verified students, public listing, details, and admin approvals."""
from decimal import Decimal
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.models import (
    db,
    Campaign,
    CampaignStatus,
    Contribution,
    Notification,
    NotificationType,
    User,
)
from backend.routes.auth import requires_role


bp = Blueprint("campaigns", __name__, url_prefix="/api")


@bp.route("/campaigns", methods=["POST"])
@requires_role("student")
def create_campaign():
    data = request.get_json() or {}
    title = data.get("title")
    description = data.get("description")
    goal_amount = data.get("goal_amount")
    deadline = data.get("deadline")

    if not title or not goal_amount:
        return jsonify({"msg": "Missing required fields"}), 400

    # identity
    identity = get_jwt_identity()
    try:
        student_id = int(identity)
    except Exception:
        return jsonify({"msg": "Invalid token identity"}), 401

    user = User.query.get(student_id)
    if not user:
        return jsonify({"msg": "User not found"}), 404
    if not user.verified:
        return jsonify({"msg": "Student not verified"}), 403

    # create campaign with pending status; admin must approve to activate
    campaign = Campaign(
        student_id=student_id,
        title=title,
        description=description,
        goal_amount=Decimal(str(goal_amount)),
        raised_amount=Decimal("0.00"),
        deadline=deadline,
        status=CampaignStatus.pending,
    )

    db.session.add(campaign)
    db.session.commit()

    return jsonify(campaign.to_dict()), 201


@bp.route("/campaigns", methods=["GET"])
def list_campaigns():
    # public list of active campaigns
    campaigns = Campaign.query.filter_by(status=CampaignStatus.active).all()
    return jsonify([c.to_dict() for c in campaigns])


@bp.route("/campaigns/<int:campaign_id>", methods=["GET"])
def get_campaign(campaign_id: int):
    c = Campaign.query.get(campaign_id)
    if not c:
        return jsonify({"msg": "Not found"}), 404

    # contributions summary
    total = db.session.query(db.func.coalesce(db.func.sum(Contribution.amount), 0)).filter(Contribution.campaign_id == c.id).scalar()
    count = Contribution.query.filter_by(campaign_id=c.id).count()

    result = c.to_dict()
    result.update({"contributions_count": count, "contributions_total": str(total)})
    return jsonify(result)


@bp.route("/admin/campaigns/<int:campaign_id>/approve", methods=["POST"])
@requires_role("admin")
def admin_approve_campaign(campaign_id: int):
    campaign = Campaign.query.get(campaign_id)
    if not campaign:
        return jsonify({"msg": "Not found"}), 404

    campaign.status = CampaignStatus.active
    db.session.add(campaign)

    # notify student
    note = Notification(user_id=campaign.student_id, message=f"Your campaign '{campaign.title}' was approved.", type=NotificationType.info, data={"campaign_id": campaign.id})
    db.session.add(note)

    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/admin/campaigns/<int:campaign_id>/reject", methods=["POST"])
@requires_role("admin")
def admin_reject_campaign(campaign_id: int):
    data = request.get_json() or {}
    reason = data.get("reason")
    if not reason:
        return jsonify({"msg": "Missing reason"}), 400

    campaign = Campaign.query.get(campaign_id)
    if not campaign:
        return jsonify({"msg": "Not found"}), 404

    campaign.status = CampaignStatus.failed
    db.session.add(campaign)

    note = Notification(user_id=campaign.student_id, message=f"Your campaign '{campaign.title}' was rejected: {reason}", type=NotificationType.info, data={"campaign_id": campaign.id, "reason": reason})
    db.session.add(note)

    db.session.commit()
    return jsonify({"ok": True})
