"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { fmt, fmtMoney, fmtDate, fmtPct, truncate } from "@/lib/format";
import KpiCard from "@/components/ui/KpiCard";
import { Doughnut, Line, Bar } from "@/components/charts/ChartWrapper";

export default function DashboardPage() {
  const [kpi, setKpi] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/tools/dashboard").then((d) => {
      setKpi(d);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-24 bg-slate-200 rounded-xl animate-pulse" />
        ))}
      </div>
    );
  }

  if (!kpi) return <div className="text-red-500">Không tải được dữ liệu</div>;

  const tx = kpi.transactions || {};
  const qt = kpi.quotations || {};
  const dv = kpi.deliveries || {};
  const trend = kpi.monthly_trend || [];
  const suppliers = kpi.supplier_ranking || [];
  const makers = kpi.top_makers || [];
  const alerts = kpi.alerts || [];
  const recent = kpi.recent || [];
  const typeSplit = kpi.type_split || {};

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page header */}
      <div>
        <h2 className="text-2xl font-bold">Tổng Quan</h2>
        <p className="text-sm text-slate-500">
          Bảng điều khiển hệ thống mua hàng — AMA Bắc Ninh
        </p>
      </div>

      {/* Alerts */}
      {alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((a: any, i: number) => (
            <div
              key={i}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm ${
                a.level === "warning"
                  ? "bg-amber-50 border border-amber-200 text-amber-800"
                  : "bg-blue-50 border border-blue-200 text-blue-800"
              }`}
            >
              <span>{a.level === "warning" ? "⚠️" : "ℹ️"}</span>
              {a.message}
            </div>
          ))}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <KpiCard label="Sản Phẩm" value={fmt(tx.unique_bqms)} color="blue" />
        <KpiCard label="Giao Dịch" value={fmt(tx.total)} color="green" sub={`${fmt(tx.unique_rfq)} RFQ`} />
        <KpiCard label="Tỷ Lệ Thắng" value={fmtPct(qt.win_rate)} color="purple" sub={`${fmt(qt.wins)} thắng / ${fmt(qt.losses)} thua`} />
        <KpiCard label="Tổng USD" value={`$${fmtMoney(tx.total_usd)}`} color="cyan" />
        <KpiCard label="Báo Giá" value={fmt(qt.total)} color="amber" />
        <KpiCard label="Giao Hàng" value={fmt(dv.total)} color="green" sub={`${fmt(dv.delivered)} đã giao`} />
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* Pie: GC vs TM */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="text-sm font-semibold mb-4">Phân Loại Sản Phẩm</h3>
          <div className="h-48">
            <Doughnut
              data={{
                labels: ["Gia Công (GC)", "Thương Mại (TM)", "Khác"],
                datasets: [{
                  data: [typeSplit.gc || 0, typeSplit.tm || 0, typeSplit.other || 0],
                  backgroundColor: ["#2563eb", "#059669", "#e2e8f0"],
                  borderWidth: 0,
                }],
              }}
              options={{
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { position: "bottom", labels: { font: { size: 11 } } } },
                cutout: "65%",
              }}
            />
          </div>
        </div>

        {/* Line: Monthly trend */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="text-sm font-semibold mb-4">Xu Hướng Báo Giá Theo Tháng</h3>
          <div className="h-48">
            <Line
              data={{
                labels: trend.map((t: any) => t.month?.slice(5) || ""),
                datasets: [
                  {
                    label: "Tổng", data: trend.map((t: any) => t.total),
                    borderColor: "#2563eb", backgroundColor: "rgba(37,99,235,0.08)",
                    fill: true, tension: 0.4, pointRadius: 3,
                  },
                  {
                    label: "Thắng", data: trend.map((t: any) => t.wins),
                    borderColor: "#059669", backgroundColor: "transparent",
                    tension: 0.4, pointRadius: 3, borderDash: [5, 5],
                  },
                ],
              }}
              options={{
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { position: "bottom", labels: { font: { size: 11 } } } },
                scales: { y: { beginAtZero: true, ticks: { font: { size: 10 } } }, x: { ticks: { font: { size: 10 } } } },
              }}
            />
          </div>
        </div>

        {/* Bar: Top suppliers */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="text-sm font-semibold mb-4">Nhà Cung Cấp Hàng Đầu</h3>
          <div className="h-48">
            <Bar
              data={{
                labels: suppliers.slice(0, 6).map((s: any) => truncate(s.supplier, 15)),
                datasets: [{
                  label: "Tỷ lệ thắng %",
                  data: suppliers.slice(0, 6).map((s: any) => s.win_pct),
                  backgroundColor: suppliers.slice(0, 6).map((_: any, i: number) =>
                    ["#2563eb", "#059669", "#7c3aed", "#d97706", "#0891b2", "#dc2626"][i]
                  ),
                  borderRadius: 6,
                }],
              }}
              options={{
                responsive: true, maintainAspectRatio: false,
                indexAxis: "y" as const,
                plugins: { legend: { display: false } },
                scales: { x: { max: 100, ticks: { font: { size: 10 } } }, y: { ticks: { font: { size: 10 } } } },
              }}
            />
          </div>
        </div>
      </div>

      {/* Row 2: Makers + Recent */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Top makers */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="text-sm font-semibold mb-3">Hãng Sản Xuất Phổ Biến</h3>
          <div className="grid grid-cols-2 gap-2">
            {makers.map((m: any, i: number) => (
              <div key={i} className="flex items-center justify-between bg-slate-50 rounded-lg px-3 py-2">
                <span className="text-xs text-slate-600 truncate max-w-[140px]">{m.maker}</span>
                <span className="text-sm font-bold text-brand">{fmt(m.cnt)}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Recent transactions */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="text-sm font-semibold mb-3">Giao Dịch Gần Đây</h3>
          <div className="space-y-1.5">
            {recent.map((r: any, i: number) => (
              <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-slate-50 transition text-xs">
                <span className={`px-2 py-0.5 rounded text-[9px] font-semibold ${
                  r.type === "gc" ? "bg-blue-100 text-blue-700" :
                  r.type === "tm" ? "bg-emerald-100 text-emerald-700" :
                  "bg-slate-100 text-slate-500"
                }`}>
                  {r.type || "—"}
                </span>
                <span className="font-mono text-slate-500">{r.rfq_no}</span>
                <span className="flex-1 truncate text-slate-700">{truncate(r.spec, 40)}</span>
                <span className="text-slate-400">{fmtDate(r.transaction_date)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
