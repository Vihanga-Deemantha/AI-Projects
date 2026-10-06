import AuthGuard from "@/components/AuthGuard";
import AuthShell from "@/components/AuthShell";
import VerifyEmailFlow from "@/components/VerifyEmailFlow";

export const metadata = { title: "Verify your email" };

export default function VerifyEmailPage() {
  return (
    <AuthGuard>
      <AuthShell>
        <VerifyEmailFlow />
      </AuthShell>
    </AuthGuard>
  );
}
