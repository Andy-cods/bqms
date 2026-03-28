"""
Tool 5 — Market Price Search UI
=================================
Tab layout:
  [SEARCH]        → Input form + live progress + results
  [GIÁ ĐÃ CHỐT]  → Saved prices table + delete
"""

from __future__ import annotations

import json
import threading
import time
from typing import Optional

import streamlit as st

from tools.tool5_market_search.engine import (
    PLATFORM_CONFIG,
    SearchResult,
    delete_confirmed_price,
    get_confirmed_prices,
    init_market_tables,
    save_confirmed_price,
    search,
    to_usd,
)

# ─── CSS injected once ───────────────────────────────────────
_MARKET_CSS = """
<style>
.mkt-kpi-row { display:flex; gap:12px; margin-bottom:16px; flex-wrap:wrap; }
.mkt-kpi {
  flex:1; min-width:140px; background:var(--s2,#f5f0eb);
  border:1px solid var(--b2,#d4c9be); border-radius:8px;
  padding:12px 16px; text-align:center;
}
.mkt-kpi .val { font-size:1.5rem; font-weight:700; color:var(--green,#3c8c5a); font-family:var(--mono,'SF Mono',monospace); }
.mkt-kpi .lbl { font-size:0.72rem; color:var(--t2,#7a6a5a); margin-top:4px; text-transform:uppercase; letter-spacing:.06em; }
.verdict-badge {
  display:inline-block; padding:4px 14px; border-radius:20px;
  font-size:0.8rem; font-weight:700; letter-spacing:.05em;
  margin-bottom:16px;
}
.verdict-good   { background:#d4edda; color:#1a5e2f; }
.verdict-high   { background:#f8d7da; color:#721c24; }
.verdict-hard   { background:#fff3cd; color:#856404; }
.verdict-plenty { background:#d1ecf1; color:#0c5460; }
.verdict-stable { background:#e2d9f3; color:#432874; }
.sup-card {
  background:var(--s2,#faf6f1); border:1px solid var(--b2,#d4c9be);
  border-radius:10px; padding:14px 16px; margin-bottom:10px;
  position:relative;
}
.sup-card .sup-rank {
  position:absolute; top:10px; right:12px;
  font-size:0.7rem; color:var(--t2,#7a6a5a); font-family:var(--mono,'SF Mono',monospace);
}
.sup-card .sup-name  { font-weight:700; font-size:0.95rem; }
.sup-card .sup-price { font-size:1.1rem; font-weight:700; color:var(--green,#3c8c5a); font-family:var(--mono,'SF Mono',monospace); }
.sup-card .sup-meta  { font-size:0.78rem; color:var(--t2,#7a6a5a); margin-top:4px; }
.sup-card .sup-contact {
  margin-top:8px; font-size:0.76rem;
  background:var(--ga,#e8f4ea); border-radius:6px;
  padding:4px 10px; display:inline-block;
}
.rec-chip {
  display:inline-block; padding:3px 10px; border-radius:12px;
  font-size:0.72rem; font-weight:700; margin-left:8px;
}
.rec-chot   { background:#d4edda; color:#1a5e2f; }
.rec-xemxet { background:#fff3cd; color:#856404; }
.rec-boqua  { background:#f8d7da; color:#721c24; }
.score-bar { height:6px; border-radius:3px; background:#e0d8d0; margin-top:2px; }
.score-fill { height:6px; border-radius:3px; background:var(--green,#3c8c5a); }
.plat-row {
  display:flex; gap:8px; align-items:center; padding:8px 12px;
  border-bottom:1px solid var(--b1,#ede6df); font-size:0.83rem;
}
.plat-row:last-child { border-bottom:none; }
.plat-tag {
  font-size:0.7rem; font-weight:700; padding:2px 8px;
  border-radius:10px; background:var(--gb,#dceede); color:#1a5e2f;
  font-family:var(--mono,'SF Mono',monospace);
}
.stars { color:#e4a200; font-size:0.85rem; }
.progress-log {
  font-family:var(--mono,'SF Mono',monospace); font-size:0.75rem;
  background:var(--s1,#f9f4ef); border:1px solid var(--b1,#ede6df);
  border-radius:8px; padding:10px 14px; max-height:160px; overflow-y:auto;
  color:var(--t2,#7a6a5a);
}
.save-panel {
  background:var(--s2,#faf6f1); border:1px solid var(--b2,#d4c9be);
  border-radius:10px; padding:16px; margin-top:12px;
}
</style>
"""


