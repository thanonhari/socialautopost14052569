param(
    [Parameter(Mandatory = $true)]
    [string]$JobId,

    [string]$Operator = "staging-check",

    [string]$Approval = "APPROVED",

    [string]$BaseUrl = "http://127.0.0.1:8765",

    [int]$TimeoutSec = 900,

    [switch]$StartApp
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Require-EnvVar {
    param([string]$Name)
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Missing required env var: $Name"
    }
    return $value
}

function Wait-HttpReady {
    param(
        [string]$Url,
        [int]$TimeoutSeconds
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            Invoke-RestMethod -Uri $Url -TimeoutSec 3 | Out-Null
            return
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "Server did not become ready: $Url"
}

function Wait-AutopostDone {
    param(
        [string]$Url,
        [string]$Id,
        [int]$TimeoutSeconds
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $job = Invoke-RestMethod -Uri "$Url/api/jobs/$Id" -TimeoutSec 10
        if ($job.autopost_status -in @("done", "failed")) {
            return $job
        }
        Start-Sleep -Seconds 2
    }
    throw "Timeout waiting for autopost completion for job $Id"
}

function Read-JsonFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        return $null
    }
    return Get-Content $Path -Raw | ConvertFrom-Json
}

function Read-JsonLines {
    param([string]$Path)
    $items = @()
    if (-not (Test-Path $Path)) {
        return $items
    }
    foreach ($line in Get-Content $Path) {
        if ($line.Trim()) {
            $items += ($line | ConvertFrom-Json)
        }
    }
    return $items
}

Write-Host "Validating required environment variables..."
Require-EnvVar "SOCIALAUTOPOST_APPROVAL_PHRASE" | Out-Null
Require-EnvVar "SOCIALAUTOPOST_LIVE_MAX_DELIVERIES" | Out-Null
Require-EnvVar "SOCIALAUTOPOST_SHORTS_ADAPTER" | Out-Null
Require-EnvVar "SOCIALAUTOPOST_SHORTS_TOKEN" | Out-Null
Require-EnvVar "SOCIALAUTOPOST_SHORTS_TOKEN_EXPIRES_AT" | Out-Null
Require-EnvVar "SOCIALAUTOPOST_SHORTS_REFRESH_TOKEN" | Out-Null
Require-EnvVar "SOCIALAUTOPOST_SHORTS_CLIENT_ID" | Out-Null
Require-EnvVar "SOCIALAUTOPOST_SHORTS_CLIENT_SECRET" | Out-Null

$adapterMode = [Environment]::GetEnvironmentVariable("SOCIALAUTOPOST_SHORTS_ADAPTER")
if ($adapterMode -ne "native") {
    throw "SOCIALAUTOPOST_SHORTS_ADAPTER must be set to 'native'"
}

$jobDir = Join-Path $root "storage\jobs\$JobId"
$exportsIndexPath = Join-Path $jobDir "exports\index.json"
if (-not (Test-Path $exportsIndexPath)) {
    throw "Job $JobId is missing exports\index.json"
}

$exportsIndex = Read-JsonFile $exportsIndexPath
$clipCount = @($exportsIndex).Count
if ($clipCount -lt 1) {
    throw "Job $JobId has an empty export index"
}

Write-Host "Job $JobId has $clipCount export clip(s)."
if ($clipCount -gt 1) {
    Write-Warning "This run will attempt all exported clips for the shorts platform."
}

$appProcess = $null
try {
    if ($StartApp) {
        $python = (Get-Command python).Source
        Write-Host "Starting app with $python"
        $appProcess = Start-Process -FilePath $python -ArgumentList "-u app.py" -WorkingDirectory $root -WindowStyle Hidden -PassThru
        Wait-HttpReady -Url "$BaseUrl/api/jobs" -TimeoutSeconds 20
    } else {
        Write-Host "Using existing app at $BaseUrl"
        Wait-HttpReady -Url "$BaseUrl/api/jobs" -TimeoutSeconds 10
    }

    $job = Invoke-RestMethod -Uri "$BaseUrl/api/jobs/$JobId" -TimeoutSec 10
    if ($job.status -ne "done") {
        throw "Job $JobId is not ready. Current status: $($job.status)"
    }
    if (-not $job.rights_confirmed) {
        throw "Job $JobId must have rights_confirmed=true before live autopost"
    }

    $payload = @{
        dry_run = $false
        approval = $Approval
        language = "en"
        platforms = @("shorts")
        operator = $Operator
    } | ConvertTo-Json -Depth 5

    Write-Host "Triggering live Shorts native autopost..."
    Invoke-RestMethod `
        -Method Post `
        -Uri "$BaseUrl/api/jobs/$JobId/autopost" `
        -ContentType "application/json" `
        -Headers @{ "X-Operator" = $Operator } `
        -Body $payload | Out-Null

    $finalJob = Wait-AutopostDone -Url $BaseUrl -Id $JobId -TimeoutSeconds $TimeoutSec

    $reportPath = Join-Path $jobDir "autopost.report.json"
    $queuePath = Join-Path $jobDir "autopost.queue.json"
    $controlPath = Join-Path $jobDir "autopost.control.json"
    $auditPath = Join-Path $jobDir "autopost.audit.jsonl"
    $tokenCachePath = Join-Path $root "storage\oauth\shorts.token.json"

    $report = Read-JsonFile $reportPath
    $queue = Read-JsonFile $queuePath
    $control = Read-JsonFile $controlPath
    $audit = Read-JsonLines $auditPath

    $results = @($report.results)
    $postedCount = @($results | Where-Object { $_.status -eq "posted" }).Count
    $failedCount = @($results | Where-Object { $_.delivery_state -eq "failed" }).Count
    $remoteIds = @($results | ForEach-Object { $_.remote_id } | Where-Object { $_ })
    $actions = @($audit | ForEach-Object { $_.action })

    $summary = [ordered]@{
        job_id = $JobId
        app_status = $finalJob.autopost_status
        report_status = $report.status
        clip_count = $clipCount
        result_count = $results.Count
        posted_count = $postedCount
        failed_count = $failedCount
        remote_ids = $remoteIds
        token_cache_exists = Test-Path $tokenCachePath
        report_path = $reportPath
        queue_path = $queuePath
        control_path = $controlPath
        audit_path = $auditPath
        control_state = if ($control) { $control.state } else { "" }
        audit_actions = $actions
    }

    $summaryJson = $summary | ConvertTo-Json -Depth 6
    Write-Host ""
    Write-Host "Summary:"
    Write-Output $summaryJson
} finally {
    if ($appProcess -and (Get-Process -Id $appProcess.Id -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $appProcess.Id -Force
    }
}
