"use client";
import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import DataTable, { Column } from "@/components/ui/DataTable";
import PageHeader from "@/components/ui/PageHeader";
import SearchBar from "@/components/ui/SearchBar";

const COLS: Column[] = [
  { key: "po_date", label: "Ngày PO", type: "date", width: "90px" },
  { key: "po_number", label: "Số PO", width: "110px" },
  { key: "rfq_no", label: "Mã RFQ", width: "110px" },
  { key: "bqms_code", label: "BQMS", width: "120px" },
  { key: "spec", label: "Mô tả", type: "trunc" },
  { key: "quantity", label: "SL", type: "number", width: "60px" },
  { key: "unit_price", label: "Đơn giá", type: "money", width: "80px" },
  { key: "buyer", label: "Bên mua", width: "70px" },
  { key: "status", label: "Trạng thái", width: "100px" },
  { key: "delivery_date", label: "Ngày giao", type: "date", width: "90px" },
];

export default function GiaoHangPage() {
  const [data, setData] = useState<any>({ data: [], total: 0, page: 1, pages: 0 });
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    const d = await apiFetch(`/deliveries?page=${p}&limit=25&po_number=${encodeURIComponent(search)}`);
    if (d) { setData(d); setPage(p); }
    setLoading(false);
  }, [search]);

  useEffect(() => { load(1); }, []);

  return (
    <div className="animate-fade-in">
      <PageHeader title="Giao Hàng" subtitle={`${data.total?.toLocaleString("vi-VN")} đơn giao hàng`}>
        <SearchBar value={search} onChange={setSearch} onSearch={() => load(1)} placeholder="Tìm theo số PO..." />
      </PageHeader>
      <DataTable columns={COLS} data={data.data || []} total={data.total || 0} page={page} pages={data.pages || 0} onPageChange={load} loading={loading} />
    </div>
  );
}
