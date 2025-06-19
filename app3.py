import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objs as go
import requests, re
from bs4 import BeautifulSoup

# --- Page Config ---
st.set_page_config(page_title="AlphaStack | Valuation", layout="wide")
st.title("📊 AlphaStack: Interactive Valuation + Peers")

# --- Peer Scraper + Fallback ---
@st.cache_data(ttl=3600)
def get_yahoo_peers(ticker):
    try:
        url = f"https://finance.yahoo.com/quote/{ticker}/"
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        syms = re.findall(r'"symbol":"([A-Z\.]+)"', r.text)
        peers = []
        for s in syms:
            if s != ticker and "." in s and s not in peers:
                peers.append(s)
            if len(peers) >= 5:
                break
        return peers
    except:
        return []

# Static fallback map for common Indian tickers
FALLBACK = {
    "TCS.NS":        ["INFY.NS","WIPRO.NS","TECHM.NS","HCLTECH.NS"],
    "BRITANNIA.NS":  ["NESTLEIND.NS","HINDUNILVR.NS","ITC.NS"],
    "RELIANCE.NS":   ["IOC.NS","ONGC.NS","BPCL.NS"],
    "HDFCBANK.NS":   ["ICICIBANK.NS","KOTAKBANK.NS","AXISBANK.NS"]
}

# --- Sidebar ---
st.sidebar.header("⚙️ Settings")
stress_event = st.sidebar.selectbox("Stress Test Event", [
    "None","COVID‑19 (2020)","2008 Financial Crisis","Great Depression","Scam 1992"
])
model = st.sidebar.selectbox("Valuation Model", ["DCF","Relative (P/E)","DDM"])

ticker = st.text_input("Stock Ticker (e.g. TCS.NS)", "TCS.NS")

# --- Upload & Sample ---
st.subheader("📂 Upload Multi‑Year Financials")
uploaded = st.file_uploader("CSV/XLSX with Year, Revenue, EBIT, CapEx, Dep, ΔWC, Cash, Debt, Shares", type=["csv","xlsx"])
with st.expander("📘 Sample Template"):
    sample = pd.DataFrame({
        "Year":[2020,2021,2022,2023,2024],
        "Revenue":[45000,48000,52000,56000,60000],
        "EBIT":[9000,9600,10400,11200,12000],
        "CapEx":[1200,1300,1400,1500,1600],
        "Dep":[800,850,900,950,1000],
        "ΔWC":[-700,-600,-500,-450,-400],
        "Cash":[15000,16000,17000,18000,20000],
        "Debt":[8000,8200,8400,9000,10000],
        "Shares":[350,350,350,350,350]
    })
    st.dataframe(sample)
    st.download_button("📥 Download Sample", data=sample.to_csv(index=False), file_name="sample.csv")

# --- Compute Historical Defaults ---
if uploaded:
    df_hist = pd.read_csv(uploaded) if uploaded.name.endswith("csv") else pd.read_excel(uploaded)
    df_hist = df_hist.sort_values("Year")
    yrs = df_hist["Year"].iloc[-1] - df_hist["Year"].iloc[0]
    rev_cagr = ((df_hist["Revenue"].iloc[-1]/df_hist["Revenue"].iloc[0])**(1/yrs)-1)*100
    ebit_m_hist = (df_hist["EBIT"]/df_hist["Revenue"]).mean()*100
    capex_r = (df_hist["CapEx"]/df_hist["Revenue"]).mean()*100
    dep_r   = (df_hist["Dep"]/df_hist["Revenue"]).mean()*100
    wc_r    = (df_hist["ΔWC"]/df_hist["Revenue"]).mean()*100
    cash_o  = df_hist["Cash"].iloc[-1]
    debt_o  = df_hist["Debt"].iloc[-1]
    shares_o= df_hist["Shares"].iloc[-1]
else:
    rev_cagr= ebit_m_hist= capex_r= dep_r= wc_r= None
    cash_o= debt_o= shares_o= None

