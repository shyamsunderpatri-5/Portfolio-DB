"""
Enhanced Performance Analytics Module
Comprehensive portfolio performance tracking
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from database import get_db
from auth import get_current_user_id

def show_performance_dashboard():
    """Display comprehensive performance dashboard"""
    st.title("📈 Performance Dashboard")
    
    db = get_db()
    user_id = get_current_user_id()
    
    # Get comprehensive stats
    stats = db.get_portfolio_stats(user_id)
    
    if not stats or stats['total_trades'] == 0:
        st.info("""
        📊 **No trading history yet!**
        
        Start trading and close some positions to see your performance statistics here.
        """)
        return
    
    # =========================================================================
    # OVERVIEW METRICS
    # =========================================================================
    st.markdown("### 💰 Portfolio Overview")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "📊 Active Positions",
            stats['active_positions']
        )
    
    with col2:
        st.metric(
            "💵 Capital Deployed",
            f"₹{stats['total_invested']:,.0f}"
        )
    
    with col3:
        net_pnl = stats['net_pnl']
        net_color = "normal" if net_pnl >= 0 else "inverse"
        st.metric(
            "💰 Net P&L (Closed)",
            f"₹{net_pnl:+,.0f}",
            delta_color=net_color
        )
    
    with col4:
        st.metric(
            "🎯 Total Trades",
            stats['total_trades']
        )
    
    with col5:
        if stats['total_invested'] > 0:
            roi = (stats['net_pnl'] / stats['total_invested']) * 100
            roi_color = "normal" if roi >= 0 else "inverse"
            st.metric(
                "📊 ROI",
                f"{roi:+.2f}%",
                delta_color=roi_color
            )
        else:
            st.metric("📊 ROI", "N/A")
    
    st.divider()
    
    # =========================================================================
    # WIN/LOSS STATISTICS
    # =========================================================================
    st.markdown("### 🎯 Win/Loss Statistics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Win rate calculation
        win_rate = (stats['wins'] / stats['total_trades'] * 100) if stats['total_trades'] > 0 else 0
        
        # Win rate gauge chart
        fig_winrate = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=win_rate,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Win Rate %", 'font': {'size': 20}},
            delta={'reference': 50, 'increasing': {'color': "green"}, 'decreasing': {'color': "red"}},
            gauge={
                'axis': {'range': [None, 100], 'tickwidth': 1},
                'bar': {'color': "darkblue"},
                'bgcolor': "white",
                'borderwidth': 2,
                'bordercolor': "gray",
                'steps': [
                    {'range': [0, 40], 'color': '#ffcccc'},
                    {'range': [40, 60], 'color': '#ffffcc'},
                    {'range': [60, 100], 'color': '#ccffcc'}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 50
                }
            }
        ))
        fig_winrate.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig_winrate, use_container_width=True)
    
    with col2:
        # Win/Loss breakdown
        fig_wl = go.Figure(data=[go.Pie(
            labels=['Wins', 'Losses'],
            values=[stats['wins'], stats['losses']],
            hole=0.4,
            marker_colors=['#28a745', '#dc3545'],
            textinfo='label+percent+value',
            textposition='auto'
        )])
        fig_wl.update_layout(
            title="Win/Loss Distribution",
            height=250,
            margin=dict(l=20, r=20, t=50, b=20),
            showlegend=True
        )
        st.plotly_chart(fig_wl, use_container_width=True)
    
    with col3:
        # Key statistics
        st.markdown("#### 📊 Key Stats")
        st.metric("✅ Winning Trades", stats['wins'])
        st.metric("❌ Losing Trades", stats['losses'])
        st.metric("📈 Win Rate", f"{win_rate:.1f}%")
        
        # Win/Loss streak (simplified)
        if win_rate >= 60:
            st.success("🌟 Excellent performance!")
        elif win_rate >= 50:
            st.info("👍 Good performance")
        elif win_rate >= 40:
            st.warning("⚠️ Needs improvement")
        else:
            st.error("🚨 Review strategy")
    
    st.divider()
    
    # =========================================================================
    # PROFIT/LOSS ANALYSIS
    # =========================================================================
    st.markdown("### 💵 Profit/Loss Analysis")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "📈 Total Profit",
            f"₹{stats['total_profit']:,.0f}",
            delta_color="normal"
        )
    
    with col2:
        st.metric(
            "📉 Total Loss",
            f"₹{stats['total_loss']:,.0f}",
            delta_color="inverse"
        )
    
    with col3:
        # Profit factor
        profit_factor = stats['total_profit'] / stats['total_loss'] if stats['total_loss'] > 0 else float('inf')
        pf_display = f"{profit_factor:.2f}" if profit_factor < 100 else "∞"
        pf_color = "normal" if profit_factor >= 1.5 else "inverse"
        
        st.metric(
            "⚖️ Profit Factor",
            pf_display,
            delta_color=pf_color,
            help="Total Profit / Total Loss (>1.5 is good)"
        )
    
    with col4:
        # Expectancy
        expectancy = (win_rate/100 * stats['avg_win']) - ((100-win_rate)/100 * stats['avg_loss'])
        exp_color = "normal" if expectancy >= 0 else "inverse"
        
        st.metric(
            "📊 Expectancy",
            f"₹{expectancy:+,.0f}",
            delta_color=exp_color,
            help="Expected profit/loss per trade"
        )
    
    # Profit/Loss bar chart
    fig_pl = go.Figure()
    
    fig_pl.add_trace(go.Bar(
        name='Profit',
        x=['Profit'],
        y=[stats['total_profit']],
        marker_color='#28a745',
        text=[f"₹{stats['total_profit']:,.0f}"],
        textposition='auto'
    ))
    
    fig_pl.add_trace(go.Bar(
        name='Loss',
        x=['Loss'],
        y=[stats['total_loss']],
        marker_color='#dc3545',
        text=[f"₹{stats['total_loss']:,.0f}"],
        textposition='auto'
    ))
    
    fig_pl.update_layout(
        title="Total Profit vs Loss",
        yaxis_title="Amount (₹)",
        height=300,
        showlegend=True
    )
    
    st.plotly_chart(fig_pl, use_container_width=True)
    
    st.divider()
    
    # =========================================================================
    # AVERAGE WIN/LOSS
    # =========================================================================
    st.markdown("### 📊 Average Win vs Loss")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "💰 Average Win",
            f"₹{stats['avg_win']:,.0f}",
            delta_color="normal"
        )
    
    with col2:
        st.metric(
            "📉 Average Loss",
            f"₹{stats['avg_loss']:,.0f}",
            delta_color="inverse"
        )
    
    with col3:
        # Win/Loss ratio
        wl_ratio = stats['avg_win'] / stats['avg_loss'] if stats['avg_loss'] > 0 else float('inf')
        wl_display = f"1:{wl_ratio:.2f}" if wl_ratio < 100 else "1:∞"
        
        st.metric(
            "⚖️ Win/Loss Ratio",
            wl_display,
            help="Average Win / Average Loss"
        )
    
    # Average comparison chart
    fig_avg = go.Figure(data=[
        go.Bar(
            name='Average',
            x=['Win', 'Loss'],
            y=[stats['avg_win'], stats['avg_loss']],
            marker_color=['#28a745', '#dc3545'],
            text=[f"₹{stats['avg_win']:,.0f}", f"₹{stats['avg_loss']:,.0f}"],
            textposition='auto'
        )
    ])
    
    fig_avg.update_layout(
        title="Average Win vs Loss per Trade",
        yaxis_title="Amount (₹)",
        height=300,
        showlegend=False
    )
    
    st.plotly_chart(fig_avg, use_container_width=True)
    
    st.divider()
    
    # =========================================================================
    # TRADE HISTORY
    # =========================================================================
    st.markdown("### 📋 Recent Trade History")
    
    trades = db.get_trade_history(user_id, limit=50)
    
    if trades:
        # Convert to DataFrame
        df_trades = pd.DataFrame(trades)
        
        # Format for display
        df_display = pd.DataFrame({
            'Date': pd.to_datetime(df_trades['exit_date']).dt.strftime('%Y-%m-%d'),
            'Ticker': df_trades['ticker'],
            'Type': df_trades['trade_type'],
            'Entry': df_trades['entry_price'].apply(lambda x: f"₹{float(x):,.2f}"),
            'Exit': df_trades['exit_price'].apply(lambda x: f"₹{float(x):,.2f}"),
            'Qty': df_trades['quantity'],
            'P&L': df_trades['pnl'].apply(lambda x: f"₹{float(x):+,.0f}"),
            'P&L %': df_trades['pnl_pct'].apply(lambda x: f"{float(x):+.2f}%"),
            'Result': df_trades['is_win'].apply(lambda x: '✅' if x else '❌'),
            'Days': df_trades['holding_days'],
            'Reason': df_trades['exit_reason']
        })
        
        # Color code based on result
        def highlight_result(row):
            if row['Result'] == '✅':
                return ['background-color: #d4edda'] * len(row)
            else:
                return ['background-color: #f8d7da'] * len(row)
        
        st.dataframe(
            df_display.style.apply(highlight_result, axis=1),
            use_container_width=True,
            hide_index=True,
            height=400
        )
        
        # Download button
        csv = df_display.to_csv(index=False)
        st.download_button(
            "📥 Download Trade History (CSV)",
            csv,
            file_name=f"trade_history_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
        
        # P&L over time chart
        st.markdown("#### 📈 Cumulative P&L")
        
        df_trades_sorted = df_trades.sort_values('exit_date')
        df_trades_sorted['cumulative_pnl'] = df_trades_sorted['pnl'].astype(float).cumsum()
        
        fig_cumulative = go.Figure()
        
        fig_cumulative.add_trace(go.Scatter(
            x=pd.to_datetime(df_trades_sorted['exit_date']),
            y=df_trades_sorted['cumulative_pnl'],
            mode='lines+markers',
            name='Cumulative P&L',
            line=dict(color='#667eea', width=3),
            marker=dict(size=8),
            fill='tozeroy',
            fillcolor='rgba(102, 126, 234, 0.1)'
        ))
        
        fig_cumulative.add_hline(y=0, line_dash="dash", line_color="gray")
        
        fig_cumulative.update_layout(
            title="Cumulative P&L Over Time",
            xaxis_title="Date",
            yaxis_title="Cumulative P&L (₹)",
            height=400,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig_cumulative, use_container_width=True)
        
    else:
        st.info("No closed trades yet. Close some positions to see trade history.")
    
    st.divider()
    
    # =========================================================================
    # PERFORMANCE SUMMARY
    # =========================================================================
    st.markdown("### 📊 Performance Summary")
    
    if stats['total_trades'] >= 10:
        # Calculate grades
        win_rate_grade = "A" if win_rate >= 60 else "B" if win_rate >= 50 else "C" if win_rate >= 40 else "D"
        pf_grade = "A" if profit_factor >= 2 else "B" if profit_factor >= 1.5 else "C" if profit_factor >= 1.2 else "D"
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"""
            **🎯 Win Rate:** {win_rate:.1f}% (Grade: **{win_rate_grade}**)
            - Wins: {stats['wins']} | Losses: {stats['losses']}
            - Target: 50%+ for consistent profitability
            """)
            
            st.markdown(f"""
            **⚖️ Profit Factor:** {pf_display} (Grade: **{pf_grade}**)
            - Total Profit: ₹{stats['total_profit']:,.0f}
            - Total Loss: ₹{stats['total_loss']:,.0f}
            - Target: 1.5+ for good performance
            """)
        
        with col2:
            st.markdown(f"""
            **💰 Expectancy:** ₹{expectancy:+,.0f}
            - Average Win: ₹{stats['avg_win']:,.0f}
            - Average Loss: ₹{stats['avg_loss']:,.0f}
            - Positive expectancy indicates profitable strategy
            """)
            
            st.markdown(f"""
            **📊 Total Trades:** {stats['total_trades']}
            - Active Positions: {stats['active_positions']}
            - Net P&L: ₹{net_pnl:+,.0f}
            - Keep trading to build robust statistics
            """)
        
        # Overall assessment
        if win_rate >= 55 and profit_factor >= 1.5:
            st.success("🌟 **Excellent Performance!** Your strategy is working well. Keep it up!")
        elif win_rate >= 45 and profit_factor >= 1.2:
            st.info("👍 **Good Performance.** You're on the right track with room for improvement.")
        elif expectancy > 0:
            st.warning("⚠️ **Average Performance.** Strategy is marginally profitable. Consider refinements.")
        else:
            st.error("🚨 **Poor Performance.** Strategy needs significant review and adjustment.")
    else:
        st.info(f"📊 You have {stats['total_trades']} trade(s) logged. Complete at least 10 trades for meaningful performance analysis.")
