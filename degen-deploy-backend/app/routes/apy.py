from fastapi import APIRouter, HTTPException
from app.services.apy_service import get_all_apys, get_protocol_apy

router = APIRouter()

@router.get("/all")
async def fetch_all_apys():
    try:
        apys = await get_all_apys()
        return {
            "success": True,
            "count": len(apys),
            "protocols": apys
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{protocol_name}")
async def fetch_protocol_apy(protocol_name: str):
    try:
        data = await get_protocol_apy(protocol_name)
        return {
            "success": True,
            "data": data
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))