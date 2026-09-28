import { Alert } from "@/components/ui/Alert";
import { EmptyState } from "@/components/ui/EmptyState";
import { SkeletonLines } from "@/components/ui/Skeleton";
import { Spinner } from "@/components/ui/Spinner";

/** Loading: a card with a spinner and a few placeholder lines. It fades in after a beat, so a load that
 *  finishes at once never flashes it. */
export function LoadingBanner({ label = "در حال بارگذاری..." }: { label?: string }) {
  return (
    <div
      role="status"
      className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card animate-fade-in"
      style={{ animationDelay: "150ms" }}
    >
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Spinner className="text-brand-600" />
        {label}
      </div>
      <SkeletonLines rows={3} className="mt-4" />
    </div>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <Alert tone="danger" role="alert">
      {message}
    </Alert>
  );
}

export function EmptyBanner({ message }: { message: string }) {
  return <EmptyState message={message} compact />;
}
