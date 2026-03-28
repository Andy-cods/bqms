"use client";
import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import DataTable, { Column } from "@/components/ui/DataTable";
import PageHeader from "@/components/ui/PageHeader";
import SearchBar from "@/components/ui/SearchBar";

const COLS: Column[] = [
  { key: "date", label: "Ngày", type: "date", width: "90px" },
  { key: "rfq_no", label: "Mã RFQ", width: "110px" },
  { key: "bqms_code", label: "Mã BQMS", width: "130px" },
  { key: "spec", label: "Mô tả", type: "trunc" },
  { key: "maker", label: "Hãng", width: "100px" },
  { key: "quantity_forecast", label: "SL dự kiến", type: "number", width: "80px" },
  { key: "price_bqms_v1", label: "Giá V1", type: "money", width: "80px" },
  { key: "price_bqms_v2", label: "Giá V2", type: "money", width: "80px" },
  { key: "supplier", label: "NCC", type: "trunc", width: "120px" },
  { key: "result", label: "Kết quả", type: "badge", width: "70px" },
];

const RESULT_FILTERS = [
  { key: "", label: "Tất cả" },
  { key: "Y", label: "Thắng" },
  { key: "N", label: "Thua" },
];

export default function BaoGiaPage() {
  const [data, setData] = useState<any>({ data: [], total: 0, page: 1, pages: 0 });
  const [search, setSearch] = useState("");
  const [resultFilter, setResultFilter] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    const d = await apiFetch(`/quotations?page=${p}&limit=25&q=${encodeURIComponent(search)}&result=${resultFilter}`);
    if (d) { setData(d); setPage(p); }
    setLoading(false);
  }, [search, resultFilter]);

  useEffect(() => { load(1); }, [resultFilter]);

  return (
    <div className="animate-fade-in">
      <PageHeader title="Báo Giá" subtitle={`${data.total?.toLocaleString("vi-VN")} bản báo giá`}>
        <SearchBar value={search} onChange={setSearch} onSearch={() => load(1)} placeholder="Tìm theo RFQ, BQMS, NCC..." />
      </PageHeader>

      <div className="flex gap-2 mb-4">
        {RESULT_FILTERS.map((f) => (
          <button key={f.key} onClick={() => setResultFilter(f.key)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition ${
              resultFilter === f.key ? "bg-brand text-white" : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"}`}>
            {f.label}
          </button>
        ))}
      </div>

      <DataTable columns={COLS} data={data.data || []} total={data.total || 0} page={page} pages={data.pages || 0} onPageChange={load} loading={loading} />
    </div>
  );
}
