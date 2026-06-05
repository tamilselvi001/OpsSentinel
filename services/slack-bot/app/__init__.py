"""Slack human-in-the-loop gate — the asynchronous approve/reject gate for agent proposals.

Posts a plain-text decision brief (root cause, historical precedent, proposed fix, risk level) with
binary Approve/Reject buttons; on Approve publishes to opssentinel-actions (the Phase-3 executor's
channel), on Reject sets status=rejected. Both are audited. Signatures are verified.
"""
