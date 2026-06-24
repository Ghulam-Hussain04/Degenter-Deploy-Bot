"""
app/services/withdraw_service.py

Selective withdrawal — supports all combinations:
  • Withdraw ALL funds
  • Withdraw ALL from a specific protocol       (protocol="Orca")
  • Withdraw FIXED AMOUNT from a protocol       (protocol="Orca", amount=50)
  • Withdraw PERCENTAGE from a protocol         (protocol="Orca", percent=50)
  • Withdraw ALL from a risk tier               (risk_profile="low")
  • Withdraw FIXED AMOUNT from total portfolio  (amount=200)  → deducts from unlocked positions highest-first

Since we're in mock/SQL mode:
  • "Withdraw" = subtract amount from user_positions.amount_usdc in DB
  • If remaining amount on a position becomes 0 → mark status="withdrawn"
  • If remaining amount > 0 → update amount_usdc to the remainder (partial)
  • Locked positions are always skipped with a clear message
"""

from datetime import datetime, timezone
from app.database import supabase
from app.services.positions_service import check_lock_status

# Maps risk profile string → allowed protocol names
RISK_FILTER = {
    "low":    ["Kamino", "Save"],
    "medium": ["Kamino", "Marginfi", "Save", "Raydium", "Orca"],
    "high":   ["Kamino", "Marginfi", "Save", "Raydium", "Orca", "Meteora"],
    "any":    ["Kamino", "Marginfi", "Save", "Raydium", "Orca", "Meteora"],
}

WITHDRAWAL_FEES = {
    "Kamino":   0.0,
    "Marginfi": 0.0,
    "Save":     0.0,
    "Raydium":  0.001,
    "Orca":     0.001,
    "Meteora":  0.002,
}


def _apply_fee(amount: float, protocol: str) -> dict:
    fee_rate = WITHDRAWAL_FEES.get(protocol, 0.0)
    fee = round(amount * fee_rate, 4)
    net = round(amount - fee, 4)
    return {"gross": amount, "fee": fee, "net": net, "fee_rate": fee_rate}


def _validate_user(user_id: str):
    user = supabase.table("users").select("id").eq("id", user_id).execute()
    if not user.data:
        raise ValueError(f"User {user_id} not found")


def _get_active_positions(user_id: str) -> list:
    result = supabase.table("user_positions") \
        .select("*") \
        .eq("user_id", user_id) \
        .eq("status", "active") \
        .execute()
    return result.data or []


def _split_locked(positions: list):
    """Separate positions into unlocked and locked lists."""
    unlocked, locked = [], []
    for pos in positions:
        is_locked, days_remaining = check_lock_status(pos.get("lock_until"))
        if is_locked:
            locked.append({**pos, "days_remaining": days_remaining})
        else:
            unlocked.append(pos)
    return unlocked, locked


def _build_locked_info(locked_positions: list) -> list:
    return [
        {
            "position_id": p["id"],
            "protocol": p["protocol_name"],
            "amount": float(p["amount_usdc"]),
            "days_remaining": p["days_remaining"],
            "lock_until": p.get("lock_until"),
        }
        for p in locked_positions
    ]


# ─────────────────────────────────────────────────────────────────────────────
# PREPARE — builds withdrawal plan, does NOT touch DB yet
# ─────────────────────────────────────────────────────────────────────────────

