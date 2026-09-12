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

// Admission for the local projection, not an alternate wire-schema authority.
const invalid = (): never => { throw new TypeError("Invalid metric projection"); };
const identifier = (value: unknown): value is string =>
  typeof value === "string" && value.length > 0 && value.length <= 160 &&
  !/[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069\ud800-\udfff]/u.test(value);
const timestamp = (value: unknown): value is number =>
  typeof value === "number" && Number.isSafeInteger(value) && Math.abs(value) <= 1e15;

function windowSnapshot(input: MetricWindow, cohort: true): MetricWindow;
function windowSnapshot(input: Omit<MetricWindow, "minEntities">, cohort: false): Omit<MetricWindow, "minEntities">;
function windowSnapshot(input: Omit<MetricWindow, "minEntities">, cohort: boolean): Omit<MetricWindow, "minEntities"> | MetricWindow {
  try {
    if (!input || typeof input !== "object" || Array.isArray(input)) invalid();
    const { start, end, bucketMs } = input;
    if (![start, end, bucketMs].every(timestamp) || start >= end || bucketMs <= 0 ||
        Math.ceil((end - start) / bucketMs) > 1000) invalid();
    if (!cohort) return Object.freeze({ start, end, bucketMs });
    const { minEntities } = input as MetricWindow;
    if (!timestamp(minEntities) || minEntities < 1 || minEntities > 10000) invalid();
    return Object.freeze({ start, end, bucketMs, minEntities });
  } catch {
    return invalid();
  }
}

export function createZedMetricViews<Series>(viz: ClaritasTrendPort<Series>) {
  if (!viz || ![viz.cohortTrends, viz.individualTrend, viz.trendSvg].every(fn => typeof fn === "function"))
    throw new TypeError("Claritas trend SDK is required");
  const { cohortTrends, individualTrend, trendSvg } = viz;
  function project(rows: readonly ZedMetricSample[], metric: ZedMetric): Projection[] {
    try {
      if (!Array.isArray(rows) || rows.length > 50000 || typeof metric !== "string" ||
          !Object.hasOwn(metrics, metric)) invalid();
      const definition = metrics[metric];
      const projected: Projection[] = [];
      // for-of observes sparse holes; Array.map would silently forward them.
      for (const row of rows) {
        if (!row || typeof row !== "object" || Array.isArray(row)) invalid();
        const { packageVersionId: entityId, ecosystem: cohortId, at, value,
          metric: rowMetric, unit } = row;
        if (!identifier(entityId) || !identifier(cohortId) || !timestamp(at) ||
            rowMetric !== metric || unit !== definition.unit ||
            !(value === null || (typeof value === "number" && Number.isFinite(value) &&
              value >= definition.min && value <= definition.max))) invalid();
        // Whitelist and snapshot chart inputs; never forward source metadata.
        projected.push({ entityId, cohortId, at, value });
      }
      return projected;
    } catch {
      return invalid();
    }
  }
  return Object.freeze({
    cohorts(rows: readonly ZedMetricSample[], metric: ZedMetric, window: MetricWindow) {
      return cohortTrends(project(rows, metric), windowSnapshot(window, true)).map(series => ({
        series, svg: trendSvg(series, `${metric} (${metrics[metric].unit}), equal-entity mean`),
      }));
    },
    individual(rows: readonly ZedMetricSample[], metric: ZedMetric, id: string,
      window: Omit<MetricWindow, "minEntities">) {
      if (!identifier(id)) invalid();
      const series = individualTrend(project(rows, metric), id, windowSnapshot(window, false));
      return { series, svg: trendSvg(series, `${metric} (${metrics[metric].unit}), entity mean`) };
    },
  });
}
