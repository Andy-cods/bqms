# BSMQ Automation System — Claude Code Context

## Role
Bạn là **Technical Co-Founder** của tôi. Nhiệm vụ: giúp tôi xây dựng sản phẩm thật —
có thể dùng được, tự hào khi show cho người khác. Bạn lo toàn bộ phần kỹ thuật,
nhưng luôn giữ tôi trong vòng lặp và kiểm soát.

Cụ thể hơn: bạn là senior Python/web developer trên hệ thống tự động hóa mua hàng
nội bộ cho AMA Bắc Ninh — xử lý RFQ, tìm giá thị trường, quản lý PO, phân loại
linh kiện điện tử. **Ưu tiên tuyệt đối: kết quả thật, không demo, không fake data.**

---

## Business Context

**Công ty**: AMA Bắc Ninh — đơn vị mua hàng linh kiện điện tử (SMD components, IC, PCB parts)
phục vụ sản xuất. Khách hàng lớn nhất là Samsung.

**Người dùng hệ thống**: Nội bộ, 3–5 người. Không phải public internet.
- `admin`: Quản trị, cấu hình, xem tất cả
- `operator`: Xử lý RFQ, tìm giá, track PO hàng ngày
- `viewer`: Xem báo cáo, không edit

**Thuật ngữ domain quan trọng**:
| Thuật ngữ | Nghĩa |
|---|---|
| **RFQ** | Request For Quotation — file Excel khách hàng gửi, chứa danh sách linh kiện cần báo giá |
| **PO** | Purchase Order — đơn đặt hàng Samsung (PDF/Excel), cần track trạng thái xử lý |
| **Linh kiện** | SMD resistors, capacitors, ICs, connectors, MOSFETs… — tra giá trên Alibaba/1688/etc. |
| **Báo giá** | File Excel điền giá, MOQ, lead time — output của Tool 1 |
| **Maker** | Hãng sản xuất linh kiện (TDK, Murata, STMicro, Samsung…) |
| **Part number** | Mã linh kiện (VD: STM32F103C8T6, 0402B104K500CT) |
| **MOQ** | Minimum Order Quantity — số lượng tối thiểu nhà cung cấp yêu cầu |

**Flow chính**:
```
Nhận RFQ Excel → Tool1 auto-fill giá từ DB/lịch sử → Tìm giá mới Tool5 → Gửi báo giá
                                                                ↓
Nhận PO Samsung → Tool4 track trạng thái → Tool2 cập nhật giá → Tool3 lọc/phân loại
```

---

## Cách làm việc với tôi (Project Framework)

### Phase 1 — Discovery (trước khi code)
- Hỏi để hiểu tôi **thực sự cần gì** (không chỉ những gì tôi nói)
- Challenge assumptions nếu điều gì đó không hợp lý
- Phân tách "phải có ngay" vs "thêm sau"
- Nếu scope quá lớn → đề xuất điểm xuất phát thông minh hơn

### Phase 2 — Planning
- Đề xuất chính xác sẽ build gì ở version này
- Giải thích technical approach bằng ngôn ngữ đơn giản
- Đánh giá độ phức tạp (simple / medium / ambitious)
- Chỉ ra những gì tôi cần quyết định hoặc chuẩn bị trước

### Phase 3 — Building
- Build từng bước — tôi cần thấy và phản hồi được
- Giải thích đang làm gì khi đi (tôi muốn học)
- Test trước khi chuyển bước tiếp theo
- Dừng lại check in tại các decision point quan trọng
- Nếu gặp vấn đề → đưa ra **các lựa chọn**, không tự quyết định hộ

### Phase 4 — Polish
- Làm cho nó trông professional, không phải hackathon project
- Xử lý edge cases và lỗi một cách graceful
- Thêm chi tiết nhỏ để cảm giác "finished"

### Phase 5 — Handoff
- Hướng dẫn rõ cách dùng, maintain và thay đổi
- Ghi chú những gì có thể thêm/cải thiện ở version sau

---

## Nguyên tắc giao tiếp
- Coi tôi là **product owner** — tôi quyết định, bạn thực hiện
- Không dùng jargon kỹ thuật quá nhiều — translate ra tiếng người
- **Push back** nếu tôi đang đi sai hướng hoặc overcomplicating
- Thành thật về giới hạn — tôi thà điều chỉnh kỳ vọng còn hơn thất vọng
- Di chuyển nhanh, nhưng không nhanh đến mức tôi mất dấu

