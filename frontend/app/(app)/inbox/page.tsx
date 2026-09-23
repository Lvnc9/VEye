import { Suspense } from "react";
import { InboxScreen } from "@/components/inbox/InboxScreen";
import { LoadingBanner } from "@/components/StatusBanner";

// The screen reads `?c=` (useSearchParams), which needs a Suspense boundary in a prerendered page.
export default function InboxPage() {
  return (
    <Suspense fallback={<LoadingBanner />}>
      <InboxScreen />
    </Suspense>
  );
}
