# APEX Signal Outcome Model & Lifecycle (`SIGNAL_OUTCOME_MODEL.md`)

## 1. Complete Lifecycle State Machine

Signals transition through a formal deterministic state machine:

```
CANDIDATE ──► ANALYZING ──► VALIDATING ──► QUALIFIED
                                              │
              ┌───────────────────────────────┴───────────────────────────────┐
              ▼                               ▼                               ▼
          TRIGGERED                       EXPIRED                        INVALIDATED
              │
              ▼
           ACTIVE
              │
    ┌─────────┼─────────┐
    ▼         ▼         ▼
 TARGET_1  STOPPED   EXPIRED
    │
    ▼
 TARGET_2
    │
    ▼
 TARGET_3 (Terminal Success)
```

### State Definitions:
- `CANDIDATE`: Preliminary screener candidate.
- `ANALYZING`: Computing multi-timeframe feature vectors and strategy votes.
- `VALIDATING`: Passing through 17-stage hard validation gates.
- `QUALIFIED`: Fully validated opportunity with assigned stops, targets, and sizing.
- `TRIGGERED`: Market price traded within entry zone.
- `ACTIVE`: Executed in paper ledger or live broker.
- `TARGET_1 / 2 / 3`: Progressive profit targets achieved.
- `STOPPED`: Stop loss price reached (terminal loss).
- `EXPIRED`: Observation window or trading session lapsed without filling or hitting stop/target.
- `INVALIDATED`: Market structure or volatility invalidated premise before trigger.
- `REJECTED`: Candidate rejected by a hard gate during evaluation.
- `CANCELLED`: User or risk circuit breaker cancelled candidate.

Every transition creates an immutable event in the `signal_events` database table. Illegal transitions immediately raise `InvalidStateTransitionError`.

---

## 2. Historical Outcome Evaluation Engine

For every qualified signal, the engine evaluates subsequent candles to determine empirical performance:

### Metrics Computed:
1. **Entry Fill**: Verifies price traded through entry level within max wait window.
2. **Maximum Favorable Excursion (MFE)**:
   - For LONG: $MFE = \max(High - Entry, 0)$
   - For SHORT: $MFE = \max(Entry - Low, 0)$
   - Normalized as points, percentage of entry, and multiples of initial risk $R$.
3. **Maximum Adverse Excursion (MAE)**:
   - For LONG: $MAE = \max(Entry - Low, 0)$
   - For SHORT: $MAE = \max(High - Entry, 0)$
   - Normalized as points, percentage of entry, and multiples of initial risk $R$.
4. **Realized R**:
   - Initial Risk Distance: $R_{dist} = |Entry - Stop|$
   - Realized $R = \frac{ExitPrice - Entry}{R_{dist}}$ (for LONG)
5. **Holding Time**:
   - Holding candles and elapsed seconds from entry timestamp to exit timestamp.
6. **Transaction Costs & Slippage**:
   - Evaluated via `TransactionCostCalculator` covering Brokerage, STT, Exchange, SEBI, GST, Stamp Duty, and Slippage.
   - Reconciles Gross PnL and Net PnL: $Net PnL = Gross PnL - Total Costs$.
