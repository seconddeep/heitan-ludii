[CmdletBinding()]
param(
    [string]$LudiiJar = $env:LUDII_JAR,
    [string]$ConfigPath = '',
    [ValidateRange(1, 64)]
    [int]$Parallelism = 1,
    [ValidateRange(1, 10000)]
    [int]$BatchSize = 10,
    [switch]$MetadataOnly
)

$ErrorActionPreference = 'Stop'
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$issueRoot = [System.IO.Path]::GetFullPath((Join-Path $scriptDirectory '..'))
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $issueRoot '..\..'))
if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $issueRoot 'config.json'
}
$configPath = [System.IO.Path]::GetFullPath($ConfigPath)

if ([string]::IsNullOrWhiteSpace($LudiiJar)) {
    throw 'Pass -LudiiJar or set the LUDII_JAR environment variable.'
}
$LudiiJar = [System.IO.Path]::GetFullPath($LudiiJar)
if (-not (Test-Path -LiteralPath $LudiiJar -PathType Leaf)) {
    throw "Ludii JAR not found: $LudiiJar"
}
if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw "Experiment configuration not found: $configPath"
}

$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
if ($config.ludii_version -ne '1.3.14') {
    throw "This workflow is validated against Ludii 1.3.14, not $($config.ludii_version)."
}
if (@($config.experiments).Count -lt 2) {
    throw 'At least two UCT strength experiments are required.'
}

$ids = @{}
foreach ($experiment in $config.experiments) {
    if ([string]$experiment.black_agent -ne 'UCT' -or [string]$experiment.white_agent -ne 'UCT') {
        throw "Experiment '$($experiment.id)' is not UCT self-play."
    }
    if ([int]$experiment.games -le 0 -or [int]$experiment.iteration_limit -le 0) {
        throw "Experiment '$($experiment.id)' must have positive games and iteration_limit values."
    }
    if ($ids.ContainsKey([string]$experiment.id)) {
        throw "Duplicate experiment id: $($experiment.id)"
    }
    $ids[[string]$experiment.id] = $true
}

$gamePath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $config.game))
$runnerPath = Join-Path $repoRoot 'experiments\issue-11\scripts\HeitanExperiment.java'
$analysisPath = Join-Path $scriptDirectory 'analyze-results.ps1'
$resultsPath = Join-Path $issueRoot 'results'
$rawPath = Join-Path $resultsPath 'raw'
$trialsPath = Join-Path $resultsPath 'trials'
New-Item -ItemType Directory -Force -Path $rawPath, $trialsPath | Out-Null

