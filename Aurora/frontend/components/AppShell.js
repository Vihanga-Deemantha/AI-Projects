"use client";

import { useState } from "react";
import AppSidebar from "@/components/AppSidebar";
import { DESKTOP_QUERY, useMediaQuery } from "@/hooks/media";

/**
 * The frame around every signed-in screen (Practice, History, Progress, Profile): the sidebar plus
 * whichever page is open. It lives in app/(app)/layout.js, so it stays mounted while the learner
 * moves between those screens instead of being rebuilt, and asking the server who they are again,
 * on every click.
 *
 * Below the `lg` breakpoint the sidebar is a drawer. While it is open the page behind it is made
 * inert, so neither Tab nor a screen reader can wander into content the drawer is covering.
 */
export default function AppShell({ children }) {
  const isDesktop = useMediaQuery(DESKTOP_QUERY);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Growing the window into the desktop layout puts the sidebar permanently on screen, so a drawer
  // left "open" must not come back the next time the window shrinks. (Derived during render, the
  // pattern React recommends for state that follows a change, rather than in an effect.)
  const [wasDesktop, setWasDesktop] = useState(isDesktop);
  if (isDesktop !== wasDesktop) {
    setWasDesktop(isDesktop);
    if (isDesktop) setDrawerOpen(false);
  }

  return (
    <div className="flex min-h-screen flex-1 flex-col lg:flex-row">
      <AppSidebar open={drawerOpen} onOpenChange={setDrawerOpen} isDesktop={isDesktop} />
      {/* `contents` takes this wrapper out of the layout, so each page's own <main> is still a direct flex item of the row above. */}
      <div className="contents" inert={drawerOpen && !isDesktop}>
        {children}
      </div>
    </div>
  );
}