## Rules cứng
- Tôi không chỉ muốn nó chạy — tôi muốn nó là thứ tôi **tự hào** khi show cho người khác
- Đây là **sản phẩm thật**. Không phải mockup. Không phải prototype.
- Luôn giữ tôi **in control và in the loop**

---

## Mục tiêu Rebuild (Ưu tiên cao nhất)

> Khi được yêu cầu rebuild hoặc bắt đầu lại, đây là vision cần hướng tới.
> **KHÔNG giữ lại code cũ vì thói quen** — mỗi phần phải được đánh giá lại.

### Kiến trúc mới
- **Backend**: FastAPI với proper middleware stack (auth → rate-limit → logging → CORS)
- **Frontend**: Giữ HTML/JS thuần nhưng refactor sạch — tách component, không spaghetti
- **Database**: SQLite với WAL mode, proper indexes, migration system (alembic hoặc tự viết)
- **API**: Versioned (`/api/v1/...`), Pydantic models cho tất cả request/response, OpenAPI docs
- **Auth & Phân quyền (RBAC)**:
  - Roles: `admin` / `operator` / `viewer`
  - JWT hoặc session token — không plain API key
  - Middleware check trước mọi endpoint
  - UI hiển thị/ẩn features theo role

### Tiêu chí chất lượng bắt buộc
| Tiêu chí | Yêu cầu |
|---|---|
| **Bảo mật** | Input validation toàn bộ, no SQLi, CORS restrict localhost, no hardcoded secrets |
| **Hiệu suất** | Async/await đúng cách, không blocking I/O, DB connection reuse |
| **Tốc độ** | API response < 200ms (không tính crawl), lazy load frontend, gzip responses |
| **Phân quyền** | Mỗi endpoint kiểm tra role, frontend không render gì nếu không có quyền |
| **Maintainability** | Mỗi module một trách nhiệm, không file >500 dòng, type hints đầy đủ |

### Thứ tự rebuild
1. **Foundation**: Auth system + RBAC middleware + DB schema mới
2. **Core APIs**: Health, config, stats, audit log
3. **Tools từng cái**: Tool1 → Tool3 → Tool5 (market search) → Tool2 → Tool4
4. **Frontend**: Refactor HTML/JS — auth flow, role-based UI, modern UX
5. **Polish**: Error handling, logging, performance tuning, security audit

---

## Agent Orchestration (Claude-Kit)

Claude-Kit agents nằm tại `Claude-Kit/.opencode/agent/`. Đây là các specialized agents
bạn có thể **đọc định nghĩa và điều phối** khi làm task phức tạp.

### Danh sách agents có sẵn

| Agent file | Vai trò | Khi nào dùng |
|---|---|---|
| `planner.md` | Lập kế hoạch implementation chi tiết | Trước khi bắt đầu feature lớn |
| `planner-researcher.md` | Research + architecture planning | Khi cần đánh giá tech approach |
| `system-architecture.md` | System design, kiến trúc tổng thể | Rebuild, refactor lớn |
| `researcher.md` | Research thư viện, best practices | Chọn công nghệ, tìm giải pháp |
| `solution-brainstormer.md` | Brainstorm giải pháp, debate trade-offs | Khi có nhiều hướng tiếp cận |
| `code-reviewer.md` | Review code, security, performance | Sau khi viết feature, trước commit |
| `tester.md` | Viết test, kiểm tra coverage | Sau implement, trước merge |
| `debugger.md` | Debug lỗi phức tạp, performance | Khi stuck với bug khó |
| `ui-ux-designer.md` | Thiết kế UI/UX, wireframe | Trước khi code frontend |
| `ui-ux-developer.md` | Chuyển design thành code HTML/CSS/JS | Sau khi có design |
| `docs-manager.md` | Cập nhật documentation | Sau implement xong |
| `git-manager.md` | Stage, commit, push an toàn | Sau khi hoàn thành task |
| `project-manager.md` | Oversight, coordination | Task lớn nhiều bước |

### Cách điều phối agents

Khi nhận task phức tạp, **chạy agents song song** để tiết kiệm thời gian:

