import glob
import json
import os
import re
import shutil
import sqlite3
import time
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st

from tools.tool1_autofill.engine import run_gia_cong_prepare_job, run_gia_cong_export_job
from tools.tool2_pricetracker.engine import load_bqms_analytics


def _norm_rfq(v: str) -> str:
    s = (v or "").strip().upper()
    return re.sub(r"[^A-Z0-9]", "", s)


@st.cache_data(show_spinner=False)
def _all_rfq_folders(rfq_root: str) -> list[str]:
    out = []
    if not os.path.isdir(rfq_root):
        return out
    for y in _rfq_year_dirs(rfq_root):
        for m in _month_dirs(y):
            out.extend(_rfq_folders(m))
    return out


def _find_rfq_candidates(rfq_root: str, rfq_no: str, limit: int = 30) -> list[str]:
    key = _norm_rfq(rfq_no)
    if not key:
        return []
    cands = []
    for p in _all_rfq_folders(rfq_root):
        base = os.path.basename(p)
        bkey = _norm_rfq(base)
        if key in bkey:
            score = 2 if bkey.startswith(key) else 1
            try:
                mt = os.path.getmtime(p)
            except Exception:
                mt = 0
            cands.append((score, mt, p))
    cands.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [x[2] for x in cands[:limit]]


