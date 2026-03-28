"""
BSMQ Automation System - Main Shell v5
Uses BSMQ Dashboard v5 design system as main frontend.
5 tabs: Ops Center | Bidding | Database | Analytics | System
"""

import os
import sys
import json
import datetime
from collections import Counter

import streamlit as st
import streamlit.components.v1 as components

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="BSMQ Ops Center",
    page_icon="B",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# BSMQ Dashboard v5 â€” Full CSS (ported from BSMQ_Dashboard_v5.html)
# ---------------------------------------------------------------------------
V5_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,300;0,14..32,400;0,14..32,500;0,14..32,600;0,14..32,700&display=swap');

/* ── Warm Minimalist Design System ── */
:root {
  /* Surfaces */
  --bg:   #F2EDE6;
  --s1:   #FAF8F5;
  --s2:   #EDE8E0;
  --s3:   #E5DFD6;
  --s4:   #DDD8CF;
  --b0:   #D0C8BC;
  --b1:   rgba(61,53,48,0.08);
  --b2:   rgba(61,53,48,0.12);
  --b3:   rgba(61,53,48,0.18);

  /* Text */
  --text: #3D3530;
  --t2:   #6B5F56;
  --t3:   #B5AA9A;
  --t4:   #DDD8CF;

  /* Accent */
  --accent:   #8B6F5C;
  --accent-h: #7A6050;
  --accent-a: rgba(139,111,92,0.10);
  --accent-b: rgba(139,111,92,0.20);

  /* Status */
  --green:  #7A9E7E; --ga: rgba(122,158,126,0.12); --gb: rgba(122,158,126,0.20);
  --yellow: #C4955A; --ya: rgba(196,149,90,0.12);  --yb: rgba(196,149,90,0.20);
  --red:    #B85C5C; --ra: rgba(184,92,92,0.12);   --rb: rgba(184,92,92,0.20);
  --blue:   #5C85B8; --ba: rgba(92,133,184,0.12);  --bb: rgba(92,133,184,0.20);
  --cyan:   #5CA8A8; --ca: rgba(92,168,168,0.12);
  --orange: #C4855A; --oa: rgba(196,133,90,0.12);
  --violet: #8B7CF8; --va: rgba(139,124,248,0.12);

  /* Typography */
  --sans: "Inter", -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
  --mono: "SF Mono", "ui-monospace", "Cascadia Code", monospace;

  /* Geometry */
  --r:      8px;
  --r-card: 12px;
  --r-tag:  6px;

  /* Shadows */
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.06);
  --shadow-lg: 0 8px 32px rgba(0,0,0,0.08);
}

/* ── Reset & Base ── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, .stApp {
  background: var(--bg) !important;
  color: var(--text) !important;
  font-family: var(--sans) !important;
  font-size: 14px;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
  font-feature-settings: "cv01","cv02","cv03","cv04","tnum";
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.01em;
}

/* ── Streamlit overrides ── */
.stApp > header { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }
.block-container {
  max-width: 1440px !important;
  padding: 8px 40px 48px !important;
}
[data-testid="column"] { padding: 0 6px !important; }
[data-testid="stHorizontalBlock"] { gap: 12px !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--s2); }
::-webkit-scrollbar-thumb { background: var(--b0); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--t3); }

/* ── Typography ── */
h1,h2,h3,h4,h5,h6 { font-family: var(--sans); color: var(--text); font-weight: 600; line-height: 1.3; }
h1 { font-size: 22px; font-weight: 700; letter-spacing: -0.4px; }
h2 { font-size: 17px; font-weight: 600; letter-spacing: -0.2px; }
h3 { font-size: 14px; font-weight: 600; letter-spacing: -0.1px; }
p, span, li, td, th { font-family: var(--sans); color: var(--text); }
code, pre { font-family: var(--mono); }

/* ── Streamlit text ── */
.stMarkdown p, .stText { color: var(--text) !important; font-family: var(--sans) !important; }
label[data-testid="stWidgetLabel"] p { color: var(--t2) !important; font-size: 13px !important; font-weight: 500 !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
  background: transparent !important;
  border-bottom: 1px solid var(--b2) !important;
  gap: 0 !important;
  padding: 0 !important;
}
.stTabs [data-baseweb="tab"] {
  background: transparent !important;
  color: var(--t2) !important;
  font-family: var(--sans) !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  padding: 10px 20px !important;
  border: none !important;
  border-bottom: 2px solid transparent !important;
  border-radius: 0 !important;
  transition: color 0.15s, border-color 0.15s !important;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--text) !important; }
.stTabs [aria-selected="true"] {
  color: var(--accent) !important;
  border-bottom-color: var(--accent) !important;
  font-weight: 600 !important;
}
.stTabs [data-baseweb="tab-panel"] { padding: 24px 0 0 !important; }

/* ── Buttons ── */
.stButton > button {
  background: var(--accent) !important;
  color: #fff !important;
  border: none !important;
  border-radius: var(--r) !important;
  font-family: var(--sans) !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  padding: 8px 16px !important;
  cursor: pointer !important;
  transition: background 0.15s, box-shadow 0.15s !important;
  box-shadow: var(--shadow-sm) !important;
}
.stButton > button:hover {
  background: var(--accent-h) !important;
  box-shadow: var(--shadow-md) !important;
}
.stButton > button[kind="secondary"] {
  background: var(--s1) !important;
  color: var(--accent) !important;
  border: 1px solid var(--b2) !important;
}
.stButton > button[kind="secondary"]:hover {
  background: var(--s2) !important;
  border-color: var(--accent) !important;
}

/* ── Inputs ── */
.stTextInput > div > div > input,
.stTextArea textarea,
.stSelectbox > div > div,
.stNumberInput > div > div > input {
  background: var(--s1) !important;
  color: var(--text) !important;
  border: 1px solid var(--b2) !important;
  border-radius: var(--r) !important;
  font-family: var(--sans) !important;
  font-size: 13px !important;
  padding: 8px 12px !important;
  transition: border-color 0.15s, box-shadow 0.15s !important;
}
.stTextInput > div > div > input:focus,
.stTextArea textarea:focus {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px var(--accent-a) !important;
  outline: none !important;
}
.stSelectbox > div > div:hover { border-color: var(--accent) !important; }
.stSelectbox [data-baseweb="popover"] { background: var(--s1) !important; border: 1px solid var(--b2) !important; border-radius: var(--r-card) !important; box-shadow: var(--shadow-lg) !important; }
.stSelectbox [role="option"] { background: transparent !important; color: var(--text) !important; font-size: 13px !important; }
.stSelectbox [role="option"]:hover { background: var(--s2) !important; }

/* ── Metric ── */
[data-testid="stMetric"] {
  background: var(--s1) !important;
  border: 1px solid var(--b1) !important;
  border-radius: var(--r-card) !important;
  padding: 16px 20px !important;
  box-shadow: var(--shadow-sm) !important;
}
[data-testid="stMetric"] label { color: var(--t2) !important; font-size: 12px !important; font-weight: 500 !important; text-transform: uppercase !important; letter-spacing: 0.5px !important; }
[data-testid="stMetricValue"] { color: var(--text) !important; font-size: 28px !important; font-weight: 700 !important; line-height: 1.1 !important; }
[data-testid="stMetricDelta"] { font-size: 12px !important; }

/* ── Expander ── */
.stExpander { border: 1px solid var(--b2) !important; border-radius: var(--r-card) !important; background: var(--s1) !important; box-shadow: var(--shadow-sm) !important; margin-bottom: 8px !important; }
.stExpander details summary { color: var(--text) !important; font-weight: 500 !important; font-size: 14px !important; }

/* ── Divider ── */
hr { border: none !important; border-top: 1px solid var(--b2) !important; margin: 16px 0 !important; }

/* ── DataFrame / Table ── */
.stDataFrame, [data-testid="stTable"] {
  border: 1px solid var(--b2) !important;
  border-radius: var(--r-card) !important;
  overflow: hidden !important;
  box-shadow: var(--shadow-sm) !important;
}
[data-testid="stTable"] th { background: var(--s2) !important; color: var(--t2) !important; font-size: 12px !important; font-weight: 600 !important; text-transform: uppercase !important; letter-spacing: 0.4px !important; padding: 10px 14px !important; border-bottom: 1px solid var(--b2) !important; }
[data-testid="stTable"] td { color: var(--text) !important; padding: 10px 14px !important; border-bottom: 1px solid var(--b1) !important; font-size: 13px !important; }
[data-testid="stTable"] tr:last-child td { border-bottom: none !important; }
[data-testid="stTable"] tr:hover td { background: var(--s2) !important; }

