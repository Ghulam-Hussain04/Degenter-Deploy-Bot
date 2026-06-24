from datetime import datetime, timezone
from app.database import supabase
from app.services.apy_service import get_all_apys


def check_lock_status(lock_until: str | None):
    """
    Returns lock status and days remaining
    """
    if not lock_until:
        return False, None

    now = datetime.now(timezone.utc)

    # Parse lock_until string to datetime
    if isinstance(lock_until, str):
        lock_dt = datetime.fromisoformat(lock_until.replace("Z", "+00:00"))
    else:
        lock_dt = lock_until

    # FIX: if lock_dt has no timezone, add UTC
    if lock_dt.tzinfo is None:
        lock_dt = lock_dt.replace(tzinfo=timezone.utc)

    if now >= lock_dt:
        return False, None  # Lock expired

    days_remaining = (lock_dt - now).days + 1
    return True, days_remaining

async def get_user_positions(user_id: str):
    """
    Get all active positions for a user with current APY
    """

    # Step 1 — Validate user
    user = supabase.table("users") \
        .select("*") \
        .eq("id", user_id) \
        .execute()

    if not user.data:
        raise ValueError(f"User {user_id} not found")

    # Step 2 — Fetch active positions
    positions = supabase.table("user_positions") \
        .select("*") \
        .eq("user_id", user_id) \
        .eq("status", "active") \
        .execute()

    if not positions.data:
        return {
            "success": True,
            "user_id": user_id,
            "total_invested": 0,
            "weighted_apy": 0,
            "positions": [],
            "message": "No active positions found"
        }

    # Step 3 — Get current APYs for all protocols
    all_apys = await get_all_apys()
    apy_map = {p["protocol"]: p["apy"] for p in all_apys}

    # Step 4 — Build position details
    result_positions = []
    total_invested = 0
    weighted_sum = 0

    for pos in positions.data:
        protocol = pos["protocol_name"]
        amount = float(pos["amount_usdc"])
        current_apy = apy_map.get(protocol, pos["apy_at_deposit"])
        is_locked, days_remaining = check_lock_status(pos.get("lock_until"))

        result_positions.append({
            "position_id": pos["id"],
            "protocol": protocol,
            "protocol_type": pos["protocol_type"],
            "amount_usdc": amount,
            "apy_at_deposit": float(pos["apy_at_deposit"]),
            "current_apy": current_apy,
            "lock_until": pos.get("lock_until"),
            "is_locked": is_locked,
            "days_remaining": days_remaining,
            "status": pos["status"]
        })

        total_invested += amount
        weighted_sum += amount * current_apy

    # Step 5 — Calculate weighted APY
    weighted_apy = round(weighted_sum / total_invested, 2) if total_invested > 0 else 0

    return {
        "success": True,
        "user_id": user_id,
        "total_invested": round(total_invested, 2),
        "weighted_apy": weighted_apy,
        "positions": result_positions,
        "message": f"Found {len(result_positions)} active positions"
    }