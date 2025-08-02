import os
from broker.alpaca.mapping.transform_data import transform_data, transform_modify_order_data
from utils.httpx_client import get_httpx_client
from utils.logging import get_logger

logger = get_logger(__name__)

def get_api_response(endpoint, auth, method="GET", payload=None):
    """
    Make API request to Alpaca
    
    Args:
        endpoint: API endpoint
        auth: Authentication token (API key)
        method: HTTP method
        payload: Request payload
        
    Returns:
        dict: API response
    """
    client = get_httpx_client()
    base_url = 'https://paper-api.alpaca.markets/v2'
    
    BROKER_API_SECRET = os.getenv('BROKER_API_SECRET')
    
    headers = {
        'APCA-API-KEY-ID': auth,
        'APCA-API-SECRET-KEY': BROKER_API_SECRET,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    url = f"{base_url}{endpoint}"
    
    try:
        if method.upper() == 'GET':
            response = client.get(url, headers=headers)
        elif method.upper() == 'POST':
            response = client.post(url, headers=headers, json=payload)
        elif method.upper() == 'PATCH':
            response = client.patch(url, headers=headers, json=payload)
        elif method.upper() == 'DELETE':
            response = client.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
            
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        logger.error(f"Alpaca API request failed: {str(e)}")
        return {'error': str(e)}

def get_order_book(auth):
    """Get order book from Alpaca"""
    return get_api_response("/orders", auth)

def get_trade_book(auth):
    """Get trade book from Alpaca - using orders with filled status"""
    try:
        # First try to get filled orders
        response = get_api_response("/orders?status=filled", auth)
        
        # Check for API error response
        if isinstance(response, dict) and 'error' in response:
            logger.error(f"API error in trade book: {response['error']}")
            return []
        
        # Ensure we return a list for consistency
        if not isinstance(response, list):
            logger.warning(f"Expected list but got {type(response)} for trade book: {response}")
            return []
        
        logger.info(f"Retrieved {len(response)} filled orders from Alpaca")
        
        # If no filled orders found, for testing purposes, also get partially filled orders
        if not response:
            logger.info("No filled orders found, checking for partially filled orders...")
            response = get_api_response("/orders?status=partially_filled", auth)
            if isinstance(response, list):
                logger.info(f"Found {len(response)} partially filled orders")
            else:
                response = []
        
        # If still no data, check all recent orders for debugging
        if not response:
            logger.info("No filled or partially filled orders found, checking all recent orders...")
            all_orders = get_api_response("/orders", auth)
            if isinstance(all_orders, list):
                logger.info(f"Total orders in account: {len(all_orders)}")
                if all_orders:
                    sample_order = all_orders[0]
                    logger.info(f"Sample order status: {sample_order.get('status')}, filled_qty: {sample_order.get('filled_qty')}")
        else:
            # Log first filled order for debugging
            sample_order = response[0]
            logger.info(f"Sample filled order: ID={sample_order.get('id')}, symbol={sample_order.get('symbol')}, "
                       f"side={sample_order.get('side')}, filled_qty={sample_order.get('filled_qty')}, "
                       f"filled_avg_price={sample_order.get('filled_avg_price')}")
            logger.info(f"Complete sample order data: {sample_order}")
        
        # Return all filled orders - let the mapping handle the filtering
        return response
        
    except Exception as e:
        logger.error(f"Error fetching trade book: {e}")
        return []

def get_positions(auth):
    """Get positions from Alpaca"""
    return get_api_response("/positions", auth)

def get_holdings(auth):
    """Get holdings from Alpaca - same as positions for Alpaca"""
    return get_api_response("/positions", auth)

def place_order_api(data, auth):
    """
    Place order with Alpaca
    
    Args:
        data: Order data in OpenAlgo format
        auth: Authentication token
        
    Returns:
        dict: Order response
    """
    try:
        # Transform OpenAlgo data to Alpaca format
        alpaca_data = transform_data(data)
        
        # Place order with Alpaca
        response = get_api_response("/orders", auth, "POST", alpaca_data)
        
        return response
        
    except Exception as e:
        logger.error(f"Place order failed: {str(e)}")
        return {'error': str(e)}

def place_smartorder_api(data, auth):
    """
    Place smart order (for position closure)
    """
    try:
        # Get current positions to determine what to close
        positions = get_positions(auth)
        
        symbol = data.get('symbol')
        
        # Find the position to close
        target_position = None
        if isinstance(positions, list):
            for pos in positions:
                if pos.get('symbol') == symbol:
                    target_position = pos
                    break
        
        if not target_position:
            return {'error': f'No position found for {symbol}'}
        
        # Create close order (opposite side)
        qty = abs(float(target_position.get('qty', 0)))
        if qty == 0:
            return {'error': 'No quantity to close'}
        
        # Determine side - if current position is long, we sell; if short, we buy
        current_qty = float(target_position.get('qty', 0))
        side = 'sell' if current_qty > 0 else 'buy'
        
        close_order_data = {
            'symbol': symbol,
            'qty': str(int(qty)),
            'side': side,
            'type': 'market',
            'time_in_force': 'day'
        }
        
        response = get_api_response("/orders", auth, "POST", close_order_data)
        return response
        
    except Exception as e:
        logger.error(f"Smart order failed: {str(e)}")
        return {'error': str(e)}

def cancel_order(orderid, auth):
    """Cancel order"""
    endpoint = f"/orders/{orderid}"
    return get_api_response(endpoint, auth, "DELETE")

def modify_order(data, auth):
    """Modify existing order"""
    try:
        orderid = data.get('orderid')
        if not orderid:
            return {'error': 'Order ID is required'}
        
        alpaca_data = transform_modify_order_data(data)
        endpoint = f"/orders/{orderid}"
        return get_api_response(endpoint, auth, "PATCH", alpaca_data)
        
    except Exception as e:
        logger.error(f"Modify order failed: {str(e)}")
        return {'error': str(e)}

def close_all_positions(current_api_key, auth):
    """Close all open positions"""
    try:
        # Get all positions
        positions = get_positions(auth)
        
        if not isinstance(positions, list):
            return {'error': 'Failed to get positions'}
        
        closed_orders = []
        
        for position in positions:
            qty = float(position.get('qty', 0))
            if qty == 0:
                continue  # Skip positions with zero quantity
            
            symbol = position.get('symbol')
            side = 'sell' if qty > 0 else 'buy'
            
            close_order_data = {
                'symbol': symbol,
                'qty': str(abs(int(qty))),
                'side': side,
                'type': 'market',
                'time_in_force': 'day'
            }
            
            response = get_api_response("/orders", auth, "POST", close_order_data)
            closed_orders.append(response)
        
        return {'closed_orders': closed_orders, 'count': len(closed_orders)}
        
    except Exception as e:
        logger.error(f"Close all positions failed: {str(e)}")
        return {'error': str(e)}

def cancel_all_orders_api(data, auth):
    """Cancel all pending orders"""
    try:
        # Get all open orders
        orders = get_api_response("/orders?status=open", auth)
        
        if not isinstance(orders, list):
            return {'error': 'Failed to get orders'}
        
        cancelled_orders = []
        
        for order in orders:
            order_id = order.get('id')
            if order_id:
                response = cancel_order(order_id, auth)
                cancelled_orders.append(response)
        
        return {'cancelled_orders': cancelled_orders, 'count': len(cancelled_orders)}
        
    except Exception as e:
        logger.error(f"Cancel all orders failed: {str(e)}")
        return {'error': str(e)}

def get_open_position(tradingsymbol, exchange, producttype, auth):
    """Get specific open position"""
    try:
        positions = get_positions(auth)
        
        if not isinstance(positions, list):
            return None
        
        # Find the specific position
        for position in positions:
            if position.get('symbol') == tradingsymbol:
                qty = float(position.get('qty', 0))
                if qty != 0:  # Only return if there's an actual position
                    return position
        
        return None
        
    except Exception as e:
        logger.error(f"Get open position failed: {str(e)}")
        return None
