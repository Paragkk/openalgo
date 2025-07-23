import os
from utils.httpx_client import get_httpx_client
from utils.logging import get_logger

logger = get_logger(__name__)

def get_margin_data(auth):
    """Get account margin/funds data from Alpaca"""
    try:
        client = get_httpx_client()
        BROKER_API_SECRET = os.getenv('BROKER_API_SECRET')
        
        # Alpaca account endpoint
        url = 'https://paper-api.alpaca.markets/v2/account'
        
        headers = {
            'APCA-API-KEY-ID': auth,
            'APCA-API-SECRET-KEY': BROKER_API_SECRET,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = client.get(url, headers=headers)
        response.raise_for_status()
        
        account_data = response.json()
        
        # Extract values from Alpaca account data
        cash = float(account_data.get('cash', 0))
        buying_power = float(account_data.get('buying_power', 0))
        equity = float(account_data.get('equity', 0))
        last_equity = float(account_data.get('last_equity', 0))
        initial_margin = float(account_data.get('initial_margin', 0))
        
        # Calculate P&L
        unrealized_pnl = equity - cash if equity > 0 and cash > 0 else 0
        realized_pnl = equity - last_equity if last_equity > 0 else 0
        
        # Transform Alpaca account data to OpenAlgo standard format
        margin_data = {
            "availablecash": "{:.2f}".format(cash),
            "collateral": "{:.2f}".format(buying_power - cash),  # Margin available beyond cash
            "utiliseddebits": "{:.2f}".format(initial_margin),
            "m2munrealized": "{:.2f}".format(unrealized_pnl),
            "m2mrealized": "{:.2f}".format(realized_pnl),
        }
        
        return margin_data
        
    except Exception as e:
        logger.error(f"Failed to get margin data: {str(e)}")
        # Return empty data structure in case of error, matching other brokers
        return {
            "availablecash": "0.00",
            "collateral": "0.00", 
            "utiliseddebits": "0.00",
            "m2munrealized": "0.00",
            "m2mrealized": "0.00",
        }

def get_portfolio_history(auth, period='1M', timeframe='1D'):
    """Get portfolio history from Alpaca"""
    try:
        client = get_httpx_client()
        BROKER_API_SECRET = os.getenv('BROKER_API_SECRET')
        
        # Alpaca portfolio history endpoint
        url = 'https://paper-api.alpaca.markets/v2/account/portfolio/history'
        
        params = {
            'period': period,
            'timeframe': timeframe,
            'extended_hours': True
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
        logger.error(f"Failed to get portfolio history: {str(e)}")
        return {'error': str(e)}

def get_account_activities(auth, activity_type=None):
    """Get account activities from Alpaca"""
    try:
        client = get_httpx_client()
        BROKER_API_SECRET = os.getenv('BROKER_API_SECRET')
        
        # Alpaca account activities endpoint
        url = 'https://paper-api.alpaca.markets/v2/account/activities'
        
        params = {}
        if activity_type:
            params['activity_type'] = activity_type
        
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
        logger.error(f"Failed to get account activities: {str(e)}")
        return {'error': str(e)}

def get_account_configurations(auth):
    """Get account configurations from Alpaca"""
    try:
        client = get_httpx_client()
        BROKER_API_SECRET = os.getenv('BROKER_API_SECRET')
        
        # Alpaca account configurations endpoint
        url = 'https://paper-api.alpaca.markets/v2/account/configurations'
        
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
        logger.error(f"Failed to get account configurations: {str(e)}")
        return {'error': str(e)}

def update_account_configurations(auth, config_data):
    """Update account configurations"""
    try:
        client = get_httpx_client()
        BROKER_API_SECRET = os.getenv('BROKER_API_SECRET')
        
        # Alpaca account configurations endpoint
        url = 'https://paper-api.alpaca.markets/v2/account/configurations'
        
        headers = {
            'APCA-API-KEY-ID': auth,
            'APCA-API-SECRET-KEY': BROKER_API_SECRET,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = client.patch(url, headers=headers, json=config_data)
        response.raise_for_status()
        
        return response.json()
        
    except Exception as e:
        logger.error(f"Failed to update account configurations: {str(e)}")
        return {'error': str(e)}

def calculate_available_margin(margin_data):
    """Calculate available margin for trading"""
    try:
        buying_power = float(margin_data.get('buying_power', 0))
        initial_margin = float(margin_data.get('initial_margin', 0))
        
        available_margin = buying_power - initial_margin
        
        return {
            'available_margin': max(0, available_margin),
            'buying_power': buying_power,
            'used_margin': initial_margin
        }
        
    except Exception as e:
        logger.error(f"Failed to calculate available margin: {str(e)}")
        return {'error': str(e)}
