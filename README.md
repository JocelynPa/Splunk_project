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
