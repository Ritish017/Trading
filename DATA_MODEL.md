# APEX DATA MODEL SPECIFICATION

## 1. Relational & Time-Series Models (PostgreSQL + TimescaleDB)

### `instruments`
Master equity contract lookup table (`instrument_id`, `symbol`, `exchange`, `name`, `sector`, `lot_size`, `tick_size`, `is_tradable`).

### `ticks` (TimescaleDB Hypertable)
Streaming tick store (`timestamp`, `symbol`, `exchange`, `ltp`, `open`, `high`, `low`, `close`, `volume`, `open_interest`, `bid`, `ask`, `provider`).

### `candles` (TimescaleDB Hypertable)
Aggregated OHLCV time bars (`timestamp`, `symbol`, `timeframe`, `open`, `high`, `low`, `close`, `volume`, `vwap`).

### `option_snapshots` (TimescaleDB Hypertable)
Option chain time-series (`timestamp`, `underlying_symbol`, `expiry_date`, `strike_price`, `option_type`, `ltp`, `iv`, `open_interest`, `change_in_oi`, `volume`).

### `paper_orders` & `paper_positions`
Paper trade execution log (`order_id`, `symbol`, `product_type`, `side`, `quantity`, `price`, `status`, `filled_price`, `slippage`, `brokerage`).

### `trade_journal`
Manual & automated trade review journal (`journal_id`, `position_id`, `symbol`, `entry_timestamp`, `exit_timestamp`, `setup_name`, `market_regime`, `pnl`, `pnl_pct`, `emotion_rating`, `mistakes`, `lessons`).

### `backtest_runs`
Stored strategy backtest experiments (`backtest_id`, `strategy_name`, `symbol`, `timeframe`, `initial_capital`, `final_capital`, `total_return_pct`, `win_rate_pct`, `profit_factor`, `max_drawdown_pct`, `walk_forward_status`).
