"use client";
import { useState } from "react";
import { apiFetch } from "@/lib/api";
import PageHeader from "@/components/ui/PageHeader";

export default function ClassifyPage() {
  const [step, setStep] = useState(1);
  const [items, setItems] = useState("");
  const [results, setResults] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleClassify = async () => {
    const parsed = items.split("\n").filter(Boolean).map((line) => {
      const parts = line.split(/[,\t]+/);
      return { bqms_code: parts[0]?.trim(), spec: parts[1]?.trim() || "" };
    });
    if (!parsed.length) return;
    setLoading(true); setStep(2);
    const data = await apiFetch("/tools/classify", { method: "POST", body: JSON.stringify(parsed) });
    setResults(data); setLoading(false); setStep(3);
  };

  const decisionColor: Record<string, string> = {
    yes: "bg-emerald-50 border-emerald-200 text-emerald-700",
    no: "bg-red-50 border-red-200 text-red-700",
    maybe: "bg-amber-50 border-amber-200 text-amber-700",
  };
  const decisionLabel: Record<string, string> = { yes: "Tham gia", no: "Bỏ qua", maybe: "Xem xét" };

  return (
    <div className="animate-fade-in max-w-4xl">
      <PageHeader title="Phân Loại AI" subtitle="Phân tích đơn hàng tự động dựa trên lịch sử thắng/thua" />

      <div className="flex items-center gap-2 mb-6">
        {["Nhập đơn hàng", "AI xử lý", "Kết quả"].map((label, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
              step > i + 1 ? "bg-emerald-500 text-white" : step === i + 1 ? "bg-violet-600 text-white" : "bg-slate-200 text-slate-500"}`}>
              {step > i + 1 ? "✓" : i + 1}
            </div>
            <span className={`text-xs ${step === i + 1 ? "text-violet-600 font-medium" : "text-slate-400"}`}>{label}</span>
            {i < 2 && <div className="w-12 h-px bg-slate-200" />}
          </div>
        ))}
      </div>

      {step === 1 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h3 className="text-sm font-semibold mb-2">Nhập danh sách đơn hàng</h3>
          <p className="text-xs text-slate-500 mb-4">Mỗi dòng: Mã BQMS, Spec (phân cách dấu phẩy)</p>
          <textarea value={items} onChange={(e) => setItems(e.target.value)} rows={6}
            placeholder="Z0000001-709890, ALIGN BRACKET SUS 304" className="w-full px-4 py-3 border border-slate-200 rounded-xl text-sm font-mono focus:outline-none focus:ring-2 focus:ring-violet-200 focus:border-violet-500" />
          <button onClick={handleClassify} disabled={!items.trim()}
            className="mt-4 px-6 py-2.5 bg-violet-600 hover:bg-violet-700 text-white rounded-xl text-sm font-medium transition disabled:opacity-40">
            🤖 Chạy phân loại AI →
          </button>
        </div>
      )}

      {step === 2 && loading && (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <div className="text-4xl mb-4 animate-bounce">🤖</div>
          <p className="text-sm text-slate-600">AI đang phân tích lịch sử đơn hàng...</p>
          <div className="w-48 h-1.5 bg-slate-200 rounded-full mx-auto mt-4 overflow-hidden">
            <div className="h-full bg-violet-500 rounded-full animate-pulse w-2/3" />
          </div>
        </div>
      )}

      {step === 3 && results && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center">
              <div className="text-2xl font-bold text-emerald-600">{results.summary?.yes}</div>
              <div className="text-[10px] text-emerald-500 uppercase">Tham gia</div>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center">
              <div className="text-2xl font-bold text-red-600">{results.summary?.no}</div>
              <div className="text-[10px] text-red-500 uppercase">Bỏ qua</div>
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center">
              <div className="text-2xl font-bold text-amber-600">{results.summary?.maybe}</div>
              <div className="text-[10px] text-amber-500 uppercase">Xem xét</div>
            </div>
          </div>

          {results.results?.map((r: any, i: number) => (
            <div key={i} className={`rounded-xl border p-4 ${decisionColor[r.decision] || "bg-white border-slate-200"}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-xs">{r.input?.bqms_code}</span>
                <span className="text-xs font-bold">{decisionLabel[r.decision] || r.decision}</span>
              </div>
              <div className="text-xs opacity-80">{r.reason}</div>
              <div className="flex gap-4 mt-2 text-[10px] opacity-60">
                <span>Thắng: {r.history?.wins}</span>
                <span>Thua: {r.history?.losses}</span>
                <span>Có giá: {r.history?.has_price}</span>
                <span>Độ tin cậy: {(r.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
          ))}

          <button onClick={() => { setStep(1); setResults(null); }}
            className="px-4 py-2 border border-slate-200 rounded-xl text-sm text-slate-600 hover:bg-slate-50 transition">
            ← Phân loại mới
          </button>
        </div>
      )}
    </div>
  );
}
