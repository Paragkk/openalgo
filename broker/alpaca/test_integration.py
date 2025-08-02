#!/usr/bin/env python3
"""
Alpaca Integration Test Script
Tests basic functionality of the Alpaca broker integration
"""

import os
import sys
import json

# Add the OpenAlgo root directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def test_alpaca_auth():
    """Test Alpaca authentication"""
    print("Testing Alpaca Authentication...")
    
    try:
        from broker.alpaca.api.auth_api import authenticate_broker
        
        # Test authentication
        auth_token, error = authenticate_broker()
        
        if auth_token:
            print(f"✓ Authentication successful")
            print(f"  Auth token: {auth_token[:10]}...")
            return auth_token
        else:
            print(f"✗ Authentication failed: {error}")
            return None
            
    except Exception as e:
        print(f"✗ Authentication test error: {str(e)}")
        return None

def test_account_info(auth_token):
    """Test getting account information"""
    print("\nTesting Account Information...")
    
    try:
        from broker.alpaca.api.auth_api import get_account_info
        
        account_info = get_account_info(auth_token)
        
        if 'error' not in account_info:
            print("✓ Account info retrieved successfully")
            print(f"  Account ID: {account_info.get('id', 'N/A')}")
            print(f"  Status: {account_info.get('status', 'N/A')}")
            print(f"  Currency: {account_info.get('currency', 'N/A')}")
            return True
        else:
            print(f"✗ Account info failed: {account_info['error']}")
            return False
            
    except Exception as e:
        print(f"✗ Account info test error: {str(e)}")
        return False

def test_data_transformation():
    """Test data transformation functions"""
    print("\nTesting Data Transformation...")
    
    try:
        from broker.alpaca.mapping.transform_data import transform_data
        
        # Test OpenAlgo to Alpaca transformation
        openalgo_order = {
            'symbol': 'AAPL',
            'action': 'BUY',
            'quantity': '10',
            'pricetype': 'MARKET',
            'price': '0',
            'validity': 'DAY'
        }
        
        alpaca_order = transform_data(openalgo_order)
        
        expected_fields = ['symbol', 'side', 'type', 'qty', 'time_in_force']
        
        if all(field in alpaca_order for field in expected_fields):
            print("✓ Data transformation successful")
            print(f"  Original: {openalgo_order}")
            print(f"  Transformed: {alpaca_order}")
            return True
        else:
            print(f"✗ Data transformation missing fields")
            print(f"  Expected: {expected_fields}")
            print(f"  Got: {list(alpaca_order.keys())}")
            return False
            
    except Exception as e:
        print(f"✗ Data transformation test error: {str(e)}")
        return False

def test_order_mapping():
    """Test order data mapping"""
    print("\nTesting Order Data Mapping...")
    
    try:
        from broker.alpaca.mapping.order_data import map_order_data
        
        # Mock Alpaca order response
        alpaca_order = {
            'id': '12345678-1234-1234-1234-123456789012',
            'symbol': 'AAPL',
            'side': 'buy',
            'qty': '10',
            'status': 'filled',
            'type': 'market',
            'created_at': '2023-01-01T10:00:00Z',
            'filled_qty': '10',
            'filled_avg_price': '150.00'
        }
        
        openalgo_order = map_order_data(alpaca_order)
        
        expected_fields = ['orderid', 'symbol', 'exchange', 'action', 'quantity', 'status']
        
        if all(field in openalgo_order for field in expected_fields):
            print("✓ Order mapping successful")
            print(f"  Alpaca order: {alpaca_order['id'][:8]}...")
            print(f"  OpenAlgo format: {openalgo_order['orderid'][:8]}...")
            return True
        else:
            print(f"✗ Order mapping missing fields")
            return False
            
    except Exception as e:
        print(f"✗ Order mapping test error: {str(e)}")
        return False

