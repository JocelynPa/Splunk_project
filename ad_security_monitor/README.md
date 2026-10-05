# AD Security & Break-Glass Monitor

A Splunk app for Active Directory administrators and security experts. It
gives one central place to see everything that happens to (and with) the
**`secadm` break-glass account**, plus the state of the directory itself.

| Dashboard | What it answers |
|---|---|
| **AD Accounts Overview** | How many accounts are enabled / disabled / locked / expired, how many have **password never expires**, stale accounts, privileged accounts, risky flags (PASSWD_NOTREQD, AS-REP roastable, unconstrained delegation), `krbtgt` password age, computers by OS. Built on the lookups of the *Microsoft Windows Active Directory Objects* app. |
| **Break-Glass Account (secadm)** | Account state (enabled, password age, never-expires, privileged), **password changes/resets**, attribute changes, enable/disable, lockouts, group membership changes, **who** did it, **from where**, **when**, every logon (type, source IP/host, DC), failed attempts, actions performed *by* the account, off-hours use, source hosts never seen before. |
| **AD Replication & Sync Health** | Per-link replication state (last success, lag, consecutive failures), KCC / lingering object / tombstone / USN rollback / DNS / DFSR events, 4932/4933 sync audit, Kerberos clock-skew (time sync). |
| **AD Account Activity & Threat Detection** | Account creation/deletion/disable, admin password resets, lockouts, privileged group changes, audit log cleared / audit policy changed, DSRM and SID History, password spray, Kerberoasting, DCSync. |

Disabled-by-default alerts (saved searches) cover break-glass logon,
password change, modification, actions performed by the account,
privileged group changes, audit log cleared, failing replication links, and
a daily KPI snapshot for the trend panel.

## Data prerequisites

1. **Windows Security event logs from the domain controllers** (via
   Splunk_TA_windows + Universal Forwarder) in the index set in the
   `adx_index` macro (default `wineventlog`). Required audit policies:
   *Account Management* (4720-4726, 4738, 4740, 4767, 4781, 4794, group
   events 4728/4729/4732/4733/4756/4757), *Logon* (4624/4625/4648/4672),
   *Kerberos Authentication Service* + *Kerberos Service Ticket Operations*
   (4768/4769/4771), *Credential Validation* (4776), *Directory Service
   Changes* (5136, for attribute-level changes on `secadm`), and optionally
   *Directory Service Access* (4662, DCSync) and *Detailed Directory Service
   Replication* (4932/4933).
2. **Directory Service and DFS Replication event logs** from the DCs
   (`WinEventLog:Directory Service`, `WinEventLog:DFS Replication`).
3. **Microsoft Windows Active Directory Objects lookups** for user and
   computer objects (overview dashboard + the break-glass state table).
4. *(Optional)* the replication-status scripted input in
   [`deploy_to_domain_controllers/TA_adx_replication`](../deploy_to_domain_controllers/TA_adx_replication)
   (see below) for the per-link replication table.

## Configuration (one place: `default/macros.conf`, or Settings > Advanced search > Search macros)

| Macro | Purpose | Default |
|---|---|---|
| `adx_index` | Index of the Windows event logs | `index=wineventlog` |
| `adx_users_lookup` / `adx_computers_lookup` | Lookup names from the AD Objects app | `ms_ad_obj_user_lookup` / `ms_ad_obj_computer_lookup` |
| `adx_repl_data` | Replication scripted-input data | `adx:replication` in `adx_index` |
| `adx_stale_days`, `adx_max_pwd_age_days`, `adx_krbtgt_max_age_days`, `adx_spray_threshold` | Thresholds | 90, 90, 180, 10 |
| `adx_offhours_filter` | What counts as off-hours | before 07:00, from 19:00, weekends |
| `adx_priv_group_names` | Privileged groups (EN + FR names) | Domain Admins, Admins du domaine, ... |
| `adx_normalize` | Maps Splunk_TA_windows field names to `target_user`, `actor_user`, `src_ip`, `src_host`, ... | see file |
| `adx_users` / `adx_computers` | Maps lookup columns (`sAMAccountName`, `userAccountControl`, `pwdLastSet`, `lastLogonTimestamp`, `accountExpires`, `memberOf`, `distinguishedName`, `lockoutTime`) | see file |

**Check these two first** - they depend on your environment:

* The lookup names and column names of the AD Objects app. Run
  `| inputlookup <your lookup> | head 1` and adjust `adx_users_lookup` /
  `adx_users` if the columns differ. `userAccountControl` may be the numeric
  bitmask **or** text flags (`ACCOUNTDISABLE`, `DONT_EXPIRE_PASSWORD`, ...);
  timestamps may be FILETIME, epoch or text - `adx_ts()` handles all of these.
* The event field names in `adx_normalize` (classic vs XML event format,
  Splunk_TA_windows version). Check with the Break-Glass dashboard on a known
  `secadm` password change that the "Change log" shows target/actor.

### Break-glass accounts

`lookups/adx_breakglass_accounts.csv` lists the accounts (`secadm` by
default). Add rows to monitor more than one account; all break-glass panels
and alerts follow the file. An account is matched both when it is the
**target** of an event (someone changes/uses it) and when it is the **actor**
(it is used to change other things).

### Replication scripted input

Copy `TA_adx_replication` to **one** domain controller (or an admin host with
RSAT) running a Universal Forwarder, set `disabled = 0` in
`default/inputs.conf`, and adjust `index` if needed. It queries every DC with
`Get-ADReplicationPartnerMetadata` every 10 minutes and emits one line per
inbound link. A copy of `props.conf` is also provided for the indexers.

## Notes and limits

* The overview reflects the last refresh of the AD Objects lookups, not live
  LDAP. `lastLogonTimestamp` is replicated only every ~9-14 days, so use the
  event-based panels for real-time usage of `secadm`.
* Group events (4728/4732/4756...) identify the member by DN; the member is
  matched by the CN of its DN, so members logged only as a SID are not
  attributed to `secadm`.
* No data from your environment was available when this app was written, so
  the SPL has not been run against real events; expect to tune the macros
  above on first install.

## Install

Copy the `ad_security_monitor` folder to `$SPLUNK_HOME/etc/apps/` on the
search head (or deploy it through the SHC deployer) and restart/refresh.
