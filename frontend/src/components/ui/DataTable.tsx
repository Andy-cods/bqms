"use client";

import { useState } from "react";
import { fmtDate, fmt, truncate } from "@/lib/format";

export interface Column {
  key: string;
  label: string;
  type?: "text" | "date" | "number" | "money" | "badge" | "trunc";
  badgeMap?: Record<string, string>;
  width?: string;
}

interface Props {
  columns: Column[];
  data: any[];
  total: number;
  page: number;
  pages: number;
  onPageChange: (p: number) => void;
  loading?: boolean;
  emptyText?: string;
  onRowClick?: (row: any) => void;
}

function renderCell(row: any, col: Column) {
  const v = row[col.key];
  if (v == null || v === "") return <span className="text-slate-300">—</span>;

  switch (col.type) {
    case "date":
      return <span className="tabular-nums text-slate-500">{fmtDate(v)}</span>;
    case "number":
      return <span className="tabular-nums">{fmt(v)}</span>;
    case "money":
      return <span className="tabular-nums">{v != null ? fmt(Math.round(Number(v))) : "—"}</span>;
    case "badge": {
      const colors: Record<string, string> = {
        gc: "bg-blue-100 text-blue-700",
        tm: "bg-emerald-100 text-emerald-700",
        Y: "bg-emerald-100 text-emerald-700",
        y: "bg-emerald-100 text-emerald-700",
        N: "bg-red-100 text-red-700",
        n: "bg-red-100 text-red-700",
        ...(col.badgeMap || {}),
      };
      const cls = colors[v] || "bg-slate-100 text-slate-600";
      return <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${cls}`}>{v}</span>;
    }
    case "trunc":
      return <span className="block max-w-[200px] truncate" title={v}>{truncate(v, 45)}</span>;
    default:
      return <span>{String(v)}</span>;
  }
}

export default function DataTable({ columns, data, total, page, pages, onPageChange, loading, emptyText, onRowClick }: Props) {
  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-12 border-b border-slate-100 flex items-center px-4 gap-4">
            {columns.map((_, j) => (
              <div key={j} className="h-4 bg-slate-100 rounded animate-pulse flex-1" />
            ))}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="px-3 py-2.5 text-left text-[10px] font-semibold text-slate-500 uppercase tracking-wider"
                  style={col.width ? { width: col.width } : undefined}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="text-center py-12 text-slate-400 text-sm">
                  {emptyText || "Không có dữ liệu"}
                </td>
              </tr>
            ) : (
              data.map((row, i) => (
                <tr
                  key={row.id || i}
                  className={`border-b border-slate-50 hover:bg-blue-50/30 transition ${onRowClick ? "cursor-pointer" : ""}`}
                  onClick={() => onRowClick?.(row)}
                >
                  {columns.map((col) => (
                    <td key={col.key} className="px-3 py-2.5">
                      {renderCell(row, col)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100 bg-slate-50/50">
          <span className="text-[11px] text-slate-400">
            {fmt(total)} kết quả · Trang {page}/{pages}
          </span>
          <div className="flex gap-1">
            <button
              onClick={() => onPageChange(Math.max(1, page - 1))}
              disabled={page <= 1}
              className="px-2.5 py-1 text-[11px] border border-slate-200 rounded-md bg-white hover:bg-slate-50 disabled:opacity-40 transition"
            >
              ←
            </button>
            {Array.from({ length: Math.min(pages, 7) }, (_, i) => {
              let p: number;
              if (pages <= 7) p = i + 1;
              else if (page <= 4) p = i + 1;
              else if (page >= pages - 3) p = pages - 6 + i;
              else p = page - 3 + i;
              return (
                <button
                  key={p}
                  onClick={() => onPageChange(p)}
                  className={`px-2.5 py-1 text-[11px] rounded-md transition ${
                    p === page
                      ? "bg-brand text-white border border-brand"
                      : "border border-slate-200 bg-white hover:bg-slate-50"
                  }`}
                >
                  {p}
                </button>
              );
            })}
            <button
              onClick={() => onPageChange(Math.min(pages, page + 1))}
              disabled={page >= pages}
              className="px-2.5 py-1 text-[11px] border border-slate-200 rounded-md bg-white hover:bg-slate-50 disabled:opacity-40 transition"
            >
              →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
