import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import pytz

# --- DATABASE LAYER (PostgreSQL via Supabase — persistent on Streamlit Cloud) ---
# Requires: pip install psycopg2-binary
# Set in Streamlit Cloud Secrets:
#   [postgres]
#   url = "postgresql://user:password@db.xxx.supabase.co:5432/postgres"
import psycopg2
import psycopg2.extras

@st.cache_resource
def get_db_pool():
    from psycopg2 import pool as pg_pool
    pg = st.secrets["postgres"]
    return pg_pool.SimpleConnectionPool(
        1, 10,
        host=pg["host"],
        port=int(pg.get("port", 5432)),
        dbname=pg.get("dbname", "postgres"),
        user=pg["user"],
        password=pg["password"],
        sslmode="require",
        connect_timeout=10
    )

def get_connection():
    return get_db_pool().getconn()

def release_connection(conn):
    get_db_pool().putconn(conn)

def init_db():
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS products 
                     (id SERIAL PRIMARY KEY, name TEXT UNIQUE, category TEXT, 
                      product_type TEXT, buying_price REAL, selling_price REAL, stock REAL,
                      shots_per_bottle REAL DEFAULT 0)''')
        try:
            c.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS shots_per_bottle REAL DEFAULT 0")
        except Exception:
            pass
        c.execute('''CREATE TABLE IF NOT EXISTS sales 
                     (id SERIAL PRIMARY KEY, product_name TEXT, category TEXT, quantity REAL, 
                      unit_sold TEXT, sell_price REAL, buying_price REAL, profit REAL, 
                      payment_method TEXT, timestamp TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS expenses 
                     (id SERIAL PRIMARY KEY, category TEXT, amount REAL, 
                      description TEXT, timestamp TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS activity_log 
                     (id SERIAL PRIMARY KEY, action_type TEXT, description TEXT, 
                      "user" TEXT DEFAULT 'ADMIN', timestamp TIMESTAMP)''')
        c.execute('''CREATE TABLE IF NOT EXISTS keg_settings
                     (id SERIAL PRIMARY KEY, size_name TEXT UNIQUE, ml REAL, price REAL)''')
        # Insert defaults if not present
        c.execute("""INSERT INTO keg_settings (size_name, ml, price) VALUES ('ndogo', 200, 60)
                     ON CONFLICT (size_name) DO NOTHING""")
        c.execute("""INSERT INTO keg_settings (size_name, ml, price) VALUES ('kubwa', 400, 80)
                     ON CONFLICT (size_name) DO NOTHING""")
        c.execute("""INSERT INTO keg_settings (size_name, ml, price) VALUES ('jug', 1200, 240)
                     ON CONFLICT (size_name) DO NOTHING""")
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        release_connection(conn)

init_db()

# --- MAXIMALIST STYLING ---
st.set_page_config(page_title="CALIFORNIA BOSS V19", layout="wide", page_icon="🔞", initial_sidebar_state="collapsed")

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

    /* ===== STICKY HEADER — moves with page, sidebar-aware ===== */
    .header-container {
        background-color: #000000;
        border-bottom: 8px solid #FF007A;
        position: sticky; top: 0; left: 0; right: 0; z-index: 9999;
        width: 100%; box-sizing: border-box;
        padding: 10px 14px 10px 56px;
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

    /* ===== SPACER — no longer needed with sticky header ===== */
    .spacer { height: 0px; }

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

    /* ===== SIDEBAR COLLAPSE BUTTON — styled to match California Boss ===== */
    button[data-testid="stSidebarCollapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        position: fixed !important;
        top: 10px !important;
        left: 10px !important;
        z-index: 10100 !important;
        background: #CCFF00 !important;
        border: 3px solid #000000 !important;
        border-radius: 4px !important;
        width: 36px !important;
        height: 36px !important;
        padding: 6px !important;
        cursor: pointer !important;
        box-shadow: 4px 4px 0px #FF007A !important;
    }
    button[data-testid="stSidebarCollapsedControl"] svg {
        fill: #000000 !important;
        stroke: #000000 !important;
        width: 18px !important;
        height: 18px !important;
    }
    button[data-testid="stSidebarCollapsedControl"]:hover {
        background: #FF007A !important;
    }
    button[data-testid="stBaseButton-headerNoPadding"] {
        background: #CCFF00 !important;
        border: 2px solid #000000 !important;
        border-radius: 4px !important;
    }
    button[data-testid="stBaseButton-headerNoPadding"] svg {
        fill: #000000 !important;
        stroke: #000000 !important;
    }
    button[data-testid="stBaseButton-headerNoPadding"]:hover {
        background: #FF007A !important;
    }

    /* ===== HOVER EFFECTS ===== */
    .neo-card {
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        cursor: default;
    }
    .neo-card:hover {
        transform: translate(-3px, -3px);
        box-shadow: 12px 12px 0px #FF007A !important;
    }
    .metric-card {
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .metric-card:hover {
        transform: translate(-2px, -2px);
        box-shadow: 10px 10px 0px #FF007A !important;
    }
    .kpi-box {
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .kpi-box:hover {
        transform: translate(-3px, -3px);
        box-shadow: 10px 10px 0px black !important;
    }
    .eod-card {
        transition: box-shadow 0.2s ease;
    }
    .eod-card:hover {
        box-shadow: 16px 16px 0px #FF007A !important;
    }
    /* Expander hover */
    [data-testid="stExpander"]:hover {
        border-color: #FF007A !important;
        box-shadow: 4px 4px 0px #FF007A;
    }
    /* Tab hover */
    [data-testid="stTab"]:hover {
        background: #CCFF00 !important;
        color: black !important;
    }

    /* ===== MOBILE OPTIMISATIONS ===== */
    @media (max-width: 768px) {
        /* Tighter main container padding — more usable space */
        [data-testid="stMainBlockContainer"] {
            padding-left: 8px !important;
            padding-right: 8px !important;
            padding-bottom: 20px !important;
        }
        .block-container {
            padding-left: 8px !important;
            padding-right: 8px !important;
            max-width: 100% !important;
        }

        /* Header: stack on very narrow screens */
        .header-container {
            padding: 8px 10px 8px 52px !important;
            gap: 6px !important;
        }
        .header-text {
            font-size: clamp(0.9rem, 5vw, 1.3rem) !important;
        }
        .live-clock {
            font-size: 0.58rem !important;
            padding: 3px 6px !important;
        }

        /* Buttons: bigger tap targets on mobile */
        .stButton > button {
            height: 4rem !important;
            font-size: clamp(0.85rem, 3.5vw, 1rem) !important;
            min-height: 48px !important;
        }

        /* Metric grid: 2 columns max on mobile */
        .metric-grid {
            grid-template-columns: repeat(2, 1fr) !important;
        }
        .kpi-container {
            grid-template-columns: repeat(2, 1fr) !important;
        }

        /* EOD grid: stack to single column */
        .eod-row {
            grid-template-columns: 1fr !important;
        }

        /* Tabs: allow horizontal scroll if many tabs */
        [data-testid="stTabs"] > div:first-child {
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch;
            flex-wrap: nowrap !important;
        }
        [data-testid="stTab"] {
            white-space: nowrap !important;
            min-width: fit-content !important;
            font-size: 0.75rem !important;
            padding: 6px 10px !important;
        }

        /* Inputs: tall enough to tap comfortably */
        .stTextInput input,
        .stNumberInput input,
        .stSelectbox select,
        [data-testid="stSelectbox"] > div {
            min-height: 48px !important;
            font-size: 1rem !important;
        }

        /* Reduce neo-card shadow on mobile for cleaner look */
        .neo-card {
            box-shadow: 4px 4px 0px #000000 !important;
            padding: 10px !important;
        }

        /* Sale overlay close button — bigger touch target */
        .x-close-btn {
            width: 72px !important;
            height: 72px !important;
            font-size: 2rem !important;
            top: 16px !important;
            right: 16px !important;
        }

        /* Sidebar toggle: always accessible */
        button[data-testid="stSidebarCollapsedControl"],
        #calif-sidebar-toggle {
            top: 8px !important;
            left: 8px !important;
            width: 40px !important;
            height: 40px !important;
        }

        /* Dataframe scrollable horizontally */
        .stDataFrame {
            overflow-x: auto !important;
        }
    }

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
if 'out_of_stock' not in st.session_state: st.session_state.out_of_stock = False
if 'pending_sale' not in st.session_state: st.session_state.pending_sale = None

# --- UTILITY FUNCTIONS ---
def run_query(q, params=None):
    conn = get_connection()
    try:
        c = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        c.execute(q, params or ())
        rows = c.fetchall()
        conn.commit()
        if rows:
            return pd.DataFrame([dict(r) for r in rows])
        return pd.DataFrame()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        release_connection(conn)

@st.cache_data(ttl=4)
def run_query_cached(q, params=None):
    """For read-only queries where 4s stale data is fine — avoids repeated DB round trips."""
    return run_query(q, params)

def execute_db(q, params=()):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute(q, params)
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        release_connection(conn)

def log_activity(action_type, description):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("INSERT INTO activity_log (action_type, description, timestamp) VALUES (%s,%s,%s)",
                  (action_type, description, now_eat()))
        conn.commit()
    except Exception as e:
        conn.rollback()
    finally:
        release_connection(conn)

EAT = pytz.timezone('Africa/Nairobi')

def now_eat():
    return datetime.now(EAT).replace(tzinfo=None)

def record_sale(p_id, p_name, cat, qty, s_price, b_price, method, unit):
    conn = get_connection()
    try:
        c = conn.cursor()
        c.execute("SELECT stock FROM products WHERE id = %s", (p_id,))
        row = c.fetchone()
        if row is None or row[0] < qty:
            conn.rollback()
            st.session_state.sale_msg = "OUT OF STOCK"
            st.session_state.out_of_stock = True
            return
        profit = s_price - b_price
        c.execute("""INSERT INTO sales (product_name, category, quantity, unit_sold, sell_price, buying_price, profit, payment_method, timestamp) 
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                  (p_name, cat, qty, unit, s_price, b_price, profit, method, now_eat()))
        c.execute("UPDATE products SET stock = stock - %s WHERE id = %s", (qty, p_id))
        conn.commit()
        st.session_state.sale_msg = f"{p_name} ({unit}) SOLD FOR KES {s_price:,.0f}/-"
        st.session_state.sale_complete = True
    except Exception as e:
        conn.rollback()
        st.session_state.sale_msg = f"ERROR: {e}"
        st.session_state.out_of_stock = True
    finally:
        release_connection(conn)

# --- FIXED RESPONSIVE HEADER ---
now = now_eat()
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

# ── SIDEBAR TOGGLE — adapted from mie.py (confirmed working) ──────────────────
# Strategy:
#   1. Look for stSidebarCollapsedControl (exists when sidebar is COLLAPSED) → style it, remove custom btn
#   2. Look for stBaseButton-headerNoPadding (exists when sidebar is EXPANDED) → inject custom btn that clicks it
#   3. Poll every 800ms so state changes are caught immediately
components.html("""<script>
(function() {
  function ensureSidebarToggle() {
    var doc = window.parent.document;

    // ── Sidebar is COLLAPSED: native expand button is in the main page ──
    var native = doc.querySelector('button[data-testid="stSidebarCollapsedControl"]');
    if (native) {
      native.style.cssText = [
        'display:flex!important','visibility:visible!important','opacity:1!important',
        'position:fixed!important','top:10px!important','left:10px!important',
        'z-index:10100!important','width:36px!important','height:36px!important',
        'border-radius:4px!important','cursor:pointer!important','padding:6px!important',
        'align-items:center!important','justify-content:center!important',
        'background:#CCFF00!important',
        'border:3px solid #000000!important',
        'box-shadow:4px 4px 0px #FF007A!important'
      ].join(';');
      native.querySelectorAll('svg').forEach(function(s) {
        s.style.fill = '#000000';
        s.style.stroke = '#000000';
        s.style.width = '18px';
        s.style.height = '18px';
      });
      // Remove any custom injected button — native one is now visible and working
      var old = doc.getElementById('calif-sidebar-toggle');
      if (old) old.remove();
      return;
    }

    // ── Sidebar is EXPANDED: inject a custom button that triggers native collapse ──
    if (!doc.getElementById('calif-sidebar-toggle')) {
      var btn = doc.createElement('button');
      btn.id = 'calif-sidebar-toggle';
      btn.title = 'Hide sidebar';
      btn.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18"><path fill="#000" d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/></svg>';
      btn.style.cssText = [
        'position:fixed','top:10px','left:10px','z-index:10100',
        'width:36px','height:36px','border-radius:4px',
        'border:3px solid #000000',
        'background:#CCFF00',
        'cursor:pointer','display:flex','align-items:center','justify-content:center',
        'padding:6px','box-shadow:4px 4px 0px #FF007A'
      ].join(';');
      btn.onmouseover = function() {
        this.style.background = '#FF007A';
        this.querySelector('svg path').setAttribute('fill', '#CCFF00');
      };
      btn.onmouseout = function() {
        this.style.background = '#CCFF00';
        this.querySelector('svg path').setAttribute('fill', '#000');
      };
      btn.onclick = function() {
        // Click Streamlit's native collapse button inside the sidebar header
        var inner = doc.querySelector('button[data-testid="stBaseButton-headerNoPadding"]');
        if (!inner) inner = doc.querySelector('[data-testid="stSidebar"] button');
        if (inner) { inner.click(); return; }
        // Last resort — hide sidebar directly
        var sidebar = doc.querySelector('section[data-testid="stSidebar"]');
        if (sidebar) sidebar.style.display = 'none';
      };
      doc.body.appendChild(btn);
    }

    // Keep polling — sidebar state will change and we need to react
    setTimeout(ensureSidebarToggle, 800);
  }

  // Start after short delay to let Streamlit render
  setTimeout(ensureSidebarToggle, 300);
})();
</script>""", height=0, scrolling=False)

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

# --- OUT OF STOCK POPUP ---
if st.session_state.out_of_stock:
    st.markdown('<div id="close-oos-wrapper" style="position:fixed;top:-999px;left:-999px;width:1px;height:1px;overflow:hidden;opacity:0;pointer-events:none;">', unsafe_allow_html=True)
    oos_clicked = st.button("__CLOSE_OOS_INTERNAL__", key="close_oos_hidden")
    st.markdown('</div>', unsafe_allow_html=True)
    if oos_clicked:
        st.session_state.out_of_stock = False
        st.rerun()
    components.html("""
    <!DOCTYPE html>
    <html>
    <head>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Archivo+Black&display=swap');
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            background: #FF007A;
            font-family: 'Archivo Black', sans-serif;
            display: flex; flex-direction: column;
            justify-content: center; align-items: center;
            width: 100vw; height: 100vh;
            border: 20px solid black;
            text-align: center; padding: 20px;
            overflow: hidden;
        }
        .x-btn {
            position: fixed; top: 20px; right: 20px;
            width: 64px; height: 64px;
            background: #000; color: #FF007A;
            border: 5px solid #000;
            font-size: 2rem; font-family: 'Archivo Black', sans-serif;
            font-weight: 900; cursor: pointer;
            display: flex; align-items: center; justify-content: center;
        }
        .oos-txt { font-size: clamp(3rem, 15vw, 9rem); color: black; line-height: 0.9; }
        .oos-sub { font-size: clamp(1rem, 4vw, 2rem); color: white; background: black; padding: 12px 24px; margin-top: 24px; }
        .close-btn {
            margin-top: 40px; background: #000; color: #fff;
            border: 6px solid #000;
            font-size: clamp(1rem, 4vw, 1.6rem);
            font-family: 'Archivo Black', sans-serif;
            font-weight: 900; text-transform: uppercase;
            padding: 20px 36px; cursor: pointer;
            box-shadow: 8px 8px 0px white;
        }
    </style>
    </head>
    <body>
        <button class="x-btn" onclick="doClose()">✕</button>
        <div class="oos-txt">OUT OF<br>STOCK!</div>
        <div class="oos-sub">⛔ PLEASE RESTOCK BEFORE SELLING</div>
        <button class="close-btn" onclick="doClose()">✖ CLOSE &amp; GO BACK ➔</button>
        <script>
        function doClose() {
            var btns = window.parent.document.querySelectorAll('button');
            for (var i = 0; i < btns.length; i++) {
                if (btns[i].innerText === '__CLOSE_OOS_INTERNAL__') { btns[i].click(); return; }
            }
            window.parent.location.reload();
        }
        </script>
    </body>
    </html>
    """, height=700, scrolling=False)
    st.stop()

# --- FULL SCREEN SALE POPUP ---
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
    st.markdown("---")
    if st.session_state.vault_unlocked:
        st.markdown("<p style='color:red; font-size:0.75rem;'>⚠️ DANGER ZONE</p>", unsafe_allow_html=True)
        if st.button("🗑️ CLEAR ALL DATA"):
            st.session_state['confirm_clear'] = True
        if st.session_state.get('confirm_clear'):
            st.warning("THIS WILL DELETE ALL DATA. Enter password to confirm:")
            clear_pin = st.text_input("PASSWORD", type="password", key="clear_db_pin")
            c1, c2 = st.columns(2)
            if c1.button("✅ CONFIRM DELETE"):
                if clear_pin == "nesh001":
                    conn = get_connection()
                    try:
                        c = conn.cursor()
                        c.execute("DELETE FROM sales")
                        c.execute("DELETE FROM expenses")
                        c.execute("DELETE FROM products")
                        conn.commit()
                    except Exception:
                        conn.rollback()
                    finally:
                        release_connection(conn)
                    st.session_state['confirm_clear'] = False
                    st.success("Database cleared!")
                    st.rerun()
                else:
                    st.error("❌ WRONG PASSWORD")
            if c2.button("❌ CANCEL"):
                st.session_state['confirm_clear'] = False
                st.rerun()

# ============================================================
# --- 🛒 1. POS TERMINAL ---
# ============================================================
if page == "🛒 POS TERMINAL":
    # --- SALE LOCK: block all selling while popup is pending ---
    if st.session_state.sale_complete or st.session_state.out_of_stock:
        st.stop()
    df_p = run_query_cached("SELECT * FROM products")
    # Load keg settings ONCE here — not inside the product loop
    keg_settings_df = run_query_cached("SELECT * FROM keg_settings ORDER BY ml ASC")
    if df_p.empty:
        st.error("INVENTORY IS EMPTY. GO TO ADMIN VAULT TO ADD STOCK.")
    else:
        # Distinct icons per category tab
        cats  = ["KEG",   "Beers", "Spirits", "Wines", "Sodas", "Energy Drinks", "Condoms", "Shots"]
        icons = ["🍺",    "🍾",   "🥃",     "🍷",   "🥤",   "⚡",            "🛡️",     "🥂"]
        tabs = st.tabs([f"{icons[i]} {cats[i]}" for i in range(len(cats))])

        for i, tab in enumerate(tabs):
            with tab:
                category = cats[i]
                items = df_p[df_p['category'] == category]

                if category == "Spirits":
                    spirit_types = ["Mzinga", "Quarter", "Nusu"]
                    s_tabs = st.tabs(["🥃 MZINGA", "🥃 QUARTER", "🥃 NUSU"])
                    for st_idx, s_tab in enumerate(s_tabs):
                        with s_tab:
                            s_type = spirit_types[st_idx]
                            s_items = items[items['product_type'] == s_type]
                            if s_items.empty:
                                st.info(f"No {s_type} spirits yet.")
                                continue
                            s_cols = st.columns(2)
                            for s_i, s_row in s_items.reset_index(drop=True).iterrows():
                                with s_cols[s_i % 2]:
                                    stk_color = "red" if s_row['stock'] <= 1 else "black"
                                    st.markdown(f"""
                                        <div class="neo-card">
                                            <h2 style="margin:0; font-size:clamp(0.9rem,3vw,1.3rem);">{s_row['name']}</h2>
                                            <small style="color:grey;">TYPE: {s_row['product_type']}</small><br>
                                            <h4 style="background:{stk_color}; color:white; display:inline-block; padding:2px 8px; margin-top:5px; font-size:0.8rem;">
                                                STK: {s_row['stock']:.2f}
                                            </h4>
                                            <h3 style="color:#FF007A; margin:4px 0;">KES {s_row['selling_price']:,.0f}</h3>
                                        </div>
                                    """, unsafe_allow_html=True)
                                    with st.popover(f"💵 SELL {s_row['name']}", use_container_width=True):
                                        s_method = st.radio("PAYMENT", ["CASH", "M-PESA"], key=f"pay_{s_row['id']}")
                                        if s_type in ["Mzinga", "Nusu"]:
                                            # Only full bottle allowed for Mzinga and Nusu
                                            if st.button(f"FULL {s_type.upper()}", key=f"f_{s_row['id']}"):
                                                record_sale(s_row['id'], s_row['name'], category, 1, s_row['selling_price'], s_row['buying_price'], s_method, f"Full {s_type}")
                                                st.rerun()
                                        else:
                                            # Quarter: full and half allowed
                                            b1, b2 = st.columns(2)
                                            if b1.button(f"FULL {s_type.upper()}", key=f"f_{s_row['id']}"):
                                                record_sale(s_row['id'], s_row['name'], category, 1, s_row['selling_price'], s_row['buying_price'], s_method, f"Full {s_type}")
                                                st.rerun()
                                            if b2.button(f"HALF {s_type.upper()}", key=f"h_{s_row['id']}"):
                                                record_sale(s_row['id'], s_row['name'], category, 0.5, s_row['selling_price']*0.5, s_row['buying_price']*0.5, s_method, f"Half {s_type}")
                                                st.rerun()
                    continue

                if items.empty:
                    st.info(f"Nothing in {category} yet.")
                    continue

                cols = st.columns(2)
                for idx, row in items.reset_index(drop=True).iterrows():
                    with cols[idx % 2]:
                        stk_color = "red" if row['stock'] <= 1 else "black"
                        if category == "Shots":
                            stk_label = f"SHOTS LEFT: {row['stock']:.0f}"
                            price_label = f"KES {row['selling_price']:,.0f} / Shot"
                        else:
                            stk_label = f"STK: {row['stock']:.2f}"
                            price_label = f"KES {row['selling_price']:,.0f}"
                        st.markdown(f"""
                            <div class="neo-card">
                                <h2 style="margin:0; font-size:clamp(0.9rem,3vw,1.3rem);">{row['name']}</h2>
                                <small style="color:grey;">TYPE: {row['product_type']}</small><br>
                                <h4 style="background:{stk_color}; color:white; display:inline-block; padding:2px 8px; margin-top:5px; font-size:0.8rem;">
                                    {stk_label}
                                </h4>
                                <h3 style="color:#FF007A; margin:4px 0;">{price_label}</h3>
                            </div>
                        """, unsafe_allow_html=True)

                        with st.popover(f"💵 SELL {row['name']}", use_container_width=True):
                            method = st.radio("PAYMENT", ["CASH", "M-PESA"], key=f"pay_{row['id']}")

                            if category == "KEG":
                                cost_l = 156.0
                                if not keg_settings_df.empty:
                                    for _, ks_row in keg_settings_df.iterrows():
                                        ml_val   = float(ks_row['ml'])
                                        price_val = float(ks_row['price'])
                                        litres   = ml_val / 1000.0
                                        label_str = ks_row['size_name'].upper()
                                        btn_label = f"{label_str} ({int(ml_val)}ML @ {int(price_val)}/-)"
                                        if st.button(btn_label, key=f"keg_{ks_row['size_name']}_{row['id']}"):
                                            if row['stock'] < litres:
                                                st.error("⛔ OUT OF STOCK")
                                            else:
                                                record_sale(row['id'], row['name'], "KEG", litres, price_val,
                                                            litres * cost_l, method, f"{int(ml_val)}ML {label_str}")
                                                st.rerun()

                            elif category == "Spirits" and row['product_type'] == "Nusu":
                                if st.button("FULL NUSU", key=f"fn_{row['id']}"):
                                    record_sale(row['id'], row['name'], category, 1, row['selling_price'], row['buying_price'], method, "Full Nusu")
                                    st.rerun()

                            elif category == "Spirits" and row['product_type'] == "Quarter":
                                s1, s2 = st.columns(2)
                                if s1.button("FULL QTR", key=f"fq_{row['id']}"):
                                    record_sale(row['id'], row['name'], category, 1, row['selling_price'], row['buying_price'], method, "Full Quarter")
                                    st.rerun()
                                if s2.button("HALF QTR", key=f"hq_{row['id']}"):
                                    record_sale(row['id'], row['name'], category, 0.5, row['selling_price']*0.5, row['buying_price']*0.5, method, "Half Quarter")
                                    st.rerun()

                            else:
                                unit_label = "Full Bottle" if category in ["Beers", "Wines", "Spirits"] else ("Shot" if category == "Shots" else "Unit")
                                if category == "Shots":
                                    if st.button(f"SELL 1 SHOT — KES {row['selling_price']:,.0f}", key=f"std_{row['id']}"):
                                        cost_per_shot = row['buying_price'] / row['shots_per_bottle'] if row['shots_per_bottle'] > 0 else 0
                                        record_sale(row['id'], row['name'], category, 1, row['selling_price'], cost_per_shot, method, "Shot")
                                        st.rerun()
                                else:
                                    if st.button(f"CONFIRM {unit_label}", key=f"std_{row['id']}"):
                                        record_sale(row['id'], row['name'], category, 1, row['selling_price'], row['buying_price'], method, unit_label)
                                        st.rerun()

# ============================================================
# --- 📈 2. ANALYTICS & PROFIT ---
# ============================================================
elif page == "📈 ANALYTICS & PROFIT":
    st.markdown("<h1 style='font-size:clamp(1.5rem,6vw,3rem);'>FINANCIAL INTEL</h1>", unsafe_allow_html=True)
    df_s = run_query_cached("SELECT * FROM sales")

    if df_s.empty:
        st.warning("NO SALES LOGGED YET.")
    else:
        df_s['timestamp'] = pd.to_datetime(df_s['timestamp'])
        # Fetch keg stock ONCE before the tab loop
        keg_stk_analytics = run_query_cached("SELECT stock FROM products WHERE category = 'KEG' LIMIT 1")
        t_d, t_w, t_m = st.tabs(["⚡ DAILY", "📅 WEEKLY", "📊 MONTHLY"])
        analytics_configs = [(t_d, 0, "Daily"), (t_w, 7, "Weekly"), (t_m, 30, "Monthly")]

        for tab, days, label in analytics_configs:
            with tab:
                today_eat = now_eat().date()
                if days == 0:
                    # Daily: today only
                    v_s = df_s[df_s['timestamp'].dt.date == today_eat]
                else:
                    start_date = (now_eat() - timedelta(days=days)).date()
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

                if v_s.empty:
                    st.info(f"No sales data for this {label.lower()} period.")
                else:
                    c1, c2 = st.columns(2)
                    with c1:
                        if days == 0:
                            # Daily: group by hour
                            chart_df = v_s.copy()
                            chart_df['hour'] = chart_df['timestamp'].dt.strftime('%H:00')
                            chart_df = chart_df.groupby('hour')[['sell_price', 'profit']].sum().reset_index()
                            fig = px.bar(chart_df, x='hour', y=['sell_price', 'profit'], barmode='group',
                                         title="Today — Sales by Hour", color_discrete_sequence=['#2563EB', '#FF007A'])
                        else:
                            chart_df = v_s.groupby(v_s['timestamp'].dt.date)[['sell_price', 'profit']].sum().reset_index()
                            fig = px.bar(chart_df, x='timestamp', y=['sell_price', 'profit'], barmode='group',
                                         title=f"{label} Sales vs Profit", color_discrete_sequence=['#2563EB', '#FF007A'])
                        st.plotly_chart(fig, use_container_width=True, key=f"sales_chart_{label}")
                    with c2:
                        top_sellers = v_s.groupby('product_name')['sell_price'].sum().sort_values(ascending=False).head(5).reset_index()
                        fig_top = px.bar(top_sellers, x='sell_price', y='product_name', orientation='h',
                                         title=f"Top 5 Brands ({label})", color_discrete_sequence=['#CCFF00'])
                        st.plotly_chart(fig_top, use_container_width=True, key=f"top_chart_{label}")

                    # KEG LIVE LEVEL — shown in every tab, uses pre-fetched data
                    if not keg_stk_analytics.empty:
                        rem = float(keg_stk_analytics.iloc[0]['stock'])
                        cur_mtungi = rem % 50 if rem % 50 != 0 else (50 if rem > 0 else 0)
                        fig_gauge = go.Figure(go.Indicator(
                            mode="gauge+number", value=cur_mtungi,
                            title={'text': f"🍺 KEG LITRES LEFT (Total: {rem:.1f}L)"},
                            gauge={'axis': {'range': [0, 50]}, 'bar': {'color': "#CCFF00"}, 'bgcolor': "black"}
                        ))
                        st.plotly_chart(fig_gauge, use_container_width=True, key=f"keg_gauge_{label}")

                # Transaction log — daily only shows today's + reversal
                if label == "Daily":
                    st.markdown("### 📋 TODAY'S TRANSACTION LOG")
                    if v_s.empty:
                        st.info("No transactions today yet.")
                    else:
                        st.dataframe(
                            v_s[['timestamp', 'product_name', 'category', 'unit_sold', 'quantity', 'sell_price', 'buying_price', 'profit', 'payment_method']].sort_values('timestamp', ascending=False),
                            use_container_width=True
                        )
                        st.markdown("#### ↩️ REVERSE RECENT TRANSACTION")
                        st.caption("Transactions can be reversed within 3 minutes of being made. Stock will be restored. Password required.")
                        now_ts = now_eat()
                        editable = v_s[pd.to_datetime(v_s['timestamp']) >= pd.Timestamp(now_ts - timedelta(minutes=3))]
                        if editable.empty:
                            st.info("No transactions within the last 3 minutes to reverse.")
                        else:
                            edit_options = {f"#{r['id']} — {r['product_name']} ({r['unit_sold']}) KES {r['sell_price']:,.0f} @ {pd.to_datetime(r['timestamp']).strftime('%H:%M:%S')}": r['id']
                                           for _, r in editable.iterrows()}
                            chosen_label = st.selectbox("Select transaction to reverse", list(edit_options.keys()), key="edit_tx_select")
                            chosen_id = edit_options[chosen_label]
                            chosen_row = v_s[v_s['id'] == chosen_id].iloc[0]
                            st.markdown(f"""
                            <div style="background:#FF007A; border:3px solid black; padding:10px 14px; margin:8px 0; box-shadow:4px 4px 0px black;">
                                <span style="color:white; font-size:0.75rem; letter-spacing:2px; text-transform:uppercase;">⚠️ THIS WILL BE REVERSED</span><br>
                                <span style="color:white; font-size:0.9rem;"><b>{chosen_row['product_name']}</b> ({chosen_row['unit_sold']}) — KES {chosen_row['sell_price']:,.0f} via {chosen_row['payment_method']}</span><br>
                                <span style="color:black; font-size:0.75rem;">Stock of <b>{chosen_row['quantity']}</b> unit(s) will be returned to inventory.</span>
                            </div>
                            """, unsafe_allow_html=True)
                            rev_pin = st.text_input("Password to confirm reversal", type="password", key="reverse_tx_pin")
                            if st.button("↩️ CONFIRM REVERSAL", key="confirm_reverse_tx"):
                                if rev_pin == "nesh001":
                                    conn = get_connection()
                                    try:
                                        c = conn.cursor()
                                        qty_to_restore = float(chosen_row['quantity'])
                                        product_name   = str(chosen_row['product_name'])
                                        sale_id        = int(chosen_id)
                                        c.execute("UPDATE products SET stock = stock + %s WHERE name = %s",
                                                  (qty_to_restore, product_name))
                                        c.execute("DELETE FROM sales WHERE id = %s", (sale_id,))
                                        conn.commit()
                                        log_activity("SALE REVERSED", f"Sale #{sale_id} | {product_name} ({chosen_row['unit_sold']}) | KES {chosen_row['sell_price']:,.0f} | Qty {qty_to_restore} returned to stock")
                                        st.success(f"✅ REVERSED — {product_name} stock restored by {qty_to_restore} units.")
                                        st.rerun()
                                    except Exception as e:
                                        conn.rollback()
                                        st.error(f"❌ REVERSAL FAILED: {e}")
                                    finally:
                                        release_connection(conn)
                                else:
                                    st.error("❌ WRONG PASSWORD")
                elif label == "Weekly":
                    st.markdown("### 📋 THIS WEEK'S TRANSACTIONS")
                    if not v_s.empty:
                        st.dataframe(
                            v_s[['timestamp', 'product_name', 'category', 'unit_sold', 'quantity', 'sell_price', 'profit', 'payment_method']].sort_values('timestamp', ascending=False),
                            use_container_width=True
                        )
                else:
                    st.markdown("### 📋 THIS MONTH'S TRANSACTIONS")
                    if not v_s.empty:
                        st.dataframe(
                            v_s[['timestamp', 'product_name', 'category', 'unit_sold', 'quantity', 'sell_price', 'profit', 'payment_method']].sort_values('timestamp', ascending=False),
                            use_container_width=True
                        )

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
                execute_db("INSERT INTO expenses (category, amount, description, timestamp) VALUES (%s,%s,%s,%s)",
                           (cat, amt, note, now_eat()))
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
                    execute_db("UPDATE expenses SET category=%s, amount=%s, description=%s WHERE id=%s",
                               (new_cat, new_amt, new_desc, row['id']))
                    st.success("UPDATED ✅"); st.rerun()
                if col_b.button("🗑️ DELETE", key=f"edel_{row['id']}"):
                    execute_db("DELETE FROM expenses WHERE id=%s", (row['id'],))
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

        t1, t2, t3, t4 = st.tabs(["📦 STOCK ENTRY", "🛠️ INVENTORY MGMT", "🌃 CLOSE DAY (EOD)", "📋 ACTIVITY LOG"])

        # ---- TAB 1: STOCK ENTRY ----
        with t1:
            st.markdown("### ADD NEW STOCK")
            cat_n = st.selectbox("CHOOSE CATEGORY", ["KEG", "Beers", "Spirits", "Wines", "Sodas", "Energy Drinks", "Condoms", "Shots"])

            with st.form("new_product_form"):
                if cat_n == "KEG":
                    qty_n = st.number_input("How many Mitungi?", min_value=1.0, step=1.0)
                    p_name, p_type, p_buy, p_sell = "KEG MTUNGI", "Standard", 7800.0, 0.0
                elif cat_n == "Spirits":
                    brand = st.text_input("Product Brand Name (e.g. Chrome, KC)")
                    p_type = st.radio("Size Type", ["Mzinga", "Quarter", "Nusu"])
                    p_name = f"{brand} {p_type}"
                    p_buy  = st.number_input("Buying Price (Full Bottle)")
                    p_sell = st.number_input("Selling Price (Full Bottle)")
                    qty_n  = st.number_input("Quantity of Bottles", min_value=1.0)
                elif cat_n == "Shots":
                    p_name = st.text_input("Product Name (e.g. Whiskey Shots)")
                    p_type = "Shots"
                    p_buy  = st.number_input("Buying Price per Bottle")
                    shots_per_bottle = st.number_input("Shots per Bottle", min_value=1.0, step=1.0, value=20.0)
                    p_sell = st.number_input("Selling Price per Shot (KES)")
                    qty_n  = st.number_input("Number of Bottles", min_value=1.0, step=1.0)
                else:
                    p_name = st.text_input("Product Name")
                    p_type = "Standard"
                    p_buy  = st.number_input("Buying Price")
                    p_sell = st.number_input("Selling Price")
                    qty_n  = st.number_input("Quantity", min_value=1.0)

                if st.form_submit_button("COMMIT TO INVENTORY"):
                    if cat_n == "KEG":
                        final_q = qty_n * 50
                        spb = 0
                    elif cat_n == "Shots":
                        final_q = qty_n * shots_per_bottle
                        spb = shots_per_bottle
                    else:
                        final_q = qty_n
                        spb = 0
                    conn = get_connection()
                    try:
                        c = conn.cursor()
                        try:
                            c.execute("INSERT INTO products (name, category, product_type, buying_price, selling_price, stock, shots_per_bottle) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                                      (p_name, cat_n, p_type, p_buy, p_sell, final_q, spb))
                        except Exception:
                            conn.rollback()
                            c.execute("UPDATE products SET stock = stock + %s WHERE name = %s", (final_q, p_name))
                        conn.commit()
                    except Exception:
                        conn.rollback()
                    finally:
                        release_connection(conn)
                    log_activity("STOCK ADDED", f"{p_name} | Qty: {final_q} | Buy: {p_buy} | Sell: {p_sell}")
                    st.success(f"✅ UPDATED: {p_name}"); st.rerun()

            st.markdown("### CURRENT INVENTORY STATUS")
            st.dataframe(run_query("SELECT name, category, product_type, stock, buying_price, selling_price FROM products"),
                         use_container_width=True)

            st.markdown("---")
            st.markdown("### 🍺 KEG SIZE & PRICE SETTINGS")
            st.caption("Adjust the ML and price for each keg serving size.")
            ks_df = run_query("SELECT * FROM keg_settings ORDER BY ml ASC")
            if not ks_df.empty:
                for _, ks_row in ks_df.iterrows():
                    with st.expander(f"⚙️ {ks_row['size_name'].upper()} — {int(ks_row['ml'])}ml @ KES {int(ks_row['price'])}"):
                        ka, kb = st.columns(2)
                        new_ml    = ka.number_input("ML", value=float(ks_row['ml']),    min_value=10.0, step=10.0, key=f"kml_{ks_row['id']}")
                        new_kprice = kb.number_input("Price (KES)", value=float(ks_row['price']), min_value=1.0, key=f"kpr_{ks_row['id']}")
                        if st.button("UPDATE KEG SIZE", key=f"ksave_{ks_row['id']}"):
                            execute_db("UPDATE keg_settings SET ml=%s, price=%s WHERE id=%s",
                                       (new_ml, new_kprice, int(ks_row['id'])))
                            log_activity("KEG SETTING CHANGED", f"{ks_row['size_name'].upper()}: {ks_row['ml']}ml@{ks_row['price']} → {new_ml}ml@{new_kprice}")
                            st.success(f"✅ {ks_row['size_name'].upper()} updated")
                            st.rerun()

        # ---- TAB 2: INVENTORY MANAGEMENT ----
        with t2:
            inv_tab1, inv_tab2, inv_tab3 = st.tabs(["✏️ EDIT PRODUCTS", "📊 TODAY vs YESTERDAY", "📅 DAILY CLOSING SNAPSHOT"])

            with inv_tab1:
                st.markdown("### INVENTORY BY CATEGORY")
                df_m = run_query("SELECT * FROM products ORDER BY category, name")
                if df_m.empty:
                    st.info("No products in inventory.")
                else:
                    cats_inv = df_m['category'].unique().tolist()
                    for cat_inv in cats_inv:
                        st.markdown(f"<div style='background:black;color:#CCFF00;padding:6px 12px;font-size:0.8rem;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px;'>📦 {cat_inv}</div>", unsafe_allow_html=True)
                        cat_items = df_m[df_m['category'] == cat_inv]
                        for _, row in cat_items.iterrows():
                            stk_warn = " 🔴" if float(row['stock']) < 2 else ""
                            with st.expander(f"✏️ {row['name']} | STK: {row['stock']:.2f}{stk_warn} | SELL: {row['selling_price']:,.0f}"):
                                new_name = st.text_input("Product Name", value=str(row['name']), key=f"nm_{row['id']}")
                                c_a, c_b = st.columns(2)
                                new_s   = c_a.number_input("Stock Count",    value=float(row['stock']),         key=f"s_{row['id']}")
                                new_p   = c_b.number_input("Selling Price",  value=float(row['selling_price']), key=f"p_{row['id']}")
                                c_c, c_d = st.columns(2)
                                new_bp  = c_c.number_input("Buying Price",   value=float(row['buying_price']),  key=f"bp_{row['id']}")
                                if row['category'] == 'Shots':
                                    spb_val = float(row['shots_per_bottle']) if row['shots_per_bottle'] else 0.0
                                    new_spb = c_d.number_input("Shots per Bottle", value=spb_val, min_value=0.0, key=f"spb_{row['id']}")
                                if st.button("SAVE UPDATES", key=f"btn_{row['id']}"):
                                    changes = []
                                    if new_name != row['name']: changes.append(f"Name: {row['name']} → {new_name}")
                                    if new_s != row['stock']: changes.append(f"Stock: {row['stock']} → {new_s}")
                                    if new_p != row['selling_price']: changes.append(f"Sell: {row['selling_price']} → {new_p}")
                                    if new_bp != row['buying_price']: changes.append(f"Buy: {row['buying_price']} → {new_bp}")
                                    if row['category'] == 'Shots':
                                        execute_db("UPDATE products SET name=%s, stock=%s, selling_price=%s, buying_price=%s, shots_per_bottle=%s WHERE id=%s",
                                                   (new_name, new_s, new_p, new_bp, new_spb, int(row['id'])))
                                        if new_spb != spb_val: changes.append(f"Shots/Bottle: {spb_val} → {new_spb}")
                                    else:
                                        execute_db("UPDATE products SET name=%s, stock=%s, selling_price=%s, buying_price=%s WHERE id=%s",
                                                   (new_name, new_s, new_p, new_bp, int(row['id'])))
                                    log_activity("STOCK ADJUSTMENT", f"{row['name']} | {' | '.join(changes) if changes else 'No changes'}")
                                    st.success("✅ SAVED"); st.rerun()
                                st.markdown("---")
                                st.markdown("<span style='color:red; font-size:0.8rem;'>⚠️ DANGER: DELETE THIS PRODUCT</span>", unsafe_allow_html=True)
                                del_key = f"del_confirm_{row['id']}"
                                if del_key not in st.session_state:
                                    st.session_state[del_key] = False
                                if st.button("🗑️ DELETE PRODUCT", key=f"delbtn_{row['id']}"):
                                    st.session_state[del_key] = True
                                if st.session_state.get(del_key):
                                    del_pin = st.text_input("Enter password to confirm deletion:", type="password", key=f"delpin_{row['id']}")
                                    d1, d2 = st.columns(2)
                                    if d1.button("✅ CONFIRM DELETE", key=f"delconf_{row['id']}"):
                                        if del_pin == "nesh001":
                                            execute_db("DELETE FROM products WHERE id=%s", (int(row['id']),))
                                            log_activity("PRODUCT DELETED", f"{row['name']} | Category: {row['category']} | Type: {row['product_type']}")
                                            st.session_state[del_key] = False
                                            st.success(f"✅ {row['name']} DELETED")
                                            st.rerun()
                                        else:
                                            st.error("❌ WRONG PASSWORD")
                                    if d2.button("❌ CANCEL", key=f"delcancel_{row['id']}"):
                                        st.session_state[del_key] = False
                                        st.rerun()

            with inv_tab2:
                st.markdown("### 📊 TODAY vs YESTERDAY — STOCK MOVEMENT")
                df_all_sales = run_query("SELECT * FROM sales")
                df_prod      = run_query("SELECT * FROM products")
                if df_all_sales.empty or df_prod.empty:
                    st.info("Not enough data yet.")
                else:
                    df_all_sales['timestamp'] = pd.to_datetime(df_all_sales['timestamp'])
                    today_dt    = now_eat().date()
                    yesterday_dt = today_dt - timedelta(days=1)
                    today_sales = df_all_sales[df_all_sales['timestamp'].dt.date == today_dt]
                    yest_sales  = df_all_sales[df_all_sales['timestamp'].dt.date == yesterday_dt]
                    today_qty   = today_sales.groupby('product_name')['quantity'].sum().rename('today_sold')
                    yest_qty    = yest_sales.groupby('product_name')['quantity'].sum().rename('yesterday_sold')
                    compare_df  = df_prod[['name', 'category', 'stock']].set_index('name')
                    compare_df  = compare_df.join(today_qty, how='left').join(yest_qty, how='left').fillna(0).reset_index()
                    compare_df.columns = ['Product', 'Category', 'Current Stock', 'Today Sold', 'Yesterday Sold']
                    compare_df['Δ vs Yesterday'] = compare_df['Today Sold'] - compare_df['Yesterday Sold']
                    st.dataframe(compare_df.sort_values('Today Sold', ascending=False), use_container_width=True)
                    fig_comp = px.bar(compare_df[compare_df['Today Sold'] + compare_df['Yesterday Sold'] > 0],
                                      x='Product', y=['Today Sold', 'Yesterday Sold'],
                                      barmode='group', title="Today vs Yesterday Sales by Product",
                                      color_discrete_sequence=['#CCFF00', '#2563EB'])
                    st.plotly_chart(fig_comp, use_container_width=True, key="compare_chart")

            with inv_tab3:
                st.markdown("### 📅 DAILY CLOSING STOCK SNAPSHOT")
                st.caption("Select a date to see estimated closing stock — current stock plus all sales made on that day.")
                snap_date = st.date_input("Select Date", now_eat().date(), key="snap_date")
                df_snap_sales = run_query("SELECT product_name, SUM(quantity) as qty_sold FROM sales WHERE DATE(timestamp) = %s GROUP BY product_name", (snap_date,))
                df_snap_prod  = run_query("SELECT name, category, stock, selling_price FROM products")
                if df_snap_prod.empty:
                    st.info("No inventory data.")
                else:
                    if df_snap_sales.empty:
                        df_snap_prod['qty_sold_that_day'] = 0
                        df_snap_prod['closing_stock'] = df_snap_prod['stock']
                    else:
                        df_snap_prod = df_snap_prod.merge(df_snap_sales.rename(columns={'product_name': 'name'}), on='name', how='left').fillna(0)
                        df_snap_prod['qty_sold_that_day'] = df_snap_prod['qty_sold']
                        df_snap_prod['closing_stock'] = df_snap_prod['stock'] + df_snap_prod['qty_sold_that_day']
                    display_snap = df_snap_prod[['name', 'category', 'closing_stock', 'qty_sold_that_day', 'stock']].copy()
                    display_snap.columns = ['Product', 'Category', 'Est. Closing Stock', 'Sold That Day', 'Current Stock']
                    st.dataframe(display_snap.sort_values('Category'), use_container_width=True)

        # ---- TAB 3: END OF DAY (DETAILED) ----
        with t3:
            st.markdown("### 🌃 END OF DAY RECONCILIATION")

            eod_mode = st.radio("VIEW MODE", ["📅 BY CALENDAR DATE", "⏰ BY CUSTOM TIME RANGE"], horizontal=True)

            if eod_mode == "📅 BY CALENDAR DATE":
                date_check = st.date_input("Select Date", now_eat().date())
                df_day = run_query("SELECT * FROM sales WHERE DATE(timestamp) = %s", (date_check,))
                eod_label = str(date_check)
            else:
                st.caption("Set your opening and closing times for the business day.")
                col_d1, col_d2 = st.columns(2)
                biz_date  = col_d1.date_input("Opening Date", now_eat().date(), key="biz_open_date")
                close_date = col_d2.date_input("Closing Date", (now_eat() + timedelta(days=1)).date(), key="biz_close_date")
                col_t1, col_t2 = st.columns(2)
                open_time  = col_t1.time_input("Opening Time", value=datetime.strptime("08:00", "%H:%M").time(), key="biz_open_time")
                close_time = col_t2.time_input("Closing Time", value=datetime.strptime("03:00", "%H:%M").time(), key="biz_close_time")
                biz_start = datetime.combine(biz_date, open_time)
                biz_end   = datetime.combine(close_date, close_time)
                df_day = run_query(
                    "SELECT * FROM sales WHERE timestamp >= %s AND timestamp < %s",
                    (biz_start, biz_end)
                )
                eod_label = f"{biz_date} {open_time.strftime('%I:%M%p')} → {close_date} {close_time.strftime('%I:%M%p')}"

            if df_day.empty:
                st.warning("NO SALES DATA FOR THIS PERIOD.")
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
                    <h2 style="color:#CCFF00; margin:0 0 5px;">🌃 EOD REPORT: {eod_label}</h2>
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

                # Category breakdown charts for the day
                st.markdown("### 📊 INCOME BY CATEGORY")
                cat_breakdown = df_day.groupby('category')['sell_price'].sum().reset_index().sort_values('sell_price', ascending=False)
                fig_cat_bar = px.bar(cat_breakdown, x='category', y='sell_price',
                                     title=f"Revenue by Category — {eod_label}",
                                     color='category',
                                     color_discrete_sequence=['#2563EB', '#FF007A', '#CCFF00', '#000000', '#2ECC71', '#E0E0E0', '#FF6B6B'],
                                     text='sell_price')
                fig_cat_bar.update_traces(texttemplate='KES %{text:,.0f}', textposition='outside')
                fig_cat_bar.update_layout(showlegend=False, plot_bgcolor='black', paper_bgcolor='black',
                                          font_color='white', title_font_color='#CCFF00')
                st.plotly_chart(fig_cat_bar, use_container_width=True, key="eod_cat_bar")

                fig_cat = px.pie(cat_breakdown, values='sell_price', names='category',
                                 title=f"Revenue Share — {eod_label}",
                                 color_discrete_sequence=['#2563EB', '#FF007A', '#CCFF00', '#2ECC71', '#E0E0E0', '#FF6B6B'])
                st.plotly_chart(fig_cat, use_container_width=True, key="eod_pie")

                payment_breakdown = df_day.groupby('payment_method')['sell_price'].sum().reset_index()
                fig_pay = px.bar(payment_breakdown, x='payment_method', y='sell_price',
                                 title="Cash vs M-Pesa Today",
                                 color='payment_method',
                                 color_discrete_map={'CASH': '#CCFF00', 'M-PESA': '#2ECC71'})
                st.plotly_chart(fig_pay, use_container_width=True, key="eod_pay_bar")

                # Low stock warning
                st.markdown("### ⚠️ LOW STOCK ALERT (Remaining < 2)")
                df_low = run_query("SELECT name, category, stock FROM products WHERE stock < 2 ORDER BY stock ASC")
                if df_low.empty:
                    st.success("✅ All products have sufficient stock.")
                else:
                    for _, lrow in df_low.iterrows():
                        st.markdown(f"""
                        <div style="background:#FF007A; border:3px solid black; padding:8px 14px; margin-bottom:6px; box-shadow:3px 3px 0px black; display:flex; justify-content:space-between; align-items:center;">
                            <span style="color:white; font-weight:900; font-size:0.9rem;">🔴 {lrow['name']}</span>
                            <span style="color:black; background:#CCFF00; padding:2px 10px; font-size:0.8rem; font-weight:900;">{lrow['category']}</span>
                            <span style="color:white; font-size:0.9rem;">STK: <b>{lrow['stock']:.2f}</b></span>
                        </div>
                        """, unsafe_allow_html=True)
        # ---- TAB 4: ACTIVITY LOG ----
        with t4:
            st.markdown("### 📋 DAILY ACTIVITY LOG")
            st.caption("Stock additions, deletions, adjustments — all non-sale admin actions are recorded here.")

            if 'activity_log_unlocked' not in st.session_state:
                st.session_state.activity_log_unlocked = False

            if not st.session_state.activity_log_unlocked:
                st.markdown("<div class='neo-card'><h3>🔒 ACTIVITY LOG LOCKED</h3>", unsafe_allow_html=True)
                act_pin = st.text_input("ENTER PASSWORD TO VIEW ACTIVITY LOG", type="password", key="activity_pin_input")
                if st.button("UNLOCK ACTIVITY LOG", key="unlock_activity_btn"):
                    if act_pin == "nesh001":
                        st.session_state.activity_log_unlocked = True
                        st.rerun()
                    else:
                        st.error("❌ WRONG PASSWORD")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                if st.button("🔒 LOCK ACTIVITY LOG", key="lock_activity_btn"):
                    st.session_state.activity_log_unlocked = False
                    st.rerun()

                act_col1, act_col2 = st.columns([2, 1])
                with act_col1:
                    act_date = st.date_input("Filter by Date", now_eat().date(), key="act_date_filter")
                with act_col2:
                    act_type_filter = st.selectbox("Action Type", ["ALL", "STOCK ADDED", "STOCK ADJUSTMENT", "PRODUCT DELETED", "SALE REVERSED"], key="act_type_filter")

                if act_type_filter == "ALL":
                    df_act = run_query("SELECT * FROM activity_log WHERE DATE(timestamp) = %s ORDER BY timestamp DESC", (act_date,))
                else:
                    df_act = run_query("SELECT * FROM activity_log WHERE DATE(timestamp) = %s AND action_type = %s ORDER BY timestamp DESC", (act_date, act_type_filter))

                if df_act.empty:
                    st.info("NO ACTIVITY RECORDED FOR THIS DATE / FILTER.")
                else:
                    # Summary counts
                    added_count   = len(df_act[df_act['action_type'] == 'STOCK ADDED'])
                    adjust_count  = len(df_act[df_act['action_type'] == 'STOCK ADJUSTMENT'])
                    deleted_count = len(df_act[df_act['action_type'] == 'PRODUCT DELETED'])
                    st.markdown(f"""
                    <div class="metric-grid">
                        <div class="metric-card mc-keg">
                            <div class="m-label">📦 STOCK ADDED</div>
                            <div class="m-value">{added_count}</div>
                        </div>
                        <div class="metric-card mc-cash">
                            <div class="m-label">✏️ ADJUSTMENTS</div>
                            <div class="m-value">{adjust_count}</div>
                        </div>
                        <div class="metric-card mc-profit">
                            <div class="m-label">🗑️ DELETED</div>
                            <div class="m-value">{deleted_count}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    for _, arow in df_act.iterrows():
                        ts_str = pd.to_datetime(arow['timestamp']).strftime('%d %b %Y %H:%M:%S') if arow['timestamp'] else "—"
                        icon = "📦" if arow['action_type'] == "STOCK ADDED" else ("🗑️" if arow['action_type'] == "PRODUCT DELETED" else ("✏️" if arow['action_type'] == "STOCK ADJUSTMENT" else "🔄"))
                        color = "#CCFF00" if arow['action_type'] == "STOCK ADDED" else ("#FF007A" if arow['action_type'] == "PRODUCT DELETED" else ("#2563EB" if arow['action_type'] == "STOCK ADJUSTMENT" else "#FF6B00"))
                        st.markdown(f"""
                        <div style="background:black; border:3px solid {color}; padding:10px 14px; margin-bottom:8px; box-shadow:4px 4px 0px {color};">
                            <span style="color:{color}; font-size:0.7rem; letter-spacing:2px; text-transform:uppercase;">{icon} {arow['action_type']}</span>
                            <span style="color:#888; font-size:0.65rem; float:right;">{ts_str}</span>
                            <br>
                            <span style="color:white; font-size:0.85rem;">{arow['description']}</span>
                        </div>
                        """, unsafe_allow_html=True)

# ============================================================
# --- FOOTER ---
# ============================================================
st.markdown("""
<div style="background:#000000;border-top:6px solid #FF007A;margin-top:60px;font-family:'Space Mono',monospace;overflow:hidden;">
    <div style="background:#FF007A;padding:6px 0;overflow:hidden;white-space:nowrap;">
        <span style="display:inline-block;color:#000;font-size:0.65rem;font-weight:900;letter-spacing:3px;text-transform:uppercase;animation:ticker 18s linear infinite;">
            &nbsp;&nbsp;&nbsp;🍺 CALIFORNIA BOSS &nbsp;★&nbsp; KILGORIS FINEST CLUB &nbsp;★&nbsp; BUILT BY LEWIS &nbsp;★&nbsp; QUINN PRODUCTIONS 2026 &nbsp;★&nbsp; STAY WINNING &nbsp;★&nbsp; 🍺 CALIFORNIA BOSS &nbsp;★&nbsp; NAIROBI'S FINEST POS &nbsp;★&nbsp; BUILT BY LEWIS &nbsp;★&nbsp; QUINN PRODUCTIONS 2026 &nbsp;★&nbsp; STAY WINNING &nbsp;★&nbsp;
        </span>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0;border-top:2px solid #222;">
        <div style="padding:20px 16px;border-right:2px solid #222;">
            <div style="color:#FF007A;font-size:0.55rem;letter-spacing:3px;text-transform:uppercase;margin-bottom:6px;">SYSTEM</div>
            <div style="color:#CCFF00;font-size:0.75rem;font-weight:900;letter-spacing:1px;">CALIFORNIA BOSS</div>
            <div style="color:#555;font-size:0.58rem;margin-top:4px;letter-spacing:2px;">VERSION 0.01.v1</div>
        </div>
        <div style="padding:20px 16px;border-right:2px solid #222;text-align:center;">
            <div style="font-size:clamp(1.4rem,5vw,2.2rem);color:#CCFF00;font-family:'Archivo Black',sans-serif;line-height:1;-webkit-text-stroke:1px #FF007A;letter-spacing:1px;">CALIF</div>
            <div style="color:#FF007A;font-size:0.5rem;letter-spacing:4px;text-transform:uppercase;margin-top:4px;">BOSS</div>
        </div>
        <div style="padding:20px 16px;text-align:right;">
            <div style="color:#FF007A;font-size:0.55rem;letter-spacing:3px;text-transform:uppercase;margin-bottom:6px;">PRODUCER</div>
            <div style="color:#CCFF00;font-size:0.75rem;font-weight:900;letter-spacing:1px;">QUINN PRODUCTIONS</div>
            <div style="color:#555;font-size:0.58rem;margin-top:4px;letter-spacing:2px;">© 2026 · ALL RIGHTS RESERVED</div>
        </div>
    </div>
    <div style="background:#FF007A;padding:7px 16px;display:flex;justify-content:space-between;align-items:center;">
        <span style="color:#000;font-size:0.55rem;font-weight:900;letter-spacing:2px;text-transform:uppercase;">CREATED BY LEWIS ⚡</span>
        <span style="color:#000;font-size:0.55rem;font-weight:900;letter-spacing:2px;">🔞 ADULTS ONLY</span>
    </div>
</div>
<style>
@keyframes ticker { 0% { transform:translateX(0); } 100% { transform:translateX(-50%); } }
</style>
""", unsafe_allow_html=True)
