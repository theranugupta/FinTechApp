"use client";

import { useEffect, useMemo, useState } from "react";
import { useTheme } from "next-themes";
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  type ChartData,
  type ChartOptions,
} from "chart.js";
import { Doughnut } from "react-chartjs-2";
import { getRefundStatusStats, RefundStatusStats } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";

ChartJS.register(ArcElement, Tooltip, Legend);

// Fixed colors per status (status values are system enums, not translated).
// Swagger UI method-badge colors: POST green, GET blue, DELETE red.
const STATUS_COLORS: Record<string, string> = {
  SUCCESS: "rgb(73,204,144)", // swagger green #49cc90
  PENDING: "rgb(97,175,254)", // swagger blue  #61affe
  FAILED: "rgb(249,62,62)", // swagger red   #f93e3e
};

// `refreshKey` lets the parent force a refetch after a new refund is created.
export function RefundStatusChart({
  token,
  refreshKey,
}: {
  token: string;
  refreshKey?: number;
}) {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const [stats, setStats] = useState<RefundStatusStats | null>(null);

  useEffect(() => {
    let alive = true;
    getRefundStatusStats(token)
      .then((s) => alive && setStats(s))
      .catch(() => alive && setStats({ statuses: {} }));
    return () => {
      alive = false;
    };
  }, [token, refreshKey]);

  const isDark = resolvedTheme === "dark";
  const tickColor = isDark ? "rgba(226,232,240,0.82)" : "rgba(59,65,81,0.75)";

  const entries = Object.entries(stats?.statuses ?? {});
  const total = entries.reduce((sum, [, n]) => sum + n, 0);

  const data: ChartData<"doughnut"> = useMemo(() => {
    const labels = entries.map(([s]) => s);
    return {
      labels,
      datasets: [
        {
          data: entries.map(([, n]) => n),
          backgroundColor: labels.map((s) => STATUS_COLORS[s] ?? "rgb(148,163,184)"),
          borderColor: isDark ? "rgba(20,16,34,1)" : "rgba(255,255,255,1)",
          borderWidth: 2,
        },
      ],
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stats, isDark]);

  const options: ChartOptions<"doughnut"> = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      cutout: "62%",
      plugins: {
        legend: { position: "bottom", labels: { color: tickColor, usePointStyle: true, boxWidth: 8 } },
      },
    }),
    [tickColor]
  );

  if (!stats) {
    return <p className="text-sm text-muted-foreground">{t("common.loading")}</p>;
  }
  if (total === 0) {
    return <p className="text-sm text-muted-foreground">{t("statusChart.empty")}</p>;
  }

  return (
    <div className="relative h-56 w-full">
      <Doughnut data={data} options={options} />
      {/* Center total */}
      <div className="pointer-events-none absolute inset-x-0 top-[42%] -translate-y-1/2 text-center">
        <p className="text-2xl font-bold text-brand-gradient">{total}</p>
        <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
          {t("status.count")}
        </p>
      </div>
    </div>
  );
}
