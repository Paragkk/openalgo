import os
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
from utils.logging import get_logger
from database.auth_db import get_auth_token
from broker.alpaca.api.data import get_historical_data, get_current_price
from broker.alpaca.api.order_api import place_order_api
from broker.alpaca.database.master_contract_db import db_session as sym_db_session, SymToken
from broker.alpaca.models.models import (
    db_session, init_db, MarketData, DailyWatchlist, TradeSignal, OpenPosition
)

logger = get_logger(__name__)


def ensure_initialized():
    """Ensure ATS tables are created."""
    init_db()


# 1) Screener: pick top N by simple heuristic (e.g., highest price) for demo
def run_daily_screener(top_n: int = 10, reason: str = 'SIMPLE_TOP_PRICE') -> Dict:
    ensure_initialized()
    today = date.today()
    try:
        # Example: choose active NASDAQ large caps by symbol prefix (A..), limit to top N alphabetically
        symbols = (
            sym_db_session.query(SymToken)
            .filter(SymToken.exchange.in_(['NASDAQ', 'NYSE']))
            .order_by(SymToken.symbol.asc())
            .limit(200)
            .all()
        )
        picked = symbols[:top_n]

        # Insert into daily_watchlist
        for idx, sym in enumerate(picked, start=1):
            existing = (
                db_session.query(DailyWatchlist)
                .filter(DailyWatchlist.date == today, DailyWatchlist.symbol_id == sym.id)
                .first()
            )
            if existing:
                existing.rank = idx
                existing.reason = reason
                existing.status = 'ACTIVE'
            else:
                db_session.add(DailyWatchlist(
                    date=today,
                    symbol_id=sym.id,
                    rank=idx,
                    reason=reason,
                    status='ACTIVE'
                ))
        db_session.commit()
        return {"status": "ok", "count": len(picked)}
    except Exception as e:
        db_session.rollback()
        logger.error(f"Screener failed: {e}")
        return {"status": "error", "message": str(e)}


# 2) Data Collector: fetch historical bars and append to market_data
def collect_historical_data(days: int = 5, timeframe: str = '1m', user_id: Optional[str] = None) -> Dict:
    ensure_initialized()
    try:
        # Get watchlist symbols
        today = date.today()
        watchlist = (
            db_session.query(DailyWatchlist, SymToken)
            .join(SymToken, DailyWatchlist.symbol_id == SymToken.id)
            .filter(DailyWatchlist.date == today, DailyWatchlist.status == 'ACTIVE')
            .all()
        )
        if not watchlist:
            return {"status": "ok", "message": "No symbols in watchlist"}

        auth_user = user_id or os.getenv('DEFAULT_USER') or ''
        auth = get_auth_token(auth_user)
        if not auth:
            return {"status": "error", "message": "No auth token configured for Alpaca"}

        start = (datetime.utcnow() - timedelta(days=days)).isoformat() + 'Z'
        end = datetime.utcnow().isoformat() + 'Z'

        inserted = 0
        for wl, sym in watchlist:
            bars = get_historical_data(sym.symbol, sym.exchange, timeframe, start, end, auth)
            series = (bars or {}).get('bars', {}).get(sym.symbol, [])
            for b in series:
                ts = b.get('t') or b.get('timestamp')
                if not ts:
                    continue
                ts_dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                # Upsert by (symbol_id, timestamp)
                existing = (
                    db_session.query(MarketData)
                    .filter(MarketData.symbol_id == sym.id, MarketData.timestamp == ts_dt)
                    .first()
                )
                if existing:
                    existing.open = b.get('o')
                    existing.high = b.get('h')
                    existing.low = b.get('l')
                    existing.close = b.get('c')
                    existing.volume = b.get('v')
                else:
                    db_session.add(MarketData(
                        symbol_id=sym.id,
                        timestamp=ts_dt,
                        open=b.get('o'),
                        high=b.get('h'),
                        low=b.get('l'),
                        close=b.get('c'),
                        volume=b.get('v')
                    ))
                    inserted += 1
        db_session.commit()
        return {"status": "ok", "inserted": inserted}
    except Exception as e:
        db_session.rollback()
        logger.error(f"Historical data collection failed: {e}")
        return {"status": "error", "message": str(e)}


