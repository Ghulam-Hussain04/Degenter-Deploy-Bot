from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.routes import user, invest, rebalance, withdraw, positions, apy, ai_chat, balance

app = FastAPI(title="Degen Deploy API", version="1.0.0")

# Mount static files
app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
async def serve_frontend():
    return FileResponse("index.html")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(user.router,       prefix="/api/user",      tags=["User"])
app.include_router(invest.router,     prefix="/api/invest",    tags=["Invest"])
app.include_router(rebalance.router,  prefix="/api/rebalance", tags=["Rebalance"])
app.include_router(withdraw.router,   prefix="/api/withdraw",  tags=["Withdraw"])
app.include_router(positions.router,  prefix="/api/position",  tags=["Positions"])
app.include_router(apy.router,        prefix="/api/apy",       tags=["APY"])
app.include_router(ai_chat.router,    prefix="/api/ai",        tags=["AI Chat"])
app.include_router(balance.router,    prefix="/api/balance",   tags=["Balance"])