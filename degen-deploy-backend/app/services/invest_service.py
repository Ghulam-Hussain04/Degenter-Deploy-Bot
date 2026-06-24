from datetime import datetime, timedelta, timezone
from app.services.apy_service import get_top_protocols, get_all_apys
from app.database import supabase
from typing import Optional

VALID_PROTOCOLS = ["Kamino", "Marginfi", "Save", "Raydium", "Orca", "Meteora"]

def calculate_weighted_apy(positions: list) -> float:
    """
    Calculate weighted average APY across positions
    """
    total_amount = sum(p["amount"] for p in positions)
    if total_amount == 0:
        return 0.0
    
    weighted = sum(p["amount"] * p["apy"] for p in positions)
    return round(weighted / total_amount, 2)


def calculate_lock_until(lock_days: int) -> Optional[str]:
    """
    Calculate lock end date based on lock period
    """
    if lock_days == 0:
        return None
    unlock_date = datetime.now(timezone.utc) + timedelta(days=lock_days)
    return unlock_date.isoformat()


def split_equally(amount: float, n: int) -> list:
    """
    Split amount equally across n protocols
    Handles rounding (last position gets remainder)
    """
    if n == 0:
        return []
    
    base = round(amount / n, 2)
    amounts = [base] * n
    
    # Give remainder to last position to avoid rounding issues
    total_assigned = base * n
    remainder = round(amount - total_assigned, 2)
    amounts[-1] = round(amounts[-1] + remainder, 2)
    
    return amounts


async def prepare_invest(user_id: str, amount: float, risk_profile: str):
    """
    Core invest logic:
    1. Validate user exists
    2. Get top 3 protocols for risk profile
    3. Split amount equally
    4. Save positions as 'pending' in DB
    5. Return position details
    """

    # Step 1 — Validate user exists
    user = supabase.table("users") \
        .select("*") \
        .eq("id", user_id) \
        .execute()

    if not user.data or len(user.data) == 0:
        raise ValueError(f"User {user_id} not found")

    # Step 2 — Get top 3 protocols filtered by risk
    top_protocols = await get_top_protocols(risk_profile, top_n=3)

    if not top_protocols:
        raise ValueError(f"No protocols available for risk profile: {risk_profile}")

    # Step 3 — Split amount equally
    n = len(top_protocols)
    amounts = split_equally(amount, n)

    # Step 4 — Build positions + save to DB as pending
    positions = []
    db_records = []

    for i, protocol in enumerate(top_protocols):
        lock_until = calculate_lock_until(protocol["lock_days"])

        position = {
            "protocol": protocol["protocol"],
            "amount": amounts[i],
            "apy": protocol["apy"],
            "lock_days": protocol["lock_days"],
            "lock_until": lock_until
        }
        positions.append(position)

        # DB record
        db_records.append({
            "user_id": user_id,
            "protocol_name": protocol["protocol"],
            "protocol_type": protocol["type"],
            "amount_usdc": amounts[i],
            "apy_at_deposit": protocol["apy"],
            "lock_until": lock_until,
            "status": "pending"
        })

    # Save all positions to DB
    saved = supabase.table("user_positions") \
        .insert(db_records) \
        .execute()

    if not saved.data:
        raise Exception("Failed to save positions to database")

    # Step 5 — Calculate weighted APY + return
    weighted_apy = calculate_weighted_apy(positions)

    return {
        "success": True,
        "user_id": user_id,
        "total_amount": amount,
        "risk_profile": risk_profile,
        "weighted_apy": weighted_apy,
        "positions": positions,
        "pending_position_ids": [r["id"] for r in saved.data],
        "message": f"Ready to invest ${amount} across {n} protocols at {weighted_apy}% weighted APY. Please sign the transactions."
    }


