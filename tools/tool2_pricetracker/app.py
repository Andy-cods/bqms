"""
Tool 2 - BQMS Analytics dashboard UI.
"""

import os
import glob
import tempfile
import sys
import json
import re
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tools.tool2_pricetracker.engine import (
    load_bqms_analytics,
    load_bc_bqms_2026,
    capture_bc_row_image_via_com,
)

_PREF_PATH = os.path.join(_ROOT, "cache", "tool2_view_prefs.json")
_T2_SNAP_ROOT = os.path.join(_ROOT, "cache", "tool2_bc2026_snapshots")


def _safe_file_token(v: str, max_len: int = 80) -> str:
    s = str(v or "").strip()
    if not s:
        return "na"
    s = re.sub(r'[\\/*?:"<>|]+', "_", s)
    s = re.sub(r"\s+", "_", s)
    return s[:max_len] or "na"


def _capture_keys(source_path: str, excel_row: int, source_mtime: int) -> tuple[str, str, str, str]:
    cache_tag = f"{abs(hash(source_path))}_{int(excel_row)}_{int(source_mtime)}"
    cap_key = f"t2_bc2026_cap_{cache_tag}"
    cache_key = f"t2_bc2026_cap_img_{cache_tag}"
    status_key = f"t2_bc2026_cap_status_{cache_tag}"
    return cache_tag, cap_key, cache_key, status_key


def _save_captured_snapshot(source_path: str, excel_row: int, rfq_no: str, bqms_code: str, img_bytes: bytes) -> str:
    base = os.path.splitext(os.path.basename(source_path or ""))[0] or "bc_file"
    out_dir = os.path.join(_T2_SNAP_ROOT, _safe_file_token(base, 60))
    os.makedirs(out_dir, exist_ok=True)
    name = f"r{int(excel_row):06d}_{_safe_file_token(rfq_no, 24)}_{_safe_file_token(bqms_code, 28)}.png"
    out_path = os.path.join(out_dir, name)
    with open(out_path, "wb") as f:
        f.write(img_bytes or b"")
    return os.path.normpath(out_path)


def _non_empty_columns(df: pd.DataFrame) -> list[str]:
    keep = []
    for c in df.columns:
        s = df[c].astype(str).str.strip().str.lower()
        if s.replace("nan", "").replace("nat", "").replace("none", "").ne("").any():
            keep.append(c)
    return keep


