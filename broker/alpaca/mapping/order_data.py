def map_order_data(order_data):
    """
    Map Alpaca order data to OpenAlgo standard format
    
    Args:
        order_data: Raw order data from Alpaca
        
    Returns:
        dict: OpenAlgo standard order data
    """
    return {
        'orderid': str(order_data.get('id', '')),
        'symbol': order_data.get('symbol', ''),
        'exchange': 'NASDAQ',  # Default for Alpaca
        'action': order_data.get('side', '').upper(),
        'quantity': int(order_data.get('qty', 0)),
        'price': float(order_data.get('limit_price', 0)) if order_data.get('limit_price') else 0,
        'product': 'CNC',  # Alpaca doesn't have product types, default to CNC
        'status': map_order_status(order_data.get('status', '')),
        'timestamp': order_data.get('created_at', ''),
        'filled_quantity': int(order_data.get('filled_qty', 0)),
        'pending_quantity': int(order_data.get('qty', 0)) - int(order_data.get('filled_qty', 0)),
        'average_price': float(order_data.get('filled_avg_price', 0)) if order_data.get('filled_avg_price') else 0,
        'order_type': order_data.get('type', '').upper(),
        'trigger_price': float(order_data.get('stop_price', 0)) if order_data.get('stop_price') else 0
    }

def map_trade_data(trade_data):
    """Map Alpaca trade data to OpenAlgo format"""
    # For Alpaca, trades are represented as filled orders
    return {
        'tradeid': str(trade_data.get('id', '')),
        'orderid': str(trade_data.get('id', '')),  # Same as order ID for Alpaca
        'symbol': trade_data.get('symbol', ''),
        'exchange': 'NASDAQ',
        'action': trade_data.get('side', '').upper(),
        'quantity': int(trade_data.get('filled_qty', 0)),
        'price': float(trade_data.get('filled_avg_price', 0)) if trade_data.get('filled_avg_price') else 0,
        'product': 'CNC',
        'timestamp': trade_data.get('filled_at', trade_data.get('created_at', ''))
    }

def map_position_data(position_data):
    """Map Alpaca position data to OpenAlgo format"""
    qty = float(position_data.get('qty', 0))
    avg_entry_price = float(position_data.get('avg_entry_price', 0))
    market_value = float(position_data.get('market_value', 0))
    
    # Calculate P&L
    pnl = float(position_data.get('unrealized_pl', 0))
    day_change = float(position_data.get('unrealized_intraday_pl', 0))
    
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
    transformed_orders = []
    
    if not raw_orders:
        return transformed_orders
        
    for order in raw_orders:
        transformed_order = map_order_data(order)
        transformed_orders.append(transformed_order)
        
    return transformed_orders

def transform_tradebook_data(raw_trades):
    """Transform list of raw trades to OpenAlgo format"""
    transformed_trades = []
    
    if not raw_trades:
        return transformed_trades
        
    for trade in raw_trades:
        transformed_trade = map_trade_data(trade)
        transformed_trades.append(transformed_trade)
        
    return transformed_trades

def transform_positions_data(raw_positions):
    """Transform list of raw positions to OpenAlgo format"""
    transformed_positions = []
    
    if not raw_positions:
        return transformed_positions
        
    for position in raw_positions:
        # Only include positions with non-zero quantity
        qty = float(position.get('qty', 0))
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
        qty = float(position.get('qty', 0))
        if qty == 0:
            continue  # Skip positions with zero quantity
            
        avg_entry_price = float(position.get('avg_entry_price', 0))
        market_value = float(position.get('market_value', 0))
        current_price = market_value / abs(qty) if qty != 0 else 0
        
        portfolio_item = {
            'symbol': position.get('symbol', ''),
            'exchange': 'NASDAQ',
            'quantity': int(qty),
            'average_price': avg_entry_price,
            'current_price': current_price,
            'pnl': float(position.get('unrealized_pl', 0)),
            'day_change': float(position.get('unrealized_intraday_pl', 0)),
            'day_change_percent': float(position.get('unrealized_intraday_plpc', 0)) * 100,
            'market_value': market_value
        }
        portfolio.append(portfolio_item)
        
    return portfolio

def calculate_portfolio_statistics(portfolio):
    """Calculate portfolio statistics"""
    total_value = sum(abs(p.get('market_value', 0)) for p in portfolio)
    total_pnl = sum(p.get('pnl', 0) for p in portfolio)
    total_day_change = sum(p.get('day_change', 0) for p in portfolio)
    
    return {
        'total_value': total_value,
        'total_pnl': total_pnl,
        'total_day_change': total_day_change,
        'positions_count': len(portfolio)
    }

def transform_holdings_data(raw_positions):
    """Transform raw positions to OpenAlgo holdings format"""
    return map_portfolio_data(raw_positions)
