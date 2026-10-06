import AppShell from "@/components/AppShell";
import AuthGuard from "@/components/AuthGuard";

/**
 * Everything a signed-in learner sees (Practice, Progress, History, Profile) shares this frame: the
 * login check and the sidebar are set up once and stay in place while the pages change inside them,
 * rather than every page rebuilding them, and asking the server who the user is, on each click.
 */
export default function AppLayout({ children }) {
  return (
    <AuthGuard>
      <AppShell>{children}</AppShell>
    </AuthGuard>
  );
}
