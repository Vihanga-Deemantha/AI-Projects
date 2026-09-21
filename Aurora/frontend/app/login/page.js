import { Suspense } from "react";
import AuthForm from "@/components/AuthForm";
import AuthShell from "@/components/AuthShell";
import GuestGuard from "@/components/GuestGuard";

export const metadata = { title: "Sign in — AURA" };

export default function LoginPage() {
  return (
    <AuthShell>
      <GuestGuard>
        {/* AuthForm reads useSearchParams() (for ?error=... from a failed
            Google OAuth redirect), which requires a Suspense boundary on a
            statically-prerendered page. */}
        <Suspense fallback={null}>
          <AuthForm mode="login" />
        </Suspense>
      </GuestGuard>
    </AuthShell>
  );
}
