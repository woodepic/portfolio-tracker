import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import numpy as np

# Set up the mobile-friendly page layout
st.set_page_config(page_title="My Portfolio Tracker", layout="centered")
st.title("Portfolio vs. VFV.TO")

portfolio_weights = {
    'AVUS': 0.43,
    'CACE.TO': 0.10,
    'CADE.TO': 0.25,
    'CAEM.TO': 0.10,
    'CASV.TO': 0.12
}
benchmark = 'VFV.TO'

# 1. UI Elements - Time window selection
time_filter = st.radio(
    "Select Time Window:", 
    ["1D", "1W", "1M", "3M", "6M", "1Y", "ALL", "Custom Date"], 
    horizontal=True
)

if time_filter == "Custom Date":
    custom_date = st.date_input("Compare from date:", value=datetime.date(2026, 6, 8))
    start_date = pd.to_datetime(custom_date)
    
    # Determine intervals based on historical lookback depth
    days_diff = (datetime.date.today() - custom_date).days
    if days_diff <= 7:
        period_str, interval_str = "1mo", "15m"
    elif days_diff <= 60:
        period_str, interval_str = "3mo", "1h"
    else:
        period_str, interval_str = "2y", "1d"
else:
    mapping = {
        "1D": ("5d", "5m"),
        "1W": ("5d", "15m"),
        "1M": ("1mo", "1h"),
        "3M": ("3mo", "1h"),
        "6M": ("6mo", "1d"),
        "1Y": ("1y", "1d"),
        "ALL": ("2y", "1d")
    }
    period_str, interval_str = mapping[time_filter]
    start_date = None

# Cache data pulls to optimize performance
@st.cache_data(ttl=60)
def load_data(period, interval):
    tickers = list(portfolio_weights.keys()) + [benchmark, 'CAD=X']
    data = yf.download(tickers, period=period, interval=interval)['Close']
    
    # Strip timezone data to match local environments perfectly
    data.index = data.index.tz_localize(None)
    
    missing_tickers = [col for col in data.columns if data[col].isna().all()]
    if missing_tickers:
        st.error(f"Yahoo Finance has no data for: {', '.join(missing_tickers)}.")
        st.stop()
        
    data = data.ffill().bfill().dropna()
    
    if data.empty:
        st.error("The data table is empty.")
        st.stop()
        
    data['AVUS_CAD'] = data['AVUS'] * data['CAD=X']
    returns = data.pct_change().dropna()
    
    returns['My Portfolio'] = (
        returns['AVUS_CAD'] * portfolio_weights['AVUS'] +
        returns['CACE.TO'] * portfolio_weights['CACE.TO'] +
        returns['CADE.TO'] * portfolio_weights['CADE.TO'] +
        returns['CAEM.TO'] * portfolio_weights['CAEM.TO'] +
        returns['CASV.TO'] * portfolio_weights['CASV.TO']
    )
    return returns[['My Portfolio', benchmark]]

with st.spinner("Fetching high-resolution market data..."):
    try:
        daily_returns = load_data(period_str, interval_str)
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.stop()

# 2. Slice the data based on the chosen time window
if time_filter == "Custom Date":
    filtered_returns = daily_returns.loc[daily_returns.index >= start_date]
elif time_filter == "1D":
    latest_date = daily_returns.index.max().date()
    filtered_returns = daily_returns.loc[daily_returns.index.date == latest_date]
else:
    filtered_returns = daily_returns

if filtered_returns.empty:
    st.warning("Not enough data for this specific time period. The ETFs may not have existed yet.")
else:
    # 3. Compounding growth base calculations
    cum_returns = (1 + filtered_returns).cumprod()
    cum_returns = (cum_returns / cum_returns.iloc[0]) - 1
    cum_returns = cum_returns * 100 

    latest_actual_time = cum_returns.index.max()

    # 4. FIXED 50-POINT SAMPLER
    if time_filter == "1D":
        current_date = latest_actual_time.date()
        
        market_start = pd.Timestamp(datetime.datetime.combine(current_date, datetime.time(9, 30)))
        market_end = pd.Timestamp(datetime.datetime.combine(current_date, datetime.time(16, 0)))
        
        # FIX: lowercase 's' for modern Pandas compatibility
        full_schedule = pd.date_range(start=market_start, end=market_end, periods=50).round('s')
        chart_data = pd.DataFrame(index=full_schedule, columns=cum_returns.columns)
        
        safe_returns = cum_returns.sort_index()
        
        for t in full_schedule:
            if t <= latest_actual_time:
                val = safe_returns.asof(t)
                chart_data.loc[t] = val.fillna(0.0)
                
        # Force the starting point of the canvas to rest exactly at 0.0%
        chart_data.iloc[0] = 0.0
    else:
        # Standard downsampling algorithm for other preset views
        if len(cum_returns) > 50:
            indices = np.linspace(0, len(cum_returns) - 1, 50).astype(int)
            chart_data = cum_returns.iloc[indices]
        else:
            chart_data = cum_returns

    # Grab performance metrics using raw historical boundaries (avoiding downsampling bias)
    latest_port = cum_returns['My Portfolio'].iloc[-1]
    latest_bench = cum_returns[benchmark].iloc[-1]
    
    # Render UI Header Components
    col1, col2 = st.columns(2)
    col1.metric(f"Portfolio Growth ({time_filter})", f"{latest_port:.2f}%")
    col2.metric(f"VFV.TO Growth ({time_filter})", f"{latest_bench:.2f}%")
    
    # Display the final synchronized line chart
    st.line_chart(chart_data)
    st.caption(f"Chart resolution normalized to 50 points. Performance charts are indexed to 0% at inception.")