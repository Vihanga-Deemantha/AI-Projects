import { Suspense } from "react";
import AuthForm from "@/components/AuthForm";
import AuthShell from "@/components/AuthShell";
import GuestGuard from "@/components/GuestGuard";

export const metadata = { title: "Sign up — AURA" };

export default function SignupPage() {
  return (
    <AuthShell>
      <GuestGuard>
        {/* See app/login/page.js — AuthForm's useSearchParams() call needs a
            Suspense boundary on a statically-prerendered page. */}
        <Suspense fallback={null}>
          <AuthForm mode="signup" />
        </Suspense>
      </GuestGuard>
    </AuthShell>
  );
}