def _verdict_html(verdict: str) -> str:
    mapping = {
        "GIÁ TỐT": ("verdict-good", "✅ GIÁ TỐT"),
        "GIÁ CAO": ("verdict-high", "⚠️ GIÁ CAO"),
        "KHÓ TÌM": ("verdict-hard", "🔍 KHÓ TÌM"),
        "DỒI DÀO": ("verdict-plenty", "📦 DỒI DÀO"),
        "GIÁ ỔN ĐỊNH": ("verdict-stable", "📊 GIÁ ỔN ĐỊNH"),
    }
    cls, label = mapping.get(verdict, ("verdict-stable", verdict or "N/A"))
    return f'<span class="verdict-badge {cls}">{label}</span>'


def _rec_chip(rec: str) -> str:
    mapping = {
        "CHỐT": ("rec-chot", "✅ CHỐT"),
        "XEM XÉT": ("rec-xemxet", "🟡 XEM XÉT"),
        "BỎ QUA": ("rec-boqua", "❌ BỎ QUA"),
    }
    cls, label = mapping.get(rec, ("rec-xemxet", rec))
    return f'<span class="rec-chip {cls}">{label}</span>'


def _stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n)


def _score_bar(score: float, max_score: float = 10.0) -> str:
    pct = min(100, int(score / max_score * 100))
    return (
        f'<div class="score-bar">'
        f'<div class="score-fill" style="width:{pct}%"></div>'
        f'</div>'
    )


# ─── Platform stats table ────────────────────────────────────

