import { Suspense } from "react";
import { LoginScreen } from "./LoginScreen";

// The screen reads `?next=` (useSearchParams), which needs a Suspense boundary in a prerendered page.
export default function LoginPage() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-surface" />}>
      <LoginScreen />
    </Suspense>
  );
}
