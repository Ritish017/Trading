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
