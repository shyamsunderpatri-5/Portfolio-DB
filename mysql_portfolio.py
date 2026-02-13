"""
============================================================================
MYSQL PORTFOLIO DATA MODULE
Handles all portfolio operations in MySQL (replaces Google Sheets)
============================================================================
"""

import mysql.connector
from mysql.connector import Error
import pandas as pd
from datetime import datetime
from typing import Optional, Tuple, List, Dict
import streamlit as st
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

def get_mysql_connection():
    """
    Create MySQL database connection
    Returns: connection object or None
    """
    try:
        connection = mysql.connector.connect(
            host=st.secrets.get("MYSQL_HOST", "localhost"),
            port=st.secrets.get("MYSQL_PORT", 3306),
            user=st.secrets.get("MYSQL_USER", "root"),
            password=st.secrets.get("MYSQL_PASSWORD", ""),
            database=st.secrets.get("MYSQL_DATABASE", "portfolio_db"),
            autocommit=False
        )
        return connection
    except Error as e:
        logger.error(f"Database connection failed: {e}")
        st.error(f"❌ Database connection failed: {e}")
        return None


# ============================================================================
# PORTFOLIO LOADING (Replaces Google Sheets load_portfolio)
# ============================================================================

def load_portfolio_mysql(user_id: int) -> Optional[pd.DataFrame]:
    """
    Load user's active portfolio from MySQL
    
    Args:
        user_id: The logged-in user's ID
    
    Returns:
        DataFrame with portfolio data or None
    """
    connection = get_mysql_connection()
    
    if not connection:
        return None
    
    try:
        query = """
            SELECT 
                id,
                ticker AS Ticker,
                position AS Position,
                entry_price AS Entry_Price,
                current_price AS Current_Price,
                quantity AS Quantity,
                stop_loss AS Stop_Loss,
                target_1 AS Target_1,
                target_2 AS Target_2,
                entry_date AS Entry_Date,
                status AS Status,
                realized_pnl AS Realized_PnL,
                notes AS Notes,
                created_at,
                updated_at
            FROM portfolio_trades
            WHERE user_id = %s AND status IN ('ACTIVE', 'PENDING')
            ORDER BY created_at DESC
        """
        
        df = pd.read_sql(query, connection, params=(user_id,))
        
        if df.empty:
            logger.info(f"No active positions found for user {user_id}")
            return None
        
        # Convert Decimal values to float for all price columns
        price_columns = ['Entry_Price', 'Current_Price', 'Stop_Loss', 'Target_1', 'Target_2', 'Realized_PnL']
        for col in price_columns:
            if col in df.columns:
                df[col] = df[col].astype(float)
        
        # Convert date columns
        if 'Entry_Date' in df.columns:
            df['Entry_Date'] = pd.to_datetime(df['Entry_Date'], errors='coerce')
        
        # Set defaults for optional columns
        if 'Quantity' not in df.columns or df['Quantity'].isna().any():
            df['Quantity'] = df['Quantity'].fillna(1)
        
        if 'Target_2' not in df.columns or df['Target_2'].isna().any():
            df['Target_2'] = df['Target_2'].fillna(df['Target_1'] * 1.1)
        
        if 'Realized_PnL' not in df.columns:
            df['Realized_PnL'] = 0.0
        
        logger.info(f"Loaded {len(df)} positions for user {user_id}")
        
        return df
    
    except Error as e:
        logger.error(f"Error loading portfolio: {e}")
        st.error(f"❌ Error loading portfolio: {e}")
        return None
    
    finally:
        if connection:
            connection.close()


# ============================================================================
# ADD NEW TRADE
# ============================================================================