def _fmt_vnd(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    try:
        n = int(round(float(v)))
        return f"{n:,}".replace(",", ".") + " VND"
    except Exception:
        return ""


def _fmt_rmb(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return ""
    try:
        n = float(v)
        return f"{n:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".") + " RMB"
    except Exception:
        return ""


def _load_prefs() -> dict:
    try:
        if os.path.isfile(_PREF_PATH):
            with open(_PREF_PATH, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_prefs(prefs: dict) -> None:
    os.makedirs(os.path.dirname(_PREF_PATH), exist_ok=True)
    with open(_PREF_PATH, "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False, indent=2)


def _append_queue_log(stage: str, item: dict) -> None:
    if "t2_queue_log" not in st.session_state:
        st.session_state.t2_queue_log = []
    st.session_state.t2_queue_log.append(
        {
            "ts": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stage": stage,
            "rfq_no": str(item.get("rfq_no", "") or ""),
            "bqms_code": str(item.get("bqms_code", "") or ""),
        }
    )


def _safe_chart_frame(df: pd.DataFrame, x_col: str, y_col: str) -> pd.DataFrame:
    if df is None or df.empty or x_col not in df.columns or y_col not in df.columns:
        return pd.DataFrame(columns=[x_col, y_col])
    out = df[[x_col, y_col]].copy()
    out[y_col] = pd.to_numeric(out[y_col], errors="coerce")
    out.replace([np.inf, -np.inf], np.nan, inplace=True)
    out.dropna(subset=[x_col, y_col], inplace=True)
    out = out[out[y_col].notna()]
    if out.empty:
        return out
    out[y_col] = out[y_col].astype(float)
    return out


def _normalize_dir_path(p: str) -> str:
    p = (p or "").strip()
    if p.startswith(":\\"):
        p = "C" + p
    return p


def _pick_latest_bqms_file(folder: str) -> str:
    folder = _normalize_dir_path(folder)
    if not os.path.isdir(folder):
        return ""
    candidates = glob.glob(os.path.join(folder, "*.xls*"))
    candidates = [os.path.normpath(c) for c in candidates if os.path.isfile(c)]
    if not candidates:
        return ""

    def _score(path: str) -> tuple[int, float]:
        n = os.path.basename(path).lower()
        sc = 0
        if "bqms" in n:
            sc += 3
        if "hoi hang" in n:
            sc += 3
        if "thong ke" in n:
            sc += 2
        if "gia phoi" in n:
            sc -= 5
        return (sc, os.path.getmtime(path))

    candidates.sort(key=_score, reverse=True)
    return candidates[0]


def _resolve_bc_2026_file(path_or_dir: str) -> str:
    p = _normalize_dir_path(path_or_dir)
    if not p:
        return ""
    if os.path.isfile(p):
        return os.path.normpath(p)
    cands = []
    if os.path.isdir(p):
        year = datetime.now().year
        month = datetime.now().month
        scan_dirs = [p]
        for dn in [f"BC BQMS {year}", "BC BQMS 2026"]:
            dp = os.path.join(p, dn)
            if os.path.isdir(dp) and dp not in scan_dirs:
                scan_dirs.insert(0, dp)

        for d in scan_dirs:
            cands.extend(glob.glob(os.path.join(d, "*.xls*")))
            # If month folders exist, include files inside current-month folders first.
            for sn in os.listdir(d):
                sd = os.path.join(d, sn)
                if not os.path.isdir(sd):
                    continue
                fold = sn.lower().replace("_", " ").replace("-", " ")
                if "thang" in fold:
                    cands.extend(glob.glob(os.path.join(sd, "*.xls*")))
    else:
        cands = glob.glob(p + "*.xls*")
        if not cands and "bc bqms" in p.lower():
            cands = glob.glob(p.replace("2026", "") + "*.xls*")
    cands = [os.path.normpath(x) for x in cands if os.path.isfile(x)]
    if not cands:
        return ""
    month = datetime.now().month

    def _score_bc(path: str) -> tuple[int, float]:
        n = os.path.basename(path).lower().replace("_", " ").replace("-", " ")
        sc = 0
        if "bc bqms" in n:
            sc += 5
        if f"thang {month}" in n or f"thang{month}" in n:
            sc += 50
        if "origin" in n:
            sc -= 3
        try:
            mt = os.path.getmtime(path)
        except Exception:
            mt = 0
        return (sc, mt)

    cands.sort(key=_score_bc, reverse=True)
    return cands[0]


def render_tool2_tab(_db_path: str):
    st.markdown('<div class="sec" style="margin:8px 0 8px;">Tool 2 - BQMS Analytics Board</div>', unsafe_allow_html=True)

    path = st.text_input(
        "Thong ke hoi hang BQMS file path",
        value=st.session_state.get("t2_bqms_analytics_path", "Thong ke hoi hang BQMS.xlsx"),
        key="t2_bqms_analytics_path",
        placeholder=r"C:\...\Thong ke hoi hang BQMS.xlsx",
    )
    sync_folder = st.text_input(
        "Sync folder",
        value=st.session_state.get(
            "t2_sync_folder",
            os.path.join(os.path.expanduser("~"), "OneDrive - SONG CHAU CO., LTD", "Puplic", "BQMS"),
        ),
        key="t2_sync_folder",
        placeholder=os.path.join(os.path.expanduser("~"), "OneDrive - SONG CHAU CO., LTD", "Puplic", "BQMS"),
    )
    uploaded = st.file_uploader("Or upload Excel file", type=["xlsx", "xls"], key="t2_upload_bqms")

    c1, c2, c3 = st.columns([1, 1, 3])
    with c1:
        load = st.button("Load analytics", key="t2_load_analytics", use_container_width=True)
    with c2:
        auto_sync = st.toggle("Auto sync", value=st.session_state.get("t2_auto_sync", True), key="t2_auto_sync")
    with c3:
        st.caption("Tool 2 now focuses on statistics and chartboard from BQMS history file.")

    if auto_sync:
        # Refresh page every 15s when auto-sync is enabled.
        st_autorefresh(interval=15000, key="t2_auto_sync_refresh")

    latest_from_folder = _pick_latest_bqms_file(sync_folder)
    run_path = path
    if latest_from_folder:
        st.caption(f"Latest BQMS file in sync folder: {latest_from_folder}")

    if not load and "t2_analytics_result" in st.session_state:
        result = st.session_state["t2_analytics_result"]
        if auto_sync:
            if uploaded is not None:
                suffix = ".xlsx" if uploaded.name.lower().endswith(".xlsx") else ".xls"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(uploaded.getbuffer())
                    run_path = tmp.name
            elif os.path.isfile(path):
                run_path = path
            elif latest_from_folder:
                run_path = latest_from_folder
            result = load_bqms_analytics(run_path)
            st.session_state["t2_analytics_result"] = result
    elif load or auto_sync:
        if uploaded is not None:
            suffix = ".xlsx" if uploaded.name.lower().endswith(".xlsx") else ".xls"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.getbuffer())
                run_path = tmp.name
        elif os.path.isfile(path):
            run_path = path
        elif latest_from_folder:
            run_path = latest_from_folder
        result = load_bqms_analytics(run_path)
        st.session_state["t2_analytics_result"] = result
    else:
        st.info("Select file path then click 'Load analytics'.")
        return

    if not result.get("ok"):
        st.error(result.get("error", "Cannot load analytics data."))
        return

    df = result["df"].copy()
    meta = result["meta"]
    if meta.get("mapped_debug"):
        with st.expander("Column mapping debug", expanded=False):
            st.json(meta["mapped_debug"])

    st.markdown(
        f'<div class="g5" style="margin:8px 0 10px;">'
        f'<div class="kpi" style="--kc:var(--cyan)"><div class="kl">Rows</div><div class="kv">{meta["rows"]:,}</div><div class="ks">loaded records</div></div>'
        f'<div class="kpi" style="--kc:var(--green)"><div class="kl">Wins</div><div class="kv">{meta["wins"]:,}</div><div class="ks">result = win</div></div>'
        f'<div class="kpi" style="--kc:var(--red)"><div class="kl">Loses</div><div class="kv">{meta["loses"]:,}</div><div class="ks">result = lose</div></div>'
        f'<div class="kpi" style="--kc:var(--yellow)"><div class="kl">Win Rate</div><div class="kv">{meta["win_rate"]}%</div><div class="ks">wins / (wins + loses)</div></div>'
        f'<div class="kpi" style="--kc:var(--violet)"><div class="kl">Avg Price</div><div class="kv">{meta["avg_price"]:,}</div><div class="ks">from priced rows</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        f"Raw rows scanned: {meta.get('raw_rows', 0):,} | "
        f"Rows kept after auto-clean: {meta.get('kept_rows', 0):,} | "
        f"Dashboard rows: {meta.get('rows', 0):,}"
    )

    # Date filters in compact dropdown/tick UI
    min_dt = df["date"].dropna().min()
    max_dt = df["date"].dropna().max()
    with st.expander("Time Filters", expanded=False):
        p1, p2, p3, p4 = st.columns(4)
        if p1.button("Today", key="t2_preset_today", use_container_width=True):
            d = pd.Timestamp.now().date()
            st.session_state["t2_date_range"] = (d, d)
        if p2.button("This week", key="t2_preset_week", use_container_width=True):
            now = pd.Timestamp.now()
            start = (now - pd.Timedelta(days=now.weekday())).date()
            end = now.date()
            st.session_state["t2_date_range"] = (start, end)
        if p3.button("This month", key="t2_preset_month", use_container_width=True):
            now = pd.Timestamp.now()
            start = now.replace(day=1).date()
            end = now.date()
            st.session_state["t2_date_range"] = (start, end)
        if p4.button("This quarter", key="t2_preset_quarter", use_container_width=True):
            now = pd.Timestamp.now()
            q_start_month = ((now.month - 1) // 3) * 3 + 1
            start = now.replace(month=q_start_month, day=1).date()
            end = now.date()
            st.session_state["t2_date_range"] = (start, end)

        tf0, tf1, tf2, tf3 = st.columns([2, 1, 1, 1])
        if pd.notna(min_dt) and pd.notna(max_dt):
            with tf0:
                date_range = st.date_input(
                    "Date range",
                    value=(min_dt.date(), max_dt.date()),
                    key="t2_date_range",
                )
        else:
            date_range = ()

        years = sorted([int(y) for y in df["date"].dropna().dt.year.unique().tolist() if pd.notna(y)])
        months = sorted([int(m) for m in df["date"].dropna().dt.month.unique().tolist() if pd.notna(m)])
        days = sorted([int(d) for d in df["date"].dropna().dt.day.unique().tolist() if pd.notna(d)])
        with tf1:
            year_pick = st.multiselect("Year", options=years, default=years, key="t2_year_filter")
        with tf2:
            month_pick = st.multiselect("Month", options=months, default=months, key="t2_month_filter")
        with tf3:
            day_pick = st.multiselect("Day", options=days, default=days, key="t2_day_filter")

    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        d0, d1 = date_range
        if d0 and d1:
            df = df[(df["date"].dt.date >= d0) & (df["date"].dt.date <= d1) | df["date"].isna()]
    if year_pick:
        df = df[df["date"].dt.year.isin(year_pick) | df["date"].isna()]
    if month_pick:
        df = df[df["date"].dt.month.isin(month_pick) | df["date"].isna()]
    if day_pick:
        df = df[df["date"].dt.day.isin(day_pick) | df["date"].isna()]

    left, right = st.columns([2, 1])
    with left:
        st.markdown('<div class="sec">Trend by Month</div>', unsafe_allow_html=True)
        trend = df[df["year_month"] != ""].groupby("year_month").size().reset_index(name="count")
        trend = _safe_chart_frame(trend, "year_month", "count")
        if not trend.empty:
            st.line_chart(trend.set_index("year_month")["count"], use_container_width=True)
        else:
            st.caption("No date column detected for monthly trend.")

        st.markdown('<div class="sec" style="margin-top:10px;">Top Makers (volume)</div>', unsafe_allow_html=True)
        maker = df[df["maker"] != ""].groupby("maker").size().reset_index(name="count").sort_values("count", ascending=False).head(12)
        maker = _safe_chart_frame(maker, "maker", "count")
        if not maker.empty:
            st.bar_chart(maker.set_index("maker")["count"], use_container_width=True)
        else:
            st.caption("No maker column detected.")

    with right:
        st.markdown('<div class="sec">Result Mix</div>', unsafe_allow_html=True)
        mix = df.groupby("result").size().reset_index(name="count").sort_values("count", ascending=False)
        st.dataframe(mix, use_container_width=True, height=190)

        st.markdown('<div class="sec" style="margin-top:10px;">Round Mix</div>', unsafe_allow_html=True)
        round_mix = df[df["round"] != ""].groupby("round").size().reset_index(name="count").sort_values("count", ascending=False).head(10)
        if not round_mix.empty:
            st.dataframe(round_mix, use_container_width=True, height=190)
        else:
            st.caption("No round column detected.")

    st.markdown('<div class="sec" style="margin-top:10px;">Data Explorer</div>', unsafe_allow_html=True)
    prefs = _load_prefs()
    f1, f2, f3 = st.columns([2, 1, 1])
    owner_opts = sorted([x for x in df["owner"].dropna().astype(str).unique().tolist() if x.strip() != ""])
    result_opts = sorted([x for x in df["result"].dropna().astype(str).unique().tolist() if x.strip() != ""])
    with f1:
        owner_pick = st.multiselect("Auto filter by owner", options=owner_opts, default=[], key="t2_owner_filter")
    with f2:
        result_pick = st.multiselect("Result", options=result_opts, default=[], key="t2_result_filter")
    with f3:
        quoted_only = st.toggle("Quoted only", value=False, key="t2_quoted_only")

    q = st.text_input("Filter records", placeholder="code / maker / spec", key="t2_filter")
    newest_first = st.toggle("Newest first", value=True, key="t2_newest_first")
    view = df.copy()
    if owner_pick:
        view = view[view["owner"].isin(owner_pick)]
    if result_pick:
        view = view[view["result"].isin(result_pick)]
    if quoted_only:
        view = view[view["has_quote"] == True]

    if q.strip():
        low = q.strip().lower()
        view = view[
            view["bqms_code"].str.lower().str.contains(low, na=False)
            | view["maker"].str.lower().str.contains(low, na=False)
            | view["spec"].str.lower().str.contains(low, na=False)
            | view["rfq_no"].str.lower().str.contains(low, na=False)
        ]

    if newest_first:
        view = view.sort_values(by=["date"], ascending=False, na_position="last")
    else:
        view = view.sort_values(by=["date"], ascending=True, na_position="last")

    rename_cols = {
        "date": "Ngay",
        "owner": "Nguoi phu trach",
        "rfq_no": "RFQ No",
        "bqms_code": "BQMS code",
        "spec": "Spec",
        "maker": "Maker",
        "qty_forecast": "So luong du kien",
        "in_rmb": "Gia nhap RMB",
        "in_vnd": "Gia nhap VND",
        "quote_ama": "Gia bao cho AMA",
        "quote_v1": "Gia bao cho BQMS V1",
        "quote_v2": "V2",
        "quote_v3": "V3",
        "quote_v4": "V4",
        "note": "Ghi chu",
        "supplier": "NCC",
        "round": "Round",
        "result": "Ket qua",
    }
    ordered = [
        "date", "owner", "rfq_no", "bqms_code", "spec", "maker",
        "qty_forecast", "in_rmb", "in_vnd", "quote_ama",
        "quote_v1", "quote_v2", "quote_v3", "quote_v4",
        "note", "supplier", "round", "result",
    ]
    cols = [c for c in ordered if c in view.columns]
    action_src = view[cols].copy()
    view = action_src.copy()
    # Currency formatting
    if "in_rmb" in view.columns:
        view["in_rmb"] = view["in_rmb"].map(_fmt_rmb)
    for col in ["in_vnd", "quote_ama", "quote_v1", "quote_v2", "quote_v3", "quote_v4"]:
        if col in view.columns:
            view[col] = view[col].map(_fmt_vnd)

    view = view.rename(columns=rename_cols).fillna("")
    auto_cols = _non_empty_columns(view)
    default_cols = prefs.get("visible_columns", auto_cols)
    default_cols = [c for c in default_cols if c in auto_cols] or auto_cols

    s1, s2, s3 = st.columns([2, 1, 1])
    with s1:
        # Dropdown-like selector with checkboxes (no long multiselect tags).
        with st.popover(f"Columns ({len(default_cols)}/{len(auto_cols)})"):
            cbtn1, cbtn2 = st.columns(2)
            if cbtn1.button("All", key="t2_cols_all", use_container_width=True):
                for c in auto_cols:
                    st.session_state[f"t2_col_chk_{c}"] = True
            if cbtn2.button("None", key="t2_cols_none", use_container_width=True):
                for c in auto_cols:
                    st.session_state[f"t2_col_chk_{c}"] = False

            for c in auto_cols:
                k = f"t2_col_chk_{c}"
                if k not in st.session_state:
                    st.session_state[k] = c in default_cols
                st.checkbox(c, key=k)

        visible_cols = [c for c in auto_cols if st.session_state.get(f"t2_col_chk_{c}", False)]
    with s2:
        show_table = st.toggle("Show table", value=prefs.get("show_table", True), key="t2_show_table")
    with s3:
        if st.button("Save view", key="t2_save_view", use_container_width=True):
            _save_prefs({"visible_columns": visible_cols, "show_table": show_table})
            st.success("Saved")
    if "t2_quote_queue" not in st.session_state:
        st.session_state.t2_quote_queue = []

    if show_table:
        cols_show = visible_cols if visible_cols else auto_cols
        raw_for_action = action_src.copy()
        display_for_action = view[cols_show].copy()

        if display_for_action.empty:
            st.caption("No rows available.")
        else:
            per_page = st.selectbox("Rows per page", [20, 50, 100], index=1, key="t2_page_size")
            total_rows = len(display_for_action)
            total_pages = max((total_rows - 1) // per_page + 1, 1)
            page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1, key="t2_page")
            start = (int(page) - 1) * per_page
            end = min(start + per_page, total_rows)

            page_disp = display_for_action.iloc[start:end].copy().reset_index(drop=True)
            page_raw = raw_for_action.iloc[start:end].copy().reset_index(drop=True)
            st.caption(f"Rows {start + 1}-{end} / {total_rows}")

            ACTION_COL = "⋯"
            action_opts = ["", "Create Quote Dossier", "View Details", "Track Row"]
            if ACTION_COL not in page_disp.columns:
                page_disp.insert(0, ACTION_COL, "")

            edited = st.data_editor(
                page_disp,
                key=f"t2_table_editor_{start}_{end}",
                hide_index=True,
                use_container_width=True,
                height=520,
                column_config={
                    ACTION_COL: st.column_config.SelectboxColumn(
                        "⋯",
                        width="small",
                        options=action_opts,
                        required=False,
                        help="Choose row action",
                    )
                },
                disabled=[c for c in page_disp.columns if c != ACTION_COL],
            )

            if st.button("Apply row actions", key=f"t2_apply_row_actions_{start}_{end}", use_container_width=True):
                acted = 0
                for i, row in edited.iterrows():
                    action = str(row.get(ACTION_COL, "") or "").strip()
                    if not action:
                        continue
                    raw_row = page_raw.iloc[i].to_dict()

                    date_txt = ""
                    rv_date = raw_row.get("date", "")
                    if pd.notna(rv_date):
                        try:
                            date_txt = pd.to_datetime(rv_date).strftime("%d/%m/%Y")
                        except Exception:
                            date_txt = str(rv_date)

                    item = {
                        "date": date_txt,
                        "rfq_no": str(raw_row.get("rfq_no", "") or ""),
                        "bqms_code": str(raw_row.get("bqms_code", "") or ""),
                        "spec": str(raw_row.get("spec", "") or ""),
                        "maker": str(raw_row.get("maker", "") or ""),
                        "qty_forecast": raw_row.get("qty_forecast"),
                        "quote_v1": raw_row.get("quote_v1"),
                        "quote_v2": raw_row.get("quote_v2"),
                        "quote_v3": raw_row.get("quote_v3"),
                        "quote_v4": raw_row.get("quote_v4"),
                        "note": str(raw_row.get("note", "") or ""),
                    }

                    if action == "Create Quote Dossier":
                        st.session_state.t2_quote_queue.append(item)
                        st.session_state.t2_prefill_order = item
                        st.session_state.t1_auto_import_queue = True
                        _append_queue_log("queued", item)
                        acted += 1
                    elif action == "View Details":
                        with st.expander(
                            f"Details - {item.get('rfq_no','')} - {item.get('bqms_code','')}",
                            expanded=True,
                        ):
                            st.json(raw_row)
                        acted += 1
                    elif action == "Track Row":
                        st.info(f"Tracked: {item.get('rfq_no','')} / {item.get('bqms_code','')}")
                        acted += 1

                if acted:
                    st.success(f"Applied {acted} action(s).")
                    st.rerun()
                else:
                    st.caption("No action selected.")
    else:
        st.caption("Table hidden to reduce load. Toggle 'Show table' when needed.")

    if st.session_state.t2_quote_queue:
        st.markdown('<div class="sec" style="margin-top:10px;">Quote Queue</div>', unsafe_allow_html=True)
        qdf = pd.DataFrame(st.session_state.t2_quote_queue)
        show_qcols = [c for c in ["date", "rfq_no", "bqms_code", "spec", "maker"] if c in qdf.columns]
        st.dataframe(qdf[show_qcols], use_container_width=True, height=160)
        qlog = st.session_state.get("t2_queue_log", [])
        if qlog:
            with st.expander("Queue lifecycle log", expanded=False):
                st.dataframe(pd.DataFrame(qlog), use_container_width=True, height=140)


def render_tool2_bc2026_tab(_db_path: str):
    st.markdown('<div class="sec" style="margin:8px 0 8px;">BC BQMS 2026 Monitor</div>', unsafe_allow_html=True)
    bc_path = st.text_input(
        "BC BQMS 2026 file/folder",
        value=st.session_state.get(
            "t2_bc2026_path",
            os.path.join(os.path.expanduser("~"), "OneDrive - SONG CHAU CO., LTD", "Puplic", "BQMS", "TONG HOP BQMS", "BC BQMS 2026"),
        ),
        key="t2_bc2026_path",
    )
    include_colors = st.toggle("Read row colors", value=True, key="t2_bc2026_colors")
    c1, c2, c3 = st.columns([1, 1, 3])
    with c1:
        load = st.button("Load BC 2026", key="t2_bc2026_load", use_container_width=True)
    with c2:
        auto_sync = st.toggle("Auto sync", value=st.session_state.get("t2_bc2026_auto_sync", True), key="t2_bc2026_auto_sync")
    with c3:
        st.caption("Separate source. No merge with Thong ke hoi hang BQMS.")

    if auto_sync:
        st_autorefresh(interval=15000, key="t2_bc2026_auto_refresh")

    run_path = _resolve_bc_2026_file(bc_path)
    if not run_path:
        st.error("Cannot find BC BQMS file in provided path/folder.")
        return

    st.caption(f"Auto-selected current month file: {run_path}")
    try:
        run_mtime = int(os.path.getmtime(run_path))
    except Exception:
        run_mtime = 0

    last_path = str(st.session_state.get("t2_bc2026_last_path", "") or "")
    last_mtime = int(st.session_state.get("t2_bc2026_last_mtime", 0) or 0)
    missing_cache = "t2_bc2026_result" not in st.session_state
    changed_source = (run_path != last_path) or (run_mtime != last_mtime)
    should_reload = bool(load or missing_cache or (auto_sync and changed_source))

    if should_reload:
        result = load_bc_bqms_2026(run_path, include_colors=include_colors, include_images=False)
        st.session_state["t2_bc2026_result"] = result
        st.session_state["t2_bc2026_last_path"] = run_path
        st.session_state["t2_bc2026_last_mtime"] = run_mtime
    else:
        result = st.session_state["t2_bc2026_result"]

    if not result.get("ok"):
        st.error(result.get("error", "Cannot load BC BQMS 2026 data."))
        # Fallback: show raw sheet preview so tab still usable even if mapping differs.
        run_path = _resolve_bc_2026_file(bc_path)
        if run_path and os.path.isfile(run_path):
            try:
                xls = pd.ExcelFile(run_path, engine="openpyxl")
                sheet = xls.sheet_names[0]
                raw = pd.read_excel(run_path, sheet_name=sheet, engine="openpyxl", header=None)
                st.caption(f"Raw preview fallback · file: {os.path.basename(run_path)} · sheet: {sheet}")
                st.dataframe(raw.head(200).fillna(""), use_container_width=True, height=520)
            except Exception as e:
                st.warning(f"Raw preview failed: {e}")
        return

    df = result["df"].copy()
    meta = result.get("meta", {})
    st.caption("Source: " + " | ".join(meta.get("sources", [bc_path])))
    st.markdown(
        f'<div class="g5" style="margin:8px 0 10px;">'
        f'<div class="kpi" style="--kc:var(--cyan)"><div class="kl">Rows</div><div class="kv">{meta.get("rows", 0):,}</div><div class="ks">loaded records</div></div>'
        f'<div class="kpi" style="--kc:var(--green)"><div class="kl">Wins</div><div class="kv">{meta.get("wins", 0):,}</div><div class="ks">result = win</div></div>'
        f'<div class="kpi" style="--kc:var(--red)"><div class="kl">Loses</div><div class="kv">{meta.get("loses", 0):,}</div><div class="ks">result = lose</div></div>'
        f'<div class="kpi" style="--kc:var(--yellow)"><div class="kl">Pending</div><div class="kv">{meta.get("pending", 0):,}</div><div class="ks">result = pending</div></div>'
        f'<div class="kpi" style="--kc:var(--violet)"><div class="kl">Updated</div><div class="kv" style="font-size:14px;">{meta.get("updated_at", "")}</div><div class="ks">last load</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    q = st.text_input("Filter BC rows", placeholder="rfq / bqms / spec / maker", key="t2_bc2026_filter")
    view = df.copy()
    if q.strip():
        low = q.strip().lower()
        view = view[
            view["rfq_no"].astype(str).str.lower().str.contains(low, na=False)
            | view["bqms_code"].astype(str).str.lower().str.contains(low, na=False)
            | view["spec"].astype(str).str.lower().str.contains(low, na=False)
            | view["maker"].astype(str).str.lower().str.contains(low, na=False)
        ]
    view = view.sort_values(by=["date"], ascending=False, na_position="last")

    show_cols = [
        "date", "rfq_no", "bqms_code", "spec", "explain", "loai_hang", "maker", "mark",
        "unit", "qty_forecast", "deadline_text", "status_raw", "note",
        "has_image", "row_color", "sheet", "source_file",
    ]
    show_cols = [c for c in show_cols if c in view.columns]
    if "date" in view.columns:
        view["date"] = pd.to_datetime(view["date"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("")
    per_page = st.selectbox("Rows per page", [20, 50, 100], index=1, key="t2_bc2026_page_size")
    total_rows = len(view)
    total_pages = max((total_rows - 1) // per_page + 1, 1)
    page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1, key="t2_bc2026_page")
    start = (int(page) - 1) * per_page
    end = min(start + per_page, total_rows)
    page_view = view.iloc[start:end].copy().reset_index(drop=True)
    st.caption(f"Rows {start + 1}-{end} / {total_rows}")
    st.dataframe(page_view[show_cols].fillna(""), use_container_width=True, height=500)

    # Image evidence preview (embedded images from Excel rows).
    with st.expander("Image evidence preview", expanded=False):
        st.caption(f"Snapshot cache folder: {_T2_SNAP_ROOT}")

        b1, b2, b3 = st.columns([1, 1, 2])
        with b1:
            batch_limit = st.number_input(
                "Batch size",
                min_value=1,
                max_value=30,
                value=10,
                step=1,
                key="t2_bc2026_batch_limit",
            )
        with b2:
            only_missing = st.toggle("Only missing image", value=True, key="t2_bc2026_batch_missing")
        with b3:
            run_batch = st.button("Batch capture visible rows", key="t2_bc2026_batch_run", use_container_width=True)

        if run_batch:
            candidates = []
            for _, rec0 in page_view.iterrows():
                excel_row0 = int(rec0.get("excel_row", 0) or 0)
                source_path0 = str(rec0.get("source_path", "") or "")
                if excel_row0 <= 0 or not source_path0:
                    continue
                if only_missing and int(rec0.get("has_image", 0) or 0) == 1:
                    continue
                candidates.append(rec0)
            candidates = candidates[: int(batch_limit)]

            if not candidates:
                st.info("No eligible rows on this page for batch capture.")
            else:
                progress = st.progress(0.0)
                status = st.empty()
                report = []
                ok_n = 0
                for i, rec0 in enumerate(candidates, start=1):
                    excel_row0 = int(rec0.get("excel_row", 0) or 0)
                    source_path0 = str(rec0.get("source_path", "") or "")
                    rfq0 = str(rec0.get("rfq_no", "") or "")
                    bqms0 = str(rec0.get("bqms_code", "") or "")
                    source_mtime0 = 0
                    if source_path0 and os.path.isfile(source_path0):
                        try:
                            source_mtime0 = int(os.path.getmtime(source_path0))
                        except Exception:
                            source_mtime0 = 0
                    _, _, cache_key0, status_key0 = _capture_keys(source_path0, excel_row0, source_mtime0)
                    status.caption(f"Capturing row {excel_row0} ({i}/{len(candidates)}) ...")
                    b, e = capture_bc_row_image_via_com(source_path0, excel_row0, col_letter="I")
                    if b:
                        ok_n += 1
                        st.session_state[cache_key0] = b
                        saved_path0 = _save_captured_snapshot(source_path0, excel_row0, rfq0, bqms0, b)
                        st.session_state[status_key0] = {
                            "state": "captured_batch",
                            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "detail": saved_path0,
                        }
                        report.append(
                            {"excel_row": excel_row0, "rfq_no": rfq0, "bqms_code": bqms0, "status": "ok", "output_file": saved_path0, "error": ""}
                        )
                    else:
                        st.session_state[status_key0] = {
                            "state": "error",
                            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "detail": str(e),
                        }
                        report.append(
                            {"excel_row": excel_row0, "rfq_no": rfq0, "bqms_code": bqms0, "status": "error", "output_file": "", "error": str(e)}
                        )
                    progress.progress(float(i / max(len(candidates), 1)))
                status.caption(f"Batch done: {ok_n}/{len(candidates)} captured.")
                st.session_state["t2_bc2026_batch_report"] = report
                st.success(f"Batch capture completed: {ok_n}/{len(candidates)} row(s).")

        batch_report = st.session_state.get("t2_bc2026_batch_report", [])
        if batch_report:
            with st.expander("Batch capture report", expanded=False):
                st.dataframe(pd.DataFrame(batch_report), use_container_width=True, height=200)

        row_opts = [f"{i+1}. {page_view.iloc[i].get('rfq_no','')} | {page_view.iloc[i].get('bqms_code','')}" for i in range(len(page_view))]
        if row_opts:
            idx = st.selectbox("Select row to preview image", list(range(len(row_opts))), format_func=lambda i: row_opts[i], key="t2_bc2026_img_row")
            rec = page_view.iloc[int(idx)]
            img_bytes = rec.get("image_bytes", b"")
            excel_row = int(rec.get("excel_row", 0) or 0)
            source_path = str(rec.get("source_path", "") or "")
            source_mtime = 0
            if source_path and os.path.isfile(source_path):
                try:
                    source_mtime = int(os.path.getmtime(source_path))
                except Exception:
                    source_mtime = 0

            _, cap_key, cache_key, status_key = _capture_keys(source_path, excel_row, source_mtime)

            if not (isinstance(img_bytes, (bytes, bytearray)) and len(img_bytes) > 0):
                if excel_row > 0 and source_path:
                    if st.button("Capture image from Excel row (COM + snapshot fallback)", key=cap_key, use_container_width=False):
                        b, e = capture_bc_row_image_via_com(source_path, excel_row, col_letter="I")
                        if b:
                            img_bytes = b
                            st.session_state[cache_key] = b
                            saved_path = _save_captured_snapshot(
                                source_path,
                                excel_row,
                                str(rec.get("rfq_no", "") or ""),
                                str(rec.get("bqms_code", "") or ""),
                                b,
                            )
                            st.session_state[status_key] = {
                                "state": "captured",
                                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "detail": saved_path,
                            }
                        elif e:
                            st.session_state[status_key] = {
                                "state": "error",
                                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "detail": str(e),
                            }
                            st.warning(e)
                cache_b = st.session_state.get(cache_key, b"") if excel_row > 0 else b""
                if isinstance(cache_b, (bytes, bytearray)) and len(cache_b) > 0:
                    img_bytes = cache_b
                    if status_key not in st.session_state:
                        st.session_state[status_key] = {
                            "state": "captured_cached",
                            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "detail": "Loaded from cached capture",
                        }

            status_obj = st.session_state.get(status_key, {}) if excel_row > 0 else {}
            if isinstance(img_bytes, (bytes, bytearray)) and len(img_bytes) > 0:
                st.image(img_bytes, caption=f"RFQ {rec.get('rfq_no','')} · BQMS {rec.get('bqms_code','')}", use_container_width=False)
                if status_obj:
                    st.caption(f"Image source: {status_obj.get('state','')} · {status_obj.get('ts','')}")
                    if status_obj.get("detail"):
                        st.caption(f"Saved file: {status_obj.get('detail','')}")
                else:
                    st.caption("Image source: embedded in worksheet")
            else:
                st.caption("No embedded image detected. Use capture button for this row.")
                if status_obj.get("state") == "error":
                    st.caption(f"Last capture error: {status_obj.get('detail','')[:240]}")