# --- Sliders seeded by history ---
st.header("🔧 Forecast Assumptions")
col1,col2 = st.columns(2)
with col1:
    revenue_growth  = st.slider("Revenue Growth %", 0.0,50.0, float(rev_cagr) if rev_cagr else 10.0, 0.1)
    ebit_margin     = st.slider("EBIT Margin %", 0.0,50.0, float(ebit_m_hist) if ebit_m_hist else 20.0, 0.1)
    terminal_growth = st.slider("Terminal Growth %", 0.0,10.0,3.0, 0.1)
with col2:
    tax_rate        = st.slider("Tax Rate %", 0.0,50.0,25.0,0.1)
    discount_rate   = st.slider("WACC %", 0.0,30.0,10.0,0.1)
    forecast_years  = st.slider("Forecast Years",1,10,5)

# --- Generate ---
if st.button("🚀 Generate Valuation"):
    try:
        stock = yf.Ticker(ticker)
        info  = stock.info
        hist  = stock.history(period="1y")
        price = float(hist["Close"].iloc[-1])

        # Snapshot
        st.subheader(f"🏢 {info.get('shortName',ticker)}")
        st.write(f"Sector: {info.get('sector','N/A')} | Industry: {info.get('industry','N/A')}")
        st.write(f"Market Cap: ₹{info.get('marketCap',0):,} | PE: {info.get('trailingPE','N/A')} | Div Yield: {info.get('dividendYield',0)*100:.2f}%")

        # Inputs (override or yf)
        revenue = df_hist["Revenue"].iloc[-1] if uploaded else info.get("totalRevenue",1e3)
        ebit     = revenue*(ebit_margin/100)
        cash     = cash_o if uploaded else info.get("totalCash",0)
        debt     = debt_o if uploaded else info.get("totalDebt",0)
        shares   = shares_o if uploaded else info.get("sharesOutstanding",1)
        capex    = revenue*(capex_r/100) if uploaded else 0
        dep      = revenue*(dep_r/100)   if uploaded else 0
        wc       = revenue*(wc_r/100)    if uploaded else 0

        # DCF
        def run_dcf():
            tax   = ebit*(tax_rate/100)
            nopat = ebit-tax
            base  = nopat+dep-capex-wc
            rows=[]
            for y in range(1,forecast_years+1):
                p=base*((1+revenue_growth/100)**y)
                d=p/((1+discount_rate/100)**y)
                rows.append((y,round(p,2),round(d,2)))
            df=pd.DataFrame(rows,columns=["Year","Proj FCF","Disc FCF"])
            st.markdown("### 🔢 DCF Cash Flows"); st.dataframe(df)
            last=rows[-1][1]
            tv=(last*(1+terminal_growth/100))/((discount_rate/100)-(terminal_growth/100))
            dtv=tv/((1+discount_rate/100)**forecast_years)
            ev=df["Disc FCF"].sum()+dtv; eqv=ev+cash-debt
            return ev,eqv,eqv/shares

        # Execute only DCF for brevity here… (or keep your multi‐model logic)

        ev,eqv,iv = run_dcf()
        st.success(f"Enterprise Value: ₹{ev:,.2f}")
        st.success(f"Equity Value:     ₹{eqv:,.2f}")
        st.success(f"IV/share:         ₹{iv:,.2f}")
        pct=(iv-price)/price*100
        st.info(f"🧠 Insight: {'Undervalued' if pct>0 else 'Overvalued'} by {abs(pct):.1f}%")

        # Interactive Plotly Chart
        st.markdown("### 📉 1Y Price Chart")
        fig = go.Figure([go.Scatter(x=hist.index, y=hist["Close"], mode="lines", name="Close")])
        fig.update_layout(title=f"{ticker} 1Y Price", xaxis_title="Date", yaxis_title="Price")
        st.plotly_chart(fig, use_container_width=True)

        # Peers with fallback
        peers = get_yahoo_peers(ticker) or FALLBACK.get(ticker.upper(), [])
        st.markdown("### 🥊 Peers")
        if peers:
            comp=[]
            for p in peers:
                pi=yf.Ticker(p).info
                comp.append({"Ticker":p,"PE":pi.get("trailingPE"),"MktCap":pi.get("marketCap"),"RevGrw":pi.get("revenueGrowth")})
            st.dataframe(pd.DataFrame(comp))
        else:
            st.info("No peers found.")

        # Stress Test (same as before)…

    except Exception as e:
        st.error(f"Error: {e}")






