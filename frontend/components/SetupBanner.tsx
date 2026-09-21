"use client";

import Link from "next/link";
import { useCurrentUser } from "@/lib/current-user";
import { useApiQuery } from "@/lib/use-api-query";
import type { SetupStatus } from "@/lib/types";

/** A nudge for the manager while first-run setup is unfinished: the wizard is resumable from any
 *  browser, so this is how someone who closed the tab (or signed in elsewhere) finds their way back.
 *  Hidden for everyone who could not act on it, and once setup is complete. */
export function SetupBanner() {
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
      <Link href="/setup" className="rounded bg-sky-600 px-3 py-1.5 font-medium text-white hover:bg-sky-700">
        {data.needed ? "شروع راه‌اندازی" : "ادامهٔ راه‌اندازی"}
      </Link>
    </div>
  );
}