$startedAt = [DateTime]::UtcNow
$timingSource = 'script'
if ($MetadataOnly) {
    $evidenceFiles = @(
        Get-ChildItem -LiteralPath $rawPath -Filter '*.csv' -File -ErrorAction SilentlyContinue
        Get-ChildItem -LiteralPath $trialsPath -Filter '*.trl' -File -Recurse -ErrorAction SilentlyContinue
    )
    if ($evidenceFiles.Count -gt 0) {
        $startedAt = ($evidenceFiles | Sort-Object CreationTimeUtc | Select-Object -First 1).CreationTimeUtc
        $timingSource = 'evidence_file_timestamps'
    }
}
$timings = @()
if (-not $MetadataOnly) {
    # A run is a complete snapshot. Remove only generated raw/trial evidence
    # from a previous run so stale batches cannot enter the analysis.
    Get-ChildItem -LiteralPath $rawPath -Filter '*.csv' -File -ErrorAction SilentlyContinue | Remove-Item -Force
    Get-ChildItem -LiteralPath $trialsPath -Filter '*.trl' -File -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force

    $experimentOffset = 0L
    $tasks = @()
    foreach ($experiment in $config.experiments) {
        $experimentId = [string]$experiment.id
        $experimentTrials = Join-Path $trialsPath $experimentId
        New-Item -ItemType Directory -Force -Path $experimentTrials | Out-Null
        $effectiveBatchSize = if ($Parallelism -eq 1) { [int]$experiment.games } else { $BatchSize }
        for ($batchOffset = 0; $batchOffset -lt [int]$experiment.games; $batchOffset += $effectiveBatchSize) {
            $batchGames = [Math]::Min($effectiveBatchSize, [int]$experiment.games - $batchOffset)
            $batchNumber = [int]([Math]::Floor($batchOffset / $effectiveBatchSize) + 1)
            $tasks += [pscustomobject]@{
                experiment_id = $experimentId
                black_agent = [string]$experiment.black_agent
                white_agent = [string]$experiment.white_agent
                games = $batchGames
                base_seed = [long]$config.base_seed + $experimentOffset + $batchOffset
                iteration_limit = [int]$experiment.iteration_limit
                max_seconds = [double]$experiment.max_seconds_per_move
                raw_file = Join-Path $rawPath ("{0}-batch-{1:D3}.csv" -f $experimentId, $batchNumber)
                trials_directory = $experimentTrials
                game_index_offset = $batchOffset
            }
        }
        $experimentOffset += [long]$experiment.games
    }

    $pending = [System.Collections.Queue]::new()
    foreach ($task in $tasks) { $pending.Enqueue($task) }
    $running = @()
    $batchResults = @()
    while ($pending.Count -gt 0 -or $running.Count -gt 0) {
        while ($pending.Count -gt 0 -and $running.Count -lt $Parallelism) {
            $task = $pending.Dequeue()
            $job = Start-Job -ScriptBlock {
                param($JavaJar, $Source, $Game, $Task)
                $watch = [System.Diagnostics.Stopwatch]::StartNew()
                & java -cp $JavaJar $Source `
                    $Game `
                    $Task.experiment_id `
                    $Task.black_agent `
                    $Task.white_agent `
                    $Task.games `
                    $Task.base_seed `
                    $Task.iteration_limit `
                    $Task.max_seconds `
                    $Task.raw_file `
                    $Task.trials_directory `
                    $Task.game_index_offset | ForEach-Object { Write-Host $_ }
                $exitCode = $LASTEXITCODE
                $watch.Stop()
                [pscustomobject]@{
                    experiment_id = $Task.experiment_id
                    games = $Task.games
                    iteration_limit = $Task.iteration_limit
                    elapsed_seconds = $watch.Elapsed.TotalSeconds
                    exit_code = $exitCode
                }
            } -ArgumentList $LudiiJar, $runnerPath, $gamePath, $task
            $running += $job
        }

        $finishedJob = Wait-Job -Job $running -Any
        $received = @(Receive-Job -Job $finishedJob)
        $result = @($received | Where-Object { $_.PSObject.Properties.Name -contains 'exit_code' }) | Select-Object -Last 1
        Remove-Job -Job $finishedJob
        $running = @($running | Where-Object Id -ne $finishedJob.Id)
        if ($null -eq $result -or [int]$result.exit_code -ne 0) {
            throw "Experiment batch failed in job $($finishedJob.Id)."
        }
        $batchResults += $result
        Write-Host ("Completed batch: {0}, {1} games, {2} iterations" -f $result.experiment_id, $result.games, $result.iteration_limit)
    }

    foreach ($experiment in $config.experiments) {
        $group = @($batchResults | Where-Object experiment_id -eq ([string]$experiment.id))
        $elapsed = ($group | Measure-Object -Property elapsed_seconds -Sum).Sum
        $timings += [pscustomobject][ordered]@{
            experiment_id = [string]$experiment.id
            games = [int]$experiment.games
            iteration_limit = [int]$experiment.iteration_limit
            worker_seconds = [Math]::Round($elapsed, 3)
            average_worker_seconds_per_game = [Math]::Round($elapsed / [int]$experiment.games, 3)
            batches = $group.Count
        }
    }
    $timings | Export-Csv -LiteralPath (Join-Path $resultsPath 'timings.csv') -NoTypeInformation -Encoding UTF8
}

$gitCommit = (& git -c "safe.directory=$($repoRoot.Replace('\', '/'))" -C $repoRoot rev-parse HEAD).Trim()
$javaVersion = (& java --version | Select-Object -First 1).ToString()
$finishedAt = [DateTime]::UtcNow
if ($MetadataOnly -and $evidenceFiles.Count -gt 0) {
    $finishedAt = ($evidenceFiles | Sort-Object LastWriteTimeUtc | Select-Object -Last 1).LastWriteTimeUtc
}
$environment = [ordered]@{
    generated_at_utc = $finishedAt.ToString('o')
    run_started_at_utc = $startedAt.ToString('o')
    elapsed_seconds = [Math]::Round(($finishedAt - $startedAt).TotalSeconds, 3)
    timing_source = $timingSource
    config = 'experiments/issue-30/config.json'
    config_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $configPath).Hash.ToLowerInvariant()
    runner = 'experiments/issue-11/scripts/HeitanExperiment.java'
    runner_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $runnerPath).Hash.ToLowerInvariant()
    run_script_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $MyInvocation.MyCommand.Path).Hash.ToLowerInvariant()
    analysis_script_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $analysisPath).Hash.ToLowerInvariant()
    game = $config.game
    game_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $gamePath).Hash.ToLowerInvariant()
    git_commit = $gitCommit
    ludii_version = $config.ludii_version
    ludii_jar_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $LudiiJar).Hash.ToLowerInvariant()
    java = $javaVersion
    os = [System.Environment]::OSVersion.VersionString
}
$environment | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $resultsPath 'environment.json') -Encoding UTF8

if ($MetadataOnly) {
    Write-Host "Environment metadata written to $(Join-Path $resultsPath 'environment.json')"
} else {
    Write-Host "Raw results written to $rawPath"
}
