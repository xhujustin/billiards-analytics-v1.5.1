param(
    [string]$BaseUrl = "http://localhost:8001",
    [string]$PlayerName = "player1",
    [int]$Iterations = 100,
    [int]$Warmup = 5,
    [int]$TimeoutSec = 5,
    [string]$ReportDir = "backend/test-program/reports"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-Percentile {
    param(
        [double[]]$Values,
        [double]$Percentile
    )

    if (-not $Values -or $Values.Count -eq 0) {
        return 0.0
    }

    $sorted = $Values | Sort-Object
    $rank = [Math]::Ceiling(($Percentile / 100.0) * $sorted.Count)
    $index = [Math]::Max(0, [Math]::Min($sorted.Count - 1, [int]$rank - 1))
    return [double]$sorted[$index]
}

function Invoke-EndpointTest {
    param(
        [string]$Name,
        [string]$Url,
        [int]$WarmupCount,
        [int]$TestCount,
        [int]$RequestTimeoutSec
    )

    Write-Host "--- Endpoint: $Name ---"
    Write-Host "URL: $Url"

    $latencies = New-Object System.Collections.Generic.List[double]
    $successCount = 0
    $failureCount = 0
    $statusCodes = @{}

    $totalRequestCount = $WarmupCount + $TestCount

    for ($i = 1; $i -le $totalRequestCount; $i++) {
        $isWarmup = $i -le $WarmupCount
        $sw = [System.Diagnostics.Stopwatch]::StartNew()

        try {
            $response = Invoke-WebRequest -Uri $Url -Method Get -TimeoutSec $RequestTimeoutSec
            $sw.Stop()

            $statusCode = [string][int]$response.StatusCode
            if (-not $statusCodes.ContainsKey($statusCode)) {
                $statusCodes[$statusCode] = 0
            }
            $statusCodes[$statusCode]++

            if (-not $isWarmup) {
                $latencies.Add($sw.Elapsed.TotalMilliseconds)
                if ($statusCode -ge 200 -and $statusCode -lt 300) {
                    $successCount++
                } else {
                    $failureCount++
                }
            }
        }
        catch {
            $sw.Stop()

            if (-not $isWarmup) {
                $latencies.Add($sw.Elapsed.TotalMilliseconds)
                $failureCount++
            }

            $errorKey = "EXCEPTION"
            if (-not $statusCodes.ContainsKey($errorKey)) {
                $statusCodes[$errorKey] = 0
            }
            $statusCodes[$errorKey]++
        }
    }

    $latencyArray = $latencies.ToArray()
    $elapsedSec = ($latencyArray | Measure-Object -Sum).Sum / 1000.0
    if ($elapsedSec -le 0) { $elapsedSec = 0.0001 }

    $summary = [ordered]@{
        name = $Name
        url = $Url
        iterations = $TestCount
        warmup = $WarmupCount
        success_count = $successCount
        failure_count = $failureCount
        error_rate = [Math]::Round(($failureCount / [Math]::Max(1, $TestCount)) * 100.0, 2)
        rps = [Math]::Round($TestCount / $elapsedSec, 2)
        latency_ms = [ordered]@{
            min = [Math]::Round((($latencyArray | Measure-Object -Minimum).Minimum), 2)
            avg = [Math]::Round((($latencyArray | Measure-Object -Average).Average), 2)
            p50 = [Math]::Round((Get-Percentile -Values $latencyArray -Percentile 50), 2)
            p95 = [Math]::Round((Get-Percentile -Values $latencyArray -Percentile 95), 2)
            p99 = [Math]::Round((Get-Percentile -Values $latencyArray -Percentile 99), 2)
            max = [Math]::Round((($latencyArray | Measure-Object -Maximum).Maximum), 2)
        }
        status_codes = $statusCodes
    }

    $health = "PASS"
    if ($summary.error_rate -gt 1 -or $summary.latency_ms.p95 -gt 500) {
        $health = "WARN"
    }
    if ($summary.error_rate -gt 5 -or $summary.latency_ms.p95 -gt 1000) {
        $health = "FAIL"
    }
    $summary["health"] = $health

    Write-Host ("Result: health={0}, err={1}%, p95={2}ms, p99={3}ms, rps={4}" -f $summary.health, $summary.error_rate, $summary.latency_ms.p95, $summary.latency_ms.p99, $summary.rps)
    Write-Host ""

    return $summary
}

if ($Iterations -le 0) {
    throw "Iterations must be > 0"
}
if ($Warmup -lt 0) {
    throw "Warmup must be >= 0"
}

$playerEscaped = [uri]::EscapeDataString($PlayerName)

$targets = @(
    [ordered]@{ name = "health"; url = "$BaseUrl/health" },
    [ordered]@{ name = "recordings_game"; url = "$BaseUrl/api/recordings?mode=game&limit=6&offset=0" },
    [ordered]@{ name = "recordings_practice"; url = "$BaseUrl/api/recordings?mode=practice&limit=6&offset=0" },
    [ordered]@{ name = "stats_player"; url = "$BaseUrl/api/stats/player/$playerEscaped" },
    [ordered]@{ name = "stats_summary"; url = "$BaseUrl/api/stats/summary" },
    [ordered]@{ name = "performance_stats"; url = "$BaseUrl/api/performance/stats" }
)

Write-Host "Stability benchmark started"
Write-Host ("BaseUrl={0}, Iterations={1}, Warmup={2}, TimeoutSec={3}" -f $BaseUrl, $Iterations, $Warmup, $TimeoutSec)
Write-Host ""

$runAt = Get-Date
$results = New-Object System.Collections.Generic.List[object]

foreach ($target in $targets) {
    $result = Invoke-EndpointTest -Name $target.name -Url $target.url -WarmupCount $Warmup -TestCount $Iterations -RequestTimeoutSec $TimeoutSec
    $results.Add($result)
}

$totalFailures = (($results | ForEach-Object { [int]$_["failure_count"] }) | Measure-Object -Sum).Sum
$worstP95 = (($results | ForEach-Object { [double]$_["latency_ms"]["p95"] }) | Measure-Object -Maximum).Maximum
$worstP99 = (($results | ForEach-Object { [double]$_["latency_ms"]["p99"] }) | Measure-Object -Maximum).Maximum

$overall = [ordered]@{
    total_endpoints = $results.Count
    total_requests = $Iterations * $results.Count
    total_failures = $totalFailures
    worst_p95_ms = [Math]::Round($worstP95, 2)
    worst_p99_ms = [Math]::Round($worstP99, 2)
    overall_error_rate = [Math]::Round((($totalFailures / [Math]::Max(1, ($Iterations * $results.Count))) * 100.0), 2)
}

$report = [ordered]@{
    run_at = $runAt.ToString("yyyy-MM-dd HH:mm:ss")
    base_url = $BaseUrl
    iterations = $Iterations
    warmup = $Warmup
    timeout_sec = $TimeoutSec
    player_name = $PlayerName
    overall = $overall
    endpoints = $results
}

if (-not (Test-Path $ReportDir)) {
    New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
}

$reportFile = Join-Path $ReportDir ("stability_report_{0}.json" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
$report | ConvertTo-Json -Depth 10 | Set-Content -Path $reportFile -Encoding UTF8

Write-Host "Benchmark completed"
Write-Host ("Report file: {0}" -f $reportFile)
Write-Host ("Overall: err={0}% worst_p95={1}ms worst_p99={2}ms" -f $overall.overall_error_rate, $overall.worst_p95_ms, $overall.worst_p99_ms)


