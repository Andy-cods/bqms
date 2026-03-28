interface KpiCardProps {
  label: string;
  value: string | number;
  sub?: string;
  color?: "blue" | "green" | "red" | "amber" | "purple" | "cyan";
  trend?: number;
}

const COLORS = {
  blue: "border-l-blue-500 text-blue-600",
  green: "border-l-emerald-500 text-emerald-600",
  red: "border-l-red-500 text-red-600",
  amber: "border-l-amber-500 text-amber-600",
  purple: "border-l-violet-500 text-violet-600",
  cyan: "border-l-cyan-500 text-cyan-600",
};

export default function KpiCard({ label, value, sub, color = "blue", trend }: KpiCardProps) {
  return (
    <div className={`bg-white rounded-xl border border-slate-200 border-l-4 ${COLORS[color].split(" ")[0]} p-5 animate-fade-in`}>
      <div className={`text-3xl font-bold tabular-nums ${COLORS[color].split(" ")[1]}`}>
        {value}
      </div>
      <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mt-1">
        {label}
      </div>
      {sub && <div className="text-xs text-slate-500 mt-1">{sub}</div>}
      {trend != null && (
        <div className={`text-xs mt-1 font-medium ${trend >= 0 ? "text-emerald-600" : "text-red-500"}`}>
          {trend >= 0 ? "↑" : "↓"} {Math.abs(trend)}%
        </div>
      )}
    </div>
  );
}
