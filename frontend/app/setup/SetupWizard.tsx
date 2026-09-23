"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { OrgTreeList } from "@/components/OrgTreeList";
import { AccountStep } from "@/components/setup/AccountStep";
import { CompanyStep } from "@/components/setup/CompanyStep";
import { ReadyStep } from "@/components/setup/ReadyStep";
import { SectionsStep } from "@/components/setup/SectionsStep";
import { StartSetupButton } from "@/components/setup/StartSetupButton";
import { UnitsStep } from "@/components/setup/UnitsStep";
import { DarkError, StepCard, primaryButton } from "@/components/setup/ui";
import { apiGetIfSignedIn } from "@/lib/api-client";
import { useApiQuery } from "@/lib/use-api-query";
import type { Company, OrgTreeResponse } from "@/lib/organization";
import { CHART_STEPS, wizardStepFor, type WizardStep } from "@/lib/setup";
import { hasCapability, type SetupStatus, type User } from "@/lib/types";

/**
 * The first-run wizard. There is **no draft state**: every step writes real rows through the
 * ordinary `/org/` API, and `Company.setup_step` is only a bookmark, so a refresh, a crash or another
 * browser lands back on the right step from `GET /setup/status/` + `GET /org/tree/`.
 */
export function SetupWizard() {
  const [reload, setReload] = useState(0);
  const status = useApiQuery<SetupStatus>("/setup/status/", reload);
  const refresh = () => setReload((n) => n + 1);

  return (
    <main className="min-h-screen bg-surface text-slate-100">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-8">
        <header className="mb-8 flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-surface-raised text-lg font-bold text-accent">
            وی
          </span>
          <div>
            <h1 className="text-lg font-bold">راه‌اندازی وی‌آی</h1>
            <p className="text-xs text-slate-500">حساب مدیر عامل و ساختار سازمان</p>
          </div>
        </header>

        {status.loading ? (
          <p className="text-sm text-slate-400">در حال بارگذاری...</p>
        ) : status.error || !status.data ? (
          <DarkError message={status.error ?? "دریافت وضعیت راه‌اندازی ممکن نشد."} />
        ) : status.data.needed ? (
          <div className="mx-auto max-w-xl">
            <FirstStep status={status.data} onDone={refresh} />
          </div>
        ) : (
          <SignedInWizard status={status.data} reload={reload} refresh={refresh} />
        )}
      </div>
    </main>
  );
}

/**
 * No company yet. A signed-in مدیر عامل gets one button and no setup token (decided with the owner
 * 2026-09-23); a visitor with no session — a fresh install, where nobody can sign in yet — gets the
 * token form. The session check must not bounce that visitor to /login, hence apiGetIfSignedIn.
 */
function FirstStep({ status, onDone }: { status: SetupStatus; onDone: () => void }) {
  const [me, setMe] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    apiGetIfSignedIn<User>("/auth/me/")
      .then((user) => !cancelled && setMe(user))
      .catch(() => !cancelled && setMe(null));
    return () => {
      cancelled = true;
    };
  }, []);

  if (me === undefined) return <p className="text-sm text-slate-400">در حال بارگذاری...</p>;
  if (!me || !hasCapability(me, "manage_organization")) return <AccountStep status={status} onDone={onDone} />;

  return (
    <StepCard
      title="راه‌اندازی شرکت"
      intro={`با حساب ${me.full_name} وارد شده‌اید؛ شما مدیر عامل و ریشهٔ ساختار سازمان خواهید بود. در گام بعد نام شرکت، لوگو و حوزه‌ها را تعیین می‌کنید.`}
    >
      <StartSetupButton onStarted={onDone} className={`${primaryButton} w-full`} errorClassName="text-sm text-red-300" />
    </StepCard>
  );
}

