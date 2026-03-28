export function fmt(n: number | null | undefined): string {
  if (n == null) return "—";
  return Number(n).toLocaleString("vi-VN");
}

export function fmtMoney(n: number | null | undefined): string {
  if (n == null) return "—";
  if (Math.abs(n) >= 1_000_000) return fmt(Math.round(n / 1_000_000)) + "M";
  if (Math.abs(n) >= 1_000) return fmt(Math.round(n / 1_000)) + "K";
  return fmt(Math.round(n * 100) / 100);
}

export function fmtDate(d: string | null | undefined): string {
  if (!d) return "—";
  try {
    return new Date(d).toLocaleDateString("vi-VN");
  } catch {
    return d;
  }
}

export function fmtPct(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${Number(n).toFixed(1)}%`;
}

export function truncate(s: string | null | undefined, max = 50): string {
  if (!s) return "";
  return s.length > max ? s.slice(0, max) + "..." : s;
}
