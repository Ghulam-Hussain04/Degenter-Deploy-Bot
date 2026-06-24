from pydantic import BaseModel
from typing import Optional, List

class InvestPrepareRequest(BaseModel):
    user_id: str
    amount: float
    risk_profile: str = "any"  # any, low, medium, high

class PositionDetail(BaseModel):
    protocol: str
    amount: float
    apy: float
    lock_days: int
    lock_until: Optional[str] = None

class InvestPrepareResponse(BaseModel):
    success: bool
    user_id: str
    total_amount: float
    risk_profile: str
    weighted_apy: float
    positions: List[PositionDetail]
    message: str

class InvestConfirmRequest(BaseModel):
    user_id: str
    position_ids: List[str]       # IDs returned from /prepare or /prepare-custom
    tx_signatures: List[str]      # Signatures from Phantom after signing

class ConfirmedPosition(BaseModel):
    position_id: str
    protocol: str
    amount: float
    apy: float
    status: str
    tx_signature: str

class InvestConfirmResponse(BaseModel):
    success: bool
    user_id: str
    confirmed_positions: List[ConfirmedPosition]
    total_invested: float
    message: str

# ── Custom protocol invest ────────────────────────────────────────────────────

class AllocationItem(BaseModel):
    protocol: str    # e.g. "Kamino"
    amount: float    # USDC amount for this protocol

class InvestCustomRequest(BaseModel):
    user_id: str
    allocations: List[AllocationItem]