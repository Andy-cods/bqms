"""Extract transactions from TT XNK BQMS Excel files.

Column mapping (from real file analysis):
  A: TT (row number)
  B: Ngay Thang (transaction date)
  C: Don hang (RFQ no, e.g. QT26000091)
  D: BMSQ (BQMS code, e.g. Z0000001-709890)
  E: Ten hang hoa (product name/spec)
  F: Explain (description)
  G: Loai hang (type: Thuong mai / Gia cong)
  H: Maker (manufacturer)
  I: Ghi chu (notes)
  J: Ghi chu 2
  K: Don vi tinh (unit)
  L: So luong (quantity)
  M: Quote Deadline
  N-Y: Import/export data columns
"""

import hashlib
from datetime import datetime
from typing import Optional

import openpyxl


# Columns to extract (0-indexed from column A)
COL_MAP = {
    "row_num": 0,       # A
    "date": 1,          # B
    "rfq_no": 2,        # C
    "bqms_code": 3,     # D
    "spec": 4,          # E
    "description": 5,   # F
    "type": 6,          # G
    "maker": 7,         # H
    "note1": 8,         # I
    "note2": 9,         # J
    "unit": 10,         # K
    "quantity": 11,     # L
    "deadline": 12,     # M
    "import_date": 13,  # N
    "bqms3": 14,        # O
    "desc_import": 15,  # P
    "hs_code": 16,      # Q
    "unit2": 17,        # R
    "qty2": 18,         # S
    "total_usd": 19,    # T
}


def _str(v) -> str:
    if v is None:
        return ""
    return str(v).replace("\xa0", " ").strip()


def _num(v) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(",", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _date(v) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    if not s:
        return None
    return s[:10]  # Best effort


def _hash_row(rfq: str, bqms: str, date_str: str, spec: str) -> str:
    key = f"{rfq}|{bqms}|{date_str}|{spec}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def _classify_type(v: str) -> Optional[str]:
    lh = v.lower().replace("\xa0", " ").strip()
    if any(x in lh for x in ("gia cong", "gia công", "gc")):
        return "gc"
    if any(x in lh for x in ("thuong mai", "thương mại", "tm")):
        return "tm"
    return None


def extract_file(filepath: str, sheets: list[str] | None = None) -> list[dict]:
    """Extract transactions from a TT XNK BQMS file.

    Args:
        filepath: Path to .xlsm/.xlsx file
        sheets: Sheet names to process. None = auto-detect (DATA + month sheets)

    Returns:
        List of transaction dicts ready for DB insert
    """
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)

    if sheets is None:
        # Process DATA sheet + monthly sheets (JAN, FEB, etc.)
        target_sheets = []
        for s in wb.sheetnames:
            sl = s.upper()
            if sl in ("DATA", "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                       "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"):
                target_sheets.append(s)
        if not target_sheets:
            target_sheets = wb.sheetnames[:1]
    else:
        target_sheets = sheets

    import os
    source_file = os.path.basename(filepath)
    results = []
    seen_hashes = set()

    for sheet_name in target_sheets:
        ws = wb[sheet_name]
        row_idx = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            row_idx += 1
            # Skip empty rows
            if not row or len(row) < 5:
                continue

            rfq = _str(row[COL_MAP["rfq_no"]] if len(row) > COL_MAP["rfq_no"] else None)
            bqms = _str(row[COL_MAP["bqms_code"]] if len(row) > COL_MAP["bqms_code"] else None)
            spec = _str(row[COL_MAP["spec"]] if len(row) > COL_MAP["spec"] else None)

            # Skip if no meaningful data
            if not rfq and not bqms and not spec:
                continue

            date_val = row[COL_MAP["date"]] if len(row) > COL_MAP["date"] else None
            date_str = _date(date_val)

            # Dedup by hash
            h = _hash_row(rfq, bqms, date_str or "", spec)
            if h in seen_hashes:
                continue
            seen_hashes.add(h)

            type_raw = _str(row[COL_MAP["type"]] if len(row) > COL_MAP["type"] else None)
            maker = _str(row[COL_MAP["maker"]] if len(row) > COL_MAP["maker"] else None)
            unit = _str(row[COL_MAP["unit"]] if len(row) > COL_MAP["unit"] else None)
            qty = _num(row[COL_MAP["quantity"]] if len(row) > COL_MAP["quantity"] else None)
            total_usd = _num(row[COL_MAP["total_usd"]] if len(row) > COL_MAP["total_usd"] else None)
            note = _str(row[COL_MAP["note1"]] if len(row) > COL_MAP["note1"] else None)
            desc = _str(row[COL_MAP["description"]] if len(row) > COL_MAP["description"] else None)

            results.append({
                "transaction_date": date_str,
                "rfq_no": rfq,
                "bqms_code": bqms,
                "spec": spec[:500] if spec else None,
                "maker": maker[:200] if maker else None,
                "quantity": qty,
                "unit": unit or "EA",
                "price_rmb": None,
                "price_vnd": None,
                "price_quoted": total_usd,
                "version": None,
                "result": _classify_type(type_raw) if type_raw else None,
                "person_in_charge": desc[:200] if desc else None,
                "notes": note[:500] if note else None,
                "source_file": source_file,
                "source_sheet": sheet_name,
                "source_row": row_idx + 1,
                "row_hash": h,
            })

    wb.close()
    return results
