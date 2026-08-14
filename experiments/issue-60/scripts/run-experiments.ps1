[CmdletBinding()]
param(
    [string]$LudiiJar = 'C:\Users\verti\Ludii-1.3.14.jar',
    [ValidateRange(1, 16)][int]$Parallelism = 1,
    [ValidateRange(1, 30)][int]$BatchSize = 5,
    [switch]$Resume,
    [switch]$FinalizeOnly
)
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$issue = [IO.Path]::GetFullPath((Join-Path $scriptDir '..'))
$repo = [IO.Path]::GetFullPath((Join-Path $issue '..\..'))
$config = Get-Content -Raw (Join-Path $issue 'config.json') | ConvertFrom-Json
$experiment = $config.experiment

foreach ($name in @('analyze-scale.mjs', 'analyze-scale.test.mjs', 'HeitanScaleReplay.java')) {
    $source = Join-Path $repo "$($config.frozen_analysis_source)/scripts/$name"
    $copy = Join-Path $scriptDir $name
    if ((Get-FileHash $source -Algorithm SHA256).Hash -ne (Get-FileHash $copy -Algorithm SHA256).Hash) {
        throw "Frozen Issue 56 analysis source differs: $name"
    }
}

$results = Join-Path $issue 'results'
$raw = Join-Path $results 'raw'
$trials = Join-Path $results "trials/$($experiment.id)"
New-Item -ItemType Directory -Force -Path $raw, $trials | Out-Null
$runner = Join-Path $scriptDir 'Heitan6x6Experiment.java'
$game = Join-Path $repo $config.game

if (-not $FinalizeOnly) {
    $tasks = @()
    $count = [int]$experiment.games
    if ($Resume) {
        $existingRows = @(Get-ChildItem $raw -Filter "$($experiment.id)-batch-*.csv" -File -ErrorAction SilentlyContinue | ForEach-Object { Import-Csv $_.FullName })
        if (@($existingRows.game_index | Sort-Object -Unique).Count -ne $existingRows.Count) { throw 'Duplicate indices in resumable runner data.' }
        $existingIndices = @($existingRows.game_index | ForEach-Object { [int]$_ })
        for ($number = [int]$experiment.index_offset + 1; $number -le [int]$experiment.index_offset + $count; $number++) {
            if ($number -notin $existingIndices) {
                $tasks += [pscustomobject]@{
                    games = 1
                    seed = [long]$experiment.base_seed + $number - [int]$experiment.index_offset - 1
                    offset = $number - 1
                    raw = Join-Path $raw ('{0}-batch-resume-{1:D4}.csv' -f $experiment.id, $number)
                }
            }
        }
    } else {
        Get-ChildItem $trials -Filter '*.trl' -File -ErrorAction SilentlyContinue | Remove-Item -Force
        Get-ChildItem $raw -Filter "$($experiment.id)-batch-*.csv" -File -ErrorAction SilentlyContinue | Remove-Item -Force
        $effectiveBatchSize = if ($Parallelism -eq 1) { $count } else { $BatchSize }
        for ($offset = 0; $offset -lt $count; $offset += $effectiveBatchSize) {
            $size = [Math]::Min($effectiveBatchSize, $count - $offset)
            $tasks += [pscustomobject]@{
                games = $size
                seed = [long]$experiment.base_seed + $offset
                offset = [int]$experiment.index_offset + $offset
                raw = Join-Path $raw ('{0}-batch-{1:D3}.csv' -f $experiment.id, ([int]($offset / $effectiveBatchSize) + 1))
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
            $arguments = @('-cp', $LudiiJar, $runner, $game, $experiment.id, $experiment.agent,
                $task.games, $task.seed, $experiment.iteration_limit, $task.raw, $trials, $repo, $task.offset)
            $process = Start-Process -FilePath java -ArgumentList $arguments -NoNewWindow -PassThru
            $running += [pscustomobject]@{ process = $process; task = $task }
        }
        do {
            Start-Sleep -Milliseconds 500
            $done = @($running | Where-Object { $_.process.HasExited })
        } while (-not $done.Count)
        foreach ($item in $done) {
            if ($item.process.ExitCode) { throw "Experiment process $($item.process.Id) exited $($item.process.ExitCode)" }
        }
        $doneIds = @($done.process.Id)
        $running = @($running | Where-Object { $_.process.Id -notin $doneIds })
    }
} else {
    $firstTrial = Get-ChildItem $trials -Filter '*.trl' -File | Sort-Object CreationTimeUtc | Select-Object -First 1
    if (-not $firstTrial) { throw 'No Issue 60 trials to finalize.' }
    $started = $firstTrial.CreationTimeUtc
}

$rows = @(Get-ChildItem $raw -Filter "$($experiment.id)-batch-*.csv" -File | ForEach-Object { Import-Csv $_.FullName })
if ($rows.Count -ne [int]$experiment.games) { throw "Unexpected game count: $($rows.Count)" }
if (@($rows.seed | Sort-Object -Unique).Count -ne $rows.Count) { throw 'Duplicate seeds.' }
$expectedIndices = ([int]$experiment.index_offset + 1)..([int]$experiment.index_offset + [int]$experiment.games)
$expectedSeeds = [long]$experiment.base_seed..([long]$experiment.base_seed + [int]$experiment.games - 1)
if ((Compare-Object $expectedIndices @($rows.game_index | ForEach-Object { [int]$_ } | Sort-Object)).Count) { throw 'Unexpected game-index range.' }
if ((Compare-Object $expectedSeeds @($rows.seed | ForEach-Object { [long]$_ } | Sort-Object)).Count) { throw 'Unexpected seed range.' }
if (@($rows | Where-Object { $_.completed -ne 'true' -or $_.end_type -ne 'NaturalEnd' -or [int]$_.moves -ne 144 -or [int]$_.turns -ne 48 }).Count) {
    throw 'At least one generated trial is incomplete or has unexpected dimensions.'
}

$environment = [ordered]@{
    schema_version = 1
    source_issue = 60
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    elapsed_seconds = [Math]::Round(([DateTime]::UtcNow - $started).TotalSeconds, 3)
    games = $rows.Count
    experiment = $experiment.id
    index_first = ($rows.game_index | Measure-Object -Minimum).Minimum
    index_last = ($rows.game_index | Measure-Object -Maximum).Maximum
    seed_first = ($rows.seed | Measure-Object -Minimum).Minimum
    seed_last = ($rows.seed | Measure-Object -Maximum).Maximum
    parallelism = $Parallelism
    batch_size = $BatchSize
    resumed = $Resume.IsPresent
    ludii_version = $config.ludii_version
    ludii_jar_sha256 = (Get-FileHash $LudiiJar -Algorithm SHA256).Hash.ToLowerInvariant()
    game_sha256 = (Get-FileHash $game -Algorithm SHA256).Hash.ToLowerInvariant()
    runner_sha256 = (Get-FileHash $runner -Algorithm SHA256).Hash.ToLowerInvariant()
}
$environment | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $results 'environment-run.json') -Encoding UTF8
Write-Host "Generated and validated $($rows.Count) Issue 60 games"
