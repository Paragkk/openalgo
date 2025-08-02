"""
Alpaca API Diagnostic Tool
=========================

This tool helps diagnose issues with Alpaca API responses by:
1. Testing API connectivity
2. Examining actual response structures
3. Identifying available fields in orders/trades
4. Testing the mapping functions with real data

Usage:
    python broker/alpaca/diagnostic_tool.py

Requirements:
    - Set BROKER_API_KEY and BROKER_API_SECRET environment variables
    - Ensure OpenAlgo project structure is available
"""

import os
import sys
import json
from datetime import datetime

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from broker.alpaca.api.order_api import get_api_response, get_trade_book
from broker.alpaca.mapping.order_data import map_single_trade, transform_tradebook_data

def print_header(title):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def print_section(title):
    """Print a formatted section header"""
    print(f"\n--- {title} ---")

def check_environment():
    """Check if required environment variables are set"""
    print_header("ENVIRONMENT CHECK")
    
    required_vars = ['BROKER_API_KEY', 'BROKER_API_SECRET']
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing_vars.append(var)
            print(f"❌ {var}: NOT SET")
        else:
            # Show only first 8 characters for security
            masked_value = value[:8] + "..." if len(value) > 8 else value
            print(f"✅ {var}: {masked_value}")
    
    if missing_vars:
        print(f"\n⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these variables before running the diagnostic:")
        print("set BROKER_API_KEY=your_alpaca_api_key")
        print("set BROKER_API_SECRET=your_alpaca_secret_key")
        return False
    
    print("\n✅ All required environment variables are set")
    return True

def test_api_connectivity(auth_token):
    """Test basic API connectivity"""
    print_header("API CONNECTIVITY TEST")
    
    try:
        # Test account endpoint
        print_section("Testing Account Endpoint")
        account_response = get_api_response("/account", auth_token)
        
        if isinstance(account_response, dict) and 'error' in account_response:
            print(f"❌ Account API Error: {account_response['error']}")
            return False
        else:
            print("✅ Account API: Connected successfully")
            print(f"   Account Status: {account_response.get('status', 'N/A')}")
            print(f"   Buying Power: ${account_response.get('buying_power', 'N/A')}")
        
        # Test orders endpoint
        print_section("Testing Orders Endpoint")
        orders_response = get_api_response("/orders", auth_token)
        
        if isinstance(orders_response, dict) and 'error' in orders_response:
            print(f"❌ Orders API Error: {orders_response['error']}")
            return False
        else:
            print("✅ Orders API: Connected successfully")
            print(f"   Total Orders: {len(orders_response) if isinstance(orders_response, list) else 'N/A'}")
        
        return True
        
    except Exception as e:
        print(f"❌ API Connectivity Error: {str(e)}")
        return False

def analyze_orders_structure(auth_token):
    """Analyze the structure of orders returned by Alpaca API"""
    print_header("ORDERS STRUCTURE ANALYSIS")
    
    try:
        # Get all orders
        print_section("All Orders")
        all_orders = get_api_response("/orders", auth_token)
        
        if isinstance(all_orders, dict) and 'error' in all_orders:
            print(f"❌ Error getting orders: {all_orders['error']}")
            return
        
        if not isinstance(all_orders, list):
            print(f"❌ Unexpected response type: {type(all_orders)}")
            return
        
        print(f"📊 Total orders found: {len(all_orders)}")
        
        if not all_orders:
            print("ℹ️  No orders found in account")
            return
        
        # Analyze first order structure
        print_section("Sample Order Structure")
        sample_order = all_orders[0]
        print("Available fields in order:")
        for key, value in sample_order.items():
            value_type = type(value).__name__
            value_str = str(value)[:50] + "..." if len(str(value)) > 50 else str(value)
            print(f"  {key}: {value_str} ({value_type})")
        
        # Analyze orders by status
        print_section("Orders by Status")
        status_counts = {}
        filled_orders = []
        
        for order in all_orders:
            status = order.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
            
            if status in ['filled', 'partially_filled']:
                filled_orders.append(order)
        
        for status, count in status_counts.items():
            print(f"  {status}: {count} orders")
        
        # Analyze filled orders specifically
        if filled_orders:
            print_section("Filled Orders Analysis")
            print(f"📊 Found {len(filled_orders)} filled/partially filled orders")
            
            sample_filled = filled_orders[0]
            print("\nSample filled order details:")
            important_fields = [
                'id', 'symbol', 'side', 'status', 'qty', 'filled_qty', 
                'filled_avg_price', 'type', 'created_at', 'filled_at', 
                'updated_at', 'price', 'limit_price', 'stop_price'
            ]
            
            for field in important_fields:
                value = sample_filled.get(field)
                print(f"  {field}: {value}")
            
            # Test mapping on real data
            print_section("Testing Mapping Function")
            mapped_trade = map_single_trade(sample_filled)
            print("Mapped trade result:")
            print(f"  Symbol: {mapped_trade['symbol']}")
            print(f"  Action: {mapped_trade['action']}")
            print(f"  Quantity: {mapped_trade['quantity']}")
            print(f"  Average Price: {mapped_trade['average_price']}")
            print(f"  Trade Value: {mapped_trade['trade_value']}")
            print(f"  Order ID: {mapped_trade['orderid']}")
            print(f"  Timestamp: {mapped_trade['timestamp']}")
            
        else:
            print("ℹ️  No filled orders found")
        
        # Get specifically filled orders
        print_section("Filled Orders Endpoint")
        filled_response = get_api_response("/orders?status=filled", auth_token)
        
        if isinstance(filled_response, list):
            print(f"📊 Orders with status=filled: {len(filled_response)}")
        else:
            print(f"❌ Unexpected response from filled orders endpoint: {type(filled_response)}")
        
    except Exception as e:
        print(f"❌ Error analyzing orders: {str(e)}")

