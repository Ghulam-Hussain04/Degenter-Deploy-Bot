"""
Drop this in your backend root and run:  python verify_apy_v2.py
Tests the new direct-API apy_service.
"""
import asyncio, sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

async def main():
    # Patch config for standalone test
    import app.config as cfg
    cfg.ALLOW_BASELINE_APY = True   # show fallbacks if APIs fail
    cfg.APY_CACHE_TTL_SECONDS = 300
    cfg.APY_HTTP_TIMEOUT_SECONDS = 20

    # Import AFTER patching
    from app.services.apy_service import get_all_apys, get_top_protocols

    print("=" * 65)
    print("DEGEN DEPLOY — APY Service v2 Verification")
    print("=" * 65)

    print("\n[1] Fetching all APYs...")
    t0 = time.monotonic()
    try:
        apys = await get_all_apys(force_refresh=True)
        elapsed = time.monotonic() - t0
        print(f"    ✅ Got {len(apys)} protocols in {elapsed:.1f}s\n")

        expected = {"Kamino", "Save", "Raydium", "Orca", "Meteora", "Marginfi"}
        found = {p["protocol"] for p in apys}

        print(f"  {'Protocol':<12} {'APY':>7}  {'Source':<14} {'TVL':>14}  Status")
        print("  " + "-" * 65)
        for p in apys:
            tvl = f"${p.get('tvl_usd'):,.0f}" if p.get("tvl_usd") else "—"
            src = p.get("source", "—")
            warn = " ⚠️  BASELINE" if src == "baseline" else ""
            sane = "✅" if 0.5 < p["apy"] < 100 else "❌ SUSPICIOUS"
            print(f"  {p['protocol']:<12} {p['apy']:>6.2f}%  {src:<14} {tvl:>14}  {sane}{warn}")

        missing = expected - found
        if missing:
            print(f"\n  ❌ Still missing: {missing}")
        else:
            print(f"\n  ✅ All 6 protocols present!")

    except Exception as e:
        print(f"    ❌ FAILED: {e}")
        return

    print("\n[2] Sanity check — APY ranges (should be 1–50% for lending, 5–80% for LP)...")
    for p in apys:
        apy = p["apy"]
        typ = p.get("type", "?")
        src = p.get("source", "?")
        if src == "baseline":
            print(f"  ⚠️  {p['protocol']:12s} {apy:6.2f}%  (baseline — no live data)")
        elif typ == "lending" and not (0.5 <= apy <= 30):
            print(f"  ❌ {p['protocol']:12s} {apy:6.2f}%  SUSPICIOUS for lending")
        elif typ == "lp" and not (0.5 <= apy <= 200):
            print(f"  ❌ {p['protocol']:12s} {apy:6.2f}%  SUSPICIOUS for LP")
        else:
            print(f"  ✅ {p['protocol']:12s} {apy:6.2f}%  looks reasonable")

    print("\n[3] Top protocols per risk profile...")
    for risk in ["any", "low", "medium", "high"]:
        top = await get_top_protocols(risk, top_n=3)
        names = [f"{p['protocol']} ({p['apy']:.1f}%)" for p in top]
        print(f"  {risk:8s} → {', '.join(names)}")

    print("\n" + "=" * 65)

asyncio.run(main())