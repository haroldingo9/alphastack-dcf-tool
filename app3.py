import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import requests, re
from bs4 import BeautifulSoup

# --- Page Setup ---
st.set_page_config(page_title="AlphaStack | DCF Tool", layout="wide")
st.title("📊 AlphaStack: Multi‑Year Data‑Driven Valuation")
st.markdown("Use your multi‑year financials to derive forecast assumptions automatically.")

# --- Peer Detection ---
@st.cache_data(ttl=3600)
def get_yahoo_peers(ticker):
    try:
        url = f"https://finance.yahoo.com/quote/{ticker}/"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
        syms = re.findall(r'"symbol":"([A-Z\.]+)"', r.text)
        peers=[]
        for s in syms:
            if s!=ticker and "." in s and s not in peers:
                peers.append(s)
            if len(peers)>=5: break
        return peers
    except:
        return []

# --- Sidebar & Inputs ---
st.sidebar.header("⚙️ Settings")
stress_event = st.sidebar.selectbox("Stress Test Event", [
    "None","COVID‑19 (2020)","2008 Financial Crisis","Great Depression","Scam 1992"
])
model = st.sidebar.selectbox("Valuation Model", ["DCF","Relative (P/E)","Dividend Discount (DDM)"])

ticker = st.text_input("Enter Stock Ticker", "TCS.NS")

# --- Upload & Sample Template ---
st.subheader("📂 Upload Multi‑Year Financials (2020–2024, etc.)")
uploaded = st.file_uploader(
    "CSV/Excel w/ cols: Year, Revenue, EBIT, Net Income, CapEx, Depreciation, ΔWC, Cash, Debt, Shares",
    type=["csv","xlsx"]
)
with st.expander("📘 Sample Template"):
    sample = pd.DataFrame({
        "Year":[2020,2021,2022,2023,2024],
        "Revenue":[45000,48000,52000,56000,60000],
        "EBIT":[9000,9600,10400,11200,12000],
        "Net Income":[6500,7000,7600,8200,9000],
        "CapEx":[1200,1300,1400,1500,1600],
        "Depreciation":[800,850,900,950,1000],
        "ΔWC":[-700,-600,-500,-450,-400],
        "Cash":[15000,16000,17000,18000,20000],
        "Debt":[8000,8200,8400,9000,10000],
        "Shares":[350,350,350,350,350]
    })
    st.dataframe(sample)
    st.download_button("📥 Download Sample", data=sample.to_csv(index=False),
                       file_name="financials_sample.csv", mime="text/csv")

# --- Derive Historical Ratios if Uploaded ---
if uploaded:
    df_fin = pd.read_csv(uploaded) if uploaded.name.endswith("csv") else pd.read_excel(uploaded)
    df_fin = df_fin.sort_values("Year")
    # CAGR in Revenue
    yrs = df_fin["Year"].iloc[-1] - df_fin["Year"].iloc[0]
    rev_cagr = ((df_fin["Revenue"].iloc[-1] / df_fin["Revenue"].iloc[0])**(1/yrs) - 1)*100
    # Avg historical EBIT margin
    ebit_margin_hist = (df_fin["EBIT"]/df_fin["Revenue"]).mean()*100
    # Avg ratios
    capex_ratio = (df_fin["CapEx"]/df_fin["Revenue"]).mean()*100
    dep_ratio   = (df_fin["Depreciation"]/df_fin["Revenue"]).mean()*100
    wc_ratio    = (df_fin["ΔWC"]/df_fin["Revenue"]).mean()*100
    cash_override  = df_fin["Cash"].iloc[-1]
    debt_override  = df_fin["Debt"].iloc[-1]
    shares_override= df_fin["Shares"].iloc[-1]
else:
    rev_cagr = ebit_margin_hist = capex_ratio = dep_ratio = wc_ratio = None
    cash_override = debt_override = shares_override = None

# --- Sliders with Defaults from History if Available ---
st.header("🔧 Forecast Assumptions")
col1,col2 = st.columns(2)
with col1:
    revenue_growth  = st.slider(
        "Revenue Growth % p.a.",
        0.0, 50.0,
        float(rev_cagr) if rev_cagr else 10.0, 0.1
    )
    ebit_margin     = st.slider(
        "EBIT Margin %",
        0.0, 50.0,
        float(ebit_margin_hist) if ebit_margin_hist else 20.0,0.1
    )
    terminal_growth = st.slider("Terminal Growth Rate %",0.0,10.0,3.0,0.1)
with col2:
    tax_rate        = st.slider("Tax Rate % of EBIT",0.0,50.0,25.0,0.1)
    discount_rate   = st.slider("Discount Rate WACC %",0.0,30.0,10.0,0.1)
    forecast_years  = st.slider("Forecast Period (yrs)",1,10,5)

