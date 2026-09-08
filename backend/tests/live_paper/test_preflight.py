"""
Unit tests for SessionPreflight check harness.
"""

import pytest
from backend.app.live_paper.preflight import SessionPreflight


@pytest.mark.asyncio
async def test_session_preflight_runs_and_passes_critical_checks():
    preflight = SessionPreflight(target_date="2026-09-10")
    report = await preflight.run_all_checks()

    # Preflight should be READY or READY_WITH_WARNINGS (since off-market hours or future date are warnings)
    assert report.overall_status in ("READY", "READY_WITH_WARNINGS")

    check_dict = {c.name: c for c in report.checks}

    # Verify critical items pass
    assert check_dict["upstox_authentication"].status == "PASS"
    assert check_dict["websocket_authorization"].status == "PASS"
    assert check_dict["protobuf_decoding"].status == "PASS"
    assert check_dict["universe_loaded"].status == "PASS"
    assert check_dict["strategy_registry"].status == "PASS"
    assert check_dict["frozen_hash_matches"].status == "PASS"
    assert check_dict["paper_mode_enforced"].status == "PASS"
    assert check_dict["live_order_path_blocked"].status == "PASS"
    assert check_dict["database_available"].status == "PASS"
    assert check_dict["master_jsonl_writable"].status == "PASS"
