"use client";

import { LogOut, Settings, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useTranslation } from "@/lib/i18n";

export function ProfileMenu() {
  const { t } = useTranslation();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          size="icon"
          className="rounded-full border-transparent bg-brand-gradient p-0 text-white shadow-md shadow-black/5 hover:brightness-110"
          aria-label={t("profile.label")}
        >
          <UserRound className="h-4 w-4" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-[14rem]">
        <div className="flex items-center gap-3 px-2 py-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-gradient text-white">
            <UserRound className="h-4 w-4" />
          </span>
          <div className="leading-tight">
            <p className="text-sm font-semibold">{t("profile.label")}</p>
            <p className="text-xs text-muted-foreground">{t("profile.role")}</p>
          </div>
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem>
          <Settings className="h-4 w-4" />
          {t("profile.settings")}
        </DropdownMenuItem>
        <DropdownMenuItem className="text-destructive focus:text-destructive">
          <LogOut className="h-4 w-4" />
          {t("profile.signout")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
