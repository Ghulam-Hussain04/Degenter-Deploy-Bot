from app.database import supabase

async def connect_user(wallet_address: str):
    # Check if user already exists
    existing = supabase.table("users") \
        .select("*") \
        .eq("wallet_address", wallet_address) \
        .execute()

    # If user exists → return them
    if existing.data and len(existing.data) > 0:
        user = existing.data[0]
        return {
            "id": user["id"],
            "wallet_address": user["wallet_address"],
            "risk_profile": user["risk_profile"],
            "created_at": user["created_at"],
            "is_new": False
        }

    # If user doesn't exist → create them
    new_user = supabase.table("users") \
        .insert({
            "wallet_address": wallet_address,
            "risk_profile": "any"
        }) \
        .execute()

    user = new_user.data[0]
    return {
        "id": user["id"],
        "wallet_address": user["wallet_address"],
        "risk_profile": user["risk_profile"],
        "created_at": user["created_at"],
        "is_new": True
    }