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
    // suppressHydrationWarning: browser extensions (Grammarly's `data-gr-*`, translators, dark-mode
    // add-ons) write attributes onto <html>/<body> before React hydrates. It only silences attribute
    // mismatches on these two elements — anything inside {children} still warns.
    <html lang="fa" dir="rtl" className={`${vazir.variable} h-full`} suppressHydrationWarning>
      <body className="min-h-full bg-slate-100 text-slate-900 antialiased" suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
