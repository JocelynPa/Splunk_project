# Infrastructure & Security Audit

A self-contained Splunk app that audits the state of a Splunk deployment
along two axes:

1. **Infrastructure health** - is the platform itself working correctly?
   Indexing pipeline queues, indexing volume, host CPU/memory, errors and
   warnings, the search scheduler, disk usage per index, forwarder
   connections, KV store status, cluster mode, and license usage.
2. **Security posture** - is the deployment configured and used safely?
   Authentication activity and failed logins, the user/role inventory,
   privileged configuration changes, TLS/SSL configuration, world-writable
   knowledge objects, and access to sensitive REST endpoints.

Like `license_usage_dashboard` in this repo, every panel queries Splunk's
own internal indexes (`_internal`, `_audit`) and built-in REST endpoints
(`server/info`, `data/indexes`, `authentication/users`,
`authorization/roles`, `licenser/pools`, `kvstore/status`,
`cluster/config`, `saved/searches`, `configs/conf-server`,
`server/settings`) - no add-on or external data onboarding required.

## Requirements

- Install on a search head with visibility into the instance(s) you want
  to audit. Most panels call authenticated REST endpoints that expose
  admin-level configuration, so the viewing user needs the built-in
  `admin` role, or a custom role with at least: `rest_properties_get`,
  `list_settings`, `edit_user` (read access), `edit_roles` (read access),
  and search access to `_internal` and `_audit`.
- No add-on, index, or data onboarding is required - `_internal`,
  `_audit`, and the REST endpoints used here exist on every Splunk
  instance out of the box.
- **Field names on REST-backed panels can shift slightly between Splunk
  versions** (e.g. `authentication.conf` password-policy keys, exact
  `sslConfig` field names). Every search here was written against
  well-documented, long-stable endpoints and fields, but validate the
  handful of TLS/SSL and lockout panels against your target version's
  `*.conf.spec` files if something looks off, and adjust the macro in
  `macros.conf` - every dashboard panel is built from a macro, so a fix
  in one place fixes every panel that uses it.
- **Disk space panel/finding** (`/services/server/status/partitions-space`)
  assumes the endpoint's `free`/`capacity` values are in MB, matching
  `minFreeSpace` (also MB, per `server.conf.spec`) - this holds on every
  version this was checked against, but if the "Disk Space by Partition"
  numbers look off by a factor of ~1000 on your instance, the endpoint is
  returning KB instead; fix the `/1024` conversions in
  `infrastructure_health.xml` and the matching check in `audit_summary.xml`
  / `savedsearches.conf`.
- Login-activity panels reflect Splunk's own local authentication
  logging (`index=_audit action=login`). If the deployment sits behind
  SSO/SAML, failed attempts rejected upstream of Splunk won't appear
  here.

## Dashboards

1. **Audit Summary** (default landing page) - five headline KPIs (errors,
   skipped searches, max queue fill, failed logins, locked-out accounts)
   plus a single consolidated **Audit Findings** table: about a dozen
   pass/fail checks spanning both infrastructure and security, each rated
   `OK` / `WARNING` / `CRITICAL` with a plain-language detail (e.g. "3
   index(es) at/above 80% of max size", "Splunk Web is serving over plain
   HTTP"). This is the "read this first" view - it tells you what needs
   attention, the other two dashboards tell you why.
2. **Infrastructure Health** - indexing queue fill % (trend + current
   snapshot), host CPU/memory, indexing volume by index, errors/warnings
   by component (table + trend), skipped scheduled searches, forwarder
   connections, disk usage by index vs. its max size, **disk space by
   partition vs. the `minFreeSpace` threshold** (the free-space floor
   below which Splunk stops indexing/searching - a frequent, avoidable
   cause of outages), KV store status, cluster mode, and license usage
   vs. quota.
3. **Security Audit** - login activity trend and top users by failed
   login, the full user inventory (roles, auth type, lockout state), the
   role inventory (capability count, allowed/default search indexes),
   privileged configuration changes from the audit trail (user/role/auth
   edits over the last 7 days), Splunk Web and management-port (8089) SSL
   status, globally-shared saved searches writable by everyone, and
   recent access to sensitive REST endpoints (users, roles, indexes,
   server settings).

## How the findings checklist works

`audit_summary.xml`'s **Audit Findings** table is built by running each
check as its own small search (a REST call or an `_internal`/`_audit`
search reduced to a single summary row), tagging it with
`Category`/`Check`/`Status`/`Detail`, and `append`-ing all of them
together into one table sorted `CRITICAL` > `WARNING` > `OK`. Thresholds
(e.g. "WARNING at 20 failed logins/24h, CRITICAL at 100") are reasonable
starting points, not universal truths - tune them in the `eval case(...)`
clauses to match the deployment's normal baseline.

## Install

1. Copy (or symlink) the `infra_security_audit/` folder into
   `$SPLUNK_HOME/etc/apps/`.
2. Restart Splunk, or use **Apps > Manage Apps > Install app from file**
   after zipping this folder.
3. Install on a search head (or the instance you want to audit directly)
   with an account that has the `admin` role (see Requirements above).
4. Open the app - **Audit Summary**, **Infrastructure Health**, and
   **Security Audit** are in the app's navigation bar.

## Extending this into your own app

- **Trend the findings over time**: enable the disabled
  `[Infra & Security Audit - Daily Findings Snapshot to Summary Index]`
  saved search in `default/savedsearches.conf` - it runs the same
  findings checklist once a day and `collect`s it into a `summary`
  index, so you can build a "how has our posture changed" view instead
  of only ever seeing today's state.
- **Alerting**: wrap any individual check (or the full findings search)
  in a saved search with an alert action (e.g. trigger when any row has
  `Status="CRITICAL"`) to get notified proactively instead of only
  seeing it on a dashboard.
- **Multi-instance / distributed environments**: every REST-backed macro
  in `macros.conf` uses `splunk_server=local`. On a search head with
  access to peers, change this to `splunk_server=*` (or a specific list)
  to audit indexers/peers from one place - just be aware panels like
  disk usage or queue fill will then return one row per peer, so you may
  want to add `by splunk_server` to the relevant `stats`/`table`
  commands.
- **More checks**: the findings table is a plain `append` chain of
  single-row searches with `Category`/`Check`/`Status`/`Detail` fields -
  add a new check by writing one more search in that shape and appending
  it, in both `audit_summary.xml` and (if you enable trending)
  `savedsearches.conf`.

## Files

```
infra_security_audit/
  default/
    app.conf
    macros.conf                 # every base search/REST call, reused across all 3 dashboards
    savedsearches.conf          # daily findings snapshot to summary index (disabled)
    data/ui/nav/default.xml
    data/ui/views/
      audit_summary.xml
      infrastructure_health.xml
      security_audit.xml
  metadata/
    default.meta
```
