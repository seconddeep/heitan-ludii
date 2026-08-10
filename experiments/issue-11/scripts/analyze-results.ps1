[CmdletBinding()]
param(
    [string]$ResultsPath = ''
)

$ErrorActionPreference = 'Stop'
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($ResultsPath)) {
    $ResultsPath = Join-Path $scriptDirectory '..\results'
}
$resultsPath = [System.IO.Path]::GetFullPath($ResultsPath)
$rawPath = Join-Path $resultsPath 'raw'
$rawFiles = @(Get-ChildItem -LiteralPath $rawPath -Filter '*.csv' -File | Sort-Object Name)
if ($rawFiles.Count -eq 0) {
    throw "No raw result CSV files found in $rawPath"
}

$rows = @($rawFiles | ForEach-Object { Import-Csv -LiteralPath $_.FullName })
if ($rows.Count -eq 0) {
    throw 'Raw result files contain no games.'
}

foreach ($row in $rows) {
    if ($row.completed -ne 'true') {
        throw "Incomplete game: $($row.experiment_id) #$($row.game_index)"
    }
    if ([int]$row.moves -ne 72 -or [int]$row.p1_total_pieces -ne 36 -or [int]$row.p2_total_pieces -ne 36) {
        throw "Piece or move invariant failed: $($row.experiment_id) #$($row.game_index)"
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

$summary = foreach ($group in ($rows | Group-Object experiment_id)) {
    $games = @($group.Group)
    $p1Wins = @($games | Where-Object { [int]$_.winner -eq 1 }).Count
    $p2Wins = @($games | Where-Object { [int]$_.winner -eq 2 }).Count
    $draws = @($games | Where-Object { [int]$_.winner -eq 0 }).Count
    $interval = Get-WilsonInterval $p1Wins $games.Count
    [pscustomobject][ordered]@{
        experiment_id = $group.Name
        games = $games.Count
        p1_wins = $p1Wins
        p2_wins = $p2Wins
        draws = $draws
        p1_win_rate_pct = [Math]::Round(100.0 * $p1Wins / $games.Count, 2)
        p1_win_rate_95ci_low_pct = $interval[0]
        p1_win_rate_95ci_high_pct = $interval[1]
        average_moves = Get-Average $games 'moves'
        average_turns = Get-Average $games 'turns'
        average_p1_score = Get-Average $games 'p1_score'
        average_p2_score = Get-Average $games 'p2_score'
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
        decided_by_secured = @($games | Where-Object deciding_criterion -eq 'secured_objectives').Count
        decided_by_advantage = @($games | Where-Object deciding_criterion -eq 'advantage_objectives').Count
        decided_by_objective_pieces = @($games | Where-Object deciding_criterion -eq 'objective_pieces').Count
    }
}
$summary | Export-Csv -LiteralPath (Join-Path $resultsPath 'summary.csv') -NoTypeInformation -Encoding UTF8

$objectiveRows = foreach ($group in ($rows | Group-Object experiment_id)) {
    $games = @($group.Group)
    foreach ($siteNumber in 0..15) {
        $siteName = 'O{0}{1}' -f [Math]::Floor($siteNumber / 4), ($siteNumber % 4)
        $states = foreach ($game in $games) {
            $entry = @($game.final_board -split '\|' | Where-Object { $_ -like "$siteName`:*" })
            if ($entry.Count -ne 1) {
                throw "Missing final state for $siteName in $($game.experiment_id) #$($game.game_index)"
            }
            $parts = $entry[0] -split ':'
            [pscustomobject]@{ state = [int]$parts[1]; p1 = [int]$parts[2]; p2 = [int]$parts[3] }
        }
        [pscustomobject][ordered]@{
            experiment_id = $group.Name
            objective = $siteName
            p1_secured_rate_pct = [Math]::Round(100.0 * @($states | Where-Object state -eq 3).Count / $games.Count, 2)
            p2_secured_rate_pct = [Math]::Round(100.0 * @($states | Where-Object state -eq 4).Count / $games.Count, 2)
            p1_advantage_rate_pct = [Math]::Round(100.0 * @($states | Where-Object state -eq 1).Count / $games.Count, 2)
            p2_advantage_rate_pct = [Math]::Round(100.0 * @($states | Where-Object state -eq 2).Count / $games.Count, 2)
            neutral_rate_pct = [Math]::Round(100.0 * @($states | Where-Object state -eq 0).Count / $games.Count, 2)
            average_p1_pieces = Get-Average $states 'p1'
            average_p2_pieces = Get-Average $states 'p2'
        }
    }
}
$objectiveRows | Export-Csv -LiteralPath (Join-Path $resultsPath 'objectives.csv') -NoTypeInformation -Encoding UTF8

$criterionRows = foreach ($group in ($rows | Group-Object experiment_id)) {
    foreach ($criterion in @('secured_objectives', 'advantage_objectives', 'objective_pieces', 'draw')) {
        $count = @($group.Group | Where-Object deciding_criterion -eq $criterion).Count
        [pscustomobject]@{
            experiment_id = $group.Name
            deciding_criterion = $criterion
            games = $count
            rate_pct = [Math]::Round(100.0 * $count / $group.Count, 2)
        }
    }
}
$criterionRows | Export-Csv -LiteralPath (Join-Path $resultsPath 'deciding-criteria.csv') -NoTypeInformation -Encoding UTF8

$analysis = [ordered]@{
    generated_at_utc = [DateTime]::UtcNow.ToString('o')
    games = $rows.Count
    validation = [ordered]@{
        completed = $rows.Count
        natural_end = @($rows | Where-Object end_type -eq 'NaturalEnd').Count
        moves_72 = @($rows | Where-Object { [int]$_.moves -eq 72 }).Count
        piece_totals_36_each = @($rows | Where-Object { [int]$_.p1_total_pieces -eq 36 -and [int]$_.p2_total_pieces -eq 36 }).Count
        scores_verified = $rows.Count
        winners_verified = $rows.Count
    }
}
$analysis | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $resultsPath 'analysis.json') -Encoding UTF8

Write-Host "Validated and analyzed $($rows.Count) games."
