from datetime import datetime, timedelta
from utils.logging import get_logger
from broker.alpaca.models.ats_schema import get_session, MarketData
from database.symbol import SymToken as Symbols
from broker.alpaca.api.data import get_historical_data
from database.auth_db import get_latest_auth_token_by_broker
import pytz

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
        
        logger.info(f"Retrieved {len(bars)} bars for {symbol} from {'Yahoo Finance' if 'error' not in resp else 'Alpaca'}")
        
        # Check if there's an error in the response
        if 'error' in resp and 'market data access denied' in resp['error'].lower():
            logger.warning(f"Market data access denied for {symbol}. Skipping historical data collection.")
            return 0

        inserted = 0
        updated = 0
        for bar in bars:
            ts = bar.get('t') or bar.get('timestamp')
            if not ts:
                logger.warning(f"Bar missing timestamp for {symbol}: {bar}")
                continue
            # Normalize timestamp string
            try:
                # Parse timestamp and normalize to UTC
                if isinstance(ts, str):
                    if ts.endswith('Z'):
                        ts_dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    else:
                        ts_dt = datetime.fromisoformat(ts)
                    
                    # Convert to UTC if it has timezone info
                    if ts_dt.tzinfo is not None:
                        ts_dt = ts_dt.astimezone(pytz.UTC).replace(tzinfo=None)
                    # If no timezone info, assume it's already UTC
                else:
                    ts_dt = ts
            except Exception as e:
                logger.error(f"Failed to parse timestamp '{ts}' for {symbol}: {e}")
                continue
                
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
                # Check if record exists
                existing = sess.query(MarketData).filter(
                    MarketData.symbol_id == sym.id,
                    MarketData.timestamp == ts_dt
                ).first()
                
                if existing:
                    # Update existing record
                    existing.open = bar.get('o')
                    existing.high = bar.get('h')
                    existing.low = bar.get('l')
                    existing.close = bar.get('c')
                    existing.volume = bar.get('v')
                    updated += 1
                else:
                    # Insert new record
                    sess.add(md)
                    inserted += 1
                
                sess.commit()
            except Exception as e:
                logger.error(f"Failed to upsert bar for {symbol} at {ts_dt}: {e}")
                sess.rollback()
        logger.info(f'Backfill for {symbol}: {inserted} inserted, {updated} updated')
        return inserted
    except Exception as e:
        logger.error(f'Backfill failed for {symbol}: {e}')
        return 0
    finally:
        sess.close()


def collect_incremental(symbols: list[str], timeframe: str = '1m') -> int:
    """Collect latest bars incrementally for a list of symbols."""
    from broker.alpaca.models.ats_schema import DailyWatchlist
    
    auth = get_latest_auth_token_by_broker('alpaca')
    if not auth:
        logger.error('No Alpaca auth token found - please authenticate with Alpaca first')
        return 0

    sess = get_session()
    total = 0
    try:
        # If no symbols provided, get all from active watchlist
        if not symbols:
            subq = sess.query(DailyWatchlist.symbol_id).filter(DailyWatchlist.status == 'ACTIVE').subquery()
            symbol_objs = sess.query(Symbols).filter(Symbols.id.in_(subq)).all()
            symbols = [s.symbol for s in symbol_objs]
            logger.info(f'Collecting data for {len(symbols)} watchlist symbols')
        
        if not symbols:
            logger.warning('No symbols to collect data for')
            return 0
            
        for symbol in symbols:
            sym = sess.query(Symbols).filter(Symbols.symbol == symbol).first()
            if not sym:
                continue
                
            # Get the latest timestamp for this symbol from database
            latest_record = sess.query(MarketData).filter(
                MarketData.symbol_id == sym.id
            ).order_by(MarketData.timestamp.desc()).first()
            
            if latest_record:
                # Start from the latest timestamp + 1 minute to avoid duplicates
                start = latest_record.timestamp + timedelta(minutes=1)
                logger.info(f'Incremental collection for {symbol}: starting from {start}')
            else:
                # No data exists, fetch last 2 hours as fallback
                start = datetime.utcnow() - timedelta(hours=2)
                logger.info(f'No existing data for {symbol}, starting from {start}')
            
            end = datetime.utcnow()
            
            # Only fetch if we have a reasonable time window
            if (end - start).total_seconds() < 60:  # Less than 1 minute
                logger.debug(f'Skipping {symbol}: time window too small ({end - start})')
                continue
                
            try:
                resp = get_historical_data(symbol, sym.exchange or 'NASDAQ', timeframe, start.isoformat()+'Z', end.isoformat()+'Z', auth)
                
                # Check if market data access is denied
                if 'error' in resp and 'market data access denied' in resp['error'].lower():
                    logger.warning(f"Market data access denied for {symbol}. Skipping historical data collection.")
                    continue
                    
                if not resp or not isinstance(resp, dict):
                    logger.warning(f'No data received for {symbol}')
                    continue
                    
                bars = resp.get('bars', {}).get(symbol, [])
                logger.info(f"Retrieved {len(bars)} bars for {symbol} from {'Yahoo Finance' if 'error' not in resp and resp.get('timeframe') else 'Alpaca'}")
                
                if not bars:
                    logger.debug(f'No new bars received for {symbol}')
                    continue
                    
            except Exception as api_error:
                logger.error(f'API error for {symbol}: {api_error}')
                continue
                
            inserted_count = 0
            updated_count = 0
            
            for bar in bars:
                ts = bar.get('t') or bar.get('timestamp')
                if not ts:
                    logger.warning(f"Bar missing timestamp for {symbol}: {bar}")
                    continue
                try:
                    # Parse timestamp and normalize to UTC
                    if isinstance(ts, str):
                        if ts.endswith('Z'):
                            ts_dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        else:
                            ts_dt = datetime.fromisoformat(ts)
                        
                        # Convert to UTC if it has timezone info
                        if ts_dt.tzinfo is not None:
                            ts_dt = ts_dt.astimezone(pytz.UTC).replace(tzinfo=None)
                        # If no timezone info, assume it's already UTC
                    else:
                        ts_dt = ts
                except Exception as e:
                    logger.error(f"Failed to parse timestamp '{ts}' for {symbol}: {e}")
                    continue
                    
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
                    # Check if record exists
                    existing = sess.query(MarketData).filter(
                        MarketData.symbol_id == sym.id,
                        MarketData.timestamp == ts_dt
                    ).first()
                    
                    if existing:
                        # Update existing record
                        existing.open = bar.get('o')
                        existing.high = bar.get('h')
                        existing.low = bar.get('l')
                        existing.close = bar.get('c')
                        existing.volume = bar.get('v')
                        updated_count += 1
                    else:
                        # Insert new record
                        sess.add(md)
                        inserted_count += 1
                    
                    sess.commit()
                    sess.commit()
                    total += 1
                except Exception as e:
                    logger.error(f"Failed to upsert bar for {symbol} at {ts_dt}: {e}")
                    sess.rollback()
                    
            # Log the actual results for this symbol
            if inserted_count > 0 or updated_count > 0:
                logger.info(f'Processed {symbol}: {inserted_count} inserted, {updated_count} updated')
                
        if total:
            logger.info(f'Incremental collected rows: {total}')
        return total
    except Exception as e:
        logger.error(f'Incremental collection failed: {e}')
        return 0
    finally:
        sess.close()
