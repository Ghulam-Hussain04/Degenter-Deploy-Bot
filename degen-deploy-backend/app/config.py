from dotenv import load_dotenv
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL")


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


APY_CACHE_TTL_SECONDS = _int_env("DEGEN_DEPLOY_APY_CACHE_TTL_SECONDS", 300)
APY_HTTP_TIMEOUT_SECONDS = _int_env("DEGEN_DEPLOY_APY_HTTP_TIMEOUT_SECONDS", 15)
ALLOW_BASELINE_APY = _bool_env("DEGEN_DEPLOY_ALLOW_BASELINE_APY", False)
DEFI_LLAMA_POOLS_URL = os.getenv(
    "DEGEN_DEPLOY_YIELDS_URL",
    "https://yields.llama.fi/pools",
)

PROTOCOL_APY_URLS = {
    "Kamino": os.getenv("DEGEN_DEPLOY_KAMINO_APY_URL"),
    "Marginfi": os.getenv("DEGEN_DEPLOY_MARGINFI_APY_URL"),
    "Save": os.getenv("DEGEN_DEPLOY_SAVE_APY_URL"),
    "Raydium": os.getenv("DEGEN_DEPLOY_RAYDIUM_APY_URL"),
    "Orca": os.getenv("DEGEN_DEPLOY_ORCA_APY_URL"),
    "Meteora": os.getenv("DEGEN_DEPLOY_METEORA_APY_URL"),
}

PROTOCOL_POOL_IDS = {
    "Raydium": (
        os.getenv("DEGEN_DEPLOY_RAYDIUM_SOL_USDC_POOL_ID")
        or os.getenv("RAYDIUM_SOL_USDC_POOL_ID")
    ),
    "Orca": (
        os.getenv("DEGEN_DEPLOY_ORCA_SOL_USDC_POOL_ID")
        or os.getenv("ORCA_SOL_USDC_POOL_ID")
    ),
    "Meteora": (
        os.getenv("DEGEN_DEPLOY_METEORA_SOL_USDC_POOL_ID")
        or os.getenv("METEORA_SOL_USDC_POOL_ID")
    ),
}
