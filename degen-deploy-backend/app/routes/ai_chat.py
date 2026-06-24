from fastapi import APIRouter, HTTPException
from app.models.ai_chat import ChatRequest
from app.services.groq_service import chat

router = APIRouter()

@router.post("/chat")
async def ai_chat(request: ChatRequest):
    try:
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.conversation_history
        ]

        result = await chat(
            user_id=request.user_id,
            message=request.message,
            conversation_history=history
        )
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))