def _sma(values: List[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    return sum(values[-period:]) / period


# 3) Signal Engine: simple SMA crossover (fast 5 vs slow 20)
def run_signal_engine() -> Dict:
    ensure_initialized()
    try:
        today = date.today()
        active = (
            db_session.query(DailyWatchlist, SymToken)
            .join(SymToken, DailyWatchlist.symbol_id == SymToken.id)
            .filter(DailyWatchlist.date == today, DailyWatchlist.status == 'ACTIVE')
            .all()
        )
        created = 0
        for wl, sym in active:
            # Skip if open trade exists
            openpos = (
                db_session.query(OpenPosition)
                .filter(OpenPosition.symbol_id == sym.id, OpenPosition.status == 'OPEN')
                .first()
            )
            if openpos:
                # Only check for EXIT condition
                prices = (
                    db_session.query(MarketData)
                    .filter(MarketData.symbol_id == sym.id)
                    .order_by(MarketData.timestamp.asc())
                    .all()
                )
                closes = [float(p.close or 0) for p in prices][-30:]
                fast = _sma(closes, 5)
                slow = _sma(closes, 20)
                if fast is not None and slow is not None and fast < slow:
                    db_session.add(TradeSignal(
                        symbol_id=sym.id,
                        signal_type='EXIT',
                        confidence=95
                    ))
                    created += 1
                continue

            # Generate entry signals
            prices = (
                db_session.query(MarketData)
                .filter(MarketData.symbol_id == sym.id)
                .order_by(MarketData.timestamp.asc())
                .all()
            )
            closes = [float(p.close or 0) for p in prices][-30:]
            fast = _sma(closes, 5)
            slow = _sma(closes, 20)
            if fast is None or slow is None:
                continue

            if fast > slow:
                sig = TradeSignal(symbol_id=sym.id, signal_type='BUY', confidence=90)
                db_session.add(sig)
                created += 1
            elif fast < slow:
                sig = TradeSignal(symbol_id=sym.id, signal_type='SELL', confidence=90)
                db_session.add(sig)
                created += 1

        db_session.commit()
        return {"status": "ok", "signals": created}
    except Exception as e:
        db_session.rollback()
        logger.error(f"Signal engine failed: {e}")
        return {"status": "error", "message": str(e)}


# 4) Execution Engine: consume unexecuted signals, risk checks, place orders, lock symbol
def run_execution_engine(max_positions: int = 5, user_id: Optional[str] = None) -> Dict:
    ensure_initialized()
    try:
        # Risk: max open positions
        open_count = db_session.query(OpenPosition).filter(OpenPosition.status == 'OPEN').count()
        capacity = max(0, max_positions - open_count)
        if capacity == 0:
            return {"status": "ok", "placed": 0, "message": "Capacity full"}

        # Get next signals, oldest first
        signals = (
            db_session.query(TradeSignal, SymToken)
            .join(SymToken, TradeSignal.symbol_id == SymToken.id)
            .filter(TradeSignal.executed == False)  # noqa: E712
            .order_by(TradeSignal.signal_time.asc())
            .limit(capacity)
            .all()
        )

        if not signals:
            return {"status": "ok", "placed": 0}

        user = user_id or os.getenv('DEFAULT_USER') or ''
        auth = get_auth_token(user)
        if not auth:
            return {"status": "error", "message": "No auth token"}

        placed = 0
        for sig, sym in signals:
            # Enforce one-active-trade-per-symbol
            already_open = (
                db_session.query(OpenPosition)
                .filter(OpenPosition.symbol_id == sym.id, OpenPosition.status == 'OPEN')
                .first()
            )
            if already_open and sig.signal_type != 'EXIT':
                sig.executed = True  # mark as consumed with no action
                continue

            if sig.signal_type == 'EXIT':
                # For simplicity, mark position closed; real exit would place closing order
                pos = (
                    db_session.query(OpenPosition)
                    .filter(OpenPosition.symbol_id == sym.id, OpenPosition.status == 'OPEN')
                    .first()
                )
                if pos:
                    # Fetch current price for PnL
                    px = get_current_price(sym.symbol, auth)
                    exit_price = float(px.get('price', 0)) if isinstance(px, dict) else 0
                    pos.status = 'CLOSED'
                    pos.exit_time = datetime.utcnow()
                    pos.exit_price = exit_price
                    if pos.avg_entry_price is not None and pos.quantity:
                        if pos.side == 'BUY':
                            pos.pnl = (exit_price - float(pos.avg_entry_price)) * pos.quantity
                        else:
                            pos.pnl = (float(pos.avg_entry_price) - exit_price) * pos.quantity
                sig.executed = True
                placed += 1
                continue

            # For BUY/SELL, place a small market order
            side = 'buy' if sig.signal_type == 'BUY' else 'sell'
            payload = {
                'symbol': sym.symbol,
                'quantity': '1',
                'action': side.upper(),
                'pricetype': 'MARKET',
                'product': 'CNC',
                'exchange': sym.exchange
            }
            resp = place_order_api(payload, auth)
            if isinstance(resp, dict) and resp.get('id'):
                # Lock symbol
                price = get_current_price(sym.symbol, auth)
                entry_price = float(price.get('price', 0)) if isinstance(price, dict) else None
                db_session.add(OpenPosition(
                    symbol_id=sym.id,
                    side='BUY' if side == 'buy' else 'SELL',
                    quantity=1,
                    avg_entry_price=entry_price,
                ))
                sig.executed = True
                placed += 1

        db_session.commit()
        return {"status": "ok", "placed": placed}
    except Exception as e:
        db_session.rollback()
        logger.error(f"Execution engine failed: {e}")
        return {"status": "error", "message": str(e)}
