const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T | null> {
  const token =
    typeof window !== "undefined" ? sessionStorage.getItem("token") : null;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  try {
    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (res.status === 401) {
      if (typeof window !== "undefined") {
        sessionStorage.clear();
        window.location.href = "/login";
      }
      return null;
    }
    return await res.json();
  } catch {
    return null;
  }
}

export async function apiLogin(
  email: string,
  password: string
): Promise<{ access_token?: string; user?: any; error?: string }> {
  const form = new URLSearchParams();
  form.append("username", email);
  form.append("password", password);
  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form,
    });
    return await res.json();
  } catch {
    return { error: "Loi ket noi" };
  }
}

export function getUser(): { name: string; role: string; email: string } | null {
  if (typeof window === "undefined") return null;
  const u = sessionStorage.getItem("user");
  return u ? JSON.parse(u) : null;
}

export function isLoggedIn(): boolean {
  if (typeof window === "undefined") return false;
  return !!sessionStorage.getItem("token");
}

export function logout() {
  sessionStorage.clear();
  window.location.href = "/login";
}
