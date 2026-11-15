import asyncio
import asyncpg
import json
import os

PG_URL = "postgresql://apex_user:OKQP959mnEYGgqh7TnkCoK77aVWVB4jE@dpg-dag6bl0hchos73826v50-a.singapore-postgres.render.com:5432/apex_quant"

async def sync_logs(session_dates):
    conn = await asyncpg.connect(PG_URL)
    
    for s_date in session_dates:
        target_dir = os.path.join("logs", "live_paper", s_date)
        os.makedirs(target_dir, exist_ok=True)
        target_file = os.path.join(target_dir, f"APEX_{s_date}_MASTER.jsonl")
        
        print(f"Fetching events for {s_date} from PostgreSQL...")
        rows = await conn.fetch("""
            SELECT event_id, experiment_id, event_type, event_timestamp_utc, event_timestamp_ist,
                   sequence_number, symbol, source, data_provenance, git_commit, config_hash,
                   engine_version, payload
            FROM audit_events
            WHERE session_date = $1
            ORDER BY sequence_number ASC
        """, s_date)
        
        print(f"  Found {len(rows)} events. Writing to {target_file}...")
        with open(target_file, "w", encoding="utf-8") as f:
            for r in rows:
                event_dict = {
                    "event_id": r["event_id"],
                    "experiment_id": r["experiment_id"],
                    "event_type": r["event_type"],
                    "event_timestamp_utc": r["event_timestamp_utc"],
                    "event_timestamp_ist": r["event_timestamp_ist"],
                    "sequence_number": r["sequence_number"],
                    "symbol": r["symbol"],
                    "source": r["source"],
                    "data_provenance": r["data_provenance"],
                    "git_commit": r["git_commit"],
                    "config_hash": r["config_hash"],
                    "engine_version": r["engine_version"],
                    "payload": json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"],
                }
                f.write(json.dumps(event_dict, separators=(",", ":")) + "\n")
        
        file_size_kb = os.path.getsize(target_file) / 1024
        print(f"  Exported {target_file} ({file_size_kb:.1f} KB)")
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(sync_logs(["2026-09-11", "2026-09-12"]))
