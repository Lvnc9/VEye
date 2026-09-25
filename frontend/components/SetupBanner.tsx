"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { StartSetupButton } from "@/components/setup/StartSetupButton";
import { useCurrentUser } from "@/lib/current-user";
import { useApiQuery } from "@/lib/use-api-query";
import type { SetupStatus } from "@/lib/types";

const BUTTON = "rounded bg-sky-600 px-3 py-1.5 font-medium text-white hover:bg-sky-700";

/** A nudge for the manager while first-run setup is unfinished: the wizard is resumable from any
 *  browser, so this is how someone who closed the tab (or signed in elsewhere) finds their way back.
 *  Hidden for everyone who could not act on it, and once setup is complete. */
export function SetupBanner() {
  const router = useRouter();
  const { can } = useCurrentUser();
  const status = useApiQuery<SetupStatus>("/setup/status/");
  const data = status.data;
  if (!data || !can("manage_organization")) return null;
  if (!data.needed && data.step === "DONE") return null;

  return (
    <div role="status" className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900">
      <span>
        {data.needed
          ? "ساختار سازمان و شرکت هنوز تعریف نشده است."
          : "راه‌اندازی ساختار سازمان هنوز به پایان نرسیده است."}
      </span>
      {data.needed ? (
        // Already signed in as the مدیر عامل: one press, straight into the wizard.
        <StartSetupButton
          onStarted={() => router.push("/setup")}
          className={`${BUTTON} disabled:opacity-50`}
          errorClassName="w-full text-xs text-red-700"
        />
      ) : (
        <Link href="/setup" className={BUTTON}>
          ادامهٔ راه‌اندازی
        </Link>
      )}
    </div>
  );
}
