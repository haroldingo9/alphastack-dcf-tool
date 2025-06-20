import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import requests, re
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands
import pandas_ta as ta

st.set_page_config(page_title="AlphaStack+", layout="wide")
st.title("📊 AlphaStack+: Valuation & Technical Analysis Platform")

# Sidebar stress test events
st.sidebar.header("⚙️ Settings")
stress_events = st.sidebar.multiselect(
    "Stress Events to Compare",
    ["COVID-19 (2020)", "2008 Financial Crisis", "Scam 1992"]
)

# Peer fallback
FALLBACK_PEERS = {"TCS.NS": ["INFY.NS","WIPRO.NS","HCLTECH.NS","TECHM.NS"]}
@st.cache_data(ttl=3600)
def get_peers(tk):
    try:
        r = requests.get(f"https://finance.yahoo.com/quote/{tk}", headers={"User-Agent":"Mozilla/5.0"})
        syms = re.findall(r'"symbol":"([A-Z\.]+)"', r.text)
        return [s for s in syms if "." in s and s!=tk][:5]
    except:
        return FALLBACK_PEERS.get(tk, [])

# Inputs
ticker = st.text_input("Enter ticker (e.g., TCS.NS)", "TCS.NS")

st.header("🔧 Valuation Inputs")
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

# Upload template
st.subheader("📂 Upload Your Financials (optional override)")
uploaded = st.file_uploader("CSV/XLSX: Year, Revenue, EBIT, CapEx, Dep, ΔWC, Cash, Debt, Shares", type=["csv","xlsx"])
if uploaded:
    df_up = pd.read_csv(uploaded) if uploaded.name.endswith("csv") else pd.read_excel(uploaded)
    df_up = df_up.sort_values("Year")

# Sample
with st.expander("📄 Sample Input Template"):
    sample = pd.DataFrame({
        "Year":[2020,2021,2022,2023],
        "Revenue":[10000,11000,12500,14000],
        "EBIT":[2000,2200,2500,2800],
        "CapEx":[500,550,600,650],
        "Dep":[300,320,350,380],
        "ΔWC":[-100,-80,-60,-40],
        "Cash":[1000,1200,1400,1600],
        "Debt":[800,850,900,950],
        "Shares":[100,100,100,100]
    })
    st.dataframe(sample)
    st.download_button("Download CSV Sample", data=sample.to_csv(index=False), file_name="alphastack_sample.csv")