async def confirm_invest(user_id: str, position_ids: list, tx_signatures: list):
    """
    Confirm investment after user signs transactions:
    1. Validate position IDs belong to this user
    2. Match each position with its tx signature
    3. Mark positions as active in DB
    4. Return confirmed positions
    """

    # Step 1 — Fetch positions from DB
    positions = supabase.table("user_positions") \
        .select("*") \
        .in_("id", position_ids) \
        .eq("user_id", user_id) \
        .eq("status", "pending") \
        .execute()

    if not positions.data:
        raise ValueError("No pending positions found for this user")

    if len(positions.data) != len(tx_signatures):
        raise ValueError(
            f"Mismatch: {len(positions.data)} positions but {len(tx_signatures)} signatures"
        )

    # Step 2 — Update each position with tx signature + mark active
    confirmed = []

    for i, position in enumerate(positions.data):
        tx_sig = tx_signatures[i]

        # Update position in DB
        updated = supabase.table("user_positions") \
            .update({
                "status": "active",
                "tx_signature": tx_sig
            }) \
            .eq("id", position["id"]) \
            .execute()

        confirmed.append({
            "position_id": position["id"],
            "protocol": position["protocol_name"],
            "amount": position["amount_usdc"],
            "apy": position["apy_at_deposit"],
            "status": "active",
            "tx_signature": tx_sig
        })

    # Step 3 — Calculate total invested
    total_invested = sum(p["amount_usdc"] for p in positions.data)

    return {
        "success": True,
        "user_id": user_id,
        "confirmed_positions": confirmed,
        "total_invested": total_invested,
        "message": f"✅ Investment confirmed! ${total_invested} deployed across {len(confirmed)} protocols."
    }


# ── Custom invest — specific protocols + amounts ──────────────────────────────

async def prepare_invest_custom(user_id: str, allocations: list):
    """
    Invest in user-specified protocols with user-specified amounts.
    allocations: [{"protocol": "Kamino", "amount": 100}, ...]

    Differences from prepare_invest:
    - No risk filter — user picks exact protocols
    - No equal split — user provides exact amounts per protocol
    - Supports any number of protocols (1, 2, 3, ...)
    - Confirm flow is identical (same pending_position_ids shape)
    """

    # Validate user
    user = supabase.table("users").select("*").eq("id", user_id).execute()
    if not user.data:
        raise ValueError(f"User {user_id} not found")

    if not allocations:
        raise ValueError("At least one allocation is required")

    # Get current APYs for all protocols
    all_apys = await get_all_apys()
    apy_map = {p["protocol"]: p for p in all_apys}

    positions = []
    db_records = []
    total_amount = 0.0

    for alloc in allocations:
        raw_protocol = str(alloc.get("protocol", "")).strip()
        amount = float(alloc.get("amount", 0))

        # Case-insensitive protocol matching
        matched = next(
            (p for p in VALID_PROTOCOLS if p.lower() == raw_protocol.lower()),
            None
        )
        if not matched:
            raise ValueError(
                f"Unknown protocol '{raw_protocol}'. "
                f"Valid options: {', '.join(VALID_PROTOCOLS)}"
            )

        if amount <= 0:
            raise ValueError(f"Amount for {matched} must be greater than 0")

        proto_data = apy_map.get(matched)
        if not proto_data:
            raise ValueError(f"APY data for {matched} is currently unavailable")

        lock_until = calculate_lock_until(proto_data["lock_days"])

        positions.append({
            "protocol": matched,
            "amount": round(amount, 2),
            "apy": proto_data["apy"],
            "lock_days": proto_data["lock_days"],
            "lock_until": lock_until,
        })

        db_records.append({
            "user_id": user_id,
            "protocol_name": matched,
            "protocol_type": proto_data["type"],
            "amount_usdc": round(amount, 2),
            "apy_at_deposit": proto_data["apy"],
            "lock_until": lock_until,
            "status": "pending",
        })

        total_amount += amount

    # Save all to DB
    saved = supabase.table("user_positions").insert(db_records).execute()
    if not saved.data:
        raise Exception("Failed to save positions to database")

    weighted_apy = calculate_weighted_apy(positions)

    return {
        "success": True,
        "user_id": user_id,
        "total_amount": round(total_amount, 2),
        "risk_profile": "custom",
        "weighted_apy": weighted_apy,
        "positions": positions,
        "pending_position_ids": [r["id"] for r in saved.data],
        "message": (
            f"Ready to invest ${round(total_amount, 2)} across "
            f"{len(positions)} protocol(s) at {weighted_apy}% weighted APY. "
            f"Please sign the transactions."
        ),
    }
