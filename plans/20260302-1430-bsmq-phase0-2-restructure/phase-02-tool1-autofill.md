# Phase 02 — Tool 1 Auto Fill (Complete)

**Context:** [plan.md](./plan.md) | Depends on: [Phase 00](./phase-00-project-restructure.md), [Phase 01](./phase-01-database-layer.md)
**Date:** 2026-03-02 | **Priority:** HIGH — daily-use tool
**Status:** ⬜ Pending | **Review:** ⬜ Not reviewed

---

## Overview

Extract logic from monolith `app.py` (1567 LOC) into:
- `tools/tool1_autofill/engine.py` — pure logic, zero Streamlit deps
- `tools/tool1_autofill/app.py` — Streamlit UI, imports engine
- `app.py` — new shell with 5 tabs (Tool 1 lives in Tab 1)

---

## Key Insights

- **Current app.py already has working logic** — extraction, not rewrite:
  - `parse_bc_bqms()` → lines ~340–530
  - `fill_cam_ket()` → lines ~760–950
  - `fill_quotation()` → lines ~950–1180
  - `process_orders()` → lines ~1275–1360
  - Image handling → lines ~540–620
- **Template cells verified from existing code:**
  - CAM_KET: rows 16–18 per product, 3-row merged blocks
  - QUOTATION: header at C4/H6/C7/A14, data rows from 17
- **GC = disabled** — existing code already filters GC orders
- **Unit Price = empty** — existing code already leaves H/L cells blank
- **New app.py shell** replaces current app.py — Tab 1 embeds Tool 1 UI
- Design system: MUST match BSMQ Dashboard v4 CSS variables exactly

---

## Requirements

**Functional (from Acceptance Criteria):**
1. Upload BC BQMS → correct order list displayed
2. GC orders: disabled checkbox + tooltip "Gia công — chưa hỗ trợ"
3. TM orders: enabled checkbox
4. Select 1 TM order → creates 2 Excel + 2 PDF in `outputs/QT.../`
5. CAM_KET: BQMS/Spec/Maker correct, Unit Price empty, date filled
6. QUOTATION: RFQ No/Items/Qty correct, Unit Price empty, Amount formula
7. Files saved to `[rfq_folder]/[QT26XXXXXX]/` OR `./outputs/QT26XXXXXX/`
8. 3 orders simultaneously → 3 separate folders
9. Deadline <24h → red highlight + ⚠️ warning badge
10. Image auto-match by filename containing BQMS code

**Non-functional:**
- `engine.py` has ZERO `import streamlit` lines
- PDF export via LibreOffice; graceful degradation if not installed
- Progress callback pattern — engine reports to UI without coupling
- Template files NEVER modified — always copy to output first

---

## Architecture

### engine.py (Pure Logic)

```python
"""
No Streamlit. Returns data, paths, dicts.
Called by tools/tool1_autofill/app.py (UI) and future CLI/batch scripts.
"""

# Types
@dataclass
class OrderItem:
    rfq_no: str         # QT26015802
    bqms_code: str      # Z0000002-258685
    spec: str
    short_name: str     # Tên ngắn tiếng Việt
    loai_hang: str      # 'gc' | 'tm'
    maker: str
    unit: str           # EA
    so_luong: float
    han_bg: str         # raw "2/4 17h"
    han_bg_dt: datetime | None
    is_urgent: bool     # deadline < 24h

@dataclass
class JobResult:
    rfq_no: str
    success: bool
    files: list[str]    # output file paths
    error: str | None
    duration_s: float

# Functions
def parse_bc_bqms(file_input) -> pd.DataFrame          # file path or bytes
def classify_loai_hang(val: str) -> str                 # 'gc'|'tm'|'unknown'
def sanitize_filename(name: str) -> str                 # remove /\:*?"<>|
def match_images_to_orders(image_files, df) -> dict     # {code: bytes}
def fill_cam_ket(orders, template_path, output_path, img_map) -> str
def fill_commercial_quotation(orders, rfq_no, template_path, output_path, img_map) -> str
def export_pdf(xlsx_path, output_dir, libreoffice_path) -> str | None
def create_output_folder(base_path, rfq_no, on_conflict='version') -> str
def run_auto_fill_job(order_group, config, img_map, progress_callback=None) -> JobResult
```

