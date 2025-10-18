"""SQLAlchemy models for the crowdfunding platform.

This module uses Flask-SQLAlchemy idioms. It defines the core domain
models: User, InstitutionProfile, VerificationRequest, Campaign,
Contribution, Ledger, and Notification. Each model includes a `to_dict()`
helper that excludes sensitive fields (like password_hash).
"""
from datetime import datetime
from decimal import Decimal
import enum

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.dialects.sqlite import JSON as SQLITE_JSON
from sqlalchemy.types import TypeDecorator, Numeric


# Use the usual Flask-SQLAlchemy pattern
db = SQLAlchemy()


class RoleEnum(enum.Enum):
    student = "student"
    donor = "donor"
    institution = "institution"
    admin = "admin"


class VerificationRoleEnum(enum.Enum):
    student = "student"
    institution = "institution"


class VerificationStatus(enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class CampaignStatus(enum.Enum):
    draft = "draft"
    pending = "pending"
    active = "active"
    successful = "successful"
    failed = "failed"


class ContributionStatus(enum.Enum):
    pending = "pending"
    locked = "locked"
    disbursed = "disbursed"
    refunded = "refunded"


class TxTypeEnum(enum.Enum):
    lock = "lock"
    disburse = "disburse"
    refund = "refund"
    student_verified = "student_verified"
    institution_verified = "institution_verified"


class PaymentMethodEnum(enum.Enum):
    paystack = "paystack"
    crypto = "crypto"
    manual = "manual"


class NotificationType(enum.Enum):
    info = "info"
    fraud_alert = "fraud_alert"
    verification = "verification"


class NumericAsDecimal(TypeDecorator):
    """TypeDecorator to return Decimal from Numeric columns."""

    impl = Numeric

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        return Decimal(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return Decimal(value)


def now():
    return datetime.utcnow()


class User(db.Model):
    """A user of the platform. Roles: student, donor, institution, admin.

    The `extra` JSON column holds role-specific metadata (e.g. institution
    registration details, student ID uploads).
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(RoleEnum), nullable=False, default=RoleEnum.donor)
    verified = db.Column(db.Boolean, nullable=False, default=False)
    extra = db.Column(SQLITE_JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    updated_at = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)

    # relationships
    institution_profile = db.relationship(
        "InstitutionProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    campaigns = db.relationship("Campaign", back_populates="student", lazy="dynamic")
    contributions = db.relationship("Contribution", back_populates="donor", lazy="dynamic")

    # admin reviewer relationships for verification requests
    reviewed_requests = db.relationship(
        "VerificationRequest",
        back_populates="reviewed_by_user",
        foreign_keys="VerificationRequest.reviewed_by",
        lazy="dynamic",
    )

    def to_dict(self, include_email=True):
        """Return a dict representation, excluding password_hash by default."""
        data = {
            "id": self.id,
            "full_name": self.full_name,
            "role": self.role.value if self.role else None,
            "verified": self.verified,
            "extra": self.extra,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_email:
            data["email"] = self.email
        return data





class InstitutionProfile(db.Model):
    """One-to-one profile for institution users. Contains accreditation and bank details."""

    __tablename__ = "institution_profiles"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    institution_name = db.Column(db.String(255), nullable=False)
    email_domain = db.Column(db.String(255), nullable=True)
    bank_account_details = db.Column(SQLITE_JSON, nullable=True)
    accreditation_docs = db.Column(SQLITE_JSON, nullable=True)
    verified = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    updated_at = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)

    user = db.relationship("User", back_populates="institution_profile")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "institution_name": self.institution_name,
            "email_domain": self.email_domain,
            "bank_account_details": self.bank_account_details,
            "accreditation_docs": self.accreditation_docs,
            "verified": self.verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class VerificationRequest(db.Model):
    """Represents a verification request for students or institutions."""

    __tablename__ = "verification_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = db.Column(db.Enum(VerificationRoleEnum), nullable=False)
    document_urls = db.Column(SQLITE_JSON, nullable=True)
    status = db.Column(db.Enum(VerificationStatus), nullable=False, default=VerificationStatus.pending)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    updated_at = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)

    user = db.relationship("User", foreign_keys=[user_id])
    reviewed_by_user = db.relationship("User", foreign_keys=[reviewed_by])

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "role": self.role.value if self.role else None,
            "document_urls": self.document_urls,
            "status": self.status.value if self.status else None,
            "reviewed_by": self.reviewed_by,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Campaign(db.Model):
    """A student-created fundraising campaign."""

    __tablename__ = "campaigns"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    goal_amount = db.Column(Numeric(18, 2), nullable=False)
    raised_amount = db.Column(Numeric(18, 2), nullable=False, default=Decimal("0.00"))
    deadline = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.Enum(CampaignStatus), nullable=False, default=CampaignStatus.draft)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    updated_at = db.Column(db.DateTime, nullable=False, default=now, onupdate=now)

    student = db.relationship("User", back_populates="campaigns")
    contributions = db.relationship("Contribution", back_populates="campaign", lazy="dynamic")

    def to_dict(self, include_description=True):
        return {
            "id": self.id,
            "student_id": self.student_id,
            "title": self.title,
            "description": self.description if include_description else None,
            "goal_amount": str(self.goal_amount) if self.goal_amount is not None else None,
            "raised_amount": str(self.raised_amount) if self.raised_amount is not None else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "status": self.status.value if self.status else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Contribution(db.Model):
    """A donor's contribution toward a campaign."""

    __tablename__ = "contributions"

    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = db.Column(Numeric(18, 2), nullable=False)
    status = db.Column(db.Enum(ContributionStatus), nullable=False, default=ContributionStatus.pending)
    tx_hash = db.Column(db.String(255), nullable=True)
    ip_address = db.Column(db.String(100), nullable=True)
    payment_card = db.Column(db.String(100), nullable=True)
    payment_method = db.Column(db.Enum(PaymentMethodEnum), nullable=False, default=PaymentMethodEnum.paystack)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    donor = db.relationship("User", back_populates="contributions")
    campaign = db.relationship("Campaign", back_populates="contributions")

    def to_dict(self):
        return {
            "id": self.id,
            "donor_id": self.donor_id,
            "campaign_id": self.campaign_id,
            "amount": str(self.amount) if self.amount is not None else None,
            "status": self.status.value if self.status else None,
            "tx_hash": self.tx_hash,
            "payment_method": self.payment_method.value if self.payment_method else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Ledger(db.Model):
    """Immutable ledger table that stores transaction events for transparency.

    Each row contains a payload JSON, a pointer to previous hash, and a calculated
    hash for simple tamper-evidence.
    """

    __tablename__ = "ledger"

    id = db.Column(db.Integer, primary_key=True)
    tx_type = db.Column(db.Enum(TxTypeEnum), nullable=False)
    payload = db.Column(SQLITE_JSON, nullable=False)
    prev_hash = db.Column(db.String(128), nullable=True)
    hash = db.Column(db.String(128), nullable=False, unique=True, index=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=now)

    def to_dict(self):
        return {
            "id": self.id,
            "tx_type": self.tx_type.value if self.tx_type else None,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "hash": self.hash,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class Notification(db.Model):
    """User-facing notifications stored for display in-app."""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.Enum(NotificationType), nullable=False, default=NotificationType.info)
    data = db.Column(SQLITE_JSON, nullable=True)
    seen = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)

    user = db.relationship("User")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "message": self.message,
            "type": self.type.value if self.type else None,
            "data": self.data,
            "seen": self.seen,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# Simple helper to create a ledger hash; in production this would be a
# cryptographic hash over canonicalized payloads and prev_hash. Here we
# compute a simple hash to keep the ledger append-only semantics.
import hashlib


def compute_ledger_hash(prev_hash: str, payload: dict) -> str:
    hasher = hashlib.sha256()
    if prev_hash:
        hasher.update(prev_hash.encode("utf-8"))
    hasher.update(str(payload).encode("utf-8"))
    return hasher.hexdigest()


@event.listens_for(Ledger, "before_insert")
def _ledger_before_insert(mapper, connection, target):
    # compute hash if not provided
    if not target.hash:
        # fetch last hash from DB
        last = connection.execute(db.select(Ledger.hash).order_by(Ledger.id.desc()).limit(1)).scalar()
        target.prev_hash = last
        target.hash = compute_ledger_hash(last, target.payload)


__all__ = [
    "db",
    "User",
    "InstitutionProfile",
    "VerificationRequest",
    "Campaign",
    "Contribution",
    "Ledger",
    "Notification",
]
