"use client";

import { useTranslation } from "@/lib/i18n";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { ThemeSwitcher } from "@/components/ThemeSwitcher";
import { ProfileMenu } from "@/components/ProfileMenu";

// Brand logo: a gradient "F" mark + wordmark.
function Logo() {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-3">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-gradient text-lg font-black text-white shadow-md shadow-black/5">
        F
      </span>
      <div className="leading-tight">
        <p className="text-lg font-extrabold tracking-tight">
          Fin<span className="text-brand-gradient">Pay</span>
        </p>
        <p className="hidden text-[11px] text-muted-foreground sm:block">
          {t("app.tagline")}
        </p>
      </div>
    </div>
  );
}

export function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/70 backdrop-blur-md">
      {/* Thin gradient accent line at the very top. */}
      <div className="h-1 w-full bg-brand-gradient" />
      <div className="mx-auto flex max-w-4xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Logo />
        <div className="flex items-center gap-2">
          <LanguageSwitcher />
          <ThemeSwitcher />
          <ProfileMenu />
        </div>
      </div>
    </header>
  );
}
