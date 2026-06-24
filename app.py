import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import plotly.graph_objects as go

# Set up the mobile-friendly page layout
st.set_page_config(page_title="My Portfolio Tracker", layout="centered")

# --- AGGRESSIVE MOBILE UI OPTIMIZATIONS ---
st.markdown("""
<style>
    /* Strip the thick default padding to make the app edge-to-edge */
    .block-container {
        padding-top: 0rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        padding-bottom: 0rem !important;
        max-width: 100% !important;
    }
    
    /* Drag the main title upward to eliminate dead space */
    h1 {
        padding-top: 0rem !important;
        margin-top: -1rem !important;
        margin-bottom: 0.5rem !important;
    }
    
    /* Hide the Streamlit header and footer */
    header {visibility: hidden;}
    footer {visibility: hidden;}

    /* Force the browser to pass pinch gestures directly to the chart */
    div[data-testid="stPlotlyChart"] {
        touch-action: pan-y pinch-zoom !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("Portfolio vs. VFV.TO")

portfolio_weights = {
    'AVUS': 0.43,
    'CACE.TO': 0.10,
    'CADE.TO': 0.25,
    'CAEM.TO': 0.10,
    'CASV.TO': 0.12
}
benchmark = 'VFV.TO'

# 1. UI Elements
time_filter = st.radio(
    "Select Investment 'Buy' Date:", 
    ["1D", "1W", "1M", "3M", "6M", "1Y", "ALL", "Custom Date"], 
    horizontal=True
)

# We still use today temporarily just to determine the API fetch window depth
today = pd.Timestamp(datetime.date.today())

if time_filter == "Custom Date":
    custom_date = st.date_input("Compare from date:", value=datetime.date(2026, 6, 8))
    window_days = (today - pd.Timestamp(custom_date)).days
    
    if window_days <= 7:
        period_str, interval_str = "1mo", "15m"
    elif window_days <= 60:
        period_str, interval_str = "730d", "1h"
    else:
        period_str, interval_str = "10y", "1d"
else:
    mapping = {
        "1D": (pd.Timedelta(days=1), "1mo", "5m"),    
        "1W": (pd.Timedelta(days=7), "1mo", "15m"),   
        "1M": (pd.Timedelta(days=30), "730d", "1h"),  
        "3M": (pd.Timedelta(days=90), "730d", "1h"),  
        "6M": (pd.Timedelta(days=180), "10y", "1d"),  
        "1Y": (pd.Timedelta(days=365), "10y", "1d"),
        "ALL": (None, "10y", "1d")
    }
    time_delta, period_str, interval_str = mapping[time_filter]

@st.cache_data(ttl=60)
def load_data(period, interval):
    tickers = list(portfolio_weights.keys()) + [benchmark, 'CAD=X']
    data = yf.download(tickers, period=period, interval=interval)['Close']
    data.index = data.index.tz_localize(None)
    
    missing_tickers = [col for col in data.columns if data[col].isna().all()]
    if missing_tickers:
        st.error(f"Yahoo Finance has no data for: {', '.join(missing_tickers)}.")
        st.stop()
        
    data = data.ffill().dropna()
    if data.empty:
        st.error("The data table is empty. The selected timeframe predates the launch of these ETFs.")
        st.stop()
        
    data['AVUS_CAD'] = data['AVUS'] * data['CAD=X']
    cols_to_keep = ['AVUS_CAD', 'CACE.TO', 'CADE.TO', 'CAEM.TO', 'CASV.TO', benchmark]
    return data[cols_to_keep]

with st.spinner("Fetching maximum allowable market data..."):
    try:
        padded_prices = load_data(period_str, interval_str)
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.stop()

# 2. ISOLATE THE EXACT BUY PRICE (FIXED LOGIC)
if time_filter == "1D":
    # BUG 2 FIX: Identify the latest market day, completely ignoring your phone's clock
    latest_day = padded_prices.index.max().normalize()
    
    # BUG 1 FIX: Grab all data strictly prior to this latest day to find yesterday's closing price
    prior_prices = padded_prices.loc[padded_prices.index < latest_day]
    
    if not prior_prices.empty:
        buy_date_prices = prior_prices.iloc[-1]
    else:
        buy_date_prices = padded_prices.iloc[0]
        
    x_axis_start = latest_day + pd.Timedelta(hours=9, minutes=30)

elif time_filter == "ALL":
    buy_date_prices = padded_prices.iloc[0]
    x_axis_start = padded_prices.index.min()

elif time_filter == "Custom Date":
    target_date = pd.Timestamp(custom_date)
    valid_indices = padded_prices.index[padded_prices.index >= target_date]
    if valid_indices.empty:
        st.warning("Not enough data for this specific time period. The ETFs may not have existed yet.")
        st.stop()
    buy_date_prices = padded_prices.loc[valid_indices[0]]
    x_axis_start = target_date

else:
    # BUG 2 FIX: Calculate time windows backward from the market's latest timestamp, not midnight tonight
    latest_timestamp = padded_prices.index.max()
    target_date = latest_timestamp - time_delta
    
    valid_indices = padded_prices.index[padded_prices.index >= target_date]
    if valid_indices.empty:
        buy_date_prices = padded_prices.iloc[0]
    else:
        buy_date_prices = padded_prices.loc[valid_indices[0]]
        
    x_axis_start = target_date

# 3. BUY AND HOLD MATH
normalized_prices = padded_prices / buy_date_prices

cum_returns = pd.DataFrame(index=normalized_prices.index)
cum_returns['My Portfolio'] = (
    (normalized_prices['AVUS_CAD'] * portfolio_weights['AVUS'] +
     normalized_prices['CACE.TO'] * portfolio_weights['CACE.TO'] +
     normalized_prices['CADE.TO'] * portfolio_weights['CADE.TO'] +
     normalized_prices['CAEM.TO'] * portfolio_weights['CAEM.TO'] +
     normalized_prices['CASV.TO'] * portfolio_weights['CASV.TO']) - 1
) * 100
cum_returns[benchmark] = (normalized_prices[benchmark] - 1) * 100

latest_port = cum_returns['My Portfolio'].iloc[-1]
latest_bench = cum_returns[benchmark].iloc[-1]

# HTML Flexbox for perfect side-by-side spacing
st.markdown(f"""
<div style="display: flex; gap: 2.5rem; margin-top: 10px; margin-bottom: 5px;">
    <div>
        <div style="font-size: 0.85rem; color: #a1a1aa; margin-bottom: -5px;">Portfolio Growth</div>
        <div style="font-size: 2.2rem; font-weight: 600;">{latest_port:.2f}%</div>
    </div>
    <div>
        <div style="font-size: 0.85rem; color: #a1a1aa; margin-bottom: -5px;">VFV.TO Growth</div>
        <div style="font-size: 2.2rem; font-weight: 600;">{latest_bench:.2f}%</div>
    </div>
</div>
""", unsafe_allow_html=True)

# 4. PLOTLY INTEGRATION
fig = go.Figure()

fig.add_trace(go.Scatter(x=cum_returns.index, y=cum_returns['My Portfolio'], mode='lines', name='My Portfolio', line=dict(color='#3b82f6', width=2)))
fig.add_trace(go.Scatter(x=cum_returns.index, y=cum_returns[benchmark], mode='lines', name='VFV.TO', line=dict(color='#10b981', width=2)))

fig.update_layout(
    height=380, 
    xaxis_range=[x_axis_start, cum_returns.index.max()],
    margin=dict(l=0, r=0, t=10, b=0),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode="x unified",
    xaxis_title=None,
    yaxis_title=None, 
    dragmode='pan',
    xaxis=dict(fixedrange=False),
    yaxis=dict(fixedrange=False)
)

fig.update_yaxes(ticksuffix="%")

# Adds the minimal toolbar back to guarantee pinch-to-zoom works on iOS without cluttering the screen
minimal_config = {
    'displayModeBar': True,
    'displaylogo': False,
    'modeBarButtonsToRemove': [
        'lasso2d', 'select2d', 'autoScale2d', 
        'hoverClosestCartesian', 'hoverCompareCartesian', 'toggleSpikelines'
    ]
}

st.plotly_chart(fig, use_container_width=True, config=minimal_config)
