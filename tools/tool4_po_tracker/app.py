"""
Tool 4 — PO Tracker UI  (v3 redesign)
Tab "PO TRACKER" trong BSMQ main app.
"""

import logging
import os
from datetime import datetime

import streamlit as st

logger = logging.getLogger(__name__)

# ── Palette (warm minimalist) ──────────────────────────────────────────────────
_BG     = "#F2EDE6"
_S1     = "#FAF8F5"
_S2     = "#EDE8E0"
_S3     = "#E5DFD6"
_TEXT   = "#3D3530"
_T2     = "#6B5F56"
_T3     = "#B5AA9A"
_ACC    = "#8B6F5C"
_ACC2   = "#A08070"
_GREEN  = "#7A9E7E"
_BLUE   = "#5C85B8"
_RED    = "#B85C5C"
_YEL    = "#C4955A"
_BORDER = "rgba(61,53,48,0.10)"
_BORDER2= "rgba(61,53,48,0.18)"

# ── Session state keys ─────────────────────────────────────────────────────────
_K = {
    "status":       "po4_status",
    "rows":         "po4_rows",
    "log":          "po4_log",
    "last_run":     "po4_last_run",
    "pdf_result":   "po4_pdf_result",
    "excel_result": "po4_excel_result",
    "pdf_map":      "po4_pdf_map",
    "err_msg":      "po4_err_msg",
}


