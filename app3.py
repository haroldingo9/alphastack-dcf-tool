import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import requests, re
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands

# --- Setup ---
st.set_page_config(page_title="AlphaStack+ | Advanced Valuation", layout="wide")
st.title("📊 AlphaStack+: Advanced Valuation & Chart Analysis")

# --- Sidebar Settings ---
st.sidebar.header("⚙️ Settings")
stress_event = st.sidebar.multiselect(
    "Stress Events", ["COVID-19 (2020)", "2008 Financial Crisis"]
)

# --- Peer Detection ---
FALLBACK = {"TCS.NS": ["INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"]}
@st.cache_data(ttl=3600)
def get_peers(tk):
    try:
        r = requests.get(f"https://finance.yahoo.com/quote/{tk}", headers={"User-Agent": "Mozilla/5.0"})
        syms = re.findall(r'"symbol":"([A-Z\.]+)"', r.text)
        return [s for s in syms if "." in s and s != tk][:5]
    except:
        return FALLBACK.get(tk, [])

# --- Inputs ---
ticker = st.text_input("Ticker (e.g., TCS.NS)", "TCS.NS")
st.header("🔧 DCF Assumptions")
col1, col2, col3 = st.columns(3)
with col1:
    rev_g = st.slider("Revenue Growth %", 0.0, 30.0, 10.0)
    term_g = st.slider("Terminal Growth %", 0.0, 10.0, 3.0)
with col2:
    ebit_m = st.slider("EBIT Margin %", 0.0, 50.0, 20.0)
    tax_r = st.slider("Tax Rate %", 0.0, 50.0, 25.0)
with col3:
    wacc = st.slider("WACC %", 0.0, 30.0, 10.0)
    yrs_f = st.slider("Forecast Years", 1, 10, 5)

uploaded = st.file_uploader(
    "Optional: Upload Financials (CSV/XLSX columns: Year,Revenue,EBIT,CapEx,Dep,ΔWC,Cash,Debt,Shares)",
    type=["csv", "xlsx"],
)
if uploaded:
    df_up = pd.read_csv(uploaded) if uploaded.name.endswith("csv") else pd.read_excel(uploaded)
    df_up = df_up.sort_values("Year")

