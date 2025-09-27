from flask import Blueprint, jsonify, request
from utils.session import check_session_validity
from utils.logging import get_logger
from broker.alpaca.models.ats_schema import init_db
from broker.alpaca.services.screener import run_simple_screener
from broker.alpaca.services.data_collector import backfill_historical, collect_incremental
from broker.alpaca.services.signal_engine import generate_signals
from broker.alpaca.services.execution_engine import process_trade_signals
from broker.alpaca.strategies.strategy_manager import (
    AutoTradingSystem, StrategyType, StrategyConfig, StrategyFactory, StrategyLoader
)

logger = get_logger(__name__)

alpaca_ats_bp = Blueprint('alpaca_ats_bp', __name__, url_prefix='/alpaca/ats')

# Global ATS instance
ats_system = None


@alpaca_ats_bp.route('/init-db', methods=['POST'])
@check_session_validity
def init_ats_db():
    init_db()
    return jsonify({'status': 'ok'})


@alpaca_ats_bp.route('/run-screener', methods=['POST'])
@check_session_validity
def run_screener():
    # Initialize database tables if they don't exist
    init_db()
    
    body = request.get_json(silent=True) or {}
    limit = int(body.get('limit', 20))
    sector = body.get('sector')
    inserted = run_simple_screener(limit=limit, sector=sector)
    
    # Get total watchlist count for better feedback
    from datetime import date
    from broker.alpaca.models.ats_schema import get_session, DailyWatchlist
    sess = get_session()
    today = date.today()
    total_watchlist = sess.query(DailyWatchlist).filter(DailyWatchlist.date == today).count()
    sess.close()
    
    return jsonify({
        'inserted': inserted,
        'total_watchlist': total_watchlist,
        'message': f'Screener completed. {inserted} new symbols added, {total_watchlist} total in watchlist.'
    })


@alpaca_ats_bp.route('/backfill', methods=['POST'])
@check_session_validity
def backfill():
    body = request.get_json(silent=True) or {}
    symbol = body.get('symbol')
    if not symbol:
        return jsonify({'error': 'symbol required'}), 400
    days = int(body.get('days', 30))
    timeframe = body.get('timeframe', '1d')
    count = backfill_historical(symbol, days=days, timeframe=timeframe)
    return jsonify({'inserted': count})


@alpaca_ats_bp.route('/collect', methods=['POST'])
@check_session_validity
def collect():
    body = request.get_json(silent=True) or {}
    symbols = body.get('symbols') or []
    timeframe = body.get('timeframe', '1m')
    count = collect_incremental(symbols, timeframe=timeframe)
    return jsonify({'inserted': count})


@alpaca_ats_bp.route('/signals', methods=['POST'])
@check_session_validity
def signals():
    created = generate_signals()
    return jsonify({'created': created})


@alpaca_ats_bp.route('/execute', methods=['POST'])
@check_session_validity
def execute():
    executed = process_trade_signals()
    return jsonify({'executed': executed})


@alpaca_ats_bp.route('/strategies', methods=['GET'])
@check_session_validity
def get_strategies():
    """Get available trading strategies."""
    try:
        strategies = StrategyLoader.discover_strategies()
        return jsonify({'strategies': strategies})
    except Exception as e:
        logger.error(f'Error discovering strategies: {e}')
        return jsonify({'error': 'Failed to discover strategies'}), 500


@alpaca_ats_bp.route('/strategy/select', methods=['POST'])
@check_session_validity
def select_strategy():
    """Select and configure a trading strategy."""
    global ats_system

    body = request.get_json(silent=True) or {}
    strategy_id = body.get('strategy_id')
    strategy_file = body.get('strategy_file')

    if not strategy_id:
        return jsonify({'error': 'strategy_id is required'}), 400

    try:
        # Handle dynamic strategies
        if strategy_id.startswith('dynamic_'):
            if not strategy_file:
                return jsonify({'error': 'strategy_file is required for dynamic strategies'}), 400
            strategy_type = StrategyType.DYNAMIC
            config = StrategyConfig.get_default_config(strategy_type, strategy_file)
            ats_system = AutoTradingSystem(strategy_type)
            # Override the strategy with dynamic one
            ats_system.strategy = StrategyFactory.create_strategy(strategy_type, config, strategy_file)
        else:
            strategy_type = StrategyType(strategy_id)
            ats_system = AutoTradingSystem(strategy_type)

        return jsonify({
            'status': 'success',
            'message': f'Strategy {strategy_id} selected successfully',
            'config': ats_system.get_status()
        })
    except ValueError:
        return jsonify({'error': f'Invalid strategy_id: {strategy_id}'}), 400
    except Exception as e:
        logger.error(f'Error selecting strategy: {e}')
        return jsonify({'error': 'Failed to select strategy'}), 500


@alpaca_ats_bp.route('/auto-trade/start', methods=['POST'])
@check_session_validity
def start_auto_trading():
    """Start the automated trading system."""
    global ats_system

    if ats_system is None:
        return jsonify({'error': 'No strategy selected. Please select a strategy first.'}), 400

    if ats_system.is_running:
        return jsonify({'error': 'Automated trading is already running'}), 400

    try:
        result = ats_system.start_automated_trading()
        return jsonify(result)
    except Exception as e:
        logger.error(f'Error starting auto trading: {e}')
        return jsonify({'error': 'Failed to start automated trading'}), 500


@alpaca_ats_bp.route('/auto-trade/stop', methods=['POST'])
@check_session_validity
def stop_auto_trading():
    """Stop the automated trading system."""
    global ats_system

    if ats_system is None:
        return jsonify({'error': 'No automated trading system initialized'}), 400

    if not ats_system.is_running:
        return jsonify({'error': 'Automated trading is not running'}), 400

    try:
        result = ats_system.stop_automated_trading()
        return jsonify(result)
    except Exception as e:
        logger.error(f'Error stopping auto trading: {e}')
        return jsonify({'error': 'Failed to stop automated trading'}), 500


@alpaca_ats_bp.route('/auto-trade/status', methods=['GET'])
@check_session_validity
def get_auto_trading_status():
    """Get the status of the automated trading system."""
    global ats_system

    if ats_system is None:
        return jsonify({
            'initialized': False,
            'running': False,
            'message': 'No strategy selected'
        })

    status = ats_system.get_status()
    return jsonify({
        'initialized': True,
        'running': status['is_running'],
        'strategy': status['strategy'],
        'config': status['config']
    })


@alpaca_ats_bp.route('/auto-trade/run-cycle', methods=['POST'])
@check_session_validity
def run_trading_cycle():
    """Run a single cycle of the automated trading system."""
    global ats_system

    if ats_system is None:
        return jsonify({'error': 'No strategy selected. Please select a strategy first.'}), 400

    try:
        # Step 1: Generate signals
        signals_result = ats_system._generate_signals()

        # Step 2: Execute signals
        execution_result = ats_system._execute_signals()

        return jsonify({
            'status': 'success',
            'message': 'Trading cycle completed',
            'results': {
                'signals_generated': signals_result['signals_created'],
                'orders_executed': execution_result['orders_executed']
            }
        })
    except Exception as e:
        logger.error(f'Error running trading cycle: {e}')
        return jsonify({'error': 'Failed to run trading cycle'}), 500
