from utils.data_utils import safe_float

def map_order_data(order_data):
    """
    Map Alpaca order data to OpenAlgo standard format.
    Handles both single orders and lists of orders.
    
    Args:
        order_data: Either a single order dict or a list of order dicts from Alpaca
        
    Returns:
        Either a single mapped order dict or a list of mapped order dicts
    """
    if isinstance(order_data, list):
        return [map_single_order(order) for order in order_data]
    else:
        return map_single_order(order_data)

def map_single_order(order):
    """
    Map a single order from Alpaca format to OpenAlgo format.
    
    Args:
        order: Single order dict from Alpaca API
        
    Returns:
        dict: Mapped order in OpenAlgo format
    """
    return {
        'orderid': str(order.get('id', '')),
        'symbol': order.get('symbol', ''),
        'exchange': 'NASDAQ',  # Default for Alpaca
        'action': order.get('side', '').upper(),
        'quantity': int(order.get('qty', 0)),
        'price': safe_float(order.get('limit_price', 0)),
        'product': 'CNC',  # Alpaca doesn't have product types, default to CNC
        'status': map_order_status(order.get('status', '')),
        'timestamp': order.get('created_at', ''),
        'filled_quantity': int(order.get('filled_qty', 0)),
        'pending_quantity': int(order.get('qty', 0)) - int(order.get('filled_qty', 0)),
        'average_price': safe_float(order.get('filled_avg_price', 0)),
        'order_type': order.get('type', '').upper(),
        'trigger_price': safe_float(order.get('stop_price', 0))
    }

def map_trade_data(trade_data):
    """
    Map Alpaca trade data to OpenAlgo standard format.
    Handles both single trades and lists of trades.
    
    Args:
        trade_data: Either a single trade dict or a list of trade dicts from Alpaca
        
    Returns:
        Either a single mapped trade dict or a list of mapped trade dicts
    """
    if isinstance(trade_data, list):
        mapped_trades = []
        for trade in trade_data:
            mapped_trade = map_single_trade(trade)
            # Only add trades that have some data (not completely empty)
            if mapped_trade.get('symbol') and mapped_trade.get('action'):
                mapped_trades.append(mapped_trade)
        return mapped_trades
    else:
        return map_single_trade(trade_data)

def map_single_trade(trade):
    """Map a single trade from Alpaca format to OpenAlgo format"""
    # For Alpaca, trades are represented as filled orders
    from utils.logging import get_logger
    logger = get_logger(__name__)
    
    logger.debug(f"Mapping trade data: {trade}")
    
    # Safely extract and convert quantity
    # Try multiple field names that Alpaca might use
    quantity = 0
    for qty_field in ['filled_qty', 'qty', 'quantity']:
        filled_qty = trade.get(qty_field, 0)
        try:
            if filled_qty:
                if isinstance(filled_qty, str):
                    quantity = int(float(filled_qty)) if filled_qty != '0' else 0
                else:
                    quantity = int(float(filled_qty))
                if quantity > 0:
                    break
        except (ValueError, TypeError):
            continue
    
    # Safely extract and convert average price
    # Try multiple field names that Alpaca might use
    average_price = 0.0
    for price_field in ['filled_avg_price', 'avg_fill_price', 'price', 'limit_price']:
        filled_avg_price = trade.get(price_field, 0)
        try:
            if filled_avg_price:
                if isinstance(filled_avg_price, str):
                    average_price = float(filled_avg_price) if filled_avg_price != '0' else 0.0
                else:
                    average_price = float(filled_avg_price)
                if average_price > 0:
                    break
        except (ValueError, TypeError):
            continue
    
    # If we still don't have price but have quantity, try to use any price field as fallback
    if quantity > 0 and average_price == 0:
        for price_field in ['stop_price', 'trail_price']:
            fallback_price = trade.get(price_field, 0)
            try:
                if fallback_price:
                    if isinstance(fallback_price, str):
                        average_price = float(fallback_price) if fallback_price != '0' else 0.0
                    else:
                        average_price = float(fallback_price)
                    if average_price > 0:
                        break
            except (ValueError, TypeError):
                continue
    
    # Calculate trade value
    trade_value = quantity * average_price if quantity > 0 and average_price > 0 else 0.0
    
    # Get transaction type (side)
    side = trade.get('side', '').upper()
    if not side:
        # Fallback to other possible field names
        side = trade.get('transaction_type', trade.get('action', '')).upper()
    
    # Get order type
    order_type = trade.get('type', '').upper()
    if not order_type:
        order_type = trade.get('order_type', 'MARKET').upper()
    
    # Get timestamp - prefer filled_at over created_at for actual execution time
    timestamp = ''
    for time_field in ['filled_at', 'updated_at', 'submitted_at', 'created_at']:
        timestamp = trade.get(time_field, '')
        if timestamp:
            break
    
    # Use a separate trade ID if available, otherwise use order ID
    trade_id = trade.get('trade_id', trade.get('id', ''))
    order_id = trade.get('order_id', trade.get('id', ''))
    
    # Determine exchange - default to NASDAQ but check if other info is available
    symbol = trade.get('symbol', '')
    exchange = 'NASDAQ'  # Default for most US stocks
    
    # Log the extracted values for debugging
    logger.debug(f"Extracted values: symbol={symbol}, side={side}, quantity={quantity}, "
                f"average_price={average_price}, trade_value={trade_value}, "
                f"order_id={order_id}, timestamp={timestamp}")
    
    # Log what fields were actually found in the trade data
    available_fields = list(trade.keys())
    logger.debug(f"Available fields in trade data: {available_fields}")
    
    return {
        'tradeid': str(trade_id),
        'orderid': str(order_id),
        'symbol': symbol,
        'exchange': exchange,
        'action': side,
        'quantity': quantity,
        'average_price': average_price,
        'trade_value': trade_value,
        'price': average_price,  # For backward compatibility
        'product': 'CNC',  # Default product type for Alpaca
        'timestamp': timestamp,
        'order_type': order_type,
        'status': 'COMPLETE'  # All trades are completed by definition
    }