# --- Generate Valuation ---
if st.button("🚀 Generate Analysis"):
    stock = yf.Ticker(ticker)
    info = stock.info
    hist_1y = stock.history(period="1y")
    hist_6m = stock.history(period="6mo")
    price = hist_1y["Close"].iloc[-1]
    pe = info.get("trailingPE", np.nan)

    st.subheader(f"🏢 {info.get('shortName','')} | {info.get('industry','')}")
    st.write(f"Market Cap: ₹{info.get('marketCap',0):,}, PE: {pe:.1f}, Div Yield: {info.get('dividendYield',0)*100:.2f}%")

    # Load financials
    if uploaded:
        last = df_up.iloc[-1]
        rev, ebit = last["Revenue"], last["EBIT"]
        capex, dep, wc = last["CapEx"], last["Dep"], last["ΔWC"]
        cash, debt, shares = last["Cash"], last["Debt"], last["Shares"]
    else:
        rev = info.get("totalRevenue", 1e9); ebit = rev*(ebit_m/100)
        capex, dep, wc = rev*.05, rev*.03, rev*.01
        cash, debt = info.get("totalCash",0), info.get("totalDebt",0)
        shares = info.get("sharesOutstanding",1e7)

    # DCF
    nopat = ebit*(1-tax_r/100)
    base_fcf = nopat + dep - capex - wc
    years = [(i, base_fcf*((1+rev_g/100)**i),
              base_fcf*((1+rev_g/100)**i)/(1+wacc/100)**i) for i in range(1,yrs_f+1)]
    df_dcf = pd.DataFrame(years, columns=["Year","FCF","Disc FCF"])
    last_fcf = df_dcf["FCF"].iloc[-1]
    tv = (last_fcf*(1+term_g/100))/(wacc/100-term_g/100)
    disc_tv = tv/(1+wacc/100)**yrs_f
    ev = df_dcf["Disc FCF"].sum() + disc_tv
    eqv = ev + cash - debt
    ivps = eqv/shares

    st.subheader("💰 Valuation Summary")
    st.success(f"EV: ₹{ev:,.2f}   |   Equity: ₹{eqv:,.2f}   |   IV/share: ₹{ivps:,.2f}")

    # Relative Valuation
    peers = get_peers(ticker.upper())
    peer_pes = []
    st.subheader("📊 Peer Comparison")
    if peers:
        peer_data=[]
        for p in peers:
            pi = yf.Ticker(p).info
            peer_data.append({
                "Ticker":p,
                "PE":pi.get("trailingPE", np.nan),
                "MarketCap":pi.get("marketCap",np.nan),
                "RevGrowth":pi.get("revenueGrowth",0)*100 if pi.get("revenueGrowth") else np.nan
            })
            peer_pes.append(pi.get("trailingPE", np.nan))
        df_p = pd.DataFrame(peer_data)
        st.dataframe(df_p)
        peer_pe_med = np.nanmedian(peer_pes)
        rel_val = ivps * peer_pe_med
        st.write(f"Relative Valuation ≈ ₹{rel_val:,.2f} (Peer median PE × IV/share)")
    else:
        st.warning("No peers found")

    # EVA
    capital = rev - wc  # simple proxy
    eva = nopat - (capital * wacc/100)
    st.write(f"📈 Economic Value Added (EVA): ₹{eva:,.2f}")

    # AI-style summary
    diff = (ivps-price)/price*100
    summary = f"{ticker} appears {'undervalued' if diff>0 else 'overvalued'} by {abs(diff):.1f}%."
    summary += f" Peer median PE is {peer_pe_med:.1f}× vs {ticker} at {pe:.1f}×."
    rsi = RSIIndicator(hist_6m["Close"]).rsi().iloc[-1]
    summary += f" RSI (6M) = {rsi:.1f}."
    st.info(summary)

    # Stress Tests
    st.subheader("🧨 Stress Test")
    events={"COVID-19 (2020)":("2020-02-01","2020-04-01"), "2008 Financial Crisis":("2008-09-01","2008-11-01")}
    for ev in stress_event:
        dr = yf.download(ticker, start=events[ev][0], end=events[ev][1])
        if not dr.empty:
            drop=(dr["Close"].iloc[-1]-dr["Close"].iloc[0])/dr["Close"].iloc[0]*100
            st.write(f"{ev} drop: {drop:.1f}%. Simulated = ₹{price*(1+drop/100):,.2f}")
        else:
            st.warning(f"No {ev} data")

    # 1Y Price + 6M Candles
    st.subheader("📈 1‑Year Price Chart")
    fig1=go.Figure([go.Scatter(x=hist_1y.index, y=hist_1y["Close"], name="Close")])
    st.plotly_chart(fig1, use_container_width=True)

    st.subheader("📊 6‑Month Candlestick + Patterns")
    hc = go.Candlestick(x=hist_6m.index, open=hist_6m["Open"], high=hist_6m["High"],
                        low=hist_6m["Low"], close=hist_6m["Close"])
    fig2 = go.Figure(data=[hc])
    st.plotly_chart(fig2, use_container_width=True)

    # Identify simple support/resistance by pivot highs/lows
    prices = hist_6m["Close"]
    pivots = prices[(prices.shift(1)<prices)&(prices.shift(-1)<prices)]
    supports = prices[(prices.shift(1)>prices)&(prices.shift(-1)>prices)]
    st.write("• Resistance levels:", ", ".join([f"₹{p:.2f}" for p in pivots.nlargest(2)]))
    st.write("• Support levels:", ", ".join([f"₹{p:.2f}" for p in supports.nsmallest(2)]))

    # Simple two-bottom pattern detection
    if len(supports)>=2 and abs(supports.nsmallest(2).diff().iloc[-1])< price*0.05:
        st.info("📌 Detected: Double Bottom pattern – potential bullish reversal.")






