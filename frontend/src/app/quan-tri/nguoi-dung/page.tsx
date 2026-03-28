"use client";
import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import PageHeader from "@/components/ui/PageHeader";
import { fmtDate } from "@/lib/format";

export default function UsersPage() {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/users/").then((d) => { setUsers(d?.data || []); setLoading(false); });
  }, []);

  const roleColor: Record<string, string> = {
    admin: "bg-red-100 text-red-700", manager: "bg-purple-100 text-purple-700",
    procurement: "bg-blue-100 text-blue-700", warehouse: "bg-amber-100 text-amber-700",
    staff: "bg-slate-100 text-slate-600",
  };
  const roleLabel: Record<string, string> = {
    admin: "Quản trị", manager: "Quản lý", procurement: "Mua hàng", warehouse: "Kho", staff: "Nhân viên",
  };

  return (
    <div className="animate-fade-in">
      <PageHeader title="Quản Lý Người Dùng" subtitle={`${users.length} tài khoản`} />
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              <th className="px-4 py-3 text-left text-[10px] font-semibold text-slate-500 uppercase">Email</th>
              <th className="px-4 py-3 text-left text-[10px] font-semibold text-slate-500 uppercase">Họ tên</th>
              <th className="px-4 py-3 text-left text-[10px] font-semibold text-slate-500 uppercase">Vai trò</th>
              <th className="px-4 py-3 text-left text-[10px] font-semibold text-slate-500 uppercase">Trạng thái</th>
              <th className="px-4 py-3 text-left text-[10px] font-semibold text-slate-500 uppercase">Đăng nhập cuối</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} className="text-center py-8 text-slate-400">Đang tải...</td></tr>
            ) : users.map((u, i) => (
              <tr key={i} className="border-b border-slate-50 hover:bg-blue-50/30 transition">
                <td className="px-4 py-3 font-mono text-slate-600">{u.email}</td>
                <td className="px-4 py-3 font-medium">{u.full_name}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${roleColor[u.role] || "bg-slate-100"}`}>
                    {roleLabel[u.role] || u.role}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${u.is_active ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>
                    {u.is_active ? "Hoạt động" : "Vô hiệu"}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-500">{fmtDate(u.last_login)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
