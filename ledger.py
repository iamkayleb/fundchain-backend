"""Ledger helper utilities.

Provides append_tx, get_chain, verify_chain and a simple anchor_chain stub.
This module uses the Ledger model defined in `backend.models` and re-uses
the same hash computation function for compatibility.
"""
from typing import Tuple, List, Dict, Any
import hashlib
from datetime import datetime
import json

from sqlalchemy import event

from backend.models import db, Ledger, TxTypeEnum, compute_ledger_hash


def _canonical_payload(payload: dict) -> str:
    """Return a stable string representation of payload for hashing."""
    try:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))
    except Exception:
        return str(payload)


def append_tx(tx_type: str, payload: dict) -> Ledger:
    """Append a transaction to the ledger and return the Ledger row.

    tx_type must be one of the values in TxTypeEnum.
    The function computes prev_hash from the last row and creates a new
    Ledger row with a computed hash. Returns the newly created Ledger.
    """
    # resolve enum
    try:
        tx_enum = TxTypeEnum(tx_type)
    except Exception:
        # allow passing either enum value or name
        try:
            tx_enum = TxTypeEnum[tx_type]
        except Exception:
            raise ValueError(f"Invalid tx_type: {tx_type}")

    # obtain last hash
    last_hash = db.session.query(Ledger.hash).order_by(Ledger.id.desc()).limit(1).scalar()

    # compute hash using the project's canonical function for compatibility
    # compute_ledger_hash expects (prev_hash, payload)
    new_hash = compute_ledger_hash(last_hash, payload)

    # create ledger row
    entry = Ledger(tx_type=tx_enum, payload=payload, prev_hash=last_hash, hash=new_hash, timestamp=datetime.utcnow())
    db.session.add(entry)
    db.session.commit()
    return entry


def get_chain() -> List[Dict[str, Any]]:
    """Return the ledger entries as ordered list of dicts (ascending id)."""
    rows = Ledger.query.order_by(Ledger.id.asc()).all()
    out = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "tx_type": getattr(r.tx_type, "value", str(r.tx_type)),
                "payload": r.payload,
                "prev_hash": r.prev_hash,
                "hash": r.hash,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            }
        )
    return out


def verify_chain() -> Tuple[bool, List[int]]:
    """Verify the ledger integrity.

    Returns (is_valid, broken_indices) where broken_indices is a list of
    ledger ids whose hash doesn't match the recomputed value.
    """
    broken = []
    rows = Ledger.query.order_by(Ledger.id.asc()).all()
    prev = None
    for r in rows:
        # recompute hash using same method
        expected = compute_ledger_hash(prev, r.payload)
        if r.hash != expected:
            broken.append(r.id)
        prev = r.hash

    return (len(broken) == 0, broken)


def anchor_chain() -> str:
    """Compute and return a root hash for the chain (stub).

    TODO: implement anchoring to a public blockchain or timestamping service.
    """
    last_hash = db.session.query(Ledger.hash).order_by(Ledger.id.desc()).limit(1).scalar()
    return last_hash or ""


def _prevent_ledger_update(mapper, connection, target):
    # simple guard: raise on attempts to UPDATE a Ledger row
    raise RuntimeError("Ledger is append-only; updates are not allowed")


# Attach listener to prevent updates to ledger rows
event.listen(Ledger, "before_update", _prevent_ledger_update)


__all__ = ["append_tx", "get_chain", "verify_chain", "anchor_chain"]