def _init():
    defaults = {
        _K["status"]:       "idle",
        _K["rows"]:         [],
        _K["log"]:          [],
        _K["last_run"]:     "",
        _K["pdf_result"]:   {},
        _K["excel_result"]: {},
        _K["pdf_map"]:      {},
        _K["err_msg"]:      "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ── API-based operations (requests, no Selenium) ───────────────────────────────

def _op_api_scan(holder: dict):
    """Full API-based scan: login → fetch PO list → write to Excel. No Selenium."""
    try:
        from tools.tool4_po_tracker.bsmq_api_client import (
            login_api, fetch_po_list, write_api_pos_to_excel, EXCEL_PATH
        )
        log = holder["log"]
        ts = lambda: datetime.now().strftime("%H:%M:%S")

        log.append((ts(), "info", "Đăng nhập BQMS API..."))
        session = login_api()
        if not session:
            log.append((ts(), "error", "Login thất bại"))
            holder["error"] = "Login failed"; return
        log.append((ts(), "ok", "Đăng nhập thành công"))

        log.append((ts(), "info", "Đang tải danh sách PO tháng này..."))
        rows = fetch_po_list(session)
        log.append((ts(), "ok", f"Lấy được {len(rows)} PO"))
        holder["rows"] = rows
        if not rows: return

        log.append((ts(), "info", "Ghi PO mới vào Excel..."))
        xl = write_api_pos_to_excel(rows, EXCEL_PATH)
        log.append((ts(), "ok",
            f"Excel: +{xl['added']} dòng mới · skip {xl['skipped']} · lỗi {xl['errors']}"))
        holder["excel_result"] = xl

        if xl["errors"] > 0:
            holder["error"] = f"Có {xl['errors']} lỗi khi ghi Excel"
        else:
            log.append((ts(), "ok", "═══ HOÀN THÀNH ═══"))
    except Exception as e:
        holder["log"].append((datetime.now().strftime("%H:%M:%S"), "error", str(e)))
        holder["error"] = str(e)


def _op_api_fetch_only(holder: dict):
    """Login + fetch PO list only (no Excel write)."""
    try:
        from tools.tool4_po_tracker.bsmq_api_client import login_api, fetch_po_list
        log = holder["log"]
        ts = lambda: datetime.now().strftime("%H:%M:%S")

        log.append((ts(), "info", "Đăng nhập BQMS API..."))
        session = login_api()
        if not session:
            log.append((ts(), "error", "Login thất bại"))
            holder["error"] = "Login failed"
            return
        log.append((ts(), "ok", "Đăng nhập thành công"))

        log.append((ts(), "info", "Đang tải danh sách PO..."))
        rows = fetch_po_list(session)
        log.append((ts(), "ok", f"Lấy được {len(rows)} PO"))
        holder["rows"] = rows
    except Exception as e:
        holder["log"].append((datetime.now().strftime("%H:%M:%S"), "error", str(e)))
        holder["error"] = str(e)


# ── Selenium operations (legacy) ───────────────────────────────────────────────

def _op_full_flow(headless: bool, holder: dict):
    try:
        from tools.tool4_po_tracker.engine import (
            create_driver, login_with_retry, handle_post_login_popups,
            navigate_to_po_receipt_mro, scrape_all_pages,
            download_po_pdfs, parse_po_pdf, write_to_excel,
            PO_TEMP_DOWNLOAD, PO_BASE_DIR, _get_po_month_folder,
        )
        log = holder["log"]
        ts = lambda: datetime.now().strftime("%H:%M:%S")

        log.append((ts(), "info", "Khởi động Chrome..."))
        driver = create_driver(headless=headless, download_dir=PO_TEMP_DOWNLOAD)
        try:
            log.append((ts(), "info", "Đăng nhập Samsung BQMS..."))
            res = login_with_retry(driver)
            if not res["success"]:
                log.append((ts(), "error", f"Login thất bại: {res['message']}"))
                holder["error"] = res["message"]; return

            log.append((ts(), "ok", f"Đăng nhập thành công"))
            handle_post_login_popups(driver)

            log.append((ts(), "info", "Điều hướng MRO > P/O Receipt..."))
            if not navigate_to_po_receipt_mro(driver):
                log.append((ts(), "error", "Không tìm thấy menu")); holder["error"] = "Nav failed"; return
            log.append((ts(), "ok", "Điều hướng thành công"))

            log.append((ts(), "info", "Scraping bảng PO..."))
            rows = scrape_all_pages(driver)
            log.append((ts(), "ok", f"Scraped {len(rows)} PO rows"))
            holder["rows"] = rows
            if not rows: return

            log.append((ts(), "info", f"Đang tải {len(rows)} PDF..."))
            pdf_res = download_po_pdfs(driver, rows)
            log.append((ts(), "ok", f"PDF: tải {pdf_res['downloaded']} · skip {pdf_res['skipped']} · lỗi {pdf_res['errors']}"))
            holder["pdf_result"] = pdf_res

            log.append((ts(), "info", "Parse PDF..."))
            pdf_map = {}
            for r in {r.get("col_5","").strip() for r in rows}:
                if not r: continue
                date_str = next((x.get("col_4","") for x in rows if x.get("col_5","").strip()==r), "")
                folder = _get_po_month_folder(date_str, PO_BASE_DIR)
                if os.path.isdir(folder):
                    for f in os.listdir(folder):
                        if r in f and f.lower().endswith(".pdf"):
                            parsed = parse_po_pdf(os.path.join(folder, f))
                            pdf_map[r] = parsed
                            log.append((ts(), "info", f"  {r}: {len(parsed.get('products',[]))} sản phẩm"))
                            break
            log.append((ts(), "ok", f"Parsed {len(pdf_map)} file PDF"))
            holder["pdf_map"] = pdf_map

            log.append((ts(), "info", "Ghi Excel..."))
            xl = write_to_excel(rows, pdf_map)
            log.append((ts(), "ok", f"Excel: +{xl['added']} dòng, skip {xl['skipped']}"))
            holder["excel_result"] = xl
            log.append((ts(), "ok", "═══ HOÀN THÀNH ═══"))
        finally:
            driver.quit()
    except Exception as e:
        holder["log"].append((datetime.now().strftime("%H:%M:%S"), "error", str(e)))
        holder["error"] = str(e)


def _op_scrape(headless: bool, holder: dict):
    try:
        from tools.tool4_po_tracker.engine import (
            create_driver, login_with_retry, handle_post_login_popups,
            navigate_to_po_receipt_mro, scrape_all_pages,
        )
        log = holder["log"]
        ts = lambda: datetime.now().strftime("%H:%M:%S")
        log.append((ts(), "info", "Khởi động Chrome...")); driver = create_driver(headless=headless)
        try:
            log.append((ts(), "info", "Đăng nhập..."))
            res = login_with_retry(driver)
            if not res["success"]:
                log.append((ts(), "error", res["message"])); holder["error"] = res["message"]; return
            log.append((ts(), "ok", "OK"))
            handle_post_login_popups(driver)
            log.append((ts(), "info", "Điều hướng..."))
            if not navigate_to_po_receipt_mro(driver):
                log.append((ts(), "error", "Failed")); holder["error"] = "Nav"; return
            log.append((ts(), "info", "Scraping..."))
            rows = scrape_all_pages(driver)
            log.append((ts(), "ok", f"Scraped {len(rows)} rows"))
            holder["rows"] = rows
        finally:
            driver.quit()
    except Exception as e:
        holder["log"].append((datetime.now().strftime("%H:%M:%S"), "error", str(e)))
        holder["error"] = str(e)


def _op_parse_excel(holder: dict):
    try:
        from tools.tool4_po_tracker.engine import parse_po_pdf, write_to_excel, PO_BASE_DIR, _get_po_month_folder
        log = holder["log"]; ts = lambda: datetime.now().strftime("%H:%M:%S")
        rows = holder.get("rows", [])
        if not rows: log.append((ts(),"error","Chưa có dữ liệu — scrape trước")); holder["error"]="No rows"; return
        pdf_map = {}
        for po_no in {r.get("col_5","").strip() for r in rows}:
            if not po_no: continue
            date_str = next((x.get("col_4","") for x in rows if x.get("col_5","").strip()==po_no), "")
            folder = _get_po_month_folder(date_str, PO_BASE_DIR)
            if os.path.isdir(folder):
                for f in os.listdir(folder):
                    if po_no in f and f.lower().endswith(".pdf"):
                        parsed = parse_po_pdf(os.path.join(folder, f))
                        pdf_map[po_no] = parsed
                        log.append((ts(),"info",f"  {po_no}: {len(parsed.get('products',[]))} sản phẩm"))
                        break
        log.append((ts(),"ok",f"Parsed {len(pdf_map)} PDF"))
        holder["pdf_map"] = pdf_map
        xl = write_to_excel(rows, pdf_map)
        log.append((ts(),"ok",f"Excel: +{xl['added']} dòng"))
        holder["excel_result"] = xl
    except Exception as e:
        holder["log"].append((datetime.now().strftime("%H:%M:%S"),"error",str(e)))
        holder["error"] = str(e)


def _run(op_fn, *args):
    """Run operation synchronously on the Streamlit main thread.

    Threading + session_state writes from background threads are not supported
    in Streamlit — results get silently dropped. Run synchronously instead;
    Streamlit shows its own "Running..." spinner in the top-right corner.
    """
    holder = {"log": [], "rows": list(st.session_state.get(_K["rows"], []))}
    st.session_state[_K["status"]] = "running"
    st.session_state[_K["err_msg"]] = ""

    # Run directly on main thread
    op_fn(*args, holder)

    # Merge results
    st.session_state[_K["log"]] = holder["log"]
    for k in ("rows", "pdf_result", "excel_result", "pdf_map"):
        if k in holder:
            st.session_state[_K[k]] = holder[k]
    st.session_state[_K["status"]] = "error" if "error" in holder else "done"
    if "error" in holder:
        st.session_state[_K["err_msg"]] = holder["error"]
    st.session_state[_K["last_run"]] = datetime.now().strftime("%d/%m %H:%M")


# ── UI helpers ─────────────────────────────────────────────────────────────────

def _inject_css():
    """Inject shared CSS for hover effects and animations."""
    st.markdown(f"""
    <style>
    /* KPI card hover */
    .po-kpi-card {{
        background: {_S1};
        border: 1px solid {_BORDER};
        border-radius: 12px;
        padding: 20px 16px 16px;
        text-align: center;
        transition: box-shadow 0.18s ease, transform 0.18s ease, border-color 0.18s ease;
        cursor: default;
    }}
    .po-kpi-card:hover {{
        box-shadow: 0 6px 24px rgba(139,111,92,0.13);
        transform: translateY(-2px);
        border-color: {_BORDER2};
    }}
    /* Running pulse animation */
    @keyframes po-pulse {{
        0%   {{ opacity: 1; }}
        50%  {{ opacity: 0.45; }}
        100% {{ opacity: 1; }}
    }}
    .po-running-dot {{
        animation: po-pulse 1.4s ease-in-out infinite;
        display: inline-block;
    }}
    /* Log scrollbar */
    .po-log-wrap::-webkit-scrollbar {{
        width: 5px;
    }}
    .po-log-wrap::-webkit-scrollbar-track {{
        background: {_S2};
        border-radius: 4px;
    }}
    .po-log-wrap::-webkit-scrollbar-thumb {{
        background: {_T3};
        border-radius: 4px;
    }}
    /* Table row hover */
    .po-tbl-row:hover td {{
        background: {_S2} !important;
    }}
    </style>
    """, unsafe_allow_html=True)


def _badge(status: str) -> str:
    """Render a status badge — returns raw HTML string."""
    cfg = {
        "idle":    (_T3,    False,  "Chờ"),
        "running": (_YEL,   True,   "Đang chạy"),
        "done":    (_GREEN, False,  "Hoàn thành"),
        "error":   (_RED,   False,  "Lỗi"),
    }
    color, pulsing, label = cfg.get(status, (_T3, False, status))
    dot_cls = ' class="po-running-dot"' if pulsing else ""
    return (
        f'<span style="display:inline-flex;align-items:center;gap:5px;'
        f'background:{color}1a;border:1px solid {color}44;'
        f'border-radius:20px;padding:3px 10px 3px 8px;">'
        f'<span{dot_cls} style="color:{color};font-size:9px;">●</span>'
        f'<span style="color:{color};font-size:11px;font-weight:600;'
        f'letter-spacing:.02em;">{label}</span>'
        f'</span>'
    )


def _kpi_card(icon: str, val: str, label: str, color: str, sub: str = "") -> str:
    """Return HTML for a single KPI card with icon + big number + label."""
    sub_html = (
        f'<div style="font-size:10px;color:{_T3};margin-top:2px;">{sub}</div>'
        if sub else ""
    )
    return f"""
    <div class="po-kpi-card">
        <div style="font-size:22px;margin-bottom:6px;line-height:1;">{icon}</div>
        <div style="font-size:30px;font-weight:700;color:{color};
                    line-height:1;letter-spacing:-.02em;">{val}</div>
        <div style="font-size:10px;color:{_T3};margin-top:6px;
                    text-transform:uppercase;letter-spacing:.07em;
                    font-weight:600;">{label}</div>
        {sub_html}
    </div>"""


def _section_label(title: str):
    """Render an uppercase section label."""
    st.markdown(
        f'<div style="font-size:10px;font-weight:700;color:{_T3};'
        f'text-transform:uppercase;letter-spacing:.10em;'
        f'margin:24px 0 10px;padding-left:2px;">{title}</div>',
        unsafe_allow_html=True,
    )


def _divider():
    st.markdown(
        f'<div style="height:1px;background:{_BORDER};margin:20px 0;"></div>',
        unsafe_allow_html=True,
    )


def _log_row(ts: str, level: str, msg: str) -> str:
    """Return HTML for one log line."""
    color = {"ok": _GREEN, "error": _RED, "info": _T2}.get(level, _TEXT)
    icon  = {"ok": "✓", "error": "✗", "info": "·"}.get(level, "·")
    # Bold the key tokens for ok/error lines
    weight = "600" if level in ("ok", "error") else "400"
    return (
        f'<div style="display:flex;gap:10px;padding:5px 0;'
        f'border-bottom:1px solid {_BORDER};">'
        f'<span style="color:{_T3};font-size:10px;min-width:54px;'
        f'font-family:monospace;padding-top:1px;flex-shrink:0;">{ts}</span>'
        f'<span style="color:{color};font-size:11px;min-width:12px;'
        f'padding-top:1px;flex-shrink:0;">{icon}</span>'
        f'<span style="color:{_TEXT};font-size:11px;flex:1;'
        f'font-weight:{weight};word-break:break-word;">{msg}</span>'
        f'</div>'
    )


def _po_table_html(display: list) -> str:
    """Render the PO list as a styled HTML table."""
    header_cells = ""
    for col in ("Ngày PO", "Số PO", "Số QT", "BQMS", "PDF ✓", "Sản phẩm"):
        header_cells += (
            f'<th style="padding:8px 12px;text-align:left;font-size:10px;'
            f'font-weight:700;color:{_T3};text-transform:uppercase;'
            f'letter-spacing:.07em;border-bottom:2px solid {_BORDER2};'
            f'white-space:nowrap;">{col}</th>'
        )

    rows_html = ""
    for i, r in enumerate(display):
        bg = _S1 if i % 2 == 0 else _S2
        pdf_val  = r["PDF"]
        pdf_col  = _GREEN if pdf_val == "✓" else _T3
        pdf_w    = "700"  if pdf_val == "✓" else "400"
        cells = ""
        for key in ("Ngày PO", "Số PO", "Số QT", "BQMS"):
            cells += (
                f'<td style="padding:7px 12px;font-size:12px;color:{_TEXT};'
                f'border-bottom:1px solid {_BORDER};white-space:nowrap;'
                f'background:{bg};">{r[key]}</td>'
            )
        # PDF column — color-coded
        cells += (
            f'<td style="padding:7px 12px;font-size:12px;color:{pdf_col};'
            f'font-weight:{pdf_w};border-bottom:1px solid {_BORDER};'
            f'text-align:center;background:{bg};">{pdf_val}</td>'
        )
        # Sản phẩm column
        sp_val = r["SP"]
        cells += (
            f'<td style="padding:7px 12px;font-size:12px;color:{_BLUE if sp_val != "—" else _T3};'
            f'border-bottom:1px solid {_BORDER};text-align:center;'
            f'background:{bg};">{sp_val}</td>'
        )
        rows_html += f'<tr class="po-tbl-row">{cells}</tr>'

    return f"""
    <div style="background:{_S1};border:1px solid {_BORDER};
                border-radius:12px;overflow:hidden;
                box-shadow:0 1px 6px rgba(61,53,48,0.06);">
        <div style="overflow-x:auto;">
            <table style="width:100%;border-collapse:collapse;">
                <thead><tr>{header_cells}</tr></thead>
                <tbody>{rows_html}</tbody>
            </table>
        </div>
    </div>"""


# ── Main render ────────────────────────────────────────────────────────────────

def render_po_tracker_tab():
    _init()
    _inject_css()

    status  = st.session_state[_K["status"]]
    rows    = st.session_state[_K["rows"]]
    logs    = st.session_state[_K["log"]]
    pdf_r   = st.session_state[_K["pdf_result"]]
    xl_r    = st.session_state[_K["excel_result"]]
    last    = st.session_state[_K["last_run"]]
    err     = st.session_state[_K["err_msg"]]
    running = status == "running"

    # ── 1. PAGE HEADER ────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="
        background:{_S1};
        border:1px solid {_BORDER};
        border-radius:14px;
        overflow:hidden;
        margin-bottom:22px;
        box-shadow:0 2px 12px rgba(61,53,48,0.07);
    ">
        <!-- top accent gradient line -->
        <div style="height:3px;background:linear-gradient(90deg,{_ACC} 0%,{_ACC2} 55%,{_S3} 100%);"></div>
        <div style="
            padding:18px 24px 16px;
            display:flex;
            align-items:center;
            justify-content:space-between;
        ">
            <div>
                <div style="font-size:22px;font-weight:700;color:{_TEXT};
                            letter-spacing:-.025em;line-height:1.15;">
                    PO Tracker
                </div>
                <div style="font-size:12px;color:{_T2};margin-top:4px;
                            display:flex;align-items:center;gap:6px;">
                    Samsung BQMS Vendor Portal
                    <span style="color:{_BORDER2};">|</span>
                    <span style="color:{_ACC};font-weight:500;">sec-bqms.com</span>
                </div>
            </div>
            <div style="text-align:right;">
                {_badge(status)}
                <div style="font-size:11px;color:{_T3};margin-top:6px;">
                    Lần cuối:&nbsp;{last if last else "—"}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Error alert
    if status == "error" and err:
        st.markdown(f"""
        <div style="background:{_RED}14;border:1px solid {_RED}44;
                    border-left:3px solid {_RED};border-radius:8px;
                    padding:10px 16px;margin-bottom:18px;
                    display:flex;align-items:flex-start;gap:10px;">
            <span style="color:{_RED};font-size:14px;flex-shrink:0;margin-top:1px;">✗</span>
            <div>
                <div style="font-size:12px;font-weight:700;color:{_RED};
                            margin-bottom:2px;">Có lỗi xảy ra</div>
                <div style="font-size:12px;color:{_T2};">{err}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── 2. KPI CARDS ─────────────────────────────────────────────────────────
    # Support both API rows (PO_NO key) and Selenium rows (col_5 key)
    def _get_po_no(r):
        return r.get("PO_NO") or r.get("col_5", "")

    n_po   = len({_get_po_no(r) for r in rows if _get_po_no(r)})
    n_dl   = pdf_r.get("downloaded", 0) if pdf_r else 0
    n_add  = xl_r.get("added", 0) if xl_r else 0
    n_skip = xl_r.get("skipped", 0) if xl_r else 0

    kpi_data = [
        ("📦", str(n_po)    if rows   else "—", "Số PO",      _TEXT,  "purchase orders"),
        ("📄", str(n_dl)    if pdf_r  else "—", "PDF tải về", _BLUE,  "files downloaded"),
        ("✏️", f"+{n_add}"  if xl_r   else "—", "Excel dòng", _GREEN, "rows written"),
        ("⏭️", str(n_skip)  if xl_r   else "—", "Đã có sẵn",  _T3,   "rows skipped"),
    ]

    cols = st.columns(4)
    for col, (icon, val, label, color, sub) in zip(cols, kpi_data):
        with col:
            st.markdown(_kpi_card(icon, val, label, color, sub), unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    _divider()

    # ── 3. CONTROL PANEL ─────────────────────────────────────────────────────
    _section_label("Điều khiển")

    # Container card
    st.markdown(f"""
    <div style="background:{_S1};border:1px solid {_BORDER};
                border-radius:12px;padding:18px 20px 8px;
                box-shadow:0 1px 6px rgba(61,53,48,0.05);
                margin-bottom:4px;">
        <div style="font-size:11px;font-weight:700;color:{_T2};
                    margin-bottom:14px;letter-spacing:.02em;">
            Tùy chọn &amp; thao tác
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Headless checkbox
    head_col, _ = st.columns([1, 3])
    with head_col:
        headless = st.checkbox(
            "🔘 Headless mode",
            value=False,
            disabled=running,
            help="Ẩn cửa sổ Chrome khi chạy",
        )

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # Action buttons — 4 columns
    b1, b2, b3, b4 = st.columns(4)

    with b1:
        if st.button(
            "▶  Full Flow",
            use_container_width=True,
            type="primary",
            disabled=running,
            help="Login Chrome → Scrape PO → Tải PDF → Parse → Ghi Excel",
        ):
            _run(_op_full_flow, headless)
            st.rerun()

    with b2:
        if st.button(
            "🔍  Login & Scrape",
            use_container_width=True,
            disabled=running,
            help="Login Chrome, vào trang PO, scrape danh sách (chưa tải PDF)",
        ):
            _run(_op_scrape, headless)
            st.rerun()

    with b3:
        if st.button(
            "📄  Parse → Excel",
            use_container_width=True,
            disabled=(running or not rows),
            help="Parse PDF đã có sẵn rồi ghi Excel",
        ):
            _run(_op_parse_excel)
            st.rerun()

    with b4:
        if st.button(
            "🗑  Xóa log",
            use_container_width=True,
            disabled=running,
            help="Xóa toàn bộ log hiển thị",
        ):
            st.session_state[_K["log"]] = []
            st.session_state[_K["status"]] = "idle"
            st.rerun()

    # Running state banner
    if running:
        st.markdown(f"""
        <div style="background:{_YEL}12;border:1px solid {_YEL}44;
                    border-radius:8px;padding:10px 16px;margin-top:14px;
                    display:flex;align-items:center;gap:10px;">
            <span class="po-running-dot"
                  style="color:{_YEL};font-size:16px;line-height:1;">⏳</span>
            <div>
                <div style="font-size:12px;font-weight:700;color:{_YEL};">
                    Đang xử lý...</div>
                <div style="font-size:11px;color:{_T2};margin-top:1px;">
                    Trang sẽ tự làm mới sau khi hoàn thành.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── 4. PO DATA TABLE ─────────────────────────────────────────────────────
    if rows:
        try:
            _divider()
            _section_label(f"Danh sách PO  ·  {len(rows)} mục")

            # Detect API rows vs Selenium rows
            is_api = bool(rows and "PO_NO" in rows[0])

            if is_api:
                from datetime import date as _date
                display = []
                for r in rows[:100]:  # cap at 100 for performance
                    po_no = r.get("PO_NO", "")
                    # Convert Unix ms timestamp
                    ts_val = r.get("PO_CONFIRM_DT")
                    try:
                        date_str = _date.fromtimestamp(int(ts_val)/1000).strftime("%d/%m/%Y") if ts_val else ""
                    except Exception:
                        date_str = str(ts_val or "")
                    qt_no   = r.get("REQ_NO", "")
                    bqms    = r.get("CIS_CODE", "") or r.get("ITEM_CODE", "")
                    spec    = r.get("SPECIFICATION", "")[:40] + ("…" if len(r.get("SPECIFICATION","")) > 40 else "")
                    recv    = r.get("RECEIVER_NAME", "")
                    mail    = recv.split(":")[-1].strip() if ":" in recv else ""
                    display.append({
                        "Ngày PO": date_str,
                        "Số PO":   po_no,
                        "Số QT":   qt_no,
                        "BQMS":    bqms,
                        "PDF":     "—",        # API flow doesn't download PDFs
                        "SP":      mail or spec or "—",
                    })
            else:
                from tools.tool4_po_tracker.engine import (
                    PO_BASE_DIR, _get_po_month_folder, _pdf_already_downloaded,
                )
                pdf_map = st.session_state[_K["pdf_map"]]
                display = []
                for r in rows[:100]:
                    po_no    = r.get("col_5", "")
                    date_str = r.get("col_4", "")
                    qt_no    = r.get("col_7", "")
                    bqms     = r.get("col_21", "")
                    folder   = _get_po_month_folder(date_str, PO_BASE_DIR)
                    has_pdf  = _pdf_already_downloaded(po_no, folder)
                    parsed   = pdf_map.get(po_no)
                    n_prod   = len(parsed.get("products", [])) if parsed else 0
                    display.append({
                        "Ngày PO": date_str,
                        "Số PO":   po_no,
                        "Số QT":   qt_no,
                        "BQMS":    bqms,
                        "PDF":     "✓" if has_pdf else "—",
                        "SP":      str(n_prod) if n_prod else "—",
                    })

            st.markdown(_po_table_html(display), unsafe_allow_html=True)

        except Exception as ex:
            st.warning(f"Bảng PO: {ex}")

    # ── 5. ACTIVITY LOG ───────────────────────────────────────────────────────
    if logs:
        _divider()
        _section_label(f"Log hoạt động  ·  {len(logs)} dòng")

        rows_html = "".join(
            _log_row(ts_val, lvl, msg)
            for ts_val, lvl, msg in reversed(logs)
        )
        st.markdown(f"""
        <div class="po-log-wrap" style="
            background:{_S1};
            border:1px solid {_BORDER};
            border-radius:12px;
            padding:12px 16px;
            max-height:300px;
            overflow-y:auto;
            font-family:'Cascadia Code','SF Mono','Menlo',monospace;
            box-shadow:inset 0 2px 6px rgba(61,53,48,0.04);
        ">
            {rows_html}
        </div>
        """, unsafe_allow_html=True)

    # ── 6. EMPTY STATE ────────────────────────────────────────────────────────
    if not rows and not logs:
        st.markdown(f"""
        <div style="
            background:{_S1};
            border:1px dashed {_BORDER2};
            border-radius:16px;
            padding:56px 32px 52px;
            text-align:center;
            margin-top:12px;
            box-shadow:0 1px 4px rgba(61,53,48,0.04);
        ">
            <div style="font-size:44px;margin-bottom:16px;
                        filter:grayscale(20%);">📋</div>
            <div style="font-size:17px;font-weight:700;color:{_TEXT};
                        margin-bottom:10px;letter-spacing:-.01em;">
                Chưa có dữ liệu PO
            </div>
            <div style="font-size:13px;color:{_T2};
                        max-width:400px;margin:0 auto;line-height:1.6;">
                Nhấn <b style="color:{_TEXT};">▶ Full Flow</b> để tự động
                login Chrome, scrape PO, tải PDF và ghi Excel.<br>
                Hoặc <b style="color:{_TEXT};">🔍 Login &amp; Scrape</b>
                để xem danh sách PO trước, rồi nhấn 📄 Parse → Excel.
            </div>
            <div style="margin-top:20px;font-size:11px;color:{_T3};">
                ↑ Sử dụng bảng điều khiển phía trên để bắt đầu
            </div>
        </div>
        """, unsafe_allow_html=True)