### tools/tool1_autofill/app.py (UI Layer)

```
render_tool1_tab()  ← called by main app.py Tab 1
  ├── step 1: config check (rfq_folder path)
  ├── step 2: upload BC BQMS → parse → show metrics
  ├── step 3: order selection (TM enabled, GC disabled + tooltip)
  ├── step 4: image upload (optional) + auto-match table
  ├── step 5: review & confirm (summary table + options)
  └── step 6: run + live progress (st.empty loop)
```

### app.py (New Shell)

```python
# 5 tabs
tab_dashboard, tab_bidding, tab_database, tab_analytics, tab_system = st.tabs([...])

with tab_dashboard:
    from tools.tool1_autofill.app import render_tool1_tab
    render_tool1_tab()

with tab_database:
    # FTS5 search bar + filter pills + table
    from modules.database import search_products, get_db_stats, init_sqlite_db
    # render inline

with tab_bidding, tab_analytics, tab_system:
    # Placeholder "Coming soon" styled card
```

---

## Related Code Files

| File | Action | Notes |
|------|--------|-------|
| `app.py` | Full rewrite | New 5-tab shell |
| `tools/tool1_autofill/engine.py` | Create | Logic extracted from old app.py |
| `tools/tool1_autofill/app.py` | Create | UI extracted from old app.py |
| `db_monitor.py` | Keep | Old app.py imports it (deprecated) |
| `watcher.py` | Keep | Old app.py imports it (deprecated) |

> **Backup:** Copy old `app.py` → `app_v1_backup.py` before rewriting

---

## Implementation Steps

### Step 1 — Backup old app.py
```bash
cp app.py app_v1_backup.py
```

### Step 2 — Create `tools/tool1_autofill/engine.py`

Extract from old app.py (DO NOT rewrite from scratch — extract + clean):

**2a. Copy these functions verbatim, then remove Streamlit deps:**
- `parse_bc_bqms()` (lines ~340–530) — already pure logic, keep as-is
- `match_images_to_orders()` (lines ~540–620) — already pure, keep as-is
- `fill_cam_ket()` (lines ~760–950) — remove any `st.` calls if any
- `fill_quotation()` (lines ~950–1180) — same
- PDF export logic (lines ~1180–1230) — wrap in `export_pdf()`

**2b. Add new wrapper function `run_auto_fill_job()`:**
```python
def run_auto_fill_job(order_group: list[OrderItem], config: dict,
                      img_map: dict, progress_callback=None) -> JobResult:
    """
    1. create_output_folder(config['rfq_folder'], rfq_no)
    2. fill_cam_ket(orders, cam_ket_template, output_cam_ket, img_map)
       → progress_callback(1, 4, "Đang điền cam kết...")
    3. fill_commercial_quotation(orders, rfq_no, quotation_template, output_q, img_map)
       → progress_callback(2, 4, "Đang điền báo giá...")
    4. export_pdf(cam_ket_path, output_dir, libreoffice_path)
       → progress_callback(3, 4, "Đang xuất PDF...")
    5. export_pdf(quotation_path, output_dir, libreoffice_path)
       → progress_callback(4, 4, "Hoàn thành")
    """
```

**2c. Add `create_output_folder()`:**
```python
def create_output_folder(base_path, rfq_no, on_conflict='version') -> str:
    folder = os.path.join(base_path, rfq_no)
    if not os.path.exists(folder):
        os.makedirs(folder)
        return folder
    if on_conflict == 'version':
        for i in range(2, 10):
            candidate = f"{folder}_v{i}"
            if not os.path.exists(candidate):
                os.makedirs(candidate)
                return candidate
    elif on_conflict == 'overwrite':
        return folder  # write into existing
    else:  # 'skip'
        return None
    return folder
```

### Step 3 — Create `tools/tool1_autofill/app.py`

