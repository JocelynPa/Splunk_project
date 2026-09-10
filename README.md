# Splunk_project

## itsi_lite

A self-contained Splunk app that replicates the core dashboard experience of
Splunk IT Service Intelligence (ITSI) - service health scoring, a service
dependency tree, KPI deep dives, and a notable events review - using fully
synthetic sample data so it works with zero external data sources. See
[`itsi_lite/README.md`](itsi_lite/README.md) for details and install steps.

## license_usage_dashboard

A self-contained Splunk app for showing clients their **real** license
consumption: an annual overview against their license pool quota, daily and
monthly trends, and a breakdown of which indexes, sourcetypes, hosts, and
sources consume the most license. Built entirely on Splunk's own internal
`license_usage.log` events - no add-on or data onboarding required. See
[`license_usage_dashboard/README.md`](license_usage_dashboard/README.md) for
details and install steps.

## infra_security_audit

A self-contained Splunk app that audits the state of a Splunk deployment:
an infrastructure health check (indexing queues, indexing volume, host
resource usage, errors, scheduler, disk usage, forwarders, KV store,
cluster mode, license usage) and a security audit (authentication
activity, user/role inventory, privileged configuration changes, TLS/SSL
configuration, world-writable knowledge objects, sensitive REST API
access), plus a consolidated pass/fail findings checklist. Built entirely
on Splunk's own internal indexes and REST endpoints - no add-on required.
See [`infra_security_audit/README.md`](infra_security_audit/README.md)
for details and install steps.

## GitDeploy_for_Splunk

A Splunk app plus companion SH Deployer agent that pushes Splunk apps to a
Git repository and optionally deploys them to a Search Head Cluster via
`splunk apply shcluster-bundle`, with a commercial RSA-based licensing
system. See
[`GitDeploy_for_Splunk/README.md`](GitDeploy_for_Splunk/README.md) and
[`GitDeploy_for_Splunk/INSTALL.md`](GitDeploy_for_Splunk/INSTALL.md) for
details and install steps.
