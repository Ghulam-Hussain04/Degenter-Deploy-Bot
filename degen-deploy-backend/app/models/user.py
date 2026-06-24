from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserConnectRequest(BaseModel):
    wallet_address: str

class UserResponse(BaseModel):
    id: str
    wallet_address: str
    risk_profile: str
    created_at: Optional[datetime]
    is_new: bool