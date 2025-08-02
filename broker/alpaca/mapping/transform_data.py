def transform_data(data):
    """
    Transform OpenAlgo order data to Alpaca format
    
    Args:
        data: OpenAlgo standard order data
        
    Returns:
        dict: Alpaca-specific order data
    """
    # Alpaca uses symbol directly (no need for token mapping for US stocks)
    symbol = data['symbol']
    
    # Map OpenAlgo fields to Alpaca fields
    transformed = {
        "symbol": symbol,
        "side": map_action(data['action']),  # buy/sell
        "type": map_order_type(data['pricetype']),
        "qty": str(int(data['quantity'])),  # Alpaca expects string
        "time_in_force": map_validity(data.get('validity', 'day')),
    }
    
    # Add price fields based on order type
    if data['pricetype'].upper() in ['LIMIT', 'STOP_LIMIT']:
        transformed["limit_price"] = str(float(data.get('price', 0)))
    
    if data['pricetype'].upper() in ['STOP', 'STOP_LIMIT']:
        transformed["stop_price"] = str(float(data.get('trigger_price', 0)))
    
    # Add extended hours trading if needed
    transformed["extended_hours"] = data.get('extended_hours', False)
    
    return transformed

def transform_modify_order_data(data):
    """Transform modify order data for Alpaca"""
    transformed = {}
    
    if 'quantity' in data:
        transformed["qty"] = str(int(data["quantity"]))
    
    if 'price' in data:
        transformed["limit_price"] = str(float(data["price"]))
    
    if 'trigger_price' in data:
        transformed["stop_price"] = str(float(data["trigger_price"]))
    
    if 'validity' in data:
        transformed["time_in_force"] = map_validity(data["validity"])
    
    return transformed

def map_action(action):
    """Map OpenAlgo action to Alpaca action"""
    mapping = {
        'BUY': 'buy',
        'SELL': 'sell'
    }
    return mapping.get(action.upper(), action.lower())

def map_order_type(pricetype):
    """Map OpenAlgo price type to Alpaca order type"""
    mapping = {
        'MARKET': 'market',
        'LIMIT': 'limit',
        'SL': 'stop',
        'SL-M': 'stop',
        'STOP': 'stop',
        'STOP_LIMIT': 'stop_limit'
    }
    return mapping.get(pricetype.upper(), 'market')

def map_product_type(product):
    """Map OpenAlgo product to Alpaca product - Alpaca doesn't use product types like Indian brokers"""
    # Alpaca doesn't have product types like CNC/MIS/NRML
    # All orders are cash orders by default
    return None

def reverse_map_product_type(alpaca_product):
    """Reverse map Alpaca product to OpenAlgo product"""
    # Since Alpaca doesn't use product types, default to CNC (Cash and Carry)
    return 'CNC'

def map_exchange(exchange):
    """Map OpenAlgo exchange to Alpaca exchange"""
    # Alpaca only supports US markets
    mapping = {
        'NASDAQ': 'NASDAQ',
        'NYSE': 'NYSE',
        'AMEX': 'AMEX'
    }
    
    exchange_upper = exchange.upper()
    if exchange_upper not in mapping:
        raise ValueError(f"Exchange '{exchange}' is not supported by Alpaca. Supported exchanges: {list(mapping.keys())}")
    
    return mapping[exchange_upper]

def map_validity(validity):
    """Map OpenAlgo validity to Alpaca time_in_force"""
    mapping = {
        'DAY': 'day',
        'GTC': 'gtc',
        'IOC': 'ioc',
        'FOK': 'fok'
    }
    return mapping.get(validity.upper(), 'day')
