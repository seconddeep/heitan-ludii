[CmdletBinding()]
param(
    [string]$LudiiJar = $env:LUDII_JAR,
    [string]$ConfigPath = '',
    [switch]$MetadataOnly
)

$ErrorActionPreference = 'Stop'
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $scriptDirectory '..\config.json'
}
$issueRoot = [System.IO.Path]::GetFullPath((Join-Path $scriptDirectory '..'))
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $issueRoot '..\..'))
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
    throw "This runner is validated against Ludii 1.3.14, not $($config.ludii_version)."
}

$gamePath = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $config.game))
$resultsPath = Join-Path $issueRoot 'results'
$rawPath = Join-Path $resultsPath 'raw'
$trialsPath = Join-Path $resultsPath 'trials'
New-Item -ItemType Directory -Force -Path $rawPath, $trialsPath | Out-Null

if (-not $MetadataOnly) {
    # Java source-file mode compiles the runner in memory and avoids leaving
    # generated class files in the repository.
    $sourcePath = Join-Path $scriptDirectory 'HeitanExperiment.java'
    $experimentOffset = 0L
    foreach ($experiment in $config.experiments) {
        $experimentId = [string]$experiment.id
        $outputFile = Join-Path $rawPath "$experimentId.csv"
        $experimentTrials = Join-Path $trialsPath $experimentId
        New-Item -ItemType Directory -Force -Path $experimentTrials | Out-Null
        $experimentSeed = [long]$config.base_seed + $experimentOffset

        & java -cp $LudiiJar $sourcePath `
            $gamePath `
            $experimentId `
            ([string]$experiment.black_agent) `
            ([string]$experiment.white_agent) `
            ([int]$experiment.games) `
            $experimentSeed `
            ([int]$experiment.iteration_limit) `
            ([double]$experiment.max_seconds_per_move) `
            $outputFile `
            $experimentTrials
        if ($LASTEXITCODE -ne 0) {
            throw "Experiment '$experimentId' failed with exit code $LASTEXITCODE"
        }

        $experimentOffset += [long]$experiment.games
    }
}

$gitCommit = (& git -c "safe.directory=$($repoRoot.Replace('\', '/'))" -C $repoRoot rev-parse HEAD).Trim()
$javaVersion = (& java --version | Select-Object -First 1).ToString()
$environment = [ordered]@{
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    config = 'experiments/issue-11/config.json'
    config_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $configPath).Hash.ToLowerInvariant()
    runner_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $scriptDirectory 'HeitanExperiment.java')).Hash.ToLowerInvariant()
    run_script_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $MyInvocation.MyCommand.Path).Hash.ToLowerInvariant()
    analysis_script_sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $scriptDirectory 'analyze-results.ps1')).Hash.ToLowerInvariant()
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
