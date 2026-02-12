"""
Position Management Module
Add, Edit, Delete, View positions
"""
import streamlit as st
import pandas as pd
from datetime import datetime, date
from database import get_db
from auth import get_current_user_id

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

def show_add_position_form():
    """Display form to add new position"""
    st.markdown("### ➕ Add New Position")
    
    with st.form("add_position_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            ticker = st.text_input(
                "Stock Ticker *",
                placeholder="RELIANCE, TCS, INFY",
                help="Enter stock symbol (NSE)"
            ).upper().strip()
            
            position_type = st.selectbox(
                "Position Type *",
                ["LONG", "SHORT"]
            )
            
            entry_price = st.number_input(
                "Entry Price (₹) *",
                min_value=0.01,
                value=100.0,
                step=0.05,
                format="%.2f"
            )
            
            quantity = st.number_input(
                "Quantity *",
                min_value=1,
                value=10,
                step=1
            )
            
            entry_date = st.date_input(
                "Entry Date",
                value=date.today(),
                max_value=date.today()
            )
        
        with col2:
            stop_loss = st.number_input(
                "Stop Loss (₹) *",
                min_value=0.01,
                value=95.0,
                step=0.05,
                format="%.2f"
            )
            
            target_1 = st.number_input(
                "Target 1 (₹) *",
                min_value=0.01,
                value=110.0,
                step=0.05,
                format="%.2f"
            )
            
            target_2 = st.number_input(
                "Target 2 (₹)",
                min_value=0.01,
                value=120.0,
                step=0.05,
                format="%.2f",
                help="Optional second target"
            )
            
            status = st.selectbox(
                "Status",
                ["ACTIVE", "PENDING"],
                help="PENDING = Entry order not yet filled"
            )
        
        # Validation summary
        st.divider()
        
        # Calculate investment and R:R
        investment = entry_price * quantity
        
        if position_type == "LONG":
            risk = entry_price - stop_loss
            reward = target_1 - entry_price
            valid_levels = entry_price > stop_loss and target_1 > entry_price
        else:
            risk = stop_loss - entry_price
            reward = entry_price - target_1
            valid_levels = entry_price < stop_loss and target_1 < entry_price
        
        risk_amount = risk * quantity
        reward_amount = reward * quantity
        rr_ratio = reward / risk if risk > 0 else 0
        
        col_a, col_b, col_c = st.columns(3)
        
        with col_a:
            st.metric("💰 Investment", f"₹{investment:,.0f}")
        
        with col_b:
            st.metric("⚠️ Risk Amount", f"₹{risk_amount:,.0f}")
        
        with col_c:
            rr_color = "green" if rr_ratio >= 2 else "orange" if rr_ratio >= 1.5 else "red"
            st.markdown(f"**⚖️ Risk:Reward**")
            st.markdown(f"<h3 style='color:{rr_color}; margin:0;'>1:{rr_ratio:.2f}</h3>", 
                       unsafe_allow_html=True)
        
        if rr_ratio < 1.5:
            st.warning("⚠️ Risk:Reward ratio is below recommended 1:1.5")
        
        st.caption("* Required fields")
        
        submitted = st.form_submit_button(
            "✅ Add Position",
            use_container_width=True,
            type="primary"
        )
        
        if submitted:
            # Validation
            errors = []
            
            if not ticker:
                errors.append("❌ Ticker is required")
            
            if not valid_levels:
                if position_type == "LONG":
                    errors.append("❌ For LONG: Entry must be > Stop Loss and < Target")
                else:
                    errors.append("❌ For SHORT: Entry must be < Stop Loss and > Target")
            
            if errors:
                for error in errors:
                    st.error(error)
            else:
                # Round prices to tick size
                entry_price_rounded = round_to_tick_size(entry_price)
                stop_loss_rounded = round_to_tick_size(stop_loss)
                target_1_rounded = round_to_tick_size(target_1)
                target_2_rounded = round_to_tick_size(target_2)
                
                # Add position to database
                db = get_db()
                user_id = get_current_user_id()
                
                success, message = db.add_position(
                    user_id=user_id,
                    ticker=ticker,
                    position_type=position_type,
                    entry_price=entry_price_rounded,
                    quantity=quantity,
                    stop_loss=stop_loss_rounded,
                    target_1=target_1_rounded,
                    target_2=target_2_rounded,
                    entry_date=entry_date.isoformat(),
                    status=status
                )
                
                if success:
                    st.success(f"✅ {message}")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(f"❌ {message}")

