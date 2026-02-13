-- ============================================================================
-- COMPLETE MYSQL SCHEMA - Smart Portfolio Monitor
-- Authentication + Portfolio Data (NO Google Sheets Dependency)
-- ============================================================================

-- Drop existing tables if needed (BE CAREFUL IN PRODUCTION!)
-- DROP TABLE IF EXISTS portfolio_trades;
-- DROP TABLE IF EXISTS session_tokens;
-- DROP TABLE IF EXISTS password_reset_tokens;
-- DROP TABLE IF EXISTS audit_log;
-- DROP TABLE IF EXISTS users;

-- -----------------------------------------------------------------------------
-- 1. USERS TABLE (Authentication)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP NULL,
    is_active BOOLEAN DEFAULT TRUE,
    failed_login_attempts INT DEFAULT 0,
    locked_until TIMESTAMP NULL,
    INDEX idx_username (username),
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 2. PORTFOLIO_TRADES TABLE (Your Stock Portfolio)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portfolio_trades (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    position VARCHAR(10) NOT NULL,  -- 'LONG' or 'SHORT'
    entry_price DECIMAL(12, 2) NOT NULL,
    current_price DECIMAL(12, 2) NULL,
    quantity INT NOT NULL DEFAULT 1,
    stop_loss DECIMAL(12, 2) NOT NULL,
    target_1 DECIMAL(12, 2) NOT NULL,
    target_2 DECIMAL(12, 2) NULL,
    entry_date DATE NULL,
    exit_date DATE NULL,
    exit_price DECIMAL(12, 2) NULL,
    realized_pnl DECIMAL(12, 2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'ACTIVE',  -- 'ACTIVE', 'INACTIVE', 'PENDING'
    notes TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
    
    INDEX idx_user_ticker (user_id, ticker),
    INDEX idx_user_status (user_id, status),
    INDEX idx_ticker (ticker),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 3. SESSION_TOKENS TABLE (Security)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS session_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_token (token),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 4. AUDIT_LOG TABLE (Track All Actions)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    ticker VARCHAR(20) NULL,
    details TEXT NULL,
    ip_address VARCHAR(45) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_action (user_id, action_type),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 5. PASSWORD_RESET_TOKENS TABLE
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    token VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_token (token)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 6. TRADE_HISTORY TABLE (Closed Trades Log)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trade_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    position_type VARCHAR(10) NOT NULL,
    entry_price DECIMAL(12, 2) NOT NULL,
    exit_price DECIMAL(12, 2) NOT NULL,
    quantity INT NOT NULL,
    pnl DECIMAL(12, 2) NOT NULL,
    pnl_percent DECIMAL(8, 2) NOT NULL,
    exit_reason VARCHAR(100) NULL,
    entry_date DATE NULL,
    exit_date DATE NOT NULL,
    holding_days INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_ticker (ticker),
    INDEX idx_exit_date (exit_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 7. PERFORMANCE_STATS TABLE (User Performance Metrics)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS performance_stats (
    user_id INT PRIMARY KEY,
    total_trades INT DEFAULT 0,
    wins INT DEFAULT 0,
    losses INT DEFAULT 0,
    total_profit DECIMAL(12, 2) DEFAULT 0,
    total_loss DECIMAL(12, 2) DEFAULT 0,
    max_drawdown DECIMAL(8, 2) DEFAULT 0,
    peak_portfolio_value DECIMAL(12, 2) DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 8. SAMPLE DATA (for testing - remove in production)
-- -----------------------------------------------------------------------------
-- Create test user (password: Test@123)
INSERT INTO users (username, email, password_hash) 
VALUES (
    'testuser',
    'test@example.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5oDWLZvXRnKVe'
);

-- Get the user_id
SET @test_user_id = LAST_INSERT_ID();

-- Sample portfolio entries
INSERT INTO portfolio_trades (user_id, ticker, position, entry_price, quantity, stop_loss, target_1, target_2, entry_date, status) 
VALUES 
    (@test_user_id, 'RELIANCE', 'LONG', 2450.00, 10, 2380.00, 2550.00, 2650.00, '2024-01-15', 'ACTIVE'),
    (@test_user_id, 'TCS', 'LONG', 3580.00, 5, 3480.00, 3720.00, 3850.00, '2024-01-20', 'ACTIVE'),
    (@test_user_id, 'INFY', 'SHORT', 1520.00, 8, 1580.00, 1420.00, 1350.00, '2024-02-01', 'ACTIVE');

-- Initialize performance stats
INSERT INTO performance_stats (user_id) VALUES (@test_user_id);

-- -----------------------------------------------------------------------------
-- 9. USEFUL QUERIES (for reference)
-- -----------------------------------------------------------------------------

-- Get active portfolio for a user
-- SELECT * FROM portfolio_trades WHERE user_id = ? AND status = 'ACTIVE';

-- Get user's trade history
-- SELECT * FROM trade_history WHERE user_id = ? ORDER BY exit_date DESC;

-- Get performance stats
-- SELECT * FROM performance_stats WHERE user_id = ?;

-- Get audit log
-- SELECT * FROM audit_log WHERE user_id = ? ORDER BY created_at DESC LIMIT 100;

-- Update current price (done by app, not manually)
-- UPDATE portfolio_trades SET current_price = ?, updated_at = NOW() WHERE id = ? AND user_id = ?;

-- Mark position as inactive
-- UPDATE portfolio_trades SET status = 'INACTIVE', exit_date = ?, exit_price = ?, realized_pnl = ? WHERE id = ? AND user_id = ?;

-- -----------------------------------------------------------------------------
-- 10. INDEXES FOR PERFORMANCE (Already created above, but listed here)
-- -----------------------------------------------------------------------------
-- users: idx_username, idx_email
-- portfolio_trades: idx_user_ticker, idx_user_status, idx_ticker, idx_status
-- session_tokens: idx_token, idx_user_id
-- audit_log: idx_user_action, idx_created_at
-- trade_history: idx_user_id, idx_ticker, idx_exit_date

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================

-- Verify tables created
SHOW TABLES;

-- Check users table
DESCRIBE users;

-- Check portfolio_trades table
DESCRIBE portfolio_trades;
