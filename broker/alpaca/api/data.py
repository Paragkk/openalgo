import os
import pandas as pd
from utils.httpx_client import get_httpx_client
from utils.logging import get_logger
from broker.alpaca.api.yahoo_finance import yahoo_provider

logger = get_logger(__name__)

def get_quotes(symbols, auth):
    """Get real-time quotes for symbols from Alpaca"""
    try:
        client = get_httpx_client()
        BROKER_API_SECRET = os.getenv('BROKER_API_SECRET')
        
        # Convert symbols to comma-separated string if it's a list
        if isinstance(symbols, list):
            symbols_str = ','.join(symbols)
        else:
            symbols_str = symbols
        
        # Alpaca market data API endpoint
        url = f'https://data.alpaca.markets/v2/stocks/quotes/latest?symbols={symbols_str}'
        
        headers = {
            'APCA-API-KEY-ID': auth,
            'APCA-API-SECRET-KEY': BROKER_API_SECRET,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = client.get(url, headers=headers)
        response.raise_for_status()
        
        return response.json()
        
    except Exception as e:
        error_str = str(e)
        # Don't log 403 errors as they are expected for paper trading accounts
        if '403' not in error_str and 'Forbidden' not in error_str:
            logger.error(f"Failed to get quotes: {error_str}")
        return {'error': f'Market data access denied. Please check your Alpaca account has market data subscription: {error_str}'}

def get_market_depth(symbol, exchange, auth):
    """Get market depth for a symbol - Alpaca doesn't provide traditional market depth"""
    try:
        # Alpaca doesn't provide market depth like Indian brokers
        # We can return basic quote information instead
        quotes = get_quotes([symbol], auth)
        
        if 'quotes' in quotes and symbol in quotes['quotes']:
            quote = quotes['quotes'][symbol]
            
            # Format as market depth structure
            market_depth = {
                'symbol': symbol,
                'exchange': 'NASDAQ',
                'bids': [
                    {
                        'price': quote.get('bid_price', 0),
                        'quantity': quote.get('bid_size', 0),
                        'orders': 1
                    }
                ],
                'asks': [
                    {
                        'price': quote.get('ask_price', 0),
                        'quantity': quote.get('ask_size', 0),
                        'orders': 1
                    }
                ]
            }
            
            return market_depth
        
        return {'error': 'No data available'}
        
    except Exception as e:
        logger.error(f"Failed to get market depth: {str(e)}")
        return {'error': str(e)}

def get_historical_data(symbol, exchange, timeframe, start_date, end_date, auth):
    """Get historical data from Alpaca"""
    try:
        client = get_httpx_client()
        BROKER_API_SECRET = os.getenv('BROKER_API_SECRET')
        
        # Map timeframe to Alpaca format
        alpaca_timeframe = map_timeframe(timeframe)
        
        # Alpaca historical data endpoint
        url = 'https://data.alpaca.markets/v2/stocks/bars'
        
        params = {
            'symbols': symbol,
            'timeframe': alpaca_timeframe,
            'start': start_date,
            'end': end_date,
            'limit': 1000,
            'adjustment': 'raw'
        }
        
        headers = {
            'APCA-API-KEY-ID': auth,
            'APCA-API-SECRET-KEY': BROKER_API_SECRET,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = client.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        return response.json()
        
    except Exception as e:
        error_str = str(e)
        # Don't log 403 errors as they are expected for paper trading accounts
        if '403' not in error_str and 'Forbidden' not in error_str:
            logger.error(f"Failed to get historical data: {error_str}")
        
        # Try Yahoo Finance as fallback for market data access issues
        logger.info(f"Attempting to fetch data from Yahoo Finance for {symbol}")
        try:
            yahoo_result = yahoo_provider.get_historical_data(
                symbol, exchange, alpaca_timeframe, start_date, end_date
            )
            if yahoo_result and 'bars' in yahoo_result and yahoo_result['bars']:
                logger.info(f"Successfully retrieved data from Yahoo Finance for {symbol}")
                return yahoo_result
        except Exception as yahoo_error:
            logger.warning(f"Yahoo Finance fallback also failed for {symbol}: {str(yahoo_error)}")
        
        # Return empty data structure for graceful handling
        return {
            'bars': {},
            'error': f'Market data access denied. Please check your Alpaca account has market data subscription: {error_str}'
        }

def get_current_price(symbol, auth):
    """Get current price for a symbol"""
    try:
        quotes = get_quotes([symbol], auth)
        
        if 'quotes' in quotes and symbol in quotes['quotes']:
            quote = quotes['quotes'][symbol]
            
            # Return the mid price or last price
            bid_price = float(quote.get('bid_price', 0))
            ask_price = float(quote.get('ask_price', 0))
            
            if bid_price > 0 and ask_price > 0:
                current_price = (bid_price + ask_price) / 2
            else:
                current_price = bid_price or ask_price
            
            return {
                'symbol': symbol,
                'price': current_price,
                'bid': bid_price,
                'ask': ask_price,
                'timestamp': quote.get('timestamp', '')
            }
        
        return {'error': 'No price data available'}
        
    except Exception as e:
        error_str = str(e)
        # Don't log 403 errors as they are expected for paper trading accounts
        if '403' not in error_str and 'Forbidden' not in error_str:
            logger.error(f"Failed to get current price: {error_str}")
        return {'error': f'Market data access denied. Please check your Alpaca account has market data subscription: {error_str}'}

def get_trades(symbol, auth):
    """Get recent trades for a symbol"""
    try:
        client = get_httpx_client()
        BROKER_API_SECRET = os.getenv('BROKER_API_SECRET')
        
        # Alpaca trades endpoint
        url = f'https://data.alpaca.markets/v2/stocks/trades/latest?symbols={symbol}'
        
        headers = {
            'APCA-API-KEY-ID': auth,
            'APCA-API-SECRET-KEY': BROKER_API_SECRET,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = client.get(url, headers=headers)
        response.raise_for_status()
        
        return response.json()
        
    except Exception as e:
        error_str = str(e)
        # Don't log 403 errors as they are expected for paper trading accounts
        if '403' not in error_str and 'Forbidden' not in error_str:
            logger.error(f"Failed to get trades: {error_str}")
        return {'error': f'Market data access denied. Please check your Alpaca account has market data subscription: {error_str}'}

def map_timeframe(timeframe):
    """Map OpenAlgo timeframe to Alpaca timeframe"""
    mapping = {
        '1m': '1Min',
        '5m': '5Min',
        '15m': '15Min',
        '30m': '30Min',
        '1h': '1Hour',
        '1d': '1Day',
        '1w': '1Week',
        '1M': '1Month'
    }
    
    return mapping.get(timeframe.lower(), '1Min')

def search_symbols(query, auth):
    """Search for symbols - Alpaca doesn't have a direct search API"""
    try:
        # This is a basic implementation
        # In a real scenario, you might want to use a separate symbol database
        # or integrate with a third-party symbol search service
        
        # For now, return a simple response
        return {
            'results': [
                {
                    'symbol': query.upper(),
                    'name': f'{query.upper()} Stock',
                    'exchange': 'NASDAQ',
                    'type': 'stock'
                }
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to search symbols: {str(e)}")
        return {'error': str(e)}


class BrokerData:
    """Alpaca Broker Data Handler"""
    
    def __init__(self, auth_token, feed_token=None):
        self.auth_token = auth_token
        self.feed_token = feed_token
    
    def get_history(self, symbol: str, exchange: str, interval: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Get historical data from Alpaca"""
        import pandas as pd
        
        # Call the existing get_historical_data function
        result = get_historical_data(symbol, exchange, interval, start_date, end_date, self.auth_token)
        
        # Check if there's an error
        if isinstance(result, dict) and 'error' in result:
            if 'market data access denied' in result['error'].lower():
                # Return empty DataFrame for graceful handling
                return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])
            else:
                raise Exception(result['error'])
        
        # Convert the response to DataFrame
        if isinstance(result, dict) and 'bars' in result and symbol in result['bars']:
            bars = result['bars'][symbol]
            df = pd.DataFrame(bars)
            
            # Rename columns to match expected format
            column_mapping = {
                't': 'timestamp',
                'o': 'open', 
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume'
            }
            df = df.rename(columns=column_mapping)
            
            # Convert timestamp if needed
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Ensure all required columns exist
            required_columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            for col in required_columns:
                if col not in df.columns:
                    df[col] = None
            
            # Add oi column if not present
            if 'oi' not in df.columns:
                df['oi'] = 0
                
            return df
        
        # Return empty DataFrame if no data
        return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'oi'])
