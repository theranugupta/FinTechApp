"use client";

import { useEffect, useMemo, useState } from "react";
import { useTheme } from "next-themes";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  type ChartData,
  type ChartOptions,
} from "chart.js";
import { Chart } from "react-chartjs-2";
import { ChevronsUpDown } from "lucide-react";
import { getDailyStats, DailyStats } from "@/lib/api";
import { useTranslation } from "@/lib/i18n";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuCheckboxItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const RANGES = [7, 14, 30];

// Register only the Chart.js pieces we use (keeps the bundle lean).
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Tooltip,
  Legend
);

export function DailyTransactionsChart({ token }: { token: string }) {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const [stats, setStats] = useState<DailyStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(14); // date-range window

  useEffect(() => {
    let alive = true;
    setStats(null);
    getDailyStats(token, days)
      .then((s) => alive && setStats(s))
      .catch(() => alive && setError("Could not load stats"));
    return () => {
      alive = false;
    };
  }, [token, days]);

  const isDark = resolvedTheme === "dark";
  const gridColor = isDark ? "rgba(255,255,255,0.08)" : "rgba(0,0,0,0.06)";
  const tickColor = isDark ? "rgba(226,232,240,0.80)" : "rgba(59,65,81,0.75)";

  const data: ChartData<"bar" | "line"> = useMemo(() => {
    const series = stats?.series ?? [];
    // Short label like "07 Jul"
    const labels = series.map((p) => {
      const d = new Date(p.date + "T00:00:00");
      return d.toLocaleDateString(undefined, { day: "2-digit", month: "short" });
    });
    return {
      labels,
      datasets: [
        {
          type: "bar" as const,
          label: t("chart.count"),
          data: series.map((p) => p.count),
          backgroundColor: isDark ? "rgba(97,175,254,0.75)" : "rgba(97,175,254,0.80)",
          borderRadius: 6,
          yAxisID: "y",
          order: 2,
        },
        {
          type: "line" as const,
          label: t("chart.amount"),
          data: series.map((p) => p.total_amount),
          borderColor: isDark ? "rgb(105,220,169)" : "rgb(73,204,144)",
          backgroundColor: isDark ? "rgb(105,220,169)" : "rgb(73,204,144)",
          tension: 0.35,
          pointRadius: 3,
          yAxisID: "y1",
          order: 1,
        },
      ],
    };
  }, [stats, isDark, t]);

  const options: ChartOptions<"bar" | "line"> = useMemo(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: tickColor, usePointStyle: true, boxWidth: 8 } },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const v = ctx.parsed.y ?? 0;
              return ctx.dataset.yAxisID === "y1"
                ? `${t("chart.amount")}: ₹${v.toLocaleString()}`
                : `${t("chart.count")}: ${v}`;
            },
          },
        },
      },
      scales: {
        x: { grid: { color: gridColor }, ticks: { color: tickColor } },
        y: {
          type: "linear",
          position: "left",
          beginAtZero: true,
          grid: { color: gridColor },
          ticks: { color: tickColor, precision: 0 },
          title: { display: true, text: t("chart.count"), color: tickColor },
        },
        y1: {
          type: "linear",
          position: "right",
          beginAtZero: true,
          grid: { drawOnChartArea: false },
          ticks: { color: tickColor },
          title: { display: true, text: t("chart.amount"), color: tickColor },
        },
      },
    }),
    [gridColor, tickColor, t]
  );

  if (error) {
    return <p className="text-sm text-muted-foreground">{error}</p>;
  }

  return (
    <div className="w-full">
      {/* Date-range selector */}
      <div className="mb-3 flex justify-end">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="outline"
              size="sm"
              className="gap-2 rounded-lg border-border/60 bg-background/50"
            >
              {t("chart.days", { n: days })}
              <ChevronsUpDown className="h-3.5 w-3.5 opacity-60" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {RANGES.map((r) => (
              <DropdownMenuCheckboxItem
                key={r}
                checked={days === r}
                onCheckedChange={() => setDays(r)}
              >
                {t("chart.days", { n: r })}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div className="h-72 w-full">
        {stats ? (
          <Chart type="bar" data={data} options={options} />
        ) : (
          <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
        )}
      </div>
    </div>
  );
}
