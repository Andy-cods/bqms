"use client";
import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import DataTable, { Column } from "@/components/ui/DataTable";
import PageHeader from "@/components/ui/PageHeader";
import SearchBar from "@/components/ui/SearchBar";

const COLS: Column[] = [
  { key: "transaction_date", label: "Ngày", type: "date", width: "90px" },
  { key: "rfq_no", label: "Mã RFQ", width: "120px" },
  { key: "bqms_code", label: "Mã BQMS", width: "130px" },
  { key: "spec", label: "Mô tả", type: "trunc" },
  { key: "type", label: "Loại", type: "badge", width: "60px" },
  { key: "maker", label: "Hãng", width: "100px" },
  { key: "quantity", label: "SL", type: "number", width: "70px" },
  { key: "unit_price_usd", label: "Giá USD", type: "money", width: "80px" },
  { key: "buyer", label: "Bên mua", width: "70px" },
  { key: "seller", label: "Bên bán", type: "trunc", width: "140px" },
];

export default function GiaoDichPage() {
  const [data, setData] = useState<any>({ data: [], total: 0, page: 1, pages: 0 });
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    const d = await apiFetch(`/transactions?page=${p}&limit=25&q=${encodeURIComponent(search)}`);
    if (d) { setData(d); setPage(p); }
    setLoading(false);
  }, [search]);

  useEffect(() => { load(1); }, []);

  return (
    <div className="animate-fade-in">
      <PageHeader title="Giao Dịch" subtitle={`${data.total?.toLocaleString("vi-VN")} giao dịch — sắp xếp mới nhất`}>
        <SearchBar value={search} onChange={setSearch} onSearch={() => load(1)} placeholder="Tìm theo RFQ, BQMS, spec..." />
      </PageHeader>
      <DataTable columns={COLS} data={data.data || []} total={data.total || 0} page={page} pages={data.pages || 0} onPageChange={load} loading={loading} />
    </div>
  );
}
