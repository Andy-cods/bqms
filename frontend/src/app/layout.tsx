import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Song Chau ERP",
  description: "Hệ thống tự động hóa mua hàng — AMA Bắc Ninh",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body className="bg-slate-50 text-slate-900">{children}</body>
    </html>
  );
}
