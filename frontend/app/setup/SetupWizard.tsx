"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { OrgTreeList } from "@/components/OrgTreeList";
import { AccountStep } from "@/components/setup/AccountStep";
import { CompanyStep } from "@/components/setup/CompanyStep";
import { PeopleStep } from "@/components/setup/PeopleStep";
import { ReadyStep } from "@/components/setup/ReadyStep";
import { SectionsStep } from "@/components/setup/SectionsStep";
import { StartSetupButton } from "@/components/setup/StartSetupButton";
import { UnitsStep } from "@/components/setup/UnitsStep";
import { DarkError, StepCard, primaryButton } from "@/components/setup/ui";
import { apiGetIfSignedIn } from "@/lib/api-client";
import { Check } from "lucide-react";
import { BrandMark } from "@/components/ui/BrandMark";
import { useApiQuery } from "@/lib/use-api-query";
import type { Company, OrgTreeResponse } from "@/lib/organization";
import { CHART_STEPS, wizardStepFor, type WizardStep } from "@/lib/setup";
import type { SetupStatus, User } from "@/lib/types";

/**
 * The first-run wizard. There is **no draft state**: every step writes real rows through the
 * ordinary `/org/` API, and `Company.setup_step` is only a bookmark, so a refresh, a crash or another
 * browser lands back on the right step from `GET /setup/status/` + `GET /org/tree/`.
 */
export function SetupWizard() {
  const [statusReload, setStatusReload] = useState(0);
  const [nodeReload, setNodeReload] = useState(0);
  const status = useApiQuery<SetupStatus>("/setup/status/", statusReload);
  const refreshStatus = () => setStatusReload((n) => n + 1);
  const refreshNodes = () => setNodeReload((n) => n + 1);

  return (
    <main className="min-h-screen bg-surface text-slate-100">
      <div className="mx-auto max-w-6xl px-4 py-10 sm:px-8">
        <header className="mb-8 flex items-center gap-3">
          <BrandMark />
          <div>
            <h1 className="text-lg font-bold">راه‌اندازی وی‌آی</h1>
            <p className="text-xs text-slate-500">حساب توسعه‌دهنده و ساختار سازمان</p>
          </div>
        </header>

        {status.loading ? (
          <p className="text-sm text-slate-400">در حال بارگذاری...</p>
        ) : status.error || !status.data ? (
          <DarkError message={status.error ?? "دریافت وضعیت راه‌اندازی ممکن نشد."} />
        ) : !status.data.company_exists ? (
          <div className="mx-auto max-w-xl">
            {/* A fresh mount re-checks the session — bootstrap just signed a new one in. */}
            <FirstStep key={String(status.data.developer_exists)} status={status.data} onDone={refreshStatus} />
          </div>
        ) : (
          <SignedInWizard
            status={status.data}
            reload={nodeReload}
            refresh={refreshNodes}
            onPeopleChanged={() => {
              refreshNodes();
              refreshStatus(); // has_root_lead may have flipped
            }}
          />
        )}
      </div>
    </main>
  );
}

