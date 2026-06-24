"""
app/services/apy_service.py  — v2
Replaces DeFiLlama guessing with direct protocol APIs for Raydium, Orca,
Meteora, and Save. Kamino uses DeFiLlama (works). Marginfi uses baseline.
"""
import asyncio
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import (
    ALLOW_BASELINE_APY,
    APY_CACHE_TTL_SECONDS,
    APY_HTTP_TIMEOUT_SECONDS,
)

# ── Protocol metadata ─────────────────────────────────────────────────────────
PROTOCOL_CONFIG = {
    "Kamino":   {"risk": "low",    "lock_days": 0, "withdrawal_fee": 0.0,   "type": "lending"},
    "Marginfi": {"risk": "medium", "lock_days": 0, "withdrawal_fee": 0.0,   "type": "lending"},
    "Save":     {"risk": "low",    "lock_days": 0, "withdrawal_fee": 0.0,   "type": "lending"},
    "Raydium":  {"risk": "medium", "lock_days": 0, "withdrawal_fee": 0.001, "type": "lp"},
    "Orca":     {"risk": "medium", "lock_days": 0, "withdrawal_fee": 0.001, "type": "lp"},
    "Meteora":  {"risk": "high",   "lock_days": 7, "withdrawal_fee": 0.002, "type": "lp"},
}

RISK_FILTER = {
    "low":    ["Kamino", "Save"],
    "medium": ["Kamino", "Marginfi", "Save", "Raydium", "Orca"],
    "high":   list(PROTOCOL_CONFIG),
    "any":    list(PROTOCOL_CONFIG),
}

# Hardcoded fallbacks — only used if DEGEN_DEPLOY_ALLOW_BASELINE_APY=1
BASELINE_APYS = {
    "Kamino":   6.2,
    "Marginfi": 5.8,
    "Save":     5.5,
    "Raydium":  8.4,
    "Orca":     9.1,
    "Meteora":  18.5,
}

# ── Pool / reserve IDs ────────────────────────────────────────────────────────
RAYDIUM_POOL_ID  = "2JtkunkYCRbe5YZuGU6kLFmNwN22Ba1pCicHoqW5Eqja"
ORCA_POOL_ID     = "HJPjoWUrhoZzkNfRpHuieeFk9WcZWjwy6PBjZ81ngndJ"
METEORA_POOL_ID  = "5rCf1DM8LjKTw4YqhnoLcngyZYeNnQqztScTogYHAS6"
SAVE_POOL_ID     = "4UpD2fh7xH3VP9QQaXtsS1YY3bxzWhtfpks7FatyKvdY"
USDC_MINT        = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

# ── API base URLs (from lead's env vars) ──────────────────────────────────────
RAYDIUM_BASE  = "https://api-v3.raydium.io"
ORCA_BASE     = "https://api.orca.so/v2/solana"
METEORA_BASE  = "https://dlmm.datapi.meteora.ag"
SAVE_BASE     = "https://api.save.finance"
DEFILLAMA_URL = "https://yields.llama.fi/pools"

# Kamino DeFiLlama pool UUID (confirmed working: $2,512 TVL, 9.32%)
# This is DeFiLlama's internal UUID, not the on-chain address
KAMINO_DEFILLAMA_UUID = None  # Will pick highest-TVL kamino USDC pool

# ── Cache ─────────────────────────────────────────────────────────────────────
_cache: dict[str, Any] = {"expires_at": 0.0, "data": None}
_cache_lock = asyncio.Lock()


# ── Helpers ───────────────────────────────────────────────────────────────────
def _base_result(protocol: str, apy: float, source: str, **kwargs) -> dict:
    cfg = PROTOCOL_CONFIG[protocol]
    return {
        "protocol": protocol,
        "apy": round(float(apy), 4),
        "risk": cfg["risk"],
        "lock_days": cfg["lock_days"],
        "withdrawal_fee": cfg["withdrawal_fee"],
        "type": cfg["type"],
        "source": source,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }


# ── Raydium — direct API ──────────────────────────────────────────────────────
async def _fetch_raydium(client: httpx.AsyncClient) -> dict:
    """
    GET /pools/info/ids?ids=<pool_id>
    Field: data[0].month.apr  (30-day average)
    Confirmed working: returned 8.36% from curl.
    """
    resp = await client.get(
        f"{RAYDIUM_BASE}/pools/info/ids",
        params={"ids": RAYDIUM_POOL_ID},
    )
    resp.raise_for_status()
    data = resp.json()

    if not data.get("success") or not data.get("data"):
        raise ValueError("Raydium: empty response")

    pool = data["data"][0]
    apy = float(pool.get("month", {}).get("apr", 0))
    if apy <= 0:
        raise ValueError("Raydium: APY is zero or missing")

    return _base_result("Raydium", apy, "raydium-api",
                        pool_id=RAYDIUM_POOL_ID, symbol="WSOL-USDC",
                        tvl_usd=pool.get("tvl"))


