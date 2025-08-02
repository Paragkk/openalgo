import os
from sqlalchemy import create_engine, Column, Integer, String, Float, Index
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from utils.httpx_client import get_httpx_client
from utils.logging import get_logger
from extensions import socketio  # Import SocketIO

logger = get_logger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///db/openalgo.db')
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
    Download master contract from Alpaca
    
    Note: Alpaca doesn't provide a traditional master contract file like Indian brokers.
    Instead, we can get a list of active assets.
    
    Args:
        auth_token: Authentication token
        
    Returns:
        bool: Success status
    """
    try:
        client = get_httpx_client()
        BROKER_API_SECRET = os.getenv('BROKER_API_SECRET')
        
        if not BROKER_API_SECRET:
            logger.error("BROKER_API_SECRET environment variable is not set")
            return False
        
        # URL to get all assets from Alpaca
        url = "https://paper-api.alpaca.markets/v2/assets"
        
        headers = {
            'APCA-API-KEY-ID': auth_token,
            'APCA-API-SECRET-KEY': BROKER_API_SECRET,
            'Accept': 'application/json'
        }
        
        # Get active stocks
        params = {
            'status': 'active',
            'asset_class': 'us_equity'
        }
        
        logger.info("Requesting assets from Alpaca API...")
        response = client.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        assets_data = response.json()
        
        if not assets_data or len(assets_data) == 0:
            logger.error("No assets received from Alpaca API")
            return False
        
        logger.info(f"Received {len(assets_data)} assets from Alpaca API")
        
        # Process and store contracts
        process_master_contract(assets_data)
        
        # Verify that data was actually stored
        stored_count = get_contract_count()
        if stored_count == 0:
            logger.error("No contracts were stored in database after processing")
            return False
        
        logger.info(f"Successfully stored {stored_count} assets from Alpaca")
        return True
        
    except Exception as e:
        logger.error(f"Failed to download master contract from Alpaca: {str(e)}")
        return False

def process_master_contract(assets_data):
    """Process and store Alpaca assets data"""
    try:
        if not assets_data:
            raise ValueError("No assets data provided")
        
        logger.info(f"Processing {len(assets_data)} assets from Alpaca")
        
        # Clear existing Alpaca data (you might want to be more selective)
        deleted_count = db_session.query(SymToken).filter(SymToken.brexchange.in_(['NASDAQ', 'NYSE', 'AMEX'])).count()
        db_session.query(SymToken).filter(SymToken.brexchange.in_(['NASDAQ', 'NYSE', 'AMEX'])).delete(synchronize_session=False)
        logger.info(f"Cleared {deleted_count} existing Alpaca assets from database")
        
        processed_count = 0
        skipped_count = 0
        
        # Process each asset
        for asset in assets_data:
            if not asset.get('tradable', False):
                skipped_count += 1
                continue  # Skip non-tradable assets
            
            symbol = asset.get('symbol', '')
            if not symbol:
                skipped_count += 1
                continue  # Skip assets without symbol
                
            name = asset.get('name', '')
            exchange = map_alpaca_exchange(asset.get('exchange', 'NASDAQ'))
            
            symbol_entry = SymToken(
                symbol=symbol,
                brsymbol=symbol,  # Alpaca uses same symbol
                name=name,
                exchange=exchange,
                brexchange=asset.get('exchange', 'NASDAQ'),
                token=asset.get('id', ''),  # Use asset ID as token
                expiry='',  # No expiry for stocks
                strike=0.0,  # No strike for stocks
                lotsize=1,  # Stocks have lot size of 1
                instrumenttype='EQ',  # Equity
                tick_size=0.01  # US stocks typically have $0.01 tick size
            )
            
            db_session.add(symbol_entry)
            processed_count += 1
        
        if processed_count == 0:
            raise ValueError("No tradable assets found to process")
        
        db_session.commit()
        logger.info(f"Alpaca master contract data updated successfully: {processed_count} assets processed, {skipped_count} skipped")
        
    except Exception as e:
        logger.error(f"Failed to process Alpaca master contract: {str(e)}")
        db_session.rollback()
        raise

def map_alpaca_exchange(alpaca_exchange):
    """Map Alpaca exchange to OpenAlgo exchange format"""
    mapping = {
        'NASDAQ': 'NASDAQ',
        'NYSE': 'NYSE', 
        'AMEX': 'AMEX',
        'ARCA': 'NYSE',  # NYSE Arca
        'BATS': 'NASDAQ',  # Map BATS to NASDAQ
        'IEX': 'NASDAQ'  # Map IEX to NASDAQ
    }
    return mapping.get(alpaca_exchange, 'NASDAQ')

def get_symbol_info(symbol, exchange='NASDAQ'):
    """Get symbol information from the database"""
    try:
        symbol_info = db_session.query(SymToken).filter(
            SymToken.symbol == symbol,
            SymToken.exchange == exchange
        ).first()
        
        if symbol_info:
            return {
                'symbol': symbol_info.symbol,
                'brsymbol': symbol_info.brsymbol,
                'name': symbol_info.name,
                'exchange': symbol_info.exchange,
                'brexchange': symbol_info.brexchange,
                'token': symbol_info.token,
                'lotsize': symbol_info.lotsize,
                'instrumenttype': symbol_info.instrumenttype,
                'tick_size': symbol_info.tick_size
            }
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to get symbol info: {str(e)}")
        return None

def search_symbols(query, limit=20):
    """Search for symbols in the database"""
    try:
        symbols = db_session.query(SymToken).filter(
            SymToken.symbol.like(f'%{query.upper()}%') |
            SymToken.name.like(f'%{query.upper()}%')
        ).limit(limit).all()
        
        results = []
        for symbol in symbols:
            results.append({
                'symbol': symbol.symbol,
                'name': symbol.name,
                'exchange': symbol.exchange,
                'instrumenttype': symbol.instrumenttype
            })
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to search symbols: {str(e)}")
        return []

def update_contract_status(symbol, exchange, status):
    """Update contract status (active/inactive)"""
    try:
        symbol_entry = db_session.query(SymToken).filter(
            SymToken.symbol == symbol,
            SymToken.exchange == exchange
        ).first()
        
        if symbol_entry:
            # You could add a status field to track active/inactive
            # For now, we'll just log the status change
            logger.info(f"Contract status updated: {symbol} on {exchange} - {status}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Failed to update contract status: {str(e)}")
        return False

def get_contract_count():
    """Get total number of contracts in database"""
    try:
        count = db_session.query(SymToken).count()
        return count
        
    except Exception as e:
        logger.error(f"Failed to get contract count: {str(e)}")
        return 0

def cleanup_old_contracts(days=30):
    """Cleanup old or inactive contracts (if needed)"""
    try:
        # For Alpaca, we might not need this as much since US stocks don't expire
        # But you could implement logic to remove delisted stocks
        logger.info("Contract cleanup completed")
        return True
        
    except Exception as e:
        logger.error(f"Failed to cleanup contracts: {str(e)}")
        return False

def master_contract_download():
    """
    Download master contract for Alpaca and emit WebSocket event
    
    This function is called by the auth_utils module to download
    the master contract and emit the appropriate WebSocket events.
    """
    logger.info("Downloading Master Contract for Alpaca")
    
    try:
        # Get the most recent auth token for Alpaca from the database
        from database.auth_db import get_latest_auth_token_by_broker
        auth_token = get_latest_auth_token_by_broker('alpaca')
        
        if not auth_token:
            error_msg = "No authentication token found for Alpaca broker"
            logger.error(error_msg)
            socketio.emit('master_contract_download', {'status': 'error', 'message': error_msg})
            raise Exception(error_msg)
        
        # Download the master contract
        success = download_master_contract(auth_token)
        
        if success:
            # Verify that data was actually stored
            contract_count = get_contract_count()
            if contract_count > 0:
                success_msg = f"Successfully downloaded {contract_count} assets"
                logger.info(success_msg)
                socketio.emit('master_contract_download', {'status': 'success', 'message': success_msg})
                return {'status': 'success', 'message': success_msg}
            else:
                error_msg = "Download completed but no assets were stored"
                logger.error(error_msg)
                socketio.emit('master_contract_download', {'status': 'error', 'message': error_msg})
                raise Exception(error_msg)
        else:
            error_msg = "Failed to download master contract from Alpaca API"
            logger.error(error_msg)
            socketio.emit('master_contract_download', {'status': 'error', 'message': error_msg})
            raise Exception(error_msg)
            
    except Exception as e:
        error_msg = f"Error during master contract download: {str(e)}"
        logger.error(error_msg)
        socketio.emit('master_contract_download', {'status': 'error', 'message': error_msg})
        raise  # Re-raise the exception so auth_utils can catch it
