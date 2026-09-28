"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { StartSetupButton } from "@/components/setup/StartSetupButton";
import { Alert } from "@/components/ui/Alert";
import { buttonClass } from "@/components/ui/Button";
import { useCurrentUser } from "@/lib/current-user";
import { useApiQuery } from "@/lib/use-api-query";
import type { SetupStatus } from "@/lib/types";

const BUTTON = buttonClass({ variant: "primary", size: "sm" });

/** A nudge for the developer while first-run setup is unfinished: the wizard is resumable from any
 *  browser, so this is how someone who closed the tab (or signed in elsewhere) finds their way back.
 *  Hidden for everyone else (Phase 10: the wizard is the developer's job, not `manage_organization`'s
 *  — the مدیر عامل holds that capability too but never runs the wizard), and once setup is complete. */
export function SetupBanner() {
  const router = useRouter();
  const { user } = useCurrentUser();
  const status = useApiQuery<SetupStatus>("/setup/status/");
  const data = status.data;
  if (!data || !user?.is_developer) return null;
  if (data.completed) return null;

  return (
    <Alert
      tone="info"
      role="status"
      className="mb-6"
      title={
        !data.company_exists
          ? "ساختار سازمان و شرکت هنوز تعریف نشده است."
          : "راه‌اندازی ساختار سازمان هنوز به پایان نرسیده است."
      }
      actions={
        !data.company_exists ? (
          // Already signed in as the developer: one press, straight into the wizard.
          <StartSetupButton
            onStarted={() => router.push("/setup")}
            className={BUTTON}
            errorClassName="w-full text-xs text-rose-700"
          />
        ) : (
          <Link href="/setup" className={BUTTON}>
            ادامهٔ راه‌اندازی
            <ArrowLeft />
          </Link>
        )
      }
    />
  );
}
