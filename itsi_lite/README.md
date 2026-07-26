# ITSI Lite - Service Intelligence Dashboards

A self-contained Splunk app that replicates the core dashboard experience of
**Splunk IT Service Intelligence (ITSI)**: service health scoring, KPI
monitoring, a service dependency tree, deep-dive trend analysis, and a
notable events review. It requires **no external data source** - every
search generates realistic synthetic data on the fly - so you can install it
and see working dashboards immediately.

This is a learning/reference implementation, not a byte-for-byte clone of
ITSI's proprietary code. It's meant to show you the underlying concepts
(service trees, weighted KPI severity, health-score rollups, glass-table
style tiles, deep dives, notable events) using plain Splunk building blocks
(lookups, macros, Simple XML) so you can extend it into your own app.

## What's inside

| Concept (ITSI)              | How it's implemented here                                  |
|------------------------------|-------------------------------------------------------------|
| Service (business/technical/entity) | `lookups/service_tree.csv` - a 3-level service hierarchy |
| KPI + thresholds             | `lookups/kpi_definitions.csv` - one row per KPI, with baseline/volatility and 4 severity thresholds |
| KPI base search              | `itsi_lite_kpi_raw` macro - generates a 48h synthetic time series per KPI (random walk around each KPI's baseline) |
| Severity coloring             | `itsi_lite_kpi_severity` macro - buckets each value into normal/low/medium/high/critical |
| Service health score rollup   | `itsi_lite_service_scores(_over_time)` macros - weighted-average rollup from KPI -> entity -> technical service -> business service |
| Glass Table / Service Analyzer | `service_tree` dashboard - colored tiles per service level + entity table |
| Deep Dive                    | `deep_dive` dashboard - composite health score chart + per-KPI swimlanes for a selected technical service |
| Notable Event Review          | `itsi_lite_notable_events` macro + `notable_events` dashboard - synthetic alerts tied to the same services/KPIs |

## Dashboards

1. **Service Health Dashboard** (default landing page) - overall business
   service health score, per-tier tiles (Web/App/DB/Payment Gateway), and a
   sortable table of every KPI's current value/severity.
2. **Service Tree** - business service -> technical services -> entities,
   rendered as color-coded tiles and a table, similar to an ITSI glass table.
3. **Deep Dive** - pick a technical service and time range; see its composite
   health score over time plus a KPI swimlane chart and entity comparison
   table.
4. **Notable Events** - a filterable table of synthetic notable events
   (severity, status, owner, description) with summary count tiles.

## Install

1. Copy (or symlink) the `itsi_lite/` folder into `$SPLUNK_HOME/etc/apps/`.
2. Restart Splunk, or use **Apps > Manage Apps > Install app from file**
   after zipping this folder (`cd itsi_lite && zip -r ../itsi_lite.tar.gz .`
   then rename/package per your Splunk version's requirements).
3. Open the app - the four dashboards are in the app's navigation bar.

No indexes, inputs, or data onboarding are required. Everything is generated
by `| inputlookup` + `eval`/`streamstats` at search time.

## Extending this into your own app

- **Point it at real data**: replace the body of the `itsi_lite_kpi_raw`
  macro with a search against your real metrics/logs (e.g.
  `| mstats avg(...) ... | eval kpi_id=...`), keeping the same output fields
  (`kpi_id`, `value`, `entity_id`, `technical_service_id`,
  `business_service_id`, `kpi_weight`, threshold_* fields) so the downstream
  severity/rollup macros keep working unchanged.
- **Grow the service tree**: add rows to `lookups/service_tree.csv` and
  `lookups/kpi_definitions.csv` - the dashboards don't hardcode entity
  counts, only the 4 technical-service IDs used for the tiles/dropdowns.
- **Persist scores over time**: enable the disabled saved searches in
  `default/savedsearches.conf` and add a `| collect index=...` stage to
  build a real summary index, closer to how ITSI's KPI base searches work.
- **Real notable events**: swap `itsi_lite_notable_events` for real
  correlation searches that write to Splunk's notable event index (or your
  own), keeping the same field names so the dashboard needs no changes.

## Files

```
itsi_lite/
  default/
    app.conf
    macros.conf                 # KPI generation, severity, rollup logic
    savedsearches.conf          # reference "KPI base search" templates (disabled)
    data/ui/nav/default.xml
    data/ui/views/
      service_health_dashboard.xml
      service_tree.xml
      deep_dive.xml
      notable_events.xml
  lookups/
    service_tree.csv            # business/technical/entity hierarchy
    kpi_definitions.csv         # per-KPI baseline, volatility, thresholds, weight
  metadata/
    default.meta
```
