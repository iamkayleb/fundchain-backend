"""Donation endpoints, payment simulation, and webhook handling.

Endpoints:
- POST /api/campaigns/<int:id>/donate
- POST /api/donations/verify
- POST /api/admin/finalize/<int:campaign_id>
"""
import uuid
import logging
from decimal import Decimal
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import (
    db,
    Campaign,
    Contribution,
    Ledger,
    TxTypeEnum,
    Notification,
    NotificationType,
    User,
)
from routes.auth import requires_role

bp = Blueprint("donations", __name__, url_prefix="/api")
logger = logging.getLogger(__name__)


@bp.route("/campaigns/<int:campaign_id>/donate", methods=["POST"])
@jwt_required(optional=True)
def donate(campaign_id: int):
    data = request.get_json() or {}
    amount = data.get("amount")
    payment_method = data.get("payment_method")
    ip_address = request.remote_addr
    payment_card = data.get("payment_card")

    if amount is None or payment_method not in ("paystack", "crypto", "manual"):
        return jsonify({"msg": "Missing amount or invalid payment_method"}), 400

    # donor may be authenticated or provide donor_id
    donor_id = data.get("donor_id")
    if not donor_id:
        identity = get_jwt_identity()
        if identity:
            donor_id = int(identity)

    campaign = Campaign.query.get(campaign_id)
    if not campaign:
        return jsonify({"msg": "Campaign not found"}), 404

    # create contribution pending
    contrib = Contribution(
        donor_id=donor_id,
        campaign_id=campaign_id,
        amount=Decimal(str(amount)),
        status="pending",
        payment_method=payment_method,
        ip_address=ip_address,
        payment_card=payment_card,
    )
    db.session.add(contrib)
    db.session.commit()

    # ledger lock entry
    payload = {"contribution_id": contrib.id, "donor_id": donor_id, "campaign_id": campaign_id, "amount": str(contrib.amount), "method": payment_method}
    ledger = Ledger(tx_type=TxTypeEnum.lock, payload=payload)
    db.session.add(ledger)
    db.session.commit()

    # simple fraud checks
    try:
        from datetime import datetime, timedelta

        T_minutes = current_app.config.get("FRAUD_WINDOW_MINUTES", 2)
        N_threshold = current_app.config.get("FRAUD_THRESHOLD", 3)
        window_start = datetime.utcnow() - timedelta(minutes=T_minutes)

        # donations by same donor in window
        recent_count = Contribution.query.filter(
            Contribution.donor_id == donor_id,
            Contribution.created_at >= window_start,
        ).count()
        suspicious = False
        flagged_contribs = []
        if recent_count >= N_threshold:
            suspicious = True
            flagged_contribs = [c.id for c in Contribution.query.filter(Contribution.donor_id == donor_id).order_by(Contribution.created_at.desc()).limit(N_threshold).all()]

        # multiple contributions from same IP in quick succession
        if ip_address:
            ip_recent = Contribution.query.filter(
                Contribution.ip_address == ip_address,
                Contribution.created_at >= window_start,
            ).count()
            if ip_recent >= N_threshold:
                suspicious = True
                flagged_contribs = flagged_contribs or []
                flagged_contribs += [c.id for c in Contribution.query.filter(Contribution.ip_address == ip_address).order_by(Contribution.created_at.desc()).limit(N_threshold).all()]

        # multiple contributions with same card
        if payment_card:
            card_recent = Contribution.query.filter(
                Contribution.payment_card == payment_card,
                Contribution.created_at >= window_start,
            ).count()
            if card_recent >= N_threshold:
                suspicious = True
                flagged_contribs = flagged_contribs or []
                flagged_contribs += [c.id for c in Contribution.query.filter(Contribution.payment_card == payment_card).order_by(Contribution.created_at.desc()).limit(N_threshold).all()]

        if suspicious:
            # notify admins
            admins = User.query.filter_by(role="admin").all()
            for a in admins:
                note = Notification(user_id=a.id, message="Suspicious donation activity detected", type=NotificationType.fraud_alert, data={"contributions": flagged_contribs})
                db.session.add(note)
            db.session.commit()
    except Exception as e:
        logger.exception("Fraud check failed")

    # simulate payment initiation
    if payment_method == "paystack":
        checkout = f"https://paystack.mock/checkout/{uuid.uuid4().hex}"
        return jsonify({"checkout_url": checkout, "contribution_id": contrib.id})
    elif payment_method == "crypto":
        address = f"0x{uuid.uuid4().hex[:40]}"
        return jsonify({"payment_address": address, "contribution_id": contrib.id})
    else:
        return jsonify({"ok": True, "contribution_id": contrib.id})


