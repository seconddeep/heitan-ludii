[CmdletBinding()]
param([string]$LudiiJar = 'C:\Users\verti\Ludii-1.3.14.jar')
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
$results = Join-Path $issue 'results'
$raw = Join-Path $results 'raw'
New-Item -ItemType Directory -Force -Path $raw | Out-Null
$games = Join-Path $raw 'games.csv'
$placements = Join-Path $raw 'placements.csv'
$states = Join-Path $raw 'turn-states.csv'
$runner = Join-Path $scriptDir 'HeitanScaleReplay.java'
$game = Join-Path $repo $config.game
$started = [DateTime]::UtcNow

for ($i = 0; $i -lt $config.analysis_sources.Count; $i++) {
    $source = $config.analysis_sources[$i]
    $trialRoot = Join-Path $repo $source.trial_root
    $actual = @(Get-ChildItem $trialRoot -Filter '*.trl' -File).Count
    if ($actual -ne [int]$source.games) {
        throw "Unexpected trial count for $($source.trial_root): $actual, expected $($source.games)"
    }
    & java -cp $LudiiJar $runner $game $source.board $source.id $source.iteration_limit $trialRoot $games $placements $states ($i -gt 0).ToString().ToLowerInvariant()
    if ($LASTEXITCODE) { throw "Replay failed: $($source.id) from $($source.trial_root)" }
}

$gameRows = @(Import-Csv $games)
$duplicates = @($gameRows | Group-Object board, experiment_id, game_index | Where-Object Count -ne 1)
if ($duplicates.Count) { throw 'Duplicate analyzed game key.' }
$expectedGames = ($config.analysis_sources | Measure-Object games -Sum).Sum
if ($gameRows.Count -ne $expectedGames) { throw "Unexpected analyzed game count: $($gameRows.Count), expected $expectedGames" }

& node --test (Join-Path $scriptDir 'analyze-scale.test.mjs')
if ($LASTEXITCODE) { throw 'Analysis tests failed.' }
& node (Join-Path $scriptDir 'analyze-scale.mjs')
if ($LASTEXITCODE) { throw 'Analysis failed.' }

$environment = [ordered]@{
    schema_version = 1
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    elapsed_seconds = [Math]::Round(([DateTime]::UtcNow - $started).TotalSeconds, 3)
    ludii_version = $config.ludii_version
    ludii_jar_sha256 = (Get-FileHash $LudiiJar -Algorithm SHA256).Hash.ToLowerInvariant()
    config_sha256 = (Get-FileHash (Join-Path $issue 'config.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    game_sha256 = (Get-FileHash $game -Algorithm SHA256).Hash.ToLowerInvariant()
    replay_sha256 = (Get-FileHash $runner -Algorithm SHA256).Hash.ToLowerInvariant()
    analysis_sha256 = (Get-FileHash (Join-Path $scriptDir 'analyze-scale.mjs') -Algorithm SHA256).Hash.ToLowerInvariant()
    frozen_analysis_sha256 = (Get-FileHash (Join-Path $repo 'experiments/issue-56/scripts/analyze-scale.mjs') -Algorithm SHA256).Hash.ToLowerInvariant()
    git_commit = (& git -c "safe.directory=$($repo.Replace('\','/'))" -C $repo rev-parse HEAD).Trim()
    java = (& java --version | Select-Object -First 1)
    node = (& node --version)
}
$environment | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $results 'environment.json') -Encoding UTF8
