import os
from utils.httpx_client import get_httpx_client
from utils.logging import get_logger

logger = get_logger(__name__)

def authenticate_broker(api_key=None, secret_key=None, **kwargs):
    """
    Authenticate with Alpaca and return access token
    
    Args:
        api_key: Alpaca API key (optional, will use env var if not provided)
        secret_key: Alpaca secret key (optional, will use env var if not provided)
        **kwargs: Additional authentication parameters
        
    Returns:
        tuple: (access_token, error_message)
    """
    try:
        # Get credentials from environment or parameters
        BROKER_API_KEY = api_key or os.getenv('BROKER_API_KEY')
        BROKER_API_SECRET = secret_key or os.getenv('BROKER_API_SECRET')
        
        if not BROKER_API_KEY or not BROKER_API_SECRET:
            return None, "API key and secret key are required"
        
        # Alpaca uses basic authentication with API key and secret
        # Test the credentials by making a simple API call
        client = get_httpx_client()
        
        # Use paper trading URL as specified
        url = 'https://paper-api.alpaca.markets/v2/account'
        
        headers = {
            'APCA-API-KEY-ID': BROKER_API_KEY,
            'APCA-API-SECRET-KEY': BROKER_API_SECRET,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = client.get(url, headers=headers)
        response.raise_for_status()
        
        response_data = response.json()
        
        # If we can get account info, authentication is successful
        if 'id' in response_data:
            # For Alpaca, we return the API key as the "access token" 
            # since it uses API key authentication rather than token-based auth
            return BROKER_API_KEY, None
        else:
            return None, "Failed to authenticate with Alpaca"
            
    except Exception as e:
        logger.error(f"Alpaca authentication failed: {str(e)}")
        return None, str(e)

def get_account_info(auth_token):
    """
    Get account information from Alpaca
    
    Args:
        auth_token: API key (used as auth token)
        
    Returns:
        dict: Account information
    """
    try:
        BROKER_API_SECRET = os.getenv('BROKER_API_SECRET')
        client = get_httpx_client()
        
        url = 'https://paper-api.alpaca.markets/v2/account'
        
        headers = {
            'APCA-API-KEY-ID': auth_token,
            'APCA-API-SECRET-KEY': BROKER_API_SECRET,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = client.get(url, headers=headers)
        response.raise_for_status()
        
        return response.json()
        
    except Exception as e:
        logger.error(f"Failed to get account info: {str(e)}")
        return {'error': str(e)}