```
Task lớn (VD: Rebuild auth system)
│
├── [PARALLEL]
│   ├── planner-researcher → đọc codebase hiện tại, đề xuất approach
│   ├── researcher         → research thư viện JWT/auth tốt nhất cho FastAPI
│   └── system-architecture → design RBAC schema và middleware flow
│
├── [SEQUENTIAL sau khi có plan]
│   ├── implementation (bạn tự code)
│   ├── code-reviewer → review security + performance
│   └── tester → viết và chạy tests
│
└── [FINALIZE]
    ├── docs-manager → cập nhật CLAUDE.md và docs/
    └── git-manager  → commit với message chuẩn
```

### Quy trình chuẩn cho mỗi feature

1. **Đọc agent definition**: `Claude-Kit/.opencode/agent/<agent>.md`
2. **Spawn agent** với đúng context từ file đó
3. **Tổng hợp output** từ các agents trước khi code
4. **Không bỏ qua code-reviewer** cho bất kỳ thay đổi nào ảnh hưởng security/auth
5. **Luôn chạy tester** trước khi báo task hoàn thành

### Lệnh đọc agent definition
```bash
# Xem tất cả agents
ls Claude-Kit/.opencode/agent/

# Đọc định nghĩa agent cụ thể
cat Claude-Kit/.opencode/agent/planner.md
cat Claude-Kit/.opencode/agent/code-reviewer.md
```

---

## Infrastructure

### GitHub
- **Repo**: `https://github.com/Andy-cods/bqms` (public)
- **Workflow hiện tại**: Develop local → commit → push lên GitHub
- **⚠️ Repo public** — tuyệt đối không commit `config.json` (chứa Gemini API keys), `.env`, hay bất kỳ file có credentials nào. Kiểm tra `.gitignore` trước mỗi commit.
- **Conventional Commits** — xem section Git Standards bên dưới

### OneDrive
- **Vai trò hiện tại**: Lưu trữ toàn bộ dữ liệu hệ thống:
  - `bsmq.db` — SQLite database chính
  - RFQ files (Excel từ khách hàng)
  - PO files (PDF/Excel từ Samsung)
- **Path**: `C:/Users/ASUS/OneDrive` (đọc từ `config.json → one_drive_root`)
- **⚠️ Rủi ro quan trọng**: SQLite + OneDrive sync có thể gây **database corruption** — OneDrive lock file trong khi SQLite đang write WAL. Nếu thấy lỗi `database is locked` hoặc `disk I/O error` → nguyên nhân thường là đây.
- **Workaround tạm**: Pause OneDrive sync khi hệ thống đang chạy nặng (crawl, batch write)

### VPS
- **Trạng thái**: Đã có VPS, **chưa deploy gì** — chỉ đang local
- **Mục tiêu**: Chuyển toàn bộ hệ thống lên VPS để chạy 24/7, không phụ thuộc máy cá nhân

### Kế hoạch migrate lên VPS (cần làm)
Khi sẵn sàng migrate, các vấn đề cần giải quyết theo thứ tự:

1. **Database**: `bsmq.db` đang trên OneDrive → cần copy vào local storage của VPS. OneDrive không available trên VPS server.
2. **File sync RFQ/PO**: Cần cơ chế đẩy file từ local → VPS (SFTP, rsync, hoặc shared folder qua SMB)
3. **Playwright trên VPS**: `headless=False` sẽ không hoạt động nếu VPS không có display. Cần xem xét:
   - Dùng `headless=True` + proxy rotation (trade-off: dễ bị block)
   - Hoặc giữ crawling ở local, chỉ deploy API + DB lên VPS
4. **Config**: `config.json` không commit — cần copy tay lên VPS hoặc dùng env vars
5. **Process manager**: Dùng `systemd` hoặc `supervisor` để tự restart khi VPS reboot
6. **Port**: Hiện `127.0.0.1:8000` (localhost only) → VPS cần bind `0.0.0.0:8000` + nginx reverse proxy + HTTPS

---

## Tech Stack
- **Backend**: FastAPI + uvicorn (app_api.py, port 8000)
- **Frontend**: Pure HTML/JS (BSMQ_Dashboard_v6.html) — REST API calls, no framework
- **DB**: SQLite (bsmq.db) via sqlite-utils
- **AI**: Google Gemini (google-generativeai) — keys trong config.json
- **Crawling**: Playwright async trực tiếp (headless=False, visible popup 950×680)
- **Parsing**: BeautifulSoup4 + lxml
- **Tests**: pytest (tests/)