# Generate valuation
if st.button("🚀 Generate Valuation"):
    stock = yf.Ticker(ticker)
    info = stock.info
    hist_1y = stock.history(period="1y")
    price = hist_1y["Close"].iloc[-1]
    pe = info.get("trailingPE", np.nan)

    st.subheader(f"{info.get('shortName','')} | {info.get('industry','')}")
    st.write(f"Market Cap: ₹{info.get('marketCap',0):,} | PE: {pe:.1f} | Div Yield: {info.get('dividendYield',0)*100:.2f}%")

    # Use upload or default data
    if uploaded:
        last = df_up.iloc[-1]
        rev,ebit = last["Revenue"],last["EBIT"]
        capex,dep,wc = last["CapEx"],last["Dep"],last["ΔWC"]
        cash,debt,shares = last["Cash"],last["Debt"],last["Shares"]
    else:
        rev=info.get("totalRevenue",1e9); ebit=rev*(ebit_m/100)
        capex,dep,wc=rev*.05,rev*.03,rev*.01
        cash,debt=info.get("totalCash",0),info.get("totalDebt",0)
        shares=info.get("sharesOutstanding",1e7)

    # DCF
    nopat=ebit*(1-tax_r/100); base_fcfn=nopat+dep-capex-wc
    rows=[(i, base_fcfn*((1+rev_g/100)**i),
            base_fcfn*((1+rev_g/100)**i)/((1+wacc/100)**i)) for i in range(1,yrs_f+1)]
    df_dcf=pd.DataFrame(rows,columns=["Year","FCF","Disc_FCF"])
    last_fcf = df_dcf["FCF"].iloc[-1]
    tv=(last_fcf*(1+term_g/100))/(wacc/100-term_g/100)
    disc_tv=tv/((1+wacc/100)**yrs_f)
    ev = df_dcf["Disc_FCF"].sum() + disc_tv
    eqv = ev + cash - debt
    ivps = eqv/shares

    st.subheader("📈 Forecast and Valuation Results")
    st.dataframe(df_dcf)
    st.write(f"**Enterprise Value:** ₹{ev:,.2f}")
    st.write(f"**Equity Value:** ₹{eqv:,.2f}")
    st.write(f"**Intrinsic Value / share:** ₹{ivps:,.2f}")
    diff = (ivps-price)/price*100
    st.info(f"🧠 Valuation Insight: Stock appears **{'undervalued' if diff>0 else 'overvalued'}** by {abs(diff):.1f}%")

    # Peer comparison
    peers=get_peers(ticker.upper())
    if peers:
        data=[]
        for p in peers:
            pi=yf.Ticker(p).info
            data.append({
                "Ticker":p,
                "PE":pi.get("trailingPE",np.nan),
                "MarketCap":pi.get("marketCap",0),
                "RevenueGrowth%":pi.get("revenueGrowth",0)*100 if pi.get("revenueGrowth") else np.nan
            })
        dfp=pd.DataFrame(data)
        st.subheader("🔍 Peer Comparison")
        st.dataframe(dfp)
    else:
        st.warning("No peers detected.")

    # Stress tests
    st.subheader("🧨 Stress Testing against market events")
    events={"COVID-19 (2020)":("2020-02-01","2020-04-01"),
            "2008 Financial Crisis":("2008-09-01","2008-11-01"),
            "Scam 1992":("1992-04-01","1992-05-15")}
    for ev in stress_events:
        dates = events.get(ev)
        if dates:
            dfc=yf.download(ticker,start=dates[0],end=dates[1])
            dfm=yf.download("^NSEI" if ticker.endswith(".NS") else "^GSPC",
                            start=dates[0],end=dates[1])
            if not dfc.empty and not dfm.empty:
                pct_stock=(dfc["Close"].iloc[-1]-dfc["Close"].iloc[0])/dfc["Close"].iloc[0]*100
                pct_index=(dfm["Close"].iloc[-1]-dfm["Close"].iloc[0])/dfm["Close"].iloc[0]*100
                adjusted=price*(1+pct_index/100)
                st.write(f"{ev}: Stock fell **{pct_stock:.1f}%**, sector/market fell **{pct_index:.1f}%**, adj price ≈ ₹{adjusted:,.2f}")
            else:
                st.warning(f"No data for {ev}")

    # 1-year candlestick chart
    st.subheader("📊 1-Year Candlestick Chart")
    fig=go.Figure(data=[go.Candlestick(x=hist_1y.index,
        open=hist_1y["Open"],high=hist_1y["High"],low=hist_1y["Low"],close=hist_1y["Close"])])
    st.plotly_chart(fig,use_container_width=True)

    # Technical analysis
    st.subheader("📌 Technical Analysis Insights")
    dfta = hist_1y.ta.indicators()  # via pandas_ta
    short=hist_1y["Close"].tail(90)
    rsi=RSIIndicator(short).rsi().iloc[-1]
    macd_diff = MACD(short).macd_diff().iloc[-1]
    bb = BollingerBands(short).bollinger_hband().iloc[-1]
    price_now = short.iloc[-1]

    # Support/resistance levels
    piv_hi=short[(short.shift(1)<short)&(short.shift(-1)<short)]
    piv_lo=short[(short.shift(1)>short)&(short.shift(-1)>short)]
    sup=list(piv_lo.nsmallest(3).round(2))
    res=list(piv_hi.nlargest(3).round(2))

    st.write("Support levels:", sup)
    st.write("Resistance levels:", res)
    # Patterns count
    patterns=[]
    if len(piv_lo)>=2 and abs(piv_lo.nsmallest(2).diff().iloc[-1])<price_now*0.05:
        patterns.append("Double Bottom")
    if short.iloc[-1]>bb:
        patterns.append("Breakout above Bollinger Band")
    if rsi>70 and macd_diff<0:
        patterns.append("Bearish divergence")
    if rsi<30 and macd_diff>0:
        patterns.append("Bullish divergence")

    st.write("Patterns detected:", patterns if patterns else "None")
    if patterns:
        st.write("Most recent:", patterns[-1])

    # Disclaimer
    st.write("> ⚠️ *All data and analysis is for educational purposes only.*")






