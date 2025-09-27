import yfinance as yf
import pandas as pd
from utils.logging import get_logger

logger = get_logger(__name__)

class YahooFinanceProvider:
    """Yahoo Finance data provider as fallback for Alpaca market data"""

    def __init__(self):
        self.max_retries = 3
        self.timeout = 30

    def get_historical_data(self, symbol: str, exchange: str, timeframe: str,
                          start_date: str, end_date: str) -> dict:
        """
        Get historical data from Yahoo Finance

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            exchange: Exchange (ignored for Yahoo Finance)
            timeframe: Timeframe (1m, 5m, 15m, 1h, 1d, 1w, 1M)
            start_date: Start date in YYYY-MM-DD format or ISO format
            end_date: End date in YYYY-MM-DD format or ISO format

        Returns:
            dict: Alpaca-compatible response format
        """
        try:
            # Clean date formats for Yahoo Finance
            start_date_clean = start_date.split('T')[0] if 'T' in start_date else start_date
            end_date_clean = end_date.split('T')[0] if 'T' in end_date else end_date
            
            # Map timeframe to Yahoo Finance interval
            interval = self._map_timeframe(timeframe)

            # Create ticker object
            ticker = yf.Ticker(symbol)

            # Download data
            data = ticker.history(
                start=start_date_clean,
                end=end_date_clean,
                interval=interval,
                timeout=self.timeout
            )

            if data.empty:
                logger.warning(f"No data found for {symbol} from Yahoo Finance")
                return {
                    'bars': {},
                    'error': f'No data available for {symbol}'
                }

            # Convert to Alpaca-compatible format
            bars = self._convert_to_alpaca_format(data, symbol)

            return {
                'bars': {symbol: bars},
                'symbol': symbol,
                'timeframe': timeframe
            }

        except Exception as e:
            logger.error(f"Yahoo Finance error for {symbol}: {str(e)}")
            return {
                'bars': {},
                'error': f'Yahoo Finance error: {str(e)}'
            }

    def _map_timeframe(self, timeframe: str) -> str:
        """Map OpenAlgo timeframe to Yahoo Finance interval"""
        mapping = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '30m': '30m',
            '1h': '1h',
            '1d': '1d',
            '1w': '1wk',
            '1M': '1mo'
        }
        return mapping.get(timeframe.lower(), '1d')

    def _convert_to_alpaca_format(self, df: pd.DataFrame, symbol: str) -> list:
        """Convert Yahoo Finance DataFrame to Alpaca bars format"""
        bars = []

        for index, row in df.iterrows():
            # Convert timestamp to ISO format
            timestamp = index.isoformat()

            bar = {
                't': timestamp,  # timestamp
                'o': round(float(row['Open']), 2),  # open
                'h': round(float(row['High']), 2),  # high
                'l': round(float(row['Low']), 2),   # low
                'c': round(float(row['Close']), 2), # close
                'v': int(row['Volume']) if not pd.isna(row['Volume']) else 0  # volume
            }
            bars.append(bar)

        return bars

    def get_quotes(self, symbols: list) -> dict:
        """Get real-time quotes from Yahoo Finance"""
        try:
            if isinstance(symbols, str):
                symbols = [symbols]

            quotes = {}
            for symbol in symbols:
                ticker = yf.Ticker(symbol)
                data = ticker.history(period="1d", interval="1m")

                if not data.empty:
                    latest = data.iloc[-1]
                    quotes[symbol] = {
                        'bid_price': round(float(latest['Close']), 2),
                        'ask_price': round(float(latest['Close']), 2),
                        'bid_size': 100,  # Default values
                        'ask_size': 100,
                        'timestamp': latest.name.isoformat()
                    }

            return {'quotes': quotes}

        except Exception as e:
            logger.error(f"Yahoo Finance quotes error: {str(e)}")
            return {'error': str(e)}

# Global instance
yahoo_provider = YahooFinanceProvider()
