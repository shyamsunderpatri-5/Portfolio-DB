"""
🧠 SMART PORTFOLIO MONITOR v6.0 - ADVANCED EDITION
===================================================
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

# ==========================================================================
# RUN APPLICATION
# ==========================================================================

def main():
    """
    Main application entry point
    """
    # Header
    st.markdown('<h1 class="main-header">🧠 Smart Portfolio Monitor v6.0</h1>', unsafe_allow_html=True)
    # Render sidebar and get settings
    settings = render_sidebar()
    # Market Status
    is_open, market_status, market_msg, market_icon = is_market_hours()
    ist_now = get_ist_now()
    # HEADER ROW (Market Status + Time + Refresh Button)
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
                    <p style='margin:8px 0; font-weight:bold; font-size:1.05em;'>{market_health['action']}</p>
                </div>
                <div style='text-align:center; min-width:100px;'>
                    <h1 style='margin:0; color:{market_health['color']};'>{market_health['health_score']}</h1>
                    <p style='margin:0; font-size:0.9em;'>Health Score</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        with st.expander("📊 Market Details", expanded=False):
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            with m_col1:
                st.metric("NIFTY 50", f"₹{market_health['nifty_price']:,.0f}", 
                         f"{market_health['nifty_change']:+.2f}%")
            with m_col2:
                st.metric("RSI", f"{market_health['nifty_rsi']:.1f}")
            with m_col3:
                st.metric("India VIX", f"{market_health['vix']:.1f}")
            with m_col4:
                st.metric("Trend", "Bullish" if market_health['above_sma20'] else "Bearish")
            st.caption(f"NIFTY SMA20: ₹{market_health['nifty_sma20']:,.0f} | SMA50: ₹{market_health['nifty_sma50']:,.0f}")
        if market_health['sl_adjustment'] == 'AGGRESSIVE':
            settings['sl_risk_threshold'] = max(30, settings['sl_risk_threshold'] - 20)
            st.warning(f"⚠️ SL Risk threshold auto-adjusted to {settings['sl_risk_threshold']}% due to weak market")
        elif market_health['sl_adjustment'] == 'TIGHTEN':
            settings['sl_risk_threshold'] = max(35, settings['sl_risk_threshold'] - 10)
            st.info(f"ℹ️ SL Risk threshold adjusted to {settings['sl_risk_threshold']}% (cautious mode)")
    else:
        market_health = None
        st.warning("⚠️ Unable to fetch market health data")
    st.divider()
    with st.expander("⚙️ Current Settings", expanded=False):
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Trail SL Trigger", f"{settings['trail_sl_trigger']}%")
        with col2:
            st.metric("SL Risk Alert", f"{settings['sl_risk_threshold']}%")
        with col3:
            st.metric("Refresh Interval", f"{settings['refresh_interval']}s")
        with col4:
            st.metric("MTF Analysis", "✅ On" if settings['enable_multi_timeframe'] else "❌ Off")
        with col5:
            st.metric("Email Alerts", "✅ On" if settings['email_settings']['enabled'] else "❌ Off")
    st.divider()
    portfolio = load_portfolio()
    if portfolio is None or len(portfolio) == 0:
        st.warning("⚠️ No positions found!")
        st.markdown("### 📋 Expected Google Sheets Format:")
        sample_df = pd.DataFrame({
            'Ticker': ['RELIANCE', 'TCS', 'INFY'],
            'Position': ['LONG', 'LONG', 'SHORT'],
            'Entry_Price': [2450.00, 3580.00, 1520.00],
            'Quantity': [10, 5, 8],
            'Stop_Loss': [2380.00, 3480.00, 1580.00],
            'Target_1': [2550.00, 3720.00, 1420.00],
            'Target_2': [2650.00, 3850.00, 1350.00],
            'Entry_Date': ['2024-01-15', '2024-01-20', '2024-02-01'],
            'Status': ['ACTIVE', 'ACTIVE', 'ACTIVE']
        })
        st.dataframe(sample_df, use_container_width=True)
        return
    is_valid, errors, warnings = validate_portfolio(portfolio)
    if errors:
        st.error("❌ Portfolio Validation Failed!")
        for error in errors:
            st.error(error)
        st.stop()
    if warnings:
        with st.expander("⚠️ Validation Warnings", expanded=False):
            for warning in warnings:
                st.warning(warning)
        st.markdown("### 📋 Expected Google Sheets Format:")
        sample_df = pd.DataFrame({
            'Ticker': ['RELIANCE', 'TCS', 'INFY'],
            'Position': ['LONG', 'LONG', 'SHORT'],
            'Entry_Price': [2450.00, 3580.00, 1520.00],
            'Quantity': [10, 5, 8],
            'Stop_Loss': [2380.00, 3480.00, 1580.00],
            'Target_1': [2550.00, 3720.00, 1420.00],
            'Target_2': [2650.00, 3850.00, 1350.00],
            'Entry_Date': ['2024-01-15', '2024-01-20', '2024-02-01'],
            'Status': ['ACTIVE', 'ACTIVE', 'ACTIVE']
        })
        st.dataframe(sample_df, use_container_width=True)
        return
    results = []
    progress_bar = st.progress(0, text="Analyzing positions...")
    for i, (_, row) in enumerate(portfolio.iterrows()):
        ticker = str(row['Ticker']).strip()
        progress_bar.progress((i + 0.5) / len(portfolio), text=f"Analyzing {ticker}...")
        entry_date = row.get('Entry_Date', None)
        result = smart_analyze_position(
            ticker,
            str(row['Position']).upper().strip(),
            float(row['Entry_Price']),
            int(row.get('Quantity', 1)),
            float(row['Stop_Loss']),
            float(row['Target_1']),
            float(row.get('Target_2', row['Target_1'] * 1.1)),
            settings['trail_sl_trigger'],
            settings['sl_risk_threshold'],
            settings['sl_approach_threshold'],
            settings['enable_multi_timeframe'],
            entry_date
        )
        if result:
            results.append(result)
        progress_bar.progress((i + 1) / len(portfolio), text=f"Completed {ticker}")
    progress_bar.empty()
    if not results:
        st.error("❌ Could not fetch stock data. Check internet connection and try again.")
        return
    portfolio_risk = calculate_portfolio_risk(results)
    sector_analysis = analyze_sector_exposure(results)
    update_drawdown(portfolio_risk['current_value'])
    total_pnl = sum(r['pnl_amount'] for r in results)
    total_invested = sum(r['entry_price'] * r['quantity'] for r in results)
    pnl_percent_total = (total_pnl / total_invested * 100) if total_invested > 0 else 0
    critical_count = sum(1 for r in results if r['overall_status'] == 'CRITICAL')
    warning_count = sum(1 for r in results if r['overall_status'] == 'WARNING')
    opportunity_count = sum(1 for r in results if r['overall_status'] == 'OPPORTUNITY')
    success_count = sum(1 for r in results if r['overall_status'] == 'SUCCESS')
    good_count = sum(1 for r in results if r['overall_status'] == 'GOOD')
    if settings['email_settings']['enabled']:
        send_portfolio_alerts(results, settings['email_settings'], portfolio_risk)
    st.markdown("### 📊 Portfolio Summary")
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    with col1:
        pnl_delta = f"{pnl_percent_total:+.2f}%"
        st.metric("💰 Total P&L", f"₹{total_pnl:+,.0f}", pnl_delta)
    with col2:
        st.metric("📊 Positions", len(results))
    with col3:
        st.metric("🔴 Critical", critical_count)
    with col4:
        st.metric("🟡 Warning", warning_count)
    with col5:
        st.metric("🟢 Good", good_count)
    with col6:
        st.metric("🔵 Opportunity", opportunity_count)
    with col7:
        st.metric("✅ Success", success_count)
    st.divider()
    tab1, tab2, tab3, tab4, tab5, tab6, tab7= st.tabs([
        "📊 Dashboard",
        "📈 Charts", 
        "🔔 Alerts",
        "📉 MTF Analysis",
        "🛡️ Portfolio Risk",
        "📈 Performance",
        "📋 Details"
    ])
    # ...existing code for each tab (see advanced app.py for full logic)...
    # For brevity, you should call the display functions for each tab as in your advanced app.py


if __name__ == "__main__":
    main()

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
    """Safe division that handles zero and NaN"""
    try:
        if denominator == 0 or pd.isna(denominator) or pd.isna(numerator):
            return default
        result = numerator / denominator
        return default if pd.isna(result) or np.isinf(result) else result
    except (TypeError, ValueError, ZeroDivisionError, FloatingPointError):
        logger.warning(f"Safe divide error: num={numerator}, denom={denominator}")
        return default

def safe_float(value, default=0.0):
    """Safely convert value to float"""
    try:
        result = float(value)
        return default if pd.isna(result) else result
    except (TypeError, ValueError):
        logger.warning(f"Safe float error: value={value}")
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
# MARKET HEALTH CHECK (NEW FEATURE)
# ============================================================================

@st.cache_data(ttl=300)
def get_market_health():
    """Analyze NIFTY 50 and India VIX for market health"""
    try:
        nifty = yf.Ticker("^NSEI")
        nifty_df = nifty.history(period="1mo")
        
        if nifty_df.empty:
            return None
        
        nifty_price = float(nifty_df['Close'].iloc[-1])
        nifty_change = ((nifty_price - float(nifty_df['Close'].iloc[-2])) / float(nifty_df['Close'].iloc[-2])) * 100
        
        nifty_sma20 = nifty_df['Close'].rolling(20).mean().iloc[-1]
        nifty_sma50 = nifty_df['Close'].rolling(50).mean().iloc[-1] if len(nifty_df) >= 50 else nifty_sma20
        nifty_rsi = calculate_rsi(nifty_df['Close']).iloc[-1]
        if pd.isna(nifty_rsi):
            nifty_rsi = 50
        
        vix = yf.Ticker("^INDIAVIX")
        vix_df = vix.history(period="5d")
        vix_value = float(vix_df['Close'].iloc[-1]) if not vix_df.empty else 15
        
        # Calculate Market Health Score
        health_score = 50
        if nifty_price > nifty_sma20:
            health_score += 15
        else:
            health_score -= 15
        if nifty_price > nifty_sma50:
            health_score += 10
        if nifty_rsi > 55:
            health_score += 15
        elif nifty_rsi < 35:
            health_score -= 15
        if vix_value < 15:
            health_score += 10
        elif vix_value > 25:
            health_score -= 20
        if nifty_sma20 > nifty_sma50:
            health_score += 10
        
        health_score = max(0, min(100, health_score))
        
        if health_score >= 70:
            status, color, icon = "BULLISH", "#28a745", "🟢"
            action = "✅ Good environment for trading"
        elif health_score >= 50:
            status, color, icon = "NEUTRAL", "#ffc107", "🟡"
            action = "⚠️ Be selective with positions"
        else:
            status, color, icon = "BEARISH", "#dc3545", "🔴"
            action = "🚨 HIGH RISK - Consider reducing"
        
        message = f"NIFTY: ₹{nifty_price:,.0f} ({nifty_change:+.2f}%) | RSI: {nifty_rsi:.0f} | VIX: {vix_value:.1f}"
        
        return {
            'status': status,
            'health_score': health_score,
            'message': message,
            'color': color,
            'icon': icon,
            'action': action,
            'nifty_price': nifty_price,
            'nifty_change': nifty_change,
            'nifty_rsi': nifty_rsi,
            'vix': vix_value
        }
    except Exception as e:
        logger.error(f"Market health check failed: {e}")
        return None

# ============================================================================
# EMERGENCY EXIT DETECTOR (NEW FEATURE)
# ============================================================================

def detect_emergency_exit(result, market_health):
    """Detect critical exit conditions"""
    emergency = False
    reasons = []
    urgency = "NORMAL"
    
    if market_health and market_health['status'] == 'BEARISH':
        if result.get('pnl_percent', 0) < -2:
            emergency = True
            urgency = "CRITICAL"
            reasons.append(f"🚨 Bearish market + Position down {result.get('pnl_percent', 0):.1f}%")
    
    if result.get('position_type') == 'LONG':
        if result.get('day_low', 0) < result.get('stop_loss', 0) * 0.98:
            emergency = True
            urgency = "CRITICAL"
            reasons.append("🚨 Gap down: Day low below SL")
    else:
        if result.get('day_high', 0) > result.get('stop_loss', 0) * 1.02:
            emergency = True
            urgency = "CRITICAL"
            reasons.append("🚨 Gap up: Day high above SL")
    
    if market_health and market_health.get('vix', 0) > 25:
        if result.get('sl_risk', 0) > 60:
            emergency = True
            urgency = "CRITICAL"
            reasons.append("🚨 VIX spike + High SL risk")
    
    return emergency, reasons, urgency

# ============================================================================
# CHART PATTERN DETECTION (NEW FEATURE)
# ============================================================================

def detect_chart_patterns(df, current_price):
    """Detect common chart patterns"""
    patterns = []
    
    if len(df) < 30:
        return patterns
    
    high = df['High']
    low = df['Low']
    
    last_30 = df.tail(30)
    highs_30 = last_30['High']
    sorted_highs = highs_30.nlargest(5)
    
    if len(sorted_highs) >= 2:
        peak1 = float(sorted_highs.iloc[0])
        peak2 = float(sorted_highs.iloc[1])
        if abs(peak1 - peak2) / peak1 < 0.02 and current_price < peak1 * 0.98:
            patterns.append({
                'name': 'DOUBLE TOP',
                'signal': 'BEARISH',
                'icon': '📉',
                'description': f'Resistance at ₹{peak1:.2f} tested twice'
            })
    
    lows_30 = last_30['Low']
    sorted_lows = lows_30.nsmallest(5)
    
    if len(sorted_lows) >= 2:
        bottom1 = float(sorted_lows.iloc[0])
        bottom2 = float(sorted_lows.iloc[1])
        if abs(bottom1 - bottom2) / bottom1 < 0.02 and current_price > bottom1 * 1.02:
            patterns.append({
                'name': 'DOUBLE BOTTOM',
                'signal': 'BULLISH',
                'icon': '📈',
                'description': f'Support at ₹{bottom1:.2f} held twice'
            })
    
    return patterns

# ============================================================================
# SUPPORT/RESISTANCE DETECTION (ENHANCED)
# ============================================================================

def find_support_resistance(df, lookback=60):
    """Find key support and resistance levels"""
    if len(df) < lookback:
        lookback = len(df)
    
    if lookback < 10:
        current_price = float(df['Close'].iloc[-1])
        return {
            'support_levels': [],
            'resistance_levels': [],
            'nearest_support': current_price * 0.95,
            'nearest_resistance': current_price * 1.05,
            'distance_to_support': 5.0,
            'distance_to_resistance': 5.0,
            'support_strength': 'WEAK',
            'resistance_strength': 'WEAK'
        }
    
    high = df['High'].tail(lookback)
    low = df['Low'].tail(lookback)
    close = df['Close'].tail(lookback)
    current_price = float(close.iloc[-1])
    
    # Find pivot points
    pivot_highs = []
    pivot_lows = []
    
    for i in range(3, len(high) - 3):
        if (high.iloc[i] >= high.iloc[i-1] and high.iloc[i] >= high.iloc[i+1]):
            pivot_highs.append(float(high.iloc[i]))
        if (low.iloc[i] <= low.iloc[i-1] and low.iloc[i] <= low.iloc[i+1]):
            pivot_lows.append(float(low.iloc[i]))
    
    nearest_support = max(pivot_lows) if pivot_lows else float(low.min())
    nearest_resistance = min([p for p in pivot_highs if p > current_price]) if [p for p in pivot_highs if p > current_price] else float(high.max())
    
    distance_to_support = ((current_price - nearest_support) / current_price) * 100
    distance_to_resistance = ((nearest_resistance - current_price) / current_price) * 100
    
    return {
        'support_levels': pivot_lows[-5:] if pivot_lows else [],
        'resistance_levels': pivot_highs[-5:] if pivot_highs else [],
        'nearest_support': nearest_support,
        'nearest_resistance': nearest_resistance,
        'distance_to_support': distance_to_support,
        'distance_to_resistance': distance_to_resistance,
        'support_strength': 'STRONG' if len(pivot_lows) >= 3 else 'WEAK',
        'resistance_strength': 'STRONG' if len(pivot_highs) >= 3 else 'WEAK'
    }

# ============================================================================
# VOLUME ANALYSIS (ENHANCED)
# ============================================================================

def analyze_volume(df):
    """Analyze volume to confirm price movements"""
    if 'Volume' not in df.columns or len(df) < 20:
        return "NEUTRAL", 1.0, "Volume data not available", "NEUTRAL"
    
    if df['Volume'].iloc[-1] == 0:
        return "NEUTRAL", 1.0, "No volume data", "NEUTRAL"
    
    avg_volume = df['Volume'].rolling(20).mean().iloc[-1]
    current_volume = df['Volume'].iloc[-1]
    volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
    
    price_change = df['Close'].iloc[-1] - df['Close'].iloc[-2]
    
    if price_change > 0 and volume_ratio > 1.5:
        signal = "STRONG_BUYING"
        desc = f"Strong buying ({volume_ratio:.1f}x)"
    elif price_change > 0 and volume_ratio > 1.0:
        signal = "BUYING"
        desc = f"Buying with volume ({volume_ratio:.1f}x)"
    elif price_change < 0 and volume_ratio > 1.5:
        signal = "STRONG_SELLING"
        desc = f"Strong selling ({volume_ratio:.1f}x)"
    elif price_change < 0 and volume_ratio > 1.0:
        signal = "SELLING"
        desc = f"Selling with volume ({volume_ratio:.1f}x)"
    else:
        signal = "NEUTRAL"
        desc = f"Normal volume ({volume_ratio:.1f}x)"
    
    return signal, volume_ratio, desc, "NEUTRAL"

# ============================================================================
# ADDITIONAL TECHNICAL INDICATORS
# ============================================================================

def calculate_stochastic(df, period=14):
    """Calculate Stochastic %K and %D"""
    if len(df) < period:
        return pd.Series([50] * len(df)), pd.Series([50] * len(df))
    
    low_min = df['Low'].rolling(period).min()
    high_max = df['High'].rolling(period).max()
    
    k_percent = 100 * ((df['Close'] - low_min) / (high_max - low_min + 1e-10))
    d_percent = k_percent.rolling(3).mean()
    
    return k_percent, d_percent

def calculate_atr(df, period=14):
    """Calculate Average True Range"""
    if len(df) < 2:
        return pd.Series([0] * len(df))
    
    tr = np.maximum(
        df['High'] - df['Low'],
        np.maximum(
            abs(df['High'] - df['Close'].shift(1)),
            abs(df['Low'] - df['Close'].shift(1))
        )
    )
    atr = tr.rolling(period).mean()
    return atr

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
# MOMENTUM & RISK ANALYSIS (NEW FEATURES)
# ============================================================================



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

# ============================================================================
# PORTFOLIO RISK ANALYSIS (NEW FEATURES)
# ============================================================================

def calculate_correlation_matrix(portfolio_df):
    """Calculate correlation between portfolio positions"""
    try:
        if portfolio_df.empty or len(portfolio_df) < 2:
            return None
        
        tickers = portfolio_df['Ticker'].unique()[:10]  # Limit to 10 for performance
        prices_dict = {}
        
        for ticker in tickers:
            df = get_stock_data_safe(ticker, period="3mo")
            if df is not None and not df.empty:
                prices_dict[ticker] = df['Close'].pct_change()
        
        if len(prices_dict) < 2:
            return None
        
        prices_df = pd.DataFrame(prices_dict)
        correlation = prices_df.corr()
        
        return correlation
    except Exception as e:
        logger.error(f"Correlation calculation failed: {e}")
        return None

def analyze_correlation_risk(portfolio_df):
    """Analyze portfolio correlation risk"""
    correlation = calculate_correlation_matrix(portfolio_df)
    
    risk_warning = ""
    risk_level = "LOW"
    
    if correlation is not None:
        # Find high correlations (>0.7)
        high_corr_count = 0
        for i in range(len(correlation.columns)):
            for j in range(i+1, len(correlation.columns)):
                if abs(correlation.iloc[i, j]) > 0.7:
                    high_corr_count += 1
        
        if high_corr_count > 3:
            risk_level = "HIGH"
            risk_warning = f"⚠️ {high_corr_count} highly correlated pairs detected - Diversify!"
        elif high_corr_count > 1:
            risk_level = "MEDIUM"
            risk_warning = f"⚠️ {high_corr_count} correlated pairs - Monitor carefully"
    
    return {
        'risk_level': risk_level,
        'warning': risk_warning,
        'correlation': correlation
    }

def analyze_sector_exposure(portfolio_df):
    """Analyze sector concentration in portfolio"""
    sector_map = {
        'TCS': 'IT', 'INFY': 'IT', 'WIPRO': 'IT', 'HCL': 'IT',
        'RELIANCE': 'ENERGY', 'ONGC': 'ENERGY',
        'HDFC': 'FINANCE', 'ICICI': 'FINANCE', 'AXIS': 'FINANCE',
        'BAJAJ': 'AUTO', 'MARUTI': 'AUTO',
        'ITC': 'CONSUMER', 'BRITANNIA': 'CONSUMER'
    }
    
    sector_exposure = {}
    total_value = portfolio_df['Quantity'].sum() * portfolio_df['Entry_Price'].mean()
    
    for _, row in portfolio_df.iterrows():
        ticker = row['Ticker']
        sector = sector_map.get(ticker, 'OTHER')
        value = float(row['Quantity']) * float(row['Entry_Price'])
        
        if sector not in sector_exposure:
            sector_exposure[sector] = 0
        sector_exposure[sector] += value
    
    sector_pct = {k: (v / total_value * 100) for k, v in sector_exposure.items()}
    
    # Check for over-concentration
    warnings = []
    for sector, pct in sector_pct.items():
        if pct > 40:
            warnings.append(f"🚨 {sector}: {pct:.1f}% - OVER-CONCENTRATED")
        elif pct > 30:
            warnings.append(f"⚠️ {sector}: {pct:.1f}% - HIGH concentration")
    
    return {
        'exposure': sector_exposure,
        'percentage': sector_pct,
        'warnings': warnings
    }

def calculate_portfolio_risk(portfolio_df):
    """Calculate overall portfolio risk metrics"""
    if portfolio_df.empty:
        return None
    
    # Convert Decimal to float
    portfolio_df = portfolio_df.copy()
    for col in ['Entry_Price', 'Target_1', 'Target_2', 'Stop_Loss']:
        if col in portfolio_df.columns:
            portfolio_df[col] = portfolio_df[col].astype(float)
    
    total_invested = 0
    total_at_risk = 0
    total_potential_gain = 0
    
    for _, row in portfolio_df.iterrows():
        entry = float(row['Entry_Price'])
        quantity = float(row['Quantity'])
        sl = float(row['Stop_Loss'])
        target = float(row['Target_1'])
        
        position_value = entry * quantity
        risk_per_share = abs(entry - sl)
        potential_gain_per_share = abs(target - entry)
        
        total_invested += position_value
        total_at_risk += risk_per_share * quantity
        total_potential_gain += potential_gain_per_share * quantity
    
    risk_percent = (total_at_risk / total_invested * 100) if total_invested > 0 else 0
    reward_percent = (total_potential_gain / total_invested * 100) if total_invested > 0 else 0
    
    risk_reward_ratio = total_potential_gain / total_at_risk if total_at_risk > 0 else 0
    
    if risk_reward_ratio >= 3:
        rating = "EXCELLENT 🟢"
    elif risk_reward_ratio >= 2:
        rating = "GOOD 🟢"
    elif risk_reward_ratio >= 1:
        rating = "FAIR 🟡"
    else:
        rating = "POOR 🔴"
    
    return {
        'total_invested': total_invested,
        'total_at_risk': total_at_risk,
        'total_potential': total_potential_gain,
        'risk_percent': risk_percent,
        'reward_percent': reward_percent,
        'ratio': risk_reward_ratio,
        'rating': rating
    }

def smart_analyze_position(ticker, position_type, entry_price, quantity, stop_loss,
                          target1, target2, trail_threshold=2.0, sl_alert_threshold=50,
                          enable_mtf=True, entry_date=None):
    """Complete smart analysis"""
    # Convert any Decimal values to float for arithmetic operations
    entry_price = float(entry_price)
    quantity = float(quantity)
    stop_loss = float(stop_loss)
    target1 = float(target1)
    target2 = float(target2)
    
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
        st.markdown("## 🚀 Actions")
        
        # Add Trade Button
        if st.button("➕ Add New Trade", use_container_width=True, key="add_trade_btn"):
            st.session_state.show_add_trade_form = not st.session_state.get('show_add_trade_form', False)
        
        st.divider()
        
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
# ADD TRADE FORM
# ============================================================================

def render_add_trade_form():
    """Display form to add new trade"""
    st.markdown("### ➕ Add New Trade")
    
    # Create form
    with st.form(key="add_trade_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            ticker = st.text_input(
                "Stock Ticker",
                placeholder="e.g., RELIANCE, TCS, INFY",
                help="Enter NSE stock ticker (without .NS)"
            ).upper()
        
        with col2:
            position = st.selectbox(
                "Position Type",
                options=["LONG", "SHORT"],
                help="LONG: Buy | SHORT: Sell"
            )
        
        col3, col4, col5 = st.columns(3)
        
        with col3:
            entry_price = st.number_input(
                "Entry Price (₹)",
                min_value=0.01,
                step=0.05,
                format="%.2f",
                help="At what price did you enter?"
            )
        
        with col4:
            quantity = st.number_input(
                "Quantity",
                min_value=1,
                step=1,
                value=10,
                help="Number of shares"
            )
        
        with col5:
            stop_loss = st.number_input(
                "Stop Loss (₹)",
                min_value=0.01,
                step=0.05,
                format="%.2f",
                help="Exit if price hits this"
            )
        
        col6, col7, col8 = st.columns(3)
        
        with col6:
            target_1 = st.number_input(
                "Target 1 (₹)",
                min_value=0.01,
                step=0.05,
                format="%.2f",
                help="First profit target"
            )
        
        with col7:
            target_2 = st.number_input(
                "Target 2 (₹)",
                min_value=0.01,
                step=0.05,
                format="%.2f",
                help="Second profit target (optional)"
            )
        
        with col8:
            # Notes (optional)
            notes = st.text_input(
                "Trade Notes (Optional)",
                placeholder="e.g., Based on support breakout",
                help="Add any notes about this trade"
            )
        
        # Submit button
        submitted = st.form_submit_button("✅ Add Trade", use_container_width=True)
    
    if submitted:
        # Validate inputs
        if not ticker:
            st.error("❌ Please enter a ticker")
            return
        
        if entry_price <= 0:
            st.error("❌ Entry price must be positive")
            return
        
        if stop_loss <= 0:
            st.error("❌ Stop loss must be positive")
            return
        
        if target_1 <= 0:
            st.error("❌ Target 1 must be positive")
            return
        
        if quantity <= 0:
            st.error("❌ Quantity must be positive")
            return
        
        # Validate position logic
        if position == "LONG":
            if stop_loss >= entry_price:
                st.error("❌ For LONG: Stop loss must be below entry price")
                return
            if target_1 <= entry_price:
                st.error("❌ For LONG: Target must be above entry price")
                return
        else:  # SHORT
            if stop_loss <= entry_price:
                st.error("❌ For SHORT: Stop loss must be above entry price")
                return
            if target_1 >= entry_price:
                st.error("❌ For SHORT: Target must be below entry price")
                return
        
        # Set target_2 if not provided
        if target_2 <= 0:
            target_2 = None
        
        # Add trade to database
        with st.spinner(f"📊 Adding {ticker} trade..."):
            success, message = add_trade_mysql(
                user_id=st.session_state.user_id,
                ticker=ticker,
                position=position,
                entry_price=entry_price,
                quantity=int(quantity),
                stop_loss=stop_loss,
                target_1=target_1,
                target_2=target_2 if target_2 and target_2 > 0 else None,
                notes=notes if notes else None
            )
        
        if success:
            st.success(message)
            log_audit_action(
                st.session_state.user_id,
                "TRADE_ADDED",
                ticker,
                f"Entry: ₹{entry_price:.2f}, Qty: {quantity}, SL: ₹{stop_loss:.2f}"
            )
            st.session_state.show_add_trade_form = False
            time.sleep(0.5)
            st.rerun()
        else:
            st.error(f"❌ Failed to add trade: {message}")

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
    
    # Show Add Trade Form if button clicked
    if st.session_state.get('show_add_trade_form', False):
        st.info("ℹ️ Click the button again to close the form")
        render_add_trade_form()
        st.divider()
    
    # Market status & health
    is_open, market_status, market_msg, market_icon = is_market_hours()
    ist_now = get_ist_now()
    market_health = get_market_health()
    
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        st.markdown(f"### {market_icon} {market_status}")
    with col2:
        st.markdown(f"### 🕐 {ist_now.strftime('%H:%M:%S')} IST")
    with col3:
        if st.button("🔄 Refresh Data", use_container_width=True, key="refresh_data_btn"):
            st.info("🔄 Data refreshed! Portfolio is being updated...")
    
    # Display market health if available
    if market_health:
        st.markdown(f"### {market_health['icon']} Market: {market_health['message']}")
        st.markdown(f"**Score:** {market_health['health_score']}/100 | {market_health['action']}", 
                    unsafe_allow_html=True)
    
    st.divider()
    
    # Load portfolio
    portfolio = load_portfolio()
    
    if portfolio is None or len(portfolio) == 0:
        st.warning(f"⚠️ No active positions found for {st.session_state.username}")
        st.info("💡 **Click the '➕ Add New Trade' button in the sidebar to add your first trade!**")
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
        st.metric("🔴 Critical", critical, delta=f"{critical} alerts")
    with col4:
        st.metric("🟡 Warning", warning, delta=f"{warning} alerts")
    
    st.divider()
    
    # Portfolio Risk Analysis
    portfolio_risk = calculate_portfolio_risk(portfolio)
    if portfolio_risk:
        st.markdown("### 📊 Portfolio Risk Analysis")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("💵 Invested", f"₹{portfolio_risk['total_invested']:,.0f}")
        with col2:
            st.metric("⚠️ At Risk", f"₹{portfolio_risk['total_at_risk']:,.0f}", 
                     delta=f"{portfolio_risk['risk_percent']:.1f}%")
        with col3:
            st.metric("🎯 Potential", f"₹{portfolio_risk['total_potential']:+,.0f}", 
                     delta=f"{portfolio_risk['reward_percent']:.1f}%")
        with col4:
            st.metric("✅ R:R Ratio", f"{portfolio_risk['ratio']:.2f}x", 
                     delta=portfolio_risk['rating'])
        st.divider()
    
    # Correlation Risk Warning
    corr_analysis = analyze_correlation_risk(portfolio)
    if corr_analysis['warning']:
        if corr_analysis['risk_level'] == 'HIGH':
            st.error(corr_analysis['warning'])
        else:
            st.warning(corr_analysis['warning'])
    
    # Sector Exposure Analysis
    sector_analysis = analyze_sector_exposure(portfolio)
    if sector_analysis['warnings']:
        st.markdown("### 🏢 Sector Exposure")
        for warning in sector_analysis['warnings']:
            st.warning(warning)
    
    st.divider()
    
    # Display positions with emergency exit detection
    for r in results:
        emergency, emergency_reasons, urgency = detect_emergency_exit(r, market_health)
        status_icon = "🚨" if emergency else "🔴" if r['overall_status'] == 'CRITICAL' else "🟡" if r['overall_status'] == 'WARNING' else "🟢"
        
        with st.expander(
            f"{status_icon} **{r['ticker']}** | "
            f"{'📈 LONG' if r['position_type'] == 'LONG' else '📉 SHORT'} | "
            f"P&L: **{r['pnl_percent']:+.2f}%** (₹{r['pnl_amount']:+,.0f}) | "
            f"SL Risk: **{r['sl_risk']}%**",
            expanded=(r['overall_status'] in ['CRITICAL', 'WARNING'] or emergency)
        ):
            col1, col2, col3 = st.columns(3)
            
            # Show emergency exit warning if detected
            if emergency:
                st.error(f"🚨 **EMERGENCY EXIT DETECTED** ({urgency})")
                for reason in emergency_reasons:
                    st.write(reason)
                st.divider()
            
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
            if r['alerts'] or emergency:
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