**3a. Dark theme CSS injection** (top of file):
```python
DARK_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=DM+Sans:wght@400;600;700;800&display=swap');
:root {
  --bg: #060709; --s1: #0c1018; --s2: #111820; --s3: #161f2c;
  --b1: #1c2840; --b2: #243350;
  --green: #0fe87a; --yellow: #fbbf24; --red: #f43f5e; --blue: #38bdf8;
  --cyan: #22d3ee; --orange: #fb923c; --violet: #818cf8; --pink: #e879f9;
  --text: #dde8f8; --t2: #7a90b0; --t3: #3a5070;
}
.stApp { background: var(--bg) !important; color: var(--text); }
.stApp > header { background: var(--s1) !important; }
[data-testid="stSidebar"] { background: var(--s1) !important; border-right: 1px solid var(--b1); }
/* Buttons */
.stButton > button {
  background: var(--s2); border: 1px solid var(--b2);
  color: var(--t2); font-family: 'IBM Plex Mono', monospace;
  border-radius: 6px; transition: all 0.15s;
}
.stButton > button:hover { border-color: var(--green); color: var(--green); }
/* DataFrames */
[data-testid="stDataFrame"] { background: var(--s1); border: 1px solid var(--b1); }
/* Metrics */
[data-testid="metric-container"] { background: var(--s1); border: 1px solid var(--b1); border-radius: 8px; padding: 12px; }
</style>
"""

def inject_css():
    st.markdown(DARK_CSS, unsafe_allow_html=True)
```

**3b. Order card HTML** for GC/TM display:
```python
def render_order_card(order: dict, is_selected: bool, idx: int) -> bool:
    """Returns new selection state"""
    loai = order.get('loai_hang', 'unknown')
    is_gc = loai == 'gc'
    badge_color = '#38bdf8' if is_gc else '#fb923c'
    badge_text = 'GC' if is_gc else 'TM'
    urgent = order.get('is_urgent', False)

    card_html = f"""
    <div style="background:{'#1c2840' if urgent else '#111820'};
                border-left: 3px solid {'#f43f5e' if urgent else badge_color};
                border-radius:8px; padding:12px; margin:4px 0;
                font-family:'IBM Plex Mono',monospace;">
      <div style="display:flex;justify-content:space-between">
        <span style="color:#dde8f8;font-weight:600">{order['rfq_no']} · {order.get('short_name','')}</span>
        <span style="background:{badge_color}22;color:{badge_color};
                     border:1px solid {badge_color}44;border-radius:4px;
                     padding:2px 8px;font-size:11px">{badge_text}</span>
      </div>
      <div style="color:#7a90b0;font-size:12px;margin-top:4px">
        BQMS: {order['bqms_code']} · Maker: {order.get('maker','')} · SL: {order.get('so_luong','')} {order.get('don_vi','EA')}
      </div>
      {'<div style="color:#f43f5e;font-size:11px">⚠️ Hạn < 24h: ' + str(order.get('han_bg','')) + '</div>' if urgent else ''}
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)

    if is_gc:
        st.checkbox(f"Chọn {order['rfq_no']}", value=False, disabled=True,
                    key=f"chk_{idx}", help="Gia công — chưa hỗ trợ")
        return False
    else:
        return st.checkbox(f"Chọn {order['rfq_no']}", value=is_selected, key=f"chk_{idx}")
```

**3c. Progress display with st.empty():**
```python
def run_with_progress(selected_orders, config, img_map):
    results = []
    placeholder = st.empty()
    progress_bar = st.progress(0)

    for i, order_group in enumerate(selected_orders):
        status_msgs = []

        def on_progress(step, total, msg):
            status_msgs.append(f"  Bước {step}/{total}: {msg}")
            with placeholder.container():
                st.markdown(f"⏳ **{order_group[0]['rfq_no']}** · Đang xử lý...")
                for m in status_msgs[-3:]:
                    st.caption(m)

        result = run_auto_fill_job(order_group, config, img_map, on_progress)
        results.append(result)
        progress_bar.progress((i + 1) / len(selected_orders))

    return results
```

**3d. main `render_tool1_tab()` function** — 6-step flow using `st.session_state`

### Step 4 — Create new `app.py` (Shell)

```python
"""BSMQ Automation System — Main Dashboard"""
import streamlit as st, os, sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="BSMQ System",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Dark theme
st.markdown(SHELL_CSS, unsafe_allow_html=True)

# 5 Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🏠 Dashboard",
    "⚔️ Bidding",
    "🗄️ Database",
    "📊 Analytics",
    "⚙️ System"
])

with tab1:
    from tools.tool1_autofill.app import render_tool1_tab
    render_tool1_tab()

with tab3:
    render_database_tab()   # inline: FTS5 search + filter pills + table

with tab2, tab4, tab5:
    st.markdown(coming_soon_card("Tab này sẽ được triển khai ở Phase 3+"))
```

