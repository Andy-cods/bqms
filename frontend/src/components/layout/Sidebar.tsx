"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { logout, getUser } from "@/lib/api";

const NAV = [
  { section: "TỔNG QUAN" },
  { href: "/dashboard", label: "Tổng Quan", icon: "📊" },
  { section: "DỮ LIỆU" },
  { href: "/san-pham", label: "Sản Phẩm", icon: "📦" },
  { href: "/giao-dich", label: "Giao Dịch", icon: "📋" },
  { href: "/bao-gia", label: "Báo Giá", icon: "💰" },
  { href: "/giao-hang", label: "Giao Hàng", icon: "🚚" },
  { section: "CÔNG CỤ" },
  { href: "/cong-cu/tu-dong-dien", label: "Tự Động Điền", icon: "⚡" },
  { href: "/cong-cu/phan-loai-ai", label: "Phân Loại AI", icon: "🤖" },
  { section: "QUẢN TRỊ" },
  { href: "/quan-tri/nguoi-dung", label: "Người Dùng", icon: "👥" },
  { href: "/quan-tri/nhat-ky", label: "Nhật Ký", icon: "📝" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const user = getUser();

  return (
    <aside className="w-[220px] bg-white border-r border-slate-200 fixed top-0 bottom-0 flex flex-col z-50">
      <div className="px-5 pt-5 pb-4">
        <h1 className="text-lg font-bold">
          <span className="text-brand">Song Chau</span> ERP
        </h1>
        <p className="text-[10px] text-slate-400 mt-0.5">AMA Bắc Ninh</p>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 space-y-0.5">
        {NAV.map((item, i) =>
          "section" in item ? (
            <div
              key={i}
              className="text-[9px] font-semibold text-slate-400 tracking-widest uppercase px-3 pt-5 pb-1"
            >
              {item.section}
            </div>
          ) : (
            <Link
              key={item.href}
              href={item.href!}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] transition-all ${
                pathname === item.href || pathname?.startsWith(item.href! + "/")
                  ? "bg-blue-50 text-brand font-semibold"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              }`}
            >
              <span className="text-sm">{item.icon}</span>
              {item.label}
            </Link>
          )
        )}
      </nav>

      <div className="p-4 border-t border-slate-100">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-8 h-8 rounded-full bg-brand/10 flex items-center justify-center text-brand text-xs font-bold">
            {user?.name?.[0] || "U"}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-medium truncate">{user?.name}</div>
            <div className="text-[10px] text-slate-400 capitalize">{user?.role}</div>
          </div>
        </div>
        <button
          onClick={logout}
          className="w-full text-xs text-slate-500 hover:text-red-600 border border-slate-200 rounded-lg py-1.5 transition"
        >
          Đăng Xuất
        </button>
      </div>
    </aside>
  );
}