def map_position_data(position_data):
    """
    Map Alpaca position data to OpenAlgo format.
    Handles both single positions and lists of positions.
    
    Args:
        position_data: Either a single position dict or a list of position dicts from Alpaca
        
    Returns:
        Either a single mapped position dict or a list of mapped position dicts
    """
    if isinstance(position_data, list):
        # Handle list of positions - map each one
        mapped_positions = []
        for position in position_data:
            mapped_position = map_single_position(position)
            if mapped_position:  # Only include valid positions
                mapped_positions.append(mapped_position)
        return mapped_positions
    else:
        # Handle single position
        return map_single_position(position_data)

def map_single_position(position_data):
    """Map a single Alpaca position to OpenAlgo format"""
    if not position_data:
        return None
        
    qty = safe_float(position_data.get('qty', 0))
    avg_entry_price = safe_float(position_data.get('avg_entry_price', 0))
    market_value = safe_float(position_data.get('market_value', 0))
    
    # Calculate P&L
    pnl = safe_float(position_data.get('unrealized_pl', 0))
    day_change = safe_float(position_data.get('unrealized_intraday_pl', 0))
    
    return {
        'symbol': position_data.get('symbol', ''),
        'exchange': 'NASDAQ',
        'quantity': int(qty),
        'product': 'CNC',
        'average_price': avg_entry_price,
        'pnl': pnl,
        'day_change': day_change,
        'market_value': market_value,
        'side': position_data.get('side', '')
    }

def map_order_status(alpaca_status):
    """Map Alpaca order status to OpenAlgo status"""
    status_mapping = {
        'new': 'PENDING',
        'partially_filled': 'OPEN', 
        'filled': 'COMPLETE',
        'done_for_day': 'CANCELLED',
        'canceled': 'CANCELLED',
        'expired': 'CANCELLED',
        'replaced': 'MODIFIED',
        'pending_cancel': 'PENDING',
        'pending_replace': 'PENDING',
        'accepted': 'OPEN',
        'pending_new': 'PENDING',
        'accepted_for_bidding': 'OPEN',
        'stopped': 'CANCELLED',
        'rejected': 'REJECTED',
        'suspended': 'CANCELLED',
        'calculated': 'OPEN'
    }
    return status_mapping.get(alpaca_status.lower(), alpaca_status.upper())

def transform_order_data(raw_orders):
    """Transform list of raw orders to OpenAlgo format"""
    if not raw_orders:
        return []
        
    return map_order_data(raw_orders)

