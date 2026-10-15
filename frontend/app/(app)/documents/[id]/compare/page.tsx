import { Suspense } from "react";
import { LoadingBanner } from "@/components/StatusBanner";
import { CompareScreen } from "@/components/compare/CompareScreen";

// The screen reads `?with=` (useSearchParams), which needs a Suspense boundary in a prerendered page.
export default function CompareRevisionsPage() {
  return (
    <Suspense fallback={<LoadingBanner />}>
      <CompareScreen />
    </Suspense>
  );
}
