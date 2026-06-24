from pydantic import BaseModel
from typing import Optional, List

class RebalancePrepareRequest(BaseModel):
    user_id: str
    target_protocol: Optional[str] = None  # None = find best APY

class RebalanceMove(BaseModel):
    from_protocol: str
    to_protocol: str
    amount: float

class RebalancePrepareResponse(BaseModel):
    success: bool
    user_id: str
    target_protocol: str
    target_apy: float
    moves: List[RebalanceMove]
    total_moving: float
    skipped_locked: List[dict]
    message: str

class RebalanceConfirmRequest(BaseModel):
    user_id: str
    from_position_ids: List[str]
    to_protocol: str
    tx_signatures: List[str]

class RebalanceConfirmResponse(BaseModel):
    success: bool
    user_id: str
    total_rebalanced: float
    new_positions: List[dict]
    message: str