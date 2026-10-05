# Emits one key=value line per inbound replication link of every DC.
# Requires the ActiveDirectory PowerShell module (RSAT) and read access to AD.
Import-Module ActiveDirectory -ErrorAction Stop
$ts = (Get-Date).ToString("yyyy-MM-ddTHH:mm:sszzz") -replace '(\d\d):(\d\d)$', '$1$2'

function ToEpoch($d) { if ($d) { [int64]([DateTimeOffset]$d).ToUnixTimeSeconds() } else { 0 } }
function Clean($s)   { ([string]$s) -replace '["\r\n]', ' ' }

foreach ($dc in (Get-ADDomainController -Filter *)) {
    try {
        $links = Get-ADReplicationPartnerMetadata -Target $dc.HostName -Partition * -PartnerType Inbound -ErrorAction Stop
        foreach ($l in $links) {
            $partner = if ($l.Partner -match 'CN=NTDS Settings,CN=([^,]+),') { $Matches[1] } else { $l.Partner }
            $msg = if ($l.LastReplicationResult -ne 0) { Clean ([ComponentModel.Win32Exception]::new([int]$l.LastReplicationResult).Message) } else { 'Success' }
            Write-Output ('timestamp={0} source_dc={1} partner={2} partition="{3}" transport={4} last_success_epoch={5} last_attempt_epoch={6} consecutive_failures={7} last_result={8} last_result_text="{9}" status=ok' -f `
                $ts, $dc.HostName, $partner, (Clean $l.Partition), $l.IntersiteTransportType, (ToEpoch $l.LastReplicationSuccess), (ToEpoch $l.LastReplicationAttempt), $l.ConsecutiveReplicationFailures, $l.LastReplicationResult, $msg)
        }
    } catch {
        Write-Output ('timestamp={0} source_dc={1} status=unreachable error="{2}"' -f $ts, $dc.HostName, (Clean $_.Exception.Message))
    }
}