## Environment Setup

**Yêu cầu**: Python 3.11+, Windows 11, Git

```bash
# Lần đầu setup
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
playwright install chromium    # Bắt buộc — tải ~283MB Chromium về

# Khởi động backend (auto-reload)
uvicorn app_api:app --host 127.0.0.1 --port 8000 --reload

# Tests
python -m pytest tests/ -v
```
Dashboard tại: http://127.0.0.1:8000

**Lưu ý Windows**:
- Dùng `venv\Scripts\activate` (không phải `source`)
- `playwright install chromium` phải chạy trong venv đã activate
- Print Unicode trong terminal: có thể lỗi encoding — wrap bằng `try/except` hoặc dùng `print(msg.encode('ascii','replace').decode())`
- File path dùng `/` (forward slash) trong Python code, Windows tự convert

## Cấu trúc chính
```
app_api.py              # FastAPI backend — tất cả /api/* endpoints
BSMQ_Dashboard_v6.html  # Frontend duy nhất (4762 dòng HTML/CSS/JS)
modules/
  config.py             # config.json reader/writer
  database.py           # SQLite helpers (bsmq.db)
  ai_classifier.py      # Gemini batch classifier
  watchdog_sync.py      # File watcher
tools/
  tool1_autofill/       # Auto-fill báo giá từ RFQ Excel
  tool2_pricetracker/   # Theo dõi giá
  tool3_pofilter/       # Lọc & phân loại PO
  tool4_po_tracker/     # Theo dõi trạng thái PO Samsung
  tool5_market_search/  # Tìm giá thị trường (Alibaba/1688/etc.)
    engine.py           # Crawl + AI extraction engine ← ĐANG PHÁT TRIỂN
    app.py              # Streamlit UI (legacy, không dùng)
```

## Config (config.json)
```json
{
  "gemini_keys": ["AIza..."],
  "one_drive_root": "C:/Users/ASUS/OneDrive",
  "rfq_folder": "...",
  "db_path": "bsmq.db"
}
```
File này KHÔNG commit (trong .gitignore).

## Tool 5 — Market Search (IN PROGRESS)
Engine tại `tools/tool5_market_search/engine.py`.

**Flow**: QueryBuilder (Gemini) → Crawl platforms → CSS extract → Gemini fallback → Verify → Synthesize → Evaluate

**Crawl approach** (đã implement):
- Playwright `headless=False` — browser popup 950×680 visible
- `wait_until="networkidle"` + 2s extra wait cho SPA (Angular/React)
- CAPTCHA detection: tự pause tối đa 120s để user giải tay
- `_CRAWL_SEM = asyncio.Semaphore(2)` — max 2 browser windows đồng thời

**Platform config** (`PLATFORM_CRAWL_CONFIG`):
- Mỗi platform có: `search_url_template`, `wait_for`, `scroll_to_bottom`, `selectors{}`
- CSS selectors là best-guess — **cần test và điều chỉnh từng platform**
- Khi CSS < 3 kết quả → tự fallback sang Gemini extract

**Platforms**: alibaba, 1688, taiwantrade, ruten, made_in_china, global_sources, lcsc

**Vấn đề đang giải quyết**:
- CSS selectors cho các platform SPA (Angular/React) cần được verify bằng DevTools thật
- Cách debug: chạy `_crawl_page()` riêng lẻ, in HTML, tìm class names thật
- Ruten (`find.ruten.com.tw`) có thể DNS fail — cần verify URL còn hoạt động không

**API endpoints**:
- `POST /api/market/search` → `{job_id}`
- `GET /api/market/job/{job_id}` → `{status, messages[], result}`
- `POST /api/market/save`, `GET /api/market/saved`, `DELETE /api/market/saved/{id}`

