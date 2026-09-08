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

## Seeing your whole deployment, not just one instance

This app is meant to be installed once (on a search head, or a search head
cluster) and give you the whole fleet from there - it does **not** need to
be installed on every indexer. It does this two ways:

1. **REST panels use `splunk_server=*`** for anything genuinely
   per-instance: the Search Peers inventory, the all-instances version/
   resource table, disk usage by index, disk space by partition, KV store
   status, cluster mode, and Splunk Web/management-port SSL. Each of these
   returns one row *per reachable instance* (tagged with a `Splunk Server`
   column) instead of collapsing to a single number. A few things stay
   scoped to the instance you're viewing from on purpose because they're
   shared/replicated config, not per-instance state: users, roles, saved
   search ACLs, and license pools (identical everywhere in a normal
   deployment, so fanning out would just produce duplicate rows).
2. **`_internal`/`_audit` searches already span every configured search
   peer automatically** (Splunk distributes any index search across
   peers, same as a normal search) - this app adds `by host` to queue
   fill, CPU/memory, errors/warnings, and forwarder connections so that
   distributed data doesn't get silently pooled into one number and hide
   which site or indexer it came from.

**The prerequisite for either of these to show anything beyond the local
instance: every indexer (and any other instance you want visibility into)
must be added as a distributed search peer** of the search head(s) this
app runs on (**Settings > Distributed search > Search peers**, or
`distsearch.conf`). This is a Splunk architecture requirement, not
something this app can work around - if an indexer isn't a search peer,
no search or REST call from the search head can see it, dashboard or not.
The new **"Search Peers (Indexers) - Fleet Inventory"** panel at the top
of Infrastructure Health is built from `/services/search/distributed/peers`
specifically because it lists every *configured* peer (including ones
currently `Down`) rather than silently omitting anything unreachable -
if a site's indexers are missing from that table entirely, they haven't
been added as peers yet.

**Multi-site / multiple independent indexer clusters** (e.g. a central
site with its own indexer cluster + cluster master, and other sites each
with their own separate indexer cluster + cluster master): Splunk
supports a single search head or SH cluster having peers across several
independent indexer clusters simultaneously, and once those peers are
added, everything above works the same regardless of which site an
indexer belongs to (the peers table's `site` column tells you). Two
things this app does *not* cover, because they need something querying
each cluster master directly rather than through the search head's peer
list:
- **Cluster masters themselves are typically not added as search peers**
  (peers are the indexers, not the CM), so "Cluster Mode by Instance"
  shows each indexer's own `mode` (`slave`) and `site`, but not a given
  site's replication/search factor health from its master's point of
  view. Check that on each site's cluster master directly (**Settings >
  Indexer clustering**), or add the CM as a peer too if you want it to
  show up in the fleet tables.
- **Search head cluster members generally aren't search peers of each
  other**, so panels that read the *local* `_internal` only (skipped
  scheduled searches, REST API access log) reflect whichever SHC member
  you're viewing the dashboard from, not the whole cluster. Switch
  members to compare, or centralize `_internal` into the indexing tier
  (many deployments already forward it there) and repoint those panels
  at that copy if you want one combined view.

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
  `sslConfig` field names, the `/services/search/distributed/peers`
  fields used by the Fleet Inventory panel). Every search here was
  written against well-documented, long-stable endpoints and fields, but
  validate the handful of TLS/SSL, lockout, and peer-inventory panels
  against your target version's `*.conf.spec`/REST reference if
  something looks off.
- **Why some panels inline `| rest ...` instead of using a macro**: the
  `audit_rest_*` macros in `macros.conf` (each a bare `| rest ...` call)
  are safe to reference with `` `macro` `` when they're the first command
  *inside* a bracketed subsearch (`append [...]`, `appendcols [...]`,
  `join [...]` - see the Audit Findings table and `savedsearches.conf`).
  They are **not** safe as the literal first token of a top-level panel
  `<query>`: Splunk decides whether to implicitly prepend `search` based
  on the raw, pre-macro-expansion text, so a query starting with a
  backtick (rather than a literal `|`) can get dispatched as `search
  \`macro\` ...`, which expands to `search | rest ...` and fails with
  *"Error in 'rest' command: This command must be the first command of a
  search."* Every panel that calls a REST endpoint directly (not nested
  in a subsearch) therefore writes `| rest ...` out in full instead of
  going through a macro. Keep this in mind if you add new panels: a
  generating-command macro is only safe to invoke top-level with an
  explicit `| \`macro\`` (pipe then backtick) *and* a macro definition
  with no leading pipe of its own - inlining the full command is simpler
  and is what this app does throughout.
