from datetime import datetime, timezone, timedelta
from app.database import supabase
from app.services.apy_service import get_all_apys, get_protocol_apy
from app.services.positions_service import check_lock_status


async def find_best_protocol(exclude_protocols: list = []) -> dict:
    """
    Find highest APY protocol not in exclude list
    """
    all_apys = await get_all_apys()  # Already sorted by APY desc
    
    for protocol in all_apys:
        if protocol["protocol"] not in exclude_protocols:
            return protocol
    
    raise ValueError("No available protocol found for rebalancing")


async def prepare_rebalance(user_id: str, target_protocol: str = None):
    """
    Prepare rebalance:
    1. Get user's active positions
    2. Find target protocol (best APY or user-specified)
    3. Check which positions are locked
    4. Build move plan for unlocked positions
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
        raise ValueError("No active positions found to rebalance")

    # Step 3 — Find target protocol
    current_protocols = [p["protocol_name"] for p in positions.data]

    if target_protocol:
        # User specified a protocol — validate it exists
        target = await get_protocol_apy(target_protocol)
    else:
        # Find best APY protocol
        # Exclude protocols user is already fully invested in
        target = await find_best_protocol()

    # Step 4 — Separate locked vs moveable positions
    moveable = []
    skipped_locked = []

    for pos in positions.data:
        # Skip if already in target protocol
        if pos["protocol_name"] == target["protocol"]:
            skipped_locked.append({
                "position_id": pos["id"],
                "protocol": pos["protocol_name"],
                "amount": float(pos["amount_usdc"]),
                "reason": "Already in target protocol"
            })
            continue

        is_locked, days_remaining = check_lock_status(pos.get("lock_until"))

        if is_locked:
            skipped_locked.append({
                "position_id": pos["id"],
                "protocol": pos["protocol_name"],
                "amount": float(pos["amount_usdc"]),
                "reason": f"Locked for {days_remaining} more days"
            })
        else:
            moveable.append(pos)

    if not moveable:
        raise ValueError(
            "All positions are either locked or already in target protocol"
        )

    # Step 5 — Build move plan
    moves = []
    total_moving = 0

    for pos in moveable:
        amount = float(pos["amount_usdc"])
        moves.append({
            "from_position_id": pos["id"],
            "from_protocol": pos["protocol_name"],
            "to_protocol": target["protocol"],
            "amount": amount
        })
        total_moving += amount

    return {
        "success": True,
        "user_id": user_id,
        "target_protocol": target["protocol"],
        "target_apy": target["apy"],
        "moves": moves,
        "total_moving": round(total_moving, 2),
        "skipped_locked": skipped_locked,
        "message": (
            f"Ready to move ${round(total_moving, 2)} to {target['protocol']} "
            f"at {target['apy']}% APY. "
            f"{len(skipped_locked)} position(s) skipped."
            if skipped_locked else
            f"Ready to move ${round(total_moving, 2)} to "
            f"{target['protocol']} at {target['apy']}% APY."
        )
    }


async def confirm_rebalance(
    user_id: str,
    from_position_ids: list,
    to_protocol: str,
    tx_signatures: list
):
    """
    After user signs rebalance transactions:
    1. Mark old positions as withdrawn
    2. Create new positions in target protocol
    3. Log rebalance in rebalance_logs
    """

    # Step 1 — Fetch old positions
    old_positions = supabase.table("user_positions") \
        .select("*") \
        .in_("id", from_position_ids) \
        .eq("user_id", user_id) \
        .eq("status", "active") \
        .execute()

    if not old_positions.data:
        raise ValueError("No active positions found for rebalancing")

    # Step 2 — Get target protocol data
    protocol_data = await get_protocol_apy(to_protocol)

    # Calculate lock_until for new positions
    lock_days = protocol_data["lock_days"]
    lock_until = None
    if lock_days > 0:
        lock_until = (
            datetime.now(timezone.utc) + timedelta(days=lock_days)
        ).isoformat()

    # Step 3 — Mark old positions as withdrawn + create new ones
    new_positions = []
    rebalance_logs = []
    total_rebalanced = 0

    for i, old_pos in enumerate(old_positions.data):
        tx_sig = tx_signatures[i] if i < len(tx_signatures) else "mock_sig"
        amount = float(old_pos["amount_usdc"])

        # Mark old position as withdrawn
        supabase.table("user_positions") \
            .update({
                "status": "withdrawn",
                "tx_signature": tx_sig
            }) \
            .eq("id", old_pos["id"]) \
            .execute()

        # Create new position in target protocol
        new_pos = supabase.table("user_positions") \
            .insert({
                "user_id": user_id,
                "protocol_name": to_protocol,
                "protocol_type": protocol_data["type"],
                "amount_usdc": amount,
                "apy_at_deposit": protocol_data["apy"],
                "lock_until": lock_until,
                "status": "active",
                "tx_signature": tx_sig
            }) \
            .execute()

        # Log the rebalance
        rebalance_logs.append({
            "user_id": user_id,
            "from_protocol": old_pos["protocol_name"],
            "to_protocol": to_protocol,
            "from_amount": amount,
            "to_amount": amount,
            "tx_signature": tx_sig,
            "notes": f"Rebalanced from {old_pos['protocol_name']} to {to_protocol}"
        })

        new_positions.append({
            "position_id": new_pos.data[0]["id"],
            "protocol": to_protocol,
            "amount": amount,
            "apy": protocol_data["apy"],
            "lock_until": lock_until
        })

        total_rebalanced += amount

    # Step 4 — Save rebalance logs
    if rebalance_logs:
        supabase.table("user_rebalance_logs") \
            .insert(rebalance_logs) \
            .execute()

    return {
        "success": True,
        "user_id": user_id,
        "total_rebalanced": round(total_rebalanced, 2),
        "new_positions": new_positions,
        "message": (
            f"✅ Rebalanced ${round(total_rebalanced, 2)} to "
            f"{to_protocol} at {protocol_data['apy']}% APY."
        )
    }

async def get_rebalance_history(user_id: str):
    """
    Get all rebalance logs for a user
    """

    # Validate user
    user = supabase.table("users") \
        .select("*") \
        .eq("id", user_id) \
        .execute()

    if not user.data:
        raise ValueError(f"User {user_id} not found")

    # Fetch rebalance logs newest first
    logs = supabase.table("user_rebalance_logs") \
        .select("*") \
        .eq("user_id", user_id) \
        .order("executed_at", desc=True) \
        .execute()

    if not logs.data:
        return {
            "success": True,
            "user_id": user_id,
            "total_rebalances": 0,
            "history": [],
            "message": "No rebalance history found"
        }

    # Format logs
    history = []
    for log in logs.data:
        history.append({
            "id": log["id"],
            "from_protocol": log["from_protocol"],
            "to_protocol": log["to_protocol"],
            "from_amount": float(log["from_amount"]),
            "to_amount": float(log["to_amount"]),
            "tx_signature": log.get("tx_signature"),
            "executed_at": log["executed_at"],
            "notes": log.get("notes")
        })

    return {
        "success": True,
        "user_id": user_id,
        "total_rebalances": len(history),
        "history": history,
        "message": f"Found {len(history)} rebalance(s)"
    }