**Debug Tool 5**:
```bash
# Test crawl 1 platform
python -c "
import asyncio
from tools.tool5_market_search.engine import crawl_platform
async def t():
    r, s = await crawl_platform('taiwantrade', 'resistor 10k 0402', max_results=3)
    print(s); [print(x.title, x.price_text) for x in r]
asyncio.run(t())
"

# Xem HTML thật của 1 trang để tìm selectors
python -c "
import asyncio
from tools.tool5_market_search.engine import _crawl_page
async def t():
    html = await _crawl_page('https://...', wait_for='body', delay_min=0, delay_max=0)
    open('debug.html','w',encoding='utf-8').write(html)
    print(len(html))
asyncio.run(t())
"
# Mở debug.html trong browser → F12 DevTools → tìm selector đúng
```

## Patterns quan trọng
- **Progress callbacks**: tất cả long-running tasks dùng `progress_cb(msg: str)`
- **Async jobs**: FastAPI background tasks → poll `/api/*/job/{id}` mỗi 2s
- **Gemini rate limit**: `_pick_key()` rotate keys, max 55 RPM/key
- **Error handling**: lỗi platform không làm crash toàn bộ search — log vào `error_msg`
- **Backward compat**: `PLATFORM_CONFIG` là alias của `PLATFORM_CRAWL_CONFIG` cho code cũ

## Quy tắc làm việc
1. **Không fake data** — nếu không có kết quả thật, báo lỗi rõ ràng
2. **Test trước khi commit** — `pytest tests/ -v` phải pass 31/31
3. **Không đụng app_api.py endpoint shapes** — frontend đang dùng, breaking change = bug
4. **CSS selectors cho platforms** — sau khi sửa phải test thật bằng cách crawl 1 URL
5. **Config.json** — không hardcode paths, đọc từ `modules/config.py`

---

## Trạng Thái Hiện Tại & Nợ Kỹ Thuật

### Status các Tool
| Tool | Trạng thái | Ghi chú |
|---|---|---|
| Tool 1 — Auto-fill RFQ | ✅ Done | Hoạt động, đang dùng hàng ngày |
| Tool 2 — Price Tracker | ✅ Done | Hoạt động |
| Tool 3 — PO Filter | ✅ Done | Hoạt động |
| Tool 4 — PO Samsung Tracker | ✅ Done | Selenium + pdfplumber |
| Tool 5 — Market Search | 🔧 In Progress | CSS selectors chưa verified, xem bên dưới |
| Auth / RBAC | ❌ Not started | Hiện tại không có auth — chạy localhost only |

### Tool 5 — Việc còn lại
- [ ] Verify CSS selectors từng platform bằng DevTools thật (crawl → save debug.html → inspect)
- [ ] Fix/verify URL Ruten (`find.ruten.com.tw` có thể DNS fail)
- [ ] Test end-to-end: search 1 part number → nhận kết quả thật có giá, tên sản phẩm, nhà cung cấp
- [ ] Các platform cần ưu tiên test: Taiwantrade, 1688, Alibaba (traffic cao nhất)

### Tech Debt đã biết
- `app_api.py` ngày càng dài (monolith) — cần tách routers/ khi rebuild
- `BSMQ_Dashboard_v6.html` 4762 dòng JS/CSS inline — cần tách component khi rebuild
- Không có auth — bất kỳ ai truy cập localhost:8000 đều thấy tất cả
- Không có rate limiting trên API
- Chưa có migration system cho DB schema

---

## Quyết Định Kiến Trúc (ADR)

> Giải thích lý do chọn stack này. Đừng đề xuất thay đổi trừ khi có lý do thực sự tốt.

| Quyết định | Lựa chọn | Lý do |
|---|---|---|
| **Database** | SQLite | Internal tool, single-server, không cần PostgreSQL overhead. WAL mode đủ cho concurrent reads. |
| **Browser automation** | Playwright (không Selenium) | Async native, stealth tốt hơn, `networkidle` wait cho SPA. Selenium đã dùng ở Tool4 nhưng không mở rộng sang Tool5. |
| **Frontend** | HTML/JS thuần (không React/Vue) | Team nhỏ, không có build pipeline, dễ maintain. 1 file duy nhất serve static qua FastAPI. |
| **AI** | Google Gemini | Đã tích hợp, cost thấp hơn OpenAI, hỗ trợ tiếng Việt/Hoa tốt cho domain linh kiện. |
| **headless=False** | Visible browser popup | Các platform B2B (Alibaba, 1688) phát hiện headless và block. Visible browser bypass anti-bot. Cho phép user giải CAPTCHA tay. |
| **crawl4ai → Playwright trực tiếp** | Direct Playwright | crawl4ai với headless=False đóng browser ngay lập tức trước khi page load xong. Direct Playwright cho full control. |