def show_positions_list():
    """Display list of all positions with edit/delete options"""
    st.markdown("### 📊 Your Positions")
    
    db = get_db()
    user_id = get_current_user_id()
    
    # Get all positions (active and inactive)
    positions = db.get_active_positions(user_id)
    
    if not positions:
        st.info("No positions found. Add your first position above!")
        return
    
    # Filter options
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_filter = st.selectbox(
            "Filter by Status",
            ["ALL", "ACTIVE", "PENDING", "INACTIVE"]
        )
    
    with col2:
        type_filter = st.selectbox(
            "Filter by Type",
            ["ALL", "LONG", "SHORT"]
        )
    
    with col3:
        search = st.text_input("🔍 Search Ticker", placeholder="RELIANCE")
    
    # Apply filters
    filtered_positions = positions
    
    if status_filter != "ALL":
        filtered_positions = [p for p in filtered_positions if p['status'] == status_filter]
    
    if type_filter != "ALL":
        filtered_positions = [p for p in filtered_positions if p['position_type'] == type_filter]
    
    if search:
        filtered_positions = [p for p in filtered_positions 
                            if search.upper() in p['ticker'].upper()]
    
    if not filtered_positions:
        st.warning("No positions match your filters")
        return
    
    st.caption(f"Showing {len(filtered_positions)} position(s)")
    
    # Display positions as expandable cards
    for position in filtered_positions:
        status_icons = {
            'ACTIVE': '🟢',
            'PENDING': '🟡',
            'INACTIVE': '🔴'
        }
        status_icon = status_icons.get(position['status'], '⚪')
        
        type_emoji = "📈" if position['position_type'] == 'LONG' else "📉"
        
        # Calculate current investment
        investment = position['entry_price'] * position['quantity']
        
        with st.expander(
            f"{status_icon} {position['ticker']} | "
            f"{type_emoji} {position['position_type']} | "
            f"Entry: ₹{position['entry_price']:,.2f} | "
            f"Qty: {position['quantity']} | "
            f"Investment: ₹{investment:,.0f}",
            expanded=False
        ):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Position details
                st.markdown("#### 📊 Position Details")
                
                detail_col1, detail_col2 = st.columns(2)
                
                with detail_col1:
                    st.write(f"**Ticker:** {position['ticker']}")
                    st.write(f"**Type:** {type_emoji} {position['position_type']}")
                    st.write(f"**Entry Price:** ₹{position['entry_price']:,.2f}")
                    st.write(f"**Quantity:** {position['quantity']}")
                    st.write(f"**Investment:** ₹{investment:,.0f}")
                
                with detail_col2:
                    st.write(f"**Stop Loss:** ₹{position['stop_loss']:,.2f}")
                    st.write(f"**Target 1:** ₹{position['target_1']:,.2f}")
                    if position['target_2']:
                        st.write(f"**Target 2:** ₹{position['target_2']:,.2f}")
                    st.write(f"**Status:** {status_icon} {position['status']}")
                    if position['entry_date']:
                        st.write(f"**Entry Date:** {position['entry_date']}")
                
                # If closed, show exit details
                if position['status'] == 'INACTIVE':
                    st.divider()
                    st.markdown("#### 🚪 Exit Details")
                    
                    exit_col1, exit_col2 = st.columns(2)
                    
                    with exit_col1:
                        st.write(f"**Exit Price:** ₹{position['exit_price']:,.2f}")
                        st.write(f"**Exit Date:** {position['exit_date']}")
                    
                    with exit_col2:
                        pnl = position['realized_pnl']
                        pnl_color = "green" if pnl >= 0 else "red"
                        st.markdown(f"**Realized P&L:** <span style='color:{pnl_color};font-weight:bold;'>₹{pnl:+,.0f}</span>",
                                   unsafe_allow_html=True)
                        if position['exit_reason']:
                            st.write(f"**Reason:** {position['exit_reason']}")
            
            with col2:
                st.markdown("#### ⚙️ Actions")
                
                # Edit button
                if position['status'] != 'INACTIVE':
                    if st.button(
                        "✏️ Edit Position",
                        key=f"edit_{position['position_id']}",
                        use_container_width=True
                    ):
                        st.session_state.editing_position = position['position_id']
                        st.rerun()
                    
                    # Quick close button
                    if st.button(
                        "🚪 Close Position",
                        key=f"close_{position['position_id']}",
                        use_container_width=True,
                        type="secondary"
                    ):
                        st.session_state.closing_position = position['position_id']
                        st.rerun()
                
                # Delete button (always available)
                if st.button(
                    "🗑️ Delete Position",
                    key=f"delete_{position['position_id']}",
                    use_container_width=True,
                    help="Permanently delete this position"
                ):
                    # Confirmation dialog
                    st.session_state.delete_confirm = position['position_id']
                
                # Delete confirmation
                if st.session_state.get('delete_confirm') == position['position_id']:
                    st.warning("⚠️ Are you sure?")
                    
                    conf_col1, conf_col2 = st.columns(2)
                    
                    with conf_col1:
                        if st.button("✅ Yes", key=f"del_yes_{position['position_id']}",
                                   use_container_width=True):
                            success, msg = db.delete_position(
                                position['position_id'],
                                user_id
                            )
                            if success:
                                st.success(msg)
                                del st.session_state.delete_confirm
                                st.rerun()
                            else:
                                st.error(msg)
                    
                    with conf_col2:
                        if st.button("❌ No", key=f"del_no_{position['position_id']}",
                                   use_container_width=True):
                            del st.session_state.delete_confirm
                            st.rerun()

