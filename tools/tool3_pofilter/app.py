"""
tools/tool3_pofilter/app.py
Tool 3 — PO Filter + AI Classifier UI.
3-panel layout: Left (upload+run) | Center (results) | Right (stats)
Called by main app.py via: render_tool3_tab()
"""

import os
import sys
import threading
from datetime import datetime

import streamlit as st

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, '..', '..'))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tools.tool3_pofilter.engine import (
    process_batch,
    calc_batch_stats,
    get_key_status,
    get_keys_count,
    load_filter_rules,
    save_filter_rules,
    log_classification_override,
)
from tools.tool1_autofill.engine import parse_bc_bqms

# ---------------------------------------------------------------------------
# CSS (reuse BSMQ v4 vars already injected by main app.py)
# ---------------------------------------------------------------------------

TOOL3_CSS = """
<style>
/* Tool 3: Decision cards (v5 vars) */
.dec-yes  { background:var(--ga); border-left:3px solid var(--green); border-radius:var(--r); padding:12px 14px; margin:6px 0; }
.dec-no   { background:var(--ra); border-left:3px solid var(--red);   border-radius:var(--r); padding:12px 14px; margin:6px 0; }
.dec-maybe{ background:var(--ya); border-left:3px solid var(--yellow);border-radius:var(--r); padding:12px 14px; margin:6px 0; }
.dec-err  { background:var(--s2); border-left:3px solid var(--b2);    border-radius:var(--r); padding:12px 14px; margin:6px 0; }

/* Confidence bar */
.conf-bar { height:4px; border-radius:2px; margin:6px 0; }

/* Key pill */
.key-pill {
  display:inline-flex; align-items:center; gap:4px;
  background:var(--s1); border:1px solid var(--b1);
  border-radius:12px; padding:3px 10px;
  font-family:var(--mono); font-size:9px; color:var(--t2);
  margin:2px;
}
.key-pill.ok   { border-color:var(--gb); color:var(--green); }
.key-pill.busy { border-color:var(--yb); color:var(--yellow); }
.key-pill.full { border-color:var(--rb); color:var(--red); }
</style>
"""


