[CmdletBinding()]
param(
    [string]$ResultsPath = '',
    [string]$ConfigPath = ''
)

$ErrorActionPreference = 'Stop'
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$issueRoot = [System.IO.Path]::GetFullPath((Join-Path $scriptDirectory '..'))
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $issueRoot '..\..'))
if ([string]::IsNullOrWhiteSpace($ConfigPath)) {
    $ConfigPath = Join-Path $issueRoot 'config.json'
}
$configPath = [System.IO.Path]::GetFullPath($ConfigPath)
if ([string]::IsNullOrWhiteSpace($ResultsPath)) {
    $ResultsPath = Join-Path $issueRoot 'results'
}
$resultsPath = [System.IO.Path]::GetFullPath($ResultsPath)
$rawPath = Join-Path $resultsPath 'raw'
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$rawFiles = @(Get-ChildItem -LiteralPath $rawPath -Filter '*.csv' -File | Sort-Object Name)
if ($rawFiles.Count -eq 0) {
    throw "No raw result CSV files found in $rawPath"
}

$rows = @($rawFiles | ForEach-Object { Import-Csv -LiteralPath $_.FullName })
if ($rows.Count -eq 0) {
    throw 'Raw result files contain no games.'
}

$configById = @{}
foreach ($experiment in $config.experiments) {
    $configById[[string]$experiment.id] = $experiment
}

