# Alpaca Broker Integration

## Overview

This directory contains the Alpaca Markets integration for OpenAlgo. Alpaca is a commission-free stock trading platform that provides access to US equity markets.

## Features

- **Paper Trading**: Uses Alpaca's paper trading environment for safe testing
- **US Stock Markets**: Access to NYSE, NASDAQ, and AMEX
- **Commission-Free Trading**: No commission fees on stock trades
- **Real-time Data**: Access to real-time market data
- **Advanced Order Types**: Support for market, limit, stop, and stop-limit orders

## Configuration

To use the Alpaca integration, you need to set up the following environment variables:

```bash
BROKER_API_KEY=your_alpaca_api_key
BROKER_API_SECRET=your_alpaca_secret_key
VALID_BROKERS=alpaca  # Add alpaca to your valid brokers list
```

## API Endpoints

The integration uses Alpaca's paper trading API:
- Base URL: `https://paper-api.alpaca.markets/v2`
- Market Data: `https://data.alpaca.markets/v2`

## File Structure

```
broker/alpaca/
├── api/
│   ├── auth_api.py          # Authentication with Alpaca
│   ├── order_api.py         # Order management
│   ├── data.py              # Market data APIs
│   └── funds.py             # Account/funds APIs
├── mapping/
│   ├── transform_data.py    # Data transformation utilities
│   └── order_data.py        # Order/position mapping
├── database/
│   └── master_contract_db.py # Asset/symbol management
├── streaming/               # WebSocket support (placeholder)
│   ├── alpaca_adapter.py
│   └── alpaca_mapping.py
└── plugin.json              # Plugin metadata
```

## Key Differences from Indian Brokers

1. **No Product Types**: Alpaca doesn't use product types like CNC/MIS/NRML
2. **Symbol Format**: Uses direct symbols (e.g., 'AAPL', 'GOOGL') instead of tokens
3. **Exchange Mapping**: Maps Indian exchanges (NSE/BSE) to US exchanges (NASDAQ/NYSE)
4. **Currency**: All transactions in USD
5. **Market Hours**: US market hours (9:30 AM - 4:00 PM ET)

## Authentication Flow

1. API keys are configured in environment variables
2. No separate login required - uses API key authentication
3. Simple validation by making a test API call to get account info

## Order Types Supported

- **Market**: Execute immediately at current market price
- **Limit**: Execute at specified price or better
- **Stop**: Stop-loss orders
- **Stop Limit**: Stop order that becomes limit order when triggered

## Limitations

- Paper trading only (can be changed to live trading by updating URLs)
- US stocks only (no options, crypto, or other asset classes in this implementation)
- WebSocket streaming not implemented (placeholder structure provided)

## Testing

Test the integration using the Alpaca paper trading environment:

1. Sign up for Alpaca paper trading account
2. Get API keys from Alpaca dashboard
3. Configure environment variables
4. Use the OpenAlgo interface to connect to Alpaca

## Future Enhancements

- WebSocket streaming implementation for real-time data
- Options trading support
- Crypto trading support
- Live trading environment support
- Extended hours trading optimization
