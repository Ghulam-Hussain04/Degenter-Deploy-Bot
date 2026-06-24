from fastapi import APIRouter, HTTPException
from app.services.positions_service import get_user_positions

router = APIRouter()

@router.get("/{user_id}")
async def fetch_user_positions(user_id: str):
    try:
        result = await get_user_positions(user_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))