"""
app/services/rebalance_service.py

Supports full AND partial rebalancing:
  • Full rebalance   → move ALL funds from current positions to target
  • Amount rebalance → move $X from a specific protocol to target
  • Percent rebalance→ move X% from a specific protocol to target

In all cases ONLY the requesting user's funds move.
Locked positions are always skipped.
"""

from datetime import datetime, timezone, timedelta
from app.database import supabase
from app.services.apy_service import get_all_apys, get_protocol_apy
from app.services.positions_service import check_lock_status


async def find_best_protocol(exclude_protocols: list = []) -> dict:
    """Find highest APY protocol not in exclude list."""
    all_apys = await get_all_apys()
    for protocol in all_apys:
        if protocol["protocol"] not in exclude_protocols:
            return protocol
    raise ValueError("No available protocol found for rebalancing")


async def prepare_rebalance(
    user_id: str,
    target_protocol: str = None,
    from_protocol: str = None,     # NEW — restrict source to one protocol
    amount: float = None,          # NEW — move fixed $ amount
    percent: float = None,         # NEW — move X% of eligible positions
):
    """
    Prepare rebalance plan.

    Modes:
      Full rebalance:
        { user_id }                                → move all unlocked to best APY
        { user_id, target_protocol }               → move all unlocked to specified protocol

      Partial — from a specific protocol:
        { user_id, from_protocol, amount }         → move $X from that protocol to best APY
        { user_id, from_protocol, percent }        → move X% from that protocol to best APY
        { user_id, from_protocol, target_protocol, amount }   → move $X to target
        { user_id, from_protocol, target_protocol, percent }  → move X% to target
        { user_id, from_protocol, target_protocol }           → move all from that protocol to target
    """

    # ── Validate user ─────────────────────────────────────────────────────
    user = supabase.table("users").select("*").eq("id", user_id).execute()
    if not user.data:
        raise ValueError(f"User {user_id} not found")

    # ── Fetch active positions ─────────────────────────────────────────────
    positions_result = supabase.table("user_positions") \
        .select("*") \
        .eq("user_id", user_id) \
        .eq("status", "active") \
        .execute()

    if not positions_result.data:
        raise ValueError("No active positions found to rebalance")

    all_positions = positions_result.data

    # ── Validate from_protocol if provided ───────────────────────────────
    from_protocol_canonical = None
    if from_protocol:
        matched = next(
            (p for p in ["Kamino","Marginfi","Save","Raydium","Orca","Meteora"]
             if p.lower() == from_protocol.strip().lower()),
            None
        )
        if not matched:
            raise ValueError(f"Unknown source protocol '{from_protocol}'")
        from_protocol_canonical = matched
        candidate_positions = [p for p in all_positions if p["protocol_name"] == matched]
        if not candidate_positions:
            raise ValueError(f"No active positions found in {matched}")
    else:
        candidate_positions = all_positions

    # ── Validate percent range ────────────────────────────────────────────
    if percent is not None and not (0 < percent <= 100):
        raise ValueError("Percent must be between 0 and 100")

    # ── Validate amount > 0 ───────────────────────────────────────────────
    if amount is not None and amount <= 0:
        raise ValueError("Amount must be greater than 0")

    # ── Find target protocol ──────────────────────────────────────────────
    if target_protocol:
        matched_target = next(
            (p for p in ["Kamino","Marginfi","Save","Raydium","Orca","Meteora"]
             if p.lower() == target_protocol.strip().lower()),
            None
        )
        if not matched_target:
            raise ValueError(f"Unknown target protocol '{target_protocol}'")
        target = await get_protocol_apy(matched_target)
    else:
        # Best APY (exclude protocols user is moving FROM if doing full rebalance)
        target = await find_best_protocol()

    # ── Separate locked vs moveable ───────────────────────────────────────
    moveable = []
    skipped = []

    for pos in candidate_positions:
        # Skip if already in target (no point moving to same place)
        if pos["protocol_name"] == target["protocol"]:
            skipped.append({
                "position_id": pos["id"],
                "protocol": pos["protocol_name"],
                "amount": float(pos["amount_usdc"]),
                "reason": "Already in target protocol"
            })
            continue

        is_locked, days_remaining = check_lock_status(pos.get("lock_until"))
        if is_locked:
            skipped.append({
                "position_id": pos["id"],
                "protocol": pos["protocol_name"],
                "amount": float(pos["amount_usdc"]),
                "reason": f"Locked for {days_remaining} more day(s)"
            })
        else:
            moveable.append(pos)

    if not moveable:
        raise ValueError("All positions are either locked or already in target protocol")

    # ── Build move plan based on amount / percent / full ─────────────────
    moves = []
    total_moving = 0.0
    # Tracks positions that will be partially reduced (not closed)
    partial_updates = []  # {position_id, new_amount}

    if amount:
        # Move fixed $ — deduct from moveable positions largest-first
        moveable.sort(key=lambda x: float(x["amount_usdc"]), reverse=True)
        total_available = sum(float(p["amount_usdc"]) for p in moveable)
        if amount > total_available:
            raise ValueError(
                f"Requested ${amount} but only ${round(total_available, 2)} is available to move"
            )

        remaining_to_move = amount
        for pos in moveable:
            if remaining_to_move <= 0:
                break
            pos_amount = float(pos["amount_usdc"])
            move_amt = min(pos_amount, remaining_to_move)
            new_pos_amount = round(pos_amount - move_amt, 4)

            moves.append({
                "from_position_id": pos["id"],
                "from_protocol": pos["protocol_name"],
                "to_protocol": target["protocol"],
                "amount": round(move_amt, 4),
                "source_position_remaining": new_pos_amount,
                "fully_closing_source": new_pos_amount == 0.0,
            })
            total_moving += move_amt
            remaining_to_move = round(remaining_to_move - move_amt, 4)

    elif percent:
        # Move X% from each moveable position
        for pos in moveable:
            pos_amount = float(pos["amount_usdc"])
            move_amt = round(pos_amount * percent / 100, 4)
            new_pos_amount = round(pos_amount - move_amt, 4)

            moves.append({
                "from_position_id": pos["id"],
                "from_protocol": pos["protocol_name"],
                "to_protocol": target["protocol"],
                "amount": move_amt,
                "source_position_remaining": new_pos_amount,
                "fully_closing_source": new_pos_amount == 0.0,
            })
            total_moving += move_amt

    else:
        # Full rebalance — move everything
        for pos in moveable:
            amount_to_move = float(pos["amount_usdc"])
            moves.append({
                "from_position_id": pos["id"],
                "from_protocol": pos["protocol_name"],
                "to_protocol": target["protocol"],
                "amount": amount_to_move,
                "source_position_remaining": 0.0,
                "fully_closing_source": True,
            })
            total_moving += amount_to_move

    if not moves:
        raise ValueError("No moves to execute")

    return {
        "success": True,
        "user_id": user_id,
        "target_protocol": target["protocol"],
        "target_apy": target["apy"],
        "moves": moves,
        "total_moving": round(total_moving, 2),
        "skipped": skipped,
        "is_partial": bool(amount or percent),
        "message": (
            f"Ready to move ${round(total_moving, 2)} to {target['protocol']} "
            f"at {target['apy']}% APY. "
            + (f"{len(skipped)} position(s) skipped." if skipped else "")
        ).strip()
    }


