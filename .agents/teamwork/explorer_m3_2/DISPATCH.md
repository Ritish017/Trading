# Task Assignment: explorer_m3_2

## Objective
Technical exploration of Milestone 3 (Requirement R3): Side-Correct Automated Exits (Feature 18) and Same-Bar Conservative Resolution Policy (Feature 19).

## Authoritative Inputs
- Original Request: C:\Tradinf2\.agents\teamwork\ORIGINAL_REQUEST.md (MANDATORY: Read this first!)
- Project Plan: C:\Tradinf2\.agents\teamwork\PROJECT.md
- Test Suite: backend/tests/e2e/test_tier1_features.py (specifically test_f18_side_correct_automated_exits, test_f19_same_bar_conservative_policy) and test_tier3_combinations.py

## Focus Areas
1. Audit backend/app/paper_trading/engine.py, orders.py, portfolio.py for exit handling and market tick processing.
2. Check how process_market_tick / evaluate_exits evaluates SL and TP for LONG positions (`low <= stop_loss` -> EXIT_STOP, `high >= take_profit` -> EXIT_TARGET).
3. Check how process_market_tick / evaluate_exits evaluates SL and TP for SHORT positions (`high >= stop_loss` -> EXIT_STOP, `low <= take_profit` -> EXIT_TARGET).
4. Check same-bar conflict resolution: when both SL and TP thresholds are breached in the same bar / tick (`low <= stop` AND `high >= target`), stop-loss MUST take precedence (conservative assumption).
5. Identify current gaps, edge cases, and provide concrete recommendations for Worker implementation. Do NOT write code yourself.

## Output
Write your findings to C:\Tradinf2\.agents\teamwork\explorer_m3_2\report.md and send a completion message with summary.

## 2026-10-07T17:17:30Z
[Message] timestamp=2026-10-07T17:17:30Z sender=db928666-a41e-4bc1-8308-20a2c4588dfa priority=MESSAGE_PRIORITY_HIGH content=You are explorer_m3_2. Your working directory is C:\Tradinf2\.agents\teamwork\explorer_m3_2\.
Read your instructions in C:\Tradinf2\.agents\teamwork\explorer_m3_2\DISPATCH.md.
MANDATORY: Read C:\Tradinf2\.agents\teamwork\ORIGINAL_REQUEST.md before starting work.
Do NOT write code or modify files outside your working directory.
Investigate Feature 18 (Side-Correct Automated Exits) and Feature 19 (Same-Bar Conservative Resolution Policy).
Inspect backend/app/paper_trading/engine.py, orders.py, portfolio.py, and backend/tests/e2e/test_tier1_features.py (test_f18_*, test_f19_*), test_tier3_combinations.py.
Document findings and recommended implementation strategy in C:\Tradinf2\.agents\teamwork\explorer_m3_2\report.md.
Send a completion message back to caller upon finishing.