def add_trade_mysql(user_id: int, ticker: str, position: str, entry_price: float,
                   quantity: int, stop_loss: float, target_1: float, target_2: float = None,
                   entry_date: str = None, status: str = 'ACTIVE', 
                   notes: str = None) -> Tuple[bool, str]:
    """
    Add new trade to portfolio
    
    Returns: (success, message)
    """
    connection = get_mysql_connection()
    
    if not connection:
        return False, "Database connection failed"
    
    cursor = connection.cursor()
    
    try:
        # Validate inputs
        position = position.upper()
        if position not in ['LONG', 'SHORT']:
            return False, "Position must be 'LONG' or 'SHORT'"
        
        if entry_price <= 0 or stop_loss <= 0 or target_1 <= 0:
            return False, "Prices must be positive"
        
        if quantity <= 0:
            return False, "Quantity must be positive"
        
        # Set default target_2 if not provided
        if target_2 is None:
            target_2 = target_1 * 1.1
        
        # Set default entry_date if not provided
        if entry_date is None:
            entry_date = datetime.now().date()
        
        query = """
            INSERT INTO portfolio_trades 
            (user_id, ticker, position, entry_price, quantity, stop_loss, 
             target_1, target_2, entry_date, status, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        values = (
            user_id, ticker.upper(), position, entry_price, quantity,
            stop_loss, target_1, target_2, entry_date, status, notes
        )
        
        cursor.execute(query, values)
        connection.commit()
        
        trade_id = cursor.lastrowid
        
        logger.info(f"Added trade {trade_id}: {ticker} for user {user_id}")
        
        return True, f"✅ Trade added successfully (ID: {trade_id})"
    
    except Error as e:
        connection.rollback()
        logger.error(f"Error adding trade: {e}")
        return False, f"Error adding trade: {e}"
    
    finally:
        cursor.close()
        connection.close()


# ============================================================================
# UPDATE STOP LOSS (Replaces update_sheet_stop_loss)
# ============================================================================

def update_stop_loss_mysql(user_id: int, ticker: str, new_sl: float, 
                          reason: str = None) -> Tuple[bool, str]:
    """
    Update stop loss for a position
    
    Args:
        user_id: User ID (for security check)
        ticker: Stock ticker
        new_sl: New stop loss price
        reason: Reason for update (optional)
    
    Returns: (success, message)
    """
    connection = get_mysql_connection()
    
    if not connection:
        return False, "Database connection failed"
    
    cursor = connection.cursor(dictionary=True)
    
    try:
        # First, verify ownership
        cursor.execute(
            """
            SELECT id, stop_loss, position 
            FROM portfolio_trades 
            WHERE user_id = %s AND ticker = %s AND status = 'ACTIVE'
            """,
            (user_id, ticker.upper())
        )
        
        result = cursor.fetchone()
        
        if not result:
            return False, f"❌ Stock {ticker} not found in your active portfolio"
        
        trade_id = result['id']
        old_sl = result['stop_loss']
        position = result['position']
        
        # Validate new SL
        if new_sl <= 0:
            return False, "Stop loss must be positive"
        
        # Update stop loss
        cursor.execute(
            """
            UPDATE portfolio_trades 
            SET stop_loss = %s, updated_at = NOW()
            WHERE id = %s AND user_id = %s
            """,
            (new_sl, trade_id, user_id)
        )
        
        connection.commit()
        
        log_msg = f"🔄 {ticker} SL updated: ₹{old_sl:.2f} → ₹{new_sl:.2f}"
        
        if reason:
            log_msg += f" | Reason: {reason}"
        
        logger.info(f"User {user_id}: {log_msg}")
        
        return True, log_msg
    
    except Error as e:
        connection.rollback()
        logger.error(f"Error updating stop loss: {e}")
        return False, f"Error updating SL: {e}"
    
    finally:
        cursor.close()
        connection.close()


# ============================================================================
# UPDATE TARGET (Replaces update_sheet_target)
# ============================================================================

def update_target_mysql(user_id: int, ticker: str, new_target: float,
                       target_num: int = 2, reason: str = None) -> Tuple[bool, str]:
    """
    Update target for a position
    
    Args:
        user_id: User ID
        ticker: Stock ticker
        new_target: New target price
        target_num: 1 or 2 (which target to update)
        reason: Reason for update
    
    Returns: (success, message)
    """
    connection = get_mysql_connection()
    
    if not connection:
        return False, "Database connection failed"
    
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Verify ownership
        cursor.execute(
            """
            SELECT id, target_1, target_2 
            FROM portfolio_trades 
            WHERE user_id = %s AND ticker = %s AND status = 'ACTIVE'
            """,
            (user_id, ticker.upper())
        )
        
        result = cursor.fetchone()
        
        if not result:
            return False, f"Stock {ticker} not found in your portfolio"
        
        trade_id = result['id']
        old_target = result[f'target_{target_num}']
        
        # Update target
        target_column = f'target_{target_num}'
        cursor.execute(
            f"""
            UPDATE portfolio_trades 
            SET {target_column} = %s, updated_at = NOW()
            WHERE id = %s AND user_id = %s
            """,
            (new_target, trade_id, user_id)
        )
        
        connection.commit()
        
        log_msg = f"🎯 {ticker} Target {target_num} updated: ₹{old_target:.2f} → ₹{new_target:.2f}"
        
        if reason:
            log_msg += f" | {reason}"
        
        logger.info(f"User {user_id}: {log_msg}")
        
        return True, log_msg
    
    except Error as e:
        connection.rollback()
        logger.error(f"Error updating target: {e}")
        return False, f"Error: {e}"
    
    finally:
        cursor.close()
        connection.close()


# ============================================================================
# MARK POSITION INACTIVE (Close Trade)
# ============================================================================

def mark_position_inactive_mysql(user_id: int, ticker: str, exit_price: float,
                                pnl_amount: float, exit_reason: str) -> Tuple[bool, str]:
    """
    Close a position and mark as inactive
    
    Returns: (success, message)
    """
    connection = get_mysql_connection()
    
    if not connection:
        return False, "Database connection failed"
    
    cursor = connection.cursor(dictionary=True)
    
    try:
        # Verify ownership and get trade details
        cursor.execute(
            """
            SELECT id, entry_price, quantity, position, entry_date
            FROM portfolio_trades 
            WHERE user_id = %s AND ticker = %s AND status = 'ACTIVE'
            """,
            (user_id, ticker.upper())
        )
        
        result = cursor.fetchone()
        
        if not result:
            return False, f"Stock {ticker} not found in your active portfolio"
        
        trade_id = result['id']
        entry_price = float(result['entry_price'])
        quantity = result['quantity']
        position_type = result['position']
        entry_date = result['entry_date']
        
        # Calculate holding days
        if entry_date:
            holding_days = (datetime.now().date() - entry_date).days
        else:
            holding_days = 0
        
        # Calculate P&L percentage
        if position_type == 'LONG':
            pnl_pct = ((float(exit_price) - entry_price) / entry_price) * 100
        else:
            pnl_pct = ((entry_price - float(exit_price)) / entry_price) * 100
        
        # Update portfolio_trades to INACTIVE
        cursor.execute(
            """
            UPDATE portfolio_trades 
            SET status = 'INACTIVE',
                exit_date = %s,
                exit_price = %s,
                realized_pnl = %s,
                notes = CONCAT(COALESCE(notes, ''), ' | Exit: ', %s),
                updated_at = NOW()
            WHERE id = %s AND user_id = %s
            """,
            (datetime.now().date(), exit_price, pnl_amount, exit_reason, trade_id, user_id)
        )
        
        # Insert into trade_history
        cursor.execute(
            """
            INSERT INTO trade_history 
            (user_id, ticker, position_type, entry_price, exit_price, 
             quantity, pnl, pnl_percent, exit_reason, entry_date, exit_date, holding_days)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (user_id, ticker.upper(), position_type, entry_price, exit_price,
             quantity, pnl_amount, pnl_pct, exit_reason, entry_date,
             datetime.now().date(), holding_days)
        )
        
        # Update performance stats
        cursor.execute(
            """
            INSERT INTO performance_stats (user_id, total_trades, wins, losses, total_profit, total_loss)
            VALUES (%s, 1, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                total_trades = total_trades + 1,
                wins = wins + %s,
                losses = losses + %s,
                total_profit = total_profit + %s,
                total_loss = total_loss + %s,
                updated_at = NOW()
            """,
            (
                user_id,
                1 if pnl_amount > 0 else 0,
                1 if pnl_amount <= 0 else 0,
                pnl_amount if pnl_amount > 0 else 0,
                abs(pnl_amount) if pnl_amount < 0 else 0,
                1 if pnl_amount > 0 else 0,
                1 if pnl_amount <= 0 else 0,
                pnl_amount if pnl_amount > 0 else 0,
                abs(pnl_amount) if pnl_amount < 0 else 0
            )
        )
        
        connection.commit()
        
        log_msg = f"🚪 {ticker} closed | Exit: ₹{exit_price:.2f} | P&L: ₹{pnl_amount:+,.0f} | {exit_reason}"
        logger.info(f"User {user_id}: {log_msg}")
        
        return True, log_msg
    
    except Error as e:
        connection.rollback()
        logger.error(f"Error closing position: {e}")
        return False, f"Error: {e}"
    
    finally:
        cursor.close()
        connection.close()


