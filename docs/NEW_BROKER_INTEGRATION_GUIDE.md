# OpenAlgo New Broker Integration Guide

## Table of Contents
1. [Overview](#overview)
2. [Architecture Understanding](#architecture-understanding)
3. [Prerequisites](#prerequisites)
4. [Step-by-Step Implementation](#step-by-step-implementation)
5. [File Structure and Components](#file-structure-and-components)
6. [Testing and Validation](#testing-and-validation)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

## Overview

This guide provides comprehensive steps for integrating a new broker into the OpenAlgo trading platform. OpenAlgo uses a modular adapter pattern that allows seamless integration of multiple brokers while maintaining a consistent API interface.

### Current Supported Brokers
OpenAlgo currently supports 23+ brokers including:
- Zerodha, Angel One, Dhan, Upstox, Fyers
- AliceBlue, Flattrade, Shoonya, Firstock
- 5paisa, IIFL, Kotak, Paytm, Groww
- And many more...

## Architecture Understanding

### Current Architecture Limitations

**⚠️ Important: Single User Per Instance**

OpenAlgo currently supports:
- ❌ **One user** per instance
- ❌ **One broker type** per instance

This means:
- One OpenAlgo instance = One user + One broker
- API keys in `.env` are tied to one specific user's trading account
- Multiple users cannot share the same instance (API keys are personal)
- To support multiple users, you need multiple OpenAlgo instances

### Single User, Single Broker Flow

```
OpenAlgo Instance
├── User A (Personal Zerodha Account)
├── User A's Zerodha API Keys in .env
└── User A's orders, positions, portfolio
```

**Each user needs their own OpenAlgo instance with their own API keys.**

### Understanding the Authentication Flow

**Two-Level Authentication:**

1. **API Level** (Instance Level):
   ```properties
   # .env - User A's personal API keys
   BROKER_API_KEY = 'user_a_zerodha_api_key'
   BROKER_API_SECRET = 'user_a_zerodha_secret'
   ```

2. **Session Level** (User Login):
   ```python
   # User A logs in with their Zerodha username/password/TOTP
   # This generates a session token for their account
   session['user'] = 'user_a'
   session['broker'] = 'zerodha'  
   session['auth_token'] = 'user_a_session_token'
   ```

**Why Both Are Needed:**
- **API Keys**: Allow the application to connect to broker's API
- **User Login**: Authenticate the specific user within their account
- **Both must belong to the same person** - you can't use someone else's API keys

### Core Concepts

1. **Adapter Pattern**: Each broker implements a standardized interface
2. **Dynamic Loading**: Brokers are loaded dynamically at runtime
3. **Consistent API**: All brokers expose the same OpenAlgo API endpoints
4. **Modular Design**: Each broker is self-contained in its own directory

### Key Components

```
broker/
├── {broker_name}/
│   ├── api/
│   │   ├── auth_api.py          # Authentication logic
│   │   ├── order_api.py         # Order management APIs
│   │   ├── data.py              # Market data APIs
│   │   └── funds.py             # Account/funds APIs
│   ├── mapping/
│   │   ├── transform_data.py    # Data transformation
│   │   └── order_data.py        # Order/position mapping
│   ├── database/
│   │   └── master_contract_db.py # Contract/symbol management
│   ├── streaming/               # WebSocket implementation
│   │   ├── {broker}_adapter.py
│   │   ├── {broker}_websocket.py
│   │   └── {broker}_mapping.py
│   └── plugin.json              # Broker metadata
```

## Prerequisites

### Broker Requirements
- [ ] Broker API documentation
- [ ] API credentials (API Key, Secret, etc.)
- [ ] Authentication flow understanding
- [ ] WebSocket feed documentation (if available)
- [ ] Symbol/contract master data access

### Development Environment
- [ ] Python 3.8+
- [ ] OpenAlgo development setup
- [ ] Broker sandbox/test environment access
- [ ] API testing tools (Postman, curl, etc.)

## Step-by-Step Implementation

### Step 1: Create Broker Directory Structure

```bash
mkdir -p broker/{broker_name}/api
mkdir -p broker/{broker_name}/mapping
mkdir -p broker/{broker_name}/database
mkdir -p broker/{broker_name}/streaming
```

### Step 2: Create Plugin Metadata

Create `broker/{broker_name}/plugin.json`:

```json
{
    "Plugin Name": "{broker_name}",
    "Plugin URI": "https://openalgo.in",
    "Description": "{Broker Name} OpenAlgo Plugin",
    "Version": "1.0",
    "Author": "Your Name",
    "Author URI": "https://openalgo.in"
}
```

### Step 3: Implement Authentication API

Create `broker/{broker_name}/api/auth_api.py`:

```python
import os
import json
from utils.httpx_client import get_httpx_client
from utils.logging import get_logger

logger = get_logger(__name__)

def authenticate_broker(request_token=None, **kwargs):
    """
    Authenticate with the broker and return access token
    
    Args:
        request_token: Token from broker login flow
        **kwargs: Additional authentication parameters
        
    Returns:
        tuple: (access_token, error_message)
    """
    try:
        # IMPORTANT: API keys are user-specific (not shareable)
        # Get credentials from environment (belongs to one user only)
        BROKER_API_KEY = os.getenv('BROKER_API_KEY')
        BROKER_API_SECRET = os.getenv('BROKER_API_SECRET')
        
        # Note: These API keys belong to ONE specific user's trading account
        # Each user needs their own OpenAlgo instance with their own keys
        
        # Implement broker-specific authentication logic
        client = get_httpx_client()
        
        # Example authentication endpoint
        url = 'https://api.{broker}.com/auth/token'
        
        # Prepare authentication data based on broker requirements
        auth_data = {
            'api_key': BROKER_API_KEY,
            'api_secret': BROKER_API_SECRET,
            'request_token': request_token
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        response = client.post(url, json=auth_data, headers=headers)
        response.raise_for_status()
        
        response_data = response.json()
        
        # Extract access token based on broker's response format
        if 'access_token' in response_data:
            return response_data['access_token'], None
        elif 'data' in response_data and 'access_token' in response_data['data']:
            return response_data['data']['access_token'], None
        else:
            return None, "Access token not found in response"
            
    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        return None, str(e)
```

### Step 4: Implement Order API

Create `broker/{broker_name}/api/order_api.py`:

```python
import json
import os
from database.auth_db import get_auth_token
from database.token_db import get_token, get_br_symbol, get_symbol
from broker.{broker_name}.mapping.transform_data import (
    transform_data, map_product_type, reverse_map_product_type, 
    transform_modify_order_data
)
from utils.httpx_client import get_httpx_client
from utils.logging import get_logger

logger = get_logger(__name__)

def get_api_response(endpoint, auth, method="GET", payload=None):
    """
    Make API request to broker
    
    Args:
        endpoint: API endpoint
        auth: Authentication token
        method: HTTP method
        payload: Request payload
        
    Returns:
        dict: API response
    """
    client = get_httpx_client()
    base_url = 'https://api.{broker}.com'
    
    headers = {
        'Authorization': f'Bearer {auth}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    url = f"{base_url}{endpoint}"
    
    try:
        if method.upper() == 'GET':
            response = client.get(url, headers=headers)
        elif method.upper() == 'POST':
            response = client.post(url, headers=headers, json=payload)
        elif method.upper() == 'PUT':
            response = client.put(url, headers=headers, json=payload)
        elif method.upper() == 'DELETE':
            response = client.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
            
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        logger.error(f"API request failed: {str(e)}")
        return {'error': str(e)}

def get_order_book(auth):
    """Get order book from broker"""
    return get_api_response("/orders", auth)

def get_trade_book(auth):
    """Get trade book from broker"""
    return get_api_response("/trades", auth)

def get_positions(auth):
    """Get positions from broker"""
    return get_api_response("/positions", auth)

def get_holdings(auth):
    """Get holdings from broker"""
    return get_api_response("/holdings", auth)

def place_order_api(data, auth):
    """
    Place order with broker
    
    Args:
        data: Order data in OpenAlgo format
        auth: Authentication token
        
    Returns:
        dict: Order response
    """
    try:
        # Transform OpenAlgo data to broker format
        broker_data = transform_data(data)
        
        # Place order with broker
        response = get_api_response("/orders", auth, "POST", broker_data)
        
        return response
        
    except Exception as e:
        logger.error(f"Place order failed: {str(e)}")
        return {'error': str(e)}

def place_smartorder_api(data, auth):
    """
    Place smart order (for position closure)
    """
    # Smart order logic for closing positions
    # This typically involves getting current positions and placing opposite orders
    pass

def cancel_order(orderid, auth):
    """Cancel order"""
    endpoint = f"/orders/{orderid}"
    return get_api_response(endpoint, auth, "DELETE")

def modify_order(data, auth):
    """Modify existing order"""
    orderid = data.get('orderid')
    broker_data = transform_modify_order_data(data)
    endpoint = f"/orders/{orderid}"
    return get_api_response(endpoint, auth, "PUT", broker_data)

def close_all_positions(current_api_key, auth):
    """Close all open positions"""
    # Implementation to close all positions
    pass

def cancel_all_orders_api(data, auth):
    """Cancel all pending orders"""
    # Implementation to cancel all orders
    pass

def get_open_position(tradingsymbol, exchange, producttype, auth):
    """Get specific open position"""
    positions = get_positions(auth)
    # Filter and return specific position
    pass
```

### Step 5: Implement Data Transformation

Create `broker/{broker_name}/mapping/transform_data.py`:

```python
from database.token_db import get_br_symbol

def transform_data(data):
    """
    Transform OpenAlgo order data to broker format
    
    Args:
        data: OpenAlgo standard order data
        
    Returns:
        dict: Broker-specific order data
    """
    # Get broker-specific symbol
    symbol = get_br_symbol(data['symbol'], data['exchange'])
    
    # Map OpenAlgo fields to broker fields
    transformed = {
        "symbol": symbol,  # or tradingsymbol, instrument, etc.
        "exchange": map_exchange(data['exchange']),
        "side": map_action(data['action']),  # BUY/SELL
        "order_type": map_order_type(data['pricetype']),
        "quantity": int(data['quantity']),
        "product": map_product_type(data['product']),
        "price": float(data.get('price', 0)),
        "trigger_price": float(data.get('trigger_price', 0)),
        "disclosed_quantity": int(data.get('disclosed_quantity', 0)),
        "validity": "DAY",  # or map_validity(data.get('validity', 'DAY'))
        "tag": "openalgo"
    }
    
    return transformed

def transform_modify_order_data(data):
    """Transform modify order data"""
    return {
        "order_type": map_order_type(data["pricetype"]),
        "quantity": int(data["quantity"]),
        "price": float(data["price"]),
        "trigger_price": float(data.get("trigger_price", 0)),
        "disclosed_quantity": int(data.get("disclosed_quantity", 0))
    }

def map_action(action):
    """Map OpenAlgo action to broker action"""
    mapping = {
        'BUY': 'BUY',    # Adjust based on broker
        'SELL': 'SELL'
    }
    return mapping.get(action.upper(), action.upper())

def map_order_type(pricetype):
    """Map OpenAlgo price type to broker order type"""
    mapping = {
        'MARKET': 'MARKET',
        'LIMIT': 'LIMIT',
        'SL': 'SL',
        'SL-M': 'SL-M'
    }
    return mapping.get(pricetype.upper(), pricetype.upper())

def map_product_type(product):
    """Map OpenAlgo product to broker product"""
    mapping = {
        'CNC': 'CNC',    # Cash and Carry
        'MIS': 'MIS',    # Intraday
        'NRML': 'NRML'   # Normal/Overnight
    }
    return mapping.get(product.upper(), product.upper())

def reverse_map_product_type(broker_product):
    """Reverse map broker product to OpenAlgo product"""
    reverse_mapping = {
        'CNC': 'CNC',
        'MIS': 'MIS', 
        'NRML': 'NRML'
    }
    return reverse_mapping.get(broker_product.upper(), broker_product.upper())

def map_exchange(exchange):
    """Map OpenAlgo exchange to broker exchange"""
    mapping = {
        'NSE': 'NSE',
        'BSE': 'BSE',
        'NFO': 'NFO',    # NSE F&O
        'BFO': 'BFO',    # BSE F&O
        'CDS': 'CDS',    # Currency
        'MCX': 'MCX'     # Commodity
    }
    return mapping.get(exchange.upper(), exchange.upper())
```

### Step 6: Implement Order Data Mapping

Create `broker/{broker_name}/mapping/order_data.py`:

```python
from datetime import datetime

def map_order_data(order_data):
    """
    Map broker order data to OpenAlgo standard format
    
    Args:
        order_data: Raw order data from broker
        
    Returns:
        dict: OpenAlgo standard order data
    """
    return {
        'orderid': str(order_data.get('order_id', '')),
        'symbol': order_data.get('symbol', ''),
        'exchange': order_data.get('exchange', ''),
        'action': order_data.get('side', ''),
        'quantity': int(order_data.get('quantity', 0)),
        'price': float(order_data.get('price', 0)),
        'product': order_data.get('product', ''),
        'status': map_order_status(order_data.get('status', '')),
        'timestamp': order_data.get('order_timestamp', ''),
        'filled_quantity': int(order_data.get('filled_quantity', 0)),
        'pending_quantity': int(order_data.get('pending_quantity', 0)),
        'average_price': float(order_data.get('average_price', 0))
    }

def map_trade_data(trade_data):
    """Map broker trade data to OpenAlgo format"""
    return {
        'tradeid': str(trade_data.get('trade_id', '')),
        'orderid': str(trade_data.get('order_id', '')),
        'symbol': trade_data.get('symbol', ''),
        'exchange': trade_data.get('exchange', ''),
        'action': trade_data.get('side', ''),
        'quantity': int(trade_data.get('quantity', 0)),
        'price': float(trade_data.get('price', 0)),
        'product': trade_data.get('product', ''),
        'timestamp': trade_data.get('trade_timestamp', '')
    }

def map_position_data(position_data):
    """Map broker position data to OpenAlgo format"""
    return {
        'symbol': position_data.get('symbol', ''),
        'exchange': position_data.get('exchange', ''),
        'quantity': int(position_data.get('net_quantity', 0)),
        'product': position_data.get('product', ''),
        'average_price': float(position_data.get('average_price', 0)),
        'pnl': float(position_data.get('unrealized_pnl', 0)),
        'day_change': float(position_data.get('day_change', 0))
    }

def map_order_status(broker_status):
    """Map broker order status to OpenAlgo status"""
    status_mapping = {
        'PENDING': 'PENDING',
        'OPEN': 'OPEN',
        'COMPLETE': 'COMPLETE',
        'CANCELLED': 'CANCELLED',
        'REJECTED': 'REJECTED',
        'EXECUTED': 'COMPLETE',
        'FILLED': 'COMPLETE'
    }
    return status_mapping.get(broker_status.upper(), broker_status.upper())

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
        transformed_position = map_position_data(position)
        transformed_positions.append(transformed_position)
        
    return transformed_positions

def calculate_order_statistics(orders):
    """Calculate order statistics"""
    total_orders = len(orders)
    completed_orders = len([o for o in orders if o.get('status') == 'COMPLETE'])
    pending_orders = len([o for o in orders if o.get('status') in ['PENDING', 'OPEN']])
    
    return {
        'total_orders': total_orders,
        'completed_orders': completed_orders,
        'pending_orders': pending_orders
    }

def map_portfolio_data(holdings_data):
    """Map holdings data to portfolio format"""
    portfolio = []
    
    if not holdings_data:
        return portfolio
        
    for holding in holdings_data:
        portfolio_item = {
            'symbol': holding.get('symbol', ''),
            'exchange': holding.get('exchange', ''),
            'quantity': int(holding.get('quantity', 0)),
            'average_price': float(holding.get('average_price', 0)),
            'current_price': float(holding.get('last_price', 0)),
            'pnl': float(holding.get('pnl', 0)),
            'day_change': float(holding.get('day_change', 0)),
            'day_change_percent': float(holding.get('day_change_percent', 0))
        }
        portfolio.append(portfolio_item)
        
    return portfolio

def calculate_portfolio_statistics(portfolio):
    """Calculate portfolio statistics"""
    total_value = sum(p.get('current_price', 0) * p.get('quantity', 0) for p in portfolio)
    total_pnl = sum(p.get('pnl', 0) for p in portfolio)
    total_day_change = sum(p.get('day_change', 0) for p in portfolio)
    
    return {
        'total_value': total_value,
        'total_pnl': total_pnl,
        'total_day_change': total_day_change
    }

def transform_holdings_data(raw_holdings):
    """Transform raw holdings to OpenAlgo format"""
    return map_portfolio_data(raw_holdings)
```

### Step 7: Implement Data API (Optional)

Create `broker/{broker_name}/api/data.py` if the broker supports market data:

```python
import json
from utils.httpx_client import get_httpx_client
from utils.logging import get_logger

logger = get_logger(__name__)

def get_quotes(symbols, auth):
    """Get real-time quotes for symbols"""
    # Implementation for getting quotes
    pass

def get_market_depth(symbol, exchange, auth):
    """Get market depth for a symbol"""
    # Implementation for market depth
    pass

def get_historical_data(symbol, exchange, timeframe, start_date, end_date, auth):
    """Get historical data"""
    # Implementation for historical data
    pass
```

### Step 8: Implement Funds API (Optional)

Create `broker/{broker_name}/api/funds.py`:

```python
def get_margin_data(auth):
    """Get account margin/funds data"""
    # Implementation for getting margin/funds
    pass
```

### Step 9: Implement Master Contract Database

Create `broker/{broker_name}/database/master_contract_db.py`:

```python
import os
import pandas as pd
import json
from sqlalchemy import create_engine, Column, Integer, String, Float, Index
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from utils.httpx_client import get_httpx_client
from utils.logging import get_logger

logger = get_logger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_engine(DATABASE_URL)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

class SymToken(Base):
    __tablename__ = 'symtoken'
    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False, index=True)
    brsymbol = Column(String, nullable=False, index=True)
    name = Column(String)
    exchange = Column(String, index=True)
    brexchange = Column(String, index=True)
    token = Column(String, index=True)
    expiry = Column(String)
    strike = Column(Float)
    lotsize = Column(Integer)
    instrumenttype = Column(String)
    tick_size = Column(Float)
    
    __table_args__ = (Index('idx_symbol_exchange', 'symbol', 'exchange'),)

def download_master_contract(auth_token):
    """
    Download master contract from broker
    
    Args:
        auth_token: Authentication token
        
    Returns:
        bool: Success status
    """
    try:
        client = get_httpx_client()
        
        # URL to download master contract (varies by broker)
        url = "https://api.{broker}.com/instruments"
        
        headers = {
            'Authorization': f'Bearer {auth_token}',
            'Accept': 'application/json'
        }
        
        response = client.get(url, headers=headers)
        response.raise_for_status()
        
        # Parse response based on broker format (CSV, JSON, etc.)
        contracts_data = response.json()  # or response.text for CSV
        
        # Process and store contracts
        process_master_contract(contracts_data)
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to download master contract: {str(e)}")
        return False

def process_master_contract(contracts_data):
    """Process and store master contract data"""
    try:
        # Clear existing data
        db_session.query(SymToken).delete()
        
        # Process each contract
        for contract in contracts_data:
            symbol_entry = SymToken(
                symbol=contract.get('symbol', ''),
                brsymbol=contract.get('tradingsymbol', ''),
                name=contract.get('name', ''),
                exchange=map_exchange_to_openalgo(contract.get('exchange', '')),
                brexchange=contract.get('exchange', ''),
                token=str(contract.get('instrument_token', '')),
                expiry=contract.get('expiry', ''),
                strike=float(contract.get('strike', 0)),
                lotsize=int(contract.get('lot_size', 1)),
                instrumenttype=contract.get('instrument_type', ''),
                tick_size=float(contract.get('tick_size', 0.05))
            )
            db_session.add(symbol_entry)
            
        db_session.commit()
        logger.info("Master contract data updated successfully")
        
    except Exception as e:
        logger.error(f"Failed to process master contract: {str(e)}")
        db_session.rollback()

def map_exchange_to_openalgo(broker_exchange):
    """Map broker exchange to OpenAlgo exchange"""
    mapping = {
        'NSE': 'NSE',
        'BSE': 'BSE',
        'NFO': 'NFO',
        'BFO': 'BFO',
        'CDS': 'CDS',
        'MCX': 'MCX'
    }
    return mapping.get(broker_exchange, broker_exchange)
```

### Step 10: Update Environment Configuration

**Current Reality**: Each user needs their own instance with their own API keys:

```properties
VALID_BROKERS = 'alpaca,fivepaisa,fivepaisaxts,aliceblue,angel,compositedge,dhan,dhan_sandbox,firstock,flattrade,fyers,groww,ibulls,iifl,indmoney,kotak,paytm,pocketful,shoonya,tradejini,upstox,wisdom,zebu,zerodha'

# Set YOUR personal broker API credentials (not shareable)
BROKER_API_KEY = 'YOUR_PERSONAL_{BROKER_NAME}_API_KEY'
BROKER_API_SECRET = 'YOUR_PERSONAL_{BROKER_NAME}_API_SECRET'
```

**For Multiple Users**, each needs their own instance:

```bash
# User A's Instance
mkdir openalgo-user-a
cd openalgo-user-a
# Copy OpenAlgo files
# Edit .env with User A's API keys
FLASK_PORT=5000 python app.py

# User B's Instance  
mkdir openalgo-user-b
cd openalgo-user-b
# Copy OpenAlgo files
# Edit .env with User B's API keys
FLASK_PORT=5001 python app.py
```

### Step 11: Add Broker Login Flow

Add broker-specific login handling in `blueprints/brlogin.py`:

```python
# Add this in the broker_callback function

elif broker == '{broker_name}':
    if request.method == 'GET':
        return render_template('{broker_name}.html')
    
    elif request.method == 'POST':
        # Extract form data based on broker requirements
        userid = request.form.get('userid')
        password = request.form.get('password')
        totp = request.form.get('totp')  # if required
        
        # Authenticate with broker
        auth_token, error_message = auth_function(userid, password, totp)
        
        if auth_token:
            return handle_auth_success(auth_token, session['user'], broker)
        else:
            return render_template('{broker_name}.html', error=error_message)
```

### Step 12: Create Login Template

Create `templates/{broker_name}.html`:

```html
{% extends "layout.html" %}

{% block title %}{Broker Name} Authentication - OpenAlgo{% endblock %}

{% block content %}
<div class="min-h-[calc(100vh-8rem)] flex items-center justify-center py-8">
    <div class="container mx-auto px-4">
        <div class="flex flex-col lg:flex-row items-center justify-between gap-8 lg:gap-16">
            <div class="card flex-shrink-0 w-full max-w-md shadow-2xl bg-base-100">
                <div class="card-body">
                    <div class="flex justify-center mb-6">
                        <img class="h-20 w-auto" src="{{ url_for('static', filename='favicon/apple-touch-icon.png') }}" alt="OpenAlgo">
                    </div>

                    <form action="/{broker_name}/callback" method="POST" class="space-y-4">
                        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                        
                        <div class="form-control">
                            <label class="label">
                                <span class="label-text">User ID</span>
                            </label>
                            <input type="text" 
                                   id="userid" 
                                   name="userid" 
                                   required 
                                   class="input input-bordered" 
                                   placeholder="Enter your {Broker Name} User ID" />
                        </div>

                        <div class="form-control">
                            <label class="label">
                                <span class="label-text">Password</span>
                            </label>
                            <input type="password" 
                                   id="password" 
                                   name="password" 
                                   required 
                                   class="input input-bordered" 
                                   placeholder="Enter your password" />
                        </div>

                        <!-- Add TOTP field if broker requires it -->
                        <div class="form-control">
                            <label class="label">
                                <span class="label-text">TOTP (Optional)</span>
                            </label>
                            <input type="text" 
                                   id="totp" 
                                   name="totp" 
                                   class="input input-bordered" 
                                   placeholder="Enter TOTP if required" />
                        </div>

                        {% if error %}
                        <div class="alert alert-error">
                            <span>{{ error }}</span>
                        </div>
                        {% endif %}

                        <div class="form-control mt-6">
                            <button type="submit" class="btn btn-primary w-full">
                                Connect to {Broker Name}
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

### Step 13: Implement WebSocket Support (Optional)

If the broker supports WebSocket feeds, create the streaming components:

Create `broker/{broker_name}/streaming/{broker_name}_adapter.py`:

```python
import threading
import json
import time
from typing import Dict, Any, Optional

from database.auth_db import get_auth_token, get_feed_token
from database.token_db import get_token

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from websocket_proxy.base_adapter import BaseBrokerWebSocketAdapter
from websocket_proxy.mapping import SymbolMapper
from .{broker_name}_mapping import {BrokerName}ExchangeMapper, {BrokerName}CapabilityRegistry

class {BrokerName}WebSocketAdapter(BaseBrokerWebSocketAdapter):
    """{Broker Name}-specific implementation of the WebSocket adapter"""
    
    def __init__(self):
        super().__init__()
        self.broker_name = "{broker_name}"
        self.ws_client = None
        self.auth_token = None
        self.feed_token = None

    def initialize(self, broker_name: str, user_id: str, **kwargs):
        """Initialize the adapter with broker-specific settings"""
        self.user_id = user_id
        self.broker_name = broker_name
        
        # Get authentication tokens
        self.auth_token = get_auth_token(user_id)
        self.feed_token = get_feed_token(user_id)  # if separate feed token needed
        
        if not self.auth_token:
            return {"status": "error", "message": "Authentication token not found"}
            
        # Initialize WebSocket client
        # Implementation depends on broker's WebSocket library
        
        return {"status": "success", "message": f"{self.broker_name} adapter initialized"}

    def connect(self):
        """Establish WebSocket connection"""
        try:
            # Implement broker-specific connection logic
            pass
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")

    def disconnect(self):
        """Disconnect from WebSocket"""
        try:
            if self.ws_client:
                # Implement disconnect logic
                pass
        except Exception as e:
            self.logger.error(f"Disconnect failed: {e}")

    def subscribe(self, symbol: str, exchange: str, mode: int = 2, depth_level: int = 5):
        """Subscribe to market data"""
        try:
            # Get token for symbol
            token_info = SymbolMapper.get_token_from_symbol(symbol, exchange)
            if not token_info:
                return self._create_error_response("SYMBOL_NOT_FOUND", 
                                                  f"Symbol {symbol} not found")
            
            # Implement subscription logic
            # Store subscription for reconnection
            correlation_id = f"{symbol}_{exchange}_{mode}"
            self.subscriptions[correlation_id] = {
                'symbol': symbol,
                'exchange': exchange,
                'token': token_info['token'],
                'mode': mode
            }
            
            return {
                'status': 'success',
                'symbol': symbol,
                'exchange': exchange,
                'mode': mode,
                'message': 'Subscription successful'
            }
            
        except Exception as e:
            self.logger.error(f"Subscription failed: {e}")
            return self._create_error_response("SUBSCRIPTION_FAILED", str(e))

    def unsubscribe(self, symbol: str, exchange: str, mode: int = 2):
        """Unsubscribe from market data"""
        # Implement unsubscription logic
        pass

    def on_message(self, message):
        """Handle incoming WebSocket messages"""
        try:
            # Parse and process message
            # Transform to OpenAlgo format
            # Publish to ZeroMQ
            pass
        except Exception as e:
            self.logger.error(f"Message processing failed: {e}")

    def on_open(self):
        """Handle WebSocket connection open"""
        self.connected = True
        self.logger.info("WebSocket connection established")

    def on_close(self):
        """Handle WebSocket connection close"""
        self.connected = False
        self.logger.info("WebSocket connection closed")

    def on_error(self, error):
        """Handle WebSocket errors"""
        self.logger.error(f"WebSocket error: {error}")
```

## Testing and Validation

### Step 1: Unit Testing

Create test cases for each component:

```python
# tests/test_{broker_name}_integration.py

import unittest
from broker.{broker_name}.api.auth_api import authenticate_broker
from broker.{broker_name}.api.order_api import place_order_api, get_order_book

class Test{BrokerName}Integration(unittest.TestCase):
    
    def setUp(self):
        self.test_auth_token = "test_token"
        
    def test_authentication(self):
        # Test authentication flow
        pass
        
    def test_place_order(self):
        # Test order placement
        pass
        
    def test_get_order_book(self):
        # Test order book retrieval
        pass

if __name__ == '__main__':
    unittest.main()
```

### Step 2: Integration Testing

1. Test authentication flow
2. Test order placement and cancellation
3. Test data retrieval (orders, trades, positions)
4. Test WebSocket connectivity (if implemented)
5. Test error handling

### Step 3: Manual Testing Checklist

- [ ] Broker authentication works correctly
- [ ] Orders can be placed successfully
- [ ] Orders can be cancelled/modified
- [ ] Order book displays correctly
- [ ] Trade book displays correctly
- [ ] Positions are shown accurately
- [ ] Error messages are user-friendly
- [ ] WebSocket data feeds work (if implemented)

## Best Practices

### Code Quality

1. **Follow OpenAlgo Patterns**: Study existing brokers for consistency
2. **Error Handling**: Implement comprehensive error handling
3. **Logging**: Use proper logging for debugging
4. **Documentation**: Document all functions and classes
5. **Type Hints**: Use Python type hints where applicable

### Security

1. **Token Management**: Never log or expose authentication tokens
2. **Input Validation**: Validate all user inputs
3. **Rate Limiting**: Respect broker API rate limits
4. **Environment Variables**: Store sensitive data in environment variables

### Performance

1. **Connection Pooling**: Use httpx client with connection pooling
2. **Caching**: Cache frequently accessed data when appropriate
3. **Async Operations**: Use async operations where beneficial
4. **Resource Cleanup**: Properly close connections and clean up resources

### Testing

1. **Use Sandbox**: Always test with broker's sandbox environment first
2. **Mock External Calls**: Mock broker API calls in unit tests
3. **Edge Cases**: Test edge cases and error scenarios
4. **Load Testing**: Test with multiple concurrent requests

## Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Check API credentials
   - Verify authentication flow
   - Check token expiry handling

2. **Order Placement Issues**
   - Verify data transformation
   - Check required fields mapping
   - Validate symbol/exchange mapping

3. **Data Mapping Errors**
   - Check field name mappings
   - Verify data type conversions
   - Handle null/missing values

4. **WebSocket Issues**
   - Check connection stability
   - Verify authentication for WebSocket
   - Handle reconnection scenarios

### Debugging Tips

1. **Enable Debug Logging**:
   ```python
   import logging
   logging.getLogger().setLevel(logging.DEBUG)
   ```

2. **Use API Testing Tools**: Test broker APIs directly with Postman/curl

3. **Check Network Connectivity**: Ensure proper network access to broker APIs

4. **Monitor Rate Limits**: Track API usage to avoid rate limiting

5. **Validate Responses**: Always validate broker API responses

### Support and Resources

1. **OpenAlgo Documentation**: https://openalgo.in/docs
2. **Broker API Documentation**: Refer to specific broker's API docs
3. **Community Support**: OpenAlgo community forums
4. **Issue Tracking**: GitHub issues for bugs and feature requests

---

## Conclusion

Following this guide will help you successfully integrate a new broker into OpenAlgo. The modular architecture ensures that each broker integration is self-contained and follows consistent patterns. 

Remember to:
- Test thoroughly in sandbox environment
- Follow security best practices
- Maintain code quality standards
- Document your implementation
- Submit pull requests for community benefit

For additional support, refer to existing broker implementations in the OpenAlgo codebase and engage with the community for guidance.
