from datetime import datetime, timedelta
from utils.logging import get_logger
from broker.alpaca.models.ats_schema import get_session, MarketData
from database.symbol import SymToken as Symbols
from broker.alpaca.api.data import get_historical_data
from database.auth_db import get_latest_auth_token_by_broker

logger = get_logger(__name__)


def backfill_historical(symbol: str, days: int = 30, timeframe: str = '1d') -> int:
    """Backfill last N days of bars into market_data for a symbol."""
    auth = get_latest_auth_token_by_broker('alpaca')
    if not auth:
        logger.error('No Alpaca auth token found')
        return 0

    sess = get_session()
    try:
        sym = sess.query(Symbols).filter(Symbols.symbol == symbol).first()
        if not sym:
            logger.error(f'Symbol not found: {symbol}')
            return 0

        end = datetime.utcnow()
        start = end - timedelta(days=days)
        resp = get_historical_data(symbol, sym.exchange or 'NASDAQ', timeframe, start.isoformat()+'Z', end.isoformat()+'Z', auth)
        bars = resp.get('bars', {}).get(symbol, []) if isinstance(resp, dict) else []

        inserted = 0
        for bar in bars:
            ts = bar.get('t') or bar.get('timestamp')
            if not ts:
                continue
            # Normalize timestamp string
            ts_dt = datetime.fromisoformat(ts.replace('Z','+00:00')) if isinstance(ts, str) else ts
            md = MarketData(
                symbol_id=sym.id,
                timestamp=ts_dt,
                open=bar.get('o'),
                high=bar.get('h'),
                low=bar.get('l'),
                close=bar.get('c'),
                volume=bar.get('v')
            )
            # upsert: rely on unique(symbol_id, timestamp)
            try:
                sess.add(md)
                sess.commit()
                inserted += 1
            except Exception:
                sess.rollback()
        logger.info(f'Backfill inserted {inserted} rows for {symbol}')
        return inserted
    except Exception as e:
        logger.error(f'Backfill failed for {symbol}: {e}')
        return 0
    finally:
        sess.close()


def collect_incremental(symbols: list[str], timeframe: str = '1m') -> int:
    """Collect latest bars incrementally for a list of symbols."""
    auth = get_latest_auth_token_by_broker('alpaca')
    if not auth:
        logger.error('No Alpaca auth token found')
        return 0

    sess = get_session()
    total = 0
    try:
        for symbol in symbols:
            sym = sess.query(Symbols).filter(Symbols.symbol == symbol).first()
            if not sym:
                continue
            # fetch last hour to be safe
            end = datetime.utcnow()
            start = end - timedelta(hours=2)
            resp = get_historical_data(symbol, sym.exchange or 'NASDAQ', timeframe, start.isoformat()+'Z', end.isoformat()+'Z', auth)
            bars = resp.get('bars', {}).get(symbol, []) if isinstance(resp, dict) else []
            for bar in bars:
                ts = bar.get('t') or bar.get('timestamp')
                if not ts:
                    continue
                ts_dt = datetime.fromisoformat(ts.replace('Z','+00:00')) if isinstance(ts, str) else ts
                md = MarketData(
                    symbol_id=sym.id,
                    timestamp=ts_dt,
                    open=bar.get('o'),
                    high=bar.get('h'),
                    low=bar.get('l'),
                    close=bar.get('c'),
                    volume=bar.get('v')
                )
                try:
                    sess.add(md)
                    sess.commit()
                    total += 1
                except Exception:
                    sess.rollback()
        if total:
            logger.info(f'Incremental collected rows: {total}')
        return total
    except Exception as e:
        logger.error(f'Incremental collection failed: {e}')
        return 0
    finally:
        sess.close()
