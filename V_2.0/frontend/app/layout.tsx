import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

// The same Vazir build the desktop app embeds in its PDFs, so the web UI and
// the generated documents render Persian identically.
const vazir = localFont({
  src: [
    { path: "./fonts/Vazir.ttf", weight: "400", style: "normal" },
    { path: "./fonts/Vazir-Bold.ttf", weight: "700", style: "normal" },
  ],
  variable: "--font-vazir",
  display: "swap",
});

export const metadata: Metadata = {
  title: "وی‌آی | سامانه کنترل مستندات",
  description: "سامانه مدیریت و کنترل مستندات",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fa" dir="rtl" className={`${vazir.variable} h-full`}>
      <body className="min-h-full bg-slate-100 text-slate-900 antialiased">{children}</body>
    </html>
  );
}
