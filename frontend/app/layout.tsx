import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { InlineScript } from "@/components/InlineScript";
import { Providers } from "@/components/Providers";
import { THEME_INIT_SCRIPT } from "@/lib/theme";
import "./globals.css";

// The screen font (UI 2, owner's decision 2026-10-15): Vazirmatn, Vazir's successor by the same designer,
// with every weight from thin to black. Variable, one file. OFL — app/fonts/Vazirmatn-OFL.txt.
const vazirmatn = localFont({
  src: "./fonts/Vazirmatn-Variable.woff2",
  weight: "100 900",
  variable: "--font-vazirmatn",
  display: "swap",
});

// The same Vazir build the PDFs embed. Only the document paper uses it (`.paper`, `.rich-content`), so the
// on-screen preview of a document still matches its print; it loads when such a page needs it.
const vazir = localFont({
  src: [
    { path: "./fonts/Vazir.ttf", weight: "400", style: "normal" },
    { path: "./fonts/Vazir-Bold.ttf", weight: "700", style: "normal" },
  ],
  variable: "--font-vazir",
  display: "swap",
  preload: false,
});

export const metadata: Metadata = {
  title: "وی‌آی | سامانه کنترل مستندات",
  description: "سامانه مدیریت و کنترل مستندات",
};

export const viewport: Viewport = {
  // Content may reach under a phone's rounded corners and home bar; the bottom bar pads itself back
  // with env(safe-area-inset-bottom).
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f7fb" },
    { media: "(prefers-color-scheme: dark)", color: "#0a1020" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: the theme script below and browser extensions (Grammarly's `data-gr-*`,
    // translators, dark-mode add-ons) write onto <html>/<body> before React hydrates. It only silences
    // attribute mismatches on these two elements — anything inside {children} still warns.
    <html lang="fa" dir="rtl" className={`${vazirmatn.variable} ${vazir.variable} h-full`} suppressHydrationWarning>
      <head>
        {/* Before the first paint: the saved theme and sidebar state (lib/theme.ts). */}
        <InlineScript html={THEME_INIT_SCRIPT} />
      </head>
      <body className="min-h-full bg-background text-foreground antialiased" suppressHydrationWarning>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