/* ── Alerts ── */
.stAlert { border-radius: var(--r-card) !important; border: 1px solid var(--b2) !important; font-size: 13px !important; }
[data-baseweb="notification"][kind="info"] { background: var(--ba) !important; border-color: var(--blue) !important; }
[data-baseweb="notification"][kind="warning"] { background: var(--ya) !important; border-color: var(--yellow) !important; }
[data-baseweb="notification"][kind="error"] { background: var(--ra) !important; border-color: var(--red) !important; }
[data-baseweb="notification"][kind="success"] { background: var(--ga) !important; border-color: var(--green) !important; }

/* ── Progress ── */
.stProgress > div > div { background: var(--s3) !important; border-radius: 4px !important; }
.stProgress > div > div > div { background: var(--accent) !important; border-radius: 4px !important; }

/* ── Spinner ── */
.stSpinner > div { border-top-color: var(--accent) !important; }

/* ── Checkbox / Radio / Toggle ── */
.stCheckbox label span { color: var(--text) !important; font-size: 13px !important; }
.stRadio label span { color: var(--text) !important; font-size: 13px !important; }

/* ═══════════════════════════════════════════
   BSMQ Custom Components
═══════════════════════════════════════════ */

/* ── Section header (.sec) ── */
.sec {
  display: flex; align-items: center; gap: 10px;
  padding: 16px 0 12px;
  border-bottom: 1px solid var(--b2);
  margin-bottom: 16px;
}
.sec h3 { font-size: 15px; font-weight: 600; color: var(--text); }
.sec .badge {
  background: var(--accent-a); color: var(--accent);
  border: 1px solid var(--accent-b);
  border-radius: 20px; padding: 2px 8px; font-size: 11px; font-weight: 600;
}

/* ── Module card (.mod) ── */
.mod {
  background: var(--s1);
  border: 1px solid var(--b1);
  border-radius: var(--r-card);
  padding: 20px;
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.15s;
}
.mod:hover { box-shadow: var(--shadow-md); }
.mod-title { font-size: 13px; font-weight: 600; color: var(--t2); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
.mod-value { font-size: 22px; font-weight: 700; color: var(--text); }
.mod-sub { font-size: 12px; color: var(--t3); margin-top: 4px; }

/* ── KPI grid (.g5) ── */
.g5 { display: grid; grid-template-columns: repeat(5,1fr); gap: 12px; margin-bottom: 24px; }

/* ── KPI card (.kpi) ── */
.kpi {
  background: var(--s1);
  border: 1px solid var(--b1);
  border-left: 3px solid var(--kc, var(--accent));
  border-radius: var(--r-card);
  padding: 16px 18px;
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.15s, transform 0.15s;
}
.kpi:hover { box-shadow: var(--shadow-md); transform: translateY(-1px); }
.kl { font-size: 11px; font-weight: 600; color: var(--t2); text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 8px; }
.kv { font-size: 26px; font-weight: 700; color: var(--text); line-height: 1.1; letter-spacing: -0.5px; }
.ks { font-size: 12px; color: var(--t3); margin-top: 4px; }

/* ── Generic card (.card) ── */
.card {
  background: var(--s1);
  border: 1px solid var(--b1);
  border-radius: var(--r-card);
  padding: 20px;
  box-shadow: var(--shadow-sm);
  margin-bottom: 12px;
  transition: box-shadow 0.15s;
}
.card:hover { box-shadow: var(--shadow-md); }
.card-title { font-size: 12px; font-weight: 600; color: var(--t2); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; }
.card-body { font-size: 14px; color: var(--text); }

/* ── Pipeline ── */
.pipeline {
  display: flex; align-items: center; gap: 0;
  background: var(--s1); border: 1px solid var(--b1);
  border-radius: var(--r-card); padding: 12px 16px;
  box-shadow: var(--shadow-sm); overflow-x: auto;
  margin-bottom: 16px;
}
.pipe-step {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px; border-radius: var(--r); font-size: 12px; font-weight: 500;
  color: var(--t2); white-space: nowrap; position: relative;
}
.pipe-step::after {
  content: "";
  position: absolute; right: -12px; top: 50%; transform: translateY(-50%);
  width: 8px; height: 1px; background: var(--b0);
}
.pipe-step:last-child::after { display: none; }
.pipe-step.active { background: var(--accent-a); color: var(--accent); font-weight: 600; }
.pipe-step.done { background: var(--ga); color: var(--green); }
.pipe-step.warn { background: var(--ya); color: var(--yellow); }
.pipe-step.danger { background: var(--ra); color: var(--red); }
.pipe-dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; flex-shrink: 0; }

/* ── Order card (.order-card) ── */
.order-card {
  background: var(--s1);
  border: 1px solid var(--b1);
  border-radius: var(--r-card);
  padding: 16px;
  box-shadow: var(--shadow-sm);
  margin-bottom: 8px;
  transition: box-shadow 0.15s, border-color 0.15s;
}
.order-card:hover { box-shadow: var(--shadow-md); border-color: var(--b3); }
.order-card .oc-id { font-size: 13px; font-weight: 600; color: var(--text); }
.order-card .oc-meta { font-size: 12px; color: var(--t3); margin-top: 2px; }
.order-card .oc-status { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: var(--r-tag); }