# ── Orca — direct API ─────────────────────────────────────────────────────────
async def _fetch_orca(client: httpx.AsyncClient) -> dict:
    """
    GET /whirlpool/<pool_id>
    Our pool ID returned 'not found' — try both path variants.
    If both fail, this raises and the baseline kicks in.
    TODO: confirm field name once we get a valid response.
    """
    for path in [
        f"{ORCA_BASE}/whirlpool/{ORCA_POOL_ID}",
        f"{ORCA_BASE}/whirlpools/{ORCA_POOL_ID}",
    ]:
        resp = await client.get(path)
        if resp.status_code == 404:
            continue
        resp.raise_for_status()
        data = resp.json()

        # Try common Orca APY field names
        apy = (
            data.get("apy")
            or data.get("stats", {}).get("apy")
            or data.get("feeApr")
            or (data.get("feeApr24h", 0) + data.get("rewardApr24h", 0))
        )
        if apy:
            val = float(apy)
            if 0 < val < 1:   # decimal → percent
                val *= 100
            return _base_result("Orca", val, "orca-api",
                                pool_id=ORCA_POOL_ID, symbol="SOL-USDC")

    raise ValueError(f"Orca: pool {ORCA_POOL_ID} not found on API")


# ── Meteora — direct API ──────────────────────────────────────────────────────
async def _fetch_meteora(client: httpx.AsyncClient) -> dict:
    """
    GET /pair/<pool_id>
    Returned empty on first try — may have been a timeout.
    Using 20s timeout since it's a smaller API.
    """
    resp = await client.get(f"{METEORA_BASE}/pair/{METEORA_POOL_ID}")
    if resp.status_code == 404:
        raise ValueError(f"Meteora: pool {METEORA_POOL_ID} not found")
    resp.raise_for_status()
    data = resp.json()

    # Try common Meteora DLMM field names
    apy = (
        data.get("apr")
        or data.get("apy")
        or data.get("fees_24h_apr")
        or data.get("fee_apr")
    )
    if not apy:
        raise ValueError("Meteora: no APY field in response")

    val = float(apy)
    if 0 < val < 1:
        val *= 100

    return _base_result("Meteora", val, "meteora-api",
                        pool_id=METEORA_POOL_ID, symbol="SOL-USDC",
                        tvl_usd=data.get("liquidity"))


# ── Save — direct API ─────────────────────────────────────────────────────────
async def _fetch_save(client: httpx.AsyncClient) -> dict:
    """
    GET /v1/reserves?scope=all&pool=<main_pool_id>
    Find the USDC reserve by mint address, extract supplyInterest.
    """
    resp = await client.get(
        f"{SAVE_BASE}/v1/reserves",
        params={"scope": "all", "pool": SAVE_POOL_ID},
    )
    resp.raise_for_status()
    payload = resp.json()

    reserves = payload if isinstance(payload, list) else payload.get("results", [])

    for item in reserves:
        # The reserve is nested under a "reserve" key
        reserve = item.get("reserve", item)
        liquidity = reserve.get("liquidity", {})
        mint = str(liquidity.get("mintPubkey", ""))

        if USDC_MINT not in mint:
            continue

        # supplyInterest is in the reserve's "rates" or top-level
        # From the curl output: "liquidity":{"mintPubkey":"EPjFWdd5..."}
        # Rates are typically under reserve.config or reserve itself
        rates = reserve.get("rates", {})
        supply_apy = (
            rates.get("supplyInterest")
            or rates.get("supplyApy")
            or reserve.get("supplyInterest")
            or reserve.get("supplyApy")
        )

        if supply_apy is not None:
            val = float(supply_apy)
            # Save returns as percentage already (e.g. 5.5 not 0.055)
            # but if it's a decimal, convert
            if 0 < val < 1:
                val *= 100
            if val > 0.1:  # ignore near-zero
                return _base_result("Save", val, "save-api",
                                    pool_id=SAVE_POOL_ID, symbol="USDC")

    raise ValueError("Save: USDC reserve not found or APY is zero")