@bp.route("/donations/verify", methods=["POST"])
def donations_verify():
    data = request.get_json() or {}
    contribution_id = data.get("contribution_id")
    tx_hash = data.get("tx_hash")
    success = data.get("success")

    if contribution_id is None or success is None:
        return jsonify({"msg": "Missing fields"}), 400

    contrib = Contribution.query.get(contribution_id)
    if not contrib:
        return jsonify({"msg": "Contribution not found"}), 404

    if success:
        contrib.status = "locked"
        if tx_hash:
            contrib.tx_hash = tx_hash
        # atomically update campaign raised_amount
        campaign = Campaign.query.get(contrib.campaign_id)
        if campaign:
            # ensure Decimal addition
            campaign.raised_amount = (campaign.raised_amount or Decimal("0.00")) + contrib.amount
            db.session.add(campaign)
        db.session.add(contrib)
        db.session.commit()
        return jsonify({"ok": True})
    else:
        contrib.status = "failed"
        db.session.add(contrib)
        db.session.commit()
        return jsonify({"ok": False})


@bp.route("/admin/finalize/<int:campaign_id>", methods=["POST"])
@requires_role("admin")
def finalize_campaign(campaign_id: int):
    data = request.get_json() or {}
    force = data.get("force", False)

    campaign = Campaign.query.get(campaign_id)
    if not campaign:
        return jsonify({"msg": "Campaign not found"}), 404

    # decide if successful: goal reached or forced
    goal_reached = (campaign.goal_amount is not None and campaign.raised_amount >= campaign.goal_amount)
    if not goal_reached and not force:
        return jsonify({"msg": "Goal not reached"}), 400

    # fetch locked contributions
    locked = Contribution.query.filter_by(campaign_id=campaign_id, status="locked").all()

    if goal_reached or force:
        # disburse each
        for c in locked:
            c.status = "disbursed"
            db.session.add(c)
            # ledger entry per disbursement
            payload = {"contribution_id": c.id, "campaign_id": campaign_id, "amount": str(c.amount)}
            ledger = Ledger(tx_type=TxTypeEnum.disburse, payload=payload)
            db.session.add(ledger)
            # simulate transfer (TODO: integrate with Paystack/crypto transfer API here)
            logger.info(f"Simulated transfer for contribution {c.id} amount={c.amount}")

        # notify student
        note = Notification(user_id=campaign.student_id, message=f"Your campaign '{campaign.title}' has been disbursed.", type=NotificationType.info, data={"campaign_id": campaign.id})
        db.session.add(note)
        campaign.status = "successful"
        db.session.add(campaign)
        db.session.commit()
        return jsonify({"ok": True, "disbursed_count": len(locked)})
    else:
        # refunds
        for c in locked:
            c.status = "refunded"
            db.session.add(c)
            payload = {"contribution_id": c.id, "campaign_id": campaign_id, "amount": str(c.amount)}
            ledger = Ledger(tx_type=TxTypeEnum.refund, payload=payload)
            db.session.add(ledger)
            logger.info(f"Simulated refund for contribution {c.id} amount={c.amount}")

        campaign.status = "failed"
        db.session.add(campaign)
        db.session.commit()
        return jsonify({"ok": True, "refunded_count": len(locked)})


@bp.route("/admin/notifications", methods=["GET"])
@requires_role("admin")
def admin_notifications():
    notes = Notification.query.filter_by(type=NotificationType.fraud_alert).order_by(Notification.created_at.desc()).all()
    return jsonify([n.to_dict() for n in notes])


@bp.route("/notifications", methods=["GET"])
@jwt_required()
def my_notifications():
    identity = get_jwt_identity()
    try:
        user_id = int(identity)
    except Exception:
        return jsonify({"msg": "Invalid token identity"}), 401
    notes = Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).all()
    return jsonify([n.to_dict() for n in notes])
