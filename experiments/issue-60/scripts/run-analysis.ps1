[CmdletBinding()]
param([string]$LudiiJar = 'C:\Users\verti\Ludii-1.3.14.jar')
$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$issue = [IO.Path]::GetFullPath((Join-Path $scriptDir '..'))
$repo = [IO.Path]::GetFullPath((Join-Path $issue '..\..'))
$config = Get-Content -Raw (Join-Path $issue 'config.json') | ConvertFrom-Json
$frozen = Join-Path $repo $config.frozen_analysis_source

foreach ($name in @('analyze-scale.mjs', 'analyze-scale.test.mjs', 'HeitanScaleReplay.java')) {
    $source = Join-Path $frozen "scripts/$name"
    $copy = Join-Path $scriptDir $name
    if ((Get-FileHash $source -Algorithm SHA256).Hash -ne (Get-FileHash $copy -Algorithm SHA256).Hash) {
        throw "Frozen Issue 56 analysis source differs: $name"
    }
}

& (Join-Path $scriptDir 'New-TrialSources.ps1')
if ($LASTEXITCODE) { throw 'Trial-source manifest generation failed.' }

$results = Join-Path $issue 'results'
$raw = Join-Path $results 'raw'
New-Item -ItemType Directory -Force -Path $raw | Out-Null
$games = Join-Path $raw 'games.csv'
$placements = Join-Path $raw 'placements.csv'
$states = Join-Path $raw 'turn-states.csv'
$replay = Join-Path $scriptDir 'HeitanScaleReplay.java'
$game = Join-Path $repo $config.game
$started = [DateTime]::UtcNow

Push-Location $issue
try {
    for ($i = 0; $i -lt $config.analysis_sources.Count; $i++) {
        $source = $config.analysis_sources[$i]
        $trialRoot = Join-Path $repo $source.trial_root
        & java -cp $LudiiJar $replay $game $source.board $source.id $source.iteration_limit $trialRoot $games $placements $states ($i -gt 0).ToString().ToLowerInvariant()
        if ($LASTEXITCODE) { throw "Replay failed for source issue $($source.source_issue)" }
    }
} finally {
    Pop-Location
}

$gameRows = @(Import-Csv $games)
$manifestRows = @(Import-Csv (Join-Path $results 'trial-sources.csv'))
$gameKeys = @($gameRows | ForEach-Object { "$($_.board)|$($_.experiment_id)|$([int]$_.game_index)" } | Sort-Object)
$manifestKeys = @($manifestRows | ForEach-Object { "$($_.board)|$($_.experiment_id)|$([int]$_.game_index)" } | Sort-Object)
if ((Compare-Object $gameKeys $manifestKeys).Count) { throw 'Replayed games differ from trial-source manifest.' }
if (@($gameKeys | Group-Object | Where-Object Count -ne 1).Count) { throw 'Duplicate replayed game key.' }

& node --test (Join-Path $scriptDir 'analyze-scale.test.mjs')
if ($LASTEXITCODE) { throw 'Frozen analysis tests failed.' }
& node (Join-Path $scriptDir 'analyze-scale.mjs')
if ($LASTEXITCODE) { throw 'Frozen analysis failed.' }

$environment = [ordered]@{
    schema_version = 1
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    elapsed_seconds = [Math]::Round(([DateTime]::UtcNow - $started).TotalSeconds, 3)
    games = $gameRows.Count
    ludii_version = $config.ludii_version
    ludii_jar_sha256 = (Get-FileHash $LudiiJar -Algorithm SHA256).Hash.ToLowerInvariant()
    config_sha256 = (Get-FileHash (Join-Path $issue 'config.json') -Algorithm SHA256).Hash.ToLowerInvariant()
    game_sha256 = (Get-FileHash $game -Algorithm SHA256).Hash.ToLowerInvariant()
    replay_sha256 = (Get-FileHash $replay -Algorithm SHA256).Hash.ToLowerInvariant()
    analysis_sha256 = (Get-FileHash (Join-Path $scriptDir 'analyze-scale.mjs') -Algorithm SHA256).Hash.ToLowerInvariant()
    frozen_analysis_sha256 = (Get-FileHash (Join-Path $frozen 'scripts/analyze-scale.mjs') -Algorithm SHA256).Hash.ToLowerInvariant()
    trial_sources_sha256 = (Get-FileHash (Join-Path $results 'trial-sources.csv') -Algorithm SHA256).Hash.ToLowerInvariant()
    git_commit = (& git -c "safe.directory=$($repo.Replace('\','/'))" -C $repo rev-parse HEAD).Trim()
    java = (& java --version | Select-Object -First 1)
    node = (& node --version)
}
$environment | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $results 'environment.json') -Encoding UTF8
Write-Host "Replayed and analyzed $($gameRows.Count) games"
