"""
APEX Live Paper Trading — Command Line Interface
===============================================
Usage:
  python -m backend.app.live_paper.cli preflight [--date YYYY-MM-DD]
  python -m backend.app.live_paper.cli run [--date YYYY-MM-DD] [--dry-run]
  python -m backend.app.live_paper.cli verify --log-file PATH
"""

import argparse
import asyncio
import json
import logging
import os
import sys

from backend.app.live_paper.preflight import SessionPreflight
from backend.app.live_paper.session_runner import LivePaperSessionRunner
from backend.app.live_paper.master_evidence_logger import MasterEvidenceLogger

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def run_preflight_command(date_str: str) -> int:
    preflight = SessionPreflight(target_date=date_str)
    report = await preflight.run_all_checks()
    print("\n" + "=" * 80)
    print(f"APEX PREFLIGHT VERIFICATION REPORT — SESSION {report.session_date}")
    print("=" * 80)
    for c in report.checks:
        badge = f"[{c.status}]"
        print(f"{badge:<10} {c.name:<25} : {c.details}")
    print("-" * 80)
    print(f"OVERALL STATUS: {report.overall_status}")
    print(f"SUMMARY       : {report.summary['passed']} Passed, {report.summary['warnings']} Warnings, {report.summary['failures']} Failures")
    print("=" * 80 + "\n")
    return 0 if report.overall_status in ("READY", "READY_WITH_WARNINGS") else 1


async def run_session_command(date_str: str, dry_run: bool, duration_seconds: int = 0) -> int:
    experiment_id = f"APEX-LIVE-PAPER-{date_str}"
    print(f"Starting APEX Live Paper Session: {experiment_id} (Dry Run: {dry_run})")
    runner = LivePaperSessionRunner(
        experiment_id=experiment_id,
        session_date=date_str,
        dry_run=dry_run,
    )

    try:
        await runner.start()
        if duration_seconds > 0:
            print(f"Running for {duration_seconds} seconds...")
            await asyncio.sleep(duration_seconds)
            await runner.stop()
        else:
            print("Session running. Press Ctrl+C to finalize session...")
            while runner.is_running:
                await asyncio.sleep(1.0)
    except KeyboardInterrupt:
        print("\nSession interrupted by operator. Finalizing...")
        await runner.stop()
    except Exception as e:
        logger.error(f"Fatal error in session: {e}")
        await runner.stop()
        return 1

    print(f"\nMaster Evidence File: {runner.evidence_logger.log_file}")
    print(f"Master Evidence SHA-256: {runner.evidence_logger.compute_sha256()}")
    print("Session finalized successfully.")
    return 0


def verify_log_command(log_file: str) -> int:
    if not os.path.exists(log_file):
        print(f"Error: Log file not found: {log_file}")
        return 1

    print(f"Verifying Master Evidence File: {log_file}")
    total_lines = 0
    seq_prev = 0
    errors = 0
    seq_violations = 0

    with open(log_file, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            total_lines += 1
            line_str = line.strip()
            if not line_str:
                continue
            try:
                record = json.loads(line_str)
                seq = record.get("sequence_number", 0)
                if seq <= seq_prev and total_lines > 1:
                    seq_violations += 1
                seq_prev = seq
            except Exception as e:
                errors += 1

    import hashlib
    hasher = hashlib.sha256()
    with open(log_file, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    sha256_hash = hasher.hexdigest()

    print("=" * 60)
    print(f"Events Verified     : {total_lines}")
    print(f"Sequence Violations : {seq_violations}")
    print(f"JSON Errors         : {errors}")
    print(f"SHA-256 Checksum    : {sha256_hash}")
    print(f"Integrity Status    : {'VERIFIED_VALID' if errors == 0 and seq_violations == 0 else 'INVALID'}")
    print("=" * 60)
    return 0 if errors == 0 and seq_violations == 0 else 1


def main():
    parser = argparse.ArgumentParser(description="APEX Live Paper Trading CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Preflight
    p_preflight = subparsers.add_parser("preflight", help="Run pre-market preflight validation")
    p_preflight.add_argument("--date", default="", help="Target date YYYY-MM-DD")

    # Run
    p_run = subparsers.add_parser("run", help="Run live paper trading session")
    p_run.add_argument("--date", default="", help="Session date YYYY-MM-DD")
    p_run.add_argument("--dry-run", action="store_true", help="Run with test fixtures rather than live feed")
    p_run.add_argument("--duration", type=int, default=0, help="Run duration in seconds (0 for indefinite)")

    # Verify
    p_verify = subparsers.add_parser("verify", help="Verify integrity of master JSONL evidence file")
    p_verify.add_argument("--log-file", required=True, help="Path to master JSONL log file")

    args = parser.parse_args()

    if args.command == "preflight":
        date_str = args.date or None
        code = asyncio.run(run_preflight_command(date_str))
        sys.exit(code)
    elif args.command == "run":
        date_str = args.date or None
        code = asyncio.run(run_session_command(date_str, args.dry_run, args.duration))
        sys.exit(code)
    elif args.command == "verify":
        code = verify_log_command(args.log_file)
        sys.exit(code)


if __name__ == "__main__":
    main()
