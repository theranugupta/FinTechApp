"use client";

import { ShieldCheck } from "lucide-react";
import { useTranslation } from "@/lib/i18n";

export function Footer() {
  const { t } = useTranslation();
  const year = 2026; // static: Date is intentionally not read at render for SSR stability

  return (
    <footer className="mt-auto border-t border-border/60 bg-background/70 backdrop-blur-md">
      <div className="h-1 w-full bg-brand-gradient opacity-70" />
      <div className="mx-auto flex max-w-4xl flex-col items-center justify-between gap-2 px-4 py-5 text-sm text-muted-foreground sm:flex-row sm:px-6">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-brand-gradient text-xs font-black text-white">
            F
          </span>
          <span>© {year} {t("footer.rights")}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <ShieldCheck className="h-4 w-4 text-muted-foreground" />
          <span>{t("footer.secure")}</span>
        </div>
      </div>
    </footer>
  );
}
