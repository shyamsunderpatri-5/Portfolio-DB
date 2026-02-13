# 🧠 Smart Portfolio Monitor v6.0 - MERGED EDITION

## ✅ What Was Done

Your app.py has been successfully merged with the advanced version. All features have been integrated while maintaining your MySQL database flow instead of Google Sheets.

---

## 🎯 Key Features Now Included

### 1. **Market Health Analysis** ✅
- Real-time NIFTY 50 monitoring
- India VIX tracking
- RSI, SMA20, SMA50 analysis
- Automatic alert threshold adjustment based on market conditions
- Color-coded market status (BULLISH/NEUTRAL/WEAK/BEARISH)

### 2. **Advanced Technical Analysis** ✅
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Volume analysis with ratios
- Momentum scoring (0-100)
- Moving averages (SMA20, SMA50, EMA9)

### 3. **Stop Loss Management** ✅
- SL Risk prediction (0-100%)
- Trail stop loss recommendations with auto-update to MySQL
- Dynamic SL calculations based on ATR
- Approaching SL warnings with visual alerts

### 4. **Target Management** ✅
- Multi-level targets (Target 1, Target 2)
- Upside potential scoring
- Dynamic target extension recommendations
- Auto-update to MySQL when conditions met

### 5. **Position Monitoring** ✅
- Real-time P&L tracking
- Entry date tracking with holding period calculation
- Tax implication analysis (LTCG/STCG)
- Risk-Reward ratio calculations

### 6. **Email Alerts** ✅
- Configurable alert types (Critical, Target, SL Approach, etc.)
- Beautiful HTML email formatting
- Alert cooldown mechanism (avoid spam)
- Customizable per-alert email settings

### 7. **Dashboard & Visualization** ✅
- Portfolio summary cards
- Individual position expandable cards
- Candlestick charts with moving averages
- RSI and MACD indicator charts
- Volume analysis charts

### 8. **Risk Management** ✅
- Portfolio-level risk calculation
- Sector exposure analysis
- Correlation analysis (optional)
- Drawdown tracking

---

## 🔄 Database Integration (MySQL)

### What Changed:
- **Removed:** Google Sheets API functions
- **Added:** MySQL database functions for all operations
- **Benefits:** 
  - No API rate limits
  - Multi-user support via `user_id`
  - Real-time data persistence
  - Better security with secrets management

### Key MySQL Functions:

```python
# Loading portfolio
load_portfolio_mysql(user_id)

# Updating positions
update_sheet_stop_loss(user_id, ticker, new_sl, reason)
update_sheet_target(user_id, ticker, new_target, target_num, reason)
mark_position_inactive(user_id, ticker, exit_price, pnl_amount)
```

---

## 📋 How to Use

### 1. **Ensure Secrets are Configured**

Edit `secrets.toml`:
```toml
[mysql]
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_USER = "your_user"
MYSQL_PASSWORD = "your_password"
MYSQL_DATABASE = "portfolio_db"

[email]
EMAIL_ADDRESS = "your_email@gmail.com"
EMAIL_PASSWORD = "xxxx xxxx xxxx xxxx"  # Gmail App Password
RECIPIENT_EMAIL = "recipient@gmail.com"
```

### 2. **Start the App**
```bash
streamlit run app.py
```

### 3. **Log In**
- Use your authentication module (`auth_module.py` or `auth_ui.py`)
- App checks `st.session_state.user_id`

### 4. **Monitor Your Portfolio**
- View market health at the top
- Analyze each position with detailed metrics
- Exit positions with one-click confirmation
- Receive email alerts automatically

---

## 🚀 Advanced Features

### Auto-Update to MySQL
Whenever these conditions are met, the app automatically updates MySQL:

1. **Stop Loss Update**
   - When trail stop > original SL
   - Emails sent automatically
   - Reason recorded in database

2. **Target Extension**
   - When upside score >= 60%
   - After target 1 is hit
   - New target calculated from ATR and support/resistance

3. **Position Closure**
   - When SL is hit OR target is achieved
   - Manual exit confirmation available
   - P&L recorded to `realized_pnl` field
   - Position marked as 'INACTIVE'

### Email Alerts
Automatically sent for:
- 🔴 **Critical:** SL hit, high risk
- 🎯 **Target Hit:** T1/T2 achievement
- ⚠️ **SL Approach:** Within threshold distance
- 🔄 **Trail SL:** Stop loss updated
- 📈 **New Target:** Target extended
- 📋 **Important:** Other alerts

---

## 📊 Session State Management

The app tracks:
- Email logs (50 most recent)
- Trade history
- Performance statistics
- Drawdown tracking
- Performance metrics

All data is stored in `st.session_state` for fast access.

---

## 🔧 Technical Improvements

### Performance
- `@st.cache_data` decorators for expensive operations
- Rate-limited API calls to yfinance
- 5-minute cache for market health data
- 15-second cache for position analysis

### Error Handling
- Graceful fallbacks for API failures
- Database connection retry logic
- Comprehensive logging
- User-friendly error messages

### Security
- Secrets-based credentials (no hardcoded values)
- Email authentication via app passwords
- User-specific data via `user_id`
- SQL injection prevention with parameterized queries

---

## 📝 Database Schema Required

Ensure your `portfolio_trades` table has these columns:

```sql
CREATE TABLE portfolio_trades (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    position ENUM('LONG', 'SHORT'),
    entry_price DECIMAL(10, 2),
    quantity INT,
    stop_loss DECIMAL(10, 2),
    target_1 DECIMAL(10, 2),
    target_2 DECIMAL(10, 2),
    entry_date DATE,
    status ENUM('ACTIVE', 'PENDING', 'INACTIVE') DEFAULT 'ACTIVE',
    realized_pnl DECIMAL(12, 2),
    exit_date DATE,
    exit_reason VARCHAR(255),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

## ✨ What's Preserved

- ✅ Your MySQL database integration
- ✅ Your authentication flow
- ✅ Your `mysql_portfolio.py` functions
- ✅ Your `auth_module.py` and `auth_ui.py`
- ✅ Secrets-based configuration

---

## 🆕 What's New

- ✨ 8+ Advanced technical indicators
- ✨ Real-time market health dashboard
- ✨ Email alerts with beautiful HTML formatting
- ✨ Professional dashboard UI with color coding
- ✨ Auto-update MySQL features
- ✨ Portfolio risk analysis
- ✨ Complete position analysis with charts
- ✨ One-click exit confirmations

---

## 🐛 Troubleshooting

### "No active positions found"
- Check that your `portfolio_trades` table has `status='ACTIVE'` records
- Verify `user_id` is set correctly in `st.session_state`

### Email not sending
- Verify EMAIL_ADDRESS and EMAIL_PASSWORD in secrets
- Use Gmail app password (not regular password)
- Enable "Less secure apps" if needed

### Charts not showing
- Ensure ticker symbols are valid (add `.NS` for NSE unless already present)
- Check internet connection for yfinance data
- Wait for cache to refresh (5 minutes)

---

## 📞 Support

For issues, check:
1. Database connection in `get_mysql_connection()`
2. Email credentials in sidebar settings
3. Ticker symbols match your database
4. User authentication in `st.session_state.user_id`

---

**Version:** 6.0 | **Last Updated:** 2026-02-13  
**Database:** MySQL | **Auth:** Yes | **Email:** Yes
