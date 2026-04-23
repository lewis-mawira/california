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
        <div style="padding:12px 16px;border-right:2px solid #222;text-align:center;">
            <img src="data:image/jpeg;base64,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" style="width:80px;height:80px;object-fit:cover;border-radius:50%;border:3px solid #FF007A;box-shadow:0 0 12px #FF007A;" />
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