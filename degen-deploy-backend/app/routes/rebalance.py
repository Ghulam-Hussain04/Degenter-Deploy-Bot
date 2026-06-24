"""
app/routes/rebalance.py
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from app.services.solana_service import (
    prepare_rebalance,
    confirm_rebalance,
    get_rebalance_history,
)

router = APIRouter()


class RebalancePrepareRequest(BaseModel):
    user_id: str

    # Target — where to move funds to
    target_protocol: Optional[str] = Field(
        default=None,
        description="Protocol to move funds INTO. If omitted, picks best APY."
    )

    # Source filter — which position(s) to move FROM (optional, default = all)
    from_protocol: Optional[str] = Field(
        default=None,
        description="Only move funds FROM this protocol e.g. 'Orca'"
    )

    # Partial amount controls (both optional — if neither given, full rebalance)
    amount: Optional[float] = Field(
        default=None,
        description="Fixed USDC amount to move e.g. 10 (moves $10 from Orca to target)",
        gt=0
    )
    percent: Optional[float] = Field(
        default=None,
        description="Percentage of eligible positions to move e.g. 50 (moves 50%)",
        gt=0,
        le=100
    )


class RebalanceMoveItem(BaseModel):
    from_position_id: str
    from_protocol: str
    to_protocol: str
    amount: float
    source_position_remaining: float
    fully_closing_source: bool


class RebalanceConfirmRequest(BaseModel):
    user_id: str
    moves: List[RebalanceMoveItem]
    to_protocol: str
    tx_signatures: List[str]


@router.post("/prepare")
async def rebalance_prepare(request: RebalancePrepareRequest):
    """
    Build rebalance plan. Supports full and partial rebalancing.

    Examples:
      Full rebalance to best APY:
        { "user_id": "..." }

      Full rebalance to specific protocol:
        { "user_id": "...", "target_protocol": "Kamino" }

      Move $10 from Orca to best APY:
        { "user_id": "...", "from_protocol": "Orca", "amount": 10 }

      Move 50% from Orca to Raydium:
        { "user_id": "...", "from_protocol": "Orca", "target_protocol": "Raydium", "percent": 50 }

      Move all Orca to Kamino:
        { "user_id": "...", "from_protocol": "Orca", "target_protocol": "Kamino" }
    """
    try:
        result = await prepare_rebalance(
            user_id=request.user_id,
            target_protocol=request.target_protocol,
            from_protocol=request.from_protocol,
            amount=request.amount,
            percent=request.percent,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm")
async def rebalance_confirm(request: RebalanceConfirmRequest):
    """
    Execute rebalance after user signs.
    Pass the `moves` list exactly as returned from /prepare.
    Partial moves reduce the source position amount; full moves close it.
    """
    try:
        moves_dicts = [m.dict() for m in request.moves]
        result = await confirm_rebalance(
            user_id=request.user_id,
            moves=moves_dicts,
            to_protocol=request.to_protocol,
            tx_signatures=request.tx_signatures,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{user_id}")
async def rebalance_history(user_id: str):
    try:
        result = await get_rebalance_history(user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))