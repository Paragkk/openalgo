"""
Common utilities for data conversion and validation.
Provides safe conversion functions to handle None, empty, and invalid values.
"""


def safe_float(value, default=0.0):
    """
    Safely convert value to float, handling None and invalid values.
    
    Args:
        value: Value to convert to float (can be None, string, number, etc.)
        default: Default value to return if conversion fails (default: 0.0)
        
    Returns:
        float: Converted value or default if conversion fails
        
    Examples:
        >>> safe_float("123.45")
        123.45
        >>> safe_float(None)
        0.0
        >>> safe_float("")
        0.0
        >>> safe_float("invalid", 10.0)
        10.0
    """
    if value is None or value == '':
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=0):
    """
    Safely convert value to int, handling None and invalid values.
    
    Args:
        value: Value to convert to int (can be None, string, number, etc.)
        default: Default value to return if conversion fails (default: 0)
        
    Returns:
        int: Converted value or default if conversion fails
        
    Examples:
        >>> safe_int("123")
        123
        >>> safe_int(None)
        0
        >>> safe_int("")
        0
        >>> safe_int("invalid", 10)
        10
        >>> safe_int("123.9")  # Handles float strings
        123
    """
    if value is None or value == '':
        return default
    try:
        return int(float(value))  # First convert to float to handle "123.0" strings
    except (ValueError, TypeError):
        return default


def safe_str(value, default=''):
    """
    Safely convert value to string, handling None values.
    
    Args:
        value: Value to convert to string
        default: Default value to return if value is None (default: '')
        
    Returns:
        str: String representation of value or default if value is None
        
    Examples:
        >>> safe_str(123)
        '123'
        >>> safe_str(None)
        ''
        >>> safe_str(None, 'N/A')
        'N/A'
    """
    if value is None:
        return default
    return str(value)


def safe_bool(value, default=False):
    """
    Safely convert value to boolean, handling various truthiness representations.
    
    Args:
        value: Value to convert to boolean
        default: Default value to return if value is None (default: False)
        
    Returns:
        bool: Boolean representation of value or default if value is None
        
    Examples:
        >>> safe_bool("true")
        True
        >>> safe_bool("1")
        True
        >>> safe_bool("false")
        False
        >>> safe_bool("0")
        False
        >>> safe_bool(None)
        False
    """
    if value is None:
        return default
    
    if isinstance(value, bool):
        return value
    
    if isinstance(value, str):
        value = value.lower().strip()
        if value in ('true', '1', 'yes', 'on', 'y', 't'):
            return True
        elif value in ('false', '0', 'no', 'off', 'n', 'f', ''):
            return False
    
    try:
        return bool(float(value))
    except (ValueError, TypeError):
        return default
