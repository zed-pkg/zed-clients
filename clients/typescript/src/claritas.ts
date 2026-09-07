/** Local projection adapter, not a wire contract, telemetry collector or auth boundary.
 * Supply the explicitly composed Claritas library/SDK; algorithms stay upstream.
 */
export type ZedMetric = "install_duration_ms" | "cache_hit_ratio" | "download_bytes";
export interface ZedMetricSample {
  readonly packageVersionId: string;
  readonly ecosystem: string;
  readonly metric: ZedMetric;
  readonly unit: string;
  readonly at: number;
  readonly value: number | null;
}
export interface MetricWindow {
  readonly start: number;
  readonly end: number;
  readonly bucketMs: number;
  readonly minEntities: number;
}
type Projection = { entityId: string; cohortId: string; at: number; value: number | null };
/** Structural port for in-process calls; no duplicated Claritas wire declarations. */
export interface ClaritasTrendPort<Series> {
  cohortTrends(rows: readonly Projection[], window: MetricWindow): Series[];
  individualTrend(rows: readonly Projection[], id: string, window: Omit<MetricWindow, "minEntities">): Series;
  trendSvg(series: Series, title: string): string;
}
const metrics = {
  "install_duration_ms": {
    "unit": "ms",
    "min": 0,
    "max": 1000000000000000.0
  },
  "cache_hit_ratio": {
    "unit": "ratio",
    "min": 0,
    "max": 1
  },
  "download_bytes": {
    "unit": "bytes",
    "min": 0,
    "max": 1000000000000000.0
  }
} as const;

export function createZedMetricViews<Series>(viz: ClaritasTrendPort<Series>) {
  if (!viz || ![viz.cohortTrends, viz.individualTrend, viz.trendSvg].every(fn => typeof fn === "function"))
    throw new TypeError("Claritas trend SDK is required");
  const { cohortTrends, individualTrend, trendSvg } = viz;
  function project(rows: readonly ZedMetricSample[], metric: ZedMetric): Projection[] {
    if (!Array.isArray(rows) || rows.length > 50000 || !Object.hasOwn(metrics, metric))
      throw new TypeError("Invalid metric projection");
    const definition = metrics[metric];
    return rows.map(row => {
      if (!row || row.metric !== metric || row.unit !== definition.unit ||
          !(row.value === null || (typeof row.value === "number" && Number.isFinite(row.value) &&
            row.value >= definition.min && row.value <= definition.max)))
        throw new TypeError("Invalid metric projection");
      // Whitelist only chart inputs; never forward arbitrary source metadata.
      return { entityId: row.packageVersionId, cohortId: row.ecosystem, at: row.at, value: row.value };
    });
  }
  return Object.freeze({
    cohorts(rows: readonly ZedMetricSample[], metric: ZedMetric, window: MetricWindow) {
      return cohortTrends(project(rows, metric), window).map(series => ({
        series, svg: trendSvg(series, `${metric} (${metrics[metric].unit}), equal-entity mean`),
      }));
    },
    individual(rows: readonly ZedMetricSample[], metric: ZedMetric, id: string,
      window: Omit<MetricWindow, "minEntities">) {
      const series = individualTrend(project(rows, metric), id, window);
      return { series, svg: trendSvg(series, `${metric} (${metrics[metric].unit}), entity mean`) };
    },
  });
}
