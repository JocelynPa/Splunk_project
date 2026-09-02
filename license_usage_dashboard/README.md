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
   license pool quota (color-coded), a 13-month consumption trend, and the
   top 10 indexes over the last 30 days.
2. **Daily & Monthly Trend** - a time-range picker driving a daily
   consumption chart (with a 7-day moving average overlay), a fixed
   12-month monthly chart, and a day-by-day table flagging any day that
   came close to or went over quota.
3. **Top Sources** - pick a time range and a dimension (index, sourcetype,
   host, or source) to see the top 15 contributors as a bar chart, a pie
   chart of the top 10, and a Pareto table (share of total + cumulative
   share) to quickly spot the few sources driving most of the volume.

## How the numbers are computed

- `macros.conf` -> `license_usage_base`: the shared base search,
  `index=_internal source=*license_usage.log* type=Usage`.
- `license_usage_gb`: converts the raw `b` (bytes) field to `GB` and
  normalizes missing `idx`/`h`/`s`/`st` values to `(UNKNOWN)`.
- `license_pool_quota_gb`: `| rest /services/licenser/pools` converted to
  GB, used to compute "today vs. quota" and the daily quota table.

These are the same fields and endpoint Splunk's own Monitoring Console
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
4. Open the app - the three dashboards are in the app's navigation bar.

## Extending this into your own app

- **Longer retention than `_internal` allows**: many deployments only keep
  `_internal` for 30-90 days, which isn't enough for a true annual view.
  Enable the disabled `[License Usage - Daily Rollup to Summary Index]`
  saved search in `default/savedsearches.conf` - it rolls up each day's
  usage by index/sourcetype/host/source via `collect` into a `summary`
  index. Once enough history has accumulated, point the
  `license_usage_base` macro at that summary index instead of
  `_internal` so the year-long views stay accurate indefinitely.
- **Multiple license pools / a license peer deployment**: the panels sum
  across all pools returned by `licenser/pools`. If the client wants
  per-pool quota tracking (e.g. separate pools for prod vs. dev), split
  `license_pool_quota_gb` by `title` and add a pool selector input.
- **Alerting**: pair the daily rollup saved search with an alert action
  (e.g. `| where PctOfQuota>=90`) to notify the client proactively before
  they breach quota, instead of only showing it on a dashboard.
- **Forecasting**: add a `predict` (or `x11`/`ma`) panel on the daily
  series in `daily_monthly_trend.xml` to project consumption forward and
  help the client anticipate when they'll need to increase their license.

## Files

```
license_usage_dashboard/
  default/
    app.conf
    macros.conf                 # base search, GB conversion, pool quota
    savedsearches.conf          # summary-index rollup (disabled)
    data/ui/nav/default.xml
    data/ui/views/
      license_overview.xml
      daily_monthly_trend.xml
      top_sources.xml
  metadata/
    default.meta
```
