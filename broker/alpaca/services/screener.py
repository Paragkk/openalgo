from datetime import date
from utils.logging import get_logger
from broker.alpaca.models.ats_schema import get_session, DailyWatchlist
from database.symbol import SymToken as Symbols

logger = get_logger(__name__)

# Simple screener: pick top N symbols by alphabetical (placeholder) or sector filter

def run_simple_screener(limit: int = 20, sector: str | None = None) -> int:
    """Populate today's daily_watchlist with a simple ranking.

    Strategy: 
    - Filter symbols by sector if provided
    - Rank by symbol ascending as a placeholder
    - Insert if not already present for today
    Returns count inserted.
    """
    sess = get_session()
    today = date.today()
    try:
        q = sess.query(Symbols)
        if sector:
            # sector not present in symtoken; placeholder for future enrichment
            pass
        q = q.order_by(Symbols.symbol.asc()).limit(limit)
        symbols = q.all()

        inserted = 0
        rank = 1
        for s in symbols:
            exists = sess.query(DailyWatchlist.id).filter(
                DailyWatchlist.date == today,
                DailyWatchlist.symbol_id == s.id
            ).first()
            if exists:
                continue
            dw = DailyWatchlist(
                date=today,
                symbol_id=s.id,
                rank=rank,
                reason='simple_alpha',
                status='ACTIVE'
            )
            sess.add(dw)
            inserted += 1
            rank += 1
        sess.commit()
        logger.info(f'Screener inserted {inserted} symbols for {today}')
        return inserted
    except Exception as e:
        sess.rollback()
        logger.error(f'Screener failed: {e}')
        return 0
    finally:
        sess.close()
