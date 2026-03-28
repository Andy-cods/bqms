"use client";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSearch: () => void;
  placeholder?: string;
}

export default function SearchBar({ value, onChange, onSearch, placeholder }: Props) {
  return (
    <div className="flex gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && onSearch()}
        placeholder={placeholder || "Tìm kiếm..."}
        className="px-4 py-2 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand/20 focus:border-brand transition w-64"
      />
      <button
        onClick={onSearch}
        className="px-4 py-2 bg-brand hover:bg-brand-dark text-white text-sm font-medium rounded-xl transition"
      >
        Tìm
      </button>
    </div>
  );
}
