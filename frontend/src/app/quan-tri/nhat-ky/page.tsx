"use client";
import { useEffect, useState, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import DataTable, { Column } from "@/components/ui/DataTable";
import PageHeader from "@/components/ui/PageHeader";

const COLS: Column[] = [
  { key: "created_at", label: "Thời gian", type: "date", width: "100px" },
  { key: "action", label: "Hành động", type: "badge", width: "120px",
    badgeMap: { LOGIN_SUCCESS: "bg-emerald-100 text-emerald-700", LOGIN_FAILED: "bg-red-100 text-red-700",
               USER_CREATED: "bg-blue-100 text-blue-700", PASSWORD_CHANGED: "bg-amber-100 text-amber-700" } },
  { key: "table_name", label: "Bảng", width: "80px" },
  { key: "record_id", label: "ID bản ghi", type: "trunc", width: "200px" },
  { key: "ip_address", label: "IP", width: "120px" },
];

export default function AuditPage() {
  const [data, setData] = useState<any>({ data: [], total: 0, page: 1, pages: 0 });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (p = 1) => {
    setLoading(true);
    const d = await apiFetch(`/audit-log?page=${p}&limit=25`);
    if (d) { setData(d); setPage(p); }
    setLoading(false);
  }, []);

  useEffect(() => { load(1); }, []);

  return (
    <div className="animate-fade-in">
      <PageHeader title="Nhật Ký Hệ Thống" subtitle="Lịch sử hoạt động và thay đổi" />
      <DataTable columns={COLS} data={data.data || []} total={data.total || 0} page={page} pages={data.pages || 0} onPageChange={load} loading={loading} />
    </div>
  );
}
