# Phase 4: ChromeDriver Handling

**Part of:** [BSMQ Packaging Plan](./plan.md)
**Status:** Pending
**Depends on:** Phase 1, Phase 3

---

## Overview

Tool 4 (PO Tracker) uses Selenium + Chrome to automate Samsung BQMS portal.
Current code uses `webdriver_manager.chrome.ChromeDriverManager` — auto-downloads matching
ChromeDriver at runtime. No manual ChromeDriver bundling needed.

**Decision: keep webdriver-manager.** Already in requirements.txt and engine.py. No changes.

---

## Key Insights

1. **No manual ChromeDriver needed.** webdriver-manager auto-downloads matching ChromeDriver
   for installed Chrome version. Works out-of-the-box with embedded Python.

2. **Chrome must be pre-installed by user.** Cannot bundle Chrome (license, ~100 MB).
   README must state: "Google Chrome is required for Tool 4."

3. **ChromeDriver cache:** `~/.wdm/drivers/chromedriver/` — machine-persistent, auto-managed.

4. **Offline scenario needs clear error.** Wrap ChromeDriverManager in try/except; return
   user-friendly error via API instead of stack trace.

5. **Chrome auto-update:** webdriver-manager handles stale driver automatically on next run.

---

## Changes Required

### engine.py — add try/except + WDM_CACHE_PATH

```python
from modules.config import get_config
import os

# Allow configurable ChromeDriver cache location
cfg = get_config()
if cfg.get("chromedriver_cache_path"):
    os.environ["WDM_CACHE_PATH"] = cfg["chromedriver_cache_path"]

try:
    driver_path = ChromeDriverManager().install()
except Exception as e:
    raise RuntimeError(
        f"ChromeDriver download failed. Ensure internet access and Chrome is installed. "
        f"Detail: {e}"
    ) from e

service = Service(driver_path)
driver = webdriver.Chrome(service=service, options=options)
```

### config.py — add Chrome detection to get_setup_status()

```python
import shutil, os
chrome_found = bool(
    shutil.which("chrome") or
    os.path.exists(r"C:\Program Files\Google\Chrome\Application\chrome.exe") or
    os.path.exists(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe")
)
```

Return `"chrome_found": chrome_found` in setup status dict.

### config.json — add new keys to _DEFAULTS

```python
"chromedriver_cache_path": "",
"chrome_headless": False,
```

---

## Related Code Files

- `tools/tool4_po_tracker/engine.py` — wrap ChromeDriverManager + add WDM_CACHE_PATH
- `modules/config.py` — add Chrome detection in get_setup_status()
- `app_api.py` — catch RuntimeError from Tool 4, return 503 with user-friendly message

---

## Todo List

- [ ] Add try/except around ChromeDriverManager().install() in engine.py
- [ ] Add chromedriver_cache_path + chrome_headless to config.py _DEFAULTS
- [ ] Add WDM_CACHE_PATH env var passthrough in engine.py
- [ ] Add Chrome detection to get_setup_status()
- [ ] Add Chrome not-found warning to wizard UI (Phase 3 integration)
- [ ] Test Tool 4 first run with embedded Python
- [ ] Test behavior when internet unavailable (should show clean error)

---

## Success Criteria

- Tool 4 starts Chrome via embedded Python without manual setup
- ChromeDriver auto-downloaded on first use
- Clear error shown if Chrome not installed or internet unavailable
- `chrome_headless` config key respected

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Chrome not installed | Medium | Medium | Detection in wizard + README |
| Antivirus blocks ChromeDriver | Low | High | Document: add cache folder to AV exclusions |
| Corporate proxy blocks wdm | Low | Medium | Document WDM_PROXY env var |

---

## Next Steps

Phase 5: Assemble and build the final distribution ZIP.
