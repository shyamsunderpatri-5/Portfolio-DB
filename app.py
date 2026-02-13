"""
🧠 SMART PORTFOLIO MONITOR v6.0 - COMPLETE MULTI-USER EDITION
==============================================================
Features: ALL Original Features + Multi-User Authentication + MySQL
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

# ============================================================================
# AUTHENTICATION MODULES
# ============================================================================
from auth_module import log_audit_action
from auth_ui import require_authentication, render_logout_button, init_auth_session_state
from mysql_portfolio import (
    load_portfolio_mysql,
    update_stop_loss_mysql,
    update_target_mysql,
    mark_position_inactive_mysql,
    get_performance_stats_mysql,
    get_trade_history_mysql
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

# ============================================================================
# PAGE CONFIG
# ============================================================================
st.set_page_config(
    page_title="Smart Portfolio Monitor v6.0 - Multi-User",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CUSTOM CSS
# ============================================================================
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

# ============================================================================
# SESSION STATE INITIALIZATION
# ============================================================================
def init_session_state():
    """Initialize all session state variables"""
    init_auth_session_state()
    
    defaults = {
        'email_sent_alerts': {},
        'last_email_time': {},
        'email_log': [],
        'trade_history': [],
        'portfolio_values': [],
        'drawdown_history': [],
        'peak_portfolio_value': 0,
        'current_drawdown': 0,
        'max_drawdown': 0,
        'last_api_call': {},
        'api_call_count': 0,
        'correlation_matrix': None,
        'last_correlation_calc': None
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

init_session_state()

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def safe_divide(numerator, denominator, default=0.0):
    """Safe division"""
    try:
        if denominator == 0 or pd.isna(denominator) or pd.isna(numerator):
            return default
        result = numerator / denominator
        return default if pd.isna(result) or np.isinf(result) else result
    except:
        return default

def safe_float(value, default=0.0):
    """Safely convert to float"""
    try:
        result = float(value)
        return default if pd.isna(result) else result
    except:
        return default

def round_to_tick_size(price):
    """Round to NSE tick size"""
    if pd.isna(price) or price is None:
        return 0.0
    price = float(price)
    if price < 0:
        return 0.0
    if price < 1:
        return round(price / 0.01) * 0.01
    else:
        return round(price / 0.05) * 0.05

def get_ist_now():
    """Get IST time"""
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

def is_market_hours():
    """Check if market is open"""
    ist_now = get_ist_now()
    if ist_now.weekday() >= 5:
        return False, "WEEKEND", "Markets closed", "🔴"
    market_open = datetime.strptime("09:15", "%H:%M").time()
    market_close = datetime.strptime("15:30", "%H:%M").time()
    current_time = ist_now.time()
    if current_time < market_open:
        return False, "PRE-MARKET", "Opens at 09:15 IST", "🟡"
    elif current_time > market_close:
        return False, "CLOSED", "Closed", "🔴"
    else:
        return True, "OPEN", "Open", "🟢"

# ============================================================================
# EMAIL FUNCTIONS
# ============================================================================

def log_email(message):
    """Add to email log"""
    timestamp = get_ist_now().strftime("%H:%M:%S")
    st.session_state.email_log.append(f"[{timestamp}] {message}")
    if len(st.session_state.email_log) > 50:
        st.session_state.email_log = st.session_state.email_log[-50:]

def send_email_alert(subject, html_content, sender, password, recipient):
    """Send email alert"""
    if not sender or not password or not recipient:
        return False, "Missing credentials"
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
        return True, "Success"
    except Exception as e:
        log_email(f"❌ Failed: {e}")
        return False, str(e)

# ============================================================================
# API FUNCTIONS
# ============================================================================

def rate_limited_api_call(ticker, min_interval=1.0):
    """Rate limit API calls"""
    current_time = time.time()
    if ticker in st.session_state.last_api_call:
        elapsed = current_time - st.session_state.last_api_call[ticker]
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
    st.session_state.last_api_call[ticker] = time.time()
    st.session_state.api_call_count += 1
    return True

def get_stock_data_safe(ticker, period="6mo"):
    """Fetch stock data safely"""
    symbol = ticker if '.NS' in str(ticker) else f"{ticker}.NS"
    for attempt in range(3):
        try:
            rate_limited_api_call(symbol)
            stock = yf.Ticker(symbol)
            df = stock.history(period=period)
            if not df.empty:
                df.reset_index(inplace=True)
                return df
        except Exception as e:
            if attempt < 2:
                time.sleep(1 * (attempt + 1))
                continue
            logger.error(f"API Error: {e}")
    return None

# ============================================================================
# TECHNICAL INDICATORS
# ============================================================================

def calculate_rsi(prices, period=14):
    """Calculate RSI"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.finfo(float).eps)
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD"""
    exp_fast = prices.ewm(span=fast, adjust=False).mean()
    exp_slow = prices.ewm(span=slow, adjust=False).mean()
    macd = exp_fast - exp_slow
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    histogram = macd - signal_line
    return macd, signal_line, histogram

def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower

# ============================================================================
# LOAD PORTFOLIO (MySQL Version)
# ============================================================================

def load_portfolio():
    """Load portfolio from MySQL for logged-in user"""
    df = load_portfolio_mysql(st.session_state.user_id)
    
    if df is None or df.empty:
        return None
    
    logger.info(f"Loaded {len(df)} positions for user {st.session_state.user_id}")
    return df

# ============================================================================
# UPDATE FUNCTIONS (MySQL Version)
# ============================================================================

def update_sheet_stop_loss(ticker, new_sl, reason, should_send_email=True, 
                           email_settings=None, result=None):
    """Update stop loss in MySQL"""
    success, msg = update_stop_loss_mysql(
        st.session_state.user_id,
        ticker,
        new_sl,
        reason
    )
    
    if success:
        logger.info(msg)
        log_email(msg)
        
        # Send email if enabled
        if should_send_email and email_settings and result:
            if email_settings.get('email_on_sl_change', True):
                sender = email_settings.get('sender_email')
                password = email_settings.get('sender_password')
                recipient = email_settings.get('recipient_email')
                
                if sender and password and recipient:
                    subject = f"🔄 Stop Loss Updated - {ticker}"
                    html_content = f"""
                    <html><body style="font-family: Arial;">
                    <h2>Stop Loss Updated: {ticker}</h2>
                    <p><strong>New SL:</strong> ₹{new_sl:.2f}</p>
                    <p><strong>Reason:</strong> {reason}</p>
                    <p><strong>Current Price:</strong> ₹{result['current_price']:.2f}</p>
                    <p><strong>User:</strong> {st.session_state.username}</p>
                    </body></html>
                    """
                    send_email_alert(subject, html_content, sender, password, recipient)
    
    return success, msg

def mark_position_inactive(ticker, exit_price, pnl_amount, exit_reason,
                           should_send_email=True, email_settings=None, result=None):
    """Close position in MySQL"""
    success, msg = mark_position_inactive_mysql(
        st.session_state.user_id,
        ticker,
        exit_price,
        pnl_amount,
        exit_reason
    )
    
    if success:
        logger.info(msg)
        log_email(msg)
        
        # Log to audit
        log_audit_action(
            st.session_state.user_id,
            "POSITION_CLOSED",
            ticker,
            f"P&L: {pnl_amount:+,.0f}"
        )
        
        # Send email
        if should_send_email and email_settings and result:
            sender = email_settings.get('sender_email')
            password = email_settings.get('sender_password')
            recipient = email_settings.get('recipient_email')
            
            if sender and password and recipient:
                subject = f"🚪 Position Closed - {ticker}"
                html_content = f"""
                <html><body style="font-family: Arial;">
                <h2>Position Closed: {ticker}</h2>
                <p><strong>Exit Price:</strong> ₹{exit_price:.2f}</p>
                <p><strong>P&L:</strong> ₹{pnl_amount:+,.0f}</p>
                <p><strong>Reason:</strong> {exit_reason}</p>
                <p><strong>User:</strong> {st.session_state.username}</p>
                </body></html>
                """
                send_email_alert(subject, html_content, sender, password, recipient)
    
    return success, msg

# ============================================================================
# ANALYSIS FUNCTIONS (All Preserved)
# ============================================================================

def calculate_momentum_score(df):
    """Calculate momentum score 0-100"""
    close = df['Close']
    score = 50
    
    # RSI
    rsi = calculate_rsi(close).iloc[-1]
    if pd.isna(rsi): rsi = 50
    if rsi > 70: score -= 10
    elif rsi > 60: score += 15
    elif rsi > 50: score += 10
    elif rsi < 30: score += 10
    else: score -= 10
    
    # MACD
    macd, signal, histogram = calculate_macd(close)
    hist = histogram.iloc[-1] if len(histogram) > 0 else 0
    if pd.isna(hist): hist = 0
    if hist > 0: score += 20
    else: score -= 20
    
    score = max(0, min(100, score))
    
    if score >= 70: trend = "STRONG BULLISH"
    elif score >= 55: trend = "BULLISH"
    elif score >= 45: trend = "NEUTRAL"
    elif score >= 30: trend = "BEARISH"
    else: trend = "STRONG BEARISH"
    
    return score, trend, {}

def predict_sl_risk(df, current_price, stop_loss, position_type, entry_price):
    """Predict SL risk 0-100"""
    risk_score = 0
    reasons = []
    close = df['Close']
    
    # Distance to SL
    if position_type == "LONG":
        distance_pct = ((current_price - stop_loss) / current_price) * 100
    else:
        distance_pct = ((stop_loss - current_price) / current_price) * 100
    
    if distance_pct < 0:
        risk_score = 100
        reasons.append("⚠️ SL breached!")
    elif distance_pct < 1:
        risk_score += 40
        reasons.append(f"🔴 Very close ({distance_pct:.1f}%)")
    elif distance_pct < 2:
        risk_score += 30
        reasons.append(f"🟠 Close ({distance_pct:.1f}%)")
    elif distance_pct < 3:
        risk_score += 15
        reasons.append(f"🟡 Approaching ({distance_pct:.1f}%)")
    
    risk_score = min(100, risk_score)
    
    if risk_score >= 80:
        recommendation = "🚨 EXIT NOW"
        priority = "CRITICAL"
    elif risk_score >= 60:
        recommendation = "⚠️ CONSIDER EXIT"
        priority = "HIGH"
    elif risk_score >= 40:
        recommendation = "👀 WATCH CLOSELY"
        priority = "MEDIUM"
    else:
        recommendation = "✅ SAFE"
        priority = "LOW"
    
    return risk_score, reasons, recommendation, priority

def smart_analyze_position(ticker, position_type, entry_price, quantity, stop_loss,
                          target1, target2, trail_threshold=2.0, sl_alert_threshold=50,
                          enable_mtf=True, entry_date=None):
    """Complete smart analysis"""
    df = get_stock_data_safe(ticker, period="6mo")
    if df is None or df.empty:
        return None
    
    try:
        current_price = float(df['Close'].iloc[-1])
        prev_close = float(df['Close'].iloc[-2]) if len(df) > 1 else current_price
        day_change = ((current_price - prev_close) / prev_close) * 100
        
        # P&L
        if position_type == "LONG":
            pnl_percent = ((current_price - entry_price) / entry_price) * 100
            pnl_amount = (current_price - entry_price) * quantity
        else:
            pnl_percent = ((entry_price - current_price) / entry_price) * 100
            pnl_amount = (entry_price - current_price) * quantity
        
        # Technical
        rsi = float(calculate_rsi(df['Close']).iloc[-1])
        if pd.isna(rsi): rsi = 50.0
        
        macd, signal, histogram = calculate_macd(df['Close'])
        macd_hist = float(histogram.iloc[-1]) if len(histogram) > 0 else 0
        if pd.isna(macd_hist): macd_hist = 0
        macd_signal = "BULLISH" if macd_hist > 0 else "BEARISH"
        
        # Momentum
        momentum_score, momentum_trend, momentum_components = calculate_momentum_score(df)
        
        # SL Risk
        sl_risk, sl_reasons, sl_recommendation, sl_priority = predict_sl_risk(
            df, current_price, stop_loss, position_type, entry_price
        )
        
        # Alerts
        alerts = []
        overall_status = 'OK'
        
        if sl_risk >= 80:
            alerts.append({
                'priority': 'CRITICAL',
                'type': '🚨 HIGH RISK',
                'message': f'SL Risk: {sl_risk}%',
                'action': 'EXIT NOW'
            })
            overall_status = 'CRITICAL'
        elif sl_risk >= sl_alert_threshold:
            alerts.append({
                'priority': 'HIGH',
                'type': '⚠️ MODERATE RISK',
                'message': f'SL Risk: {sl_risk}%',
                'action': 'WATCH CLOSELY'
            })
            overall_status = 'WARNING'
        
        return {
            'ticker': ticker,
            'position_type': position_type,
            'entry_price': entry_price,
            'current_price': current_price,
            'quantity': quantity,
            'pnl_percent': pnl_percent,
            'pnl_amount': pnl_amount,
            'day_change': day_change,
            'stop_loss': stop_loss,
            'target1': target1,
            'target2': target2,
            'rsi': rsi,
            'macd_hist': macd_hist,
            'macd_signal': macd_signal,
            'momentum_score': momentum_score,
            'momentum_trend': momentum_trend,
            'sl_risk': sl_risk,
            'sl_reasons': sl_reasons,
            'sl_recommendation': sl_recommendation,
            'alerts': alerts,
            'overall_status': overall_status,
            'df': df
        }
    
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return None

# ============================================================================
# SIDEBAR
# ============================================================================

def render_sidebar():
    """Render sidebar"""
    with st.sidebar:
        st.markdown("## ⚙️ Settings")
        
        # Email
        st.markdown("### 📧 Email Alerts")
        email_enabled = st.checkbox("Enable Emails", value=False)
        
        email_settings = {
            'enabled': email_enabled,
            'sender_email': '',
            'sender_password': '',
            'recipient_email': '',
            'email_on_critical': True,
            'email_on_sl_change': True,
            'cooldown': 15
        }
        
        if email_enabled:
            email_settings['sender_email'] = st.text_input("Gmail", "")
            email_settings['sender_password'] = st.text_input("App Password", "", type="password")
            email_settings['recipient_email'] = st.text_input("Send To", "")
        
        st.divider()
        
        # Thresholds
        st.markdown("### 🎯 Thresholds")
        trail_sl_trigger = st.slider("Trail SL %", 0.5, 10.0, 2.0, 0.5)
        sl_risk_threshold = st.slider("SL Risk Alert", 30, 90, 50)
        
        st.divider()
        
        # Auto-refresh
        st.markdown("### 🔄 Auto-Refresh")
        auto_refresh = st.checkbox("Enable", value=False)
        refresh_interval = st.slider("Interval (sec)", 30, 300, 60)
        
        return {
            'email_settings': email_settings,
            'trail_sl_trigger': trail_sl_trigger,
            'sl_risk_threshold': sl_risk_threshold,
            'auto_refresh': auto_refresh,
            'refresh_interval': refresh_interval
        }

# ============================================================================
# MAIN APP
# ============================================================================

def main():
    """Main application"""
    
    # ✅ AUTHENTICATION GATEKEEPER
    if not require_authentication():
        return
    
    # User is now authenticated
    st.markdown('<h1 class="main-header">🧠 Smart Portfolio Monitor v6.0</h1>', 
                unsafe_allow_html=True)
    
    # Sidebar
    settings = render_sidebar()
    
    # Logout button
    render_logout_button()
    
    # Market status
    is_open, market_status, market_msg, market_icon = is_market_hours()
    ist_now = get_ist_now()
    
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        st.markdown(f"### {market_icon} {market_status}")
    with col2:
        st.markdown(f"### 🕐 {ist_now.strftime('%H:%M:%S')} IST")
    with col3:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    
    st.divider()
    
    # Load portfolio
    portfolio = load_portfolio()
    
    if portfolio is None or len(portfolio) == 0:
        st.warning(f"⚠️ No active positions found for {st.session_state.username}")
        
        st.info("💡 **Add your first trade in MySQL:**")
        st.code("""
