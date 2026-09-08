from sqlalchemy import Column, Integer, String, Float, Boolean, BigInteger, Index, DateTime, Text, JSON
from sqlalchemy.sql import func
from backend.app.database.connection import Base

class MarketTickModel(Base):
    __tablename__ = "market_ticks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider = Column(String(50), nullable=False, index=True)
    instrument_key = Column(String(100), nullable=True, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    ltp = Column(Float, nullable=False)
    volume = Column(BigInteger, default=0)
    bid = Column(Float, nullable=True)
    ask = Column(Float, nullable=True)
    raw_timestamp = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MarketCandleModel(Base):
    __tablename__ = "market_candles"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False, index=True)
    interval = Column(String(20), nullable=False, index=True)
    timestamp = Column(BigInteger, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(BigInteger, default=0)
    source = Column(String(50), default="UPSTOX")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class OptionSnapshotModel(Base):
    __tablename__ = "option_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    underlying = Column(String(50), nullable=False, index=True)
    expiry = Column(String(30), nullable=True)
    strike = Column(Float, nullable=False, index=True)
    option_type = Column(String(10), nullable=False) # CALL or PUT
    timestamp = Column(Float, nullable=False, index=True)
    ltp = Column(Float, default=0.0)
    oi = Column(BigInteger, default=0)
    volume = Column(BigInteger, default=0)
    iv = Column(Float, nullable=True)
    delta = Column(Float, nullable=True)
    gamma = Column(Float, nullable=True)
    theta = Column(Float, nullable=True)
    vega = Column(Float, nullable=True)
    bid = Column(Float, default=0.0)
    ask = Column(Float, default=0.0)
    source = Column(String(50), default="UPSTOX")
    provenance = Column(String(50), default="RECORDED_AUTHENTIC")
    provider_instrument_key = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class MarketInformationModel(Base):
    __tablename__ = "market_information"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    info_type = Column(String(50), nullable=False, index=True) # fii-dii, oi, pcr, max-pain
    symbol = Column(String(50), nullable=True, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    data_json = Column(JSON, nullable=False)
    source = Column(String(50), default="UPSTOX")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ProviderHealthModel(Base):
    __tablename__ = "provider_health"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider = Column(String(50), nullable=False, index=True)
    timestamp = Column(Float, nullable=False, index=True)
    status = Column(String(50), nullable=False) # CONNECTED, DISCONNECTED, CONFIGURATION_ERROR
    latency_ms = Column(Float, nullable=True)
    last_tick = Column(Float, nullable=True)
    error_code = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Explicit composite indexes
Index("idx_candle_sym_tf_ts", MarketCandleModel.symbol, MarketCandleModel.interval, MarketCandleModel.timestamp)
Index("idx_tick_sym_ts", MarketTickModel.symbol, MarketTickModel.timestamp)
Index("idx_option_und_strike_ts", OptionSnapshotModel.underlying, OptionSnapshotModel.strike, OptionSnapshotModel.timestamp)

# Paper Trading Durable Domain Models
class PaperAccountModel(Base):
    __tablename__ = "paper_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(100), unique=True, nullable=False, index=True)
    available_capital = Column(Float, nullable=False, default=1000000.0)
    initial_capital = Column(Float, nullable=False, default=1000000.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PaperOrderModel(Base):
    __tablename__ = "paper_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(100), unique=True, nullable=False, index=True)
    account_id = Column(String(100), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    exchange = Column(String(20), nullable=False, default="NSE")
    side = Column(String(10), nullable=False)
    order_type = Column(String(20), nullable=False, default="MARKET")
    product_type = Column(String(20), nullable=False, default="CNC")
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    requested_price = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    status = Column(String(30), nullable=False, default="FILLED")
    source = Column(String(50), default="MANUAL")
    signal_id = Column(String(100), nullable=True, index=True)
    candidate_id = Column(String(100), nullable=True)
    strategy_version = Column(String(50), nullable=True)
    signal_engine_version = Column(String(50), nullable=True)
    configuration_hash = Column(String(100), nullable=True)
    decision_reason = Column(Text, nullable=True)
    rejection_reason = Column(String(255), nullable=True)
    filled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PaperPositionModel(Base):
    __tablename__ = "paper_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    position_id = Column(String(100), unique=True, nullable=False, index=True)
    account_id = Column(String(100), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    side = Column(String(10), nullable=False)
    product_type = Column(String(20), nullable=False, default="CNC")
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    target_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    margin_locked = Column(Float, nullable=False, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PaperFillModel(Base):
    __tablename__ = "paper_fills"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fill_id = Column(String(100), unique=True, nullable=False, index=True)
    order_id = Column(String(100), nullable=False, index=True)
    account_id = Column(String(100), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    side = Column(String(10), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    brokerage = Column(Float, default=20.0)
    stt = Column(Float, default=0.0)
    exchange_charges = Column(Float, default=0.0)
    sebi_charges = Column(Float, default=0.0)
    gst = Column(Float, default=0.0)
    stamp_duty = Column(Float, default=0.0)
    taxes = Column(Float, default=0.0)
    slippage = Column(Float, default=0.0)
    timestamp = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PaperClosedTradeModel(Base):
    __tablename__ = "paper_closed_trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_id = Column(String(100), unique=True, nullable=False, index=True)
    account_id = Column(String(100), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    side = Column(String(10), nullable=False)
    product_type = Column(String(20), nullable=False)
    quantity = Column(Integer, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    gross_pnl = Column(Float, nullable=False)
    brokerage = Column(Float, default=20.0)
    taxes = Column(Float, default=0.0)
    realized_pnl = Column(Float, nullable=False)
    entry_time = Column(Float, nullable=True)
    closed_at = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Research Durable Domain Models
class ResearchHypothesisModel(Base):
    __tablename__ = "research_hypotheses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hypothesis_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    technical_strategy_id = Column(String(100), nullable=False, index=True)
    fundamental_factor_id = Column(String(100), nullable=False, index=True)
    regime_filter = Column(String(50), nullable=True)
    universe = Column(String(50), nullable=False, default="NIFTY50")
    timeframe = Column(String(20), nullable=False, default="1D")
    status = Column(String(50), nullable=False, default="HYPOTHESIS_FORMULATED")
    scorecard_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ResearchExperimentModel(Base):
    __tablename__ = "research_experiments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_id = Column(String(100), unique=True, nullable=False, index=True)
    strategy_id = Column(String(100), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    timeframe = Column(String(20), nullable=False, default="5m")
    parameters_json = Column(JSON, nullable=False)
    metrics_json = Column(JSON, nullable=False)
    workflow_state = Column(String(50), default="RESEARCH_CANDIDATE")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Signal Intelligence Engine Durable Domain Models
# ---------------------------------------------------------------------------

class SignalModel(Base):
    """
    Authoritative persistent representation of generated trade opportunities.
    Survives worker restarts, crashes, and distributed instances.
    """
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(String(100), unique=True, nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    exchange = Column(String(20), nullable=False, default="NSE")
    instrument_id = Column(String(100), nullable=True)
    asset_class = Column(String(20), nullable=False, default="EQUITY")
    direction = Column(String(20), nullable=False, index=True)
    signal_type = Column(String(30), nullable=False)
    timeframe = Column(String(20), nullable=False, default="15m")
    state = Column(String(30), nullable=False, default="QUALIFIED", index=True)
    quality_grade = Column(String(20), nullable=False, default="A", index=True)
    opportunity_score = Column(Float, nullable=False, default=0.0)
    confidence = Column(Float, nullable=False, default=0.0)
    is_heuristic_confidence = Column(Boolean, default=True)
    calibrated_probability = Column(Float, nullable=True)
    entry = Column(Float, nullable=True)
    entry_zone_low = Column(Float, nullable=True)
    entry_zone_high = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    stop_method = Column(String(50), nullable=True)
    target_1 = Column(Float, nullable=True)
    target_2 = Column(Float, nullable=True)
    target_3 = Column(Float, nullable=True)
    target_method = Column(String(50), nullable=True)
    risk_reward = Column(Float, nullable=False, default=0.0)
    position_size_json = Column(JSON, nullable=True)
    liquidity_score = Column(Float, default=0.0)
    market_regime = Column(String(50), default="UNKNOWN")
    regime_compatible = Column(Boolean, default=True)
    mtf_alignment_score = Column(Float, default=0.0)
    mtf_result_json = Column(JSON, nullable=True)
    confluence_score = Column(Float, default=0.0)
    confluence_label = Column(String(50), nullable=True)
    confluence_json = Column(JSON, nullable=True)
    why_reasons_json = Column(JSON, nullable=True)
    invalidation_conditions_json = Column(JSON, nullable=True)
    rejection_reasons_json = Column(JSON, nullable=True)
    provenance = Column(String(50), default="RAW_AUTHENTIC_DATA")
    expiry = Column(String(50), nullable=True)
    expiry_condition = Column(String(255), default="Valid until end of session")
    candles_used = Column(Integer, default=0)
    candidate_id = Column(String(100), nullable=True, index=True)
    strategy_version = Column(String(50), nullable=True)
    signal_engine_version = Column(String(50), nullable=True)
    configuration_hash = Column(String(100), nullable=True, index=True)
    git_commit = Column(String(100), nullable=True)
    market_timestamp = Column(Float, nullable=True)
    data_age_ms = Column(Float, nullable=True)
    spread = Column(Float, nullable=True)
    effective_strategy_count = Column(Integer, default=0)
    volatility_regime = Column(String(50), nullable=True)
    trend_regime = Column(String(50), nullable=True)
    breadth_regime = Column(String(50), nullable=True)
    liquidity_regime = Column(String(50), nullable=True)
    futures_decision_json = Column(JSON, nullable=True)
    options_decision_json = Column(JSON, nullable=True)
    cost_estimate_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SignalEventModel(Base):
    """
    Immutable audit trail for all signal lifecycle state transitions.
    """
    __tablename__ = "signal_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(String(100), nullable=False, index=True)
    from_state = Column(String(30), nullable=False)
    to_state = Column(String(30), nullable=False, index=True)
    transition_reason = Column(String(255), nullable=False)
    trigger_price = Column(Float, nullable=True)
    event_timestamp = Column(Float, nullable=False, index=True)
    event_metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SignalStrategyVoteModel(Base):
    """
    Strategy consensus votes stored permanently with the signal.
    """
    __tablename__ = "signal_strategy_votes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(String(100), nullable=False, index=True)
    strategy_id = Column(String(100), nullable=False, index=True)
    strategy_name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    direction = Column(String(20), nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)
    strength = Column(Float, nullable=False, default=0.0)
    rules_passing = Column(Integer, default=0)
    rules_total = Column(Integer, default=1)
    is_correlated = Column(Boolean, default=False)
    correlated_family = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SignalRejectionModel(Base):
    """
    Durable log of candidates rejected by hard or soft gates.
    """
    __tablename__ = "signal_rejections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False, index=True)
    gate_failed = Column(String(100), nullable=False, index=True)
    gate_type = Column(String(20), nullable=False, default="HARD")
    category = Column(String(50), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    evidence = Column(Text, nullable=True)
    actual_value = Column(Float, nullable=True)
    threshold_value = Column(Float, nullable=True)
    partial_score = Column(Float, default=0.0)
    actionable_advice = Column(Text, nullable=True)
    candidate_id = Column(String(100), nullable=True, index=True)
    strategy_version = Column(String(50), nullable=True)
    configuration_hash = Column(String(100), nullable=True, index=True)
    git_commit = Column(String(100), nullable=True)
    market_timestamp = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class CandidateObservationModel(Base):
    """
    Durable Signal Observatory model recording EVERY evaluated market candidate.
    Tracks both qualified opportunities and rejected candidates across all 17 gates.
    """
    __tablename__ = "candidate_observations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(String(100), unique=True, nullable=False, index=True)
    signal_id = Column(String(100), nullable=True, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    exchange = Column(String(20), default="NSE")
    asset_class = Column(String(20), default="EQUITY")
    evaluation_status = Column(String(50), nullable=False, index=True)  # QUALIFIED | REJECTED_BY_RISK | REJECTED_BY_REGIME | REJECTED_BY_DATA_QUALITY | REJECTED_BY_RR | REJECTED_BY_CONFLUENCE | REJECTED_BY_LIQUIDITY | REJECTED_BY_OPTIONS
    direction = Column(String(20), default="NO_TRADE")
    strategy_version = Column(String(50), nullable=True)
    signal_engine_version = Column(String(50), nullable=True)
    configuration_hash = Column(String(100), nullable=True, index=True)
    git_commit = Column(String(100), nullable=True)
    market_timestamp = Column(Float, nullable=True)
    data_provenance = Column(String(50), default="RAW_AUTHENTIC_DATA")
    is_live = Column(Boolean, default=False)
    data_age_ms = Column(Float, nullable=True)
    last_price = Column(Float, nullable=True)
    volume = Column(BigInteger, default=0)
    liquidity_score = Column(Float, default=0.0)
    spread = Column(Float, nullable=True)
    market_regime = Column(String(50), default="UNKNOWN")
    regime_confidence = Column(Float, default=0.0)
    opportunity_score = Column(Float, default=0.0)
    heuristic_confidence = Column(Float, default=0.0)
    calibrated_probability = Column(Float, nullable=True)
    quality_grade = Column(String(20), default="NO TRADE")
    decision_reason = Column(Text, nullable=True)
    rejection_gate = Column(String(100), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    actionable_advice = Column(Text, nullable=True)
    mtf_state_json = Column(JSON, nullable=True)
    strategy_votes_json = Column(JSON, nullable=True)
    confluence_json = Column(JSON, nullable=True)
    hard_gates_passed = Column(Integer, default=0)
    hard_gates_failed = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class SignalOutcomeModel(Base):
    """
    Post-trade forward market evaluation tracking actual price excursion and outcome.
    """
    __tablename__ = "signal_outcomes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    signal_id = Column(String(100), unique=True, nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    asset_class = Column(String(20), nullable=False)
    direction = Column(String(20), nullable=False)
    status = Column(String(30), nullable=False, index=True)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    stop_loss_price = Column(Float, nullable=False)
    target_1_price = Column(Float, nullable=False)
    mae = Column(Float, nullable=False, default=0.0)
    mfe = Column(Float, nullable=False, default=0.0)
    mae_pct = Column(Float, nullable=False, default=0.0)
    mfe_pct = Column(Float, nullable=False, default=0.0)
    mae_r = Column(Float, nullable=False, default=0.0)
    mfe_r = Column(Float, nullable=False, default=0.0)
    realized_r = Column(Float, nullable=False, default=0.0)
    gross_pnl = Column(Float, nullable=False, default=0.0)
    brokerage = Column(Float, default=0.0)
    stt = Column(Float, default=0.0)
    exchange_charges = Column(Float, default=0.0)
    sebi_charges = Column(Float, default=0.0)
    gst = Column(Float, default=0.0)
    stamp_duty = Column(Float, default=0.0)
    slippage = Column(Float, default=0.0)
    net_pnl = Column(Float, nullable=False, default=0.0)
    holding_candles = Column(Integer, default=0)
    holding_time_seconds = Column(Float, default=0.0)
    entry_timestamp = Column(Float, nullable=False)
    exit_timestamp = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class SignalPerformanceSnapshotModel(Base):
    """
    Historical aggregated performance metrics across strategies, regimes, and grades.
    """
    __tablename__ = "signal_performance_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dimension_type = Column(String(50), nullable=False, index=True)
    dimension_value = Column(String(100), nullable=False, index=True)
    sample_size = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    average_r = Column(Float, default=0.0)
    expectancy = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    max_drawdown_r = Column(Float, default=0.0)
    avg_mae_r = Column(Float, default=0.0)
    avg_mfe_r = Column(Float, default=0.0)
    avg_holding_time_minutes = Column(Float, default=0.0)
    snapshot_timestamp = Column(Float, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SignalCalibrationBucketModel(Base):
    """
    Calibration evaluation table comparing predicted confidence vs observed outcome frequency.
    """
    __tablename__ = "signal_calibration_buckets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    bucket_range = Column(String(50), nullable=False, index=True)
    sample_size = Column(Integer, default=0)
    predicted_midpoint = Column(Float, nullable=False)
    actual_win_rate = Column(Float, nullable=False, default=0.0)
    calibration_error = Column(Float, nullable=False, default=0.0)
    brier_score_contribution = Column(Float, default=0.0)
    snapshot_timestamp = Column(Float, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WorkerHeartbeatModel(Base):
    """
    Persistent heartbeat and operational telemetry emitted by the Stateful Market Worker.
    Queried by REST/API endpoints to provide real-time dashboard observability across distributed deployments.
    """
    __tablename__ = "worker_heartbeats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    worker_id = Column(String(100), unique=True, nullable=False, index=True)
    experiment_id = Column(String(100), nullable=False, index=True)
    worker_status = Column(String(50), nullable=False, default="STARTING")  # STARTING, ONLINE, STOPPED, ERROR
    market_connection = Column(String(50), nullable=False, default="DISCONNECTED")  # CONNECTED, DISCONNECTED, RECONNECTING
    database_status = Column(String(50), nullable=False, default="ONLINE")
    paper_mode = Column(Boolean, nullable=False, default=True)
    live_trading = Column(Boolean, nullable=False, default=False)
    
    last_tick = Column(Float, nullable=True)
    last_event = Column(String(100), nullable=True)
    last_market_event = Column(String(100), nullable=True)
    last_signal_event = Column(String(100), nullable=True)
    last_paper_event = Column(String(100), nullable=True)

    signal_count = Column(Integer, default=0)
    candidate_count = Column(Integer, default=0)
    paper_order_count = Column(Integer, default=0)
    open_positions = Column(Integer, default=0)
    closed_positions = Column(Integer, default=0)

    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    total_costs = Column(Float, default=0.0)
    net_pnl = Column(Float, default=0.0)

    data_quality = Column(String(50), default="AUTHENTIC_LIVE")
    reconnect_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    
    details_json = Column(JSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


# Composite index for signal querying
Index("idx_signal_sym_state", SignalModel.symbol, SignalModel.state)
Index("idx_signal_grade_score", SignalModel.quality_grade, SignalModel.opportunity_score)
Index("idx_outcome_status_r", SignalOutcomeModel.status, SignalOutcomeModel.realized_r)
Index("idx_perf_dim_ts", SignalPerformanceSnapshotModel.dimension_type, SignalPerformanceSnapshotModel.dimension_value, SignalPerformanceSnapshotModel.snapshot_timestamp)
Index("idx_cand_obs_sym_status", CandidateObservationModel.symbol, CandidateObservationModel.evaluation_status)
Index("idx_order_signal_id", PaperOrderModel.signal_id)
Index("idx_worker_id_updated", WorkerHeartbeatModel.worker_id, WorkerHeartbeatModel.updated_at)