$seenSeeds = @{}
$seenGameKeys = @{}
$trialFilesVerified = 0
foreach ($row in $rows) {
    if (-not $configById.ContainsKey($row.experiment_id)) {
        throw "Unexpected experiment id: $($row.experiment_id)"
    }
    $experiment = $configById[$row.experiment_id]
    if ([int]$row.iteration_limit -ne [int]$experiment.iteration_limit) {
        throw "Iteration limit mismatch: $($row.experiment_id) #$($row.game_index)"
    }
    if ($row.completed -ne 'true' -or $row.end_type -ne 'NaturalEnd') {
        throw "Incomplete or non-natural game: $($row.experiment_id) #$($row.game_index)"
    }
    if ([int]$row.moves -ne 72 -or [int]$row.turns -ne 24) {
        throw "Move or turn invariant failed: $($row.experiment_id) #$($row.game_index)"
    }
    if ([int]$row.p1_total_pieces -ne 36 -or [int]$row.p2_total_pieces -ne 36) {
        throw "Piece invariant failed: $($row.experiment_id) #$($row.game_index)"
    }

    $calculatedP1 = 629 * [int]$row.p1_secured_objectives + 37 * [int]$row.p1_advantage_objectives + [int]$row.p1_objective_pieces
    $calculatedP2 = 629 * [int]$row.p2_secured_objectives + 37 * [int]$row.p2_advantage_objectives + [int]$row.p2_objective_pieces
    if ($calculatedP1 -ne [int]$row.p1_score -or $calculatedP2 -ne [int]$row.p2_score) {
        throw "Score invariant failed: $($row.experiment_id) #$($row.game_index)"
    }
    $expectedWinner = if ($calculatedP1 -gt $calculatedP2) { 1 } elseif ($calculatedP2 -gt $calculatedP1) { 2 } else { 0 }
    if ($expectedWinner -ne [int]$row.winner) {
        throw "Winner invariant failed: $($row.experiment_id) #$($row.game_index)"
    }

    $boardEntries = @($row.final_board -split '\|')
    if ($boardEntries.Count -ne 41) {
        throw "Final board does not contain 41 sites: $($row.experiment_id) #$($row.game_index)"
    }
    $seedKey = [string]$row.seed
    if ($seenSeeds.ContainsKey($seedKey)) {
        throw "Duplicate seed: $seedKey"
    }
    $seenSeeds[$seedKey] = $true
    $gameKey = "$($row.experiment_id)|$($row.game_index)"
    if ($seenGameKeys.ContainsKey($gameKey)) {
        throw "Duplicate experiment game index: $gameKey"
    }
    $seenGameKeys[$gameKey] = $true

    $trialPath = Join-Path $repoRoot ($row.trial_file -replace '/', '\')
    if (-not (Test-Path -LiteralPath $trialPath -PathType Leaf)) {
        throw "Trial file not found: $($row.trial_file)"
    }
    ++$trialFilesVerified
}

foreach ($experiment in $config.experiments) {
    $actual = @($rows | Where-Object experiment_id -eq ([string]$experiment.id)).Count
    if ($actual -ne [int]$experiment.games) {
        throw "Game count mismatch for $($experiment.id): expected $($experiment.games), found $actual"
    }
}

function Get-Average([object[]]$Items, [string]$Property) {
    return [Math]::Round(($Items | Measure-Object -Property $Property -Average).Average, 3)
}

function Get-WilsonInterval([int]$Successes, [int]$Total) {
    $z = 1.959963984540054
    $p = $Successes / [double]$Total
    $denominator = 1.0 + ($z * $z / $Total)
    $centre = ($p + ($z * $z / (2.0 * $Total))) / $denominator
    $margin = ($z / $denominator) * [Math]::Sqrt(($p * (1.0 - $p) / $Total) + ($z * $z / (4.0 * $Total * $Total)))
    return @([Math]::Round(100.0 * ($centre - $margin), 2), [Math]::Round(100.0 * ($centre + $margin), 2))
}

function Get-PearsonCorrelation([double[]]$Left, [double[]]$Right) {
    if ($Left.Count -ne $Right.Count -or $Left.Count -eq 0) {
        throw 'Correlation vectors must have the same non-zero length.'
    }
    $leftMean = ($Left | Measure-Object -Average).Average
    $rightMean = ($Right | Measure-Object -Average).Average
    $numerator = 0.0
    $leftSquares = 0.0
    $rightSquares = 0.0
    for ($index = 0; $index -lt $Left.Count; ++$index) {
        $leftDelta = $Left[$index] - $leftMean
        $rightDelta = $Right[$index] - $rightMean
        $numerator += $leftDelta * $rightDelta
        $leftSquares += $leftDelta * $leftDelta
        $rightSquares += $rightDelta * $rightDelta
    }
    if ($leftSquares -eq 0.0 -or $rightSquares -eq 0.0) {
        return 0.0
    }
    return [Math]::Round($numerator / [Math]::Sqrt($leftSquares * $rightSquares), 4)
}

function Get-SiteSamples([object[]]$Games, [string]$SiteName) {
    return @($Games | ForEach-Object {
        $game = $_
        $entry = @($game.final_board -split '\|' | Where-Object { $_ -like "$SiteName`:*" })
        if ($entry.Count -ne 1) {
            throw "Missing final state for $SiteName in $($game.experiment_id) #$($game.game_index)"
        }
        $parts = $entry[0] -split ':'
        [pscustomobject]@{
            state = [int]$parts[1]
            p1 = [int]$parts[2]
            p2 = [int]$parts[3]
            total = [int]$parts[2] + [int]$parts[3]
        }
    })
}

$summary = @($rows | Group-Object experiment_id | ForEach-Object {
    $games = @($_.Group)
    $p1Wins = @($games | Where-Object { [int]$_.winner -eq 1 }).Count
    $p2Wins = @($games | Where-Object { [int]$_.winner -eq 2 }).Count
    $draws = @($games | Where-Object { [int]$_.winner -eq 0 }).Count
    $interval = Get-WilsonInterval $p1Wins $games.Count
    [pscustomobject][ordered]@{
        experiment_id = $_.Name
        iteration_limit = [int]$games[0].iteration_limit
        games = $games.Count
        p1_wins = $p1Wins
        p2_wins = $p2Wins
        draws = $draws
        p1_win_rate_pct = [Math]::Round(100.0 * $p1Wins / $games.Count, 2)
        p1_win_rate_95ci_low_pct = $interval[0]
        p1_win_rate_95ci_high_pct = $interval[1]
        first_player_win_margin_pct_points = [Math]::Round(100.0 * ($p1Wins - $p2Wins) / $games.Count, 2)
        average_moves = Get-Average $games 'moves'
        average_turns = Get-Average $games 'turns'
        average_p1_secured_objectives = Get-Average $games 'p1_secured_objectives'
        average_p2_secured_objectives = Get-Average $games 'p2_secured_objectives'
        average_p1_advantage_objectives = Get-Average $games 'p1_advantage_objectives'
        average_p2_advantage_objectives = Get-Average $games 'p2_advantage_objectives'
        average_p1_objective_pieces = Get-Average $games 'p1_objective_pieces'
        average_p2_objective_pieces = Get-Average $games 'p2_objective_pieces'
        average_p1_supply_pieces = Get-Average $games 'p1_supply_pieces'
        average_p2_supply_pieces = Get-Average $games 'p2_supply_pieces'
        average_p1_secured_supply = Get-Average $games 'p1_secured_supply'
        average_p2_secured_supply = Get-Average $games 'p2_secured_supply'
    }
} | Sort-Object iteration_limit)
$summary | Export-Csv -LiteralPath (Join-Path $resultsPath 'summary.csv') -NoTypeInformation -Encoding UTF8

$objectiveNames = @(0..15 | ForEach-Object { 'O{0}{1}' -f [Math]::Floor($_ / 4), ($_ % 4) })
$supplyNames = @(0..24 | ForEach-Object { 'S{0}{1}' -f [Math]::Floor($_ / 5), ($_ % 5) })
$siteProfiles = @{}

function New-SiteRows([string[]]$SiteNames, [string]$PointType) {
    return @($rows | Group-Object experiment_id | ForEach-Object {
        $experimentId = $_.Name
        $games = @($_.Group)
        $profile = @()
        foreach ($siteName in $SiteNames) {
            $samples = @(Get-SiteSamples $games $siteName)
            $profile += [double](Get-Average $samples 'total')
            [pscustomobject][ordered]@{
                experiment_id = $experimentId
                iteration_limit = [int]$games[0].iteration_limit
                point = $siteName
                p1_secured_rate_pct = [Math]::Round(100.0 * @($samples | Where-Object state -eq 3).Count / $games.Count, 2)
                p2_secured_rate_pct = [Math]::Round(100.0 * @($samples | Where-Object state -eq 4).Count / $games.Count, 2)
                p1_control_or_advantage_rate_pct = [Math]::Round(100.0 * @($samples | Where-Object state -eq 1).Count / $games.Count, 2)
                p2_control_or_advantage_rate_pct = [Math]::Round(100.0 * @($samples | Where-Object state -eq 2).Count / $games.Count, 2)
                neutral_rate_pct = [Math]::Round(100.0 * @($samples | Where-Object state -eq 0).Count / $games.Count, 2)
                average_p1_pieces = Get-Average $samples 'p1'
                average_p2_pieces = Get-Average $samples 'p2'
                average_total_pieces = Get-Average $samples 'total'
            }
        }
        $siteProfiles["$experimentId|$PointType"] = [double[]]$profile
    })
}

$objectiveRows = New-SiteRows $objectiveNames 'objective'
$supplyRows = New-SiteRows $supplyNames 'supply'
$objectiveRows | Sort-Object iteration_limit, point | Export-Csv -LiteralPath (Join-Path $resultsPath 'objectives.csv') -NoTypeInformation -Encoding UTF8
$supplyRows | Sort-Object iteration_limit, point | Export-Csv -LiteralPath (Join-Path $resultsPath 'supply-points.csv') -NoTypeInformation -Encoding UTF8

$criterionRows = @($rows | Group-Object experiment_id | ForEach-Object {
    $group = $_
    foreach ($criterion in @('secured_objectives', 'advantage_objectives', 'objective_pieces', 'draw')) {
        $count = @($group.Group | Where-Object deciding_criterion -eq $criterion).Count
        [pscustomobject][ordered]@{
            experiment_id = $group.Name
            iteration_limit = [int]$group.Group[0].iteration_limit
            deciding_criterion = $criterion
            games = $count
            rate_pct = [Math]::Round(100.0 * $count / $group.Count, 2)
        }
    }
})
$criterionRows | Sort-Object iteration_limit, deciding_criterion | Export-Csv -LiteralPath (Join-Path $resultsPath 'deciding-criteria.csv') -NoTypeInformation -Encoding UTF8

$strengthComparisons = @()
for ($index = 0; $index -lt $summary.Count - 1; ++$index) {
    $lower = $summary[$index]
    $higher = $summary[$index + 1]
    $lowerObjective = [double[]]$siteProfiles["$($lower.experiment_id)|objective"]
    $higherObjective = [double[]]$siteProfiles["$($higher.experiment_id)|objective"]
    $lowerSupply = [double[]]$siteProfiles["$($lower.experiment_id)|supply"]
    $higherSupply = [double[]]$siteProfiles["$($higher.experiment_id)|supply"]
    $objectiveDifferences = @(for ($site = 0; $site -lt $lowerObjective.Count; ++$site) { [Math]::Abs($higherObjective[$site] - $lowerObjective[$site]) })
    $supplyDifferences = @(for ($site = 0; $site -lt $lowerSupply.Count; ++$site) { [Math]::Abs($higherSupply[$site] - $lowerSupply[$site]) })
    $strengthComparisons += [pscustomobject][ordered]@{
        lower_iteration_limit = $lower.iteration_limit
        higher_iteration_limit = $higher.iteration_limit
        p1_win_rate_delta_pct_points = [Math]::Round([double]$higher.p1_win_rate_pct - [double]$lower.p1_win_rate_pct, 2)
        average_secured_objectives_per_player_delta = [Math]::Round((([double]$higher.average_p1_secured_objectives + [double]$higher.average_p2_secured_objectives) - ([double]$lower.average_p1_secured_objectives + [double]$lower.average_p2_secured_objectives)) / 2.0, 3)
        average_objective_pieces_per_player_delta = [Math]::Round((([double]$higher.average_p1_objective_pieces + [double]$higher.average_p2_objective_pieces) - ([double]$lower.average_p1_objective_pieces + [double]$lower.average_p2_objective_pieces)) / 2.0, 3)
        objective_usage_profile_correlation = Get-PearsonCorrelation $lowerObjective $higherObjective
        objective_usage_mean_absolute_change = [Math]::Round(($objectiveDifferences | Measure-Object -Average).Average, 4)
        supply_usage_profile_correlation = Get-PearsonCorrelation $lowerSupply $higherSupply
        supply_usage_mean_absolute_change = [Math]::Round(($supplyDifferences | Measure-Object -Average).Average, 4)
    }
}
$strengthComparisons | Export-Csv -LiteralPath (Join-Path $resultsPath 'strength-comparison.csv') -NoTypeInformation -Encoding UTF8

$analysis = [ordered]@{
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    games = $rows.Count
    experiment_groups = @($config.experiments).Count
    validation = [ordered]@{
        completed_natural_end = $rows.Count
        moves_72_turns_24 = $rows.Count
        piece_totals_36_each = $rows.Count
        scores_verified = $rows.Count
        winners_verified = $rows.Count
        final_boards_41_sites = $rows.Count
        unique_seeds = $seenSeeds.Count
        unique_experiment_game_indices = $seenGameKeys.Count
        trial_files_verified = $trialFilesVerified
    }
}
$analysis | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $resultsPath 'analysis.json') -Encoding UTF8

Write-Host "Validated and analyzed $($rows.Count) games across $(@($config.experiments).Count) UCT strengths."
