"use client";
import { useState } from "react";
import { apiFetch } from "@/lib/api";
import PageHeader from "@/components/ui/PageHeader";
import { fmt, fmtDate, truncate } from "@/lib/format";

export default function MarketSearchPage() {
  const [step, setStep] = useState(1);
  const [spec, setSpec] = useState("");
  const [jobId, setJobId] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);

  const startSearch = async () => {
    if (!spec.trim()) return;
    setLoading(true); setStep(2); setLogs([]);
    const res = await apiFetch("/tool-engine/tool5/search", {
      method: "POST", body: JSON.stringify({ spec, platforms: ["database"] }),
    });
    if (res?.job_id) {
      setJobId(res.job_id);
      pollJob(res.job_id);
    }
  };

  const pollJob = async (id: string) => {
    const poll = setInterval(async () => {
      const job = await apiFetch(`/tool-engine/job/${id}`);
      if (!job) return;
      setLogs(job.logs || []);
      if (job.status === "done") {
        clearInterval(poll);
        setResult(job.result);
        setLoading(false);
        setStep(3);
      } else if (job.status === "error") {
        clearInterval(poll);
        setLoading(false);
        setLogs([...job.logs, `LỖI: ${job.error}`]);
      }
    }, 1500);
  };

  return (
    <div className="animate-fade-in max-w-5xl">
      <PageHeader title="Khảo Giá Thị Trường" subtitle="Tìm kiếm giá sản phẩm từ cơ sở dữ liệu và lịch sử" />

      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-6">
        {["Nhập thông tin", "Đang tìm kiếm", "Kết quả"].map((label, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
              step > i + 1 ? "bg-emerald-500 text-white" : step === i + 1 ? "bg-cyan-600 text-white" : "bg-slate-200 text-slate-500"}`}>
              {step > i + 1 ? "✓" : i + 1}
            </div>
            <span className={`text-xs ${step === i + 1 ? "text-cyan-600 font-medium" : "text-slate-400"}`}>{label}</span>
            {i < 2 && <div className="w-12 h-px bg-slate-200" />}
          </div>
        ))}
      </div>

      {step === 1 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h3 className="text-sm font-semibold mb-3">Mô tả sản phẩm cần tìm</h3>
          <input value={spec} onChange={(e) => setSpec(e.target.value)} onKeyDown={(e) => e.key === "Enter" && startSearch()}
            placeholder="VD: TAPE SHIELDING, RESISTOR 10K 0402, CONNECTOR USB..."
            className="w-full px-4 py-3 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-cyan-200 focus:border-cyan-500" />
          <p className="text-xs text-slate-400 mt-2">Hệ thống sẽ tìm trong 62,000+ sản phẩm, 4,900+ báo giá, và giá thị trường đã lưu</p>
          <button onClick={startSearch} disabled={!spec.trim()}
            className="mt-4 px-6 py-2.5 bg-cyan-600 hover:bg-cyan-700 text-white rounded-xl text-sm font-medium transition disabled:opacity-40">
            🔍 Bắt đầu tìm kiếm →
          </button>
        </div>
      )}

      {step === 2 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-6 h-6 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm font-medium">Đang tìm kiếm "{spec}"...</span>
          </div>
          <div className="bg-slate-900 rounded-lg p-4 font-mono text-xs text-green-400 max-h-48 overflow-y-auto">
            {logs.map((l, i) => <div key={i}>{l}</div>)}
          </div>
        </div>
      )}

      {step === 3 && result && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "Sản phẩm DB", value: result.summary?.db_matches, color: "blue" },
              { label: "Lịch sử giá", value: result.summary?.price_history, color: "purple" },
              { label: "Giá thị trường", value: result.summary?.market_prices, color: "cyan" },
              { label: "Giá mua thực tế", value: result.summary?.actual_prices, color: "green" },
            ].map((s, i) => (
              <div key={i} className={`bg-${s.color}-50 border border-${s.color}-200 rounded-xl p-4 text-center`}>
                <div className={`text-2xl font-bold text-${s.color}-600`}>{s.value || 0}</div>
                <div className={`text-[10px] text-${s.color}-500 uppercase`}>{s.label}</div>
              </div>
            ))}
          </div>

          {/* Database matches */}
          {result.database_matches?.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="text-sm font-semibold mb-3">Sản phẩm trong cơ sở dữ liệu</h3>
              <div className="space-y-2">
                {result.database_matches.map((m: any, i: number) => (
                  <div key={i} className="flex items-center gap-3 px-3 py-2 bg-slate-50 rounded-lg text-xs">
                    <span className="font-mono text-slate-500 w-36">{m.bqms_code}</span>
                    <span className="flex-1 truncate">{m.product_name || m.spec}</span>
                    <span className="text-slate-400">{m.maker}</span>
                    <span className={`px-2 py-0.5 rounded text-[9px] font-bold ${m.type === "gc" ? "bg-blue-100 text-blue-700" : "bg-emerald-100 text-emerald-700"}`}>
                      {m.type || "—"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actual prices */}
          {result.actual_prices?.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 p-5">
              <h3 className="text-sm font-semibold mb-3">Giá mua thực tế</h3>
              <table className="w-full text-xs">
                <thead><tr className="text-left text-[10px] text-slate-500 uppercase border-b">
                  <th className="py-2 px-2">BQMS</th><th className="py-2">Spec</th><th className="py-2">USD</th><th className="py-2">VND</th><th className="py-2">Bên bán</th><th className="py-2">Ngày</th>
                </tr></thead>
                <tbody>{result.actual_prices.map((p: any, i: number) => (
                  <tr key={i} className="border-b border-slate-50">
                    <td className="py-2 px-2 font-mono">{p.bqms_code}</td>
                    <td className="py-2 truncate max-w-[200px]">{truncate(p.spec, 40)}</td>
                    <td className="py-2 font-medium">{p.unit_price_usd ? `$${fmt(p.unit_price_usd)}` : "—"}</td>
                    <td className="py-2">{p.unit_price_vnd ? fmt(p.unit_price_vnd) : "—"}</td>
                    <td className="py-2 truncate max-w-[150px]">{truncate(p.seller, 30)}</td>
                    <td className="py-2 text-slate-400">{fmtDate(p.transaction_date)}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}

          <button onClick={() => { setStep(1); setResult(null); setLogs([]); }}
            className="px-4 py-2 border border-slate-200 rounded-xl text-sm text-slate-600 hover:bg-slate-50 transition">
            ← Tìm kiếm mới
          </button>
        </div>
      )}
    </div>
  );
}
