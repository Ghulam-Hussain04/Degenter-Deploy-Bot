from fastapi import APIRouter, HTTPException
from app.models.invest import InvestPrepareRequest, InvestConfirmRequest, InvestCustomRequest
from app.services.invest_service import prepare_invest, confirm_invest, prepare_invest_custom

router = APIRouter()

@router.post("/prepare")
async def invest_prepare(request: InvestPrepareRequest):
    try:
        result = await prepare_invest(
            user_id=request.user_id,
            amount=request.amount,
            risk_profile=request.risk_profile
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/prepare-custom")
async def invest_prepare_custom(request: InvestCustomRequest):
    """
    Invest in user-chosen protocols with explicit amounts.

    Examples:
      { "user_id": "...", "allocations": [{"protocol": "Kamino", "amount": 100}] }
      { "user_id": "...", "allocations": [{"protocol": "Kamino", "amount": 50}, {"protocol": "Save", "amount": 30}] }
      { "user_id": "...", "allocations": [{"protocol": "Meteora", "amount": 50}, {"protocol": "Raydium", "amount": 50}] }
    """
    try:
        allocations = [{"protocol": a.protocol, "amount": a.amount} for a in request.allocations]
        result = await prepare_invest_custom(
            user_id=request.user_id,
            allocations=allocations
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm")
async def invest_confirm(request: InvestConfirmRequest):
    try:
        result = await confirm_invest(
            user_id=request.user_id,
            position_ids=request.position_ids,
            tx_signatures=request.tx_signatures
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))