def test_tradebook_pipeline(auth_token):
    """Test the complete tradebook data pipeline"""
    print_header("TRADEBOOK PIPELINE TEST")
    
    try:
        print_section("Step 1: Raw API Response")
        raw_trades = get_trade_book(auth_token)
        print(f"Raw trades count: {len(raw_trades) if isinstance(raw_trades, list) else 'Not a list'}")
        
        if raw_trades and isinstance(raw_trades, list):
            print(f"Sample raw trade: {json.dumps(raw_trades[0], indent=2, default=str)}")
        
        print_section("Step 2: Transform Pipeline")
        transformed_trades = transform_tradebook_data(raw_trades)
        print(f"Transformed trades count: {len(transformed_trades)}")
        
        if transformed_trades:
            print("Sample transformed trade:")
            sample = transformed_trades[0]
            for key, value in sample.items():
                print(f"  {key}: {value}")
        else:
            print("ℹ️  No trades after transformation")
        
    except Exception as e:
        print(f"❌ Error testing tradebook pipeline: {str(e)}")

def generate_sample_data():
    """Generate sample data for testing when no real data exists"""
    print_header("SAMPLE DATA GENERATION")
    
    print("Generating sample Alpaca order data for testing...")
    
    sample_orders = [
        {
            "id": "12345678-1234-1234-1234-123456789012",
            "symbol": "AAPL",
            "side": "buy",
            "status": "filled",
            "qty": "10",
            "filled_qty": "10",
            "filled_avg_price": "150.25",
            "type": "market",
            "created_at": "2023-01-01T10:00:00Z",
            "filled_at": "2023-01-01T10:01:30Z",
            "updated_at": "2023-01-01T10:01:30Z"
        },
        {
            "id": "87654321-4321-4321-4321-210987654321",
            "symbol": "GOOGL",
            "side": "sell",
            "status": "filled",
            "qty": "5",
            "filled_qty": "5",
            "filled_avg_price": "2750.50",
            "type": "limit",
            "limit_price": "2750.00",
            "created_at": "2023-01-01T11:00:00Z",
            "filled_at": "2023-01-01T11:05:15Z",
            "updated_at": "2023-01-01T11:05:15Z"
        }
    ]
    
    print_section("Testing Mapping with Sample Data")
    for i, order in enumerate(sample_orders, 1):
        print(f"\nSample Order {i}:")
        mapped = map_single_trade(order)
        print(f"  Symbol: {mapped['symbol']}")
        print(f"  Action: {mapped['action']}")
        print(f"  Quantity: {mapped['quantity']}")
        print(f"  Price: {mapped['average_price']}")
        print(f"  Value: {mapped['trade_value']}")
        print(f"  Order ID: {mapped['orderid']}")
        print(f"  Timestamp: {mapped['timestamp']}")
    
    print_section("Testing Transform Pipeline with Sample Data")
    transformed = transform_tradebook_data(sample_orders)
    print(f"Transformed {len(transformed)} sample trades")
    
    if transformed:
        print("\nSample transformed trade:")
        for key, value in transformed[0].items():
            print(f"  {key}: {value}")

def main():
    """Main diagnostic function"""
    print_header("ALPACA API DIAGNOSTIC TOOL")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check environment
    if not check_environment():
        return
    
    # Get auth token
    auth_token = os.getenv('BROKER_API_KEY')
    
    # Test API connectivity
    if not test_api_connectivity(auth_token):
        print("\n❌ Cannot proceed with API connectivity issues")
        return
    
    # Analyze order structures
    analyze_orders_structure(auth_token)
    
    # Test tradebook pipeline
    test_tradebook_pipeline(auth_token)
    
    # Generate sample data for comparison
    generate_sample_data()
    
    print_header("DIAGNOSTIC COMPLETE")
    print("If you're still seeing null values in the dashboard:")
    print("1. Check if there are actual filled orders in your Alpaca account")
    print("2. Compare the real API response structure with the expected fields")
    print("3. Place a test market order to generate real trade data")
    print("4. Check the application logs for any errors during data processing")

if __name__ == "__main__":
    main()
