# Linux Monitoring (built on Splunk_TA_nix)

Dashboard Studio dashboards for Linux servers collected with `Splunk_TA_nix` (v10.x).

| Dashboard | Content |
|---|---|
| Linux Fleet Overview | KPIs (hosts, silent hosts, CPU, memory, swap, disk, load), trends, host status table, top-N |
| Linux Host Deep Dive | One host: CPU by mode, memory/swap, load, disk and network throughput, disks, processes, interfaces |
| Linux Storage & Capacity | Filesystem usage, projected days until full, I/O latency |
| Linux Access & Network Security | SSH/sudo logins, failed logins, account changes, `who`, listening ports |
| Linux Investigation & Audit Trail | Normalised forensic timeline (SSH, sudo/su, auth failures, account changes, shell history, auditd) with host/user/IP/keyword pivots |
| Collection Health | Silent hosts, data freshness per sourcetype, events per sourcetype |

## Setup
1. Enable the scripted inputs on the forwarders (`cpu.sh`, `vmstat.sh`, `df.sh`, `iostat.sh`, `ps.sh`, `interfaces.sh`, `bandwidth.sh`, `openPorts.sh`, `who.sh`, `lastlog.sh`, `hardware.sh`) and `monitor:///var/log` for `linux_secure`. They are all `disabled = 1` by default.
2. Edit `default/macros.conf`: `nix_idx` (default `index=os`) and `nix_silent_minutes`.
3. Optional: fill `lookups/nix_host_groups.csv` (`host,group`) for the host-group input.

Sourcetypes used: `cpu`, `vmstat`, `df`, `iostat`, `ps`, `interfaces`, `bandwidth`, `openPorts`, `who`, `lastlog`, `hardware`, `linux_secure`. Fields come from the TA's own props/transforms (e.g. `cpu_load_percent`, `memUsedPct`, `swapUsedPct`, `loadAvg1mi`, `UsePct`, `rKB_PS`).

## Who modified a file?
`config_file` events only say *what* changed, not *who*. The Investigation dashboard therefore correlates each recently modified `/etc` file with:
- sudo commands, shell history (`bash_history`) and auditd events on the same host that mention the file path (column `related_actions`, time | user | command), and
- an auditd panel listing the user (`auid` / `AUID`), program, syscall and file for writes under `/etc`.

For reliable attribution enable an audit watch on the servers (`/etc/audit/rules.d/etc.rules`), collect `/var/log/audit/audit.log` as sourcetype `linux_audit`, and set `log_format = ENRICHED` in `auditd.conf` so `AUID` is resolved to a user name:
```
-w /etc -p wa -k etc_changes
```
