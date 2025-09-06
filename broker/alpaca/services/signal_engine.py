from datetime import datetime
from utils.logging import get_logger
from broker.alpaca.models.ats_schema import (
    get_session, DailyWatchlist, MarketData, TradeSignals, OpenPositions
)
from database.symbol import SymToken as Symbols

logger = get_logger(__name__)

# Simple strategy: moving average crossover on last N bars (placeholder)

def generate_signals(window_short: int = 5, window_long: int = 20) -> int:
    sess = get_session()
    created = 0
    try:
        # active watchlist symbols
        subq = sess.query(DailyWatchlist.symbol_id).filter(DailyWatchlist.status == 'ACTIVE').subquery()
        symbols = sess.query(Symbols).filter(Symbols.id.in_(subq)).all()

        for sym in symbols:
            # skip if trade open
            pos = sess.query(OpenPositions).filter(OpenPositions.symbol_id == sym.id, OpenPositions.status == 'OPEN').first()
            if pos:
                # check for exit
                if _should_exit(sess, sym.id, window_short, window_long):
                    ts = TradeSignals(
                        symbol_id=sym.id,
                        signal_time=datetime.utcnow(),
                        signal_type='EXIT',
                        confidence=1.0
                    )
                    sess.add(ts)
                    created += 1
                continue

            # no open trade -> check entry
            direction = _entry_direction(sess, sym.id, window_short, window_long)
            if direction:
                ts = TradeSignals(
                    symbol_id=sym.id,
                    signal_time=datetime.utcnow(),
                    signal_type=direction,
                    confidence=0.8
                )
                sess.add(ts)
                created += 1
        sess.commit()
        return created
    except Exception as e:
        logger.error(f'Signal generation failed: {e}')
        sess.rollback()
        return 0
    finally:
        sess.close()


def _entry_direction(sess, symbol_id: int, w_s: int, w_l: int) -> str | None:
    bars = (sess.query(MarketData)
            .filter(MarketData.symbol_id == symbol_id)
            .order_by(MarketData.timestamp.desc())
            .limit(max(w_l, w_s) + 2)
            .all())
    if len(bars) < max(w_l, w_s):
        return None
    closes = [float(b.close or 0) for b in reversed(bars)]
    short = sum(closes[-w_s:]) / w_s
    long = sum(closes[-w_l:]) / w_l
    if short > long:
        return 'BUY'
    if short < long:
        return 'SELL'
    return None


def _should_exit(sess, symbol_id: int, w_s: int, w_l: int) -> bool:
    bars = (sess.query(MarketData)
            .filter(MarketData.symbol_id == symbol_id)
            .order_by(MarketData.timestamp.desc())
            .limit(max(w_l, w_s) + 2)
            .all())
    if len(bars) < max(w_l, w_s):
        return False
    closes = [float(b.close or 0) for b in reversed(bars)]
    short = sum(closes[-w_s:]) / w_s
    long = sum(closes[-w_l:]) / w_l
    # exit when cross reverts
    return abs(short - long) < 0.01