**Database tab inline render:**
```python
def render_database_tab():
    from modules.database import search_products, get_db_stats, init_sqlite_db
    cfg = load_config()
    db_path = cfg.get('db_path', './bsmq.db')
    init_sqlite_db(db_path)  # idempotent

    # KPI row
    stats = get_db_stats(db_path)
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Tổng", stats['total'])
    col2.metric("Còn hạn ✅", stats['ok'])
    col3.metric("Hết hạn ⚠️", stats['expired'])
    col4.metric("Chưa có ❓", stats['none'])
    col5.metric("Query", f"{stats['query_ms']}ms")

    # Search + Filter
    col_s, col_f = st.columns([3, 1])
    q = col_s.text_input("🔍 Tìm kiếm FTS5...", placeholder="screw M4, Z0000...")
    type_f = col_f.selectbox("Loại", ["Tất cả", "GC", "TM"])

    type_map = {"GC": "gc", "TM": "tm", "Tất cả": None}
    results = search_products(db_path, q, type_filter=type_map[type_f])

    if results:
        st.dataframe(results, use_container_width=True)
    else:
        st.info("Chưa có dữ liệu. Chạy ETL để import dữ liệu lịch sử.")
```

### Step 5 — Validate Against Acceptance Criteria

```python
# Test script: test_tool1.py
# 1. Parse a sample BC BQMS file
# 2. Run fill_cam_ket with dummy data
# 3. Verify output files exist
# 4. Verify Unit Price cells are empty
# 5. Verify date cell is filled
```

---

## Todo List

- [ ] Backup `app.py` → `app_v1_backup.py`
- [ ] Create `tools/tool1_autofill/engine.py` (extract + clean from app_v1_backup.py)
- [ ] Add `run_auto_fill_job()` to engine.py
- [ ] Add `create_output_folder()` to engine.py
- [ ] Create `tools/tool1_autofill/app.py` (UI layer with dark theme CSS)
- [ ] Implement `render_order_card()` with GC disabled + tooltip
- [ ] Implement `run_with_progress()` using `st.empty()`
- [ ] Implement `render_tool1_tab()` 6-step flow
- [ ] Create new `app.py` shell (5 tabs)
- [ ] Implement `render_database_tab()` with FTS5 search
- [ ] Run acceptance criteria tests (8 criteria)
- [ ] Verify `streamlit run app.py` launches correctly

---

## Success Criteria

| # | Criterion | Test Method |
|---|-----------|-------------|
| 1 | Upload BC BQMS → correct order list | Upload sample file, check table |
| 2 | GC checkbox disabled + tooltip | Click GC order, verify disabled |
| 3 | Select 1 TM → 2 Excel + 2 PDF created | Run job, check outputs/ folder |
| 4 | CAM_KET Unit Price cell empty | Open output xlsx, check L16 |
| 5 | QUOTATION Unit Price empty, Amount formula | Open output xlsx, check H17, I17 |
| 6 | Files in correct output folder | Verify path `outputs/QT26.../` |
| 7 | 3 orders → 3 separate folders | Run 3 orders, check 3 folders |
| 8 | Deadline <24h → red highlight | Set han_bg to today+1h, check UI |

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Merged cell ranges changed | Medium | High | Read template with openpyxl, log actual merge ranges before filling |
| LibreOffice not installed | High | Low | Graceful skip: `if not os.path.exists(libre_path): skip PDF` |
| GC template in future | Low | Low | YAGNI — keep disabled for now |
| `st.rerun()` loop in progress display | Medium | Medium | Use `st.empty()` pattern, NOT `time.sleep` loops |
| Unicode in filenames (Vietnamese chars) | Medium | Medium | `sanitize_filename()` strips/replaces all non-ASCII |

---

## Security Considerations

- Template paths: validate they're inside `templates/` dir (prevent path traversal)
- Output paths: validate they're inside `outputs/` or configured `rfq_folder`
- LibreOffice subprocess: use list args (NOT shell=True)
- Image bytes: validate MIME type before inserting into Excel

---

## Next Steps

→ Phase 3: AI Classifier (Tool 3) + `modules/ai_classifier.py`
→ Phase 4: Google Sheets integration