def _inject_step_css():
    st.markdown(
        """
        <style>
        .wiz-wrap { margin: 8px 0 12px; }
        .wiz-steps { display:flex; gap:12px; align-items:center; }
        .wiz-step {
          position: relative;
          flex: 1;
          min-height: 44px;
          display:flex;
          align-items:center;
          justify-content:center;
          font-family: var(--sans);
          font-size: 13px;
          font-weight: 700;
          color: #e8f3ff;
          background: #2f6fb0;
          clip-path: polygon(0 0, calc(100% - 18px) 0, 100% 50%, calc(100% - 18px) 100%, 0 100%, 14px 50%);
        }
        .wiz-step.first { clip-path: polygon(0 0, calc(100% - 18px) 0, 100% 50%, calc(100% - 18px) 100%, 0 100%); }
        .wiz-step.done { background: #4b90cd; }
        .wiz-step.active { background: #1f81d8; box-shadow: inset 0 0 0 2px #7dc5ff; }
        .wiz-step.todo { background: #7db0df; color: #eef6ff; }
        .wiz-card {
          margin-top: 12px;
          border: 1px solid var(--b1);
          border-radius: var(--r);
          background: var(--s2);
          padding: 14px;
        }
        .wiz-label {
          font-size: 11px;
          color: var(--t3);
          letter-spacing: 1px;
          text-transform: uppercase;
          margin-bottom: 6px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _find_bqms_root() -> str:
    candidates = [
        os.path.join(os.path.expanduser("~"), "OneDrive - SONG CHAU CO., LTD", "Puplic", "BQMS"),
        os.path.join(os.path.expanduser("~"), "OneDrive - SONG CHAU CO., LTD", "Public", "BQMS"),
    ]
    for p in candidates:
        if os.path.isdir(p):
            return p
    return candidates[0]


def _all_bqms_roots() -> list[str]:
    roots = [
        os.path.join(os.path.expanduser("~"), "OneDrive - SONG CHAU CO., LTD", "Puplic", "BQMS"),
        os.path.join(os.path.expanduser("~"), "OneDrive - SONG CHAU CO., LTD", "Public", "BQMS"),
    ]
    out = []
    for p in roots:
        if os.path.isdir(p):
            out.append(p)
    return out or roots


def _rfq_year_dirs(rfq_root: str) -> list[str]:
    if not os.path.isdir(rfq_root):
        return []
    out = []
    for n in os.listdir(rfq_root):
        p = os.path.join(rfq_root, n)
        if os.path.isdir(p) and re.search(r"\brfq\b", n.lower()):
            out.append(p)
    out.sort(reverse=True)
    return out


def _month_dirs(year_dir: str) -> list[str]:
    if not os.path.isdir(year_dir):
        return []
    out = []
    for n in os.listdir(year_dir):
        p = os.path.join(year_dir, n)
        if os.path.isdir(p) and re.search(r"thang\s*\d+", n.lower()):
            out.append(p)
    out.sort(
        key=lambda x: int(re.search(r"(\d+)", os.path.basename(x)).group(1))
        if re.search(r"(\d+)", os.path.basename(x))
        else 0
    )
    out.reverse()
    return out


def _rfq_folders(month_dir: str) -> list[str]:
    if not os.path.isdir(month_dir):
        return []
    out = [os.path.join(month_dir, n) for n in os.listdir(month_dir) if os.path.isdir(os.path.join(month_dir, n))]
    out.sort(reverse=True)
    return out


def _extract_rfq_no(folder_name: str) -> str:
    base = os.path.basename(folder_name or "")
    m = re.match(r"([A-Za-z]{1,3}\d{6,})", base)
    if m:
        return m.group(1).upper()
    return base.split(" ")[0].strip()


def _project_root() -> str:
    return os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _resolve_db_path() -> str:
    from modules.config import get_config
    cfg = get_config()
    db_rel = str(cfg.get("db_path", "./bsmq.db") or "./bsmq.db")
    if os.path.isabs(db_rel):
        return db_rel
    return os.path.normpath(os.path.join(_project_root(), db_rel.lstrip("./")))


def _log_export_sheet_status(
    rfq_no: str,
    quote_level: int,
    workflow_type: str,
    output_dir: str,
    export_result: dict,
) -> None:
    db_path = _resolve_db_path()
    run_id = f"gcwiz_{uuid.uuid4().hex[:12]}"
    profile = str(export_result.get("export_profile", "locked_template_fit_width"))
    rows = export_result.get("sheet_report", []) or []
    if not rows and export_result.get("files"):
        rows = [
            {
                "sheet": os.path.splitext(os.path.basename(p))[0],
                "code": "",
                "status": "ok",
                "pdf_file": p,
                "error": "",
            }
            for p in export_result.get("files", [])
        ]

    conn = sqlite3.connect(db_path, check_same_thread=False)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gc_export_sheet_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                created_at TEXT,
                rfq_no TEXT,
                quote_level INTEGER,
                workflow_type TEXT,
                output_dir TEXT,
                sheet_name TEXT,
                bqms_code TEXT,
                status TEXT,
                pdf_file TEXT,
                error_msg TEXT,
                export_profile TEXT
            )
            """
        )
        now = datetime.now().isoformat(timespec="seconds")
        for r in rows:
            conn.execute(
                """
                INSERT INTO gc_export_sheet_log
                (run_id, created_at, rfq_no, quote_level, workflow_type, output_dir,
                 sheet_name, bqms_code, status, pdf_file, error_msg, export_profile)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    now,
                    rfq_no,
                    int(quote_level or 0),
                    workflow_type,
                    output_dir or "",
                    str(r.get("sheet", "")),
                    str(r.get("code", "")),
                    str(r.get("status", "")),
                    str(r.get("pdf_file", "")),
                    str(r.get("error", "")),
                    profile,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    if s == "" or s.lower() in ("nan", "none"):
        return None
    s = s.replace(" ", "")
    # handle both 123,456 and 123.456 style thousands
    s = s.replace(",", "")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def _history_candidates(bqms_root: str) -> list[str]:
    files = []
    for root in _all_bqms_roots():
        pats = [
            os.path.join(root, "*Thong*ke*hoi*hang*.xls*"),
            os.path.join(root, "*thong*ke*hoi*hang*.xls*"),
            os.path.join(root, "*.xls*"),
        ]
        for pat in pats:
            files.extend(glob.glob(pat))

    def _readable(f: str) -> bool:
        try:
            with open(f, "rb") as h:
                h.read(1)
            return True
        except Exception:
            return False

    files = [
        os.path.normpath(f)
        for f in files
        if os.path.isfile(f) and not os.path.basename(f).startswith("~$") and _readable(f)
    ]
    uniq = sorted(set(files), key=lambda p: os.path.getmtime(p), reverse=True)
    return uniq[:20]


def _snapshot_file() -> str:
    cache_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "cache"))
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "gcwiz_history_snapshot.xlsx")


def _load_history_resilient(path: str) -> tuple[dict, str]:
    """
    Try to read history file safely on Windows/OneDrive:
    1) copy source to local snapshot and load snapshot
    2) fallback direct load
    3) if locked/permission denied, load last snapshot
    Returns: (result_dict_from_engine, note)
    """
    src = os.path.normpath(path or "")
    snap = _snapshot_file()
    last_err = ""

    if not src:
        return {"ok": False, "error": "Empty history path", "df": None, "meta": {}}, ""
    if not os.path.exists(src):
        return {"ok": False, "error": f"File not found: {src}", "df": None, "meta": {}}, ""
    if not os.path.isfile(src):
        return {"ok": False, "error": f"Path is not a file: {src}", "df": None, "meta": {}}, ""

    for _ in range(3):
        try:
            shutil.copy2(src, snap)
            r = load_bqms_analytics(snap)
            if r.get("ok"):
                return r, "Loaded from local snapshot."
        except Exception as e:
            last_err = str(e)
            time.sleep(0.6)

    try:
        r = load_bqms_analytics(src)
        if r.get("ok"):
            return r, "Loaded directly from source file."
        last_err = r.get("error", last_err)
    except Exception as e:
        last_err = str(e)

    if "Permission denied" in last_err and os.path.isfile(snap):
        r = load_bqms_analytics(snap)
        if r.get("ok"):
            return r, "Source file is locked. Loaded from last snapshot."

    # Try Excel COM SaveCopyAs when source is opened/locked.
    try:
        ps = f"""
