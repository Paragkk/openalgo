from enum import Enum
from typing import Dict, Any, Optional, List
from utils.logging import get_logger
import importlib.util
import sys
import os
import pandas as pd
import threading
import time
from datetime import datetime

logger = get_logger(__name__)

class StrategyType(Enum):
    EMA_CROSSOVER = "ema_crossover"
    SUPER_TREND = "supertrend"
    SMA_CROSSOVER = "sma_crossover"
    MEAN_REVERSION = "mean_reversion"
    CONTINUOUS_TRADING = "continuous_trading"
    # Dynamic strategies loaded from files
    DYNAMIC = "dynamic"

class StrategyConfig:
    def __init__(self, strategy_type: StrategyType, parameters: Dict[str, Any], strategy_file: Optional[str] = None):
        self.strategy_type = strategy_type
        self.parameters = parameters
        self.strategy_file = strategy_file

    @classmethod
    def get_default_config(cls, strategy_type: StrategyType, strategy_file: Optional[str] = None) -> 'StrategyConfig':
        """Get default configuration for a strategy type."""
        defaults = {
            StrategyType.EMA_CROSSOVER: {
                'fast_period': 5,
                'slow_period': 20,
                'risk_per_trade': 0.02,
                'max_positions': 5
            },
            StrategyType.SUPER_TREND: {
                'atr_period': 10,
                'atr_multiplier': 3.0,
                'risk_per_trade': 0.02,
                'max_positions': 3
            },
            StrategyType.SMA_CROSSOVER: {
                'fast_period': 5,
                'slow_period': 20,
                'risk_per_trade': 0.02,
                'max_positions': 5
            },
            StrategyType.MEAN_REVERSION: {
                'lookback_period': 20,
                'entry_threshold': 2.0,
                'exit_threshold': 0.5,
                'risk_per_trade': 0.01,
                'max_positions': 10
            },
            StrategyType.CONTINUOUS_TRADING: {
                'data_collection_interval': 60,  # seconds
                'signal_check_interval': 30,     # seconds
                'max_positions': 1,              # Only one position at a time
                'risk_per_trade': 0.02,
                'fast_period': 5,
                'slow_period': 20,
                'min_volume': 100000,            # Minimum volume filter
                'max_spread': 0.05               # Maximum spread filter
            }
        }

        # For dynamic strategies, try to extract parameters from the file
        if strategy_type == StrategyType.DYNAMIC and strategy_file:
            file_params = cls._extract_parameters_from_file(strategy_file)
            if file_params:
                defaults[StrategyType.DYNAMIC] = file_params

        return cls(strategy_type, defaults.get(strategy_type, {}), strategy_file)

    @staticmethod
    def _extract_parameters_from_file(file_path: str) -> Optional[Dict[str, Any]]:
        """Extract strategy parameters from a Python file."""
        try:
            # Try UTF-8 first, then fallback to other encodings
            content = None
            encodings_to_try = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']

            for encoding in encodings_to_try:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                logger.warning(f"Could not decode file {file_path} with any supported encoding")
                return None

            params = {}

            # Extract common parameter patterns
            import re

            # Look for variable assignments
            patterns = {
                'fast_period': r'fast_period\s*=\s*(\d+)',
                'slow_period': r'slow_period\s*=\s*(\d+)',
                'atr_period': r'atr_period\s*=\s*(\d+)',
                'atr_multiplier': r'atr_multiplier\s*=\s*([\d.]+)',
                'quantity': r'quantity\s*=\s*(\d+)',
                'symbol': r'symbol\s*=\s*[\'"]([^\'"]+)[\'"]',
                'exchange': r'exchange\s*=\s*[\'"]([^\'"]+)[\'"]',
                'product': r'product\s*=\s*[\'"]([^\'"]+)[\'"]'
            }

            for param_name, pattern in patterns.items():
                match = re.search(pattern, content)
                if match:
                    value = match.group(1)
                    # Convert to appropriate type
                    if '.' in value:
                        params[param_name] = float(value)
                    elif value.isdigit():
                        params[param_name] = int(value)
                    else:
                        params[param_name] = value

            # Set defaults for missing parameters
            params.setdefault('risk_per_trade', 0.02)
            params.setdefault('max_positions', 5)

            return params
        except Exception as e:
            logger.error(f"Error extracting parameters from {file_path}: {e}")
            return None