async def confirm_rebalance(
    user_id: str,
    moves: list,           # list of move dicts from prepare response
    to_protocol: str,
    tx_signatures: list,
):
    """
    Execute rebalance plan:
    - For each move:
        • If fully_closing_source → mark old position as 'withdrawn', create new position
        • If partial → reduce old position amount, create new position with moved amount
    - Log all moves in user_rebalance_logs
    """

    # Validate user
    user = supabase.table("users").select("*").eq("id", user_id).execute()
    if not user.data:
        raise ValueError(f"User {user_id} not found")

    # Get target protocol data
    protocol_data = await get_protocol_apy(to_protocol)
    lock_days = protocol_data["lock_days"]
    lock_until = None
    if lock_days > 0:
        lock_until = (datetime.now(timezone.utc) + timedelta(days=lock_days)).isoformat()

    new_positions = []
    rebalance_logs = []
    total_rebalanced = 0.0

    for i, move in enumerate(moves):
        tx_sig = tx_signatures[i] if i < len(tx_signatures) else f"mock_sig_{i}"
        amount = float(move["amount"])
        from_position_id = move["from_position_id"]
        fully_closing = move.get("fully_closing_source", True)
        remaining = float(move.get("source_position_remaining", 0.0))

        # Verify position
        old_pos = supabase.table("user_positions") \
            .select("*") \
            .eq("id", from_position_id) \
            .eq("user_id", user_id) \
            .eq("status", "active") \
            .execute()

        if not old_pos.data:
            raise ValueError(f"Position {from_position_id} not found or not active")

        old_pos_data = old_pos.data[0]

        # Double-check lock
        is_locked, days_remaining = check_lock_status(old_pos_data.get("lock_until"))
        if is_locked:
            raise ValueError(
                f"Position in {old_pos_data['protocol_name']} is locked for {days_remaining} more day(s)"
            )

        # Update source position
        if fully_closing:
            supabase.table("user_positions") \
                .update({"status": "withdrawn", "tx_signature": tx_sig}) \
                .eq("id", from_position_id) \
                .execute()
        else:
            # Partial — reduce source position amount
            supabase.table("user_positions") \
                .update({"amount_usdc": remaining, "tx_signature": tx_sig}) \
                .eq("id", from_position_id) \
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
                "tx_signature": tx_sig,
            }) \
            .execute()

        # Log
        rebalance_logs.append({
            "user_id": user_id,
            "from_protocol": old_pos_data["protocol_name"],
            "to_protocol": to_protocol,
            "from_amount": amount,
            "to_amount": amount,
            "tx_signature": tx_sig,
            "notes": (
                f"{'Full' if fully_closing else 'Partial'} rebalance: "
                f"${amount} from {old_pos_data['protocol_name']} → {to_protocol}"
            )
        })

        new_positions.append({
            "position_id": new_pos.data[0]["id"],
            "protocol": to_protocol,
            "amount": amount,
            "apy": protocol_data["apy"],
            "lock_until": lock_until,
        })

        total_rebalanced += amount

    # Save all rebalance logs
    if rebalance_logs:
        supabase.table("user_rebalance_logs").insert(rebalance_logs).execute()

    return {
        "success": True,
        "user_id": user_id,
        "total_rebalanced": round(total_rebalanced, 2),
        "new_positions": new_positions,
        "message": f"✅ Rebalanced ${round(total_rebalanced, 2)} to {to_protocol} at {protocol_data['apy']}% APY."
    }


async def get_rebalance_history(user_id: str):
    """Get all rebalance logs for a user, newest first."""
    user = supabase.table("users").select("*").eq("id", user_id).execute()
    if not user.data:
        raise ValueError(f"User {user_id} not found")

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

    history = [
        {
            "id": log["id"],
            "from_protocol": log["from_protocol"],
            "to_protocol": log["to_protocol"],
            "from_amount": float(log["from_amount"]),
            "to_amount": float(log["to_amount"]),
            "tx_signature": log.get("tx_signature"),
            "executed_at": log["executed_at"],
            "notes": log.get("notes"),
        }
        for log in logs.data
    ]

    return {
        "success": True,
        "user_id": user_id,
        "total_rebalances": len(history),
        "history": history,
        "message": f"Found {len(history)} rebalance(s)"
    }