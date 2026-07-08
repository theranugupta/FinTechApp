"use client";

import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  Receipt,
  ShieldCheck,
  Banknote,
  Activity,
  History,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useTranslation } from "@/lib/i18n";

// Each item maps to a section id rendered on the page.
export const NAV_ITEMS: { id: string; labelKey: string; icon: LucideIcon }[] = [
  { id: "overview", labelKey: "nav.overview", icon: LayoutDashboard },
  { id: "details", labelKey: "nav.details", icon: Receipt },
  { id: "eligibility", labelKey: "nav.eligibility", icon: ShieldCheck },
  { id: "initiate", labelKey: "nav.initiate", icon: Banknote },
  { id: "status", labelKey: "nav.status", icon: Activity },
  { id: "history", labelKey: "nav.history", icon: History },
];

export function Sidebar() {
  const { t } = useTranslation();
  const [active, setActive] = useState<string>("overview");

  // Scroll-spy: highlight the section currently in view.
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-45% 0px -45% 0px", threshold: [0, 0.25, 0.5, 1] }
    );
    NAV_ITEMS.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, []);

  function go(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    setActive(id);
  }

  return (
    <aside className="md:sticky md:top-[73px] md:h-[calc(100vh-73px)] md:w-60 md:shrink-0 md:border-r md:border-border/60">
      <nav
        className={cn(
          "flex gap-1 overflow-x-auto p-3",
          "md:flex-col md:overflow-visible md:p-4"
        )}
      >
        <p className="hidden px-2 pb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground md:block">
          {t("nav.section")}
        </p>
        {NAV_ITEMS.map(({ id, labelKey, icon: Icon }) => {
          const isActive = active === id;
          return (
            <button
              key={id}
              onClick={() => go(id)}
              className={cn(
                "flex shrink-0 items-center gap-2.5 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-brand-gradient text-white shadow-sm shadow-black/5"
                  : "text-muted-foreground hover:bg-accent hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {t(labelKey)}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
