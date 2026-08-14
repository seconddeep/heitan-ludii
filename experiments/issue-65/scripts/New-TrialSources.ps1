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
        throw "Unexpected trial count for issue $($source.source_issue)/$($source.id): $($trials.Count)"
    }

    $glob = Join-Path $repo $source.runner_csv_glob
    $csvFiles = @(Get-ChildItem (Split-Path $glob -Parent) -Filter (Split-Path $glob -Leaf) -File)
    if (-not $csvFiles.Count) { throw "No runner CSV for issue $($source.source_issue)/$($source.id)" }
    $rows = @($csvFiles | ForEach-Object { Import-Csv $_.FullName } | Where-Object experiment_id -eq $source.id)
    if ($rows.Count -ne [int]$source.games) {
        throw "Unexpected runner rows for issue $($source.source_issue)/$($source.id): $($rows.Count)"
    }
    $byIndex = @{}
    foreach ($row in $rows) {
        $index = [int]$row.game_index
        if ($byIndex.ContainsKey($index)) { throw "Duplicate runner index $index" }
        $byIndex[$index] = $row
    }

    $indices = @()
    $seeds = @()
    foreach ($trial in $trials) {
        if ($trial.Name -notmatch '-(\d{4})\.trl$') { throw "No index in $($trial.Name)" }
        $index = [int]$Matches[1]
        if (-not $byIndex.ContainsKey($index)) { throw "No runner row for $($trial.Name)" }
        $row = $byIndex[$index]
        $seed = [long]$row.seed
        if ($row.completed -ne 'true' -or $row.end_type -ne 'NaturalEnd') { throw "Incomplete row for $($trial.Name)" }
        if ([int]$row.iteration_limit -ne [int]$source.iteration_limit) { throw "Iteration mismatch for $($trial.Name)" }
        $indices += $index
        $seeds += $seed
        $relative = $trial.FullName.Replace('\','/').Substring($repo.Replace('\','/').Length + 1)
        $manifest += [pscustomobject][ordered]@{
            board = $source.board
            experiment_id = $source.id
            search_level = $source.search_level
            game_index = $index
            seed = $seed
            source_issue = [int]$source.source_issue
            trial_file = $relative
            trial_sha256 = (Get-FileHash $trial.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    if ((Compare-Object (([int]$source.index_first)..([int]$source.index_last)) @($indices | Sort-Object)).Count) {
        throw "Index gap for issue $($source.source_issue)/$($source.id)"
    }
    if ((Compare-Object (([long]$source.seed_first)..([long]$source.seed_last)) @($seeds | Sort-Object)).Count) {
        throw "Seed gap for issue $($source.source_issue)/$($source.id)"
    }
}

if ($manifest.Count -ne ($config.analysis_sources | Measure-Object games -Sum).Sum) { throw 'Manifest total mismatch' }
if (@($manifest | Group-Object board, experiment_id, game_index | Where-Object Count -ne 1).Count) { throw 'Duplicate game keys' }
if (@($manifest | Group-Object seed | Where-Object Count -ne 1).Count) { throw 'Duplicate seeds' }
if (@($manifest | Group-Object trial_sha256 | Where-Object Count -ne 1).Count) { throw 'Duplicate trial hashes' }
$manifest | Sort-Object board, experiment_id, game_index | Export-Csv (Join-Path $results 'trial-sources.csv') -NoTypeInformation -Encoding UTF8
Write-Host "Recorded provenance for $($manifest.Count) trials"
