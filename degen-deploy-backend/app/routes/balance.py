"""
app/routes/balance.py

GET /api/balance/{wallet_address}

Returns:
  • on_chain_usdc  — mock for now (real value needs Node.js + Solana RPC)
  • invested_usdc  — sum of all active positions from DB (real)
  • available_usdc — on_chain_usdc (not yet invested)
  • total_usdc     — on_chain + invested (user's total USDC under management)

When Node.js migration happens, replace the mock RPC call in this file only.
The DB query stays the same.
"""

from fastapi import APIRouter, HTTPException
from app.database import supabase

router = APIRouter()


async def _get_on_chain_balance_mock(wallet_address: str) -> float:
    """
    MOCK — returns 0.0 until Node.js RPC microservice is ready.

    In production this will call:
      GET http://localhost:3001/balance/{wallet_address}
    which uses @solana/web3.js to fetch the SPL USDC token account balance.
    """
    # TODO: replace with real RPC call when Node.js microservice is ready
    # response = await httpx_client.get(f"http://localhost:3001/balance/{wallet_address}")
    # return response.json()["usdc_balance"]
    return 0.0


async def _get_invested_balance(wallet_address: str) -> dict:
    """
    Real DB query — sum of all active positions for this wallet.
    Looks up user by wallet_address, then sums user_positions.
    """
    # Find user by wallet address
    user = supabase.table("users") \
        .select("id") \
        .eq("wallet_address", wallet_address) \
        .execute()

    if not user.data:
        return {
            "user_found": False,
            "invested_usdc": 0.0,
            "position_count": 0,
            "positions_by_protocol": []
        }

    user_id = user.data[0]["id"]

    # Fetch all active positions
    positions = supabase.table("user_positions") \
        .select("protocol_name, amount_usdc, apy_at_deposit") \
        .eq("user_id", user_id) \
        .eq("status", "active") \
        .execute()

    if not positions.data:
        return {
            "user_found": True,
            "user_id": user_id,
            "invested_usdc": 0.0,
            "position_count": 0,
            "positions_by_protocol": []
        }

    # Aggregate by protocol
    protocol_totals = {}
    for pos in positions.data:
        proto = pos["protocol_name"]
        amt = float(pos["amount_usdc"])
        if proto not in protocol_totals:
            protocol_totals[proto] = {"protocol": proto, "amount": 0.0, "apy": float(pos["apy_at_deposit"])}
        protocol_totals[proto]["amount"] += amt

    total_invested = sum(p["amount"] for p in protocol_totals.values())

    return {
        "user_found": True,
        "user_id": user_id,
        "invested_usdc": round(total_invested, 2),
        "position_count": len(positions.data),
        "positions_by_protocol": [
            {**v, "amount": round(v["amount"], 2)}
            for v in protocol_totals.values()
        ]
    }


@router.get("/{wallet_address}")
async def get_wallet_balance(wallet_address: str):
    """
    GET /api/balance/{wallet_address}

    Returns full USDC balance breakdown:
    - on_chain_usdc:  wallet's uninvested USDC (mock until Node.js RPC ready)
    - invested_usdc:  sum of active DB positions (real)
    - total_usdc:     on_chain + invested
    - note:           explains mock status of on_chain figure

    Example response:
    {
      "wallet_address": "7xKX...",
      "on_chain_usdc": 0.0,
      "invested_usdc": 1500.00,
      "total_usdc": 1500.00,
      "position_count": 3,
      "positions_by_protocol": [
        {"protocol": "Orca", "amount": 500.00, "apy": 22.7},
        {"protocol": "Kamino", "amount": 1000.00, "apy": 6.2}
      ],
      "note": "on_chain_usdc is mocked at 0 until Node.js RPC microservice is ready"
    }
    """
    try:
        on_chain = await _get_on_chain_balance_mock(wallet_address)
        db_data = await _get_invested_balance(wallet_address)

        total = round(on_chain + db_data["invested_usdc"], 2)

        return {
            "wallet_address": wallet_address,
            "on_chain_usdc": on_chain,
            "invested_usdc": db_data["invested_usdc"],
            "total_usdc": total,
            "user_found": db_data["user_found"],
            "user_id": db_data.get("user_id"),
            "position_count": db_data["position_count"],
            "positions_by_protocol": db_data["positions_by_protocol"],
            "note": "on_chain_usdc is mocked at 0.0 until Node.js RPC microservice is ready"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))