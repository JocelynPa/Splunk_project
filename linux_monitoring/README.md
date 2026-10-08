# Linux Monitoring (built on Splunk_TA_nix)

Dashboard Studio dashboards for Linux servers collected with `Splunk_TA_nix` (v10.x).

| Dashboard | Content |
|---|---|
| Linux Fleet Overview | KPIs (hosts, silent hosts, CPU, memory, swap, disk, load), trends, host status table, top-N |
| Linux Host Deep Dive | One host: CPU by mode, memory/swap, load, disk and network throughput, disks, processes, interfaces |
| Linux Storage & Capacity | Filesystem usage, projected days until full, I/O latency |
| Linux Access & Network Security | SSH/sudo logins, failed logins, account changes, `who`, listening ports |
| Collection Health | Silent hosts, data freshness per sourcetype, events per sourcetype |

## Setup
1. Enable the scripted inputs on the forwarders (`cpu.sh`, `vmstat.sh`, `df.sh`, `iostat.sh`, `ps.sh`, `interfaces.sh`, `bandwidth.sh`, `openPorts.sh`, `who.sh`, `lastlog.sh`, `hardware.sh`) and `monitor:///var/log` for `linux_secure`. They are all `disabled = 1` by default.
2. Edit `default/macros.conf`: `nix_idx` (default `index=os`) and `nix_silent_minutes`.
3. Optional: fill `lookups/nix_host_groups.csv` (`host,group`) for the host-group input.

Sourcetypes used: `cpu`, `vmstat`, `df`, `iostat`, `ps`, `interfaces`, `bandwidth`, `openPorts`, `who`, `lastlog`, `hardware`, `linux_secure`. Fields come from the TA's own props/transforms (e.g. `cpu_load_percent`, `memUsedPct`, `swapUsedPct`, `loadAvg1mi`, `UsePct`, `rKB_PS`).
