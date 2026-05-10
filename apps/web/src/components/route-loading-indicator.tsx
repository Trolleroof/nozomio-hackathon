"use client";

import { LoaderCircle } from "lucide-react";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const CLEAR_DELAY_MS = 280;
const FAILSAFE_DELAY_MS = 5000;

export function RouteLoadingIndicator() {
  const pathname = usePathname();
  const [pendingHref, setPendingHref] = useState<string | null>(null);
  const clearTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const failsafeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function clearTimer(timerRef: typeof clearTimerRef) {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    }

    function startPending(href: string) {
      clearTimer(clearTimerRef);
      clearTimer(failsafeTimerRef);
      setPendingHref(href);
      failsafeTimerRef.current = setTimeout(() => {
        setPendingHref(null);
        failsafeTimerRef.current = null;
      }, FAILSAFE_DELAY_MS);
    }

    function handleClick(event: MouseEvent) {
      if (
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }

      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }

      const link = target.closest<HTMLAnchorElement>("a[href]");
      if (!link || (link.target && link.target !== "_self") || link.hasAttribute("download")) {
        return;
      }

      const url = new URL(link.href, window.location.href);
      if (url.origin !== window.location.origin || url.pathname === pathname) {
        return;
      }

      startPending(`${url.pathname}${url.search}${url.hash}`);
    }

    function handlePopState() {
      startPending(window.location.pathname);
    }

    document.addEventListener("click", handleClick, true);
    window.addEventListener("popstate", handlePopState);

    return () => {
      document.removeEventListener("click", handleClick, true);
      window.removeEventListener("popstate", handlePopState);
      clearTimer(clearTimerRef);
      clearTimer(failsafeTimerRef);
    };
  }, [pathname]);

  useEffect(() => {
    if (!pendingHref) {
      return;
    }

    if (pendingHref.startsWith(pathname ?? "")) {
      clearTimerRef.current = setTimeout(() => {
        setPendingHref(null);
        clearTimerRef.current = null;
      }, CLEAR_DELAY_MS);
    }
  }, [pathname, pendingHref]);

  if (!pendingHref) {
    return null;
  }

  return (
    <div
      aria-label="Loading page"
      aria-live="polite"
      className="fixed left-1/2 top-3 z-50 flex -translate-x-1/2 items-center gap-2 rounded-md border border-border bg-surface-raised px-3 py-2 text-sm font-medium text-foreground shadow-lg shadow-black/25"
      role="status"
    >
      <LoaderCircle aria-hidden="true" className="h-4 w-4 animate-spin text-accent" />
      <span>Loading page</span>
      <span className="absolute inset-x-0 -bottom-px h-px overflow-hidden rounded-b-md bg-border">
        <span className="crucible-skeleton-line block h-full w-full bg-accent/50" />
      </span>
    </div>
  );
}
