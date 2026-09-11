import AuthForm from "@/components/AuthForm";
import AuthBrandPanel from "@/components/AuthBrandPanel";

export const metadata = { title: "Log In — AURA" };

export default function LoginPage() {
  return (
    <div className="flex min-h-screen flex-1">
      <AuthBrandPanel
        quote="Pick up right where your last conversation ended."
        subtext="Your voice, style and scenario preferences are all saved."
        floatingCards={[
          null,
          { lines: ["7-day streak", "Welcome back"] },
        ]}
      />
      <div className="flex flex-1 items-center justify-center px-6 py-12">
        <AuthForm mode="login" />
      </div>
    </div>
  );
}