/* ── Job card (.jcard) ── */
.jcard {
  background: var(--s1);
  border: 1px solid var(--b1);
  border-radius: var(--r-card);
  padding: 14px 16px;
  box-shadow: var(--shadow-sm);
  margin-bottom: 8px;
  display: flex; align-items: flex-start; gap: 12px;
}
.jcard .ji { width: 32px; height: 32px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0; }
.jcard .jbody { flex: 1; min-width: 0; }
.jcard .jt { font-size: 13px; font-weight: 600; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.jcard .jm { font-size: 12px; color: var(--t3); margin-top: 2px; }

/* ── Log entry (.le) ── */
.le {
  display: flex; gap: 12px; padding: 8px 12px;
  border-bottom: 1px solid var(--b1);
  font-size: 12px; line-height: 1.5; align-items: flex-start;
}
.le:last-child { border-bottom: none; }
.le .ts { color: var(--t3); white-space: nowrap; font-family: var(--mono); font-size: 11px; padding-top: 1px; }
.le .msg { color: var(--t2); flex: 1; }
.le.info .msg { color: var(--blue); }
.le.ok .msg { color: var(--green); }
.le.warn .msg { color: var(--yellow); }
.le.err .msg { color: var(--red); }

/* ── Tags / Badges (.tag) ── */
.tag {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 8px; border-radius: var(--r-tag);
  font-size: 11px; font-weight: 600; letter-spacing: 0.2px; white-space: nowrap;
}
.tag.green  { background: var(--ga); color: var(--green); border: 1px solid var(--gb); }
.tag.yellow { background: var(--ya); color: var(--yellow); border: 1px solid var(--yb); }
.tag.red    { background: var(--ra); color: var(--red);    border: 1px solid var(--rb); }
.tag.blue   { background: var(--ba); color: var(--blue);   border: 1px solid var(--bb); }
.tag.accent { background: var(--accent-a); color: var(--accent); border: 1px solid var(--accent-b); }
.tag.muted  { background: var(--s3); color: var(--t2); border: 1px solid var(--b2); }

/* ── Decision row (.decision) ── */
.decision {
  background: var(--s1);
  border: 1px solid var(--b1);
  border-radius: var(--r-card);
  padding: 14px 16px;
  margin-bottom: 8px;
  display: flex; gap: 12px; align-items: flex-start;
  box-shadow: var(--shadow-sm);
}
.decision .di { width: 36px; height: 36px; border-radius: 8px; background: var(--s3); display: flex; align-items: center; justify-content: center; font-size: 16px; flex-shrink: 0; }
.decision .db { flex: 1; }
.decision .dt { font-size: 13px; font-weight: 600; color: var(--text); }
.decision .dd { font-size: 12px; color: var(--t3); margin-top: 3px; }

/* ── Confidence indicator (.ci) ── */
.ci {
  display: flex; align-items: center; gap: 8px; font-size: 12px;
}
.ci-bar { flex: 1; height: 4px; background: var(--s3); border-radius: 2px; overflow: hidden; }
.ci-fill { height: 100%; border-radius: 2px; background: var(--accent); }
.ci-pct { color: var(--t2); font-weight: 600; min-width: 32px; text-align: right; font-family: var(--mono); font-size: 11px; }

/* ── Compact info row ── */
.info-row { display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 8px; }
.info-row .ir { display: flex; flex-direction: column; gap: 2px; }
.info-row .ir-label { font-size: 11px; color: var(--t3); font-weight: 500; text-transform: uppercase; letter-spacing: 0.4px; }
.info-row .ir-value { font-size: 13px; color: var(--text); font-weight: 500; }

/* ── Status dots ── */
.dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.dot.green  { background: var(--green); }
.dot.yellow { background: var(--yellow); }
.dot.red    { background: var(--red); }
.dot.blue   { background: var(--blue); }
.dot.muted  { background: var(--t4); }

/* ── Monospaced display box ── */
.mono-box {
  background: var(--s2); border: 1px solid var(--b2); border-radius: var(--r);
  padding: 12px 16px; font-family: var(--mono); font-size: 12px;
  color: var(--text); line-height: 1.6; overflow-x: auto;
}

/* ── Empty state ── */
.empty-state {
  text-align: center; padding: 48px 24px; color: var(--t3);
}
.empty-state .ei { font-size: 32px; margin-bottom: 12px; }
.empty-state .et { font-size: 15px; font-weight: 600; color: var(--t2); margin-bottom: 6px; }
.empty-state .ed { font-size: 13px; }

/* ── Main layout ── */
.stApp {
  background: var(--bg) !important;
  min-height: 100vh;
}
</style>
"""

# ---------------------------------------------------------------------------
# Config helper
# ---------------------------------------------------------------------------
from modules.config import get_config as _load_config


def _get_db_path() -> str:
    cfg = _load_config()
    return os.path.join(_ROOT, cfg.get("db_path", "bsmq.db").lstrip("./"))


@st.cache_data(ttl=30)
def _load_audit_entries(limit: int = 500) -> list[dict]:
    cfg = _load_config()
    log_dir = os.path.join(_ROOT, cfg.get("log_dir", "logs"))
    log_path = os.path.join(log_dir, "audit.jsonl")
    if not os.path.exists(log_path):
        return []

    rows = []
    try:
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []

    if limit > 0:
        return rows[-limit:]
    return rows


@st.cache_data(ttl=30)
def _get_pipeline_snapshot() -> dict:
    stats = {"total": 0, "ok": 0, "expired": 0, "none": 0, "tm": 0, "gc": 0, "query_ms": 0}
    events_unprocessed = 0
    watch_folders = 0
    watch_running = False
    ai_total = 0
    ai_yes = 0
    ai_no = 0
    ai_maybe = 0
    ai_override = 0

    try:
        from modules.database import init_sqlite_db, get_db_stats
        db = _get_db_path()
        init_sqlite_db(db)
        stats = get_db_stats(db)
    except Exception:
        pass

    try:
        from modules.watchdog_sync import count_unprocessed, get_status
        events_unprocessed = count_unprocessed()
        wd = get_status() or {}
        watch_folders = int(wd.get("folders", 0) or 0)
        watch_running = bool(wd.get("running", False))
    except Exception:
        pass

    audit_rows = _load_audit_entries(limit=500)
    decisions = [
        r.get("final_decision") or r.get("decision")
        for r in audit_rows
        if r.get("action") in ("classification", "classification_override")
    ]
    if decisions:
        c = Counter(decisions)
        ai_total = sum(c.values())
        ai_yes = c.get("yes", 0)
        ai_no = c.get("no", 0)
        ai_maybe = c.get("maybe", 0)
    ai_override = sum(1 for r in audit_rows if r.get("action") == "classification_override")

    return {
        "db": stats,
        "watch_unprocessed": events_unprocessed,
        "watch_folders": watch_folders,
        "watch_running": watch_running,
        "ai_total": ai_total,
        "ai_yes": ai_yes,
        "ai_no": ai_no,
        "ai_maybe": ai_maybe,
        "ai_override": ai_override,
    }


def _get_module_health_status(total_products: int = 0) -> list[tuple]:
    try:
        from modules.folder_browser import get_watchdog_status
        wd = get_watchdog_status() or {}
        wd_running = wd.get("running", False)
    except Exception:
        wd_running = False

    return [
        ("Watchdog", wd_running, "RUN" if wd_running else "IDLE"),
        ("SQLite FTS5", True, f"{total_products:,}"),
        ("AI Classifier", None, "READY"),
        ("Auto Fill", None, "READY"),
        ("Crawler", False, "QUEUE"),
        ("Notifications", True, "OK"),
    ]


# ---------------------------------------------------------------------------
# Header bar (v5 topbar style)
# ---------------------------------------------------------------------------
def _render_header():
    now = datetime.datetime.now()
    time_str = now.strftime("%H:%M")
    date_str = now.strftime("%d/%m/%Y")
    qn = len(st.session_state.get("t2_quote_queue", []))
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:10px;'
        f'background:var(--s1);border-bottom:1px solid var(--b1);'
        f'padding:0 24px;height:48px;margin:-8px -40px 16px -40px;">'
        # Logo mark
        f'<div style="display:flex;align-items:center;gap:10px;margin-right:20px;">'
        f'<div style="width:28px;height:28px;flex-shrink:0;border-radius:7px;'
        f'background:var(--accent);'
        f'display:flex;align-items:center;justify-content:center;'
        f'font-family:var(--sans);font-weight:700;font-size:12px;color:#fff;letter-spacing:-0.5px;">B</div>'
        f'<div style="display:flex;flex-direction:column;gap:0;">'
        f'<span style="font-family:var(--sans);font-size:13px;font-weight:700;'
        f'color:var(--text);letter-spacing:-0.3px;line-height:1.2;">BSMQ</span>'
        f'<span style="font-size:9px;color:var(--t3);font-weight:400;line-height:1;">Ops Center</span>'
        f'</div>'
        f'</div>'
        # Spacer
        f'<div style="flex:1;"></div>'
        # Right side
        f'<div style="display:flex;align-items:center;gap:12px;">'
        f'<span style="font-size:11px;font-weight:500;color:var(--accent);'
        f'background:var(--accent-a);border:1px solid var(--accent-b);'
        f'padding:3px 10px;border-radius:20px;">Queue {qn}</span>'
        f'<div style="width:6px;height:6px;border-radius:50%;background:var(--green);flex-shrink:0;"></div>'
        f'<span style="font-size:12px;font-weight:500;color:var(--t2);font-family:var(--sans);">{time_str}</span>'
        f'<span style="font-size:11px;color:var(--t3);">{date_str}</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )


# ---------------------------------------------------------------------------
# Tab: Ops Center
# ---------------------------------------------------------------------------
def _render_ops_center():
    snapshot = _get_pipeline_snapshot()
    stats = snapshot["db"]
    total = stats.get("total", 0)
    ok = stats.get("ok", 0)
    expired = stats.get("expired", 0)
    none_ = stats.get("none", 0)
    qms = stats.get("query_ms", 0)
    pct_ok = int(ok / total * 100) if total else 0

    watch_unprocessed = snapshot.get("watch_unprocessed", 0)
    watch_folders = snapshot.get("watch_folders", 0)
    ai_total = snapshot.get("ai_total", 0)
    ai_yes = snapshot.get("ai_yes", 0)
    ai_maybe = snapshot.get("ai_maybe", 0)
    ai_override = snapshot.get("ai_override", 0)

    st.markdown(
        f'<div class="g5" style="margin-bottom:10px;">'
        f'<div class="kpi" style="--kc:var(--cyan)">'
        f'  <div class="kl">Products DB</div><div class="kv">{total:,}</div>'
        f'  <div class="ks">san pham · SQLite FTS5</div>'
        f'</div>'
        f'<div class="kpi" style="--kc:var(--green)">'
        f'  <div class="kl">Gia con han</div><div class="kv">{ok:,}</div>'
        f'  <div class="ks">{pct_ok}% con hieu luc</div>'
        f'</div>'
        f'<div class="kpi" style="--kc:var(--yellow)">'
        f'  <div class="kl">Het han</div><div class="kv">{expired:,}</div>'
        f'  <div class="ks">can cap nhat gia</div>'
        f'</div>'
        f'<div class="kpi" style="--kc:var(--red)">'
        f'  <div class="kl">Chua co gia</div><div class="kv">{none_:,}</div>'
        f'  <div class="ks">can tim gia moi</div>'
        f'</div>'
        f'<div class="kpi" style="--kc:var(--violet)">'
        f'  <div class="kl">FTS5 Query</div>'
        f'  <div class="kv" style="font-size:20px;padding-top:4px;">&lt;{qms}ms</div>'
        f'  <div class="ks">full-text search</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    s1_cls = "done" if snapshot.get("watch_running", False) else "danger"
    s2_cls = "active" if ai_total else ""
    s3_cls = "warn" if (expired + none_) > 0 else "done"
    s4_cls = "done" if ai_yes > 0 else ""
    s5_cls = "warn" if ai_maybe > 0 else ""

    st.markdown(
        '<div class="pipeline" style="margin-bottom:10px;">'
        f'<div class="pipe-step {s1_cls}">'
        '  <div class="pipe-num"><div class="pipe-num-dot">1</div>RECEIVE</div>'
        '  <div class="pipe-title">BC BQMS</div>'
        f'  <div class="pipe-sub">{watch_folders} watched folders<br>{watch_unprocessed} pending events</div>'
        f'  <div class="pipe-cnt">{watch_unprocessed}</div>'
        '</div>'
        f'<div class="pipe-step {s2_cls}">'
        '  <div class="pipe-num"><div class="pipe-num-dot">2</div>CLASSIFY</div>'
        '  <div class="pipe-title">AI Filter</div>'
        f'  <div class="pipe-sub">{ai_total} recent decisions<br>{ai_override} manual overrides</div>'
        f'  <div class="pipe-cnt">{ai_total}</div>'
        '</div>'
        f'<div class="pipe-step {s3_cls}">'
        '  <div class="pipe-num"><div class="pipe-num-dot">3</div>PRICE CHECK</div>'
        '  <div class="pipe-title">Price Review</div>'
        f'  <div class="pipe-sub">{expired} expired · {none_} no-price<br>vendor + history lookup</div>'
        f'  <div class="pipe-cnt">{expired + none_}</div>'
        '</div>'
        f'<div class="pipe-step {s4_cls}">'
        '  <div class="pipe-num"><div class="pipe-num-dot">4</div>AUTO FILL</div>'
        '  <div class="pipe-title">Document Build</div>'
        f'  <div class="pipe-sub">{ai_yes} likely-join orders<br>Excel + PDF</div>'
        f'  <div class="pipe-cnt">{ai_yes}</div>'
        '</div>'
        f'<div class="pipe-step {s5_cls}">'
        '  <div class="pipe-num"><div class="pipe-num-dot">5</div>SUBMIT</div>'
        '  <div class="pipe-title">Samsung AMA</div>'
        f'  <div class="pipe-sub">portal upload<br>{ai_maybe} orders need review</div>'
        f'  <div class="pipe-cnt">{ai_maybe}</div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

    col_left, col_main = st.columns([1, 2])

    with col_left:
        st.markdown(
            '<div class="card" style="--ca:var(--green);margin-bottom:8px;">'
            '<div class="card-top"></div>'
            '<div class="clabel">Daily Checklist</div>'
            '<div style="display:flex;flex-direction:column;gap:3px;">'
            '<div class="ci done"><div class="cib">1</div><div class="ci-body">'
            '<div class="ci-n">Watch incoming BC BQMS</div>'
            '<div class="ci-d">OneDrive + watchdog</div></div></div>'
            '<div class="ci run"><div class="cib">2</div><div class="ci-body">'
            '<div class="ci-n">Review AI decisions</div>'
            '<div class="ci-d">PO Filter + manual override</div></div></div>'
            '<div class="ci"><div class="cib">3</div><div class="ci-body">'
            '<div class="ci-n">Confirm vendor price</div>'
            '<div class="ci-d">Alibaba + local suppliers</div></div></div>'
            '<div class="ci"><div class="cib">4</div><div class="ci-body">'
            '<div class="ci-n">Generate quotation docs</div>'
            '<div class="ci-d">Auto Fill templates</div></div></div>'
            '<div class="ci"><div class="cib">5</div><div class="ci-body">'
            '<div class="ci-n">Submit to portal</div>'
            '<div class="ci-d">Samsung AMA rounds</div></div></div>'
            '</div></div>',
            unsafe_allow_html=True
        )

        rows = ""
        for name, ok_flag, label in _get_module_health_status(total_products=total):
            dot_cls = "dg" if ok_flag is True else ("dr" if ok_flag is False else "dy")
            badge_cls = "mok" if ok_flag is True else ("midle" if ok_flag is None else "merr")
            rows += f'<div class="mod"><div class="md {dot_cls}"></div><div class="mn">{name}</div><div class="mt {badge_cls}">{label}</div></div>'

        st.markdown(
            f'<div class="card" style="--ca:var(--blue);margin-bottom:8px;">'
            f'<div class="card-top"></div>'
            f'<div class="clabel">Modules</div>'
            f'<div style="display:flex;flex-direction:column;gap:3px;">{rows}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        st.markdown(
            '<div class="card" style="--ca:var(--cyan);">'
            '<div class="card-top"></div>'
            '<div class="clabel">Activity Log</div>',
            unsafe_allow_html=True
        )
        try:
            from modules.folder_browser import get_recent_events
            events = get_recent_events(limit=12)
            if events:
                le_html = ""
                for ev in events:
                    etype = ev.get("event_type", "")
                    fname = os.path.basename(ev.get("file_path", ""))
                    ts = str(ev.get("created_at", ""))[:19]
                    cls = "ok" if etype in ("created", "modified") else "warn"
                    tag = "t-ok" if etype == "created" else "t-w"
                    tag_lbl = "NEW" if etype == "created" else "MOD" if etype == "modified" else "DEL"
                    le_html += (
                        f'<div class="le {cls}">'
                        f'<span class="le-t">{ts[11:19]}</span>'
                        f'<span class="le-tag {tag}">{tag_lbl}</span>'
                        f'<span class="le-msg">{fname}</span>'
                        f'</div>'
                    )
                st.markdown(f'<div class="log-wrap">{le_html}</div></div>', unsafe_allow_html=True)
            else:
                st.markdown(
                    '<div style="font-size:8px;color:var(--t3);padding:6px 0;">No events yet. Configure watched folders in System tab.</div></div>',
                    unsafe_allow_html=True,
                )
        except Exception as e:
            st.markdown(f'<div style="font-size:8px;color:var(--red)">Error: {e}</div></div>', unsafe_allow_html=True)

    with col_main:
        st.markdown('<div class="sec" style="margin-bottom:8px;">Auto Fill Tool</div>', unsafe_allow_html=True)
        try:
            from tools.tool1_autofill.app import render_tool1_tab
            render_tool1_tab()
        except Exception as e:
            st.error(f"Tool 1 error: {e}")
            import traceback
            st.code(traceback.format_exc())

# ---------------------------------------------------------------------------
# Tab: Đấu Thầu (PO Filter)
# ---------------------------------------------------------------------------
def _render_bidding_tab():
    try:
        from modules.database import get_db_stats, init_sqlite_db
        db = _get_db_path()
        init_sqlite_db(db)
        stats = get_db_stats(db)
        po_total = stats.get("total", 0)
    except Exception:
        po_total = 0

    # KPI strip
    st.markdown(
        f'<div class="g4" style="margin-bottom:10px;">'
        f'<div class="kpi" style="--kc:var(--blue)">'
        f'  <div class="kl">Round 1</div><div class="kv" id="k-r1">-</div>'
        f'  <div class="ks">waiting for submission</div>'
        f'</div>'
        f'<div class="kpi" style="--kc:var(--yellow)">'
        f'  <div class="kl">Round 2</div><div class="kv" id="k-r2">-</div>'
        f'  <div class="ks">need price adjustment</div>'
        f'</div>'
        f'<div class="kpi" style="--kc:var(--orange)">'
        f'  <div class="kl">Round 3</div><div class="kv" id="k-r3">-</div>'
        f'  <div class="ks">near deadline</div>'
        f'</div>'
        f'<div class="kpi" style="--kc:var(--green)">'
        f'  <div class="kl">DB Products</div><div class="kv">{po_total:,}</div>'
        f'  <div class="ks">products in DB</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True
    )

    # PO Filter tool
    try:
        from tools.tool3_pofilter.app import render_tool3_tab
        render_tool3_tab()
    except Exception as e:
        st.error(f"Tool 3 error: {e}")
        import traceback
        st.code(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tab: Database
# ---------------------------------------------------------------------------
def _render_database_tab():
    try:
        from modules.database import init_sqlite_db, search_products, get_db_stats
        db = _get_db_path()
        init_sqlite_db(db)
        stats = get_db_stats(db)
    except Exception as e:
        st.error(f"DB error: {e}")
        return

    total   = stats.get("total", 0)
    ok      = stats.get("ok", 0)
    expired = stats.get("expired", 0)
    none_   = stats.get("none", 0)
    qms     = stats.get("query_ms", 0)

    # KPI row
    st.markdown(
        f'<div class="g5" style="margin-bottom:10px;">'
        f'<div class="kpi" style="--kc:var(--cyan)"><div class="kl">Total</div><div class="kv">{total:,}</div><div class="ks">products</div></div>'
        f'<div class="kpi" style="--kc:var(--green)"><div class="kl">Valid Price</div><div class="kv">{ok:,}</div><div class="ks">still active</div></div>'
        f'<div class="kpi" style="--kc:var(--yellow)"><div class="kl">Expired</div><div class="kv">{expired:,}</div><div class="ks">needs refresh</div></div>'
        f'<div class="kpi" style="--kc:var(--red)"><div class="kl">No Price</div><div class="kv">{none_:,}</div><div class="ks">missing data</div></div>'
        f'<div class="kpi" style="--kc:var(--violet)"><div class="kl">FTS5 Query</div>'
        f'<div class="kv" style="font-size:18px;padding-top:4px;">&lt;{qms}ms</div>'
        f'<div class="ks">full-text search</div></div>'
        f'</div>',
        unsafe_allow_html=True
    )

    mode = st.radio(
        "Database mode",
        ["BQMS Analytics", "BC BQMS 2026", "Gia Cong L2 Wizard", "Product Search"],
        horizontal=True,
        label_visibility="collapsed",
        key="db_mode_switch",
    )

    if mode == "BQMS Analytics":
        try:
            from tools.tool2_pricetracker.app import render_tool2_tab
            render_tool2_tab(db)
        except Exception as e:
            st.warning(f"Tool 2 not ready: {e}")
        return

    if mode == "BC BQMS 2026":
        try:
            import tools.tool2_pricetracker.app as tool2_app
            fn = getattr(tool2_app, "render_tool2_bc2026_tab", None)
            if callable(fn):
                fn(db)
            else:
                st.warning("BC BQMS 2026 tab is not available in current Tool 2 module. Please restart app.")
        except Exception as e:
            st.warning(f"BC BQMS 2026 tab not ready: {e}")
        return

    if mode == "Gia Cong L2 Wizard":
        st.markdown('<div class="sec" style="margin:8px 0 8px;">Gia Cong L2 Workflow Wizard</div>', unsafe_allow_html=True)
        try:
            from tools.tool1_autofill.gc_l2_wizard import render_gc_l2_wizard
            render_gc_l2_wizard()
        except Exception as e:
            st.error(f"Gia Cong L2 wizard error: {e}")
            import traceback
            st.code(traceback.format_exc())
        return

    # Product Search
    st.markdown('<div class="sec" style="margin:8px 0 8px;">Product Search</div>', unsafe_allow_html=True)

    col_s, col_f = st.columns([3, 1])
    q      = col_s.text_input("Search", placeholder="Search code, name, spec... (fuzzy FTS5)",
                               label_visibility="collapsed", key="db_q")
    type_f = col_f.selectbox("Type", ["All", "GC", "TM"],
                              label_visibility="collapsed", key="db_type")
    type_map = {"GC": "gc", "TM": "tm", "All": None}

    try:
        results = search_products(q, type_filter=type_map[type_f], db_path=db)
    except Exception as e:
        st.error(f"Search error: {e}")
        results = []

    # Filter pills (display only)
    pills_html = (
        f'<div style="display:flex;flex-wrap:wrap;gap:4px;margin:6px 0;">'
        f'<span class="pill on">All · {total:,}</span>'
        f'<span class="pill">GC · {stats.get("gc", 0):,}</span>'
        f'<span class="pill">TM · {stats.get("tm", 0):,}</span>'
        f'<span class="pill">Valid · {ok:,}</span>'
        f'<span class="pill">Expired · {expired:,}</span>'
        f'</div>'
    )
    st.markdown(pills_html, unsafe_allow_html=True)

    if results:
        import pandas as pd
        df = pd.DataFrame(results)
        show_cols = [c for c in ["code", "name", "spec", "type", "maker", "price", "price_status", "updated_at"]
                     if c in df.columns]
        st.dataframe(df[show_cols] if show_cols else df,
                     use_container_width=True, height=420)
        st.markdown(
            f'<div style="font-size:8px;color:var(--t3);margin-top:4px;">{len(results)} results · max 200 rows · FTS5</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div style="text-align:center;padding:60px;color:var(--t3);font-family:var(--mono);font-size:11px;">'
            'Enter product keyword to start searching · Fuzzy match · FTS5</div>',
            unsafe_allow_html=True
        )


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Analytics helpers (cached)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=60)
def _load_product_stats() -> dict:
    """Load product distribution from SQLite for analytics charts."""
    db_path = _get_db_path()
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT price_status, COUNT(*) FROM products GROUP BY price_status")
        status = dict(cur.fetchall())
        cur.execute("SELECT type, COUNT(*) FROM products WHERE type IS NOT NULL GROUP BY type")
        types = dict(cur.fetchall())
        cur.execute(
            "SELECT maker, COUNT(*) n FROM products WHERE maker IS NOT NULL AND maker != \'\' "
            "GROUP BY maker ORDER BY n DESC LIMIT 8"
        )
        makers = cur.fetchall()
        conn.close()
        return {"status": status, "types": types, "makers": makers}
    except Exception:
        return {"status": {}, "types": {}, "makers": []}


@st.cache_data(ttl=60)
def _load_po_stats() -> list:
    """Load po_history rows for analytics."""
    db_path = _get_db_path()
    try:
        import sqlite3, pandas as pd
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(
            "SELECT status, ai_decision, ai_confidence, created_at FROM po_history "
            "ORDER BY created_at DESC LIMIT 500",
            conn,
        )
        conn.close()
        return df.to_dict("records")
    except Exception:
        return []


_CHART_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(8,13,20,0.6)",
    font=dict(family="IBM Plex Mono", color="#6e8aaa", size=9),
    margin=dict(l=30, r=20, t=30, b=30),
    showlegend=True,
    legend=dict(font=dict(size=9), bgcolor="rgba(0,0,0,0)", bordercolor="rgba(255,255,255,.05)"),
)
_NEON = ["#00ff88", "#ff1744", "#ffb300", "#3ab8fb", "#8b7cf8", "#00e5ff", "#ff8c42", "#f06292"]


# ---------------------------------------------------------------------------
# Tab: Analytics
# ---------------------------------------------------------------------------
def _render_analytics_tab():
    import pandas as pd
    try:
        import plotly.graph_objects as go
        HAS_PLOTLY = True
    except ImportError:
        HAS_PLOTLY = False

    audit_rows    = _load_audit_entries(limit=1000)
    class_rows    = [r for r in audit_rows if r.get("action") == "classification"]
    override_rows = [r for r in audit_rows if r.get("action") == "classification_override"]
    prod_stats    = _load_product_stats()
    po_rows       = _load_po_stats()

    # KPI row
    dec_counter = Counter((r.get("decision") or "maybe") for r in class_rows)
    total    = len(class_rows)
    yes      = dec_counter.get("yes", 0)
    no       = dec_counter.get("no", 0)
    maybe    = dec_counter.get("maybe", 0)
    avg_conf = round(
        sum(float(r.get("confidence", 0) or 0) for r in class_rows) / total * 100, 1
    ) if total else 0.0
    override_ratio = (len(override_rows) / total * 100) if total else 0.0
    win_rate = 0.0
    if po_rows:
        wins = sum(1 for r in po_rows if str(r.get("status", "")).lower() == "win")
        win_rate = round(wins / len(po_rows) * 100, 1)

    st.markdown(
        f'<div class="g5" style="margin-bottom:10px;">'
        f'<div class="kpi" style="--kc:var(--violet)"><div class="kl">AI Decisions</div><div class="kv">{total:,}</div><div class="ks">audit log</div></div>'
        f'<div class="kpi" style="--kc:var(--green)"><div class="kl">Join</div><div class="kv">{yes:,}</div><div class="ks">decision = yes</div></div>'
        f'<div class="kpi" style="--kc:var(--red)"><div class="kl">Skip</div><div class="kv">{no:,}</div><div class="ks">decision = no</div></div>'
        f'<div class="kpi" style="--kc:var(--cyan)"><div class="kl">Avg Confidence</div><div class="kv">{avg_conf}%</div><div class="ks">model score</div></div>'
        f'<div class="kpi" style="--kc:var(--blue)"><div class="kl">PO Win Rate</div><div class="kv">{win_rate}%</div><div class="ks">from po_history</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Row 1: Decision bar | Price Status donut | GC vs TM bar
    c1, c2, c3 = st.columns([1, 1, 1])

    with c1:
        st.markdown('<div class="sec" style="margin-bottom:6px;">AI Decision Distribution</div>', unsafe_allow_html=True)
        if total and HAS_PLOTLY:
            fig = go.Figure(go.Bar(
                x=["Join", "Skip", "Review"],
                y=[yes, no, maybe],
                marker_color=["#00ff88", "#ff1744", "#ffb300"],
                marker_line_width=0,
            ))
            fig.update_layout(**_CHART_BASE, height=200,
                xaxis=dict(showgrid=False, color="#2e4460"),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,.04)", color="#2e4460"),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        elif total:
            chart_df = pd.DataFrame([
                {"decision": "Join", "count": yes},
                {"decision": "Skip", "count": no},
                {"decision": "Review", "count": maybe},
            ]).set_index("decision")
            st.bar_chart(chart_df, use_container_width=True)
        else:
            st.caption("No AI classification data yet.")

    with c2:
        st.markdown('<div class="sec" style="margin-bottom:6px;">Price Status</div>', unsafe_allow_html=True)
        status = prod_stats.get("status", {})
        db_total = sum(status.values())
        if db_total and HAS_PLOTLY:
            labels, values, colors = [], [], []
            for k, col in [("ok", "#00ff88"), ("expired", "#ffb300"), ("none", "#1e3350")]:
                v = status.get(k, 0)
                if v:
                    labels.append(k.upper())
                    values.append(v)
                    colors.append(col)
            fig = go.Figure(go.Pie(
                labels=labels, values=values,
                marker=dict(colors=colors, line=dict(color="#040608", width=2)),
                textinfo="percent+label",
                textfont=dict(size=9, family="IBM Plex Mono", color="#c8dff5"),
                hole=0.55,
            ))
            fig.update_layout(**_CHART_BASE, height=200, showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        elif db_total:
            st.caption(f"ok={status.get('ok',0)} / expired={status.get('expired',0)} / none={status.get('none',0)}")
        else:
            st.caption("No product data in DB.")

    with c3:
        st.markdown('<div class="sec" style="margin-bottom:6px;">GC vs TM</div>', unsafe_allow_html=True)
        types = prod_stats.get("types", {})
        gc = types.get("gc", 0)
        tm = types.get("tm", 0)
        if (gc or tm) and HAS_PLOTLY:
            fig = go.Figure(go.Bar(
                x=["GC", "TM"],
                y=[gc, tm],
                marker_color=["#3ab8fb", "#ff8c42"],
                marker_line_width=0,
                width=0.5,
            ))
            fig.update_layout(**_CHART_BASE, height=200,
                xaxis=dict(showgrid=False, color="#2e4460"),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,.04)", color="#2e4460"),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.caption(f"GC={gc}  TM={tm}" if (gc or tm) else "No product type data.")

    # Row 2: Confidence histogram | Override stats card
    c4, c5 = st.columns([2, 1])

    with c4:
        st.markdown('<div class="sec" style="margin-bottom:6px;">AI Confidence Distribution</div>', unsafe_allow_html=True)
        if class_rows and HAS_PLOTLY:
            confs = [float(r.get("confidence", 0) or 0) * 100 for r in class_rows]
            fig = go.Figure(go.Histogram(
                x=confs, nbinsx=20,
                marker_color="#8b7cf8",
                marker_line_color="#040608",
                marker_line_width=1,
            ))
            fig.update_layout(**_CHART_BASE, height=180,
                xaxis=dict(title="Confidence %", showgrid=False, color="#2e4460", range=[0, 100]),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,.04)", color="#2e4460"),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.caption("No confidence data.")

    with c5:
        st.markdown('<div class="sec" style="margin-bottom:6px;">Override Stats</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="card" style="--ca:var(--violet);">'
            f'<div class="card-top"></div>'
            f'<div class="clabel">Manual Override</div>'
            f'<div style="font-size:11px;color:var(--t2);line-height:1.9;">'
            f'<div>Total AI: <span style="color:var(--cyan);font-weight:700;">{total:,}</span></div>'
            f'<div>Overrides: <span style="color:var(--violet);font-weight:700;">{len(override_rows):,}</span></div>'
            f'<div>Ratio: <span style="color:var(--yellow);font-weight:700;">{override_ratio:.1f}%</span></div>'
            f'<div>PO records: <span style="color:var(--blue);font-weight:700;">{len(po_rows):,}</span></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    # Top Makers horizontal bar
    makers = prod_stats.get("makers", [])
    if makers and HAS_PLOTLY:
        st.markdown('<div class="sec" style="margin:10px 0 6px;">Top Makers by Product Count</div>', unsafe_allow_html=True)
        mk_names = [m[0] for m in makers]
        mk_vals  = [m[1] for m in makers]
        fig = go.Figure(go.Bar(
            x=mk_vals, y=mk_names, orientation="h",
            marker_color=[_NEON[i % len(_NEON)] for i in range(len(mk_names))],
            marker_line_width=0,
        ))
        fig.update_layout(**_CHART_BASE, height=max(160, len(mk_names) * 26),
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,.04)", color="#2e4460"),
            yaxis=dict(showgrid=False, color="#6e8aaa", autorange="reversed"),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # Recent Audit table
    st.markdown('<div class="sec" style="margin:10px 0 6px;">Recent Audit Events</div>', unsafe_allow_html=True)
    if audit_rows:
        tbl = pd.DataFrame(audit_rows[-80:]).fillna("")
        cols = [c for c in ["ts", "action", "order_id", "decision", "confidence", "original", "new", "reason"] if c in tbl.columns]
        st.dataframe(tbl[cols] if cols else tbl, use_container_width=True, height=280)
    else:
        st.info("Chua co du lieu audit log.")

# Tab: System
# ---------------------------------------------------------------------------
def _render_system_tab():
    from modules.folder_browser import (
        get_onedrive_root,
        scan_folders,
        get_watched_folders,
        add_watch_folder,
        remove_watch_folder,
        get_recent_events,
        get_visible_folders,
    )

    cfg = _load_config()
    db = _get_db_path()
    libre = cfg.get("libreoffice_path", "")
    libre_alt = cfg.get("libreoffice_path_alt", "")

    def _ex(p):
        return os.path.exists(p) if p else False

    libre_ok = _ex(libre) or _ex(libre_alt)

    col1, col2 = st.columns(2)
    with col1:
        od_root = get_onedrive_root() or ""
        rows_html = (
            f'<div style="display:flex;justify-content:space-between;font-size:8px;padding:4px 0;border-bottom:1px solid var(--b1);">'
            f'<span style="color:var(--t2)">OneDrive root</span>'
            f'<span style="color:var(--t3);font-size:7px;max-width:240px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{od_root or "Not found"}</span>'
            f'<span class="tag {"tg-ok" if od_root else "tg-no"}">{"OK" if od_root else "MISS"}</span></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:8px;padding:4px 0;border-bottom:1px solid var(--b1);">'
            f'<span style="color:var(--t2)">OneDrive guard</span><span class="tag tg-ok">READ-ONLY</span></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:8px;padding:4px 0;border-bottom:1px solid var(--b1);">'
            f'<span style="color:var(--t2)">bsmq.db</span><span class="tag {"tg-ok" if _ex(db) else "tg-no"}">{"OK" if _ex(db) else "MISSING"}</span></div>'
            f'<div style="display:flex;justify-content:space-between;font-size:8px;padding:4px 0;">'
            f'<span style="color:var(--t2)">LibreOffice</span><span class="tag {"tg-ok" if libre_ok else "tg-exp"}">{"FOUND" if libre_ok else "NOT FOUND"}</span></div>'
        )
        st.markdown(
            f'<div class="card" style="--ca:var(--green);margin-bottom:8px;">'
            f'<div class="card-top"></div><div class="clabel">Paths and Guard</div>'
            f'<div style="display:flex;flex-direction:column;gap:2px;">{rows_html}</div></div>',
            unsafe_allow_html=True,
        )

    with col2:
        try:
            from modules.database import get_db_stats, init_sqlite_db

            init_sqlite_db(db)
            s = get_db_stats(db)
            db_html = (
                f'<div style="display:flex;justify-content:space-between;font-size:8px;padding:4px 0;border-bottom:1px solid var(--b1);"><span style="color:var(--t2)">Total products</span><span style="color:var(--green)">{s["total"]:,}</span></div>'
                f'<div style="display:flex;justify-content:space-between;font-size:8px;padding:4px 0;border-bottom:1px solid var(--b1);"><span style="color:var(--t2)">GC / TM</span><span style="color:var(--t2)">{s.get("gc",0):,} / {s.get("tm",0):,}</span></div>'
                f'<div style="display:flex;justify-content:space-between;font-size:8px;padding:4px 0;"><span style="color:var(--t2)">Query latency</span><span style="color:var(--cyan)">{s["query_ms"]}ms</span></div>'
            )
        except Exception as e:
            db_html = f'<div style="font-size:8px;color:var(--red)">DB Error: {e}</div>'

        st.markdown(
            f'<div class="card" style="--ca:var(--cyan);margin-bottom:8px;">'
            f'<div class="card-top"></div><div class="clabel">Database Health</div>'
            f'<div style="display:flex;flex-direction:column;gap:2px;">{db_html}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="sec" style="margin:12px 0 8px;">Folder Monitor - OneDrive Watchdog</div>', unsafe_allow_html=True)

    od_root = get_onedrive_root()
    if not od_root:
        st.warning("Cannot find OneDrive root. Check environment variables OneDriveCommercial / OneDrive.")
    else:
        from modules.watchdog_sync import manual_sync

        watched = get_watched_folders()
        active_paths = {w.get("path", "").rstrip("/\\") for w in watched if w.get("active", True)}

        if "sys_folders" not in st.session_state:
            st.session_state.sys_folders = []
        if "tree_expanded" not in st.session_state:
            st.session_state.tree_expanded = set()

        c1, c2, c3, c4 = st.columns([1.1, 1.1, 2, 2])
        with c1:
            if st.button("Scan folders", key="sys_scan_btn", use_container_width=True):
                with st.spinner("Scanning OneDrive..."):
                    st.session_state.sys_folders = scan_folders(od_root, max_depth=6, max_count=800)
        with c2:
            if st.button("Sync now", key="sys_sync_btn", use_container_width=True):
                with st.spinner("Manual syncing watched folders..."):
                    ssum = manual_sync(max_files=12000)
                st.success(
                    f"Synced {ssum['folders']} folder(s) | +{ssum['created']} new | "
                    f"{ssum['modified']} modified | {ssum['deleted']} deleted"
                )

        with c3:
            sys_filter = st.text_input(
                "Search folder",
                value=st.session_state.get("sys_filter", ""),
                key="sys_filter",
                label_visibility="collapsed",
                placeholder="Filter by folder name...",
            )

        with c4:
            show_mode = st.selectbox(
                "Show mode",
                ["All", "Watched only", "Has Excel"],
                key="sys_show_mode",
                label_visibility="collapsed",
            )

        folders = st.session_state.sys_folders
        st.markdown(
            f'<div style="font-size:8px;color:var(--t3);margin:4px 0 8px 0;">Root: <span style="color:var(--text)">{od_root}</span> | Scanned: {len(folders)} folders</div>',
            unsafe_allow_html=True,
        )

        if not folders:
            st.info("Click 'Scan folders' to build the folder tree.")
        else:
            expanded = st.session_state.tree_expanded
            q = (sys_filter or "").strip().lower()
            by_parent = {}
            by_path = {}
            for f in folders:
                by_parent.setdefault(f.get("parent", ""), []).append(f)
                by_path[f.get("path", "")] = f

            for p in by_parent:
                by_parent[p] = sorted(by_parent[p], key=lambda x: x.get("name", "").lower())

            def _self_match(folder: dict) -> bool:
                path = folder.get("path", "")
                is_watch = path.rstrip("/\\") in active_paths
                has_xl = bool(folder.get("has_xlsx", False))
                name = folder.get("name", "").lower()
                if show_mode == "Watched only" and not is_watch:
                    return False
                if show_mode == "Has Excel" and not has_xl:
                    return False
                if q and q not in name:
                    return False
                return True

            match_cache = {}

            def _subtree_match(path: str) -> bool:
                if path in match_cache:
                    return match_cache[path]
                folder = by_path.get(path, {})
                ok = _self_match(folder)
                for ch in by_parent.get(path, []):
                    if _subtree_match(ch.get("path", "")):
                        ok = True
                        break
                match_cache[path] = ok
                return ok

            matched_nodes = [f for f in folders if _subtree_match(f.get("path", ""))]
            st.markdown(
                f'<div style="font-size:8px;color:var(--t3);margin-bottom:6px;">Showing {len(matched_nodes)} / {len(folders)} folders</div>',
                unsafe_allow_html=True,
            )

            show_files_col = any(int(f.get("file_count", 0) or 0) > 0 for f in matched_nodes)
            show_excel_col = any(bool(f.get("has_xlsx", False)) for f in matched_nodes)
            widths = [0.55, 0.8, 5.4]
            if show_files_col:
                widths.append(0.9)
            if show_excel_col:
                widths.append(0.9)

            hdr = st.columns(widths)
            hdr[0].markdown('<div style="font-size:7px;color:var(--t3);letter-spacing:1px;">OPEN</div>', unsafe_allow_html=True)
            hdr[1].markdown('<div style="font-size:7px;color:var(--t3);letter-spacing:1px;">WATCH</div>', unsafe_allow_html=True)
            hdr[2].markdown('<div style="font-size:7px;color:var(--t3);letter-spacing:1px;">FOLDER TREE</div>', unsafe_allow_html=True)
            hidx = 3
            if show_files_col:
                hdr[hidx].markdown('<div style="font-size:7px;color:var(--t3);letter-spacing:1px;">FILES</div>', unsafe_allow_html=True)
                hidx += 1
            if show_excel_col:
                hdr[hidx].markdown('<div style="font-size:7px;color:var(--t3);letter-spacing:1px;">EXCEL</div>', unsafe_allow_html=True)

            def _render_children(parent_path: str, depth: int) -> None:
                children = by_parent.get(parent_path, [])
                for folder in children:
                    path = folder.get("path", "")
                    if not _subtree_match(path):
                        continue
                    name = folder.get("name", "")
                    has_kids = len(by_parent.get(path, [])) > 0
                    is_open = path in expanded
                    is_watch = path.rstrip("/\\") in active_paths
                    has_xl = bool(folder.get("has_xlsx", False))
                    files_n = int(folder.get("file_count", 0) or 0)
                    arrow = "▾" if is_open else "▸"

                    row = st.columns(widths)
                    with row[0]:
                        if has_kids:
                            exp_chk = st.checkbox("", value=is_open, key=f"exp_{path}", label_visibility="collapsed")
                            if exp_chk != is_open:
                                if exp_chk:
                                    expanded.add(path)
                                else:
                                    expanded.discard(path)
                                st.session_state.tree_expanded = expanded
                                st.rerun()
                        else:
                            st.markdown('<div style="padding-top:7px;color:var(--t4);font-size:8px;text-align:center;">·</div>', unsafe_allow_html=True)

                    with row[1]:
                        watch_chk = st.checkbox("", value=is_watch, key=f"watch_{path}", label_visibility="collapsed")
                        if watch_chk != is_watch:
                            if watch_chk:
                                add_watch_folder(path, name)
                            else:
                                for w in watched:
                                    if w.get("path", "").rstrip("/\\") == path.rstrip("/\\"):
                                        remove_watch_folder(w.get("id", -1))
                                        break
                            st.rerun()

                    with row[2]:
                        color = "var(--green)" if is_watch else "var(--text)"
                        prefix_html = f'<span style="color:var(--t3)">{arrow}</span> ' if has_kids else ""
                        st.markdown(
                            f'<div style="padding-left:{depth * 16}px;padding-top:6px;font-size:11px;color:{color};line-height:1.2;">'
                            f'{prefix_html}{name}'
                            f'</div>',
                            unsafe_allow_html=True,
                        )

                    cidx = 3
                    if show_files_col:
                        with row[cidx]:
                            st.markdown(
                                f'<div style="padding-top:6px;font-size:10px;color:var(--t2);text-align:right;">{files_n}</div>',
                                unsafe_allow_html=True,
                            )
                        cidx += 1
                    if show_excel_col:
                        with row[cidx]:
                            xl = '<span class="tag tg-ok">xlsx</span>' if has_xl else ""
                            st.markdown(f'<div style="padding-top:4px;">{xl}</div>', unsafe_allow_html=True)

                    if has_kids and is_open:
                        _render_children(path, depth + 1)

            _render_children(od_root.rstrip("/\\"), 0)

        events = get_recent_events(limit=50)
        watched_live = [w for w in watched if w.get("active", True)]
        with st.sidebar:
            st.markdown("### Live Watched")
            if watched_live:
                for wf in watched_live:
                    fid = wf.get("id")
                    nm = wf.get("label") or os.path.basename(wf.get("path", ""))
                    cnt = sum(1 for e in events if e.get("folder_id") == fid and e.get("is_processed", 0) == 0)
                    st.markdown(f"- `{nm}`  |  new: **{cnt}**")
            else:
                st.caption("No watched folder.")

        st.markdown('<div class="sec" style="margin:12px 0 6px;">Recent Events</div>', unsafe_allow_html=True)
        if st.button("Refresh events", key="sys_refresh_events", use_container_width=False):
            st.rerun()

        if events:
            le_html = ""
            for ev in events:
                etype = ev.get("event_type", "")
                fname = os.path.basename(ev.get("file_path", ""))
                ts = str(ev.get("created_at", ""))
                hms = ts[11:19] if len(ts) >= 19 else ts
                cls = "ok" if etype == "created" else "warn" if etype == "modified" else "err"
                tag = "t-ok" if etype == "created" else "t-w" if etype == "modified" else "t-e"
                tag_l = "NEW" if etype == "created" else "MOD" if etype == "modified" else "DEL"
                le_html += (
                    f'<div class="le {cls}">'
                    f'<span class="le-t">{hms}</span>'
                    f'<span class="le-tag {tag}">{tag_l}</span>'
                    f'<span class="le-msg">{fname}</span>'
                    f'</div>'
                )
            st.markdown(f'<div class="log-wrap" style="max-height:320px;">{le_html}</div>', unsafe_allow_html=True)
        else:
            st.info("No events yet. Enable watch on at least one folder.")

    st.markdown('<div class="sec" style="margin:12px 0 6px;">Module Health</div>', unsafe_allow_html=True)

    modules_to_check = [
        ("tools.tool1_autofill.engine", "Tool 1 Auto Fill Engine", "T1"),
        ("tools.tool3_pofilter.engine", "Tool 3 PO Filter Engine", "T3"),
        ("modules.database", "Database (SQLite+FTS5)", "DB"),
        ("modules.data_validation", "Data Validation", "VAL"),
        ("modules.watchdog_sync", "Watchdog Sync", "WD"),
        ("modules.ai_classifier", "AI Classifier (Gemini)", "AI"),
        ("modules.notifications", "Notifications (Windows)", "NTF"),
        ("modules.folder_browser", "Folder Browser", "FDR"),
    ]
    rows = ""
    for mod_path, label, icon in modules_to_check:
        try:
            __import__(mod_path)
            dot = "dg"
            badge = "mok"
            badge_txt = "OK"
        except Exception as e:
            dot = "dr"
            badge = "merr"
            badge_txt = str(e)[:35]
        rows += (
            f'<div class="mod"><div class="md {dot}"></div>'
            f'<div style="font-size:9px;color:var(--t3);flex-shrink:0;width:26px;">{icon}</div>'
            f'<div class="mn">{label}</div>'
            f'<div class="mt {badge}">{badge_txt}</div></div>'
        )
    st.markdown(f'<div style="display:flex;flex-direction:column;gap:3px;">{rows}</div>', unsafe_allow_html=True)

    with st.expander("Config (config.json)"):
        st.json(cfg)

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
def _render_footer():
    try:
        from modules.database import get_db_stats
        db = _get_db_path()
        s = get_db_stats(db)
        db_lbl = f"SQLite {s['total']:,}"
    except Exception:
        db_lbl = "SQLite -"

    st.markdown(
        f'<div class="v5-footer">'
        f'<div class="fi"><span style="color:var(--green)">*</span>OneDrive READ-ONLY</div>'
        f'<div class="fi"><span style="color:var(--cyan)">*</span>{db_lbl}</div>'
        f'<div class="fi"><span style="color:var(--violet)">*</span>Gemini Keys</div>'
        f'<div class="fi"><span style="color:var(--yellow)">*</span>Watchdog</div>'
        f'<div style="margin-left:auto;font-size:7px;color:var(--t3);">BSMQ v5.0 | AMA Bac Ninh</div>'
        f'</div>',
        unsafe_allow_html=True
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # Inject v5 CSS
    st.markdown(V5_CSS, unsafe_allow_html=True)

    # Header bar
    _render_header()

    # Tabs styled to match v5 nav
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "OPS CENTER",
        "BIDDING",
        "DATABASE",
        "ANALYTICS",
        "SYSTEM",
        "PO TRACKER",
        "MARKET",
    ])

    # Best-effort auto-jump to Ops Center tab when queue is pushed from Tool 2.
    if st.session_state.get("t1_auto_import_queue", False):
        components.html(
            """
            <script>
            const t = window.parent.document.querySelectorAll('[data-baseweb="tab"]');
            if (t && t.length > 0) { t[0].click(); }
            </script>
            """,
            height=0,
            width=0,
        )

    with tab1:
        _render_ops_center()

    with tab2:
        _render_bidding_tab()

    with tab3:
        _render_database_tab()

    with tab4:
        _render_analytics_tab()

    with tab5:
        _render_system_tab()

    with tab6:
        try:
            from tools.tool4_po_tracker.app import render_po_tracker_tab
            render_po_tracker_tab()
        except Exception as e:
            import traceback
            st.error(f"PO Tracker lỗi: {e}")
            st.code(traceback.format_exc())

    with tab7:
        try:
            from tools.tool5_market_search.app import render_tool5_tab
            from modules.config import get_config as _get_cfg
            render_tool5_tab(db_path=_get_cfg().get("db_path", "./bsmq.db"))
        except Exception as e:
            import traceback
            st.error(f"Market Search lỗi: {e}")
            st.code(traceback.format_exc())

    # Footer
    _render_footer()


if __name__ == "__main__" or True:
    main()