/**
 * No company yet. Three doors, decided by `status.developer_exists` and who (if anyone) is signed
 * in: the form that creates the **one** developer account; the developer's own «شروع راه‌اندازی»
 * once they are signed in; or, for anyone else, a pointer to sign in (or, if they already are
 * someone else, the Persian notice the ADR fixes: راه‌اندازی در حال انجام است — با توسعه‌دهنده
 * تماس بگیرید). The session check must not bounce a visitor to /login, hence apiGetIfSignedIn.
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

  if (!status.developer_exists) return <AccountStep onDone={onDone} />;
  if (me === undefined) return <p className="text-sm text-slate-400">در حال بارگذاری...</p>;

  if (me?.is_developer) {
    return (
      <StepCard
        title="راه‌اندازی شرکت"
        intro={`با حساب ${me.full_name} وارد شده‌اید. در گام بعد نام شرکت، لوگو و حوزه‌ها را تعیین می‌کنید.`}
      >
        <StartSetupButton onStarted={onDone} className={`${primaryButton} w-full`} errorClassName="text-sm text-rose-300" />
      </StepCard>
    );
  }

  if (!me) {
    return (
      <StepCard title="ادامهٔ راه‌اندازی" intro="راه‌اندازی شرکت را فقط توسعه‌دهنده می‌تواند ادامه دهد.">
        <Link href="/login?next=%2Fsetup" className={`${primaryButton} inline-block`}>
          رفتن به صفحهٔ ورود
        </Link>
      </StepCard>
    );
  }

  return (
    <StepCard title="راه‌اندازی در جریان است" intro="راه‌اندازی در حال انجام است — با توسعه‌دهنده تماس بگیرید.">
      <Link href="/dashboard" className={`${primaryButton} inline-block`}>
        رفتن به نرم‌افزار
      </Link>
    </StepCard>
  );
}

/** Mounted only once a company exists, so its (authenticated) requests never run on a fresh database. */
function SignedInWizard({
  status,
  reload,
  refresh,
  onPeopleChanged,
}: {
  status: SetupStatus;
  reload: number;
  refresh: () => void;
  onPeopleChanged: () => void;
}) {
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
        <StepCard title="راه‌اندازی در جریان است" intro="برای ادامه، با حساب توسعه‌دهنده وارد شوید.">
          <Link href="/login?next=%2Fsetup" className={`${primaryButton} inline-block`}>
            رفتن به صفحهٔ ورود
          </Link>
        </StepCard>
      </div>
    );
  }

  if (!me.data?.is_developer) {
    return (
      <div className="mx-auto max-w-xl">
        <StepCard title="راه‌اندازی در جریان است" intro="راه‌اندازی در حال انجام است — با توسعه‌دهنده تماس بگیرید.">
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
  const current = step;
  const currentIndex = CHART_STEPS.findIndex((item) => item.key === current);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="space-y-6">
        <nav aria-label="مراحل راه‌اندازی">
          <ol className="flex flex-wrap items-center gap-y-2 text-xs">
            {CHART_STEPS.map((item, index) => {
              const active = item.key === current;
              const done = index < currentIndex;
              return (
                <li key={item.key} className="flex items-center">
                  {index > 0 && (
                    <span
                      aria-hidden
                      className={`mx-1.5 h-px w-4 transition-colors duration-300 sm:w-6 ${done || active ? "bg-accent/60" : "bg-line"}`}
                    />
                  )}
                  <button
                    type="button"
                    onClick={go(item.key)}
                    aria-current={active ? "step" : undefined}
                    className={`flex items-center gap-2 rounded-full border py-1 ps-1 pe-3 transition-colors duration-200 ${
                      active
                        ? "border-accent bg-accent/15 text-accent"
                        : done
                          ? "border-accent/30 text-slate-200 hover:bg-white/5"
                          : "border-line text-slate-400 hover:bg-white/5"
                    }`}
                  >
                    <span
                      className={`flex size-6 items-center justify-center rounded-full text-[11px] font-bold transition-colors duration-200 ${
                        active ? "bg-accent text-slate-950" : done ? "bg-accent/20 text-accent" : "bg-white/5 text-slate-400"
                      }`}
                    >
                      {done ? <Check className="size-3.5" /> : index + 1}
                    </span>
                    {item.title}
                  </button>
                </li>
              );
            })}
          </ol>
        </nav>

        {/* Each step rises in when you move to it. */}
        <div key={current} className="veye-page">
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
        {current === "sections" && <SectionsStep nodes={nodes} onChanged={refresh} onBack={go("units")} onNext={go("people")} />}
        {current === "people" && (
          <PeopleStep status={status} onRegistered={onPeopleChanged} onBack={go("sections")} onNext={go("ready")} />
        )}
        {current === "ready" && <ReadyStep nodes={nodes} status={status} onBack={go("people")} onPeople={go("people")} />}
        </div>
      </div>

      <aside aria-label="پیش‌نمایش ساختار" className="h-fit rounded-2xl border border-line bg-surface-raised p-4 lg:sticky lg:top-6">
        <h2 className="mb-3 text-sm font-semibold text-slate-200">ساختاری که تا اینجا ساخته‌اید</h2>
        <OrgTreeList nodes={nodes} tone="dark" />
        {tree.data?.truncated && <p className="mt-3 text-xs text-slate-500">فقط دو سطح بالا نمایش داده می‌شود.</p>}
      </aside>
    </div>
  );
}
