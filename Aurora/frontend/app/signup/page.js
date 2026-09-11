import AuthForm from "@/components/AuthForm";
import AuthBrandPanel from "@/components/AuthBrandPanel";

export const metadata = { title: "Sign Up — AURA" };

export default function SignupPage() {
  return (
    <div className="flex min-h-screen flex-1">
      <AuthBrandPanel
        quote="The first app that corrected me without making me feel stupid."
        subtext="Every session, spoken and reviewed — kept in your speech history."
        floatingCards={[
          { lines: ["PAST TENSE FIXED"] },
          { lines: ["Style: Irish English", "Voice: Alan"] },
        ]}
      />
      <div className="flex flex-1 items-center justify-center px-6 py-12">
        <AuthForm mode="signup" />
      </div>
    </div>
  );
}
