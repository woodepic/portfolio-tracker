import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import plotly.graph_objects as go

# Set up the mobile-friendly page layout
st.set_page_config(page_title="My Portfolio Tracker", layout="centered")

# --- AGGRESSIVE MOBILE UI OPTIMIZATIONS (CSS INJECTION) ---
st.markdown("""
<style>
    /* 1. Strip the thick default padding to make the app edge-to-edge and pull it to the top */
    .block-container {
        padding-top: 0rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        padding-bottom: 0rem !important;
        max-width: 100% !important;
    }
    
    /* 2. Drag the main title upward to eliminate dead space */
    h1 {
        padding-top: 0rem !important;
        margin-top: -1rem !important;
    }
    
    /* 3. Force columns to stay side-by-side on mobile by disabling flex-wrap */
    div[data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
    }
    div[data-testid="column"] {
        width: 50% !important;
        flex: 1 1 50% !important;
        min-width: 50% !important;
    }
    
    /* 4. Hide the Streamlit header and footer to gain vertical space */
    header {visibility: hidden;}
    footer {visibility: hidden;}
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

today = pd.Timestamp(datetime.date.today())

# Determine the exact "Buy Date" and set the maximum allowable API fetch window
if time_filter == "Custom Date":
    custom_date = st.date_input("Compare from date:", value=datetime.date(2026, 6, 8))
    buy_date = pd.Timestamp(custom_date)
    window_days = (today - buy_date).days
    
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
    
    if time_filter == "ALL":
        buy_date = None
    elif time_filter == "1D":
        buy_date = pd.Timestamp(datetime.datetime.combine(today.date(), datetime.time(9, 30)))
    else:
        buy_date = today - time_delta

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

# 2. ISOLATE THE EXACT BUY PRICE
if buy_date is not None:
    actual_buy_date_index = padded_prices.index[padded_prices.index >= buy_date]
    if actual_buy_date_index.empty:
        st.warning("Not enough data for this specific time period. The ETFs may not have existed yet.")
        st.stop()
    buy_date_prices = padded_prices.loc[actual_buy_date_index[0]]
else:
    buy_date_prices = padded_prices.iloc[0]

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

col1, col2 = st.columns(2)
col1.metric(f"Portfolio Growth", f"{latest_port:.2f}%")
col2.metric(f"VFV.TO Growth", f"{latest_bench:.2f}%")

# 4. PLOTLY INTEGRATION
fig = go.Figure()

fig.add_trace(go.Scatter(x=cum_returns.index, y=cum_returns['My Portfolio'], mode='lines', name='My Portfolio', line=dict(color='#3b82f6', width=2)))
fig.add_trace(go.Scatter(x=cum_returns.index, y=cum_returns[benchmark], mode='lines', name='VFV.TO', line=dict(color='#10b981', width=2)))

if buy_date is not None:
    x_axis_start = buy_date
else:
    x_axis_start = cum_returns.index.min()

fig.update_layout(
    height=350, 
    xaxis_range=[x_axis_start, cum_returns.index.max()],
    margin=dict(l=0, r=0, t=10, b=0),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode="x unified",
    xaxis_title=None,
    yaxis_title=None, 
    dragmode='pan'
)

fig.update_yaxes(ticksuffix="%")

st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False, 'scrollZoom': True})