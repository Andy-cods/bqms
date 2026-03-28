"""
tools/tool1_autofill/app.py
Tool 1 - Auto Fill UI layer.
Called by main app.py via: render_tool1_tab()
"""

import os
import sys
import json
import subprocess
from datetime import datetime

import streamlit as st

# ---------------------------------------------------------------------------
# Engine import - pure logic, no Streamlit
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tools.tool1_autofill.engine import (
    parse_bc_bqms,
    match_images_to_orders,
    run_auto_fill_job,
    run_gia_cong_l2_job,
    load_config,
    save_config,
    set_log_callback,
    is_deadline_urgent,
)

# ---------------------------------------------------------------------------
# Design system CSS - BSMQ Dashboard v4
# ---------------------------------------------------------------------------

TOOL1_CSS = """
<style>
/* Tool 1: Order cards (v5 vars) */
.bsmq-card {
  background: var(--s2);
  border-left: 3px solid var(--b2);
  border-radius: var(--r);
  padding: 10px 14px;
  margin: 4px 0;
  font-family: var(--mono);
  font-size: 12px;
  position: relative;
}
.bsmq-card.tm     { border-left-color: var(--orange); }
.bsmq-card.gc     { border-left-color: var(--blue); opacity: 0.7; }
.bsmq-card.urgent { background: var(--ra); border-left-color: var(--red); }

/* Badges */
.badge { display:inline-block; padding:2px 7px; border-radius:2px; font-size:8px; font-weight:600; letter-spacing:.5px; }
.badge-tm  { background:var(--oa); color:var(--orange); border:1px solid var(--orange)44; }
.badge-gc  { background:var(--ba); color:var(--blue);   border:1px solid var(--blue)44; }
.badge-ok  { background:var(--ga); color:var(--green);  border:1px solid var(--gb); }
.badge-urg { background:var(--ra); color:var(--red);    border:1px solid var(--rb); }

/* Section header */
.section-hdr {
  font-size:7px; letter-spacing:2.5px; text-transform:uppercase;
  color:var(--t3); display:flex; align-items:center; gap:6px;
  margin:12px 0 6px 0;
}
.section-hdr::after { content:''; flex:1; height:1px; background:var(--b1); }

/* Log entries */
.log-entry { font-family:var(--mono); font-size:9px; padding:3px 7px; margin:1px 0; border-radius:2px; display:flex; align-items:baseline; gap:5px; border-left:2px solid transparent; }
.log-ok    { color:var(--green);  border-left-color:var(--green);  background:var(--ga); }
.log-warn  { color:var(--yellow); border-left-color:var(--yellow); background:var(--ya); }
.log-error { color:var(--red);    border-left-color:var(--red);    background:var(--ra); }
.log-info  { color:var(--t2);     border-left-color:var(--b2);     background:transparent; }

/* Result cards */
.result-ok   { background:var(--ga); border:1px solid var(--gb); border-radius:var(--r); padding:10px 14px; margin:4px 0; }
.result-err  { background:var(--ra); border:1px solid var(--rb); border-radius:var(--r); padding:10px 14px; margin:4px 0; }
.result-skip { background:var(--s2); border:1px solid var(--b1); border-radius:var(--r); padding:10px 14px; margin:4px 0; }

/* KPI pill */
.kpi-pill {
  display:inline-flex; align-items:center; gap:6px;
  background:var(--s1); border:1px solid var(--b1);
  border-radius:20px; padding:4px 12px;
  font-family:var(--mono); font-size:11px; color:var(--text); margin:2px;
}
</style>
"""


