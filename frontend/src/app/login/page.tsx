"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiLogin } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@songchau.vn");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    const data = await apiLogin(email, password);
    setLoading(false);
    if (data.access_token) {
      sessionStorage.setItem("token", data.access_token);
      sessionStorage.setItem("user", JSON.stringify(data.user));
      router.push("/dashboard");
    } else {
      setError(data.error || "Đăng nhập thất bại");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 to-blue-50">
      <form
        onSubmit={handleLogin}
        className="bg-white rounded-2xl shadow-xl shadow-blue-900/5 border border-slate-200 p-10 w-[400px] animate-fade-in"
      >
        <h1 className="text-2xl font-bold mb-1">
          <span className="text-brand">Song Chau</span> ERP
        </h1>
        <p className="text-sm text-slate-400 mb-8">
          Hệ thống quản lý mua hàng — AMA Bắc Ninh
        </p>

        <div className="mb-4">
          <label className="block text-xs font-medium text-slate-500 mb-1.5">
            Email
          </label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand/20 focus:border-brand transition"
            placeholder="admin@songchau.vn"
          />
        </div>
        <div className="mb-4">
          <label className="block text-xs font-medium text-slate-500 mb-1.5">
            Mật khẩu
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-4 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-brand/20 focus:border-brand transition"
            placeholder="••••••••"
          />
        </div>

        {error && (
          <p className="text-red-500 text-xs mb-3 bg-red-50 px-3 py-2 rounded-lg">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-brand hover:bg-brand-dark text-white font-medium py-2.5 rounded-xl transition disabled:opacity-50"
        >
          {loading ? "Đang đăng nhập..." : "Đăng Nhập"}
        </button>
      </form>
    </div>
  );
}