# ============================================================================
# GET PERFORMANCE STATS
# ============================================================================

def get_performance_stats_mysql(user_id: int) -> Optional[Dict]:
    """
    Get user's performance statistics
    
    Returns: dict with performance metrics or None
    """
    connection = get_mysql_connection()
    
    if not connection:
        return None
    
    cursor = connection.cursor(dictionary=True)
    
    try:
        cursor.execute(
            """
            SELECT 
                total_trades,
                wins,
                losses,
                total_profit,
                total_loss,
                max_drawdown,
                peak_portfolio_value
            FROM performance_stats
            WHERE user_id = %s
            """,
            (user_id,)
        )
        
        stats = cursor.fetchone()
        
        if not stats or stats['total_trades'] == 0:
            return None
        
        # Convert Decimal values to float
        total_trades = int(stats['total_trades'])
        wins = int(stats['wins'])
        losses = int(stats['losses'])
        total_profit = float(stats['total_profit']) if stats['total_profit'] else 0
        total_loss = float(stats['total_loss']) if stats['total_loss'] else 0
        max_drawdown = float(stats['max_drawdown']) if stats['max_drawdown'] else 0
        peak_value = float(stats['peak_portfolio_value']) if stats['peak_portfolio_value'] else 0
        
        # Calculate derived metrics
        win_rate = (wins / total_trades) * 100
        avg_win = total_profit / wins if wins > 0 else 0
        avg_loss = total_loss / losses if losses > 0 else 0
        
        expectancy = (win_rate/100 * avg_win) - ((100-win_rate)/100 * avg_loss)
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        net_profit = total_profit - total_loss
        
        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'expectancy': expectancy,
            'profit_factor': profit_factor,
            'net_profit': net_profit,
            'max_drawdown': max_drawdown,
            'peak_portfolio_value': peak_value
        }
    
    except Error as e:
        logger.error(f"Error getting performance stats: {e}")
        return None
    
    finally:
        cursor.close()
        connection.close()


