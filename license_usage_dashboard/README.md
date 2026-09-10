# License Usage Dashboard

A self-contained Splunk app that gives a client visibility into their **real**
license consumption: an annual overview against their license pool quota,
daily and monthly trends, and a breakdown of which indexes, sourcetypes,
hosts and sources consume the most license. Unlike `itsi_lite` in this
repo, this app is not a synthetic demo - every panel queries Splunk's own
internal license accounting events (`index=_internal
source=*license_usage.log* type=Usage`), so it shows the client's actual
numbers as soon as it's installed.

## Requirements

- Runs on the Splunk instance that tracks licensing for the deployment
  (typically the license master, or a standalone instance). The dashboards
  read `index=_internal` and call `| rest /services/licenser/pools`, so the
  user viewing them needs the built-in `admin` or `power` role (or
  equivalent capabilities: search `_internal` + `list_settings`/REST
  access to `licenser/pools`).
- No add-on, index, or data onboarding is required - `_internal` and the
  licenser REST endpoint exist on every Splunk instance out of the box.

## Dashboards

1. **License Overview** (default landing page) - total consumption over the
   last 365 days, the daily average, today's usage as a percentage of the
   license pool quota (color-coded, live/in-progress figure), a 13-month
   consumption trend, the top 10 indexes over the last 30 days, a breakdown
   of consumption by license pool over the last 30 days, and a table
   comparing each pool's usage against its own quota for the most recent
   *closed* license day (sourced from Splunk's own `RolloverSummary`
   accounting, not a live estimate - see below).
2. **Daily & Monthly Trend** - a time-range picker driving a daily
   consumption chart (with a 7-day moving average overlay), a fixed
   12-month monthly chart, and a day-by-day, by-license-pool table (from
   `RolloverSummary`) flagging any day that came close to or went over the
   quota that was actually in effect that day.
3. **Top Sources** - pick a time range and a dimension (index, sourcetype,
   host, source, or license pool) to see the top 15 contributors as a bar
   chart, a pie chart of the top 10, and a Pareto table (share of total +
   cumulative share) to quickly spot the few sources driving most of the
   volume.
4. **Consumption Estimates** - projects daily, monthly (x30) and annual
   (x365) consumption from a selectable baseline window (30/90/180/365
   days), since `_internal` often doesn't hold a true year of history.
   For each of the three periods it shows the same three numbers side by
   side: a *simple* estimate (daily average), a *trend-adjusted* estimate
   (30-day forecast via Splunk's built-in `predict` command - the one to
   use for renewal sizing since it reacts to growth), and a *conservative*
   estimate (95th-percentile day, a buffer figure). Also shows how many
   days of history actually backed the estimate, so you know how much to
   trust it, plus a forecast chart with a 95% confidence band. A table per
   period (Daily/Monthly/Annual "by License Pool") breaks the same three
   methods down per pool - Simple and Conservative are computed directly
   per pool, while Trend-Adjusted allocates the single global forecast
   across pools by their historical share of consumption, since `predict`
   can't run separately per pool value in one static search.

## How the numbers are computed

This app pulls from two different event types inside `license_usage.log`,
depending on whether a panel needs a live, in-progress figure or an
authoritative, closed-book one:

- `macros.conf` -> `license_usage_base`: `index=_internal
  source=*license_usage.log* type=Usage` - raw, continuously-emitted
  per-index/sourcetype/host/source events. Used for consumption trends,
  the "Top Sources" breakdowns, and the estimate/forecast dashboard, since
  it's the only source with that level of granularity and it updates
  throughout the day.
- `license_usage_gb`: converts the raw `b` (bytes) field to `GB` and
  normalizes missing `idx`/`h`/`s`/`st`/`pool` values to `(UNKNOWN)`.
- `license_pool_quota_gb`: `| rest /services/licenser/pools` converted to
  GB - a live snapshot of each pool's *current* quota and used bytes.
  Used only for the "Today vs. License Pool Quota" single value on the
  Overview, since today's license day hasn't closed yet and this REST
  endpoint is the only source with a real-time counter.