/** Mounted only once a company exists, so its (authenticated) requests never run on a fresh database. */
function SignedInWizard({ status, reload, refresh }: { status: SetupStatus; reload: number; refresh: () => void }) {
  const me = useApiQuery<User>("/auth/me/");
  const tree = useApiQuery<OrgTreeResponse>("/org/tree/", reload);
  const company = useApiQuery<Company>("/org/company/", reload);
  const [chosen, setChosen] = useState<WizardStep | null>(null);

  if (me.loading || tree.loading || company.loading) return <p className="text-sm text-slate-400">در حال بارگذاری...</p>;

  const signedIn = me.data !== null;
  const step = chosen ?? wizardStepFor(status, signedIn);

  if (step === "done") {
    return (
      <div className="mx-auto max-w-xl">
        <StepCard title="راه‌اندازی انجام شده است" intro="ساختار سازمان از قبل ساخته شده است.">
          <Link href="/dashboard" className={`${primaryButton} inline-block`}>
            رفتن به نرم‌افزار
          </Link>
        </StepCard>
      </div>
    );
  }

  if (!signedIn || step === "login") {
    return (
      <div className="mx-auto max-w-xl">
        <StepCard title="راه‌اندازی در جریان است" intro="برای ادامه، با حساب مدیر عامل وارد شوید.">
          <Link href="/login?next=%2Fsetup" className={`${primaryButton} inline-block`}>
            رفتن به صفحهٔ ورود
          </Link>
        </StepCard>
      </div>
    );
  }

  if (!hasCapability(me.data, "manage_organization")) {
    return (
      <div className="mx-auto max-w-xl">
        <StepCard title="دسترسی لازم را ندارید" intro="راه‌اندازی ساختار سازمان را فقط مدیر عامل می‌تواند ادامه دهد. با آن حساب وارد شوید.">
          <Link href="/dashboard" className={`${primaryButton} inline-block`}>
            رفتن به نرم‌افزار
          </Link>
        </StepCard>
      </div>
    );
  }

  const nodes = tree.data?.nodes ?? [];
  const companyData = company.data;
  if (!companyData || tree.error || company.error) {
    return <DarkError message={tree.error ?? company.error ?? "دریافت اطلاعات شرکت ممکن نشد."} />;
  }

  const go = (next: WizardStep) => () => setChosen(next);
  const current = step === "account" ? "company" : step;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="space-y-6">
        <nav aria-label="مراحل راه‌اندازی">
          <ol className="flex flex-wrap gap-2 text-xs">
            {CHART_STEPS.map((item, index) => {
              const active = item.key === current;
              return (
                <li key={item.key}>
                  <button
                    type="button"
                    onClick={go(item.key)}
                    aria-current={active ? "step" : undefined}
                    className={`rounded-full border px-3 py-1.5 transition-colors ${
                      active ? "border-accent bg-accent/15 text-accent" : "border-line text-slate-400 hover:bg-white/5"
                    }`}
                  >
                    {index + 1}. {item.title}
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>

        {current === "company" && <CompanyStep company={companyData} nodes={nodes} onChanged={refresh} onNext={go("units")} />}
        {current === "units" && (
          <UnitsStep
            rootId={companyData.root}
            rootName={companyData.name}
            nodes={nodes}
            onChanged={refresh}
            onBack={go("company")}
            onNext={go("sections")}
          />
        )}
        {current === "sections" && <SectionsStep nodes={nodes} onChanged={refresh} onBack={go("units")} onNext={go("ready")} />}
        {current === "ready" && <ReadyStep nodes={nodes} onBack={go("sections")} />}
      </div>

      <aside aria-label="پیش‌نمایش ساختار" className="h-fit rounded-2xl border border-line bg-surface-raised p-4 lg:sticky lg:top-6">
        <h2 className="mb-3 text-sm font-semibold text-slate-200">ساختاری که تا اینجا ساخته‌اید</h2>
        <OrgTreeList nodes={nodes} tone="dark" />
        {tree.data?.truncated && <p className="mt-3 text-xs text-slate-500">فقط دو سطح بالا نمایش داده می‌شود.</p>}
      </aside>
    </div>
  );
}
