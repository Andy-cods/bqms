"use client";
import { useState } from "react";
import { apiFetch } from "@/lib/api";
import PageHeader from "@/components/ui/PageHeader";

export default function AutoFillPage() {
  const [step, setStep] = useState(1);
  const [items, setItems] = useState("");
  const [results, setResults] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    const parsed = items.split("\n").filter(Boolean).map((line) => {
      const parts = line.split(/[,\t]+/);
      return { bqms_code: parts[0]?.trim(), spec: parts[1]?.trim() || "", maker: parts[2]?.trim() || "" };
    });
    if (!parsed.length) return;
    setLoading(true);
    setStep(2);
    const data = await apiFetch("/tools/autofill", { method: "POST", body: JSON.stringify(parsed) });
    setResults(data);
    setLoading(false);
    setStep(3);
  };

  return (
    <div className="animate-fade-in max-w-4xl">
      <PageHeader title="Tự Động Điền Báo Giá" subtitle="Tra cứu sản phẩm và lịch sử giá từ cơ sở dữ liệu" />

      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-6">
        {["Nhập dữ liệu", "Đang xử lý", "Kết quả"].map((label, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
              step > i + 1 ? "bg-emerald-500 text-white" : step === i + 1 ? "bg-brand text-white" : "bg-slate-200 text-slate-500"}`}>
              {step > i + 1 ? "✓" : i + 1}
            </div>
            <span className={`text-xs ${step === i + 1 ? "text-brand font-medium" : "text-slate-400"}`}>{label}</span>
            {i < 2 && <div className="w-12 h-px bg-slate-200" />}
          </div>
        ))}
      </div>

      {/* Step 1: Input */}
      {step === 1 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h3 className="text-sm font-semibold mb-3">Nhập danh sách sản phẩm</h3>
          <p className="text-xs text-slate-500 mb-4">Mỗi dòng 1 sản phẩm: Mã BQMS, Spec, Maker (phân cách bằng dấu phẩy hoặc tab)</p>
          <textarea
            value={items}
            onChange={(e) => setItems(e.target.value)}
            rows={8}
            placeholder={"Z0000001-709890, ALIGN BRACKET SUS 304, SEC\nR100100W-000308, TAPE SHIELDING, SAMSUNG"}
            className="w-full px-4 py-3 border border-slate-200 rounded-xl text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand/20 focus:border-brand"
          />
          <button onClick={handleSubmit} disabled={!items.trim()}
            className="mt-4 px-6 py-2.5 bg-brand hover:bg-brand-dark text-white rounded-xl text-sm font-medium transition disabled:opacity-40">
            Tra cứu sản phẩm →
          </button>
        </div>
      )}

      {/* Step 2: Loading */}
      {step === 2 && loading && (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <div className="w-10 h-10 border-3 border-brand border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-sm text-slate-600">Đang tra cứu sản phẩm trong cơ sở dữ liệu...</p>
        </div>
      )}

      {/* Step 3: Results */}
      {step === 3 && results && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center">
              <div className="text-2xl font-bold text-blue-600">{results.summary?.total}</div>
              <div className="text-[10px] text-blue-500 uppercase">Tổng</div>
            </div>
            <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center">
              <div className="text-2xl font-bold text-emerald-600">{results.summary?.matched}</div>
              <div className="text-[10px] text-emerald-500 uppercase">Tìm thấy</div>
            </div>
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center">
              <div className="text-2xl font-bold text-amber-600">{results.summary?.with_price}</div>
              <div className="text-[10px] text-amber-500 uppercase">Có giá</div>
            </div>
          </div>

          {results.results?.map((r: any, i: number) => (
            <div key={i} className="bg-white rounded-xl border border-slate-200 p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className={`w-2 h-2 rounded-full ${r.match_count > 0 ? "bg-emerald-500" : "bg-slate-300"}`} />
                <span className="font-mono text-xs text-slate-500">{r.input?.bqms_code}</span>
                <span className="text-xs text-slate-700">{r.input?.spec}</span>
              </div>
              {r.product_matches?.length > 0 ? (
                <div className="ml-4 space-y-1">
                  {r.product_matches.map((m: any, j: number) => (
                    <div key={j} className="text-xs text-slate-600 flex gap-4">
                      <span className="font-medium">{m.maker}</span>
                      <span className="truncate flex-1">{m.spec}</span>
                      <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-600 text-[10px]">{m.type || "—"}</span>
                    </div>
                  ))}
                  {r.price_history?.length > 0 && (
                    <div className="text-[10px] text-slate-400 mt-1">
                      Lịch sử giá: {r.price_history.map((p: any) => `V1=${p.price_bqms_v1 || "—"}`).slice(0, 3).join(", ")}
                    </div>
                  )}
                </div>
              ) : (
                <div className="ml-4 text-xs text-slate-400">Không tìm thấy trong cơ sở dữ liệu</div>
              )}
            </div>
          ))}

          <button onClick={() => { setStep(1); setResults(null); }}
            className="px-4 py-2 border border-slate-200 rounded-xl text-sm text-slate-600 hover:bg-slate-50 transition">
            ← Tra cứu mới
          </button>
        </div>
      )}
    </div>
  );
}