$ErrorActionPreference = 'Stop'
$src = '{src.replace("'", "''")}'
$dst = '{snap.replace("'", "''")}'
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
$wb = $excel.Workbooks.Open($src, 0, $true)
try {{
  $wb.SaveCopyAs($dst)
}} finally {{
  $wb.Close($false)
  $excel.Quit()
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($wb) | Out-Null
  [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null
}}
"""
        import subprocess

        rr = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            timeout=90,
            capture_output=True,
            text=True,
        )
        if rr.returncode == 0 and os.path.isfile(snap):
            r = load_bqms_analytics(snap)
            if r.get("ok"):
                return r, "Loaded via Excel COM SaveCopyAs snapshot."
    except Exception:
        pass

    # Try same filename under alternative BQMS roots (Public/Puplic fallback).
    base = os.path.basename(src)
    for root in _all_bqms_roots():
        alt = os.path.join(root, base)
        if os.path.normcase(os.path.normpath(alt)) == os.path.normcase(src):
            continue
        if not os.path.isfile(alt):
            continue
        try:
            with open(alt, "rb") as h:
                h.read(1)
            r = load_bqms_analytics(alt)
            if r.get("ok"):
                return r, f"Source denied. Loaded from alternate path: {alt}"
        except Exception:
            pass

    return {"ok": False, "error": last_err or "Cannot load history file.", "df": None, "meta": {}}, ""


def _step_header(step: int):
    cls = []
    for i in [1, 2, 3]:
        if i < step:
            cls.append("done")
        elif i == step:
            cls.append("active")
        else:
            cls.append("todo")
    st.markdown(
        f"""
        <div class="wiz-wrap">
          <div class="wiz-steps">
            <div class="wiz-step first {cls[0]}">Step 1 - Select RFQ</div>
            <div class="wiz-step {cls[1]}">Step 2 - Validate Data</div>
            <div class="wiz-step {cls[2]}">Step 3 - Run L2</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_gc_l2_wizard():
    _inject_step_css()
    if "gcwiz_step" not in st.session_state:
        st.session_state.gcwiz_step = 1

    bqms_root = _find_bqms_root()
    rfq_root = os.path.join(bqms_root, "RFQ")

    step = st.session_state.gcwiz_step
    _step_header(step)
    st.markdown('<div class="wiz-card">', unsafe_allow_html=True)

    if step == 1:
        st.markdown('<div class="wiz-label">Paste RFQ No. and auto-match folder</div>', unsafe_allow_html=True)
        rfq_lookup = st.text_input(
            "Find by RFQ No.",
            value=st.session_state.get("gcwiz_rfq_lookup", ""),
            key="gcwiz_rfq_lookup",
            placeholder="QT26029114",
        )

        if rfq_lookup.strip():
            matches = _find_rfq_candidates(rfq_root, rfq_lookup.strip())
            if matches:
                smap = {f"{os.path.basename(p)}  [{os.path.basename(os.path.dirname(p))}]": p for p in matches}
                chosen = st.selectbox(
                    "Matched RFQ folders (all months)",
                    list(smap.keys()),
                    key="gcwiz_rfq_match_select",
                )
                chosen_path = smap[chosen]
                st.session_state.gcwiz_rfq_folder_path = chosen_path
                st.session_state.gcwiz_rfq_no = _extract_rfq_no(os.path.basename(chosen_path))
                st.success(f"Matched: {chosen_path}")
            else:
                st.warning("No folder matched this RFQ No. across all month folders.")

        c1, c2 = st.columns([1, 1])
        with c2:
            if st.button("Next", key="gcwiz_next_1", use_container_width=True):
                if st.session_state.get("gcwiz_rfq_no"):
                    st.session_state.gcwiz_step = 2
                    st.rerun()
                else:
                    st.warning("Paste RFQ No. and choose a matched folder first.")

    elif step == 2:
        st.markdown('<div class="wiz-label">Select BQMS History + Preview Match</div>', unsafe_allow_html=True)
        cand = _history_candidates(bqms_root)
        if not cand:
            st.error(f"No Excel file found in: {bqms_root}")
        else:
            pick = st.selectbox(
                "History file",
                cand,
                format_func=lambda p: f"{os.path.basename(p)}  [{os.path.basename(os.path.dirname(p))}]",
                key="gcwiz_history_file_select",
            )
            st.session_state.gcwiz_history_path = pick

            rfq_no = st.session_state.get("gcwiz_rfq_no", "")
            preview_ok = False
            try:
                res, load_note = _load_history_resilient(pick)
                if res.get("ok"):
                    if load_note:
                        st.caption(load_note)
                    df = res["df"]
                    k = rfq_no.lower().replace(" ", "")
                    m = df[df["rfq_no"].astype(str).str.lower().str.replace(" ", "") == k].copy()
                    qcols = [c for c in ["quote_v1", "quote_v2", "quote_v3", "quote_v4"] if c in m.columns]
                    if qcols:
                        price_rows = m[m[qcols].notna().any(axis=1)]
                    else:
                        price_rows = m.iloc[0:0]
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Rows by RFQ", f"{len(m):,}")
                    c2.metric("Rows with any quote", f"{len(price_rows):,}")
                    c3.metric("Unique BQMS", f"{price_rows['bqms_code'].astype(str).str.strip().nunique():,}")
                    preview_ok = len(price_rows) > 0
                    if not preview_ok:
                        st.warning("No quote data (V1-V4) for this RFQ in selected history file.")

                    if not m.empty:
                        show_cols = [
                            "date",
                            "rfq_no",
                            "bqms_code",
                            "spec",
                            "maker",
                            "qty_forecast",
                            "quote_v1",
                            "quote_v2",
                            "quote_v3",
                            "quote_v4",
                            "note",
                            "supplier",
                            "round",
                            "result",
                        ]
                        show_cols = [c for c in show_cols if c in m.columns]
                        view = m[show_cols].copy()
                        if "date" in view.columns:
                            view = view.sort_values("date", ascending=False, na_position="last")
                            view["date"] = pd.to_datetime(view["date"], errors="coerce").dt.strftime("%d/%m/%Y")
                            view["date"] = view["date"].fillna("")

                        st.markdown('<div class="wiz-label" style="margin-top:10px;">Extracted RFQ Rows (for verification)</div>', unsafe_allow_html=True)
                        sel_df = view.copy().reset_index(drop=True)
                        if "pick" not in sel_df.columns:
                            sel_df.insert(0, "pick", False)
                        if len(sel_df) > 0:
                            sel_df.at[0, "pick"] = True
                        edited = st.data_editor(
                            sel_df,
                            use_container_width=True,
                            height=300,
                            hide_index=True,
                            key="gcwiz_pick_rows_editor",
                            column_config={
                                "pick": st.column_config.CheckboxColumn(
                                    "Pick",
                                    help="Select rows to use for V2 pricing in Step 3",
                                )
                            },
                            disabled=[c for c in sel_df.columns if c != "pick"],
                        )

                        picked = edited[edited["pick"] == True].copy()
                        picked_records = picked.drop(columns=["pick"], errors="ignore").to_dict("records")
                        st.session_state.gcwiz_selected_rows = picked_records
                        st.caption(f"Selected rows: {len(picked_records)}")

                        missing_v2 = view[view["quote_v2"].isna()] if "quote_v2" in view.columns else pd.DataFrame()
                        if not missing_v2.empty:
                            st.warning(f"{len(missing_v2)} row(s) are missing V2 price. These rows may require manual handling.")
                    else:
                        st.warning("No row found for this RFQ in selected history file.")
                else:
                    st.error(res.get("error", "Cannot parse history file."))
            except Exception as e:
                st.error(f"Preview error: {e}")

            st.session_state.gcwiz_preview_ok = preview_ok and bool(st.session_state.get("gcwiz_selected_rows"))

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Back", key="gcwiz_back_2", use_container_width=True):
                st.session_state.gcwiz_step = 1
                st.rerun()
        with c2:
            if st.button("Next", key="gcwiz_next_2", use_container_width=True):
                if st.session_state.get("gcwiz_preview_ok") and st.session_state.get("gcwiz_history_path"):
                    st.session_state.gcwiz_step = 3
                    st.session_state.gcwiz_phase = "prepare"
                    st.session_state.gcwiz_prepare_result = None
                    st.session_state.gcwiz_export_result = None
                    st.rerun()
                else:
                    st.warning("Select at least 1 valid row (with V2) and a history file.")

    else:
        st.markdown('<div class="wiz-label">Run Automation</div>', unsafe_allow_html=True)
        rfq_no = st.session_state.get("gcwiz_rfq_no", "")
        history = st.session_state.get("gcwiz_history_path", "") or st.session_state.get("gcwiz_history_file_select", "")
        selected_rows = st.session_state.get("gcwiz_selected_rows", [])
        flow_type = st.selectbox("Workflow type", ["Gia cong", "Thuong mai"], key="gcwiz_flow_type")
        lv = st.selectbox("Quote level", ["L1", "L2", "L3", "L4"], index=1, key="gcwiz_level")
        level_num = int(str(lv).replace("L", ""))
        price_col = f"quote_v{level_num}"

        selected_price_map = {}
        selected_price_detail = []
        # Price strategy for edit value:
        # L1 -> use quote_v1
        # Lx (x>=2) -> use delta = quote_v(x-1) - quote_vx
        prev_col = f"quote_v{max(level_num - 1, 1)}"
        cur_col = f"quote_v{level_num}"
        for r in selected_rows:
            code = str(r.get("bqms_code", "")).strip()
            if not code:
                continue
            if level_num == 1:
                v1 = _num(r.get("quote_v1"))
                if v1 is not None:
                    price_val = float(v1)
                    selected_price_map[code] = price_val
                    selected_price_detail.append(
                        {"bqms_code": code, "prev": "", "curr": float(v1), "delta": price_val, "source_col": "quote_v1"}
                    )
            else:
                vp = _num(r.get(prev_col))
                vc = _num(r.get(cur_col))
                if vp is not None and vc is not None:
                    price_val = float(vp - vc)
                    selected_price_map[code] = price_val
                    selected_price_detail.append(
                        {
                            "bqms_code": code,
                            "prev": float(vp),
                            "curr": float(vc),
                            "delta": price_val,
                            "source_col": f"{prev_col}-{cur_col}",
                        }
                    )
        timeout_sec = st.number_input("Manual timeout (seconds)", min_value=60, max_value=900, value=300, step=30)

        st.info(f"RFQ: {rfq_no}")
        st.caption(f"History file: {os.path.basename(history) if history else '-'}")
        if level_num == 1:
            rule_txt = "quote_v1"
        else:
            rule_txt = f"{prev_col} - {cur_col}"
        st.caption(
            f"Selected rows: {len(selected_rows)} | target level: L{level_num} | "
            f"fill rule: {rule_txt} | usable codes: {len(selected_price_map)}"
        )
        if selected_price_detail:
            with st.expander("Resolved price source by code", expanded=False):
                st.dataframe(pd.DataFrame(selected_price_detail), use_container_width=True, height=160)

        phase = st.session_state.get("gcwiz_phase", "prepare")
        prepare_res = st.session_state.get("gcwiz_prepare_result")
        export_res = st.session_state.get("gcwiz_export_result")

        if phase == "prepare":
            pg = st.progress(0)
            ptxt = st.empty()
            can_run = bool(rfq_no and history and os.path.isfile(history) and selected_price_map)
            if not can_run:
                st.warning("Missing history/selected rows/price values for this level. Check Step 2 and level option.")

            if st.button("Run Edit Stage", type="primary", use_container_width=True, key="gcwiz_run_prepare", disabled=not can_run):
                def _cb(step_idx, total, msg):
                    pct = int((step_idx / max(total, 1)) * 100)
                    pg.progress(pct)
                    ptxt.caption(f"[{step_idx}/{total}] {msg}")

                with st.spinner("Editing Excel..."):
                    out = run_gia_cong_prepare_job(
                        rfq_no=rfq_no,
                        history_path=history,
                        rfq_root_dir=rfq_root,
                        rfq_folder_override=st.session_state.get("gcwiz_rfq_folder_path", ""),
                        manual_timeout_sec=int(timeout_sec),
                        selected_v2_map=selected_price_map,
                        quote_level=level_num,
                        workflow_type=flow_type.lower().replace(" ", "_"),
                        progress_callback=_cb,
                    )
                st.session_state.gcwiz_prepare_result = out
                if out.get("success"):
                    st.session_state.gcwiz_phase = "review"
                st.rerun()

        if phase in ("review", "export", "done"):
            out = prepare_res or {}
            if out.get("success"):
                st.success(f"Edit stage done. Folder: {out.get('output_dir')}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Sheets", f"{int(out.get('sheet_count', 0)):,}")
                c2.metric("Codes mapped", f"{int(out.get('code_count', 0)):,}")
                c3.metric("Markers found", f"{int(out.get('marker_total', 0)):,}")
            else:
                st.error("Edit stage failed.")
                if out.get("errors"):
                    st.error("\n".join(str(x) for x in out.get("errors", [])))

            if out.get("edit_report"):
                st.markdown('<div class="wiz-label" style="margin-top:8px;">Excel Edit Board</div>', unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(out["edit_report"]), use_container_width=True, height=220)
            if out.get("manual_required"):
                st.warning("Manual review required:\n" + "\n".join(f"- {x.get('sheet')}: {x.get('reason')}" for x in out.get("manual_required", [])))

            excel_path = out.get("excel_path", "")
            b1, b2 = st.columns([1, 1])
            with b1:
                if st.button("Open Excel For Manual Edit", key="gcwiz_open_excel", use_container_width=True, disabled=not excel_path):
                    try:
                        os.startfile(excel_path)
                        st.info("Excel opened. Edit manually then click Continue to Export.")
                    except Exception as e:
                        st.error(f"Cannot open Excel: {e}")
            with b2:
                if st.button("Continue To Export", key="gcwiz_continue_export", use_container_width=True, disabled=not out.get("success")):
                    st.session_state.gcwiz_phase = "export"
                    st.rerun()

        if phase == "export":
            out = prepare_res or {}
            pg2 = st.progress(0)
            p2 = st.empty()

            def _cb2(step_idx, total, msg):
                pct = int((step_idx / max(total, 1)) * 100)
                pg2.progress(pct)
                p2.caption(f"[{step_idx}/{total}] {msg}")

            with st.spinner("Exporting PDF..."):
                exp = run_gia_cong_export_job(
                    rfq_no=rfq_no,
                    excel_path=out.get("excel_path", ""),
                    output_dir=out.get("output_dir", ""),
                    level=int(out.get("level") or level_num),
                    sheet_items=out.get("sheet_items", []),
                    progress_callback=_cb2,
                )
            try:
                _log_export_sheet_status(
                    rfq_no=rfq_no,
                    quote_level=int(out.get("level") or level_num),
                    workflow_type=flow_type,
                    output_dir=out.get("output_dir", ""),
                    export_result=exp,
                )
            except Exception:
                pass
            st.session_state.gcwiz_export_result = exp
            st.session_state.gcwiz_phase = "done"
            st.rerun()

        if phase == "done":
            exp = export_res or {}
            if exp.get("success"):
                st.success("Export stage done.")
                st.caption(f"Export profile: {exp.get('export_profile', 'locked_template_fit_width')} (default locked for all RFQ)")
                if exp.get("files"):
                    st.dataframe(pd.DataFrame({"pdf_file": exp["files"]}), use_container_width=True, height=180)
                if exp.get("sheet_report"):
                    st.markdown('<div class="wiz-label" style="margin-top:8px;">Sheet Export Status</div>', unsafe_allow_html=True)
                    st.dataframe(pd.DataFrame(exp.get("sheet_report", [])), use_container_width=True, height=200)
                q1, q2 = st.columns([1, 1])
                with q1:
                    if st.button("Open Output Folder", key="gcwiz_open_pdf_folder", use_container_width=True):
                        try:
                            out_dir = (prepare_res or {}).get("output_dir", "")
                            if out_dir and os.path.isdir(out_dir):
                                os.startfile(out_dir)
                        except Exception as e:
                            st.error(f"Cannot open output folder: {e}")
                with q2:
                    if st.button("Quick Verify PDF (Top 4)", key="gcwiz_quick_verify_pdf", use_container_width=True):
                        opened = 0
                        for p in (exp.get("files", []) or [])[:4]:
                            try:
                                if os.path.isfile(p):
                                    os.startfile(p)
                                    opened += 1
                            except Exception:
                                pass
                        st.info(f"Opened {opened} PDF file(s) for quick verify.")
            else:
                st.error("Export stage failed.")
                if exp.get("warnings"):
                    st.warning("\n".join(str(x) for x in exp.get("warnings", [])))
                if exp.get("errors"):
                    st.error("\n".join(str(x) for x in exp.get("errors", [])))
                if st.button("Retry Export", key="gcwiz_retry_export", use_container_width=True):
                    st.session_state.gcwiz_phase = "export"
                    st.rerun()

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("Back", key="gcwiz_back_3", use_container_width=True):
                st.session_state.gcwiz_step = 2
                st.rerun()
        with c2:
            if st.button("Reset wizard", key="gcwiz_reset", use_container_width=True):
                for k in [
                    "gcwiz_rfq_folder_path",
                    "gcwiz_rfq_no",
                    "gcwiz_history_path",
                    "gcwiz_history_file",
                    "gcwiz_history_file_select",
                    "gcwiz_selected_v2_map",
                    "gcwiz_selected_rows",
                    "gcwiz_preview_ok",
                    "gcwiz_phase",
                    "gcwiz_prepare_result",
                    "gcwiz_export_result",
                ]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.session_state.gcwiz_step = 1
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
