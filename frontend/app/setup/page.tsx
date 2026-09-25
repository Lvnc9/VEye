import type { Metadata } from "next";
import { SetupWizard } from "./SetupWizard";

export const metadata: Metadata = { title: "راه‌اندازی | وی‌آی" };

// Public (see proxy.ts): on a fresh deployment nobody can sign in yet. The server decides what
// this page may do (no setup token since 2026-09-25): create the first مدیر عامل only while none
// exists, otherwise sign in and start — not by hiding this page.
export default function SetupPage() {
  return <SetupWizard />;
}
