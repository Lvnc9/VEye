"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, SearchCheck } from "lucide-react";
import { findingsSummary, type InternalAudit, type NonConformance } from "@/lib/quality";
import { usePagedQuery } from "@/lib/use-paged-query";
import { FindingFormDialog } from "@/components/quality/FindingFormDialog";
import { NcListItem } from "@/components/quality/NcListItem";
import { ErrorBanner } from "@/components/StatusBanner";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { SkeletonLines } from "@/components/ui/Skeleton";

/**
 * «یافته‌ها»: the non-conformances this audit raised, listed from the ordinary endpoint (`?audit=`) —
 * a finding is a record like any other, so each row is the same row as on `/quality` and opens the same
 * page. «ثبت یافته» is offered only while the audit runs and the viewer runs it (`can_raise_finding`).
 */
export function FindingsPanel({ audit, version, onChanged }: { audit: InternalAudit; version: number; onChanged: () => void }) {
  const router = useRouter();
  const [adding, setAdding] = useState(false);
  const findings = usePagedQuery<NonConformance>("/quality/nonconformances/", { audit: audit.id, page_size: 100 }, version);

  return (
    <Card aria-label="یافته‌های ممیزی">
      <CardHeader
        title="یافته‌ها"
        description={findingsSummary(audit)}
        icon={<SearchCheck />}
        actions={
          audit.can_raise_finding && (
            <Button size="sm" variant="primary" icon={<Plus />} onClick={() => setAdding(true)}>
              ثبت یافته
            </Button>
          )
        }
      />

      {audit.status === "PLANNED" && <Alert tone="info">پس از آغاز ممیزی، ممیز اصلی می‌تواند یافته‌ها را ثبت کند.</Alert>}

      {findings.loading && findings.rows.length === 0 ? (
        <SkeletonLines rows={2} />
      ) : findings.error ? (
        <ErrorBanner message={findings.error} />
      ) : findings.rows.length === 0 ? (
        audit.status !== "PLANNED" && (
          <EmptyState
            compact
            icon={<SearchCheck />}
            message={audit.status === "COMPLETED" ? "این ممیزی بدون یافته انجام شد." : "هنوز یافته‌ای ثبت نشده است."}
          />
        )
      ) : (
        <ul className="-mx-5 divide-y divide-slate-100 border-t border-slate-100 sm:-mx-6">
          {findings.rows.map((nc) => (
            <NcListItem key={nc.id} nc={nc} />
          ))}
        </ul>
      )}

      {adding && (
        <FindingFormDialog
          audit={audit}
          onSaved={(saved) => {
            setAdding(false);
            onChanged();
            router.push(`/quality/${saved.id}`);
          }}
          onClose={() => setAdding(false)}
        />
      )}
    </Card>
  );
}