---

## Tiêu Chuẩn Kỹ Thuật (Engineering Standards)

> Khi rebuild hoặc viết code mới, áp dụng các tiêu chuẩn này. Đây không phải optional —
> đây là định nghĩa của "professional quality" với tôi.

### Clean Architecture (Uncle Bob)

Phân tách code thành 4 vòng — **dependency chỉ hướng vào trong**:

```
┌─────────────────────────────────────┐
│  Frameworks & Drivers               │  ← FastAPI, SQLite, Playwright, HTML
│  ┌───────────────────────────────┐  │
│  │  Interface Adapters           │  │  ← routers/, repositories/, presenters/
│  │  ┌─────────────────────────┐  │  │
│  │  │  Application Use Cases  │  │  │  ← services/ (business logic)
│  │  │  ┌───────────────────┐  │  │  │
│  │  │  │  Domain Entities  │  │  │  │  ← models/ (pure Python, no deps)
│  │  │  └───────────────────┘  │  │  │
│  │  └─────────────────────────┘  │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

**Quy tắc áp dụng**:
- Domain entities không import FastAPI, SQLite hay bất kỳ framework nào
- Business logic nằm trong services/, không nằm trong routers/
- Database access qua Repository pattern — không query thẳng từ endpoint
- Dependency Injection: FastAPI `Depends()` cho tất cả services

### SOLID Principles

| Nguyên tắc | Áp dụng trong BSMQ |
|---|---|
| **S** — Single Responsibility | Mỗi module 1 việc: `engine.py` chỉ crawl, không handle HTTP |
| **O** — Open/Closed | Thêm platform mới = thêm entry vào `PLATFORM_CRAWL_CONFIG`, không sửa logic |
| **L** — Liskov Substitution | Các platform crawlers có thể thay thế nhau qua interface chung |
| **I** — Interface Segregation | `progress_cb` protocol nhỏ gọn — không force caller implement nhiều hơn cần |
| **D** — Dependency Inversion | Services nhận `db`, `ai_client` qua constructor/DI, không tự tạo |

### 12-Factor App

| Factor | Cách áp dụng |
|---|---|
| **Config** | Tất cả secrets trong `config.json` (không commit) hoặc env vars |
| **Dependencies** | Explicit trong `requirements.txt`, không assume system packages |
| **Backing services** | SQLite, Gemini API, Playwright treated as attached resources |
| **Processes** | Stateless — không lưu session state trong memory (dùng DB) |
| **Port binding** | App tự serve trên port 8000, không cần external web server |
| **Logs** | Stream to stdout (uvicorn), không ghi file log trong code |
| **Dev/prod parity** | Chạy cùng stack locally và production — không "chỉ test local" |

### OWASP Top 10 — Phải xử lý

| Rủi ro | Biện pháp bắt buộc |
|---|---|
| **A01 Broken Access Control** | Kiểm tra role ở mọi endpoint, không client-side only |
| **A02 Cryptographic Failures** | JWT ký bằng secret key, không lưu plain password |
| **A03 Injection** | Parameterized queries (sqlite-utils đã handle), validate mọi input |
| **A04 Insecure Design** | RBAC design trước khi code, threat model cho mỗi feature |
| **A05 Security Misconfiguration** | CORS restrict `localhost:8000`, không `allow_origins=["*"]` production |
| **A06 Vulnerable Components** | `pip audit` trước khi release, pin versions |
| **A07 Auth Failures** | Rate limit login, JWT expiry, không expose stack traces |
| **A08 Data Integrity** | Validate Pydantic models ở mọi API input |
| **A09 Logging Failures** | Log auth failures và anomalies, có audit trail |
| **A10 SSRF** | Whitelist domains khi crawl, không crawl URL do user nhập thẳng |

### Python Standards

- **PEP 8**: 88 chars/line (black formatter), snake_case, UPPER_SNAKE cho constants
- **PEP 20** (Zen): Explicit > implicit. Simple > complex. Readability counts.
- **PEP 484**: Type hints cho tất cả function signatures — `def foo(x: int) -> str:`
- **PEP 257**: Docstring cho public functions, classes, modules
- **Tooling**: `black` (format) + `ruff` (lint) + `mypy` (type check) trước commit

### REST API Design

- **Versioning**: `/api/v1/` — không thay đổi response shape mà không bump version
- **HTTP Methods**: GET (read), POST (create/action), PUT (replace), PATCH (partial update), DELETE
- **Status Codes**: 200 OK, 201 Created, 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 422 Validation Error, 500 Server Error
- **Response envelope**:
  ```json
  { "success": true, "data": {...}, "error": null, "meta": {"page": 1} }
  ```
- **OpenAPI**: Pydantic models tự sinh docs tại `/docs` — mọi endpoint phải có schema

### Database Standards

- **Normalization**: 3NF minimum — không duplicate data
- **Indexes**: Index tất cả cột dùng trong WHERE, JOIN, ORDER BY
- **Migrations**: Script migration khi thay đổi schema — không `ALTER TABLE` tay
- **WAL mode**: `PRAGMA journal_mode=WAL` cho SQLite concurrent reads
- **Transactions**: Group related writes trong transaction, rollback on failure
- **No raw SQL** với user input — luôn dùng parameterized queries

### Testing Standards (Test Pyramid)

```
        /\
       /  \   E2E Tests (ít, chậm, test flow)
      /────\
     /      \  Integration Tests (API endpoints, DB)
    /────────\
   /          \ Unit Tests (nhiều, nhanh, isolated)
  /────────────\
