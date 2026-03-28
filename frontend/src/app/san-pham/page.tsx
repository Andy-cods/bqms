"use client";
import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import DataTable, { Column } from "@/components/ui/DataTable";
import PageHeader from "@/components/ui/PageHeader";
import SearchBar from "@/components/ui/SearchBar";

const COLS: Column[] = [
  { key: "bqms_code", label: "Mã BQMS", width: "140px" },
  { key: "product_name", label: "Tên sản phẩm", type: "trunc" },
  { key: "maker", label: "Hãng SX" },
  { key: "type", label: "Loại", type: "badge" },
  { key: "unit", label: "ĐVT", width: "60px" },
  { key: "current_stock", label: "Tồn kho", type: "number", width: "80px" },
  { key: "updated_at", label: "Cập nhật", type: "date", width: "100px" },
];

const FILTERS = [
  { key: "", label: "Tất cả" },
  { key: "gc", label: "Gia công" },
  { key: "tm", label: "Thương mại" },
];

export default function SanPhamPage() {
  const [data, setData] = useState<any>({ data: [], total: 0, page: 1, pages: 0 });
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    const params = `?page=${p}&limit=25&q=${encodeURIComponent(search)}&type=${typeFilter}`;
    const d = await apiFetch(`/products${params}`);
    if (d) { setData(d); setPage(p); }
    setLoading(false);
  }, [search, typeFilter]);

  useEffect(() => { load(1); }, [typeFilter]);

  return (
    <div className="animate-fade-in">
      <PageHeader title="Sản Phẩm" subtitle={`${data.total?.toLocaleString("vi-VN")} sản phẩm trong hệ thống`}>
        <SearchBar value={search} onChange={setSearch} onSearch={() => load(1)} placeholder="Tìm theo mã, tên, hãng SX..." />
      </PageHeader>

      {/* Filter pills */}
      <div className="flex gap-2 mb-4">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setTypeFilter(f.key)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition ${
              typeFilter === f.key
                ? "bg-brand text-white"
                : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <DataTable
        columns={COLS}
        data={data.data || []}
        total={data.total || 0}
        page={page}
        pages={data.pages || 0}
        onPageChange={load}
        loading={loading}
        emptyText="Không tìm thấy sản phẩm"
      />
    </div>
  );
}
