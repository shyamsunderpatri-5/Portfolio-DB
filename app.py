"""
🧠 SMART PORTFOLIO MONITOR v6.0 - COMPLETE EDITION WITH MYSQL
==============================================================
Features: Market Health • Emergency Exit • Chart Patterns • Advanced Analytics
Multi-User Auth • MySQL Backend • Email Alerts • Dynamic Levels
"""

import os
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hashlib
import time
import json
from typing import Tuple, Optional, Dict, List, Any
import logging
import re
import mysql.connector
from mysql.connector import Error

# ==========================================================================
# LOGGING SETUP
# ==========================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import optional packages
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

# ==========================================================================
# PAGE CONFIG (MUST BE FIRST STREAMLIT COMMAND!)
# ==========================================================================
st.set_page_config(
    page_title="Smart Portfolio Monitor v6.0",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================================================
# CUSTOM CSS
# ==========================================================================
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem 0;
    }
    .critical-box {
        background: linear-gradient(135deg, #dc3545, #c82333);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        margin: 10px 0;
    }
    .success-box {
        background: linear-gradient(135deg, #28a745, #218838);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        margin: 10px 0;
    }
    .warning-box {
        background: linear-gradient(135deg, #ffc107, #e0a800);
        color: black;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        margin: 10px 0;
    }
    .info-box {
        background: linear-gradient(135deg, #17a2b8, #138496);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================================================
# INITIALIZE SESSION STATE
# ==========================================================================
def init_session_state():
    """Initialize all session state variables"""
    defaults = {
        'email_sent_alerts': {},
        'last_email_time': {},
        'email_log': [],
        'trade_history': [],
        'portfolio_values': [],
        'performance_stats': {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'total_profit': 0,
            'total_loss': 0
        },
        'drawdown_history': [],
        'peak_portfolio_value': 0,
        'current_drawdown': 0,
        'max_drawdown': 0,
        'partial_exits': {},
        'holding_periods': {},
        'last_api_call': {},
        'api_call_count': 0,
        'correlation_matrix': None,
        'last_correlation_calc': None
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

# ==========================================================================
# DATABASE FUNCTIONS (MySQL instead of Google Sheets)
# ==========================================================================

def get_mysql_connection():
    """Create MySQL database connection"""
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


def load_portfolio_mysql(user_id: int) -> Optional[pd.DataFrame]:
    """Load user's active portfolio from MySQL"""
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
                quantity AS Quantity,
                stop_loss AS Stop_Loss,
                target_1 AS Target_1,
                target_2 AS Target_2,
                entry_date AS Entry_Date,
                status AS Status,
                realized_pnl AS Realized_PnL,
                notes AS Notes
            FROM portfolio_trades
            WHERE user_id = %s AND status IN ('ACTIVE', 'PENDING')
            ORDER BY created_at DESC
        """
        
        df = pd.read_sql(query, connection, params=(user_id,))
        
        if df.empty:
            return None
        
        # Convert Decimal values to float
        price_columns = ['Entry_Price', 'Stop_Loss', 'Target_1', 'Target_2', 'Realized_PnL']
        for col in price_columns:
            if col in df.columns:
                df[col] = df[col].astype(float)
        
        if 'Entry_Date' in df.columns:
            df['Entry_Date'] = pd.to_datetime(df['Entry_Date'], errors='coerce')
        
        return df
        
    except Error as e:
        logger.error(f"Database query failed: {e}")
        return None
    finally:
        if connection.is_connected():
            connection.close()


def update_sheet_stop_loss(user_id: int, ticker: str, new_sl: float, reason: str, 
                          should_send_email=True, email_settings=None, result=None):
    """Update Stop Loss in MySQL and send email"""
    connection = get_mysql_connection()
    
    if not connection:
        return False, "Could not connect to database"
    
    try:
        cursor = connection.cursor()
        
        # Get current SL
        cursor.execute(
            "SELECT stop_loss FROM portfolio_trades WHERE user_id = %s AND ticker = %s AND status = 'ACTIVE'",
            (user_id, ticker)
        )
        result_sl = cursor.fetchone()
        
        if not result_sl:
            return False, f"Ticker {ticker} not found"
        
        old_sl = result_sl[0]
        new_sl = round_to_tick_size(new_sl)
        
        # Update database
        cursor.execute(
            "UPDATE portfolio_trades SET stop_loss = %s, updated_at = NOW() WHERE user_id = %s AND ticker = %s AND status = 'ACTIVE'",
            (new_sl, user_id, ticker)
        )
        
        connection.commit()
        
        log_message = f"🔄 AUTO-UPDATED {ticker} SL: ₹{old_sl} → ₹{new_sl:.2f} - {reason}"
        logger.info(log_message)
        log_email(log_message)
        
        # Send email if enabled
        if should_send_email and email_settings and result and email_settings.get('enabled'):
            send_sl_update_email(ticker, old_sl, new_sl, reason, email_settings, result)
        
        return True, log_message
        
    except Error as e:
        logger.error(f"Update failed: {e}")
        return False, str(e)
    finally:
        if connection.is_connected():
            connection.close()


def update_sheet_target(user_id: int, ticker: str, new_target: float, target_num: int, reason: str,
                       should_send_email=True, email_settings=None, result=None):
    """Update Target in MySQL"""
    connection = get_mysql_connection()
    
    if not connection:
        return False, "Could not connect to database"
    
    try:
        cursor = connection.cursor()
        
        target_col = f"target_{target_num}"
        cursor.execute(
            f"SELECT {target_col} FROM portfolio_trades WHERE user_id = %s AND ticker = %s AND status = 'ACTIVE'",
            (user_id, ticker)
        )
        result_target = cursor.fetchone()
        
        if not result_target:
            return False, f"Ticker {ticker} not found"
        
        old_target = result_target[0]
        new_target = round_to_tick_size(new_target)
        
        cursor.execute(
            f"UPDATE portfolio_trades SET {target_col} = %s, updated_at = NOW() WHERE user_id = %s AND ticker = %s AND status = 'ACTIVE'",
            (new_target, user_id, ticker)
        )
        
        connection.commit()
        
        log_message = f"🎯 AUTO-UPDATED {ticker} Target {target_num}: ₹{old_target} → ₹{new_target:.2f} - {reason}"
        logger.info(log_message)
        log_email(log_message)
        
        if should_send_email and email_settings and result and email_settings.get('enabled'):
            send_target_update_email(ticker, old_target, new_target, target_num, reason, email_settings, result)
        
        return True, log_message
        
    except Error as e:
        logger.error(f"Update failed: {e}")
        return False, str(e)
    finally:
        if connection.is_connected():
            connection.close()


def mark_position_inactive(user_id: int, ticker: str, exit_price: float, pnl_amount: float,
                          exit_reason: str, should_send_email=True, email_settings=None, result=None):
    """Mark position as INACTIVE and record realized P&L"""
    connection = get_mysql_connection()
    
    if not connection:
        return False, "Could not connect to database"
    
    try:
        cursor = connection.cursor()
        
        exit_date = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute(
            """UPDATE portfolio_trades SET status = 'INACTIVE', 
               realized_pnl = %s, exit_date = %s, exit_reason = %s, updated_at = NOW()
               WHERE user_id = %s AND ticker = %s AND status IN ('ACTIVE', 'PENDING')""",
            (pnl_amount, exit_date, exit_reason, user_id, ticker)
        )
        
        connection.commit()
        
        log_message = f"🚪 POSITION CLOSED: {ticker} | Exit: ₹{exit_price:.2f} | P&L: ₹{pnl_amount:+,.0f}"
        logger.info(log_message)
        log_email(log_message)
        
        if should_send_email and email_settings and result and email_settings.get('enabled'):
            send_exit_email(ticker, exit_price, pnl_amount, exit_reason, email_settings, result)
        
        return True, log_message
        
    except Error as e:
        logger.error(f"Update failed: {e}")
        return False, str(e)
    finally:
        if connection.is_connected():
            connection.close()


# ==========================================================================
# HELPER FUNCTIONS
# ==========================================================================

def get_ist_now():
    """Get current IST time"""
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def is_market_hours():
    """Check if market is open"""
    ist_now = get_ist_now()
    
    if ist_now.weekday() >= 5:
        return False, "WEEKEND", "Markets closed for weekend", "🔴"
    
    market_open = datetime.strptime("09:15", "%H:%M").time()
    market_close = datetime.strptime("15:30", "%H:%M").time()
    current_time = ist_now.time()
    
    if current_time < market_open:
        return False, "PRE-MARKET", f"Opens at 09:15 IST", "🟡"
    elif current_time > market_close:
        return False, "CLOSED", "Market closed for today", "🔴"
    else:
        return True, "OPEN", f"Closes at 15:30 IST", "🟢"

def log_email(message):
    """Add to email log"""
    timestamp = get_ist_now().strftime("%H:%M:%S")
    st.session_state.email_log.append(f"[{timestamp}] {message}")
    if len(st.session_state.email_log) > 50:
        st.session_state.email_log = st.session_state.email_log[-50:]

def safe_divide(numerator, denominator, default=0.0):
    """Safe division that handles zero and NaN"""
    try:
        if denominator == 0 or pd.isna(denominator) or pd.isna(numerator):
            return default
        result = numerator / denominator
        return default if pd.isna(result) or np.isinf(result) else result
    except:
        return default

def round_to_tick_size(price):
    """Round price according to NSE tick size rules"""
    if pd.isna(price) or price is None:
        return 0.0
    
    price = float(price)
    
    if price < 0:
        return 0.0
    
    if price < 1:
        return round(price / 0.01) * 0.01
    else:
        return round(price / 0.05) * 0.05

# ==========================================================================
# TECHNICAL ANALYSIS FUNCTIONS
# ==========================================================================

def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.finfo(float).eps)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate MACD"""
    exp_fast = prices.ewm(span=fast, adjust=False).mean()
    exp_slow = prices.ewm(span=slow, adjust=False).mean()
    macd = exp_fast - exp_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram

def calculate_momentum_score(df):
    """Calculate comprehensive momentum score (0-100)"""
    close = df['Close']
    score = 50
    components = {}
    
    rsi = calculate_rsi(close).iloc[-1]
    if pd.isna(rsi):
        rsi = 50
    
    if rsi > 70:
        rsi_score = -10
    elif rsi > 60:
        rsi_score = 15
    elif rsi > 50:
        rsi_score = 10
    elif rsi > 40:
        rsi_score = -5
    elif rsi > 30:
        rsi_score = -15
    else:
        rsi_score = 10
    
    score += rsi_score
    components['RSI'] = rsi_score
    
    macd, signal, histogram = calculate_macd(close)
    hist_current = histogram.iloc[-1] if len(histogram) > 0 else 0
    hist_prev = histogram.iloc[-2] if len(histogram) > 1 else 0
    
    if pd.isna(hist_current):
        hist_current = 0
    if pd.isna(hist_prev):
        hist_prev = 0
    
    if hist_current > 0:
        macd_score = 20 if hist_current > hist_prev else 10
    else:
        macd_score = -20 if hist_current < hist_prev else -10
    
    score += macd_score
    components['MACD'] = macd_score
    
    current_price = close.iloc[-1]
    sma_20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else close.mean()
    sma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else sma_20
    ema_9 = close.ewm(span=9).mean().iloc[-1]
    
    ma_score = 0
    if current_price > ema_9:
        ma_score += 5
    if current_price > sma_20:
        ma_score += 5
    if current_price > sma_50:
        ma_score += 5
    if sma_20 > sma_50:
        ma_score += 5
    
    if current_price < ema_9:
        ma_score -= 5
    if current_price < sma_20:
        ma_score -= 5
    if current_price < sma_50:
        ma_score -= 5
    if sma_20 < sma_50:
        ma_score -= 5
    
    score += ma_score
    components['MA'] = ma_score
    
    returns_5d = ((close.iloc[-1] / close.iloc[-6]) - 1) * 100 if len(close) > 6 else 0
    momentum_score = min(15, max(-15, returns_5d * 3))
    score += momentum_score
    components['Momentum'] = momentum_score
    
    final_score = max(0, min(100, score))
    
    if final_score >= 70:
        trend = "STRONG BULLISH"
    elif final_score >= 55:
        trend = "BULLISH"
    elif final_score >= 45:
        trend = "NEUTRAL"
    elif final_score >= 30:
        trend = "BEARISH"
    else:
        trend = "STRONG BEARISH"
    
    return final_score, trend, components

def analyze_volume(df):
    """Analyze volume"""
    if 'Volume' not in df.columns or len(df) < 20:
        return "NEUTRAL", 1.0, "Volume data not available", "NEUTRAL"
    
    if df['Volume'].iloc[-1] == 0:
        return "NEUTRAL", 1.0, "No volume data", "NEUTRAL"
    
    avg_volume = df['Volume'].rolling(20).mean().iloc[-1]
    current_volume = df['Volume'].iloc[-1]
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
    
    price_change = df['Close'].iloc[-1] - df['Close'].iloc[-2]
    
    vol_5d = df['Volume'].tail(5).mean()
    vol_20d = df['Volume'].tail(20).mean()
    volume_trend = "INCREASING" if vol_5d > vol_20d else "DECREASING"
    
    if price_change > 0 and volume_ratio > 1.5:
        signal = "STRONG_BUYING"
        desc = f"Strong buying pressure ({volume_ratio:.1f}x avg volume)"
    elif price_change > 0 and volume_ratio > 1.0:
        signal = "BUYING"
        desc = f"Buying with good volume ({volume_ratio:.1f}x)"
    elif price_change > 0 and volume_ratio < 0.7:
        signal = "WEAK_BUYING"
        desc = f"Weak rally, low volume ({volume_ratio:.1f}x)"
    elif price_change < 0 and volume_ratio > 1.5:
        signal = "STRONG_SELLING"
        desc = f"Strong selling pressure ({volume_ratio:.1f}x avg volume)"
    elif price_change < 0 and volume_ratio > 1.0:
        signal = "SELLING"
        desc = f"Selling with volume ({volume_ratio:.1f}x)"
    elif price_change < 0 and volume_ratio < 0.7:
        signal = "WEAK_SELLING"
        desc = f"Weak decline, low volume ({volume_ratio:.1f}x)"
    else:
        signal = "NEUTRAL"
        desc = f"Normal volume ({volume_ratio:.1f}x)"
    
    return signal, volume_ratio, desc, volume_trend

@st.cache_data(ttl=300)
def get_market_health():
    """Analyze market health"""
    try:
        nifty = yf.Ticker("^NSEI")
        nifty_df = nifty.history(period="1mo")
        
        if nifty_df.empty:
            return None
        
        nifty_price = float(nifty_df['Close'].iloc[-1])
        nifty_prev = float(nifty_df['Close'].iloc[-2]) if len(nifty_df) > 1 else nifty_price
        nifty_change = ((nifty_price - nifty_prev) / nifty_prev) * 100
        
        nifty_sma20 = nifty_df['Close'].rolling(20).mean().iloc[-1]
        nifty_sma50 = nifty_df['Close'].rolling(50).mean().iloc[-1] if len(nifty_df) >= 50 else nifty_sma20
        nifty_rsi = calculate_rsi(nifty_df['Close']).iloc[-1]
        
        if pd.isna(nifty_rsi):
            nifty_rsi = 50
        
        vix = yf.Ticker("^INDIAVIX")
        vix_df = vix.history(period="5d")
        vix_value = float(vix_df['Close'].iloc[-1]) if not vix_df.empty else 15
        
        health_score = 50
        
        if nifty_price > nifty_sma20:
            health_score += 15
        else:
            health_score -= 15
        
        if nifty_price > nifty_sma50:
            health_score += 10
        else:
            health_score -= 10
        
        if nifty_rsi > 55:
            health_score += 15
        elif nifty_rsi > 45:
            health_score += 5
        elif nifty_rsi < 35:
            health_score -= 15
        elif nifty_rsi < 45:
            health_score -= 10
        
        if vix_value < 12:
            health_score += 20
        elif vix_value < 15:
            health_score += 10
        elif vix_value > 25:
            health_score -= 20
        elif vix_value > 18:
            health_score -= 10
        
        if nifty_sma20 > nifty_sma50:
            health_score += 10
        else:
            health_score -= 10
        
        health_score = max(0, min(100, health_score))
        
        if health_score >= 70:
            status = "BULLISH"
            color = "#28a745"
            icon = "🟢"
            action = "✅ Good environment for trading"
            sl_adjustment = "NORMAL"
        elif health_score >= 50:
            status = "NEUTRAL"
            color = "#ffc107"
            icon = "🟡"
            action = "⚠️ Be selective with new positions"
            sl_adjustment = "NORMAL"
        elif health_score >= 30:
            status = "WEAK"
            color = "#fd7e14"
            icon = "🟠"
            action = "⚠️ Tighten stop losses, avoid new longs"
            sl_adjustment = "TIGHTEN"
        else:
            status = "BEARISH"
            color = "#dc3545"
            icon = "🔴"
            action = "🚨 HIGH RISK - Consider reducing exposure"
            sl_adjustment = "AGGRESSIVE"
        
        message = f"NIFTY: ₹{nifty_price:,.0f} ({nifty_change:+.2f}%) | RSI: {nifty_rsi:.0f} | VIX: {vix_value:.1f}"
        
        return {
            'status': status,
            'health_score': health_score,
            'message': message,
            'color': color,
            'icon': icon,
            'action': action,
            'sl_adjustment': sl_adjustment,
            'nifty_price': nifty_price,
            'nifty_change': nifty_change,
            'nifty_rsi': nifty_rsi,
            'nifty_sma20': nifty_sma20,
            'nifty_sma50': nifty_sma50,
            'vix': vix_value,
            'above_sma20': nifty_price > nifty_sma20,
            'above_sma50': nifty_price > nifty_sma50
        }
    
    except Exception as e:
        logger.error(f"Market health check failed: {e}")
        return None

def get_stock_data_safe(ticker, period="6mo"):
    """Safely fetch stock data"""
    symbol = ticker if '.NS' in str(ticker) or '.BO' in str(ticker) else f"{ticker}.NS"
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            stock = yf.Ticker(symbol)
            df = stock.history(period=period)
            
            if not df.empty:
                df.reset_index(inplace=True)
                return df
                
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1 * (attempt + 1))
                continue
            logger.error(f"API Error for {ticker}: {str(e)}")
    
    return None

def calculate_holding_period(entry_date):
    """Calculate holding period in days"""
    if entry_date is None or entry_date == '' or (isinstance(entry_date, float) and pd.isna(entry_date)):
        return 0
    
    if isinstance(entry_date, str):
        entry_date = entry_date.strip()
        formats_to_try = [
            "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y",
            "%Y/%m/%d", "%d-%b-%Y", "%d %b %Y",
            "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S",
        ]
        
        parsed = None
        for fmt in formats_to_try:
            try:
                parsed = datetime.strptime(entry_date, fmt)
                break
            except ValueError:
                continue
        
        if parsed is None:
            return 0
        
        entry_date = parsed
    
    if hasattr(entry_date, 'to_pydatetime'):
        entry_date = entry_date.to_pydatetime()
    
    if isinstance(entry_date, datetime):
        now = get_ist_now()
        try:
            if entry_date.tzinfo is not None:
                delta = now - entry_date
            else:
                delta = now.replace(tzinfo=None) - entry_date
            return max(0, delta.days)
        except:
            return 0
    
    return 0

def send_email_alert(subject, html_content, sender, password, recipient):
    """Send email alert"""
    if not sender or not password or not recipient:
        log_email("❌ Missing email credentials")
        return False, "Missing email credentials"
    
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient
        msg.attach(MIMEText(html_content, 'html'))
        
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())
        server.quit()
        
        log_email(f"✅ Email sent: {subject}")
        return True, "Email sent successfully"
    
    except Exception as e:
        log_email(f"❌ Email failed: {str(e)}")
        return False, f"Email failed: {str(e)}"

def send_sl_update_email(ticker, old_sl, new_sl, reason, email_settings, result):
    """Send SL update email"""
    subject = f"🔄 Stop Loss Updated - {ticker}"
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 10px;">
            <div style="background: #17a2b8; color: white; padding: 20px; text-align: center;">
                <h1>🔄 Stop Loss Updated</h1>
                <p>{ticker}</p>
            </div>
            <div style="padding: 20px;">
                <p><strong>Old SL:</strong> ₹{old_sl}</p>
                <p><strong>New SL:</strong> ₹{new_sl:.2f}</p>
                <p><strong>Reason:</strong> {reason}</p>
                <p><strong>Current P&L:</strong> {result['pnl_percent']:+.2f}%</p>
            </div>
        </div>
    </body>
    </html>
    """
    send_email_alert(subject, html_content, email_settings['sender_email'], 
                    email_settings['sender_password'], email_settings['recipient_email'])

def send_target_update_email(ticker, old_target, new_target, target_num, reason, email_settings, result):
    """Send target update email"""
    subject = f"🎯 Target Updated - {ticker}"
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 10px;">
            <div style="background: #28a745; color: white; padding: 20px; text-align: center;">
                <h1>🎯 Target Updated</h1>
                <p>{ticker}</p>
            </div>
            <div style="padding: 20px;">
                <p><strong>Target {target_num}:</strong> ₹{old_target} → ₹{new_target:.2f}</p>
                <p><strong>Reason:</strong> {reason}</p>
                <p><strong>Upside Score:</strong> {result.get('upside_score', 0)}%</p>
            </div>
        </div>
    </body>
    </html>
    """
    send_email_alert(subject, html_content, email_settings['sender_email'], 
                    email_settings['sender_password'], email_settings['recipient_email'])

def send_exit_email(ticker, exit_price, pnl_amount, reason, email_settings, result):
    """Send exit email"""
    header_color = "#28a745" if pnl_amount > 0 else "#dc3545"
    status_emoji = "✅" if pnl_amount > 0 else "❌"
    
    subject = f"{status_emoji} Position Closed - {ticker}"
    html_content = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 10px;">
            <div style="background: {header_color}; color: white; padding: 20px; text-align: center;">
                <h1>{status_emoji} Position Closed</h1>
                <p>{ticker}</p>
            </div>
            <div style="padding: 20px;">
                <p><strong>P&L:</strong> ₹{pnl_amount:+,.0f}</p>
                <p><strong>Exit Reason:</strong> {reason}</p>
                <p><strong>Exit Price:</strong> ₹{exit_price:,.2f}</p>
            </div>
        </div>
    </body>
    </html>
    """
    send_email_alert(subject, html_content, email_settings['sender_email'], 
                    email_settings['sender_password'], email_settings['recipient_email'])

# ==========================================================================
# SMART ANALYSIS FUNCTION (Simplified version)
# ==========================================================================

@st.cache_data(ttl=60)
def smart_analyze_position(ticker, position_type, entry_price, quantity, stop_loss,
                          target1, target2, trail_threshold=2.0, sl_alert_threshold=50):
    """Analyze a position with all features"""
    df = get_stock_data_safe(ticker, period="6mo")
    if df is None or df.empty:
        return None
    
    try:
        current_price = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2]) if len(df) > 1 else current_price
        day_change = ((current_price - prev_close) / prev_close) * 100
        day_high = float(df['High'].iloc[-1])
        day_low = float(df['Low'].iloc[-1])
    except Exception as e:
        return None
    
    # Basic P&L
    if position_type == "LONG":
        pnl_percent = ((current_price - entry_price) / entry_price) * 100
        pnl_amount = (current_price - entry_price) * quantity
    else:
        pnl_percent = ((entry_price - current_price) / entry_price) * 100
        pnl_amount = (entry_price - current_price) * quantity
    
    # Technical Indicators
    rsi = float(calculate_rsi(df['Close']).iloc[-1])
    if pd.isna(rsi):
        rsi = 50.0
    
    macd, signal, histogram = calculate_macd(df['Close'])
    macd_hist = float(histogram.iloc[-1]) if len(histogram) > 0 else 0
    if pd.isna(macd_hist):
        macd_hist = 0
    macd_signal = "BULLISH" if macd_hist > 0 else "BEARISH"
    
    # Momentum
    momentum_score, momentum_trend, momentum_components = calculate_momentum_score(df)
    
    # Volume
    volume_signal, volume_ratio, volume_desc, volume_trend = analyze_volume(df)
    
    # SL check
    if position_type == "LONG":
        sl_risk = min(100, max(0, 100 - (((current_price - stop_loss) / entry_price) * 100)))
        sl_hit = current_price <= stop_loss
    else:
        sl_risk = min(100, max(0, 100 - (((stop_loss - current_price) / entry_price) * 100)))
        sl_hit = current_price >= stop_loss
    
    # Target check
    if position_type == "LONG":
        target1_hit = current_price >= target1
        target2_hit = current_price >= target2
    else:
        target1_hit = current_price <= target1
        target2_hit = current_price <= target2
    
    # Risk-Reward
    if position_type == "LONG":
        risk = entry_price - stop_loss
        reward = target1 - entry_price
    else:
        risk = stop_loss - entry_price
        reward = entry_price - target1
    
    risk_reward_ratio = safe_divide(reward, risk, default=0.0)
    
    # Determine overall status
    overall_status = 'OK'
    overall_action = 'HOLD'
    alerts = []
    
    if sl_hit:
        overall_status = 'CRITICAL'
        overall_action = 'EXIT'
        alerts.append({
            'priority': 'CRITICAL',
            'type': '🚨 STOP LOSS HIT',
            'message': f'Price hit SL!',
            'action': 'EXIT NOW'
        })
    elif target2_hit:
        overall_status = 'SUCCESS'
        overall_action = 'BOOK_PROFITS'
        alerts.append({
            'priority': 'HIGH',
            'type': '🎯 TARGET 2 HIT',
            'message': f'Both targets achieved!',
            'action': 'BOOK PROFITS'
        })
    elif target1_hit:
        overall_status = 'OPPORTUNITY'
        overall_action = 'HOLD_EXTEND'
        alerts.append({
            'priority': 'INFO',
            'type': '🎯 TARGET 1 HIT',
            'message': f'First target achieved!',
            'action': 'Consider extending'
        })
    elif sl_risk >= sl_alert_threshold:
        overall_status = 'WARNING'
        overall_action = 'WATCH'
        alerts.append({
            'priority': 'HIGH',
            'type': '⚠️ HIGH SL RISK',
            'message': f'Risk: {sl_risk}%',
            'action': 'Watch closely'
        })
    elif pnl_percent >= 2:
        overall_status = 'GOOD'
        overall_action = 'HOLD'
    
    return {
        'ticker': ticker,
        'position_type': position_type,
        'entry_price': entry_price,
        'current_price': current_price,
        'quantity': quantity,
        'pnl_percent': pnl_percent,
        'pnl_amount': pnl_amount,
        'day_change': day_change,
        'day_high': day_high,
        'day_low': day_low,
        'stop_loss': stop_loss,
        'target1': target1,
        'target2': target2,
        'rsi': rsi,
        'macd_hist': macd_hist,
        'macd_signal': macd_signal,
        'momentum_score': momentum_score,
        'momentum_trend': momentum_trend,
        'volume_signal': volume_signal,
        'volume_ratio': volume_ratio,
        'volume_desc': volume_desc,
        'sl_risk': sl_risk,
        'sl_hit': sl_hit,
        'target1_hit': target1_hit,
        'target2_hit': target2_hit,
        'risk_reward_ratio': risk_reward_ratio,
        'alerts': alerts,
        'overall_status': overall_status,
        'overall_action': overall_action,
        'trail_stop': stop_loss,
        'should_trail': False,
        'df': df
    }

# ==========================================================================
# SIDEBAR CONFIGURATION
# ==========================================================================

def render_sidebar():
    """Render sidebar settings"""
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        
        # Email Configuration
        st.markdown("### 📧 Email Alerts")
        
        YOUR_EMAIL = st.secrets.get("EMAIL_ADDRESS", "")
        YOUR_APP_PASSWORD = st.secrets.get("EMAIL_PASSWORD", "")
        YOUR_RECIPIENT = st.secrets.get("RECIPIENT_EMAIL", "")
        
        credentials_configured = bool(
            YOUR_EMAIL and YOUR_APP_PASSWORD and "@" in YOUR_EMAIL
        )
        
        if 'email_alerts_enabled' not in st.session_state:
            st.session_state.email_alerts_enabled = False
        
        email_enabled = st.checkbox(
            "Enable Email Alerts",
            value=st.session_state.email_alerts_enabled,
            key="email_enabled_checkbox"
        )
        
        if email_enabled != st.session_state.email_alerts_enabled:
            st.session_state.email_alerts_enabled = email_enabled
        
        email_settings = {
            'enabled': False,
            'sender_email': '',
            'sender_password': '',
            'recipient_email': '',
            'cooldown': 15
        }
        
        if email_enabled:
            if credentials_configured:
                email_settings['enabled'] = True
                email_settings['sender_email'] = YOUR_EMAIL
                email_settings['sender_password'] = YOUR_APP_PASSWORD
                email_settings['recipient_email'] = YOUR_RECIPIENT if YOUR_RECIPIENT else YOUR_EMAIL
                st.success("✅ Email configured!")
            else:
                st.warning("⚠️ Configure EMAIL_ADDRESS and EMAIL_PASSWORD in secrets")
        
        st.divider()
        
        # Auto-Refresh
        st.markdown("### 🔄 Auto-Refresh")
        auto_refresh = st.checkbox("Enable Auto-Refresh", value=True)
        refresh_interval = st.slider("Interval (seconds)", 30, 300, 60)
        
        st.divider()
        
        # Alert Thresholds
        st.markdown("### 🎯 Alert Thresholds")
        trail_sl_trigger = st.slider("Trail SL after Profit %", 0.5, 10.0, 2.0, step=0.5)
        sl_risk_threshold = st.slider("SL Risk Alert Threshold", 30, 90, 50)
        
        return {
            'email_settings': email_settings,
            'auto_refresh': auto_refresh,
            'refresh_interval': refresh_interval,
            'trail_sl_trigger': trail_sl_trigger,
            'sl_risk_threshold': sl_risk_threshold,
        }

# ==========================================================================
# AUTHENTICATE USER (IMPORT AUTH UI)
# ==========================================================================

# Import auth UI functions
from auth_ui import init_auth_session_state, show_login_register_ui

# ==========================================================================
# MAIN APPLICATION
# ==========================================================================

def main():
    """Main application"""
    # Initialize auth session state
    init_auth_session_state()
    
    # Check if user is authenticated
    if 'user_id' not in st.session_state or st.session_state.user_id is None:
        # Show login/register UI
        show_login_register_ui()
        return
    
    user_id = st.session_state.user_id
    
    # Header
    st.markdown('<h1 class="main-header">🧠 Smart Portfolio Monitor v6.0</h1>', unsafe_allow_html=True)
    
    # Render sidebar
    settings = render_sidebar()
    
    # Market Status
    is_open, market_status, market_msg, market_icon = is_market_hours()
    ist_now = get_ist_now()
    
    # HEADER ROW
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        st.markdown(f"### {market_icon} {market_status}")
        st.caption(market_msg)
    
    with col2:
        st.markdown(f"### 🕐 {ist_now.strftime('%H:%M:%S')} IST")
        st.caption(ist_now.strftime('%A, %B %d, %Y'))
    
    with col3:
        if st.button("🔄 Refresh", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.rerun()
    
    st.divider()
    
    # Market Health
    market_health = get_market_health()
    
    if market_health:
        st.markdown(f"""
        <div style='background:{market_health['color']}20; padding:20px; border-radius:12px; 
                    border-left:5px solid {market_health['color']}; margin:15px 0;'>
            <div style='display:flex; justify-content:space-between; align-items:center;'>
                <div>
                    <h2 style='margin:0; color:{market_health['color']};'>
                        {market_health['icon']} Market Health: {market_health['status']}
                    </h2>
                    <p style='margin:8px 0; font-size:1.1em;'>{market_health['message']}</p>
                    <p style='margin:8px 0; font-weight:bold;'>{market_health['action']}</p>
                </div>
                <div style='text-align:center; min-width:100px;'>
                    <h1 style='margin:0; color:{market_health['color']};'>{market_health['health_score']}</h1>
                    <p style='margin:0;'>Health Score</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # Load Portfolio from MySQL
    portfolio = load_portfolio_mysql(user_id)
    
    if portfolio is None or len(portfolio) == 0:
        st.warning("⚠️ No active positions found!")
        return
    
    # Analyze all positions
    results = []
    progress_bar = st.progress(0, text="Analyzing positions...")
    
    for i, (_, row) in enumerate(portfolio.iterrows()):
        ticker = str(row['Ticker']).strip()
        progress_bar.progress((i + 0.5) / len(portfolio), text=f"Analyzing {ticker}...")
        
        result = smart_analyze_position(
            ticker,
            str(row['Position']).upper().strip(),
            float(row['Entry_Price']),
            int(row.get('Quantity', 1)),
            float(row['Stop_Loss']),
            float(row['Target_1']),
            float(row.get('Target_2', row['Target_1'] * 1.1)),
            settings['trail_sl_trigger'],
            settings['sl_risk_threshold']
        )
        
        if result:
            results.append(result)
        
        progress_bar.progress((i + 1) / len(portfolio))
    
    progress_bar.empty()
    
    if not results:
        st.error("❌ Could not fetch stock data")
        return
    
    # Summary Metrics
    total_pnl = sum(r['pnl_amount'] for r in results)
    total_invested = sum(r['entry_price'] * r['quantity'] for r in results)
    
    st.markdown("### 📊 Portfolio Summary")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("💰 Total P&L", f"₹{total_pnl:+,.0f}")
    with col2:
        st.metric("📊 Positions", len(results))
    with col3:
        critical = sum(1 for r in results if r['overall_status'] == 'CRITICAL')
        st.metric("🔴 Critical", critical)
    with col4:
        warning = sum(1 for r in results if r['overall_status'] == 'WARNING')
        st.metric("🟡 Warning", warning)
    with col5:
        good = sum(1 for r in results if r['overall_status'] in ['GOOD', 'SUCCESS'])
        st.metric("🟢 Good", good)
    
    st.divider()
    
    # Display Each Position
    for r in sorted(results, key=lambda x: ['CRITICAL', 'WARNING', 'OPPORTUNITY', 'SUCCESS', 'GOOD', 'OK'].index(x['overall_status'])):
        with st.expander(
            f"**{r['ticker']}** | {r['position_type']} | P&L: {r['pnl_percent']:+.2f}% | "
            f"SL Risk: {r['sl_risk']}% | {r['overall_action']}",
            expanded=(r['overall_status'] in ['CRITICAL', 'WARNING'])
        ):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown("##### 💰 Position")
                st.write(f"**Entry:** ₹{r['entry_price']:,.2f}")
                st.write(f"**Current:** ₹{r['current_price']:,.2f}")
                st.write(f"**Qty:** {r['quantity']}")
                pnl_color = "green" if r['pnl_percent'] >= 0 else "red"
                st.markdown(f"**P&L:** <span style='color:{pnl_color};'>{r['pnl_percent']:+.2f}%</span>",
                           unsafe_allow_html=True)
            
            with col2:
                st.markdown("##### 🎯 Levels")
                st.write(f"**SL:** ₹{r['stop_loss']:,.2f}")
                st.write(f"**T1:** ₹{r['target1']:,.2f}")
                st.write(f"**T2:** ₹{r['target2']:,.2f}")
            
            with col3:
                st.markdown("##### 📊 Indicators")
                st.write(f"**RSI:** {r['rsi']:.1f}")
                st.write(f"**MACD:** {r['macd_signal']}")
                st.write(f"**Momentum:** {r['momentum_score']:.0f}")
            
            with col4:
                st.markdown("##### 🛡️ Risk")
                st.write(f"**SL Risk:** {r['sl_risk']}%")
                st.write(f"**R:R:** 1:{r['risk_reward_ratio']:.2f}")
                st.write(f"**Volume:** {r['volume_signal']}")
            
            st.divider()
            
            # Alerts
            if r['alerts']:
                for alert in r['alerts']:
                    if alert['priority'] == 'CRITICAL':
                        st.error(f"**{alert['type']}**: {alert['message']} → {alert['action']}")
                    elif alert['priority'] == 'HIGH':
                        st.warning(f"**{alert['type']}**: {alert['message']} → {alert['action']}")
                    else:
                        st.info(f"**{alert['type']}**: {alert['message']}")
            
            st.divider()
            
            # Exit Controls
            st.markdown("##### 🚪 Exit Controls")
            
            if r['overall_action'] in ['EXIT', 'BOOK_PROFITS']:
                exit_price = st.number_input(
                    f"Exit Price for {r['ticker']}",
                    value=float(round_to_tick_size(r['current_price'])),
                    step=0.05,
                    key=f"exit_{r['ticker']}"
                )
                
                if st.button(f"Exit {r['ticker']}", key=f"btn_{r['ticker']}", use_container_width=True, type="primary"):
                    if r['position_type'] == 'LONG':
                        pnl = (exit_price - r['entry_price']) * r['quantity']
                    else:
                        pnl = (r['entry_price'] - exit_price) * r['quantity']
                    
                    success, msg = mark_position_inactive(
                        user_id, r['ticker'], exit_price, pnl, "Manual Exit",
                        should_send_email=True,
                        email_settings=settings["email_settings"],
                        result=r
                    )
                    
                    if success:
                        st.success(f"✅ {msg}")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")
    
    st.divider()
    
    # Auto-refresh
    if settings['auto_refresh'] and is_open:
        if HAS_AUTOREFRESH:
            st_autorefresh(interval=settings['refresh_interval'] * 1000, limit=None)

if __name__ == "__main__":
    main()
