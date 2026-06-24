from fastapi import APIRouter, HTTPException
from app.models.user import UserConnectRequest, UserResponse
from app.services.user_service import connect_user

router = APIRouter()

@router.post("/connect")
async def connect_wallet(request: UserConnectRequest):
    try:
        user = await connect_user(request.wallet_address)
        return user
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))