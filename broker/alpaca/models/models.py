import os
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Date, DateTime, Numeric, BigInteger,
    ForeignKey, Index, UniqueConstraint, Boolean
)
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from utils.logging import get_logger

# Reuse the project's DATABASE_URL
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///db/openalgo.db')
logger = get_logger(__name__)

# Create engine/session locally to keep module self-contained but aligned with main DB
engine = create_engine(
    DATABASE_URL,
    pool_size=50,
    max_overflow=100,
    pool_timeout=10
)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

# Import SymToken definition for FK references when available at runtime
try:
    from database.symbol import SymToken  # type: ignore
except Exception:
    SymToken = None  # Will still allow model creation; FK uses table name


class MarketData(Base):
    __tablename__ = 'market_data'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol_id = Column(Integer, ForeignKey('symtoken.id'), index=True, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    open = Column(Numeric(12, 4))
    high = Column(Numeric(12, 4))
    low = Column(Numeric(12, 4))
    close = Column(Numeric(12, 4))
    volume = Column(BigInteger)

    __table_args__ = (
        UniqueConstraint('symbol_id', 'timestamp', name='uq_market_data_symbol_ts'),
        Index('idx_market_data_symbol_ts', 'symbol_id', 'timestamp'),
    )


class DailyWatchlist(Base):
    __tablename__ = 'daily_watchlist'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    symbol_id = Column(Integer, ForeignKey('symtoken.id'), index=True, nullable=False)
    rank = Column(Integer)
    reason = Column(String)
    status = Column(String(10), default='ACTIVE', index=True)

    __table_args__ = (
        Index('idx_watchlist_date_symbol', 'date', 'symbol_id'),
    )


class TradeSignal(Base):
    __tablename__ = 'trade_signals'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol_id = Column(Integer, ForeignKey('symtoken.id'), index=True, nullable=False)
    signal_time = Column(DateTime, default=datetime.utcnow, index=True)
    signal_type = Column(String(10))  # BUY/SELL/EXIT
    confidence = Column(Numeric(5, 2))
    executed = Column(Boolean, default=False, index=True)

    __table_args__ = (
        Index('idx_signals_symbol_time', 'symbol_id', 'signal_time'),
        Index('idx_signals_executed', 'executed'),
    )


class OpenPosition(Base):
    __tablename__ = 'open_positions'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol_id = Column(Integer, ForeignKey('symtoken.id'), index=True, nullable=False)
    side = Column(String(4), nullable=False)  # BUY/SELL
    quantity = Column(Integer, nullable=False)
    avg_entry_price = Column(Numeric(12, 4))
    entry_time = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String(10), default='OPEN', index=True)  # OPEN/CLOSED
    last_update = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    exit_time = Column(DateTime)
    exit_price = Column(Numeric(12, 4))
    pnl = Column(Numeric(14, 4))

    __table_args__ = (
        Index('idx_open_positions_symbol_status', 'symbol_id', 'status'),
    )


def init_db():
    """Create ATS tables if they don't exist."""
    logger.info("Initializing Alpaca ATS tables (market_data, daily_watchlist, trade_signals, open_positions)")
    Base.metadata.create_all(bind=engine)