def show_edit_position_dialog(position_id):
    """Show edit dialog for a specific position"""
    db = get_db()
    user_id = get_current_user_id()
    
    # Get position details
    positions = db.get_active_positions(user_id)
    position = next((p for p in positions if p['position_id'] == position_id), None)
    
    if not position:
        st.error("Position not found")
        return
    
    st.markdown(f"### ✏️ Edit Position: {position['ticker']}")
    
    with st.form("edit_position_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            new_sl = st.number_input(
                "Stop Loss (₹)",
                min_value=0.01,
                value=float(position['stop_loss']),
                step=0.05,
                format="%.2f"
            )
            
            new_t1 = st.number_input(
                "Target 1 (₹)",
                min_value=0.01,
                value=float(position['target_1']),
                step=0.05,
                format="%.2f"
            )
        
        with col2:
            new_t2 = st.number_input(
                "Target 2 (₹)",
                min_value=0.01,
                value=float(position['target_2']) if position['target_2'] else float(position['target_1']) * 1.1,
                step=0.05,
                format="%.2f"
            )
            
            new_status = st.selectbox(
                "Status",
                ["ACTIVE", "PENDING", "INACTIVE"],
                index=["ACTIVE", "PENDING", "INACTIVE"].index(position['status'])
            )
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            submit = st.form_submit_button("✅ Save Changes", use_container_width=True, type="primary")
        
        with col_b:
            cancel = st.form_submit_button("❌ Cancel", use_container_width=True)
        
        if submit:
            # Round to tick size
            new_sl_rounded = round_to_tick_size(new_sl)
            new_t1_rounded = round_to_tick_size(new_t1)
            new_t2_rounded = round_to_tick_size(new_t2)
            
            success, msg = db.update_position(
                position_id,
                stop_loss=new_sl_rounded,
                target_1=new_t1_rounded,
                target_2=new_t2_rounded,
                status=new_status
            )
            
            if success:
                st.success(msg)
                del st.session_state.editing_position
                st.rerun()
            else:
                st.error(msg)
        
        if cancel:
            del st.session_state.editing_position
            st.rerun()

def show_close_position_dialog(position_id):
    """Show dialog to close a position"""
    db = get_db()
    user_id = get_current_user_id()
    
    # Get position details
    positions = db.get_active_positions(user_id)
    position = next((p for p in positions if p['position_id'] == position_id), None)
    
    if not position:
        st.error("Position not found")
        return
    
    st.markdown(f"### 🚪 Close Position: {position['ticker']}")
    
    with st.form("close_position_form"):
        exit_price = st.number_input(
            "Exit Price (₹)",
            min_value=0.01,
            value=float(position['entry_price']),
            step=0.05,
            format="%.2f"
        )
        
        exit_reason = st.selectbox(
            "Exit Reason",
            [
                "Target Hit",
                "Stop Loss Hit",
                "Manual Exit - Strategy Change",
                "Manual Exit - Risk Management",
                "Manual Exit - Market Conditions",
                "Trail SL Hit",
                "Partial Exit",
                "Other"
            ]
        )
        
        # Calculate P&L preview
        if position['position_type'] == 'LONG':
            pnl = (exit_price - position['entry_price']) * position['quantity']
            pnl_pct = ((exit_price - position['entry_price']) / position['entry_price']) * 100
        else:
            pnl = (position['entry_price'] - exit_price) * position['quantity']
            pnl_pct = ((position['entry_price'] - exit_price) / position['entry_price']) * 100
        
        pnl_color = "#28a745" if pnl >= 0 else "#dc3545"
        
        st.markdown(f"""
        <div style='background:{pnl_color}15; padding:15px; border-radius:10px; 
                    border-left:4px solid {pnl_color}; margin:10px 0;'>
            <h3 style='margin:0; color:{pnl_color};'>P&L Preview: ₹{pnl:+,.0f} ({pnl_pct:+.2f}%)</h3>
            <p style='margin:5px 0 0 0;'>Entry: ₹{position['entry_price']:,.2f} → Exit: ₹{exit_price:,.2f} × {position['quantity']} qty</p>
        </div>
        """, unsafe_allow_html=True)
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            submit = st.form_submit_button("✅ Close Position", use_container_width=True, type="primary")
        
        with col_b:
            cancel = st.form_submit_button("❌ Cancel", use_container_width=True)
        
        if submit:
            exit_price_rounded = round_to_tick_size(exit_price)
            
            success, msg = db.close_position(
                position_id,
                exit_price_rounded,
                exit_reason,
                user_id
            )
            
            if success:
                st.success(msg)
                if pnl > 0:
                    st.balloons()
                del st.session_state.closing_position
                st.rerun()
            else:
                st.error(msg)
        
        if cancel:
            del st.session_state.closing_position
            st.rerun()

def show_position_management_page():
    """Main position management page"""
    st.title("📋 Position Management")
    
    # Handle edit/close dialogs
    if 'editing_position' in st.session_state:
        show_edit_position_dialog(st.session_state.editing_position)
        st.divider()
    
    if 'closing_position' in st.session_state:
        show_close_position_dialog(st.session_state.closing_position)
        st.divider()
    
    # Show add form
    show_add_position_form()
    
    st.divider()
    
    # Show positions list
    show_positions_list()