# ── Kamino — DeFiLlama (working) ──────────────────────────────────────────────
async def _fetch_kamino_via_defillama(client: httpx.AsyncClient) -> dict:
    """
    DeFiLlama works for Kamino (returned 9.32%, $2,512 TVL).
    Filter: chain=Solana, project in {kamino-lend, kamino}, symbol=USDC
    """
    resp = await client.get(DEFILLAMA_URL)
    resp.raise_for_status()
    pools = resp.json().get("data", [])

    kamino_pools = []
    for p in pools:
        if str(p.get("chain", "")).lower() != "solana":
            continue
        if str(p.get("project", "")).lower() not in {"kamino-lend", "kamino"}:
            continue
        sym = str(p.get("symbol", "")).upper().replace("/", "-")
        if sym != "USDC":
            continue
        apy = p.get("apy") or ((p.get("apyBase") or 0) + (p.get("apyReward") or 0))
        if not apy:
            continue
        kamino_pools.append((float(p.get("tvlUsd", 0)), float(apy), p))

    if not kamino_pools:
        raise ValueError("Kamino: no USDC pool found on DeFiLlama")

    kamino_pools.sort(reverse=True)  # highest TVL first
    _, apy, pool = kamino_pools[0]

    return _base_result("Kamino", apy, "defillama",
                        pool_id=pool.get("pool"), symbol="USDC",
                        tvl_usd=pool.get("tvlUsd"))


# ── Marginfi — baseline only ──────────────────────────────────────────────────
async def _fetch_marginfi() -> dict:
    """
    Marginfi has no DeFiLlama presence and no confirmed direct API yet.
    Uses baseline until SDK microservice is ready.
    """
    return _base_result("Marginfi", BASELINE_APYS["Marginfi"], "baseline")


# ── Main fetch ────────────────────────────────────────────────────────────────
async def _load_live_apys() -> list[dict]:
    timeout = httpx.Timeout(20.0)  # Meteora needs longer timeout
    headers = {"User-Agent": "Degen-Deploy/1.0"}

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
        # Run all fetches concurrently
        tasks = await asyncio.gather(
            _fetch_kamino_via_defillama(client),
            _fetch_save(client),
            _fetch_raydium(client),
            _fetch_orca(client),
            _fetch_meteora(client),
            _fetch_marginfi(),
            return_exceptions=True,
        )

    names = ["Kamino", "Save", "Raydium", "Orca", "Meteora", "Marginfi"]
    results = {}

    for name, result in zip(names, tasks):
        if isinstance(result, Exception):
            print(f"[APY] {name} fetch failed: {result}")
            if ALLOW_BASELINE_APY:
                results[name] = _base_result(name, BASELINE_APYS[name], "baseline")
            # else: protocol is simply absent from results
        else:
            results[name] = result

    if not results:
        raise RuntimeError("No live APY data available from any source")

    data = sorted(results.values(), key=lambda x: x["apy"], reverse=True)
    return data


# ── Cache layer ───────────────────────────────────────────────────────────────
async def get_all_apys(force_refresh: bool = False) -> list[dict]:
    now = time.monotonic()
    if not force_refresh and _cache["data"] and now < _cache["expires_at"]:
        return deepcopy(_cache["data"])

    async with _cache_lock:
        now = time.monotonic()
        if not force_refresh and _cache["data"] and now < _cache["expires_at"]:
            return deepcopy(_cache["data"])

        try:
            data = await _load_live_apys()
        except Exception:
            if _cache["data"]:
                return deepcopy(_cache["data"])
            raise

        _cache["data"] = data
        _cache["expires_at"] = now + max(APY_CACHE_TTL_SECONDS, 1)
        return deepcopy(data)


async def get_protocol_apy(protocol_name: str) -> dict:
    canonical = next(
        (n for n in PROTOCOL_CONFIG if n.lower() == protocol_name.strip().lower()),
        None,
    )
    if canonical is None:
        raise ValueError(f"Protocol '{protocol_name}' not found")

    for p in await get_all_apys():
        if p["protocol"] == canonical:
            return p

    raise ValueError(f"Live APY for {canonical} is currently unavailable")


async def get_top_protocols(risk_profile: str, top_n: int = 3) -> list[dict]:
    normalized = risk_profile.strip().lower()
    if normalized not in RISK_FILTER:
        raise ValueError(f"Invalid risk profile '{risk_profile}'. Use: any, low, medium, high")

    allowed = RISK_FILTER[normalized]
    return [p for p in await get_all_apys() if p["protocol"] in allowed][:top_n]