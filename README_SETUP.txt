================================================================
  BSMQ PROCUREMENT TOOL v6 — HUONG DAN CAI DAT / SETUP GUIDE
================================================================

YEU CAU HE THONG / SYSTEM REQUIREMENTS:
  - Windows 10 (64-bit)
  - Ket noi internet (khi cai dat lan dau)
  - Google Chrome (cho Tool 4 - PO Tracker)
  - OneDrive da dong bo tren may

================================================================
LAN DAU SU DUNG / FIRST TIME SETUP
================================================================

BUOC 1: Giai nen / Extract
  - Giai nen file BSMQ_Tool_v6.zip ra thu muc bat ky
  - Vi du: Desktop\BSMQ_Tool\

BUOC 2: Cai dat / Install
  - Double-click file: install.bat
  - Cho den khi hien "CAI DAT HOAN TAT"
  - Qua trinh nay mat khoang 5-10 phut (can internet)
  - Neu that bai, xem file logs\install.log

BUOC 3: Khoi dong / Launch
  - Double-click file: run.bat
  - Trinh duyet tu dong mo tai http://localhost:8000
  - Lan dau se co man hinh cau hinh (Setup Wizard)

BUOC 4: Cau hinh / Configure
  - Chon thu muc RFQ tren OneDrive
  - Nhap Gemini API key (neu co)
  - Nhap tai khoan Samsung BQMS (cho Tool 4)
  - Nhan "Luu va Bat dau"

================================================================
SU DUNG HANG NGAY / DAILY USE
================================================================

  - Double-click run.bat
  - Trinh duyet tu dong mo
  - Dong cua so den de tat tool

================================================================
CAP NHAT / UPDATE
================================================================

  Cach 1 (tu dong): System tab → "Kiem tra cap nhat"
  Cach 2 (thu cong): Double-click update.bat

================================================================
LOI THUONG GAP / TROUBLESHOOTING
================================================================

  - "Chua cai dat"  → Chay install.bat truoc
  - Port 8000 bi chiem → Dong ung dung khac dang dung port 8000
  - Chrome khong tim thay → Cai Google Chrome truoc
  - logs\install.log → Xem chi tiet loi cai dat
  - logs\api_runtime.log → Xem chi tiet loi khi chay

================================================================
HO TRO / SUPPORT
================================================================

  Lien he admin de duoc ho tro.
  Kem theo noi dung file logs\api_runtime.log khi bao loi.

================================================================