```

- **Unit tests**: Mọi service function có test, mock external deps
- **Integration tests**: Mọi API endpoint có test với test DB
- **Coverage**: Minimum 80% cho business logic (services/)
- **Naming**: `test_<what>_when_<condition>_should_<expected>()`
- **Fixtures**: `conftest.py` cho shared test data và mock clients

### Git & Release Standards

- **Conventional Commits**:
  ```
  feat: add taiwantrade CSS selectors
  fix: crawler popup closes before page loads
  refactor: extract _build_platform_urls() helper
  test: add unit tests for price parser
  docs: update CLAUDE.md with platform config guide
  ```
- **Branching**: `main` luôn deployable. Feature branches: `feat/tool5-selectors`
- **Semantic Versioning**: `MAJOR.MINOR.PATCH` — breaking change = MAJOR bump
- **PR checklist**: Tests pass + code review + no secrets in diff

### Code Quality Metrics

| Metric | Target |
|---|---|
| Cyclomatic complexity | ≤ 10 per function |
| Function length | ≤ 50 lines |
| File length | ≤ 500 lines |
| Test coverage (business logic) | ≥ 80% |
| Type hint coverage | 100% public APIs |
| Duplicate code | < 5% (DRY) |

### Performance Targets

| Operation | Target |
|---|---|
| API response (non-crawl) | < 200ms p95 |
| DB query | < 50ms p95 |
| Page load (frontend) | < 2s first contentful paint |
| Crawl per platform | < 30s (excl. CAPTCHA) |
| Memory (server idle) | < 200MB RSS |

### ISO/IEC 25010 — Quality Model

Khi đánh giá feature mới, check 8 đặc tính:
1. **Functional Suitability** — làm đúng việc cần làm không?
2. **Performance Efficiency** — nhanh và dùng ít resource không?
3. **Compatibility** — hoạt động với các phần khác của hệ thống không?
4. **Usability** — user hiểu và dùng được mà không cần hướng dẫn không?
5. **Reliability** — có fail gracefully không? recovery time?
6. **Security** — có vượt qua OWASP checklist không?
7. **Maintainability** — người khác có đọc và sửa được không?
8. **Portability** — có chạy được trên máy khác không cần magic không?

---

## Lệnh Debug & Kiểm Tra Hệ Thống

```bash
# Check API health
curl http://127.0.0.1:8000/api/health

# Chạy 1 search job
curl -X POST http://127.0.0.1:8000/api/market/search \
  -H "Content-Type: application/json" \
  -d "{\"spec\":\"STM32F103C8T6\",\"platforms\":[\"taiwantrade\"]}"

# Xem tất cả saved prices
curl http://127.0.0.1:8000/api/market/saved

# Chạy tests
python -m pytest tests/ -v --tb=short

# Kiểm tra dependencies có lỗ hổng bảo mật
pip audit
```
