"""Shared approval-state rules for immutable emission-factor versions."""


def is_factor_approved(factor, review_decision: str | None) -> bool:
    """Legacy verified factors remain usable; new factors need an approved review."""
    return bool(getattr(factor, "verified", False) or review_decision == "approved")


def factor_approval_status(factor, review_decision: str | None) -> str:
    if getattr(factor, "verified", False):
        return "approved"
    return review_decision or "pending"
