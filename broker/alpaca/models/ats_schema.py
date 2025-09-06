import os
from sqlalchemy import (
    create_engine, Column, Integer, String, Numeric, BigInteger, Date, DateTime,
    UniqueConstraint, Index, Boolean
)
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker
from utils.logging import get_logger

logger = get_logger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///db/openalgo.db')
engine = create_engine(
    DATABASE_URL,
    pool_size=50,
    max_overflow=100,
    pool_timeout=10
)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

class MarketData(Base):
    __tablename__ = 'market_data'
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol_id = Column(Integer)  # Removed ForeignKey to symtoken
    timestamp = Column(DateTime, nullable=False)
    open = Column(Numeric(12, 4))
    high = Column(Numeric(12, 4))
    low = Column(Numeric(12, 4))
    close = Column(Numeric(12, 4))
    volume = Column(BigInteger)

    __table_args__ = (
        UniqueConstraint('symbol_id', 'timestamp', name='uq_market_data_symbol_time'),
        Index('idx_market_data_symbol_time', 'symbol_id', 'timestamp'),
    )

class DailyWatchlist(Base):
    __tablename__ = 'daily_watchlist'
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    symbol_id = Column(Integer)  # Removed ForeignKey to symtoken
    rank = Column(Integer)
    reason = Column(String)
    status = Column(String(10), default='ACTIVE')

class TradeSignals(Base):
    __tablename__ = 'trade_signals'
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol_id = Column(Integer)  # Removed ForeignKey to symtoken
    signal_time = Column(DateTime)
    signal_type = Column(String(10))  # BUY/SELL/EXIT
    confidence = Column(Numeric(5, 2))
    executed = Column(Boolean, default=False)

class OpenPositions(Base):
    __tablename__ = 'open_positions'
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol_id = Column(Integer)  # Removed ForeignKey to symtoken
    entry_time = Column(DateTime)
    entry_price = Column(Numeric(12, 4))
    qty = Column(Integer)
    side = Column(String(4))  # LONG/SHORT
    status = Column(String(10), default='OPEN')  # OPEN/CLOSED
    last_update = Column(DateTime)

    __table_args__ = (
        Index('idx_open_positions_symbol_status', 'symbol_id', 'status'),
    )

# Utility

def init_db():
    logger.info('Initializing Alpaca ATS schema tables')
    Base.metadata.create_all(bind=engine)


def get_session():
    return db_session