async def prepare_withdraw(
    user_id: str,
    protocol: str = None,       # e.g. "Orca" — target a specific protocol
    risk_profile: str = None,   # e.g. "low"  — target all low-risk positions
    amount: float = None,       # fixed USDC amount to withdraw
    percent: float = None,      # 0–100 percentage of eligible positions
):
    """
    Build a withdrawal plan based on the filters provided.

    Priority logic:
      1. protocol + amount  → withdraw $X from that protocol
      2. protocol + percent → withdraw X% from that protocol
      3. protocol only      → withdraw ALL from that protocol
      4. risk_profile       → withdraw ALL from that risk tier
      5. amount only        → withdraw $X from total portfolio (unlocked, highest amount first)
      6. percent only       → withdraw X% from every unlocked position
      7. nothing            → withdraw ALL unlocked positions
    """
    _validate_user(user_id)

    all_positions = _get_active_positions(user_id)
    if not all_positions:
        raise ValueError("No active positions found")

    # ── Step 1: filter by protocol or risk_profile ─────────────────────────
    if protocol:
        proto_canonical = protocol.strip().capitalize()
        # Handle casing like "orca" → "Orca", "raydium" → "Raydium"
        # Find exact match case-insensitively
        matched = next(
            (p for p in ["Kamino","Marginfi","Save","Raydium","Orca","Meteora"]
             if p.lower() == protocol.strip().lower()),
            None
        )
        if not matched:
            raise ValueError(f"Unknown protocol '{protocol}'")
        candidate_positions = [p for p in all_positions if p["protocol_name"] == matched]
        if not candidate_positions:
            raise ValueError(f"No active positions found in {matched}")
    elif risk_profile:
        norm = risk_profile.strip().lower()
        if norm not in RISK_FILTER:
            raise ValueError(f"Invalid risk profile '{risk_profile}'. Use: any, low, medium, high")
        allowed = RISK_FILTER[norm]
        candidate_positions = [p for p in all_positions if p["protocol_name"] in allowed]
        if not candidate_positions:
            raise ValueError(f"No active positions found for risk profile '{risk_profile}'")
    else:
        candidate_positions = all_positions

    # ── Step 2: separate locked vs unlocked ────────────────────────────────
    unlocked, locked = _split_locked(candidate_positions)

    if not unlocked:
        locked_info = _build_locked_info(locked)
        raise ValueError(
            f"All matching positions are locked. "
            f"Earliest unlock: {min(p['days_remaining'] for p in locked_info)} day(s)."
        )

    # Sort unlocked by amount desc (deduct from largest positions first)
    unlocked.sort(key=lambda x: float(x["amount_usdc"]), reverse=True)

    # ── Step 3: calculate how much to withdraw from each position ──────────
    withdraw_plan = []  # list of {position, withdraw_amount, remaining_amount}

    if protocol and amount:
        # Withdraw fixed $ from this protocol
        total_available = sum(float(p["amount_usdc"]) for p in unlocked)
        if amount > total_available:
            raise ValueError(
                f"Requested ${amount} but only ${round(total_available, 2)} available in {matched}"
            )
        remaining_to_deduct = amount
        for pos in unlocked:
            if remaining_to_deduct <= 0:
                break
            pos_amount = float(pos["amount_usdc"])
            deduct = min(pos_amount, remaining_to_deduct)
            remaining_after = round(pos_amount - deduct, 4)
            withdraw_plan.append({
                "position": pos,
                "withdraw_amount": round(deduct, 4),
                "remaining_amount": remaining_after,
            })
            remaining_to_deduct = round(remaining_to_deduct - deduct, 4)

    elif protocol and percent:
        # Withdraw X% from each position in this protocol
        if not 0 < percent <= 100:
            raise ValueError("Percent must be between 0 and 100")
        for pos in unlocked:
            pos_amount = float(pos["amount_usdc"])
            deduct = round(pos_amount * percent / 100, 4)
            remaining_after = round(pos_amount - deduct, 4)
            withdraw_plan.append({
                "position": pos,
                "withdraw_amount": deduct,
                "remaining_amount": remaining_after,
            })

    elif protocol:
        # Withdraw ALL from this protocol
        for pos in unlocked:
            withdraw_plan.append({
                "position": pos,
                "withdraw_amount": float(pos["amount_usdc"]),
                "remaining_amount": 0.0,
            })

    elif risk_profile:
        # Withdraw ALL from risk tier (amount/percent on risk not yet supported — can add)
        for pos in unlocked:
            withdraw_plan.append({
                "position": pos,
                "withdraw_amount": float(pos["amount_usdc"]),
                "remaining_amount": 0.0,
            })

    elif amount:
        # Withdraw fixed $ from total portfolio, deducting from largest positions first
        total_available = sum(float(p["amount_usdc"]) for p in unlocked)
        if amount > total_available:
            raise ValueError(
                f"Requested ${amount} but only ${round(total_available, 2)} is available (unlocked)"
            )
        remaining_to_deduct = amount
        for pos in unlocked:
            if remaining_to_deduct <= 0:
                break
            pos_amount = float(pos["amount_usdc"])
            deduct = min(pos_amount, remaining_to_deduct)
            remaining_after = round(pos_amount - deduct, 4)
            withdraw_plan.append({
                "position": pos,
                "withdraw_amount": round(deduct, 4),
                "remaining_amount": remaining_after,
            })
            remaining_to_deduct = round(remaining_to_deduct - deduct, 4)

    elif percent:
        # Withdraw X% from every unlocked position
        if not 0 < percent <= 100:
            raise ValueError("Percent must be between 0 and 100")
        for pos in unlocked:
            pos_amount = float(pos["amount_usdc"])
            deduct = round(pos_amount * percent / 100, 4)
            remaining_after = round(pos_amount - deduct, 4)
            withdraw_plan.append({
                "position": pos,
                "withdraw_amount": deduct,
                "remaining_amount": remaining_after,
            })

    else:
        # Withdraw ALL unlocked
        for pos in unlocked:
            withdraw_plan.append({
                "position": pos,
                "withdraw_amount": float(pos["amount_usdc"]),
                "remaining_amount": 0.0,
            })

    # ── Step 4: build response with fee breakdown ──────────────────────────
    withdrawable = []
    total_gross = 0.0
    total_net = 0.0

    for item in withdraw_plan:
        pos = item["position"]
        gross = item["withdraw_amount"]
        fee_info = _apply_fee(gross, pos["protocol_name"])
        total_gross += gross
        total_net += fee_info["net"]

        withdrawable.append({
            "position_id": pos["id"],
            "protocol": pos["protocol_name"],
            "gross_amount": gross,
            "fee": fee_info["fee"],
            "amount_after_fee": fee_info["net"],
            "remaining_in_position": item["remaining_amount"],
            "fully_closing": item["remaining_amount"] == 0.0,
        })

    locked_info = _build_locked_info(locked)

    return {
        "success": True,
        "user_id": user_id,
        "withdrawable": withdrawable,
        "locked": locked_info,
        "total_gross": round(total_gross, 2),
        "total_fees": round(total_gross - total_net, 4),
        "total_withdrawable": round(total_net, 2),
        "total_locked": round(sum(p["amount"] for p in locked_info), 2),
        "message": (
            f"Ready to withdraw ${round(total_net, 2)} "
            f"({len(withdrawable)} position(s) affected). "
            + (f"{len(locked_info)} position(s) locked." if locked_info else "")
        ).strip()
    }