def test_trade_mapping():
    """Test trade data mapping"""
    print("\nTesting Trade Data Mapping...")
    
    try:
        from broker.alpaca.mapping.order_data import map_trade_data
        
        # Mock Alpaca filled order response (representing a trade)
        alpaca_trade = {
            'id': '12345678-1234-1234-1234-123456789012',
            'symbol': 'AAPL',
            'side': 'buy',
            'qty': '100',
            'status': 'filled',
            'type': 'market',
            'created_at': '2023-01-01T10:00:00Z',
            'filled_at': '2023-01-01T10:01:30Z',
            'filled_qty': '100',
            'filled_avg_price': '150.25'
        }
        
        openalgo_trade = map_trade_data(alpaca_trade)
        
        expected_fields = ['tradeid', 'orderid', 'symbol', 'exchange', 'action', 'quantity', 'average_price', 'trade_value']
        
        if isinstance(openalgo_trade, list):
            # Should return empty list if no valid trades
            if not openalgo_trade:
                print("✗ Trade mapping returned empty list for valid trade")
                return False
            openalgo_trade = openalgo_trade[0] if openalgo_trade else {}
        
        if all(field in openalgo_trade for field in expected_fields):
            print("✓ Trade mapping successful")
            print(f"  Alpaca trade: {alpaca_trade['id'][:8]}...")
            print(f"  OpenAlgo format: {openalgo_trade['tradeid'][:8]}...")
            print(f"  Action: {openalgo_trade['action']}")
            print(f"  Quantity: {openalgo_trade['quantity']}")
            print(f"  Price: {openalgo_trade['average_price']}")
            print(f"  Value: {openalgo_trade['trade_value']}")
            return True
        else:
            print(f"✗ Trade mapping missing fields")
            missing = [f for f in expected_fields if f not in openalgo_trade]
            print(f"  Missing: {missing}")
            return False
            
    except Exception as e:
        print(f"✗ Trade mapping test error: {str(e)}")
        return False

def check_environment():
    """Check if required environment variables are set"""
    print("Checking Environment Configuration...")
    
    required_vars = ['BROKER_API_KEY', 'BROKER_API_SECRET']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"✗ Missing environment variables: {', '.join(missing_vars)}")
        print("  Please set these variables to test the integration:")
        print("  export BROKER_API_KEY='your_alpaca_api_key'")
        print("  export BROKER_API_SECRET='your_alpaca_secret_key'")
        return False
    else:
        print("✓ All required environment variables are set")
        return True

def main():
    """Run all tests"""
    print("="*50)
    print("Alpaca Integration Test Suite")
    print("="*50)
    
    # Check environment first
    env_ok = check_environment()
    if not env_ok:
        print("\n⚠️  Cannot run integration tests without proper environment setup")
        print("   However, unit tests can still be run...")
    
    # Run unit tests (don't require API keys)
    print("\n" + "="*30)
    print("UNIT TESTS")
    print("="*30)
    
    transform_ok = test_data_transformation()
    mapping_ok = test_order_mapping()
    trade_mapping_ok = test_trade_mapping()
    
    unit_tests_passed = transform_ok and mapping_ok and trade_mapping_ok
    
    # Run integration tests (require API keys)
    integration_tests_passed = True
    if env_ok:
        print("\n" + "="*30)
        print("INTEGRATION TESTS")
        print("="*30)
        
        auth_token = test_alpaca_auth()
        if auth_token:
            account_ok = test_account_info(auth_token)
            integration_tests_passed = account_ok
        else:
            integration_tests_passed = False
    
    # Summary
    print("\n" + "="*30)
    print("TEST SUMMARY")
    print("="*30)
    
    print(f"Unit Tests: {'✓ PASSED' if unit_tests_passed else '✗ FAILED'}")
    
    if env_ok:
        print(f"Integration Tests: {'✓ PASSED' if integration_tests_passed else '✗ FAILED'}")
    else:
        print("Integration Tests: ⚠️  SKIPPED (missing environment)")
    
    overall_status = unit_tests_passed and (integration_tests_passed if env_ok else True)
    print(f"\nOverall Status: {'✓ PASSED' if overall_status else '✗ FAILED'}")
    
    if overall_status:
        print("\n🎉 Alpaca integration is ready to use!")
    else:
        print("\n❌ Please fix the issues above before using the integration")

if __name__ == "__main__":
    main()
