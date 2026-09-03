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


