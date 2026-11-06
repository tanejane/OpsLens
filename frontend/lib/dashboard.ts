export type DashboardPeriod = string[];

export function dashboardPeriodLabel(period?: DashboardPeriod): string {
  return period?.length
    ? new Intl.DateTimeFormat("en", { month: "long", year: "numeric", timeZone: "UTC" }).format(new Date(`${period[0]}T00:00:00Z`))
    : "Period";
}

export function dashboardInvestigationQuestion(metricId: string, previous: DashboardPeriod, current: DashboardPeriod): string {
  const metric = metricId === "contribution_margin_pct" ? "contribution margin" : metricId.replaceAll("_", " ");
  return `Compare ${metric} from ${dashboardPeriodLabel(previous)} to ${dashboardPeriodLabel(current)}`;
}
