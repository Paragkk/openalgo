from datetime import datetime, date
from utils.logging import get_logger
from broker.alpaca.models.ats_schema import get_session, TradeSignals, OpenPositions
from database.symbol import SymToken as Symbols
from broker.alpaca.api.order_api import place_order_api
from database.auth_db import get_latest_auth_token_by_broker
from broker.alpaca.models.ats_schema import DailyWatchlist
from broker.alpaca.api.order_api import place_smartorder_api

logger = get_logger(__name__)

# Simple risk checks
MAX_EXPOSURE = 3  # max concurrent positions


def process_trade_signals() -> int:
    """Read unexecuted trade_signals, run checks, place orders, and lock positions."""
    sess = get_session()
    executed = 0
    try:
        auth = get_latest_auth_token_by_broker('alpaca')
        if not auth:
            logger.error('No Alpaca auth token found')
            return 0

        # exposure check
        open_count = sess.query(OpenPositions).filter(OpenPositions.status == 'OPEN').count()
        budget = max(0, MAX_EXPOSURE - open_count)
        if budget <= 0:
            logger.info('Exposure limit reached; skipping execution')
            return 0

        signals = (sess.query(TradeSignals)
                   .filter(TradeSignals.executed == False)  # noqa: E712
                   .order_by(TradeSignals.signal_time.asc())
                   .limit(budget)
                   .all())

        for sig in signals:
            sym = sess.query(Symbols).filter(Symbols.id == sig.symbol_id).first()
            if not sym:
                continue
            # one-active-trade-per-symbol rule
            pos = sess.query(OpenPositions).filter(OpenPositions.symbol_id == sym.id, OpenPositions.status == 'OPEN').first()
            if pos and sig.signal_type != 'EXIT':
                logger.info(f'Skip {sym.symbol}, already has open position')
                sig.executed = True
                sess.commit()
                continue

            if sig.signal_type in ('BUY', 'SELL'):
                side = 'buy' if sig.signal_type == 'BUY' else 'sell'
                payload = {
                    'symbol': sym.symbol,
                    'qty': '1',
                    'side': side,
                    'type': 'market',
                    'time_in_force': 'day'
                }
                resp = place_order_api(payload, auth)
                if isinstance(resp, dict) and 'id' in resp:
                    # lock position
                    op = OpenPositions(
                        symbol_id=sym.id,
                        entry_time=datetime.utcnow(),
                        entry_price=None,
                        qty=1,
                        side='LONG' if side == 'buy' else 'SHORT',
                        status='OPEN',
                        last_update=datetime.utcnow()
                    )
                    sess.add(op)
                    # pause watchlist for this symbol today
                    today = date.today()
                    wl = (sess.query(DailyWatchlist)
                          .filter(DailyWatchlist.symbol_id == sym.id, DailyWatchlist.date == today)
                          .first())
                    if wl:
                        wl.status = 'PAUSED'
                    sig.executed = True
                    sess.commit()
                    executed += 1
            elif sig.signal_type == 'EXIT':
                # mark position closed
                pos = sess.query(OpenPositions).filter(OpenPositions.symbol_id == sym.id, OpenPositions.status == 'OPEN').first()
                if pos:
                    # Place smart close order
                    payload = {'symbol': sym.symbol}
                    place_smartorder_api(payload, auth)
                    pos.status = 'CLOSED'
                    pos.last_update = datetime.utcnow()
                    # reactivate watchlist
                    today = date.today()
                    wl = (sess.query(DailyWatchlist)
                          .filter(DailyWatchlist.symbol_id == sym.id, DailyWatchlist.date == today)
                          .first())
                    if wl:
                        wl.status = 'ACTIVE'
                    sig.executed = True
                    sess.commit()
                    executed += 1
        return executed
    except Exception as e:
        logger.error(f'Execution engine failed: {e}')
        sess.rollback()
        return 0
    finally:
        sess.close()