def inject_tool1_css():
    st.markdown(TOOL1_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

def _init_state():
    defaults = {
        "t1_config":       None,
        "t1_orders":       [],
        "t1_selected":     set(),
        "t1_images_map":   {},
        "t1_logs":         [],
        "t1_results":      [],
        "t1_step":         1,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _get_config():
    if st.session_state.t1_config is None:
        st.session_state.t1_config = load_config()
    return st.session_state.t1_config


def _add_log(msg: str, level: str = "info"):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.t1_logs.append({"time": ts, "msg": msg, "level": level})


def _render_logs(logs: list, max_show: int = 20):
    for entry in reversed(logs[-max_show:]):
        lvl = entry.get("level", "info")
        css = {"ok": "log-ok", "warn": "log-warn", "error": "log-error"}.get(lvl, "log-info")
        st.markdown(
            f'<div class="log-entry {css}">[{entry["time"]}] {entry["msg"]}</div>',
            unsafe_allow_html=True
        )


def _tool2_item_to_t1_order(item: dict) -> dict:
    rfq = str(item.get("rfq_no", "") or "")
    bqms = str(item.get("bqms_code", "") or "")
    spec = str(item.get("spec", "") or "")
    qty = item.get("qty_forecast")
    try:
        qty = int(float(qty)) if qty not in (None, "") else ""
    except Exception:
        pass
    return {
        "id": f"{rfq}_{bqms}_{spec[:16]}",
        "don_hang": rfq,
        "bqms": bqms,
        "spec": spec,
        "short_name": spec[:80],
        "loai_hang": "TM",
        "maker": str(item.get("maker", "") or ""),
        "mark": "",
        "don_vi": "EA",
        "so_luong": qty,
        "han_bg": "",
        "deadline_dt": None,
        "is_urgent": False,
        "ghi_chu": str(item.get("note", "") or ""),
    }


# ---------------------------------------------------------------------------
# Order card HTML
# ---------------------------------------------------------------------------

def _order_card_html(order: dict) -> str:
    loai     = order.get("loai_hang", "TM")
    is_gc    = loai == "GC"
    urgent   = order.get("is_urgent", False)
    card_cls = "gc" if is_gc else ("urgent" if urgent else "tm")
    badge_cls = "badge-gc" if is_gc else "badge-tm"

    urgent_badge = (
        '<span class="badge badge-urg" style="margin-left:6px">URGENT</span>'
        if urgent else ""
    )

    return f"""
    <div class="bsmq-card {card_cls}">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <span style="color:#dde8f8;font-weight:600;font-size:13px">
          {order.get('don_hang','')} - {order.get('short_name','') or order.get('spec','')[:40]}
        </span>
        <span>
          <span class="badge {badge_cls}">{loai}</span>
          {urgent_badge}
        </span>
      </div>
      <div style="color:#7a90b0;margin-top:4px">
        BQMS: <span style="color:#22d3ee">{order.get('bqms','')}</span>
        - Maker: {order.get('maker','')}
        - Qty: {order.get('so_luong','')} {order.get('don_vi','EA')}
        - Deadline: {order.get('han_bg','')}
      </div>
    </div>
    """


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------

def render_tool1_tab():
    inject_tool1_css()
    _init_state()

    # Wire engine logger to session state
    set_log_callback(_add_log)

    cfg = _get_config()
    # Bridge from Tool 2 (BQMS Analytics) -> Tool 1 (Auto Fill)
    queue = st.session_state.get("t2_quote_queue", [])
    prefill = st.session_state.get("t2_prefill_order")
    auto_import = bool(st.session_state.get("t1_auto_import_queue", False))
    if queue or prefill:
        st.markdown('<div class="section-hdr">Bridge from Tool 2</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        with c1:
            st.caption(f"Rows queued from Tool 2: {len(queue)}")
        with c2:
            if st.button("Import queue", key="t1_import_queue", use_container_width=True):
                incoming = queue[:] if queue else [prefill]
                incoming = [x for x in incoming if isinstance(x, dict)]
                mapped = [_tool2_item_to_t1_order(x) for x in incoming]
                by_id = {o.get("id"): o for o in st.session_state.t1_orders}
                for o in mapped:
                    by_id[o["id"]] = o
                st.session_state.t1_orders = list(by_id.values())
                st.session_state.t1_selected = {
                    o["id"] for o in st.session_state.t1_orders if o.get("loai_hang") == "TM"
                }
                if "t2_queue_log" not in st.session_state:
                    st.session_state.t2_queue_log = []
                for x in incoming:
                    st.session_state.t2_queue_log.append(
                        {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "stage": "imported", "rfq_no": x.get("rfq_no",""), "bqms_code": x.get("bqms_code","")}
                    )
                st.toast(f"Imported {len(mapped)} rows from Tool 2", icon="✅")
                st.rerun()
        with c3:
            if st.button("Import + Run", key="t1_import_run_queue", use_container_width=True):
                incoming = queue[:] if queue else [prefill]
                incoming = [x for x in incoming if isinstance(x, dict)]
                mapped = [_tool2_item_to_t1_order(x) for x in incoming]
                by_id = {o.get("id"): o for o in st.session_state.t1_orders}
                for o in mapped:
                    by_id[o["id"]] = o
                st.session_state.t1_orders = list(by_id.values())
                st.session_state.t1_selected = {
                    o["id"] for o in mapped if o.get("loai_hang") == "TM"
                }
                cfg_run = {**cfg, "on_conflict": "version"}
                if "t2_queue_log" not in st.session_state:
                    st.session_state.t2_queue_log = []
                for x in incoming:
                    st.session_state.t2_queue_log.append(
                        {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "stage": "generated", "rfq_no": x.get("rfq_no",""), "bqms_code": x.get("bqms_code","")}
                    )
                _run_jobs([o for o in st.session_state.t1_orders if o["id"] in st.session_state.t1_selected], "split", False, cfg_run)
                st.rerun()
        with c4:
            if st.button("Clear queue", key="t1_clear_t2_queue", use_container_width=True):
                st.session_state.t2_quote_queue = []
                st.session_state.t2_prefill_order = None
                st.session_state.t1_auto_import_queue = False
                st.rerun()

        st.markdown("---")

        if auto_import and queue:
            st.session_state.t1_auto_import_queue = False
            incoming = [x for x in queue if isinstance(x, dict)]
            mapped = [_tool2_item_to_t1_order(x) for x in incoming]
            by_id = {o.get("id"): o for o in st.session_state.t1_orders}
            for o in mapped:
                by_id[o["id"]] = o
            st.session_state.t1_orders = list(by_id.values())
            st.session_state.t1_selected = {o["id"] for o in mapped if o.get("loai_hang") == "TM"}

    st.markdown('<div class="section-hdr">Gia Cong L2 Automation</div>', unsafe_allow_html=True)
    with st.expander("Run Gia Cong L2/L3 flow", expanded=False):
        gc1, gc2 = st.columns([2, 2])
        with gc1:
            rfq_root = st.text_input(
                "RFQ root folder",
                value=st.session_state.get(
                    "t1_gc_rfq_root",
                    os.path.join(os.path.expanduser("~"), "OneDrive - SONG CHAU CO., LTD", "Puplic", "BQMS", "RFQ"),
                ),
                key="t1_gc_rfq_root",
            )
        with gc2:
            history_file = st.text_input(
                "BQMS history file",
                value=st.session_state.get("t1_gc_history_file", ""),
                key="t1_gc_history_file",
                placeholder=os.path.join(os.path.expanduser("~"), "OneDrive - SONG CHAU CO., LTD", "Puplic", "BQMS", "Thong ke hoi hang BQMS.xlsx"),
            )

        cgc1, cgc2 = st.columns([2, 1])
        with cgc1:
            rfq_input = st.text_input(
                "RFQ No.",
                value=st.session_state.get("t1_gc_rfq_no", ""),
                key="t1_gc_rfq_no",
                placeholder="QT26029114",
            )
        with cgc2:
            manual_timeout = st.number_input(
                "Manual timeout (sec)",
                min_value=60,
                max_value=900,
                value=300,
                step=30,
                key="t1_gc_timeout",
            )

        pg = st.progress(0)
        pg_txt = st.empty()
        run_gc = st.button("Run Gia Cong L2", type="primary", key="t1_run_gc_l2", use_container_width=True)

        if run_gc:
            def _on_gc_progress(step, total, msg):
                pct = int((step / max(total, 1)) * 100)
                pg.progress(pct)
                pg_txt.caption(f"[{step}/{total}] {msg}")

            with st.spinner("Running Gia Cong L2 flow..."):
                r = run_gia_cong_l2_job(
                    rfq_no=rfq_input,
                    history_path=history_file,
                    rfq_root_dir=rfq_root,
                    manual_timeout_sec=int(manual_timeout),
                    progress_callback=_on_gc_progress,
                )
            pg.progress(100 if r.get("success") else 0)
            if r.get("success"):
                st.success(
                    f"Done. Round L{r.get('level')} at: {r.get('output_dir')}"
                )
            else:
                st.error("Gia Cong L2 failed.")
            if r.get("warnings"):
                st.warning("\n".join(str(x) for x in r.get("warnings", [])))
            if r.get("errors"):
                st.error("\n".join(str(x) for x in r.get("errors", [])))
            if r.get("files"):
                st.dataframe(
                    [{"file": x} for x in r.get("files", [])],
                    use_container_width=True,
                    height=160,
                )

    st.markdown("---")

    # Step 1: Config check
    with st.expander("Path Configuration", expanded=not bool(cfg.get("rfq_folder"))):
        st.markdown('<div class="section-hdr">Output Folder (RFQ Folder)</div>', unsafe_allow_html=True)
        new_path = st.text_input(
            "RFQ folder path",
            value=cfg.get("rfq_folder", ""),
            placeholder="C:\\Users\\...\\OneDrive\\BQMS\\RFQ\\RFQ 2026\\THANG 2",
            label_visibility="collapsed"
        )
        if new_path != cfg.get("rfq_folder", ""):
            cfg["rfq_folder"] = new_path
            save_config(cfg)
            st.session_state.t1_config = cfg
            st.toast("Saved RFQ path", icon="✅")

        exists = os.path.isdir(cfg.get("rfq_folder", ""))
        if cfg.get("rfq_folder"):
            if exists:
                st.success("✅ Folder exists")
            else:
                st.warning("⚠️ Folder does not exist - output will be saved to ./outputs/")

    st.markdown("---")

    # Step 2: Load BC BQMS by path
    st.markdown('<div class="section-hdr">Step 1 - Select BC BQMS file</div>', unsafe_allow_html=True)
    path_col, btn_col = st.columns([5, 1])
    with path_col:
        bc_path = st.text_input(
            "BC BQMS file path",
            value=st.session_state.get("t1_bc_path", ""),
            placeholder="C:\\Users\\...\\BQMS\\BC BQMS month X.xlsx",
            label_visibility="collapsed",
            key="t1_bc_path_input",
        )
    with btn_col:
        load_clicked = st.button("Load file", key="t1_bc_load", use_container_width=True)

    if load_clicked and bc_path:
        if not os.path.isfile(bc_path):
            st.error(f"File not found: {bc_path}")
        else:
            with st.spinner("Reading file..."):
                with open(bc_path, "rb") as fh:
                    file_bytes = fh.read()
                orders = parse_bc_bqms(file_bytes)
            if orders:
                st.session_state.t1_orders = orders
                st.session_state.t1_bc_path = bc_path
                st.session_state.t1_selected = {
                    o["id"] for o in orders if o.get("loai_hang") == "TM"
                }
                st.toast(f"Loaded {len(orders)} orders", icon="✅")
            else:
                st.warning("No orders found in this file.")

    orders = st.session_state.t1_orders

    if orders:
        tm_cnt  = sum(1 for o in orders if o.get("loai_hang") == "TM")
        gc_cnt  = sum(1 for o in orders if o.get("loai_hang") == "GC")
        urg_cnt = sum(1 for o in orders if o.get("is_urgent"))

        # KPI pills
        st.markdown(
            f'<div style="display:flex;flex-wrap:wrap;gap:4px;margin:8px 0">'
            f'<span class="kpi-pill">Total: <b>{len(orders)}</b></span>'
            f'<span class="kpi-pill" style="color:#fb923c">TM: <b>{tm_cnt}</b></span>'
            f'<span class="kpi-pill" style="color:#38bdf8">GC: <b>{gc_cnt}</b></span>'
            f'<span class="kpi-pill" style="color:#f43f5e">Urgent: <b>{urg_cnt}</b></span>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown("---")

    # Step 3: Select orders
    if orders:
        st.markdown('<div class="section-hdr">Step 2 - Select orders</div>', unsafe_allow_html=True)

        col_search, col_filter = st.columns([3, 1])
        search_q  = col_search.text_input("Search", placeholder="Product, BQMS, RFQ...",
                                           label_visibility="collapsed", key="t1_search")
        type_filter = col_filter.selectbox("Filter", ["All", "TM", "GC", "Urgent"],
                                            label_visibility="collapsed", key="t1_filter")

        def _matches(o):
            if type_filter == "TM" and o.get("loai_hang") != "TM":
                return False
            if type_filter == "GC" and o.get("loai_hang") != "GC":
                return False
            if type_filter == "Urgent" and not o.get("is_urgent"):
                return False
            if search_q:
                haystack = " ".join([
                    o.get("don_hang", ""), o.get("bqms", ""),
                    o.get("spec", ""), o.get("short_name", ""),
                    o.get("maker", "")
                ]).lower()
                if search_q.lower() not in haystack:
                    return False
            return True

        filtered = [o for o in orders if _matches(o)]

        col_all, col_none = st.columns([1, 1])
        if col_all.button("Select all TM", key="t1_sel_all"):
            st.session_state.t1_selected = {o["id"] for o in filtered if o.get("loai_hang") == "TM"}
            st.rerun()
        if col_none.button("Clear selection", key="t1_sel_none"):
            st.session_state.t1_selected = set()
            st.rerun()

        for i, order in enumerate(filtered):
            st.markdown(_order_card_html(order), unsafe_allow_html=True)
            is_gc    = order.get("loai_hang") == "GC"
            cur_sel  = order["id"] in st.session_state.t1_selected
            label    = f"{order['don_hang']} - {order.get('short_name','') or order.get('bqms','')}"
            new_sel  = st.checkbox(
                label,
                value=cur_sel,
                disabled=is_gc,
                key=f"t1_chk_{i}",
                help="GC order is not supported yet" if is_gc else None,
            )
            if new_sel != cur_sel:
                if new_sel:
                    st.session_state.t1_selected.add(order["id"])
                else:
                    st.session_state.t1_selected.discard(order["id"])

        st.markdown("---")

    # Step 4: Upload images
    if orders:
        st.markdown('<div class="section-hdr">Step 3 - Upload images (optional)</div>', unsafe_allow_html=True)
        uploaded_imgs = st.file_uploader(
            "Upload PNG/JPG images (filename contains BQMS code)",
            type=["png", "jpg", "jpeg"],
            accept_multiple_files=True,
            key="t1_img_upload",
            label_visibility="collapsed"
        )
        if uploaded_imgs:
            selected_orders = [o for o in orders if o["id"] in st.session_state.t1_selected]
            img_map = match_images_to_orders(uploaded_imgs, selected_orders or orders)
            st.session_state.t1_images_map = img_map

            # Show match table
            if img_map:
                rows_html = "".join(
                    f"<tr><td style='padding:4px 8px;color:#22d3ee'>{code}</td>"
                    f"<td style='padding:4px 8px;color:#0fe87a'>Matched</td></tr>"
                    for code in img_map
                )
                st.markdown(
                    f"<table style='font-family:IBM Plex Mono,monospace;font-size:12px;"
                    f"color:#7a90b0;width:100%'>"
                    f"<tr><th style='text-align:left;padding:4px 8px'>BQMS Code</th>"
                    f"<th style='text-align:left;padding:4px 8px'>Status</th></tr>"
                    f"{rows_html}</table>",
                    unsafe_allow_html=True
                )

        st.markdown("---")

    # Step 5: Review and run
    if orders:
        st.markdown('<div class="section-hdr">Step 4 - Review and run</div>', unsafe_allow_html=True)
        selected_orders = [o for o in orders if o["id"] in st.session_state.t1_selected]

        if not selected_orders:
            st.info("No order selected. Select TM orders in Step 2.")
        else:
            # Summary table
            summary_rows = "".join(
                f"<tr><td style='padding:4px 8px'>{i+1}</td>"
                f"<td style='padding:4px 8px;color:#22d3ee'>{o['don_hang']}</td>"
                f"<td style='padding:4px 8px'>{o.get('loai_hang','')}</td>"
                f"<td style='padding:4px 8px;color:#7a90b0'>{o.get('bqms','')}</td>"
                f"<td style='padding:4px 8px'>{o.get('so_luong','')} {o.get('don_vi','EA')}</td>"
                f"<td style='padding:4px 8px;color:#fbbf24'>{o.get('han_bg','')}</td></tr>"
                for i, o in enumerate(selected_orders)
            )
            st.markdown(
                f"<table style='font-family:IBM Plex Mono,monospace;font-size:12px;"
                f"color:#dde8f8;width:100%;border-collapse:collapse'>"
                f"<tr style='color:#7a90b0;border-bottom:1px solid #1c2840'>"
                f"<th style='text-align:left;padding:4px 8px'>#</th>"
                f"<th style='text-align:left;padding:4px 8px'>RFQ No.</th>"
                f"<th style='text-align:left;padding:4px 8px'>Type</th>"
                f"<th style='text-align:left;padding:4px 8px'>BQMS</th>"
                f"<th style='text-align:left;padding:4px 8px'>Qty</th>"
                f"<th style='text-align:left;padding:4px 8px'>Deadline</th></tr>"
                f"{summary_rows}</table>",
                unsafe_allow_html=True
            )

            st.markdown(
                '<p style="color:#fbbf24;font-size:12px;font-family:IBM Plex Mono,monospace">'
                'Price fields are left blank and can be filled manually after files are generated.</p>',
                unsafe_allow_html=True
            )

            col_opts1, col_opts2 = st.columns(2)
            merge_mode   = col_opts1.radio("File mode",
                ["1 order = 1 file", "Merge by RFQ"], key="t1_merge_mode")
            on_conflict  = col_opts2.radio("If output folder exists",
                ["Create _v2 (safe)", "Overwrite", "Skip"], key="t1_conflict")
            export_pdf_f = st.checkbox("Export PDF (requires LibreOffice)", key="t1_pdf")

            conflict_map = {
                "Create _v2 (safe)": "version",
                "Overwrite": "overwrite",
                "Skip": "skip"
            }
            cfg_run = {**cfg,
                       "on_conflict": conflict_map.get(on_conflict, "version")}

            if st.button("Run Auto Fill", type="primary", key="t1_run_btn"):
                _run_jobs(selected_orders, merge_mode, export_pdf_f, cfg_run)

    # Logs
    if st.session_state.t1_logs:
        st.markdown("---")
        st.markdown('<div class="section-hdr">Log</div>', unsafe_allow_html=True)
        with st.container(height=200):
            _render_logs(st.session_state.t1_logs)

    # Results
    if st.session_state.t1_results:
        _render_results(st.session_state.t1_results)


# ---------------------------------------------------------------------------
# Job runner
# ---------------------------------------------------------------------------

def _build_groups(selected_orders: list, merge_mode: str) -> list:
    """Group orders: 'split' = one group per product, 'merge' = group by RFQ."""
    if "Merge" in merge_mode:
        groups = {}
        for o in selected_orders:
            key = o["don_hang"]
            groups.setdefault(key, []).append(o)
        return list(groups.values())
    else:
        return [[o] for o in selected_orders]


def _run_jobs(selected_orders: list, merge_mode: str, export_pdf_f: bool, cfg: dict):
    groups  = _build_groups(selected_orders, merge_mode)
    results = []
    prog    = st.progress(0)
    status  = st.empty()

    for i, group in enumerate(groups):
        rfq_no = group[0].get("don_hang", "?")
        status.markdown(
            f'<div style="font-family:IBM Plex Mono,monospace;color:#7a90b0;font-size:12px">'
            f'Processing {rfq_no} ({i+1}/{len(groups)})</div>',
            unsafe_allow_html=True
        )

        step_placeholder = st.empty()

        def on_progress(step, total, msg, _rfq=rfq_no):
            step_placeholder.markdown(
                f'<div class="log-entry log-info"> [{step}/{total}] {msg}</div>',
                unsafe_allow_html=True
            )

        cfg_job = {**cfg, "export_pdf": export_pdf_f}
        result  = run_auto_fill_job(group, cfg_job, st.session_state.t1_images_map, on_progress)
        results.append(result)
        prog.progress((i + 1) / len(groups))

    status.empty()
    st.session_state.t1_results = results
    if "t2_queue_log" not in st.session_state:
        st.session_state.t2_queue_log = []
    for r in results:
        st.session_state.t2_queue_log.append(
            {
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "stage": "done" if r.get("success") else "error",
                "rfq_no": r.get("rfq_no", ""),
                "bqms_code": "",
            }
        )
    _add_log(f"Completed {len(groups)} orders - {sum(r['success'] for r in results)} success.", "ok")
    st.rerun()


def _render_results(results: list):
    st.markdown("---")
    st.markdown('<div class="section-hdr">Result</div>', unsafe_allow_html=True)

    output_dirs = set()
    for r in results:
        ok  = r.get("success", False)
        css = "result-ok" if ok else "result-err"
        ico = "OK" if ok else "FAIL"
        err_html = ""
        if r.get("errors"):
            err_html = "<br>".join(
                f'<span style="color:#f43f5e">{e}</span>' for e in r["errors"]
            )

        files_html = "".join(
            f'<div style="color:#7a90b0;margin-top:2px">FILE: {os.path.basename(f)}</div>'
            for f in r.get("files", [])
        )

        st.markdown(
            f'<div class="{css}">'
            f'<span style="font-weight:600;color:#dde8f8">{ico} {r["rfq_no"]}</span>'
            f'{files_html}{err_html}'
            f'</div>',
            unsafe_allow_html=True
        )

        if r.get("output_dir") and os.path.isdir(r["output_dir"]):
            output_dirs.add(r["output_dir"])

    if output_dirs:
        first_dir = sorted(output_dirs)[0]
        parent    = os.path.dirname(first_dir)
        if st.button("Open outputs folder", key="t1_open_folder"):
            try:
                os.startfile(parent)
            except Exception:
                st.info(f"Open folder: `{parent}`")