- `license_rollover_base` / `license_rollover_gb`: `index=_internal
  source=*license_usage.log* type="RolloverSummary"` - the summary event
  Splunk itself writes once per pool each time a license day *closes*,
  carrying both the day's final counted usage (`b`) and the pool quota in
  effect that day (`poolsz`). This is the same record Splunk's own license
  enforcement uses to decide whether a day was in violation, so it's more
  authoritative than re-summing `Usage` events, and - unlike a REST
  snapshot of the *current* quota - it's correct even for days before the
  quota was last changed. `license_rollover_gb` shifts `_time` back 12
  hours before binning to `1d` (the license day rollover boundary doesn't
  align with local midnight), dedupes repeated rollover updates for the
  same day via `latest()`, and aggregates bytes across license peers per
  pool (summed, since usage is additive) while quota size is taken via
  `max()` (a pool-level constant, not additive). Used for every "vs.
  quota" table that looks at past (closed) days: the pool quota table on
  Overview and the daily detail table on Daily & Monthly Trend.

These are the same fields and endpoints Splunk's own Monitoring Console
license usage views are built on, so the numbers here will match what the
client sees under **Settings > Licensing** / the Monitoring Console.

## Install

1. Copy (or symlink) the `license_usage_dashboard/` folder into
   `$SPLUNK_HOME/etc/apps/`.
2. Restart Splunk, or use **Apps > Manage Apps > Install app from file**
   after zipping this folder (`cd license_usage_dashboard && zip -r
   ../license_usage_dashboard.tar.gz .`, then rename/package per your
   Splunk version's requirements).
3. Install it on the license master (or the standalone instance) so
   `index=_internal` and `licenser/pools` reflect the real deployment.
4. Open the app - the four dashboards are in the app's navigation bar.

## Extending this into your own app

- **Longer retention than `_internal` allows**: many deployments only keep
  `_internal` for 30-90 days, which isn't enough for a true annual view.
  Enable the disabled `[License Usage - Daily Rollup to Summary Index]`
  saved search in `default/savedsearches.conf` - it rolls up each day's
  usage by index/sourcetype/host/source via `collect` into a `summary`
  index. Once enough history has accumulated, point the
  `license_usage_base` macro at that summary index instead of
  `_internal` so the year-long views stay accurate indefinitely.
- **Multiple license pools / a license peer deployment**: the "Today vs.
  License Pool Quota" single value on the overview sums across all pools
  for a quick headline number, but the "Consumption by License Pool" chart,
  the `RolloverSummary`-based "vs. Quota" tables on Overview and Daily &
  Monthly Trend, the "License Pool" breakdown on Top Sources, and the "by
  License Pool" tables on Consumption Estimates already report per pool
  (via the `pool` field), so per-pool tracking (e.g. separate pools for
  prod vs. dev) works out of the box. On a license peer deployment,
  `RolloverSummary` events are per-peer, and `license_rollover_gb` sums
  bytes across peers but takes the max of `poolsz` (a pool-level constant)
  so the quota isn't double-counted.
- **Alerting**: pair the daily rollup saved search with an alert action
  (e.g. `| where PctOfQuota>=90`) to notify the client proactively before
  they breach quota, instead of only showing it on a dashboard.
- **Tuning the forecast**: `annual_estimate.xml`'s trend-adjusted estimate
  uses `predict ... algorithm=LLT future_timespan=30`. If the client's
  usage has a strong weekly or monthly seasonal pattern, swap in `LLP`
  (periodic) with a `period` parameter, or extend `future_timespan` for a
  longer-horizon forecast at the cost of a wider confidence band.

## Files

```
license_usage_dashboard/
  default/
    app.conf
    macros.conf                 # base search, GB conversion, pool quota (live REST + RolloverSummary)
    savedsearches.conf          # summary-index rollup (disabled)
    data/ui/nav/default.xml
    data/ui/views/
      license_overview.xml
      daily_monthly_trend.xml
      top_sources.xml
      annual_estimate.xml
  metadata/
    default.meta
```
