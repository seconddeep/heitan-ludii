[CmdletBinding()]
param(
    [string]$LudiiJar = 'C:\Users\verti\Ludii-1.3.14.jar',
    [ValidateRange(1, 16)][int]$Parallelism = 1,
    [ValidateRange(1, 50)][int]$BatchSize = 5,
    [ValidateRange(0, 50)][int]$GamesPerExperiment = 0,
    [string[]]$ExperimentId = @(),
    [switch]$FinalizeOnly
)
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$issue = [IO.Path]::GetFullPath((Join-Path $scriptDir '..'))
$repo = [IO.Path]::GetFullPath((Join-Path $issue '..\..'))
$config = Get-Content -Raw (Join-Path $issue 'config.json') | ConvertFrom-Json
$frozen = Join-Path $repo $config.frozen_analysis_source
foreach ($name in @('analyze-scale.mjs', 'analyze-scale.test.mjs', 'Heitan6x6Experiment.java', 'HeitanScaleReplay.java')) {
    $source = Join-Path $frozen "scripts/$name"
    $copy = Join-Path $scriptDir $name
    if ((Get-FileHash $source -Algorithm SHA256).Hash -ne (Get-FileHash $copy -Algorithm SHA256).Hash) {
        throw "Frozen Issue 56 source differs: $name"
    }
}
$selected = @($config.experiments | Where-Object {
    $ExperimentId.Count -eq 0 -or $ExperimentId -contains $_.id
})
if ($selected.Count -eq 0) { throw 'No configured experiment selected.' }
if ($ExperimentId.Count -gt 0) {
    $unknown = @($ExperimentId | Where-Object { $_ -notin @($config.experiments.id) })
    if ($unknown.Count) { throw "Unknown experiment id: $($unknown -join ', ')" }
}

$smoke = $GamesPerExperiment -gt 0
$root = Join-Path $issue $(if ($smoke) { 'results-smoke' } else { 'results' })
$raw = Join-Path $root 'raw'
$trials = Join-Path $root 'trials'
New-Item -ItemType Directory -Force -Path $raw, $trials | Out-Null

$runner = Join-Path $scriptDir 'Heitan6x6Experiment.java'
$game = Join-Path $repo $config.game
$tasks = @()
if (-not $FinalizeOnly) {
    foreach ($experiment in $selected) {
        $count = if ($smoke) { $GamesPerExperiment } else { [int]$experiment.games }
        $indexOffset = if ($smoke) { 0 } else { [int]$experiment.index_offset }
        $seedBase = [long]$experiment.base_seed
        $trialDir = Join-Path $trials $experiment.id
        New-Item -ItemType Directory -Force -Path $trialDir | Out-Null
        Get-ChildItem $trialDir -Filter '*.trl' -File -ErrorAction SilentlyContinue | Remove-Item -Force
        Get-ChildItem $raw -Filter "$($experiment.id)-batch-*.csv" -File -ErrorAction SilentlyContinue | Remove-Item -Force
        $effective = if ($Parallelism -eq 1) { $count } else { $BatchSize }
        for ($offset = 0; $offset -lt $count; $offset += $effective) {
            $size = [Math]::Min($effective, $count - $offset)
            $batchNumber = [int]($offset / $effective) + 1
            $tasks += [pscustomobject]@{
                id = $experiment.id
                agent = $experiment.agent
                games = $size
                seed = $seedBase + $offset
                iterations = $experiment.iteration_limit
                offset = $indexOffset + $offset
                raw = Join-Path $raw ('{0}-batch-{1:D3}.csv' -f $experiment.id, $batchNumber)
                trials = $trialDir
            }
        }
    }
    $pending = [Collections.Queue]::new()
    $tasks | ForEach-Object { $pending.Enqueue($_) }
    $running = @()
    $started = [DateTime]::UtcNow
    while ($pending.Count -or $running.Count) {
        while ($pending.Count -and $running.Count -lt $Parallelism) {
            $task = $pending.Dequeue()
            $running += Start-Job -ScriptBlock {
                param($jar, $runner, $game, $repo, $task)
                & java -cp $jar $runner $game $task.id $task.agent $task.games $task.seed $task.iterations $task.raw $task.trials $repo $task.offset
                if ($LASTEXITCODE) { throw "Java exit $LASTEXITCODE" }
            } -ArgumentList $LudiiJar, $runner, $game, $repo, $task
        }
        $done = Wait-Job $running -Any
        Receive-Job $done
        if ($done.State -ne 'Completed') { throw "Experiment job $($done.Id) failed" }
        Remove-Job $done
        $running = @($running | Where-Object Id -ne $done.Id)
    }
} else {
    $firstTrial = Get-ChildItem $trials -Filter '*.trl' -File -Recurse | Sort-Object CreationTimeUtc | Select-Object -First 1
    if (-not $firstTrial) { throw 'No trials to finalize.' }
    $started = $firstTrial.CreationTimeUtc
}

$rows = @($selected | ForEach-Object {
    Get-ChildItem $raw -Filter "$($_.id)-batch-*.csv" -File | ForEach-Object { Import-Csv $_.FullName }
})
if (@($rows.seed | Sort-Object -Unique).Count -ne $rows.Count) { throw 'Duplicate seeds.' }
foreach ($experiment in $selected) {
    $expected = if ($smoke) { $GamesPerExperiment } else { [int]$experiment.games }
    $actual = @($rows | Where-Object experiment_id -eq $experiment.id).Count
    if ($actual -ne $expected) { throw "Unexpected game count for $($experiment.id): $actual, expected $expected" }
}
$environment = [ordered]@{
    schema_version = 1
    smoke = $smoke
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    elapsed_seconds = [Math]::Round(([DateTime]::UtcNow - $started).TotalSeconds, 3)
    games = $rows.Count
    experiments = @($selected.id)
    seed_min = [long](($rows.seed | Measure-Object -Minimum).Minimum)
    seed_max = [long](($rows.seed | Measure-Object -Maximum).Maximum)
    parallelism = $Parallelism
    batch_size = $BatchSize
    ludii_version = $config.ludii_version
    ludii_jar_sha256 = (Get-FileHash $LudiiJar -Algorithm SHA256).Hash.ToLowerInvariant()
    game_sha256 = (Get-FileHash $game -Algorithm SHA256).Hash.ToLowerInvariant()
    runner_sha256 = (Get-FileHash $runner -Algorithm SHA256).Hash.ToLowerInvariant()
}
$environment | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $root 'environment-run.json') -Encoding UTF8
Write-Host "Generated $($rows.Count) games in $root"
