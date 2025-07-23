"""
Alpaca WebSocket mapping and utilities
"""

class AlpacaExchangeMapper:
    """Map between OpenAlgo and Alpaca exchange formats"""
    
    @staticmethod
    def to_alpaca_exchange(openalgo_exchange):
        """Convert OpenAlgo exchange to Alpaca exchange"""
        mapping = {
            'NASDAQ': 'NASDAQ',
            'NYSE': 'NYSE',
            'AMEX': 'AMEX'
        }
        
        exchange_upper = openalgo_exchange.upper()
        if exchange_upper not in mapping:
            raise ValueError(f"Exchange '{openalgo_exchange}' is not supported by Alpaca. Supported exchanges: {list(mapping.keys())}")
        
        return mapping[exchange_upper]
    
    @staticmethod
    def from_alpaca_exchange(alpaca_exchange):
        """Convert Alpaca exchange to OpenAlgo exchange"""
        mapping = {
            'NASDAQ': 'NASDAQ',
            'NYSE': 'NYSE', 
            'AMEX': 'AMEX'
        }
        
        exchange_upper = alpaca_exchange.upper()
        if exchange_upper not in mapping:
            raise ValueError(f"Unknown Alpaca exchange '{alpaca_exchange}'. Known exchanges: {list(mapping.keys())}")
        
        return mapping[exchange_upper]

class AlpacaCapabilityRegistry:
    """Registry of Alpaca capabilities"""
    
    @staticmethod
    def get_supported_features():
        """Get list of supported features"""
        return {
            'market_data': True,
            'order_management': True,
            'portfolio_data': True,
            'account_data': True,
            'streaming': False,  # WebSocket not implemented yet
            'paper_trading': True,
            'extended_hours': True
        }
    
    @staticmethod
    def get_supported_exchanges():
        """Get list of supported exchanges"""
        return ['NASDAQ', 'NYSE', 'AMEX']
    
    @staticmethod  
    def get_supported_order_types():
        """Get list of supported order types"""
        return ['market', 'limit', 'stop', 'stop_limit']
    
    @staticmethod
    def get_supported_timeframes():
        """Get list of supported timeframes for data"""
        return ['1Min', '5Min', '15Min', '30Min', '1Hour', '1Day', '1Week', '1Month']