# ============================================================================
# GET TRADE HISTORY
# ============================================================================

def get_trade_history_mysql(user_id: int, limit: int = 50) -> Optional[pd.DataFrame]:
    """
    Get user's trade history
    
    Returns: DataFrame with trade history or None
    """
    connection = get_mysql_connection()
    
    if not connection:
        return None
    
    try:
        query = """
            SELECT 
                ticker,
                position_type,
                entry_price,
                exit_price,
                quantity,
                pnl,
                pnl_percent,
                exit_reason,
                entry_date,
                exit_date,
                holding_days,
                created_at
            FROM trade_history
            WHERE user_id = %s
            ORDER BY exit_date DESC
            LIMIT %s
        """
        
        df = pd.read_sql(query, connection, params=(user_id, limit))
        
        if not df.empty:
            # Convert Decimal values to float for price columns
            price_columns = ['entry_price', 'exit_price', 'pnl', 'pnl_percent']
            for col in price_columns:
                if col in df.columns:
                    df[col] = df[col].astype(float)
        
        return df if not df.empty else None
    
    except Error as e:
        logger.error(f"Error getting trade history: {e}")
        return None
    
    finally:
        connection.close()


# ============================================================================
# UPDATE CURRENT PRICE (for real-time tracking)
# ============================================================================

def update_current_prices_mysql(user_id: int, price_updates: List[Tuple[str, float]]) -> bool:
    """
    Batch update current prices for multiple stocks
    
    Args:
        user_id: User ID
        price_updates: List of (ticker, current_price) tuples
    
    Returns: success
    """
    connection = get_mysql_connection()
    
    if not connection:
        return False
    
    cursor = connection.cursor()
    
    try:
        for ticker, current_price in price_updates:
            cursor.execute(
                """
                UPDATE portfolio_trades 
                SET current_price = %s, updated_at = NOW()
                WHERE user_id = %s AND ticker = %s AND status = 'ACTIVE'
                """,
                (current_price, user_id, ticker.upper())
            )
        
        connection.commit()
        return True
    
    except Error as e:
        connection.rollback()
        logger.error(f"Error updating prices: {e}")
        return False
    
    finally:
        cursor.close()
        connection.close()


# ============================================================================
# DELETE TRADE (if needed)
# ============================================================================

def delete_trade_mysql(user_id: int, ticker: str) -> Tuple[bool, str]:
    """
    Delete a trade (use with caution!)
    
    Returns: (success, message)
    """
    connection = get_mysql_connection()
    
    if not connection:
        return False, "Database connection failed"
    
    cursor = connection.cursor()
    
    try:
        # Verify ownership before deleting
        cursor.execute(
            """
            DELETE FROM portfolio_trades 
            WHERE user_id = %s AND ticker = %s
            """,
            (user_id, ticker.upper())
        )
        
        rows_affected = cursor.rowcount
        connection.commit()
        
        if rows_affected > 0:
            logger.info(f"User {user_id}: Deleted {ticker}")
            return True, f"✅ Deleted {ticker}"
        else:
            return False, f"Stock {ticker} not found"
    
    except Error as e:
        connection.rollback()
        logger.error(f"Error deleting trade: {e}")
        return False, f"Error: {e}"
    
    finally:
        cursor.close()
        connection.close()