- **Disk space panel/finding** (`/services/server/status/partitions-space`)
  assumes the endpoint's `free`/`capacity` values are in MB, matching
  `minFreeSpace` (also MB, per `server.conf.spec`) - this holds on every
  version this was checked against, but if the "Disk Space by Partition"
  numbers look off by a factor of ~1000 on your instance, the endpoint is
  returning KB instead; fix the `/1024` conversions in
  `infrastructure_health.xml` and the matching check in `audit_summary.xml`
  / `savedsearches.conf`.
- Login-activity panels reflect Splunk's own local authentication
  logging (`index=_audit action=login`). **LDAP-backed auth is fine**:
  Splunk still renders its own login page and calls out to the LDAP
  server to verify the credentials, so both successful and failed
  attempts are logged the same way as local accounts - the failed/
  successful login panels need no adjustment. **SSO/SAML is different**:
  there, an external identity provider owns the login page and Splunk
  only ever sees the final assertion, so attempts rejected upstream
  (wrong password at the IdP, MFA failure, etc.) never reach Splunk and
  won't appear here.
- **User Inventory only lists users who have logged into Splunk at least
  once.** With LDAP (or any external auth), Splunk creates a local
  "shadow" user record the first time someone authenticates - it does
  not mirror the full LDAP/AD directory or group membership up front. So
  this table under-counts anyone with LDAP-mapped access who simply
  hasn't logged in yet; it is not a substitute for reviewing the LDAP
  group-to-role mapping in the LDAP strategy itself (which controls who
  *can* log in and with which role, regardless of whether they've done
  so yet).
- **LDAP Authentication Strategies panel** (`/services/authentication/
  providers/LDAP`) is a lower-confidence endpoint than the others in this
  app - field names (`SSL`, `bindDN`, `userBaseDN`, `groupBaseDN`) match
  what Splunk Web's own LDAP settings page is built on, but validate them
  against `authentication.conf.spec` on your version if the panel looks
  empty or wrong. The one thing worth trusting even before you validate
  it: if the `Encrypted` column comes back red ("Plain LDAP
  (unencrypted)"), that's worth checking manually regardless - it means
  bind credentials are going out over the wire in cleartext.

## Dashboards

1. **Audit Summary** (default landing page) - five headline KPIs (errors,
   skipped searches, max queue fill, failed logins, locked-out accounts)
   plus a single consolidated **Audit Findings** table: about a dozen
   pass/fail checks spanning both infrastructure and security, each rated
   `OK` / `WARNING` / `CRITICAL` with a plain-language detail (e.g. "3
   index(es) at/above 80% of max size", "Splunk Web is serving over plain
   HTTP"). This is the "read this first" view - it tells you what needs
   attention, the other two dashboards tell you why.
2. **Infrastructure Health** - starts with a **fleet inventory**: every
   configured search peer with its site and up/down status, and every
   reachable instance's version/OS/uptime/CPU/memory in one table. Then:
   indexing queue fill % (trend + current snapshot by host), CPU/memory
   by host, indexing volume by index, errors/warnings by host and
   component (table + trend), skipped scheduled searches, forwarder
   connections (by receiving indexer), disk usage by index by instance,
   **disk space by partition by instance vs. the `minFreeSpace`
   threshold** (the free-space floor below which Splunk stops
   indexing/searching - a frequent, avoidable cause of outages), KV
   store status by instance, cluster mode/site by instance, and license
   usage vs. quota.
3. **Security Audit** - login activity trend and top users by failed
   login, the full user inventory (roles, auth type, lockout state), the
   role inventory (capability count, allowed/default search indexes),
   **LDAP authentication strategy configuration** (host/port, bind DN,
   base DNs, and whether the connection is encrypted), privileged
   configuration changes from the audit trail (user/role/auth edits over
   the last 7 days), Splunk Web and management-port (8089) SSL status
   **by instance**, globally-shared saved searches writable by everyone,
   and recent access to sensitive REST endpoints (users, roles, indexes,
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
- **Fleet-wide the checks that are still instance-scoped**: the Audit
  Findings checklist's SSL, KV store, user/role, and license checks
  intentionally query the instance you're viewing from (see "Seeing your
  whole deployment" above) to keep the aggregation logic simple. To make
  one of them fleet-wide, switch its macro in `macros.conf` to
  `splunk_server=*` and change the `stats max(...)`/`stats values(...)`
  in that check to `stats min(...)` (or equivalent) so a single bad
  instance flips the whole check to `WARNING`/`CRITICAL` instead of
  being averaged/maxed away - the disk-space and index-size checks
  already do this correctly and are a good template.
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