class TradingStrategy:
    """Base class for trading strategies."""

    def __init__(self, config: StrategyConfig):
        self.config = config
        self.logger = get_logger(f"{self.__class__.__name__}")

    def generate_signals(self, symbol_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate trading signals based on strategy logic."""
        raise NotImplementedError

    def should_exit(self, position_data: Dict[str, Any]) -> bool:
        """Determine if a position should be exited."""
        raise NotImplementedError

class DynamicStrategy(TradingStrategy):
    """Dynamic strategy that loads and uses existing strategy files."""

    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.strategy_module = None
        self.signal_function = None
        self._load_strategy()

    def _load_strategy(self):
        """Load the strategy module dynamically."""
        if not self.config.strategy_file:
            raise ValueError("Strategy file path is required for dynamic strategies")

        try:
            # Add the strategies directory to Python path
            strategies_dir = os.path.dirname(self.config.strategy_file)
            if strategies_dir not in sys.path:
                sys.path.insert(0, strategies_dir)

            # Load the module
            module_name = os.path.splitext(os.path.basename(self.config.strategy_file))[0]
            spec = importlib.util.spec_from_file_location(module_name, self.config.strategy_file)
            self.strategy_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.strategy_module)

            # Find signal generation function
            signal_functions = ['calculate_ema_signals', 'Supertrend', 'calculate_signals']
            for func_name in signal_functions:
                if hasattr(self.strategy_module, func_name):
                    self.signal_function = getattr(self.strategy_module, func_name)
                    break

            if not self.signal_function:
                raise ValueError(f"No signal generation function found in {self.config.strategy_file}")

            logger.info(f"Successfully loaded strategy from {self.config.strategy_file}")

        except Exception as e:
            logger.error(f"Error loading strategy from {self.config.strategy_file}: {e}")
            raise

    def generate_signals(self, symbol_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate signals using the loaded strategy."""
        try:
            if not self.signal_function:
                return None

            # Convert symbol data to DataFrame format expected by strategies
            prices = symbol_data.get('prices', [])
            if not prices:
                return None

            # Create DataFrame from price data
            df = pd.DataFrame({
                'close': [p.get('close', p.get('price', 0)) for p in prices],
                'high': [p.get('high', p.get('close', 0)) for p in prices],
                'low': [p.get('low', p.get('close', 0)) for p in prices],
                'open': [p.get('open', p.get('close', 0)) for p in prices],
                'volume': [p.get('volume', 0) for p in prices]
            })

            # Call the strategy's signal function
            if 'ema' in self.config.strategy_file.lower():
                # EMA crossover strategy
                result = self.signal_function(df)
                if hasattr(result, 'any') and result.any():
                    latest_signal = result.iloc[-1]
                    if latest_signal:
                        return {
                            'signal': 'BUY',
                            'confidence': 0.8,
                            'reason': 'EMA crossover signal from loaded strategy'
                        }
            elif 'supertrend' in self.config.strategy_file.lower():
                # SuperTrend strategy
                result = self.signal_function(df,
                    self.config.parameters.get('atr_period', 5),
                    self.config.parameters.get('atr_multiplier', 1.0))
                # Parse SuperTrend result
                if isinstance(result, pd.Series) and len(result) > 0:
                    latest_value = result.iloc[-1]
                    if latest_value < df['close'].iloc[-1]:  # Price above SuperTrend
                        return {
                            'signal': 'BUY',
                            'confidence': 0.8,
                            'reason': 'SuperTrend signal from loaded strategy'
                        }
                    else:  # Price below SuperTrend
                        return {
                            'signal': 'SELL',
                            'confidence': 0.8,
                            'reason': 'SuperTrend signal from loaded strategy'
                        }

            return None
        except Exception as e:
            logger.error(f"Error generating signals with dynamic strategy: {e}")
            return None

    def should_exit(self, position_data: Dict[str, Any]) -> bool:
        """Check exit conditions using the loaded strategy."""
        # For now, use simple time-based or basic logic
        # This could be enhanced to use the strategy's exit logic
        return False

class EMACrossoverStrategy(TradingStrategy):
    """EMA Crossover Strategy Implementation."""

    def generate_signals(self, symbol_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate signals based on EMA crossover."""
        try:
            prices = symbol_data.get('prices', [])
            if len(prices) < self.config.parameters['slow_period']:
                return None

            # Calculate EMAs
            fast_period = self.config.parameters['fast_period']
            slow_period = self.config.parameters['slow_period']

            fast_ema = self._calculate_ema(prices, fast_period)
            slow_ema = self._calculate_ema(prices, slow_period)

            if len(fast_ema) < 2 or len(slow_ema) < 2:
                return None

            # Check for crossover
            prev_fast, curr_fast = fast_ema[-2], fast_ema[-1]
            prev_slow, curr_slow = slow_ema[-2], slow_ema[-1]

            if prev_fast <= prev_slow and curr_fast > curr_slow:
                return {
                    'signal': 'BUY',
                    'confidence': 0.8,
                    'reason': f'EMA {fast_period} crossed above EMA {slow_period}'
                }
            elif prev_fast >= prev_slow and curr_fast < curr_slow:
                return {
                    'signal': 'SELL',
                    'confidence': 0.8,
                    'reason': f'EMA {fast_period} crossed below EMA {slow_period}'
                }

            return None
        except Exception as e:
            self.logger.error(f"Error generating EMA crossover signals: {e}")
            return None

    def should_exit(self, position_data: Dict[str, Any]) -> bool:
        """Check if position should be exited based on EMA crossover."""
        try:
            prices = position_data.get('prices', [])
            if len(prices) < self.config.parameters['slow_period']:
                return False

            fast_period = self.config.parameters['fast_period']
            slow_period = self.config.parameters['slow_period']

            fast_ema = self._calculate_ema(prices, fast_period)
            slow_ema = self._calculate_ema(prices, slow_period)

            if len(fast_ema) < 2 or len(slow_ema) < 2:
                return False

            # Exit if EMAs cross in opposite direction
            prev_fast, curr_fast = fast_ema[-2], fast_ema[-1]
            prev_slow, curr_slow = slow_ema[-2], slow_ema[-1]

            side = position_data.get('side', 'LONG')
            if side == 'LONG' and prev_fast >= prev_slow and curr_fast < curr_slow:
                return True
            elif side == 'SHORT' and prev_fast <= prev_slow and curr_fast > curr_slow:
                return True

            return False
        except Exception as e:
            self.logger.error(f"Error checking exit condition: {e}")
            return False

    def _calculate_ema(self, prices: list, period: int) -> list:
        """Calculate Exponential Moving Average."""
        if len(prices) < period:
            return []

        ema = []
        multiplier = 2 / (period + 1)

        # First EMA is SMA
        sma = sum(prices[:period]) / period
        ema.append(sma)

        # Calculate subsequent EMAs
        for i in range(period, len(prices)):
            ema_val = (prices[i] - ema[-1]) * multiplier + ema[-1]
            ema.append(ema_val)

        return ema

class ContinuousTradingStrategy(TradingStrategy):
    """Continuous Trading Strategy with position management."""

    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.current_position = None  # Track current position
        self.entry_price = None
        self.position_side = None

    def generate_signals(self, symbol_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Generate signals based on EMA crossover with position management."""
        try:
            # If we have an open position, don't generate new entry signals
            if self.current_position is not None:
                return None

            prices = symbol_data.get('prices', [])
            volumes = symbol_data.get('volumes', [])

            if len(prices) < self.config.parameters['slow_period']:
                return None

            # Apply filters
            if not self._passes_filters(symbol_data):
                return None

            # Calculate EMAs
            fast_period = self.config.parameters['fast_period']
            slow_period = self.config.parameters['slow_period']

            fast_ema = self._calculate_ema(prices, fast_period)
            slow_ema = self._calculate_ema(prices, slow_period)

            if len(fast_ema) < 2 or len(slow_ema) < 2:
                return None

            # Check for crossover
            prev_fast, curr_fast = fast_ema[-2], fast_ema[-1]
            prev_slow, curr_slow = slow_ema[-2], slow_ema[-1]

            if prev_fast <= prev_slow and curr_fast > curr_slow:
                return {
                    'signal': 'BUY',
                    'confidence': 0.8,
                    'reason': f'EMA {fast_period} crossed above EMA {slow_period}',
                    'symbol': symbol_data.get('symbol')
                }
            elif prev_fast >= prev_slow and curr_fast < curr_slow:
                return {
                    'signal': 'SELL',
                    'confidence': 0.8,
                    'reason': f'EMA {fast_period} crossed below EMA {slow_period}',
                    'symbol': symbol_data.get('symbol')
                }

            return None
        except Exception as e:
            self.logger.error(f"Error generating continuous trading signals: {e}")
            return None

    def should_exit(self, position_data: Dict[str, Any]) -> bool:
        """Check if position should be exited based on opposite signal."""
        try:
            prices = position_data.get('prices', [])
            if len(prices) < self.config.parameters['slow_period']:
                return False

            fast_period = self.config.parameters['fast_period']
            slow_period = self.config.parameters['slow_period']

            fast_ema = self._calculate_ema(prices, fast_period)
            slow_ema = self._calculate_ema(prices, slow_period)

            if len(fast_ema) < 2 or len(slow_ema) < 2:
                return False

            # Exit if EMAs cross in opposite direction
            prev_fast, curr_fast = fast_ema[-2], fast_ema[-1]
            prev_slow, curr_slow = slow_ema[-2], slow_ema[-1]

            side = position_data.get('side', 'LONG')
            if side == 'LONG' and prev_fast >= prev_slow and curr_fast < curr_slow:
                return True
            elif side == 'SHORT' and prev_fast <= prev_slow and curr_fast > curr_slow:
                return True

            return False
        except Exception as e:
            self.logger.error(f"Error checking exit condition: {e}")
            return False

    def _passes_filters(self, symbol_data: Dict[str, Any]) -> bool:
        """Apply filters to determine if symbol should be traded."""
        try:
            volumes = symbol_data.get('volumes', [])
            prices = symbol_data.get('prices', [])

            if not volumes or not prices:
                return False

            # Volume filter
            min_volume = self.config.parameters.get('min_volume', 100000)
            recent_volumes = volumes[-20:] if len(volumes) >= 20 else volumes
            if recent_volumes:
                avg_volume = sum(recent_volumes) / len(recent_volumes)
                if avg_volume < min_volume:
                    return False

            # Spread filter (if available)
            max_spread = self.config.parameters.get('max_spread', 0.05)
            if len(prices) >= 2:
                spread = abs(prices[-1] - prices[-2]) / prices[-2]
                if spread > max_spread:
                    return False

            return True
        except Exception as e:
            self.logger.error(f"Error applying filters: {e}")
            return False

    def update_position(self, position_data: Dict[str, Any]):
        """Update current position information."""
        self.current_position = position_data.get('symbol')
        self.entry_price = position_data.get('entry_price')
        self.position_side = position_data.get('side')

    def clear_position(self):
        """Clear current position information."""
        self.current_position = None
        self.entry_price = None
        self.position_side = None

    def has_open_position(self) -> bool:
        """Check if there's an open position."""
        return self.current_position is not None

class StrategyFactory:
    """Factory for creating trading strategies."""

    @staticmethod
    def create_strategy(strategy_type: StrategyType, config: Optional[StrategyConfig] = None, strategy_file: Optional[str] = None) -> TradingStrategy:
        """Create a strategy instance."""
        if config is None:
            config = StrategyConfig.get_default_config(strategy_type, strategy_file)

        if strategy_type == StrategyType.EMA_CROSSOVER:
            return EMACrossoverStrategy(config)
        elif strategy_type == StrategyType.CONTINUOUS_TRADING:
            return ContinuousTradingStrategy(config)
        elif strategy_type == StrategyType.SUPER_TREND:
            # Would implement SuperTrend strategy
            raise NotImplementedError("SuperTrend strategy not implemented yet")
        elif strategy_type == StrategyType.SMA_CROSSOVER:
            # Would implement SMA crossover strategy
            raise NotImplementedError("SMA Crossover strategy not implemented yet")
        elif strategy_type == StrategyType.MEAN_REVERSION:
            # Would implement Mean Reversion strategy
            raise NotImplementedError("Mean Reversion strategy not implemented yet")
        elif strategy_type == StrategyType.DYNAMIC:
            if strategy_file:
                config.strategy_file = strategy_file
                return DynamicStrategy(config)
            else:
                raise ValueError("Strategy file is required for dynamic strategies")
        else:
            raise ValueError(f"Unknown strategy type: {strategy_type}")

class StrategyLoader:
    """Loader for discovering and loading strategies from the strategies folder."""

    @staticmethod
    def discover_strategies(strategies_dir: str = None) -> List[Dict[str, Any]]:
        """Discover available strategies from the strategies directory."""
        if strategies_dir is None:
            # Default to the strategies folder in the project root
            strategies_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'strategies')

        strategies = []

        if not os.path.exists(strategies_dir):
            logger.warning(f"Strategies directory not found: {strategies_dir}")
            return strategies

        # Built-in strategies
        built_in_strategies = [
            {
                'id': 'ema_crossover',
                'name': 'EMA Crossover',
                'description': 'Exponential Moving Average crossover strategy',
                'type': 'built_in',
                'file': None
            },
            {
                'id': 'supertrend',
                'name': 'SuperTrend',
                'description': 'SuperTrend trend following strategy',
                'type': 'built_in',
                'file': None
            },
            {
                'id': 'continuous_trading',
                'name': 'Continuous Trading',
                'description': 'Continuous automated trading with position management',
                'type': 'built_in',
                'file': None
            }
        ]
        strategies.extend(built_in_strategies)

        # Discover Python strategy files
        for filename in os.listdir(strategies_dir):
            if filename.endswith('.py') and not filename.startswith('__'):
                file_path = os.path.join(strategies_dir, filename)
                strategy_info = StrategyLoader._analyze_strategy_file(file_path, filename)
                if strategy_info:
                    strategies.append(strategy_info)

        return strategies

    @staticmethod
    def _analyze_strategy_file(file_path: str, filename: str) -> Optional[Dict[str, Any]]:
        """Analyze a strategy file to extract metadata."""
        try:
            # Try UTF-8 first, then fallback to other encodings
            content = None
            encodings_to_try = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']

            for encoding in encodings_to_try:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                logger.warning(f"Could not decode file {file_path} with any supported encoding")
                return None

            # Extract strategy name and description
            name = filename.replace('.py', '').replace('_', ' ').title()
            description = "Custom trading strategy"

            # Try to extract more info from comments/docstrings
            lines = content.split('\n')
            for line in lines[:20]:  # Check first 20 lines
                line = line.strip()
                if line.startswith('"""') or line.startswith("'''"):
                    # Found docstring
                    description = line.replace('"""', '').replace("'''", '').strip()
                    break
                elif line.startswith('#') and 'strategy' in line.lower():
                    description = line.replace('#', '').strip()
                    break

            # Extract parameters
            params = StrategyConfig._extract_parameters_from_file(file_path)

            return {
                'id': f"dynamic_{filename.replace('.py', '')}",
                'name': name,
                'description': description,
                'type': 'dynamic',
                'file': file_path,
                'parameters': params or {}
            }
        except Exception as e:
            logger.error(f"Error analyzing strategy file {file_path}: {e}")
            return None

class AutoTradingSystem:
    """Main auto trading system that orchestrates the entire workflow."""

    def __init__(self, strategy_type: StrategyType = StrategyType.EMA_CROSSOVER):
        self.strategy_config = StrategyConfig.get_default_config(strategy_type)
        self.strategy = StrategyFactory.create_strategy(strategy_type, self.strategy_config)
        self.logger = get_logger(__name__)
        self.is_running = False
        self.trading_thread = None
        self.data_thread = None
        self.should_stop = False

    def start_automated_trading(self) -> Dict[str, Any]:
        """Start the automated trading system."""
        try:
            if self.is_running:
                return {'status': 'error', 'message': 'Trading system is already running'}

            self.is_running = True
            self.should_stop = False
            self.logger.info(f"Starting automated trading with strategy: {self.strategy.__class__.__name__}")

            # Step 1: Run initial screener to populate watchlist
            screener_result = self._run_screener()
            self.logger.info(f"Screener completed: {screener_result}")

            # Step 2: Collect initial historical data
            data_result = self._collect_market_data()
            self.logger.info(f"Initial data collection completed: {data_result}")

            # Step 3: Start continuous data collection thread
            data_interval = self.strategy_config.parameters.get('data_collection_interval', 60)
            self.data_thread = threading.Thread(target=self._continuous_data_collection, args=(data_interval,))
            self.data_thread.daemon = True
            self.data_thread.start()

            # Step 4: Start continuous trading thread
            signal_interval = self.strategy_config.parameters.get('signal_check_interval', 30)
            self.trading_thread = threading.Thread(target=self._continuous_trading, args=(signal_interval,))
            self.trading_thread.daemon = True
            self.trading_thread.start()

            return {
                'status': 'success',
                'message': 'Automated trading system started successfully',
                'config': {
                    'data_collection_interval': data_interval,
                    'signal_check_interval': signal_interval,
                    'strategy': self.strategy.__class__.__name__
                }
            }
        except Exception as e:
            self.logger.error(f"Failed to start automated trading: {e}")
            self.is_running = False
            return {
                'status': 'error',
                'message': str(e)
            }

    def stop_automated_trading(self) -> Dict[str, Any]:
        """Stop the automated trading system."""
        try:
            self.should_stop = True
            self.is_running = False

            # Wait for threads to finish
            if self.trading_thread and self.trading_thread.is_alive():
                self.trading_thread.join(timeout=5)
            if self.data_thread and self.data_thread.is_alive():
                self.data_thread.join(timeout=5)

            # Clear position if using continuous trading strategy
            if hasattr(self.strategy, 'clear_position'):
                self.strategy.clear_position()

            self.logger.info("Automated trading system stopped successfully")
            return {
                'status': 'success',
                'message': 'Automated trading system stopped successfully'
            }
        except Exception as e:
            self.logger.error(f"Error stopping automated trading: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def _continuous_data_collection(self, interval: int):
        """Continuously collect market data at specified intervals."""
        self.logger.info(f"Starting continuous data collection every {interval} seconds")

        while not self.should_stop and self.is_running:
            try:
                # Collect incremental data for watchlist symbols
                result = self._collect_market_data()
                count = result.get('data_points_collected', 0)
                self.logger.debug(f"Collected data for {count} symbols")

                # Sleep for the specified interval
                time.sleep(interval)

            except Exception as e:
                self.logger.error(f"Error in continuous data collection: {e}")
                time.sleep(5)  # Brief pause before retrying

    def _continuous_trading(self, interval: int):
        """Continuously check for signals and execute trades."""
        self.logger.info(f"Starting continuous trading every {interval} seconds")

        while not self.should_stop and self.is_running:
            try:
                # Check for exit signals first if we have a position
                if hasattr(self.strategy, 'has_open_position') and self.strategy.has_open_position():
                    self._check_exit_signals()
                else:
                    # Generate new entry signals
                    signals_result = self._generate_signals()
                    if signals_result.get('signals_created', 0) > 0:
                        self.logger.info(f"Generated {signals_result['signals_created']} signals")

                    # Execute any pending signals
                    execution_result = self._execute_signals()
                    if execution_result.get('orders_executed', 0) > 0:
                        self.logger.info(f"Executed {execution_result['orders_executed']} orders")

                # Sleep for the specified interval
                time.sleep(interval)

            except Exception as e:
                self.logger.error(f"Error in continuous trading: {e}")
                time.sleep(5)  # Brief pause before retrying

    def _check_exit_signals(self):
        """Check for exit signals on open positions."""
        try:
            # This would need to be implemented based on how positions are tracked
            # For now, we'll use the strategy's should_exit method
            if hasattr(self.strategy, 'should_exit'):
                # Get current position data and check exit conditions
                # This is a placeholder - actual implementation would depend on position tracking
                pass
        except Exception as e:
            self.logger.error(f"Error checking exit signals: {e}")

    def _run_screener(self) -> Dict[str, Any]:
        """Run the screener to populate daily watchlist."""
        from broker.alpaca.services.screener import run_simple_screener
        inserted = run_simple_screener(limit=20)
        return {'symbols_added': inserted}

    def _collect_market_data(self) -> Dict[str, Any]:
        """Collect market data for watchlist symbols."""
        from broker.alpaca.services.data_collector import collect_incremental
        # Collect data for all watchlist symbols
        count = collect_incremental(symbols=[], timeframe='1m')  # Empty list means all watchlist
        return {'data_points_collected': count}

    def _generate_signals(self) -> Dict[str, Any]:
        """Generate trading signals using the selected strategy."""
        from broker.alpaca.services.signal_engine import generate_signals
        created = generate_signals()
        return {'signals_created': created}

    def _execute_signals(self) -> Dict[str, Any]:
        """Execute pending trading signals."""
        from broker.alpaca.services.execution_engine import process_trade_signals
        executed = process_trade_signals()
        return {'orders_executed': executed}

    def get_status(self) -> Dict[str, Any]:
        """Get the current status of the automated trading system."""
        # Map class names to user-friendly names
        strategy_name_map = {
            'EMACrossoverStrategy': 'EMA Crossover',
            'SuperTrendStrategy': 'SuperTrend',
            'ContinuousTradingStrategy': 'Continuous Trading',
            'SMACrossoverStrategy': 'SMA Crossover',
            'MeanReversionStrategy': 'Mean Reversion'
        }
        
        class_name = self.strategy.__class__.__name__
        display_name = strategy_name_map.get(class_name, class_name)
        
        return {
            'is_running': self.is_running,
            'strategy': display_name,
            'config': self.strategy_config.parameters
        }
