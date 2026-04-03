import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- DATABASE LAYER ---
def get_connection():
    return sqlite3.connect('calif_boss_v19.db', check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # product_type: 'Mzinga', 'Quarter', or 'Standard'
    c.execute('''CREATE TABLE IF NOT EXISTS products 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, category TEXT, 
                  product_type TEXT, buying_price REAL, selling_price REAL, stock REAL)''')
    # Added 'unit_sold' to track if it was a Full, Half, or Cup
    c.execute('''CREATE TABLE IF NOT EXISTS sales 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, product_name TEXT, category TEXT, quantity REAL, 
                  unit_sold TEXT, sell_price REAL, buying_price REAL, profit REAL, 
                  payment_method TEXT, timestamp DATETIME)''')
    c.execute('''CREATE TABLE IF NOT EXISTS expenses 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, amount REAL, 
                  description TEXT, timestamp DATETIME)''')
    conn.commit()
    conn.close()

init_db()

# --- MAXIMALIST STYLING ---
st.set_page_config(page_title="CALIFORNIA BOSS V19", layout="wide", page_icon="🔞")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Archivo+Black&family=Space+Mono:wght@400;700&display=swap');

    /* ===== GLOBAL RESET ===== */
    .stApp { background-color: #E0E0E0; font-family: 'Archivo Black', sans-serif; }
    .stMainBlockContainer { padding-top: 0 !important; }
    [data-testid="stMainBlockContainer"] { padding-top: 0 !important; }

    /* ===== HIDE STREAMLIT CHROME ===== */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header[data-testid="stHeader"] { display: none !important; }
    .stDeployButton { display: none !important; }

    /* ===== FIXED HEADER — SINGLE ROW, ALL ON ONE LINE ===== */
    .header-container {
        background-color: #000000;
        border-bottom: 8px solid #FF007A;
        position: fixed; top: 0; left: 0; right: 0; z-index: 9999999;
        width: 100%; box-sizing: border-box;
        padding: 10px 14px;
        display: flex; flex-direction: row;
        align-items: center; justify-content: space-between; gap: 10px;
    }
    .header-text {
        font-size: clamp(1.1rem, 4vw, 2rem);
        color: #CCFF00; text-transform: uppercase; text-align: left;
        line-height: 1; margin: 0; flex-shrink: 0;
        -webkit-text-stroke: 1px #FF007A;
        letter-spacing: 1px;
    }
    .header-status-row {
        display: flex; align-items: center; gap: 8px; flex-shrink: 0;
        margin-left: auto;
    }
    .blink-circle {
        width: 12px; height: 12px; min-width: 12px; background-color: #00FF00;
        border-radius: 50%; box-shadow: 0 0 10px #00FF00;
        animation: blinker 1s linear infinite; flex-shrink: 0;
    }
    @keyframes blinker { 50% { opacity: 0; } }
    .live-label {
        font-family: 'Space Mono', monospace; font-size: 0.6rem;
        color: #00FF00; white-space: nowrap; letter-spacing: 1px;
    }
    .live-clock {
        font-family: 'Space Mono', monospace; font-size: 0.7rem;
        color: #CCFF00; background: #111; padding: 4px 10px;
        border: 1px solid #CCFF00; letter-spacing: 1px; white-space: nowrap;
    }

    /* ===== SPACER — pushes content below fixed header ===== */
    .spacer { height: 62px; }
    @media (max-width: 480px) { .spacer { height: 66px; } }

    /* ===== FULL SCREEN SALE POPUP ===== */
    .sale-overlay {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background-color: #CCFF00; z-index: 99999;
        display: flex; flex-direction: column; justify-content: center;
        align-items: center; border: 20px solid black; text-align: center;
        padding: 20px; box-sizing: border-box;
    }
    .sold-text {
        font-size: clamp(4rem, 18vw, 10rem);
        color: black; margin: 0; line-height: 0.85;
        font-family: 'Archivo Black', sans-serif;
    }
    .sold-subtext {
        font-size: clamp(1rem, 4vw, 2.2rem);
        color: #FF007A; background: black; padding: 10px 20px; margin-top: 20px;
        word-break: break-word; max-width: 90vw;
        font-family: 'Archivo Black', sans-serif;
    }
    .sold-dbtext {
        color: black; font-weight: bold; margin-top: 10px;
        font-size: clamp(0.8rem, 3vw, 1.4rem);
        font-family: 'Archivo Black', sans-serif;
    }
    /* Pure HTML X button — top right corner */
    .x-close-btn {
        position: fixed; top: 24px; right: 24px;
        width: 60px; height: 60px;
        background: #000; color: #CCFF00;
        border: 5px solid #CCFF00;
        font-size: 1.8rem; font-family: 'Archivo Black', sans-serif;
        font-weight: 900; cursor: pointer;
        box-shadow: 4px 4px 0px #FF007A;
        display: flex; align-items: center; justify-content: center;
        z-index: 9999999;
    }
    .x-close-btn:hover { background: #FF007A; color: white; }
    /* Pure HTML next transaction button */
    .next-sale-btn {
        margin-top: 35px;
        background: #000; color: white;
        border: 6px solid #000;
        font-size: clamp(1rem, 4vw, 1.6rem);
        font-family: 'Archivo Black', sans-serif;
        font-weight: 900; text-transform: uppercase;
        padding: 18px 30px; cursor: pointer;
        box-shadow: 8px 8px 0px #FF007A;
        max-width: 90vw;
    }
    .next-sale-btn:hover { background: #FF007A; box-shadow: none; }

    /* ===== CUSTOM METRIC CARDS ===== */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
        gap: 10px; margin-bottom: 20px;
    }
    .metric-card {
        background: white; border: 5px solid black;
        padding: 12px 10px; box-shadow: 6px 6px 0px black;
        text-align: center;
    }
    .metric-card .m-label {
        font-size: 0.65rem; text-transform: uppercase; color: #555;
        letter-spacing: 1px; margin-bottom: 4px;
    }
    .metric-card .m-value {
        font-size: clamp(1.2rem, 4vw, 2rem);
        color: black; font-weight: 900; line-height: 1;
    }
    .mc-revenue { background-color: #2563EB; color: white; border-color: #2563EB; }
    .mc-revenue .m-label, .mc-revenue .m-value { color: white; }
    .mc-profit  { background-color: #FF007A; border-color: #FF007A; }
    .mc-profit .m-label, .mc-profit .m-value { color: white; }
    .mc-cash    { background-color: #CCFF00; }
    .mc-cash .m-label, .mc-cash .m-value { color: black; }
    .mc-mpesa   { background-color: #ffffff; border: 5px solid #2ECC71; }
    .mc-mpesa .m-label { color: #2ECC71; }
    .mc-mpesa .m-value { color: #2ECC71; }
    .mc-keg     { background-color: #000000; }
    .mc-keg .m-label, .mc-keg .m-value { color: #CCFF00; }

    /* ===== NEO CARDS ===== */
    .neo-card {
        background: #FFFFFF; border: 6px solid #000000;
        padding: 15px; box-shadow: 8px 8px 0px #000000;
        margin-bottom: 20px;
    }

    /* ===== KPI BOXES (Analytics) ===== */
    .kpi-container { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 25px; }
    .kpi-box { padding: 15px; border: 6px solid black; box-shadow: 6px 6px 0px black; text-align: center; }
    .kpi-box h3 { font-size: 0.7rem; margin: 0 0 6px; text-transform: uppercase; letter-spacing: 1px; }
    .kpi-box h1 { font-size: clamp(1.3rem, 4vw, 2rem); margin: 0; }
    .kpi-cash   { background-color: #2563EB; color: white; }
    .kpi-mpesa  { background-color: #FFFFFF; color: #2ECC71; }
    .kpi-profit { background-color: #FF007A; color: white; }
    .kpi-keg    { background-color: #CCFF00; color: black; }

    /* ===== BUTTONS ===== */
    .stButton>button {
        background-color: #000000 !important; color: #FFFFFF !important;
        border: 4px solid #000000 !important; border-radius: 0px !important;
        font-weight: 900 !important; text-transform: uppercase;
        box-shadow: 5px 5px 0px #FF007A !important;
        height: 3.5rem !important; width: 100% !important;
        font-size: clamp(0.75rem, 2.5vw, 1rem) !important;
        margin-top: 8px;
    }
    .stButton>button:hover {
        background-color: #CCFF00 !important; color: #000 !important;
        transform: translate(2px, 2px); box-shadow: 2px 2px 0px black !important;
    }

    /* ===== MISC ===== */
    .stDataFrame { border: 4px solid black !important; }

    /* ===== EXPENSE EDITOR CARDS ===== */
    .expense-editor-card {
        background: #fff; border: 4px solid #000; padding: 12px;
        box-shadow: 5px 5px 0px #FF007A; margin-bottom: 12px;
    }
    .expense-editor-header {
        font-size: 0.85rem; font-weight: 900; text-transform: uppercase;
        background: black; color: #CCFF00; padding: 4px 10px; margin-bottom: 8px;
        display: inline-block;
    }

    /* ===== EOD CARD ===== */
    .eod-card {
        background: black; color: white; border: 5px solid #CCFF00;
        padding: 20px; box-shadow: 10px 10px 0px #FF007A; margin-bottom: 20px;
    }
    .eod-row {
        display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px;
    }
    .eod-cell { border-top: 1px solid #333; padding-top: 10px; }
    .eod-cell p { margin: 0; font-size: 0.8rem; text-transform: uppercase; }
    .eod-cell h2 { margin: 0; font-size: clamp(1.2rem, 4vw, 2rem); }

</style>
""", unsafe_allow_html=True)

# --- APP SESSION STATE ---
if 'sale_complete' not in st.session_state: st.session_state.sale_complete = False
if 'sale_msg' not in st.session_state: st.session_state.sale_msg = ""
if 'vault_unlocked' not in st.session_state: st.session_state.vault_unlocked = False

# --- UTILITY FUNCTIONS ---
def run_query(q):
    conn = get_connection()
    df = pd.read_sql(q, conn)
    conn.close()
    return df

def execute_db(q, params=()):
    conn = get_connection()
    c = conn.cursor()
    c.execute(q, params)
    conn.commit()
    conn.close()

def record_sale(p_id, p_name, cat, qty, s_price, b_price, method, unit):
    profit = s_price - b_price
    conn = get_connection(); c = conn.cursor()
    c.execute("""INSERT INTO sales (product_name, category, quantity, unit_sold, sell_price, buying_price, profit, payment_method, timestamp) 
                 VALUES (?,?,?,?,?,?,?,?,?)""",
              (p_name, cat, qty, unit, s_price, b_price, profit, method, datetime.now()))
    c.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (qty, p_id))
    conn.commit(); conn.close()
    st.session_state.sale_msg = f"{p_name} ({unit}) SOLD FOR KES {s_price:,.0f}/-"
    st.session_state.sale_complete = True

# --- FIXED RESPONSIVE HEADER ---
now = datetime.now()
st.markdown(f"""
    <div class="header-container">
        <div class="header-text">CLUB CALIFORNIA</div>
        <div class="header-status-row">
            <div class="blink-circle"></div>
            <div class="live-label">LIVE</div>
            <div class="live-clock" id="live-clock">{now.strftime('%d %b %Y | %H:%M:%S')}</div>
        </div>
    </div>
    <div class="spacer"></div>
    <script>
        (function() {{
            function pad(n) {{ return String(n).padStart(2,'0'); }}
            function updateClock() {{
                var el = document.getElementById('live-clock');
                if (!el) return;
                var d = new Date();
                var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
                el.textContent = pad(d.getDate()) + ' ' + months[d.getMonth()] + ' ' + d.getFullYear()
                               + ' | ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
            }}
            setInterval(updateClock, 1000);
            updateClock();
        }})();
    </script>
""", unsafe_allow_html=True)

# --- FULL SCREEN SALE POPUP ---
# THE PERMANENT SOLUTION:
# st.components.v1.html() renders inside its own iframe which IS allowed to 
# navigate window.parent. We render the entire SOLD overlay as a component 
# that covers 100vw/100vh of the PARENT window. The close buttons call 
# window.parent.location.reload() which triggers a full Streamlit rerun, 
# and since sale_complete is stored in session_state (server-side), 
# it stays False after the record_sale sets it and rerun clears it.
# We use a hidden st.button as the actual Streamlit trigger, and the 
# component clicks it via postMessage → no iframe escaping needed.

if st.session_state.sale_complete:
    # Render hidden trigger button - invisible via CSS on its wrapper
    st.markdown('<div id="close-sale-wrapper" style="position:fixed;top:-999px;left:-999px;width:1px;height:1px;overflow:hidden;opacity:0;pointer-events:none;">', unsafe_allow_html=True)
    clicked = st.button("__CLOSE_SALE_INTERNAL__", key="close_sale_hidden")
    st.markdown('</div>', unsafe_allow_html=True)
    if clicked:
        st.session_state.sale_complete = False
        st.rerun()

    sale_msg_safe = st.session_state.sale_msg.replace("'", "\\'")
    components.html(f"""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Archivo+Black&display=swap');
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{
            background: #CCFF00;
            font-family: 'Archivo Black', sans-serif;
            display: flex; flex-direction: column;
            justify-content: center; align-items: center;
            width: 100vw; height: 100vh;
            border: 20px solid black;
            text-align: center; padding: 20px;
            overflow: hidden;
        }}
        .x-btn {{
            position: fixed; top: 20px; right: 20px;
            width: 64px; height: 64px;
            background: #000; color: #CCFF00;
            border: 5px solid #CCFF00;
            font-size: 2rem; font-family: 'Archivo Black', sans-serif;
            font-weight: 900; cursor: pointer;
            box-shadow: 4px 4px 0px #FF007A;
            display: flex; align-items: center; justify-content: center;
            z-index: 9999;
        }}
        .x-btn:active {{ background: #FF007A; }}
        .sold-txt {{
            font-size: clamp(5rem, 20vw, 12rem);
            color: black; line-height: 0.85;
        }}
        .sold-sub {{
            font-size: clamp(1rem, 4vw, 2rem);
            color: #FF007A; background: black;
            padding: 12px 24px; margin-top: 24px;
            max-width: 90vw; word-break: break-word;
        }}
        .sold-db {{
            color: black; font-weight: 900; margin-top: 12px;
            font-size: clamp(0.9rem, 3vw, 1.3rem);
        }}
        .close-btn {{
            margin-top: 40px;
            background: #000; color: #fff;
            border: 6px solid #000;
            font-size: clamp(1rem, 4vw, 1.6rem);
            font-family: 'Archivo Black', sans-serif;
            font-weight: 900; text-transform: uppercase;
            padding: 20px 36px; cursor: pointer;
            box-shadow: 8px 8px 0px #FF007A;
            max-width: 90vw;
        }}
        .close-btn:active {{ background: #FF007A; box-shadow: none; }}
    </style>
    </head>
    <body>
        <button class="x-btn" onclick="doClose()">✕</button>
        <div class="sold-txt">SOLD!</div>
        <div class="sold-sub">{sale_msg_safe}</div>
        <div class="sold-db">✅ DATABASE UPDATED SECURELY</div>
        <button class="close-btn" onclick="doClose()">✖ CLOSE &amp; NEXT TRANSACTION ➔</button>
        <script>
        function doClose() {{
            // Click the hidden Streamlit button in the parent frame
            var btns = window.parent.document.querySelectorAll('button');
            for (var i = 0; i < btns.length; i++) {{
                if (btns[i].innerText === '__CLOSE_SALE_INTERNAL__') {{
                    btns[i].click();
                    return;
                }}
            }}
            // Fallback: reload the parent page
            window.parent.location.reload();
        }}
        </script>
    </body>
    </html>
    """, height=700, scrolling=False)
    st.stop()

# --- NAVIGATION (MOBILE OPTIMIZED, DISTINCT ICONS PER TAB) ---
with st.sidebar:
    st.markdown("<br><br><h1>CALIF MENU</h1>", unsafe_allow_html=True)
    page = st.radio("GO TO",
                    ["🛒 POS TERMINAL",
                     "📈 ANALYTICS & PROFIT",
                     "💸 OVERHEADS",
                     "🔐 ADMIN VAULT"],
                    label_visibility="collapsed")
    st.markdown("---")
    if st.button("🔄 REFRESH APP"): st.rerun()

# ============================================================
# --- 🛒 1. POS TERMINAL ---
# ============================================================
if page == "🛒 POS TERMINAL":
    df_p = run_query("SELECT * FROM products")
    if df_p.empty:
        st.error("INVENTORY IS EMPTY. GO TO ADMIN VAULT TO ADD STOCK.")
    else:
        # Distinct icons per category tab
        cats  = ["KEG",   "Beers", "Spirits", "Wines", "Sodas", "Energy Drinks", "Condoms"]
        icons = ["🍺",    "🍾",   "🥃",     "🍷",   "🥤",   "⚡",            "🛡️"]
        tabs = st.tabs([f"{icons[i]} {cats[i]}" for i in range(len(cats))])

        for i, tab in enumerate(tabs):
            with tab:
                category = cats[i]
                items = df_p[df_p['category'] == category]

                if items.empty:
                    st.info(f"Nothing in {category} yet.")
                    continue

                cols = st.columns(2)
                for idx, row in items.reset_index(drop=True).iterrows():
                    with cols[idx % 2]:
                        st.markdown(f"""
                            <div class="neo-card">
                                <h2 style="margin:0; font-size:clamp(0.9rem,3vw,1.3rem);">{row['name']}</h2>
                                <small style="color:grey;">TYPE: {row['product_type']}</small><br>
                                <h4 style="background:black; color:white; display:inline-block; padding:2px 8px; margin-top:5px; font-size:0.8rem;">
                                    STK: {row['stock']:.2f}
                                </h4>
                                <h3 style="color:#FF007A; margin:4px 0;">KES {row['selling_price']:,.0f}</h3>
                            </div>
                        """, unsafe_allow_html=True)

                        with st.popover(f"💵 SELL {row['name']}", use_container_width=True):
                            method = st.radio("PAYMENT", ["CASH", "M-PESA"], key=f"pay_{row['id']}")

                            if category == "KEG":
                                cost_l = 156.0
                                if st.button("CUP KUBWA (400ML @ 80/-)", key=f"kb_{row['id']}"):
                                    record_sale(row['id'], row['name'], "KEG", 0.4, 80, (0.4*cost_l), method, "400ML Cup")
                                if st.button("CUP NDOGO (200ML @ 50/-)", key=f"nd_{row['id']}"):
                                    record_sale(row['id'], row['name'], "KEG", 0.2, 50, (0.2*cost_l), method, "200ML Cup")

                            elif category == "Spirits" and row['product_type'] == "Quarter":
                                s1, s2 = st.columns(2)
                                if s1.button("FULL QTR", key=f"fq_{row['id']}"):
                                    record_sale(row['id'], row['name'], category, 1, row['selling_price'], row['buying_price'], method, "Full Quarter")
                                if s2.button("HALF QTR", key=f"hq_{row['id']}"):
                                    record_sale(row['id'], row['name'], category, 0.5, row['selling_price']*0.5, row['buying_price']*0.5, method, "Half Quarter")

                            else:
                                unit_label = "Full Bottle" if category in ["Beers", "Wines", "Spirits"] else "Unit"
                                if st.button(f"CONFIRM {unit_label}", key=f"std_{row['id']}"):
                                    record_sale(row['id'], row['name'], category, 1, row['selling_price'], row['buying_price'], method, unit_label)

# ============================================================
# --- 📈 2. ANALYTICS & PROFIT ---
# ============================================================
elif page == "📈 ANALYTICS & PROFIT":
    st.markdown("<h1 style='font-size:clamp(1.5rem,6vw,3rem);'>FINANCIAL INTEL</h1>", unsafe_allow_html=True)
    df_s = run_query("SELECT * FROM sales")

    if df_s.empty:
        st.warning("NO SALES LOGGED YET.")
    else:
        df_s['timestamp'] = pd.to_datetime(df_s['timestamp'])
        t_d, t_w, t_m = st.tabs(["⚡ DAILY", "📅 WEEKLY", "📊 MONTHLY"])
        analytics_configs = [(t_d, 0, "Daily"), (t_w, 7, "Weekly"), (t_m, 30, "Monthly")]

        for tab, days, label in analytics_configs:
            with tab:
                start_date = (datetime.now() - timedelta(days=days)).date() if days > 0 else datetime.now().date()
                v_s = df_s[df_s['timestamp'].dt.date >= start_date]

                rev   = v_s['sell_price'].sum()
                prof  = v_s['profit'].sum()
                cash  = v_s[v_s['payment_method'] == 'CASH']['sell_price'].sum()
                mpesa = v_s[v_s['payment_method'] == 'M-PESA']['sell_price'].sum()

                st.markdown(f"""
                <div class="kpi-container">
                    <div class="kpi-box kpi-keg"><h3>REVENUE</h3><h1>{rev:,.0f}</h1></div>
                    <div class="kpi-box kpi-profit"><h3>PROFIT</h3><h1>{prof:,.0f}</h1></div>
                    <div class="kpi-box kpi-cash"><h3>CASH</h3><h1>{cash:,.0f}</h1></div>
                    <div class="kpi-box kpi-mpesa"><h3>M-PESA</h3><h1>{mpesa:,.0f}</h1></div>
                </div>
                """, unsafe_allow_html=True)

                c1, c2 = st.columns(2)
                with c1:
                    chart_df = v_s.groupby(v_s['timestamp'].dt.date)[['sell_price', 'profit']].sum().reset_index()
                    fig = px.bar(chart_df, x='timestamp', y=['sell_price', 'profit'], barmode='group',
                                 title=f"{label} Sales vs Profit", color_discrete_sequence=['#2563EB', '#FF007A'])
                    st.plotly_chart(fig, use_container_width=True, key=f"sales_chart_{label}")
                with c2:
                    top_sellers = v_s.groupby('product_name')['sell_price'].sum().sort_values(ascending=False).head(5).reset_index()
                    fig_top = px.bar(top_sellers, x='sell_price', y='product_name', orientation='h',
                                     title="Top 5 Brands", color_discrete_sequence=['#CCFF00'])
                    st.plotly_chart(fig_top, use_container_width=True, key=f"top_chart_{label}")

        st.markdown("### 🍺 KEG LIVE LEVEL")
        keg_stk = run_query("SELECT stock FROM products WHERE category = 'KEG' LIMIT 1")
        if not keg_stk.empty:
            rem = keg_stk.iloc[0]['stock']
            cur_mtungi = rem % 50 if rem % 50 != 0 else (50 if rem > 0 else 0)
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number", value=cur_mtungi,
                title={'text': f"LITRES LEFT (Total: {rem:.1f}L)"},
                gauge={'axis': {'range': [0, 50]}, 'bar': {'color': "#CCFF00"}, 'bgcolor': "black"}
            ))
            st.plotly_chart(fig_gauge, use_container_width=True, key="keg_gauge")

# ============================================================
# --- 💸 3. OVERHEADS (WITH EXPENSE EDITOR) ---
# ============================================================
elif page == "💸 OVERHEADS":
    st.markdown("<h1 style='font-size:clamp(1.5rem,6vw,3rem);'>EXPENSE TRACKER</h1>", unsafe_allow_html=True)

    with st.expander("➕ LOG NEW EXPENSE", expanded=True):
        with st.form("overhead_form"):
            cat = st.selectbox("CATEGORY", ["Rent", "Electricity", "Staff Wages", "Security", "DJ", "Other"])
            amt = st.number_input("AMOUNT (KES)", min_value=0)
            note = st.text_input("REMARK")
            if st.form_submit_button("LOCK EXPENSE"):
                execute_db("INSERT INTO expenses (category, amount, description, timestamp) VALUES (?,?,?,?)",
                           (cat, amt, note, datetime.now()))
                st.success("✅ EXPENSE SAVED")
                st.rerun()

    # --- EXPENSE EDITOR (edit/delete locked entries) ---
    st.markdown("---")
    st.markdown("<h2 style='font-size:clamp(1rem,4vw,1.8rem);'>🛠️ EXPENSE EDITOR</h2>", unsafe_allow_html=True)
    st.caption("Tap any entry below to edit or delete it.")

    df_e = run_query("SELECT * FROM expenses ORDER BY timestamp DESC")
    if df_e.empty:
        st.info("No expenses logged yet.")
    else:
        # Summary totals above the editor
        total_exp = df_e['amount'].sum()
        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card mc-profit">
                <div class="m-label">TOTAL EXPENSES</div>
                <div class="m-value">KES {total_exp:,.0f}</div>
            </div>
            <div class="metric-card mc-keg">
                <div class="m-label">NO. OF ENTRIES</div>
                <div class="m-value">{len(df_e)}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        for idx, row in df_e.iterrows():
            ts_str = pd.to_datetime(row['timestamp']).strftime('%d %b %Y %H:%M') if row['timestamp'] else "—"
            with st.expander(f"🧾 {row['category']} — KES {row['amount']:,.0f}  |  {ts_str}"):
                st.markdown(f'<div class="expense-editor-header">EDITING ENTRY #{row["id"]}</div>', unsafe_allow_html=True)
                new_cat  = st.selectbox("Category", ["Rent", "Electricity", "Staff Wages", "Security", "DJ", "Other"],
                                        index=["Rent", "Electricity", "Staff Wages", "Security", "DJ", "Other"].index(row['category'])
                                        if row['category'] in ["Rent", "Electricity", "Staff Wages", "Security", "DJ", "Other"] else 5,
                                        key=f"ecat_{row['id']}")
                new_amt  = st.number_input("Amount (KES)", value=float(row['amount']),  min_value=0.0, key=f"eamt_{row['id']}")
                new_desc = st.text_input("Remark", value=str(row['description']) if row['description'] else "", key=f"edsc_{row['id']}")
                col_a, col_b = st.columns(2)
                if col_a.button("💾 UPDATE", key=f"eupd_{row['id']}"):
                    execute_db("UPDATE expenses SET category=?, amount=?, description=? WHERE id=?",
                               (new_cat, new_amt, new_desc, row['id']))
                    st.success("UPDATED ✅"); st.rerun()
                if col_b.button("🗑️ DELETE", key=f"edel_{row['id']}"):
                    execute_db("DELETE FROM expenses WHERE id=?", (row['id'],))
                    st.warning("DELETED"); st.rerun()

    st.markdown("---")
    st.markdown("### 📋 ALL EXPENSES LOG")
    st.dataframe(run_query("SELECT * FROM expenses ORDER BY timestamp DESC"), use_container_width=True)

# ============================================================
# --- 🔐 4. ADMIN VAULT ---
# ============================================================
elif page == "🔐 ADMIN VAULT":
    if not st.session_state.vault_unlocked:
        st.markdown("<div class='neo-card'><h1>🔐 VAULT LOCKED</h1>", unsafe_allow_html=True)
        pin = st.text_input("ENTER MASTER PIN", type="password")
        if st.button("UNLOCK VAULT"):
            if pin == "calif2026":
                st.session_state.vault_unlocked = True
                st.rerun()
            else:
                st.error("❌ ACCESS DENIED")
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        if st.button("🔒 LOCK VAULT"):
            st.session_state.vault_unlocked = False
            st.rerun()

        t1, t2, t3 = st.tabs(["📦 STOCK ENTRY", "🛠️ INVENTORY MGMT", "🌃 CLOSE DAY (EOD)"])

        # ---- TAB 1: STOCK ENTRY ----
        with t1:
            st.markdown("### ADD NEW STOCK")
            cat_n = st.selectbox("CHOOSE CATEGORY", ["KEG", "Beers", "Spirits", "Wines", "Sodas", "Energy Drinks", "Condoms"])

            with st.form("new_product_form"):
                if cat_n == "KEG":
                    qty_n = st.number_input("How many Mitungi?", min_value=1.0, step=1.0)
                    p_name, p_type, p_buy, p_sell = "KEG MTUNGI", "Standard", 7800.0, 0.0
                elif cat_n == "Spirits":
                    brand = st.text_input("Product Brand Name (e.g. Chrome, KC)")
                    p_type = st.radio("Size Type", ["Mzinga", "Quarter"])
                    p_name = f"{brand} {p_type}"
                    p_buy  = st.number_input("Buying Price (Full Bottle)")
                    p_sell = st.number_input("Selling Price (Full Bottle)")
                    qty_n  = st.number_input("Quantity of Bottles", min_value=1.0)
                else:
                    p_name = st.text_input("Product Name")
                    p_type = "Standard"
                    p_buy  = st.number_input("Buying Price")
                    p_sell = st.number_input("Selling Price")
                    qty_n  = st.number_input("Quantity", min_value=1.0)

                if st.form_submit_button("COMMIT TO INVENTORY"):
                    final_q = (qty_n * 50) if cat_n == "KEG" else qty_n
                    conn = get_connection(); c = conn.cursor()
                    try:
                        c.execute("INSERT INTO products (name, category, product_type, buying_price, selling_price, stock) VALUES (?,?,?,?,?,?)",
                                  (p_name, cat_n, p_type, p_buy, p_sell, final_q))
                    except Exception:
                        c.execute("UPDATE products SET stock = stock + ? WHERE name = ?", (final_q, p_name))
                    conn.commit(); conn.close()
                    st.success(f"✅ UPDATED: {p_name}"); st.rerun()

            st.markdown("### CURRENT INVENTORY STATUS")
            st.dataframe(run_query("SELECT name, category, product_type, stock, buying_price, selling_price FROM products"),
                         use_container_width=True)

        # ---- TAB 2: INVENTORY MANAGEMENT ----
        with t2:
            st.markdown("### UPDATE STOCK LEVELS")
            df_m = run_query("SELECT * FROM products")
            for _, row in df_m.iterrows():
                with st.expander(f"✏️ EDIT: {row['name']} ({row['product_type']})"):
                    c_a, c_b = st.columns(2)
                    new_s = c_a.number_input("Update Stock Count",    value=float(row['stock']),         key=f"s_{row['id']}")
                    new_p = c_b.number_input("Update Selling Price",  value=float(row['selling_price']), key=f"p_{row['id']}")
                    if st.button("SAVE UPDATES", key=f"btn_{row['id']}"):
                        execute_db("UPDATE products SET stock=?, selling_price=? WHERE id=?",
                                   (new_s, new_p, row['id']))
                        st.rerun()

        # ---- TAB 3: END OF DAY (DETAILED) ----
        with t3:
            st.markdown("### 🌃 END OF DAY RECONCILIATION")
            date_check = st.date_input("Select Date", datetime.now().date())
            df_day = run_query(f"SELECT * FROM sales WHERE date(timestamp) = '{date_check}'")

            if df_day.empty:
                st.warning("NO SALES DATA FOR THIS DATE.")
            else:
                # ---- EOD Calculations ----
                total_sales  = df_day['sell_price'].sum()
                total_profit = df_day['profit'].sum()
                keg_sales    = df_day[df_day['category'] == 'KEG']['sell_price'].sum()
                cash_total   = df_day[df_day['payment_method'] == 'CASH']['sell_price'].sum()
                mpesa_total  = df_day[df_day['payment_method'] == 'M-PESA']['sell_price'].sum()

                # ---- Custom Metric Cards (5 cards) ----
                st.markdown(f"""
                <div class="metric-grid">
                    <div class="metric-card mc-revenue">
                        <div class="m-label">💰 TOTAL DAILY SALES</div>
                        <div class="m-value">KES {total_sales:,.0f}</div>
                    </div>
                    <div class="metric-card mc-profit">
                        <div class="m-label">📈 TOTAL PROFIT</div>
                        <div class="m-value">KES {total_profit:,.0f}</div>
                    </div>
                    <div class="metric-card mc-keg">
                        <div class="m-label">🍺 KEG CONTRIBUTION</div>
                        <div class="m-value">KES {keg_sales:,.0f}</div>
                    </div>
                    <div class="metric-card mc-cash">
                        <div class="m-label">💵 CASH RECEIVED</div>
                        <div class="m-value">KES {cash_total:,.0f}</div>
                    </div>
                    <div class="metric-card mc-mpesa">
                        <div class="m-label">📱 M-PESA RECEIVED</div>
                        <div class="m-value">KES {mpesa_total:,.0f}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # ---- Full EOD Summary Card ----
                st.markdown(f"""
                <div class="eod-card">
                    <h2 style="color:#CCFF00; margin:0 0 5px;">🌃 EOD REPORT: {date_check}</h2>
                    <hr style="border:2px solid #333; margin: 8px 0;">
                    <div class="eod-row">
                        <div class="eod-cell">
                            <p style="color:#2563EB;">TOTAL REVENUE</p>
                            <h2 style="color:white;">KES {total_sales:,.0f}</h2>
                        </div>
                        <div class="eod-cell">
                            <p style="color:#FF007A;">TOTAL PROFIT</p>
                            <h2 style="color:white;">KES {total_profit:,.0f}</h2>
                        </div>
                        <div class="eod-cell">
                            <p>🍺 KEG TOTAL</p>
                            <h2 style="color:#CCFF00;">KES {keg_sales:,.0f}</h2>
                        </div>
                        <div class="eod-cell">
                            <p>💵 CASH TOTAL</p>
                            <h2 style="color:white;">KES {cash_total:,.0f}</h2>
                        </div>
                        <div class="eod-cell">
                            <p style="color:#2ECC71;">📱 M-PESA TOTAL</p>
                            <h2 style="color:#2ECC71;">KES {mpesa_total:,.0f}</h2>
                        </div>
                        <div class="eod-cell" style="border-top:2px solid #CCFF00;">
                            <p style="color:#CCFF00; font-size:0.9rem;">CASH + MPESA CHECK</p>
                            <h2 style="color:#CCFF00;">KES {cash_total + mpesa_total:,.0f}</h2>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown("### 📋 DAY'S TRANSACTION LOG (DETAILED)")
                st.dataframe(
                    df_day[['timestamp', 'product_name', 'unit_sold', 'quantity', 'sell_price', 'buying_price', 'profit', 'payment_method']],
                    use_container_width=True
                )

                # Category breakdown chart for the day
                st.markdown("### 📊 SALES BY CATEGORY TODAY")
                cat_breakdown = df_day.groupby('category')['sell_price'].sum().reset_index()
                fig_cat = px.pie(cat_breakdown, values='sell_price', names='category',
                                 title=f"Revenue by Category — {date_check}",
                                 color_discrete_sequence=['#2563EB', '#FF007A', '#CCFF00', '#000000', '#2ECC71', '#E0E0E0', '#FF6B6B'])
                st.plotly_chart(fig_cat, use_container_width=True, key="eod_pie")

                payment_breakdown = df_day.groupby('payment_method')['sell_price'].sum().reset_index()
                fig_pay = px.bar(payment_breakdown, x='payment_method', y='sell_price',
                                 title="Cash vs M-Pesa Today",
                                 color='payment_method',
                                 color_discrete_map={'CASH': '#CCFF00', 'M-PESA': '#2ECC71'})
                st.plotly_chart(fig_pay, use_container_width=True, key="eod_pay_bar")