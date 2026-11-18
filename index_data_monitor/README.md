# Index Data Monitor

Proactive alerting when an index **stops receiving data**.

## How it works

- `idxmon_status` (macro) builds one row per index: the most recent
  **index time** (`_indextime`, so late/backdated events can't hide a stalled
  pipeline) from `tstats`, merged with `| rest /services/data/indexes` so that
  indexes with no data in the lookback window are still listed.
- Each index is compared with its allowed silence from the lookup
  `idxmon_thresholds` and gets a status: `STALE`, `Warning` (>= 75% of the
  threshold), `OK`, `Empty` (never received data) or `Ignored`.
- Saved search **IDX Monitor - Alert - Index not receiving data** runs every
  15 min, triggers one alert per STALE index, throttled 4h per index.
- Saved search **IDX Monitor - Alert - Index recovered** (every 15 min, offset by 2 min
  after the snapshot) fires once per index that goes from `STALE` back to
  `OK`/`Warning`, by comparing two consecutive snapshots. It depends on the
  snapshot search being enabled; throttled 1h per index.
- Saved search **IDX Monitor - Status Snapshot to Summary Index** stores the
  statuses in `index=summary` (sourcetype `idxmon_status`) for the history views.

## Views

| View | Purpose |
|---|---|
| Index Data Monitor | KPIs, freshness table, status history, drilldown to sourcetypes/hosts and hourly volume |
| Alert History | Silence episodes per index, alert runs and triggers |
| Thresholds | Effective threshold per index and the lookup content |

## Configuration

1. **Thresholds**: edit `lookups/idxmon_thresholds.csv` (or use the Lookup
   Editor app). Columns: `index` (wildcards allowed), `threshold_minutes`,
   `enabled` (0 = ignore), `severity`, `owner`, `comment`. **The first matching
   row wins** - keep specific rows first and `*` last. Default: 60 min.
   Indexes that are legitimately quiet at night/weekends should get a larger
   threshold (e.g. 4320 for 3 days).
2. **Notifications**: in *Settings > Searches, reports, and alerts*, open the
   alert and add an action (email, webhook, ITSM), or uncomment the
   `action.email.*` lines in `default/savedsearches.conf`.
3. **Macros**: `idxmon_lookback` (default `-30d@d`), `idxmon_default_threshold`,
   `idxmon_warning_ratio`.

## Notes / limits

- Run the alert as a user whose role can search **all** indexes
  (`srchIndexesAllowed`), otherwise inaccessible indexes will look silent.
- Install on a search head with the indexers as search peers (the REST call
  uses `splunk_server=*`). Metric indexes are not covered (`tstats` on events only).
- Recovery detection only works from snapshot history: an outage that began
  before the app was installed (no prior `STALE` snapshot) gets no recovery alert.
- A brand-new index with no data is `Empty` (no alert); once it received data
  and then stops, it becomes `STALE`.
- Searches were written without a Splunk instance available to test them:
  validate on a dev search head first (run `` `idxmon_status` `` in Search).
