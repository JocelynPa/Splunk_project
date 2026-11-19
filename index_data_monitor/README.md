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

*Index Data Monitor* and *Alert History* are **Dashboard Studio** dashboards (dark theme,
Splunk 9.x+; tested target: 10.4). The two threshold forms stay in Simple XML
because Dashboard Studio has no Apply button / no way to stop searches from
running on every input change, which is required for a form that writes to a lookup.

| View | Purpose |
|---|---|
| Index Data Monitor | KPIs, freshness table, status history, drilldown to sourcetypes/hosts and hourly volume |
| Alert History | Silence episodes per index, alert runs and triggers |
| Thresholds | Form to edit index thresholds; effective threshold per index and the lookup content |

## Localization

The Simple XML views (the two threshold forms) and the app name are translated
to French when the user's Splunk language is fr_FR
(`locale/fr_FR/LC_MESSAGES/index_data_monitor.po`/`.mo`); other languages fall back to
English. Dashboard Studio views, table column names built in SPL and alert email text
stay in English. After a change, run `splunk restart` or reload `/debug/refresh`.

## Sourcetype thresholds

Opt-in rules per (index, sourcetype) in `lookups/idxmon_st_thresholds.csv`,
edited from the *Sourcetype Thresholds* view. Wildcards are allowed on both
fields (first match wins). Rules without wildcards also detect a sourcetype
that vanished completely (no event in the lookback), wildcard rules only apply
to combinations seen in the lookback. Dedicated alerts: **Sourcetype not
receiving data**, **Sourcetype recovered**, plus a snapshot to the summary index
(sourcetype `idxmon_status_st`). Index-level and sourcetype-level alerts are
independent.

## Configuration

1. **Thresholds**: use the *Thresholds* view (form: add/update/delete a rule, click a
   row to load it; needs write permission on the lookup, role admin/power), or edit `lookups/idxmon_thresholds.csv` (or use the Lookup
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
  validate on a dev search head first (run `` | `idxmon_status` `` in Search).