def _render_platform_stats(stats: list[dict]):
    if not stats:
        return
    st.markdown("**Hiệu quả theo nền tảng:**")
    html = '<div style="border:1px solid var(--b2,#d4c9be);border-radius:8px;overflow:hidden;margin-bottom:16px;">'
    html += (
        '<div class="plat-row" style="background:var(--b1,#ede6df);font-weight:700;">'
        '<span style="width:120px">Nền tảng</span>'
        '<span style="width:80px;text-align:center">Kết quả</span>'
        '<span style="width:80px;text-align:center">Match %</span>'
        '<span style="width:100px;text-align:center">Giá avg</span>'
        '<span style="flex:1;text-align:center">Hiệu quả giá</span>'
        '</div>'
    )
    for s in sorted(stats, key=lambda x: -x.get("price_index", 0)):
        platform = s.get("platform", "")
        label = PLATFORM_CONFIG.get(platform, {}).get("label", platform)
        ok = s.get("crawl_ok", True)
        verified = s.get("verified_count", 0)
        total = s.get("total_crawled", 0)
        match_rate = int(s.get("match_rate", 0) * 100)
        avg = s.get("avg_price_usd", 0)
        price_idx = s.get("price_index", 0)
        err = s.get("error_msg", "")

        status_tag = (
            f'<span class="plat-tag">{label}</span>'
            if ok else
            f'<span class="plat-tag" style="background:#f8d7da;color:#721c24">{label} ✗</span>'
        )
        price_str = f"${avg:.3f}" if avg else "—"
        stars_str = f'<span class="stars">{_stars(price_idx)}</span>' if price_idx else "—"
        result_str = f"{verified}/{total}" if ok else "—"
        match_str = f"{match_rate}%" if ok and total else "—"
        error_str = f' <span style="color:#721c24;font-size:0.7rem">{err[:60]}</span>' if err else ""

        html += (
            f'<div class="plat-row">'
            f'<span style="width:120px">{status_tag}</span>'
            f'<span style="width:80px;text-align:center">{result_str}</span>'
            f'<span style="width:80px;text-align:center">{match_str}</span>'
            f'<span style="width:100px;text-align:center;font-family:var(--mono,monospace)">{price_str}</span>'
            f'<span style="flex:1;text-align:center">{stars_str}{error_str}</span>'
            f'</div>'
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


# ─── Supplier evaluation cards ───────────────────────────────

def _render_evaluated_suppliers(evaluated: list[dict],
                                  top_suppliers: list[dict],
                                  save_cb):
    """Render evaluation cards with save button."""
    if not evaluated:
        if top_suppliers:
            st.info("Không có đánh giá Agent — hiển thị kết quả tổng hợp thô.")
            for s in top_suppliers[:5]:
                st.markdown(f"**{s.get('supplier_name','')}** | {s.get('platform','')} | ${s.get('price_usd',0):.3f}")
        return

    for ev in evaluated:
        name = ev.get("supplier_name", "—")
        platform = ev.get("platform", "")
        rec = ev.get("recommendation", "XEM XÉT")
        scores = ev.get("scores", {})
        total = ev.get("total_score", 0.0)
        action = ev.get("action", "")
        risks = ev.get("risks", [])
        contact_guide = ev.get("contact_guide", "")

        # find matching synthesis supplier for price/url
        sup_info = {}
        for ts in top_suppliers:
            if ts.get("supplier_name") == name or ts.get("platform") == platform:
                sup_info = ts
                break

        price_disp = sup_info.get("price_display", f"${sup_info.get('price_usd',0):.3f}")
        moq = sup_info.get("moq", 0)
        location = sup_info.get("location", "")
        url = sup_info.get("url", "")
        certs = sup_info.get("certifications", [])

        score_items = {
            "Giá cả": scores.get("price", 0),
            "Uy tín": scores.get("reliability", 0),
            "MOQ": scores.get("moq_fit", 0),
            "Địa điểm": scores.get("location", 0),
            "Chứng nhận": scores.get("certifications", 0),
        }

        card_html = f"""
        <div class="sup-card">
          <span class="sup-rank">#{ev.get('rank',0)} &nbsp; {total:.1f}/10</span>
          <div class="sup-name">{name} {_rec_chip(rec)}</div>
          <div class="sup-price">{price_disp}</div>
          <div class="sup-meta">
            <span class="plat-tag">{PLATFORM_CONFIG.get(platform,{}).get('label',platform)}</span>
            &nbsp;{location}
            {'&nbsp; | MOQ: ' + str(moq) if moq else ''}
            {'&nbsp; | ' + ', '.join(certs) if certs else ''}
          </div>
        """
        if contact_guide:
            card_html += f'<div class="sup-contact">💬 {contact_guide}</div>'
        if action:
            card_html += f'<div style="margin-top:8px;font-size:0.8rem">→ {action}</div>'
        card_html += "</div>"

        st.markdown(card_html, unsafe_allow_html=True)

        # score bars
        with st.expander(f"Điểm chi tiết — {name}", expanded=False):
            cols = st.columns(5)
            for i, (lbl, val) in enumerate(score_items.items()):
                with cols[i]:
                    st.markdown(f"**{lbl}**")
                    st.markdown(f"<div style='font-size:1.1rem;font-weight:700'>{val:.1f}</div>", unsafe_allow_html=True)
                    st.markdown(_score_bar(val), unsafe_allow_html=True)
            if risks:
                st.markdown("**Rủi ro:** " + " | ".join(f"⚠ {r}" for r in risks))
            if url:
                st.markdown(f"[🔗 Mở link]({url})")

        # Save button
        col_btn, col_empty = st.columns([2, 5])
        with col_btn:
            if rec in ("CHỐT", "XEM XÉT") and st.button(f"💾 Chốt giá · {name[:20]}", key=f"save_{name}_{platform}"):
                save_cb(sup_info, ev)


# ─── Save price modal ────────────────────────────────────────

def _save_price_modal(sup_info: dict, ev_info: dict, db_path: str,
                       default_spec: str, default_maker: str, default_bqms: str):
    st.markdown('<div class="save-panel">', unsafe_allow_html=True)
    st.markdown(f"### 💾 Chốt giá: {sup_info.get('supplier_name','')}")

    c1, c2, c3 = st.columns(3)
    with c1:
        bqms_code = st.text_input("Mã BQMS", value=default_bqms, key="sp_bqms")
    with c2:
        product_name = st.text_input("Tên sản phẩm", value=default_spec[:60], key="sp_name")
    with c3:
        maker = st.text_input("Maker", value=default_maker, key="sp_maker")

    c4, c5, c6 = st.columns(3)
    with c4:
        price_val = st.number_input("Giá xác nhận", min_value=0.0,
                                     value=float(sup_info.get("price_usd", 0)),
                                     format="%.4f", key="sp_price")
    with c5:
        currency = st.selectbox("Đơn tiền", ["USD", "CNY", "TWD", "VND"], key="sp_cur")
    with c6:
        moq = st.number_input("MOQ", min_value=0, value=int(sup_info.get("moq", 0)), key="sp_moq")

    notes = st.text_area("Ghi chú", height=60, key="sp_notes",
                          placeholder="Điều kiện thanh toán, lead time, mẫu hàng...")

    col_save, col_cancel = st.columns([1, 4])
    with col_save:
        if st.button("✅ Lưu", key="sp_confirm", type="primary"):
            save_confirmed_price({
                "bqms_code": bqms_code,
                "product_name": product_name,
                "spec": st.session_state.get("mkt_spec", ""),
                "maker": maker,
                "confirmed_price": price_val,
                "currency": currency,
                "supplier_name": sup_info.get("supplier_name", ""),
                "supplier_url": sup_info.get("url", ""),
                "platform": sup_info.get("platform", ""),
                "moq": moq,
                "notes": notes,
            }, db_path)
            st.success("Đã lưu giá thành công!")
            st.session_state["mkt_save_target"] = None
            st.rerun()
    with col_cancel:
        if st.button("Hủy", key="sp_cancel"):
            st.session_state["mkt_save_target"] = None
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# ─── Saved Prices tab ────────────────────────────────────────

def _render_saved_prices(db_path: str):
    st.markdown("### 📂 Giá Đã Chốt")

    col_filter, col_refresh = st.columns([3, 1])
    with col_filter:
        filter_code = st.text_input("Lọc theo BQMS Code", placeholder="Để trống = tất cả",
                                     key="saved_filter")
    with col_refresh:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh", key="saved_refresh"):
            st.rerun()

    rows = get_confirmed_prices(filter_code.strip(), db_path)
    if not rows:
        st.info("Chưa có giá nào được chốt.")
        return

    st.caption(f"{len(rows)} mục — Click ✗ để xoá")

    for r in rows:
        cols = st.columns([1.2, 2, 1.2, 1.5, 1.5, 1, 0.5])
        with cols[0]:
            st.markdown(f"**{r.get('bqms_code') or '—'}**")
        with cols[1]:
            st.markdown(r.get("product_name", "")[:50])
        with cols[2]:
            p = r.get("confirmed_price", 0)
            cur = r.get("currency", "USD")
            st.markdown(f"**{p:.3f} {cur}**")
        with cols[3]:
            st.markdown(r.get("supplier_name", "")[:30])
        with cols[4]:
            platform = r.get("platform", "")
            label = PLATFORM_CONFIG.get(platform, {}).get("label", platform)
            st.markdown(f'<span class="plat-tag">{label}</span>', unsafe_allow_html=True)
        with cols[5]:
            st.markdown(r.get("confirmed_at", "")[:10])
        with cols[6]:
            if st.button("✗", key=f"del_{r['id']}", help="Xoá"):
                delete_confirmed_price(r["id"], db_path)
                st.rerun()


# ─── Main render function ─────────────────────────────────────

def render_tool5_tab(db_path: str = "./bsmq.db"):
    # init tables
    try:
        init_market_tables(db_path)
    except Exception:
        pass

    st.markdown(_MARKET_CSS, unsafe_allow_html=True)

    st_tab_search, st_tab_saved = st.tabs(["🔍 Tìm Kiếm Giá", "📂 Giá Đã Chốt"])

    # ─── SEARCH TAB ───
    with st_tab_search:
        st.markdown("## Market Price Search")
        st.caption("Tìm giá từ Alibaba · 1688 · Taiwantrade · Ruten · Xác minh sản phẩm · Đánh giá Agent")

        # ── Input form ──
        with st.form("mkt_search_form"):
            c1, c2 = st.columns([3, 2])
            with c1:
                spec = st.text_area(
                    "Spec sản phẩm *",
                    placeholder="VD: Resistor 10kΩ 0402 1% 1/16W SMD\nhoặc mô tả bằng tiếng Việt",
                    height=80,
                    key="mkt_spec",
                )
            with c2:
                maker = st.text_input("Maker / Brand", placeholder="VD: Samsung, Vishay, Yageo...", key="mkt_maker")
                bqms_code = st.text_input("Mã BQMS (nếu có)", placeholder="VD: RC0402FR-0710KL", key="mkt_bqms")

            c3, c4, c5 = st.columns(3)
            with c3:
                budget_usd = st.number_input("Ngân sách tham khảo (USD)",
                                              min_value=0.0, value=0.0, format="%.4f", key="mkt_budget")
            with c4:
                max_per_platform = st.slider("Kết quả / nền tảng", 10, 40, 20, 5, key="mkt_max")
            with c5:
                use_cache = st.toggle("Dùng cache (< 24h)", value=True, key="mkt_cache")

            st.markdown("**Nền tảng:**")
            pcol1, pcol2, pcol3, pcol4 = st.columns(4)
            with pcol1:
                p_alibaba = st.checkbox("Alibaba.com", value=True, key="p_ali")
            with pcol2:
                p_1688 = st.checkbox("1688.com", value=True, key="p_1688")
            with pcol3:
                p_taiwantrade = st.checkbox("Taiwantrade.com", value=True, key="p_tw")
            with pcol4:
                p_ruten = st.checkbox("Ruten.com.tw", value=True, key="p_ruten")

            submitted = st.form_submit_button("🔍 Bắt đầu tìm kiếm", type="primary",
                                               use_container_width=True)

        if not submitted and "mkt_result" not in st.session_state:
            st.markdown("""
            <div style="text-align:center;padding:40px;color:var(--t2,#7a6a5a);">
              <div style="font-size:2rem">🌐</div>
              <div style="margin-top:8px">Nhập thông tin sản phẩm và chọn nền tảng để bắt đầu</div>
              <div style="font-size:0.8rem;margin-top:4px">
                Hệ thống sẽ crawl ≥20 kết quả/nền tảng, xác minh sản phẩm và đánh giá nhà cung cấp
              </div>
            </div>
            """, unsafe_allow_html=True)

        if submitted:
            if not spec.strip():
                st.error("Vui lòng nhập Spec sản phẩm")
            else:
                platforms = []
                if p_alibaba:
                    platforms.append("alibaba")
                if p_1688:
                    platforms.append("1688")
                if p_taiwantrade:
                    platforms.append("taiwantrade")
                if p_ruten:
                    platforms.append("ruten")

                if not platforms:
                    st.error("Chọn ít nhất 1 nền tảng")
                else:
                    # ── Run search ──
                    st.session_state["mkt_result"] = None
                    log_placeholder = st.empty()
                    progress_bar = st.progress(0)
                    progress_messages = []

                    def _progress(msg: str):
                        progress_messages.append(msg)
                        log_html = '<div class="progress-log">' + "<br>".join(
                            f"▸ {m}" for m in progress_messages[-15:]
                        ) + "</div>"
                        log_placeholder.markdown(log_html, unsafe_allow_html=True)

                    # Update progress bar heuristically
                    progress_steps = [0.05, 0.15, 0.50, 0.70, 0.85, 0.95, 1.0]
                    step_idx = [0]

                    def _cb(msg: str):
                        _progress(msg)
                        if step_idx[0] < len(progress_steps):
                            progress_bar.progress(progress_steps[step_idx[0]])
                            step_idx[0] += 1

                    with st.spinner("Đang tìm kiếm..."):
                        result = search(
                            spec=spec.strip(),
                            maker=maker.strip(),
                            bqms_code=bqms_code.strip(),
                            budget_usd=float(budget_usd),
                            platforms=platforms,
                            max_per_platform=max_per_platform,
                            use_cache=use_cache,
                            db_path=db_path,
                            progress_cb=_cb,
                        )

                    progress_bar.progress(1.0)
                    st.session_state["mkt_result"] = result
                    log_placeholder.empty()
                    progress_bar.empty()

        # ── Display results ──
        result: Optional[SearchResult] = st.session_state.get("mkt_result")
        if result is None:
            pass
        else:
            synthesis = result.synthesis or {}
            evaluation = result.evaluation or {}
            platform_stats = result.platform_stats or []
            top_suppliers = synthesis.get("top_suppliers", [])
            evaluated = evaluation.get("evaluated_suppliers", [])
            price_analysis = synthesis.get("price_analysis", {})
            verdict = evaluation.get("market_verdict", "")
            final_pick = evaluation.get("final_pick", {})
            verified_results = result.verified_results or []

            if result.cache_used:
                st.caption("⚡ Kết quả từ cache")

            # ── KPI row ──
            total_found = sum(s.get("verified_count", 0) for s in platform_stats)
            total_sources = len([s for s in platform_stats if s.get("crawl_ok")])

            kpi_html = '<div class="mkt-kpi-row">'
            kpi_html += f'<div class="mkt-kpi"><div class="val">${price_analysis.get("min_usd", 0):.3f}</div><div class="lbl">Giá thấp nhất</div></div>'
            kpi_html += f'<div class="mkt-kpi"><div class="val">${price_analysis.get("typical_usd", 0):.3f}</div><div class="lbl">Giá phổ biến</div></div>'
            kpi_html += f'<div class="mkt-kpi"><div class="val">${price_analysis.get("max_usd", 0):.3f}</div><div class="lbl">Giá cao nhất</div></div>'
            kpi_html += f'<div class="mkt-kpi"><div class="val">{total_found}</div><div class="lbl">Kết quả hợp lệ</div></div>'
            kpi_html += f'<div class="mkt-kpi"><div class="val">{total_sources}</div><div class="lbl">Nguồn dữ liệu</div></div>'
            kpi_html += f'<div class="mkt-kpi"><div class="val">{result.total_duration_sec:.0f}s</div><div class="lbl">Thời gian</div></div>'
            kpi_html += "</div>"
            st.markdown(kpi_html, unsafe_allow_html=True)

            # ── Verdict + Summary ──
            if verdict:
                st.markdown(_verdict_html(verdict), unsafe_allow_html=True)
            if synthesis.get("market_summary"):
                st.info(synthesis["market_summary"])

            # ── Platform Stats ──
            _render_platform_stats(platform_stats)

            # ── Results columns ──
            col_left, col_right = st.columns([3, 2])

            with col_left:
                st.markdown("### Đánh giá Nhà Cung Cấp")

                def _save_cb(sup_info, ev_info):
                    st.session_state["mkt_save_target"] = (sup_info, ev_info)
                    st.rerun()

                _render_evaluated_suppliers(evaluated, top_suppliers, _save_cb)

            with col_right:
                st.markdown("### Kết luận Agent")
                if final_pick:
                    st.markdown(f"**Tốt nhất tổng thể:** {final_pick.get('best_overall','—')}")
                    st.markdown(f"**Giá tốt nhất:** {final_pick.get('best_price','—')}")
                    st.markdown(f"**Uy tín nhất:** {final_pick.get('best_reliability','—')}")
                    if final_pick.get("rationale"):
                        st.markdown(f"> {final_pick['rationale']}")
                    if final_pick.get("next_steps"):
                        st.markdown("**Bước tiếp theo:**")
                        for step in final_pick["next_steps"]:
                            st.markdown(f"- {step}")

                st.markdown("---")
                # Show unverified counts
                keep_c = len([r for r in verified_results if r.get("status") == "keep"])
                review_c = len([r for r in verified_results if r.get("status") == "review"])
                discard_c = len([r for r in verified_results if r.get("status") == "discard"])
                st.markdown(f"**Xác minh sản phẩm:**")
                st.markdown(f"- ✅ Khớp chắc chắn: **{keep_c}**")
                st.markdown(f"- 🟡 Cần xem lại: **{review_c}**")
                st.markdown(f"- ❌ Loại bỏ: **{discard_c}**")

                # query info
                qi = result.query_params.get("query_info", {})
                if qi:
                    with st.expander("🔑 Từ khóa đã dùng", expanded=False):
                        st.markdown(f"**EN:** `{qi.get('en_query','')}`")
                        st.markdown(f"**ZH:** `{qi.get('zh_query','')}`")
                        if qi.get("key_specs"):
                            st.markdown("**Specs:** " + ", ".join(qi["key_specs"]))
                        if qi.get("negative_keywords"):
                            st.markdown("**Loại trừ:** " + ", ".join(qi["negative_keywords"]))

                # Raw data expander
                with st.expander(f"📋 Dữ liệu thô ({len(verified_results)} kết quả)", expanded=False):
                    keep_results = [r for r in verified_results if r.get("status") in ("keep", "review")]
                    for r in keep_results[:30]:
                        confidence = r.get("match_confidence", 0)
                        conf_color = "#1a5e2f" if confidence >= 0.7 else "#856404"
                        platform = r.get("platform", "")
                        label = PLATFORM_CONFIG.get(platform, {}).get("label", platform)
                        url = r.get("url", "")
                        title = r.get("title", "")[:60]
                        price_text = r.get("price_text", "")
                        supplier = r.get("supplier_name", "")[:25]
                        url_tag = f' <a href="{url}" target="_blank">[link]</a>' if url else ""
                        st.markdown(
                            f'<div style="font-size:0.78rem;border-bottom:1px solid #e0d8d0;padding:4px 0">'
                            f'<span class="plat-tag">{label}</span>&nbsp;'
                            f'{title}{url_tag}<br>'
                            f'<span style="color:var(--green,#3c8c5a);font-family:monospace">{price_text}</span>'
                            f'&nbsp;|&nbsp;{supplier}'
                            f'&nbsp;|&nbsp;<span style="color:{conf_color}">{int(confidence*100)}% match</span>'
                            f'</div>',
                            unsafe_allow_html=True
                        )

            # ── Save modal ──
            save_target = st.session_state.get("mkt_save_target")
            if save_target:
                sup_info, ev_info = save_target
                _save_price_modal(
                    sup_info, ev_info, db_path,
                    default_spec=result.query_params.get("spec", ""),
                    default_maker=result.query_params.get("maker", ""),
                    default_bqms=result.query_params.get("bqms_code", ""),
                )

    # ─── SAVED PRICES TAB ───
    with st_tab_saved:
        _render_saved_prices(db_path)
