"use client";
import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import DataTable, { Column } from "@/components/ui/DataTable";
import PageHeader from "@/components/ui/PageHeader";

const TABS = [
  { key: "analytics", label: "Thống Kê Hỏi Hàng" },
  { key: "giao-hang", label: "Thống Kê Giao Hàng" },
];

const ANALYTICS_COLS: Column[] = [
  { key: "date", label: "Ngày", type: "date", width: "90px" },
  { key: "person_in_charge", label: "Phụ trách", width: "80px" },
  { key: "rfq_no", label: "RFQ", width: "110px" },
  { key: "bqms_code", label: "BQMS", width: "120px" },
  { key: "spec", label: "Spec", type: "trunc" },
  { key: "maker", label: "Hãng", width: "80px" },
  { key: "quantity_forecast", label: "SL", type: "number", width: "60px" },
  { key: "price_bqms_v1", label: "V1", type: "money", width: "70px" },
  { key: "price_bqms_v2", label: "V2", type: "money", width: "70px" },
  { key: "supplier", label: "NCC", type: "trunc", width: "100px" },
  { key: "result", label: "KQ", type: "badge", width: "50px" },
];

const DELIVERY_COLS: Column[] = [
  { key: "po_date", label: "Ngày PO", type: "date", width: "90px" },
  { key: "po_number", label: "Số PO", width: "100px" },
  { key: "rfq_no", label: "RFQ", width: "100px" },
  { key: "spec", label: "Spec", type: "trunc" },
  { key: "quantity", label: "SL", type: "number", width: "60px" },
  { key: "unit_price", label: "Đơn giá", type: "money", width: "80px" },
  { key: "total_amount", label: "Thành tiền", type: "money", width: "90px" },
  { key: "buyer", label: "Mua", width: "60px" },
  { key: "receiver_name", label: "Nhận", type: "trunc", width: "100px" },
  { key: "status", label: "TT", width: "80px" },
  { key: "delivery_date", label: "Giao", type: "date", width: "90px" },
];

export default function PriceTrackerPage() {
  const [tab, setTab] = useState("analytics");
  const [data, setData] = useState<any>({ data: [], total: 0, page: 1, pages: 0 });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    const endpoint = tab === "analytics" ? "/tool-engine/tool2/analytics" : "/tool-engine/tool2/giao-hang";
    const d = await apiFetch(`${endpoint}?page=${p}&limit=25`);
    if (d) { setData(d); setPage(p); }
    setLoading(false);
  }, [tab]);

  useEffect(() => { load(1); }, [tab]);

  return (
    <div className="animate-fade-in">
      <PageHeader title="Tool 2: Thống Kê Giá" subtitle="Phân tích dữ liệu hỏi hàng và giao hàng" />

      <div className="flex gap-2 mb-4">
        {TABS.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-4 py-2 rounded-xl text-xs font-medium transition ${
              tab === t.key ? "bg-brand text-white" : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"}`}>
            {t.label}
          </button>
        ))}
      </div>

      <DataTable
        columns={tab === "analytics" ? ANALYTICS_COLS : DELIVERY_COLS}
        data={data.data || []}
        total={data.total || 0}
        page={page}
        pages={data.pages || 0}
        onPageChange={load}
        loading={loading}
      />
    </div>
  );
}
