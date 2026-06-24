from pydantic import BaseModel
from typing import Optional, List

class PositionItem(BaseModel):
    position_id: str
    protocol: str
    protocol_type: str
    amount_usdc: float
    apy_at_deposit: float
    current_apy: float
    lock_until: Optional[str] = None
    is_locked: bool
    days_remaining: Optional[int] = None
    status: str

class PositionsResponse(BaseModel):
    success: bool
    user_id: str
    total_invested: float
    weighted_apy: float
    positions: List[PositionItem]
    message: str