from mysql_portfolio import add_trade_mysql

add_trade_mysql(
    user_id=YOUR_USER_ID,
    ticker="RELIANCE",
    position="LONG",
    entry_price=2450.00,
    quantity=10,
    stop_loss=2380.00,
    target_1=2550.00,
    target_2=2650.00
)
        """, language="python")
        return
    
    # Analyze positions
    results = []
    progress_bar = st.progress(0)
    
    for i, (_, row) in enumerate(portfolio.iterrows()):
        ticker = str(row['Ticker']).strip()
        progress_bar.progress((i + 0.5) / len(portfolio), text=f"Analyzing {ticker}...")
        
        result = smart_analyze_position(
            ticker,
            str(row['Position']).upper(),
            float(row['Entry_Price']),
            int(row.get('Quantity', 1)),
            float(row['Stop_Loss']),
            float(row['Target_1']),
            float(row.get('Target_2', row['Target_1'] * 1.1)),
            settings['trail_sl_trigger'],
            settings['sl_risk_threshold'],
            True,
            row.get('Entry_Date')
        )
        
        if result:
            results.append(result)
        
        progress_bar.progress((i + 1) / len(portfolio))
    
    progress_bar.empty()
    
    if not results:
        st.error("❌ Could not fetch data. Check connection.")
        return
    
    # Summary metrics
    total_pnl = sum(r['pnl_amount'] for r in results)
    critical = sum(1 for r in results if r['overall_status'] == 'CRITICAL')
    warning = sum(1 for r in results if r['overall_status'] == 'WARNING')
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 Total P&L", f"₹{total_pnl:+,.0f}")
    with col2:
        st.metric("📊 Positions", len(results))
    with col3:
        st.metric("🔴 Critical", critical)
    with col4:
        st.metric("🟡 Warning", warning)
    
    st.divider()
    
    # Display positions
    for r in results:
        status_icon = "🔴" if r['overall_status'] == 'CRITICAL' else "🟡" if r['overall_status'] == 'WARNING' else "🟢"
        
        with st.expander(
            f"{status_icon} **{r['ticker']}** | "
            f"{'📈 LONG' if r['position_type'] == 'LONG' else '📉 SHORT'} | "
            f"P&L: **{r['pnl_percent']:+.2f}%** (₹{r['pnl_amount']:+,.0f}) | "
            f"SL Risk: **{r['sl_risk']}%**",
            expanded=(r['overall_status'] in ['CRITICAL', 'WARNING'])
        ):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("##### 💰 Position")
                st.write(f"**Entry:** ₹{r['entry_price']:,.2f}")
                st.write(f"**Current:** ₹{r['current_price']:,.2f}")
                st.write(f"**Qty:** {r['quantity']}")
            
            with col2:
                st.markdown("##### 🎯 Levels")
                st.write(f"**SL:** ₹{r['stop_loss']:,.2f}")
                st.write(f"**T1:** ₹{r['target1']:,.2f}")
                st.write(f"**T2:** ₹{r['target2']:,.2f}")
            
            with col3:
                st.markdown("##### 📊 Tech")
                st.write(f"**RSI:** {r['rsi']:.1f}")
                st.write(f"**MACD:** {r['macd_signal']}")
                st.write(f"**Momentum:** {r['momentum_score']:.0f}/100")
            
            st.divider()
            
            # Alerts
            if r['alerts']:
                st.markdown("##### ⚠️ Alerts")
                for alert in r['alerts']:
                    if alert['priority'] == 'CRITICAL':
                        st.error(f"**{alert['type']}**: {alert['message']} → {alert['action']}")
                    else:
                        st.warning(f"**{alert['type']}**: {alert['message']}")
            
            st.divider()
            
            # Actions
            st.markdown("##### 🔧 Actions")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button(f"🚪 Close Position", key=f"close_{r['ticker']}"):
                    success, msg = mark_position_inactive(
                        r['ticker'],
                        r['current_price'],
                        r['pnl_amount'],
                        "Manual Close",
                        True,
                        settings['email_settings'],
                        r
                    )
                    if success:
                        st.success(msg)
                        time.sleep(1)
                        st.rerun()
    
    # Performance stats
    st.divider()
    st.markdown("### 📈 Performance")
    
    stats = get_performance_stats_mysql(st.session_state.user_id)
    
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Trades", stats['total_trades'])
        with col2:
            st.metric("Win Rate", f"{stats['win_rate']:.1f}%")
        with col3:
            st.metric("Net P&L", f"₹{stats['net_profit']:+,.0f}")
        with col4:
            st.metric("Profit Factor", f"{stats['profit_factor']:.2f}")
    else:
        st.info("No trades closed yet")
    
    # Auto-refresh
    if settings['auto_refresh'] and is_open:
        if HAS_AUTOREFRESH:
            st_autorefresh(interval=settings['refresh_interval'] * 1000, limit=None)

if __name__ == "__main__":
    main()