def _inject_css():
    st.markdown(TOOL3_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def _init_state():
    defaults = {
        't3_orders':     [],
        't3_results':    [],
        't3_running':    False,
        't3_progress':   0,
        't3_progress_msg': '',
        't3_done':       False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ---------------------------------------------------------------------------
# Decision card renderer
# ---------------------------------------------------------------------------

def _decision_card(result: dict, idx: int) -> None:
    fd  = result.get('final_decision', 'maybe')
    dec = result.get('decision', 'maybe')
    css = {'yes': 'dec-yes', 'no': 'dec-no', 'maybe': 'dec-maybe'}.get(fd, 'dec-err')

    icon    = {'yes': '✅', 'no': '❌', 'maybe': '❓'}.get(fd, '⚠️')
    label   = {'yes': 'THAM GIA', 'no': 'BỎ QUA', 'maybe': 'XEM LẠI'}.get(fd, 'LỖI')
    col_map = {'yes': '#0fe87a', 'no': '#f43f5e', 'maybe': '#fbbf24'}
    color   = col_map.get(fd, '#7a90b0')
    conf    = int(result.get('confidence', 0) * 100)

    overridden = result.get('overridden', False)
    ovr_badge  = (
        f'<span style="font-size:10px;color:#818cf8;'
        f'border:1px solid #818cf844;border-radius:4px;padding:1px 6px;margin-left:6px">'
        f'OVERRIDE</span>'
        if overridden else ''
    )

    price_hint = result.get('price_hint')
    ph_html    = (
        f'<div style="color:#fb923c;font-size:11px;margin-top:4px">'
        f'💰 Giá tham khảo: {price_hint}</div>'
        if price_hint else ''
    )

    st.markdown(f"""
    <div class="{css}">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <span style="font-family:'DM Sans',sans-serif;font-weight:700;font-size:13px;color:{color}">
            {icon} {label}
          </span>{ovr_badge}
          <span style="font-family:'IBM Plex Mono',monospace;font-size:12px;color:#dde8f8;margin-left:10px">
            {result.get('don_hang','')} · {(result.get('short_name','') or result.get('spec',''))[:35]}
          </span>
        </div>
        <span style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:{color}">
          {conf}%
        </span>
      </div>
      <div class="conf-bar" style="background:linear-gradient(to right,{color},{color}44);width:{conf}%"></div>
      <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#7a90b0;margin-top:4px">
        {result.get('reason','')[:120]}
      </div>
      {ph_html}
    </div>
    """, unsafe_allow_html=True)

    # Override buttons
    col_a, col_b, col_c = st.columns([1, 1, 2])
    opposite = 'no' if fd == 'yes' else 'yes'
    opp_lbl  = 'Override: Bỏ qua' if fd == 'yes' else 'Override: Tham gia'

    if col_a.button("Đồng ý", key=f"t3_ok_{idx}", use_container_width=True):
        pass  # No-op — already agreed

    if col_b.button(opp_lbl, key=f"t3_ovr_{idx}", type="secondary", use_container_width=True):
        results = st.session_state.t3_results
        results[idx]['final_decision'] = opposite
        results[idx]['overridden']     = True
        log_classification_override(
            results[idx].get('don_hang', f'#{idx}'),
            fd, opposite
        )
        st.rerun()

    if fd == 'maybe':
        if col_c.button("↗ Tham gia", key=f"t3_yes_{idx}", use_container_width=True):
            st.session_state.t3_results[idx]['final_decision'] = 'yes'
            st.session_state.t3_results[idx]['overridden']     = True
            log_classification_override(results[idx].get('don_hang',''), fd, 'yes')
            st.rerun()


# ---------------------------------------------------------------------------
# Key status display
# ---------------------------------------------------------------------------

def _render_key_status():
    try:
        statuses = get_key_status()
        if not statuses:
            st.markdown(
                '<div style="font-family:IBM Plex Mono,monospace;font-size:11px;color:#f43f5e">'
                '⚠️ Chưa có Gemini API key</div>',
                unsafe_allow_html=True
            )
            return

        pills_html = ''
        for s in statuses:
            rpm   = s['rpm']
            limit = s['limit']
            if not s['available']:
                cls = 'full'
            elif rpm > limit * 0.7:
                cls = 'busy'
            else:
                cls = 'ok'
            pills_html += (
                f'<span class="key-pill {cls}">Key #{s["index"]+1}: {rpm}/{limit}</span>'
            )
        st.markdown(f'<div>{pills_html}</div>', unsafe_allow_html=True)
    except Exception as e:
        st.caption(f"Key status error: {e}")


# ---------------------------------------------------------------------------
# Main render
# ---------------------------------------------------------------------------

def render_tool3_tab():
    _inject_css()
    _init_state()

    # ── Header ──────────────────────────────────────────────────────────
    st.markdown(
        '<div style="font-family:DM Sans,sans-serif;font-size:16px;font-weight:700;'
        'color:#818cf8;margin-bottom:4px">🤖 PO Filter · AI Classifier</div>',
        unsafe_allow_html=True
    )

    keys_n = get_keys_count()
    st.markdown(
        f'<div style="font-family:IBM Plex Mono,monospace;font-size:11px;color:#7a90b0">'
        f'{keys_n} Gemini key{"s" if keys_n!=1 else ""} cấu hình · '
        f'{keys_n * 55} rpm tổng</div>',
        unsafe_allow_html=True
    )
    st.markdown("---")

    # ── 3-column layout ──────────────────────────────────────────────────
    col_left, col_center, col_right = st.columns([1, 2, 1])

    # ── LEFT: Upload + Config ────────────────────────────────────────────
    with col_left:
        st.markdown(
            '<div style="font-family:IBM Plex Mono,monospace;font-size:12px;'
            'color:#7a90b0;margin-bottom:8px">📂 Upload BC BQMS</div>',
            unsafe_allow_html=True
        )

        uploaded = st.file_uploader(
            "BC BQMS file",
            type=['xlsx', 'xls'],
            key='t3_bc_upload',
            label_visibility='collapsed'
        )

        if uploaded:
            with st.spinner("Đọc file..."):
                orders = parse_bc_bqms(uploaded.read())
            if orders:
                st.session_state.t3_orders = orders
                st.session_state.t3_results = []
                st.session_state.t3_done    = False
                st.success(f"✅ {len(orders)} đơn")

        orders = st.session_state.t3_orders

        if orders:
            tm_cnt = sum(1 for o in orders if o.get('loai_hang') == 'TM')
            gc_cnt = sum(1 for o in orders if o.get('loai_hang') == 'GC')
            st.markdown(
                f'<div style="font-family:IBM Plex Mono,monospace;font-size:11px;color:#7a90b0">'
                f'TM: {tm_cnt} · GC: {gc_cnt} · Tổng: {len(orders)}</div>',
                unsafe_allow_html=True
            )

        st.markdown("---")

        # Key status
        st.markdown(
            '<div style="font-family:IBM Plex Mono,monospace;font-size:11px;'
            'color:#7a90b0;margin-bottom:4px">🔑 Gemini Keys</div>',
            unsafe_allow_html=True
        )
        _render_key_status()

        if keys_n == 0:
            st.warning("Chưa có API key.\nThêm GEMINI_KEY_1..4 vào .env")

        st.markdown("---")

        # Filter rules editor
        with st.expander("📋 Filter Rules", expanded=False):
            rules = load_filter_rules()
            rules_text = st.text_area(
                "Mỗi dòng 1 rule",
                value="\n".join(rules),
                height=150,
                key='t3_rules',
                label_visibility='collapsed'
            )
            if st.button("Lưu rules", key='t3_save_rules'):
                new_rules = [r.strip() for r in rules_text.splitlines() if r.strip()]
                save_filter_rules(new_rules)
                st.toast("Đã lưu rules", icon="✅")

        st.markdown("---")

        # Run button
        can_run = bool(orders) and keys_n > 0 and not st.session_state.t3_running

        if st.button(
            "▶ Chạy Classifier",
            type='primary',
            disabled=not can_run,
            key='t3_run',
            use_container_width=True
        ):
            st.session_state.t3_running  = True
            st.session_state.t3_progress = 0
            st.session_state.t3_results  = []
            st.session_state.t3_done     = False
            st.rerun()

        if not can_run and orders and keys_n == 0:
            st.caption("⚠️ Cần API key để chạy")

    # ── ACTUAL RUN (outside columns to avoid nesting issues) ─────────────
    if st.session_state.t3_running and not st.session_state.t3_done:
        orders = st.session_state.t3_orders
        prog   = st.progress(0)
        status = st.empty()

        results_acc = []

        def on_progress(current, total, order_id, result):
            pct = current / total if total > 0 else 0
            prog.progress(pct)
            dec = result.get("decision", "?")
            dec_color = "var(--green)" if dec == "yes" else "var(--red)" if dec == "no" else "var(--yellow)"
            status.markdown(
                f'<div style="font-family:var(--mono);font-size:9px;color:var(--t2)">'
                f'[{current}/{total}] {order_id} &rarr; '
                f'<span style="color:{dec_color}">{dec.upper()}</span></div>',
                unsafe_allow_html=True
            )
            results_acc.append({**orders[current-1], **result, 'overridden': False,
                                  'final_decision': result.get('decision','maybe')})

        try:
            final_results = process_batch(orders, progress_callback=on_progress)
            st.session_state.t3_results = final_results
        except Exception as e:
            st.error(f"Lỗi classifier: {e}")
            st.session_state.t3_results = results_acc

        st.session_state.t3_running = False
        st.session_state.t3_done    = True
        prog.empty()
        status.empty()
        st.rerun()

    # ── CENTER: Results ──────────────────────────────────────────────────
    with col_center:
        results = st.session_state.t3_results

        if not results and not st.session_state.t3_running:
            st.markdown(
                '<div style="text-align:center;padding:60px 20px;color:#3a5070;'
                'font-family:IBM Plex Mono,monospace;font-size:12px">'
                '🤖 Upload BC BQMS và nhấn "Chạy Classifier"<br><br>'
                'AI sẽ phân tích từng đơn và đề xuất tham gia/bỏ qua</div>',
                unsafe_allow_html=True
            )

        if st.session_state.t3_running:
            st.markdown(
                '<div style="text-align:center;padding:40px;color:#818cf8;'
                'font-family:IBM Plex Mono,monospace">⚡ Đang phân tích...</div>',
                unsafe_allow_html=True
            )

        if results:
            # Filter tabs
            filter_opt = st.radio(
                "Lọc",
                ["Tất cả", "✅ Tham gia", "❌ Bỏ qua", "❓ Xem lại"],
                horizontal=True,
                key='t3_result_filter',
                label_visibility='collapsed'
            )
            filter_map = {
                "Tất cả":      None,
                "✅ Tham gia": "yes",
                "❌ Bỏ qua":   "no",
                "❓ Xem lại":  "maybe",
            }
            filt = filter_map.get(filter_opt)

            filtered_idx = [
                i for i, r in enumerate(results)
                if filt is None or r.get('final_decision') == filt
            ]

            for i in filtered_idx:
                _decision_card(results[i], i)

    # ── RIGHT: Stats ─────────────────────────────────────────────────────
    with col_right:
        results = st.session_state.t3_results
        stats   = calc_batch_stats(results) if results else {}

        st.markdown(
            '<div style="font-family:IBM Plex Mono,monospace;font-size:12px;'
            'color:#7a90b0;margin-bottom:8px">📊 Thống kê</div>',
            unsafe_allow_html=True
        )

        if stats:
            def _stat_row(label, value, color):
                return (
                    f'<div style="display:flex;justify-content:space-between;'
                    f'font-family:IBM Plex Mono,monospace;font-size:12px;'
                    f'padding:4px 0;border-bottom:1px solid #1c2840">'
                    f'<span style="color:#7a90b0">{label}</span>'
                    f'<span style="color:{color};font-weight:600">{value}</span></div>'
                )

            st.markdown(
                _stat_row("Tổng",     stats.get('total', 0),   '#dde8f8') +
                _stat_row("✅ Tham gia", stats.get('yes', 0),  '#0fe87a') +
                _stat_row("❌ Bỏ qua",  stats.get('no', 0),   '#f43f5e') +
                _stat_row("❓ Xem lại", stats.get('maybe', 0), '#fbbf24') +
                _stat_row("⚠️ Lỗi",    stats.get('errors', 0), '#818cf8') +
                _stat_row("Avg conf", f"{stats.get('avg_confidence',0)}%", '#38bdf8'),
                unsafe_allow_html=True
            )

            st.markdown("<br>", unsafe_allow_html=True)

            if results:
                # Export summary button
                if st.button("📋 Export kết quả", key='t3_export', use_container_width=True):
                    _export_results(results)

        else:
            st.markdown(
                '<div style="color:#3a5070;font-family:IBM Plex Mono,monospace;font-size:11px">'
                'Chưa có kết quả</div>',
                unsafe_allow_html=True
            )

        st.markdown("---")

        # Key status in right panel
        st.markdown(
            '<div style="font-family:IBM Plex Mono,monospace;font-size:11px;'
            'color:#7a90b0;margin-bottom:4px">🔑 API Keys</div>',
            unsafe_allow_html=True
        )
        _render_key_status()


# ---------------------------------------------------------------------------
# Export helper
# ---------------------------------------------------------------------------

def _export_results(results: list) -> None:
    """Export classification results as CSV download."""
    import csv
    import io

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[
        'don_hang', 'bqms', 'spec', 'maker', 'so_luong', 'han_bg',
        'final_decision', 'confidence', 'reason', 'similar_wins', 'price_hint', 'overridden'
    ])
    writer.writeheader()
    for r in results:
        writer.writerow({
            'don_hang':       r.get('don_hang', ''),
            'bqms':           r.get('bqms', ''),
            'spec':           (r.get('spec', '') or '')[:100],
            'maker':          r.get('maker', ''),
            'so_luong':       r.get('so_luong', ''),
            'han_bg':         r.get('han_bg', ''),
            'final_decision': r.get('final_decision', ''),
            'confidence':     f"{int(r.get('confidence', 0) * 100)}%",
            'reason':         r.get('reason', ''),
            'similar_wins':   r.get('similar_wins', 0),
            'price_hint':     r.get('price_hint', ''),
            'overridden':     r.get('overridden', False),
        })

    fname = f"po_filter_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    st.download_button(
        "⬇ Download CSV",
        data=buf.getvalue().encode('utf-8-sig'),  # UTF-8 BOM for Excel
        file_name=fname,
        mime='text/csv',
        key='t3_dl_csv',
        use_container_width=True
    )
