"""
Database Configuration and Connection Module
Handles MySQL connection and CRUD operations
"""
import mysql.connector
from mysql.connector import Error, pooling
import streamlit as st
import hashlib
import logging
from datetime import datetime
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages MySQL database connections and operations"""
    
    def __init__(self):
        """Initialize database manager with connection pool"""
        self.connection_pool = None
        self._create_connection_pool()
    
    def _create_connection_pool(self):
        """Create MySQL connection pool from Streamlit secrets"""
        try:
            # Get credentials from Streamlit secrets
            db_config = {
                'host': st.secrets["mysql"]["host"],
                'database': st.secrets["mysql"]["database"],
                'user': st.secrets["mysql"]["user"],
                'password': st.secrets["mysql"]["password"],
                'port': st.secrets["mysql"]["port"]
            }
            
            self.connection_pool = pooling.MySQLConnectionPool(
                pool_name="portfolio_pool",
                pool_size=5,
                **db_config
            )
            
            logger.info("✅ Database connection pool created successfully")
            
        except KeyError as e:
            logger.error(f"❌ Missing database configuration in secrets: {e}")
            st.error(f"Database configuration error: {e}")
        except Error as e:
            logger.error(f"❌ Database connection error: {e}")
            st.error(f"Database connection failed: {e}")
    
    def get_connection(self):
        """Get connection from pool"""
        try:
            return self.connection_pool.get_connection()
        except Error as e:
            logger.error(f"Error getting connection from pool: {e}")
            return None
    
    def initialize_database(self):
        """Create all required tables if they don't exist"""
        connection = self.get_connection()
        if not connection:
            return False
        
        try:
            cursor = connection.cursor()
            
            # Users table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP NULL,
                is_active BOOLEAN DEFAULT TRUE,
                INDEX idx_username (username),
                INDEX idx_email (email)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # Portfolio positions table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                position_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                ticker VARCHAR(20) NOT NULL,
                position_type ENUM('LONG', 'SHORT') NOT NULL,
                entry_price DECIMAL(10, 2) NOT NULL,
                quantity INT NOT NULL,
                stop_loss DECIMAL(10, 2) NOT NULL,
                target_1 DECIMAL(10, 2) NOT NULL,
                target_2 DECIMAL(10, 2),
                entry_date DATE,
                exit_date DATE NULL,
                exit_price DECIMAL(10, 2) NULL,
                status ENUM('PENDING', 'ACTIVE', 'INACTIVE') DEFAULT 'ACTIVE',
                realized_pnl DECIMAL(12, 2) DEFAULT 0,
                exit_reason VARCHAR(255) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                INDEX idx_user_ticker (user_id, ticker),
                INDEX idx_status (status),
                INDEX idx_user_status (user_id, status)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # Trade history table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_history (
                trade_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                position_id INT,
                ticker VARCHAR(20) NOT NULL,
                trade_type ENUM('LONG', 'SHORT') NOT NULL,
                entry_price DECIMAL(10, 2) NOT NULL,
                exit_price DECIMAL(10, 2) NOT NULL,
                quantity INT NOT NULL,
                pnl DECIMAL(12, 2) NOT NULL,
                pnl_pct DECIMAL(8, 2) NOT NULL,
                exit_reason VARCHAR(255),
                is_win BOOLEAN,
                entry_date DATE,
                exit_date DATE,
                holding_days INT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                FOREIGN KEY (position_id) REFERENCES positions(position_id) ON DELETE SET NULL,
                INDEX idx_user_ticker (user_id, ticker),
                INDEX idx_user_date (user_id, exit_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # User settings table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                setting_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT UNIQUE NOT NULL,
                trail_sl_trigger DECIMAL(5, 2) DEFAULT 2.0,
                sl_risk_threshold INT DEFAULT 50,
                sl_approach_threshold DECIMAL(5, 2) DEFAULT 2.0,
                enable_email_alerts BOOLEAN DEFAULT FALSE,
                email_address VARCHAR(100),
                auto_refresh BOOLEAN DEFAULT TRUE,
                refresh_interval INT DEFAULT 60,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            connection.commit()
            logger.info("✅ All database tables initialized successfully")
            return True
            
        except Error as e:
            logger.error(f"❌ Error initializing database: {e}")
            connection.rollback()
            return False
        finally:
            cursor.close()
            connection.close()
    
    # ========================================================================
    # USER AUTHENTICATION METHODS
    # ========================================================================
    
    def hash_password(self, password: str) -> str:
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def register_user(self, username: str, email: str, password: str, 
                     full_name: str = None) -> Tuple[bool, str]:
        """Register a new user"""
        connection = self.get_connection()
        if not connection:
            return False, "Database connection failed"
        
        try:
            cursor = connection.cursor()
            password_hash = self.hash_password(password)
            
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, full_name)
                VALUES (%s, %s, %s, %s)
            """, (username, email, password_hash, full_name))
            
            user_id = cursor.lastrowid
            
            # Create default settings for new user
            cursor.execute("""
                INSERT INTO user_settings (user_id)
                VALUES (%s)
            """, (user_id,))
            
            connection.commit()
            logger.info(f"✅ User registered: {username}")
            return True, "Registration successful!"
            
        except mysql.connector.IntegrityError as e:
            if "username" in str(e):
                return False, "Username already exists"
            elif "email" in str(e):
                return False, "Email already registered"
            return False, "Registration failed"
        except Error as e:
            logger.error(f"Registration error: {e}")
            return False, f"Registration error: {str(e)}"
        finally:
            cursor.close()
            connection.close()
    
    def login_user(self, username: str, password: str) -> Tuple[bool, Optional[Dict]]:
        """Authenticate user and return user data"""
        connection = self.get_connection()
        if not connection:
            return False, None
        
        try:
            cursor = connection.cursor(dictionary=True)
            password_hash = self.hash_password(password)
            
            cursor.execute("""
                SELECT user_id, username, email, full_name, is_active
                FROM users
                WHERE username = %s AND password_hash = %s
            """, (username, password_hash))
            
            user = cursor.fetchone()
            
            if user and user['is_active']:
                # Update last login
                cursor.execute("""
                    UPDATE users SET last_login = NOW()
                    WHERE user_id = %s
                """, (user['user_id'],))
                connection.commit()
                
                logger.info(f"✅ User logged in: {username}")
                return True, user
            else:
                return False, None
                
        except Error as e:
            logger.error(f"Login error: {e}")
            return False, None
        finally:
            cursor.close()
            connection.close()
    
    # ========================================================================
    # POSITION MANAGEMENT METHODS
    # ========================================================================
    
    def add_position(self, user_id: int, ticker: str, position_type: str,
                    entry_price: float, quantity: int, stop_loss: float,
                    target_1: float, target_2: float = None, 
                    entry_date: str = None, status: str = 'ACTIVE') -> Tuple[bool, str]:
        """Add a new position"""
        connection = self.get_connection()
        if not connection:
            return False, "Database connection failed"
        
        try:
            cursor = connection.cursor()
            
            cursor.execute("""
                INSERT INTO positions 
                (user_id, ticker, position_type, entry_price, quantity, 
                 stop_loss, target_1, target_2, entry_date, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, ticker.upper(), position_type, entry_price, quantity,
                  stop_loss, target_1, target_2, entry_date, status))
            
            connection.commit()
            logger.info(f"✅ Position added: {ticker} for user {user_id}")
            return True, f"Position {ticker} added successfully!"
            
        except Error as e:
            logger.error(f"Error adding position: {e}")
            return False, f"Error: {str(e)}"
        finally:
            cursor.close()
            connection.close()
    
    def get_active_positions(self, user_id: int) -> List[Dict]:
        """Get all active positions for a user"""
        connection = self.get_connection()
        if not connection:
            return []
        
        try:
            cursor = connection.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT * FROM positions
                WHERE user_id = %s AND status = 'ACTIVE'
                ORDER BY created_at DESC
            """, (user_id,))
            
            positions = cursor.fetchall()
            return positions
            
        except Error as e:
            logger.error(f"Error fetching positions: {e}")
            return []
        finally:
            cursor.close()
            connection.close()
    
    def update_position(self, position_id: int, **kwargs) -> Tuple[bool, str]:
        """Update position fields"""
        connection = self.get_connection()
        if not connection:
            return False, "Database connection failed"
        
        try:
            cursor = connection.cursor()
            
            # Build dynamic UPDATE query
            set_clauses = []
            values = []
            
            allowed_fields = ['stop_loss', 'target_1', 'target_2', 'status', 
                            'exit_price', 'exit_date', 'realized_pnl', 'exit_reason']
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    set_clauses.append(f"{field} = %s")
                    values.append(value)
            
            if not set_clauses:
                return False, "No valid fields to update"
            
            query = f"UPDATE positions SET {', '.join(set_clauses)} WHERE position_id = %s"
            values.append(position_id)
            
            cursor.execute(query, tuple(values))
            connection.commit()
            
            return True, "Position updated successfully"
            
        except Error as e:
            logger.error(f"Error updating position: {e}")
            return False, f"Update error: {str(e)}"
        finally:
            cursor.close()
            connection.close()
    
    def delete_position(self, position_id: int, user_id: int) -> Tuple[bool, str]:
        """Delete a position (with user verification)"""
        connection = self.get_connection()
        if not connection:
            return False, "Database connection failed"
        
        try:
            cursor = connection.cursor()
            
            # Verify ownership
            cursor.execute("""
                DELETE FROM positions
                WHERE position_id = %s AND user_id = %s
            """, (position_id, user_id))
            
            if cursor.rowcount > 0:
                connection.commit()
                return True, "Position deleted successfully"
            else:
                return False, "Position not found or access denied"
                
        except Error as e:
            logger.error(f"Error deleting position: {e}")
            return False, f"Delete error: {str(e)}"
        finally:
            cursor.close()
            connection.close()
    
    def close_position(self, position_id: int, exit_price: float, 
                      exit_reason: str, user_id: int) -> Tuple[bool, str]:
        """Close a position and log to trade history"""
        connection = self.get_connection()
        if not connection:
            return False, "Database connection failed"
        
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Get position details
            cursor.execute("""
                SELECT * FROM positions
                WHERE position_id = %s AND user_id = %s AND status = 'ACTIVE'
            """, (position_id, user_id))
            
            position = cursor.fetchone()
            
            if not position:
                return False, "Position not found or already closed"
            
            # Calculate P&L
            if position['position_type'] == 'LONG':
                pnl = (exit_price - position['entry_price']) * position['quantity']
                pnl_pct = ((exit_price - position['entry_price']) / position['entry_price']) * 100
            else:
                pnl = (position['entry_price'] - exit_price) * position['quantity']
                pnl_pct = ((position['entry_price'] - exit_price) / position['entry_price']) * 100
            
            is_win = pnl > 0
            exit_date = datetime.now().date()
            
            # Calculate holding days
            if position['entry_date']:
                holding_days = (exit_date - position['entry_date']).days
            else:
                holding_days = 0
            
            # Update position
            cursor.execute("""
                UPDATE positions
                SET status = 'INACTIVE', exit_price = %s, exit_date = %s,
                    realized_pnl = %s, exit_reason = %s
                WHERE position_id = %s
            """, (exit_price, exit_date, pnl, exit_reason, position_id))
            
            # Log to trade history
            cursor.execute("""
                INSERT INTO trade_history
                (user_id, position_id, ticker, trade_type, entry_price, exit_price,
                 quantity, pnl, pnl_pct, exit_reason, is_win, entry_date, exit_date, holding_days)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (user_id, position_id, position['ticker'], position['position_type'],
                  position['entry_price'], exit_price, position['quantity'], pnl, pnl_pct,
                  exit_reason, is_win, position['entry_date'], exit_date, holding_days))
            
            connection.commit()
            logger.info(f"✅ Position closed: {position['ticker']} | P&L: ₹{pnl:+,.0f}")
            return True, f"Position closed | P&L: ₹{pnl:+,.0f}"
            
        except Error as e:
            logger.error(f"Error closing position: {e}")
            connection.rollback()
            return False, f"Error: {str(e)}"
        finally:
            cursor.close()
            connection.close()
    
    # ========================================================================
    # PERFORMANCE & ANALYTICS METHODS
    # ========================================================================
    
    def get_portfolio_stats(self, user_id: int) -> Dict:
        """Get comprehensive portfolio statistics"""
        connection = self.get_connection()
        if not connection:
            return {}
        
        try:
            cursor = connection.cursor(dictionary=True)
            
            # Active positions stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as active_count,
                    SUM(entry_price * quantity) as total_invested
                FROM positions
                WHERE user_id = %s AND status = 'ACTIVE'
            """, (user_id,))
            active_stats = cursor.fetchone()
            
            # Trade history stats
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN is_win = 1 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN is_win = 0 THEN 1 ELSE 0 END) as losses,
                    SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) as total_profit,
                    SUM(CASE WHEN pnl < 0 THEN ABS(pnl) ELSE 0 END) as total_loss,
                    SUM(pnl) as net_pnl,
                    AVG(CASE WHEN is_win = 1 THEN pnl END) as avg_win,
                    AVG(CASE WHEN is_win = 0 THEN ABS(pnl) END) as avg_loss
                FROM trade_history
                WHERE user_id = %s
            """, (user_id,))
            trade_stats = cursor.fetchone()
            
            # All positions (including closed)
            cursor.execute("""
                SELECT SUM(realized_pnl) as total_realized_pnl
                FROM positions
                WHERE user_id = %s AND status = 'INACTIVE'
            """, (user_id,))
            realized = cursor.fetchone()
            
            return {
                'active_positions': active_stats['active_count'] or 0,
                'total_invested': float(active_stats['total_invested'] or 0),
                'total_trades': trade_stats['total_trades'] or 0,
                'wins': trade_stats['wins'] or 0,
                'losses': trade_stats['losses'] or 0,
                'total_profit': float(trade_stats['total_profit'] or 0),
                'total_loss': float(trade_stats['total_loss'] or 0),
                'net_pnl': float(trade_stats['net_pnl'] or 0),
                'avg_win': float(trade_stats['avg_win'] or 0),
                'avg_loss': float(trade_stats['avg_loss'] or 0),
                'total_realized_pnl': float(realized['total_realized_pnl'] or 0)
            }
            
        except Error as e:
            logger.error(f"Error getting portfolio stats: {e}")
            return {}
        finally:
            cursor.close()
            connection.close()
    
    def get_trade_history(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Get recent trade history"""
        connection = self.get_connection()
        if not connection:
            return []
        
        try:
            cursor = connection.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT * FROM trade_history
                WHERE user_id = %s
                ORDER BY exit_date DESC, created_at DESC
                LIMIT %s
            """, (user_id, limit))
            
            return cursor.fetchall()
            
        except Error as e:
            logger.error(f"Error fetching trade history: {e}")
            return []
        finally:
            cursor.close()
            connection.close()


# Global database instance
db = None

def get_db() -> DatabaseManager:
    """Get or create database manager instance"""
    global db
    if db is None:
        db = DatabaseManager()
        db.initialize_database()
    return db