def transform_tradebook_data(raw_trades):
    """Transform list of raw trades to OpenAlgo format"""
    from utils.logging import get_logger
    logger = get_logger(__name__)
    
    transformed_data = []
    
    if not raw_trades:
        logger.info("No raw trades provided to transform_tradebook_data")
        return transformed_data
        
    logger.info(f"Processing {len(raw_trades) if isinstance(raw_trades, list) else 1} raw trades")
        
    # Process the trades - for Alpaca, these are filled orders
    trades = map_trade_data(raw_trades) if raw_trades else []
    
    if isinstance(trades, list):
        logger.info(f"After mapping: {len(trades)} trades")
        for trade in trades:
            # Include all trades that have basic data, even if quantity is 0
            if trade.get('symbol') and trade.get('action'):
                transformed_trade = {
                    "symbol": trade.get('symbol', ''),
                    "exchange": trade.get('exchange', ''),
                    "product": trade.get('product', ''),
                    "action": trade.get('action', ''),
                    "quantity": trade.get('quantity', 0),
                    "average_price": trade.get('average_price', 0.0),
                    "trade_value": trade.get('trade_value', 0.0),
                    "orderid": trade.get('orderid', ''),
                    "tradeid": trade.get('tradeid', ''),
                    "timestamp": trade.get('timestamp', ''),
                    "order_type": trade.get('order_type', ''),
                    "status": trade.get('status', 'COMPLETE')
                }
                transformed_data.append(transformed_trade)
    else:
        # Handle single trade
        if trades and trades.get('symbol') and trades.get('action'):
            transformed_trade = {
                "symbol": trades.get('symbol', ''),
                "exchange": trades.get('exchange', ''),
                "product": trades.get('product', ''),
                "action": trades.get('action', ''),
                "quantity": trades.get('quantity', 0),
                "average_price": trades.get('average_price', 0.0),
                "trade_value": trades.get('trade_value', 0.0),
                "orderid": trades.get('orderid', ''),
                "tradeid": trades.get('tradeid', ''),
                "timestamp": trades.get('timestamp', ''),
                "order_type": trades.get('order_type', ''),
                "status": trades.get('status', 'COMPLETE')
            }
            transformed_data.append(transformed_trade)
    
    logger.info(f"Final transformed data: {len(transformed_data)} trades")
    return transformed_data

def transform_positions_data(raw_positions):
    """Transform list of raw positions to OpenAlgo format"""
    transformed_positions = []
    
    if not raw_positions:
        return transformed_positions
        
    for position in raw_positions:
        # Only include positions with non-zero quantity
        qty = safe_float(position.get('qty', 0))
        if qty != 0:
            transformed_position = map_position_data(position)
            transformed_positions.append(transformed_position)
        
    return transformed_positions

def calculate_order_statistics(orders):
    """Calculate order statistics"""
    total_orders = len(orders)
    completed_orders = len([o for o in orders if o.get('status') == 'COMPLETE'])
    pending_orders = len([o for o in orders if o.get('status') in ['PENDING', 'OPEN']])
    cancelled_orders = len([o for o in orders if o.get('status') == 'CANCELLED'])
    
    return {
        'total_orders': total_orders,
        'completed_orders': completed_orders,
        'pending_orders': pending_orders,
        'cancelled_orders': cancelled_orders
    }

def map_portfolio_data(positions_data):
    """Map positions data to portfolio format"""
    portfolio = []
    
    if not positions_data:
        return portfolio
        
    for position in positions_data:
        qty = safe_float(position.get('qty', 0))
        if qty == 0:
            continue  # Skip positions with zero quantity
            
        avg_entry_price = safe_float(position.get('avg_entry_price', 0))
        market_value = safe_float(position.get('market_value', 0))
        current_price = market_value / abs(qty) if qty != 0 else 0
        
        portfolio_item = {
            'symbol': position.get('symbol', ''),
            'exchange': 'NASDAQ',
            'quantity': int(qty),
            'average_price': avg_entry_price,
            'current_price': current_price,
            'pnl': safe_float(position.get('unrealized_pl', 0)),
            'day_change': safe_float(position.get('unrealized_intraday_pl', 0)),
            'day_change_percent': safe_float(position.get('unrealized_intraday_plpc', 0)) * 100,
            'market_value': market_value
        }
        portfolio.append(portfolio_item)
        
    return portfolio

def calculate_portfolio_statistics(portfolio):
    """Calculate portfolio statistics"""
    # Calculate totals using the standard format expected by the template
    totalholdingvalue = sum(abs(p.get('market_value', 0)) for p in portfolio)
    totalinvvalue = sum(p.get('average_price', 0) * abs(p.get('quantity', 0)) for p in portfolio)
    totalprofitandloss = sum(p.get('pnl', 0) for p in portfolio)
    
    # Calculate P&L percentage (avoid division by zero)
    totalpnlpercentage = (totalprofitandloss / totalinvvalue * 100) if totalinvvalue != 0 else 0
    
    return {
        'totalholdingvalue': totalholdingvalue,
        'totalinvvalue': totalinvvalue,
        'totalprofitandloss': totalprofitandloss,
        'totalpnlpercentage': totalpnlpercentage
    }

def transform_holdings_data(raw_positions):
    """Transform raw positions to OpenAlgo holdings format"""
    return map_portfolio_data(raw_positions)
