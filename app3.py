import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import requests, re
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands

# --- Page Setup ---
st.set_page_config(page_title="AlphaStack Valuation", layout="wide")
st.title("📊 AlphaStack: Valuation + Technical Insights")

# --- Sidebar ---
st.sidebar.header("⚙️ Settings")
stress_event = st.sidebar.multiselect(
    "Stress Test Events",
    ["COVID-19 (2020)", "2008 Financial Crisis"]
)

# --- Peer Detection via Yahoo + Fallback ---
FALLBACK = {
    "TCS.NS": ["INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
}
@st.cache_data(ttl=3600)
def get_peers(tk):
    try:
        r = requests.get(f"https://finance.yahoo.com/quote/{tk}/", headers={"User-Agent":"Mozilla/5.0"})
        syms = re.findall(r'"symbol":"([A-Z\.]+)"', r.text)
        peers = [s for s in syms if s != tk and "." in s][:5]
        return peers if peers else FALLBACK.get(tk, [])
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

st.subheader("📂 Optional Financials Upload")
uploaded = st.file_uploader("CSV/XLSX: Year,Revenue,EBIT,CapEx,Dep,ΔWC,Cash,Debt,Shares", type=["csv","xlsx"])
if uploaded:
    df_up = pd.read_csv(uploaded) if uploaded.name.endswith("csv") else pd.read_excel(uploaded)
    df_up = df_up.sort_values("Year")

# --- Generate Valuation ---
if st.button("🚀 Generate Valuation"):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        st.subheader(f"🏢 {info.get('shortName','')} | {info.get('industry','')}")
        st.write(f"Market Cap: ₹{info.get('marketCap',0):,} | PE: {info.get('trailingPE','N/A')} | Div Yield: {info.get('dividendYield',0)*100:.2f}%")

        hist = stock.history(period="1y")
        current_price = hist["Close"].iloc[-1]

        # Use upload or default assumptions
        if uploaded:
            last = df_up.iloc[-1]
            rev, ebit = last["Revenue"], last["EBIT"]
            capex, dep, wc = last["CapEx"], last["Dep"], last["ΔWC"]
            cash, debt, shares = last["Cash"], last["Debt"], last["Shares"]
        else:
            rev = info.get("totalRevenue", 1e9)
            ebit = rev * (ebit_m/100)
            capex, dep, wc = rev*.05, rev*.03, rev*.01
            cash, debt = info.get("totalCash",0), info.get("totalDebt",0)
            shares = info.get("sharesOutstanding",1e7)

        nopat = ebit*(1-tax_r/100)
        base_fcf = nopat + dep - capex - wc

        dcf_list = []
        for i in range(1, yrs_f+1):
            fcf = base_fcf * ((1+rev_g/100)**i)
            disc = fcf/((1+wacc/100)**i)
            dcf_list.append((i, round(fcf,2), round(disc,2)))
        df_dcf = pd.DataFrame(dcf_list, columns=["Year","FCF","Disc FCF"])
        st.subheader("🔢 Forecasted Cash Flows")
        st.dataframe(df_dcf)

        last_fcf = df_dcf["FCF"].iloc[-1]
        tv = (last_fcf*(1+term_g/100))/(wacc/100 - term_g/100)
        disc_tv = tv/((1+wacc/100)**yrs_f)

        ev = df_dcf["Disc FCF"].sum()+disc_tv
        eqv = ev + cash - debt
        ivps = eqv/shares

        st.subheader("💰 Valuation Summary")
        st.success(f"Enterprise Value: ₹{ev:,.2f}")
        st.success(f"Equity Value: ₹{eqv:,.2f}")
        st.success(f"Intrinsic Value/share: ₹{ivps:,.2f}")

        diff = (ivps-current_price)/current_price*100
        st.markdown(f"🧠 **Insight**: Stock appears **{'undervalued' if diff>0 else 'overvalued'}** by {abs(diff):.1f}% (Mkt vs IV)")

        # --- Peer Comparison ---
        peers = get_peers(ticker.upper())
        if peers:
            data = {"Ticker":[],"PE":[],"Mkt Cap":[], "Rev Growth %":[]}
            for p in peers:
                pi = yf.Ticker(p).info
                data["Ticker"].append(p)
                data["PE"].append(pi.get("trailingPE"))
                data["Mkt Cap"].append(pi.get("marketCap"))
                data["Rev Growth %"].append(pi.get("revenueGrowth",0)*100 if pi.get("revenueGrowth") else None)
            df_p = pd.DataFrame(data)
            st.subheader("📊 Peer Comparison")
            st.dataframe(df_p)
        else:
            st.warning("No peers detected.")

        # --- Stress Tests ---
        st.subheader("🧨 Stress Test Results")
        events = {
            "COVID-19 (2020)":("2020-02-01","2020-04-01"),
            "2008 Financial Crisis":("2008-09-01","2008-11-01")
        }
        for ev in stress_event:
            start, end = events.get(ev)
            dfc = yf.download(ticker, start=start, end=end)
            if not dfc.empty:
                pct = (dfc["Close"].iloc[-1]-dfc["Close"].iloc[0])/dfc["Close"].iloc[0]*100
                sim = current_price*(1+pct/100)
                st.warning(f"During {ev}, stock fell {pct:.1f}%. If repeated, price ∼₹{sim:,.2f}")
            else:
                st.error(f"No data for {ev}")

        # --- Stock Chart + Technicals ---
        st.subheader("📈 Price Chart + Technical Pattern (30D)")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist.index, y=hist["Close"], name="Close"))
        st.plotly_chart(fig, use_container_width=True)

        short = hist["Close"].tail(30)
        rsi, macd = RSIIndicator(short).rsi().iloc[-1], MACD(short).macd_diff().iloc[-1]
        bb = BollingerBands(short).bollinger_hband().iloc[-1]
        pat = ""
        if rsi>70 and macd<0:
            pat="🔻 Bearish divergence (Overbought)"
        elif rsi<30 and macd>0:
            pat="🔼 Bullish divergence (Oversold)"
        elif short.iloc[-1]>bb:
            pat="📈 Price above upper Bollinger Band (Breakout)"
        else:
            pat="🔍 No clear pattern"

        st.info(f"🧠 Technical Pattern: {pat}")

    except Exception as e:
        st.error(f"Error: {e}")






