import type { Metadata } from "next";
import { SetupWizard } from "./SetupWizard";

export const metadata: Metadata = { title: "راه‌اندازی | وی‌آی" };

// Public (see proxy.ts): on a fresh deployment nobody can sign in yet. Everything sensitive is
// behind the one-time setup token, checked by the server — not by hiding this page.
export default function SetupPage() {
  return <SetupWizard />;
}
