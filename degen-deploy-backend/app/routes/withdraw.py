"""
app/routes/withdraw.py

POST /api/withdraw/prepare  — build withdrawal plan
POST /api/withdraw/confirm  — execute the plan (SQL update)

Withdrawal modes supported (all via same endpoint, fields are optional):
  • Withdraw ALL                          → no extra fields
  • Withdraw ALL from protocol            → protocol="Orca"
  • Withdraw $X from protocol             → protocol="Orca", amount=50
  • Withdraw X% from protocol             → protocol="Orca", percent=50
  • Withdraw ALL from risk tier           → risk_profile="low"
  • Withdraw $X from total portfolio      → amount=200
  • Withdraw X% from total portfolio      → percent=25
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from app.services.withdraw_service import prepare_withdraw, confirm_withdraw

router = APIRouter()


# ── Request models ────────────────────────────────────────────────────────────

class WithdrawPrepareRequest(BaseModel):
    user_id: str

    # Optional filters — all combinations are valid
    protocol: Optional[str] = Field(
        default=None,
        description="Target a specific protocol e.g. 'Orca', 'Kamino'"
    )
    risk_profile: Optional[str] = Field(
        default=None,
        description="Target a risk tier: 'low', 'medium', 'high', 'any'"
    )
    amount: Optional[float] = Field(
        default=None,
        description="Fixed USDC amount to withdraw",
        gt=0
    )
    percent: Optional[float] = Field(
        default=None,
        description="Percentage of eligible positions to withdraw (0–100)",
        gt=0,
        le=100
    )


class WithdrawConfirmItem(BaseModel):
    position_id: str
    withdraw_amount: float
    remaining_in_position: float


class WithdrawConfirmRequest(BaseModel):
    user_id: str
    withdrawable: List[WithdrawConfirmItem]
    tx_signatures: List[str]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/prepare")
async def withdraw_prepare(request: WithdrawPrepareRequest):
    """
    Build a withdrawal plan. Returns list of positions to withdraw from
    with fee breakdown. Frontend shows this to user, user signs, then calls /confirm.

    Examples:
      { "user_id": "...", "protocol": "Orca" }                    → all Orca
      { "user_id": "...", "protocol": "Orca", "amount": 50 }      → $50 from Orca
      { "user_id": "...", "protocol": "Orca", "percent": 50 }     → 50% from Orca
      { "user_id": "...", "risk_profile": "low" }                 → all low-risk
      { "user_id": "...", "amount": 200 }                         → $200 from portfolio
      { "user_id": "...", "percent": 25 }                         → 25% of all positions
      { "user_id": "..." }                                         → withdraw everything
    """
    try:
        result = await prepare_withdraw(
            user_id=request.user_id,
            protocol=request.protocol,
            risk_profile=request.risk_profile,
            amount=request.amount,
            percent=request.percent,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm")
async def withdraw_confirm(request: WithdrawConfirmRequest):
    """
    Execute withdrawal plan after user signs.
    Positions with remaining_in_position=0 are marked 'withdrawn'.
    Positions with remaining_in_position>0 have their amount reduced (partial).
    """
    try:
        withdrawable_dicts = [item.dict() for item in request.withdrawable]
        result = await confirm_withdraw(
            user_id=request.user_id,
            withdrawable=withdrawable_dicts,
            tx_signatures=request.tx_signatures,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))