# --- Generate Valuation ---
if st.button("🚀 Generate Valuation"):
    try:
        # Pull market data
        stock = yf.Ticker(ticker)
        info  = stock.info
        hist  = stock.history(period="1y")
        price = float(hist["Close"].iloc[-1])

        # Snapshot
        st.subheader(f"🏢 {info.get('shortName',ticker)}")
        st.write(f"Sector: {info.get('sector','N/A')} | Industry: {info.get('industry','N/A')}")
        st.write(f"Market Cap: ₹{info.get('marketCap',0):,} | PE: {info.get('trailingPE','N/A')} | Div Yield: {info.get('dividendYield',0)*100:.2f}%")

        # Use latest overrides or yfinance fallbacks
        revenue = df_fin["Revenue"].iloc[-1] if uploaded else info.get("totalRevenue",1e3)
        ebit     = revenue*(ebit_margin/100)
        cash     = cash_override if uploaded else info.get("totalCash",0)
        debt     = debt_override if uploaded else info.get("totalDebt",0)
        shares   = shares_override if uploaded else info.get("sharesOutstanding",1)
        capex    = revenue*(capex_ratio/100) if uploaded else 0
        dep      = revenue*(dep_ratio/100)   if uploaded else 0
        wc       = revenue*(wc_ratio/100)    if uploaded else 0

        # DCF Model
        def run_dcf():
            tax   = ebit*(tax_rate/100)
            nopat = ebit - tax
            base  = nopat + dep - capex - wc
            rows=[]
            for y in range(1,forecast_years+1):
                proj = base*((1+revenue_growth/100)**y)
                disc = proj/((1+discount_rate/100)**y)
                rows.append((y,round(proj,2),round(disc,2)))
            df = pd.DataFrame(rows,columns=["Year","Proj FCF","Disc FCF"])
            st.markdown("### 🔢 DCF Cash Flows")
            st.dataframe(df)
            last=rows[-1][1]
            tv  =(last*(1+terminal_growth/100))/((discount_rate/100)-(terminal_growth/100))
            dtv =tv/((1+discount_rate/100)**forecast_years)
            ev  =df["Disc FCF"].sum()+dtv
            eqv =ev+cash-debt
            return ev,eqv,eqv/shares

        # Relative P/E
        def run_pe():
            eps=info.get("trailingEps") or info.get("forwardEps") or (ebit/shares)
            pe =info.get("trailingPE") or 0
            st.markdown(f"### 🔢 P/E Model\n• EPS: {eps:.2f}\n• P/E: {pe:.2f}")
            return None,None,eps*pe

        # DDM
        def run_ddm():
            div=info.get("dividendRate") or 0
            if div and (discount_rate/100-terminal_growth/100)>0:
                val=div/(discount_rate/100-terminal_growth/100)
                st.markdown(f"### 🔢 DDM Model\n• Div/Share: {div:.2f}")
                return None,None,val
            st.warning("No dividend or invalid rates for DDM."); return None,None,None

        # Execute
        if model=="DCF":  ev,eqv,iv=run_dcf()
        elif model=="Relative (P/E)": ev,eqv,iv=run_pe()
        else: ev,eqv,iv=run_ddm()

        # Show results
        if iv is not None:
            if ev is not None:
                st.success(f"Enterprise Value: ₹{ev:,.2f}")
                st.success(f"Equity Value:     ₹{eqv:,.2f}")
            st.success(f"Intrinsic Value/share: ₹{iv:,.2f}")
            pct=(iv-price)/price*100
            tag="Undervalued" if pct>0 else "Overvalued"
            st.info(f"🧠 {tag} by {abs(pct):.1f}% (market ₹{price:.2f} vs IV ₹{iv:.2f})")

        # Price Chart
        st.markdown("### 📉 1Y Price Chart")
        fig,ax=plt.subplots(); hist["Close"].plot(ax=ax,title=f"{ticker} 1Y"); st.pyplot(fig)

        # Peer Comparison
        st.markdown("### 🥊 Peers")
        peers=get_yahoo_peers(ticker)
        if peers:
            rows=[]
            for p in peers:
                pi=yf.Ticker(p).info
                rows.append({"Ticker":p,"PE":pi.get("trailingPE"),"Mkt Cap":pi.get("marketCap"),"RevGrowth":pi.get("revenueGrowth")})
            st.dataframe(pd.DataFrame(rows))
        else:
            st.info("No peers found.")

        # Stress Test
        if stress_event!="None":
            evts={
                "COVID‑19 (2020)":("2020-02-15","2020-03-23"),
                "2008 Financial Crisis":("2008-09-01","2008-10-15"),
                "Great Depression":("1929-09-01","1930-06-01"),
                "Scam 1992":("1992-04-01","1992-05-15")
            }
            s,e=evts[stress_event]
            crash=yf.download(ticker,start=s,end=e)
            if not crash.empty:
                p0=float(crash["Close"].iloc[0]); p1=float(crash["Close"].iloc[-1])
                drop=(p1-p0)/p0*100; sim=price*(1+drop/100)
                st.markdown("### 🧨 Stress Test")
                st.warning(f"During {stress_event}, fell {drop:.1f}%")
                st.info(f"Simulated today: ₹{sim:.2f} vs ₹{price:.2f}")
            else:
                st.error("No data for that event.")

    except Exception as e:
        st.error(f"Error: {e}")






