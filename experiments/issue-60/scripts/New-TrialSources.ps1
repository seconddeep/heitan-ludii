[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$issue = [IO.Path]::GetFullPath((Join-Path $scriptDir '..'))
$repo = [IO.Path]::GetFullPath((Join-Path $issue '..\..'))
$config = Get-Content -Raw (Join-Path $issue 'config.json') | ConvertFrom-Json
$results = Join-Path $issue 'results'
New-Item -ItemType Directory -Force -Path $results | Out-Null
$manifest = @()

foreach ($source in $config.analysis_sources) {
    $trialRoot = Join-Path $repo $source.trial_root
    $trials = @(Get-ChildItem $trialRoot -Filter '*.trl' -File | Sort-Object Name)
    if ($trials.Count -ne [int]$source.games) {
        throw "Unexpected trial count for source issue $($source.source_issue): $($trials.Count), expected $($source.games)"
    }

    $csvFiles = @(Get-ChildItem (Join-Path $repo (Split-Path $source.runner_csv_glob -Parent)) -Filter (Split-Path $source.runner_csv_glob -Leaf) -File)
    if (-not $csvFiles.Count) { throw "No runner CSV files for source issue $($source.source_issue)" }
    $runnerRows = @($csvFiles | ForEach-Object { Import-Csv $_.FullName } | Where-Object { $_.experiment_id -eq $source.id })
    if ($runnerRows.Count -ne [int]$source.games) {
        throw "Unexpected runner row count for source issue $($source.source_issue): $($runnerRows.Count), expected $($source.games)"
    }
    $runnerByIndex = @{}
    foreach ($row in $runnerRows) {
        $index = [int]$row.game_index
        if ($runnerByIndex.ContainsKey($index)) { throw "Duplicate runner index $index for source issue $($source.source_issue)" }
        $runnerByIndex[$index] = $row
    }

    $indices = @()
    $seeds = @()
    foreach ($trial in $trials) {
        if ($trial.Name -notmatch '-(\d{4})\.trl$') { throw "No game index in $($trial.FullName)" }
        $index = [int]$Matches[1]
        if (-not $runnerByIndex.ContainsKey($index)) { throw "No runner row for $($trial.FullName)" }
        $row = $runnerByIndex[$index]
        $seed = [long]$row.seed
        if ($row.completed -ne 'true' -or $row.end_type -ne 'NaturalEnd') { throw "Incomplete runner row for $($trial.FullName)" }
        if ([int]$row.iteration_limit -ne [int]$source.iteration_limit) { throw "Iteration mismatch for $($trial.FullName)" }
        if ($index -lt [int]$source.index_first -or $index -gt [int]$source.index_last) { throw "Index outside configured range: $index" }
        if ($seed -lt [long]$source.seed_first -or $seed -gt [long]$source.seed_last) { throw "Seed outside configured range: $seed" }
        $indices += $index
        $seeds += $seed
        $relativeTrial = $trial.FullName.Replace('\','/').Substring($repo.Replace('\','/').Length + 1)
        $manifest += [pscustomobject][ordered]@{
            board = $source.board
            experiment_id = $source.id
            game_index = $index
            seed = $seed
            source_issue = [int]$source.source_issue
            trial_file = $relativeTrial
            trial_sha256 = (Get-FileHash $trial.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    $expectedIndices = ([int]$source.index_first)..([int]$source.index_last)
    $expectedSeeds = ([long]$source.seed_first)..([long]$source.seed_last)
    if ((Compare-Object $expectedIndices @($indices | Sort-Object)).Count) { throw "Index gap for source issue $($source.source_issue)" }
    if ((Compare-Object $expectedSeeds @($seeds | Sort-Object)).Count) { throw "Seed gap for source issue $($source.source_issue)" }
}

if ($manifest.Count -ne ($config.analysis_sources | Measure-Object games -Sum).Sum) { throw 'Manifest total differs from configured total.' }
$duplicateKeys = @($manifest | Group-Object board, experiment_id, game_index | Where-Object Count -ne 1)
if ($duplicateKeys.Count) { throw 'Duplicate analysis game key across source issues.' }
$duplicateTrials = @($manifest | Group-Object trial_sha256 | Where-Object Count -ne 1)
if ($duplicateTrials.Count) { throw 'Duplicate trial content across source issues.' }
$manifest | Sort-Object board, experiment_id, game_index | Export-Csv (Join-Path $results 'trial-sources.csv') -NoTypeInformation -Encoding UTF8
Write-Host "Recorded provenance for $($manifest.Count) trials"
