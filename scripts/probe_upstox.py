import asyncio, os, sys, time

sys.path.insert(0, r'C:\Tradinf2')
os.chdir(r'C:\Tradinf2')

TOKEN = 'eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiIyTkNONzciLCJqdGkiOiI2YTc5ZDAyNGQwYjVjOTMyZDEyNDA3YTYiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlzRXh0ZW5kZWQiOnRydWUsImlhdCI6MTc4NjM2ODAzNiwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxODE3OTM1MjAwfQ.6KNMvLDFrpNrMaOipeoKzeYCey8aulvUC_vwKE_t9BI'

async def probe():
    from backend.app.broker_providers.upstox_client import UpstoxRESTClient

    client = UpstoxRESTClient(token=TOKEN)
    now_utc = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())
    print('=== UPSTOX LIVE PROVIDER SMOKE TEST ===')
    print(f'Test Time (UTC): {now_utc}')
    print()

    # 1. Test authentication
    authenticated = False
    try:
        ws_url = await client.get_ws_authorize_url()
        authenticated = True
        print('[AUTH] AUTHENTICATED: YES')
        print('[AUTH] WS Auth URL obtained OK')
    except Exception as e:
        print(f'[AUTH] AUTHENTICATED: NO => {e}')

    print()

    # 2. Probe all target symbols
    symbols = ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS', 'TATAMOTORS.NS', 'SBIN.NS']
    header = f"{'SYMBOL':<20} {'RAW_LTP':>12} {'PROV_TS':>12} {'AGE_SEC':>10} {'SOURCE':<10}"
    print(header)
    print('-' * 70)

    for sym in symbols:
        try:
            q = await client.get_full_quote(sym)
            raw_ltp = q.get('ltp', 0)
            prov_ts = q.get('timestamp', 0)
            data_age = round(time.time() - float(prov_ts), 1) if prov_ts else -1
            ts_str = time.strftime('%H:%M:%S', time.gmtime(prov_ts)) if prov_ts else 'N/A'
            src = q.get('source', '?')
            row = f"{sym:<20} {raw_ltp:>12.2f} {ts_str:>12} {data_age:>10.1f} {src:<10}"
            print(row)
        except Exception as e:
            print(f"{sym:<20} ERROR => {str(e)[:60]}")

    await client.close()
    print()
    print(f'LIVE_PROVIDER_SMOKE_TEST = {"EXECUTED - CONNECTED" if authenticated else "EXECUTED - AUTH_FAILED"}')

asyncio.run(probe())