# ─────────────────────────────────────────────────────────────────────────────
# CONFIRM — executes the withdrawal plan against the DB
# ─────────────────────────────────────────────────────────────────────────────

async def confirm_withdraw(
    user_id: str,
    withdrawable: list,   # list of {position_id, withdraw_amount, remaining_in_position}
    tx_signatures: list,
):
    """
    Execute withdrawal plan:
    - If remaining_in_position == 0 → mark position status="withdrawn"
    - If remaining_in_position > 0  → update amount_usdc to remainder (partial withdraw)
    """
    _validate_user(user_id)

    if not withdrawable:
        raise ValueError("No withdrawal items provided")

    confirmed = []
    total_withdrawn = 0.0

    for i, item in enumerate(withdrawable):
        position_id = item["position_id"]
        withdraw_amount = float(item["withdraw_amount"])
        remaining = float(item["remaining_in_position"])
        tx_sig = tx_signatures[i] if i < len(tx_signatures) else f"mock_sig_{i}"

        # Verify position belongs to this user and is active
        pos = supabase.table("user_positions") \
            .select("*") \
            .eq("id", position_id) \
            .eq("user_id", user_id) \
            .eq("status", "active") \
            .execute()

        if not pos.data:
            raise ValueError(f"Position {position_id} not found or not active for this user")

        pos_data = pos.data[0]

        # Double-check the lock hasn't changed
        is_locked, days_remaining = check_lock_status(pos_data.get("lock_until"))
        if is_locked:
            raise ValueError(
                f"Position in {pos_data['protocol_name']} is locked for {days_remaining} more day(s)"
            )

        if remaining == 0.0:
            # Full withdrawal of this position
            supabase.table("user_positions") \
                .update({"status": "withdrawn", "tx_signature": tx_sig}) \
                .eq("id", position_id) \
                .execute()
        else:
            # Partial withdrawal — reduce amount, keep active
            supabase.table("user_positions") \
                .update({
                    "amount_usdc": remaining,
                    "tx_signature": tx_sig
                }) \
                .eq("id", position_id) \
                .execute()

        fee_info = _apply_fee(withdraw_amount, pos_data["protocol_name"])
        total_withdrawn += fee_info["net"]

        confirmed.append({
            "position_id": position_id,
            "protocol": pos_data["protocol_name"],
            "withdrawn_amount": withdraw_amount,
            "fee": fee_info["fee"],
            "received": fee_info["net"],
            "remaining_in_position": remaining,
            "status": "withdrawn" if remaining == 0.0 else "partial",
            "tx_signature": tx_sig,
        })

    return {
        "success": True,
        "user_id": user_id,
        "confirmed_withdrawals": confirmed,
        "total_received": round(total_withdrawn, 2),
        "message": f"✅ Withdrawn ${round(total_withdrawn, 2)} successfully across {len(confirmed)} position(s)."
    }