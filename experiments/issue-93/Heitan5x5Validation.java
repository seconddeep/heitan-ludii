package heitan.experiments;

import java.io.File;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.SplittableRandom;
import java.util.TreeSet;

import game.Game;
import game.equipment.other.Regions;
import game.util.graph.Edge;
import main.collections.FastArrayList;
import metadata.graphics.util.MetadataImageInfo;
import other.GameLoader;
import other.context.Context;
import other.move.Move;
import other.state.container.ContainerState;
import other.trial.Trial;

/** Validates the experimental 5x5 Heitan board and shared mechanics. */
public final class Heitan5x5Validation
{
    private static final int SUPPLY_DIM = 6;
    private static final int OBJECTIVE_DIM = 5;
    private static final int SUPPLY_COUNT = 36;
    private static final int OBJECTIVE_COUNT = 25;
    private static final int SITE_COUNT = SUPPLY_COUNT + OBJECTIVE_COUNT;
    private static final int TOTAL_PLACEMENTS = 96;
    private static final int TURNS = 32;
    private static final int PIECES_PER_PLAYER = 48;
    private static final int ADVANTAGE_WEIGHT = 49;
    private static final int SECURED_WEIGHT = 1274;

    private Heitan5x5Validation()
    {
        // Utility class.
    }

    public static void main(final String[] args) throws Exception
    {
        if (args.length < 1 || args.length > 2)
        {
            System.err.println(
                "Usage: Heitan5x5Validation <Heitan.lud> [random-games]"
            );
            System.exit(2);
        }

        final int randomGames = args.length == 2 ? Integer.parseInt(args[1]) : 20;
        if (randomGames < 0)
            throw new IllegalArgumentException("random-games must not be negative.");

        final Game game = load5x5(args[0]);
        validateStructure(game);
        validateScoringWeights();
        validateDeterministicMechanics(game);
        validateRandomGames(game, randomGames);

        System.out.printf(
            "5x5 validation passed: 61 sites, 100 exact Objective edges, "
            + "60 exact Supply-grid lines, shared-mechanics scenario, "
            + "scoring weights, and %d random games.%n",
            randomGames
        );
    }

    private static Game load5x5(final String path) throws Exception
    {
        final File file = new File(path).getCanonicalFile();
        final Game game = GameLoader.loadGameFromFile(
            file, List.of("Board/5x5")
        );
        if (game == null)
            throw new IllegalStateException("Ludii could not compile " + file);
        return game;
    }

    private static void validateStructure(final Game game)
    {
        if (game.board().graph().vertices().size() != SITE_COUNT)
            fail("Expected 61 graph vertices.");
        if (game.board().graph().edges().size() != OBJECTIVE_COUNT * 4)
            fail("Expected 100 Objective-to-Supply edges.");

        final Set<String> actualEdges = new TreeSet<>();
        final int[] degrees = new int[SITE_COUNT];
        for (final Edge edge : game.board().graph().edges())
        {
            final int first = edge.vertexA().id();
            final int second = edge.vertexB().id();
            actualEdges.add(edgeKey(first, second));
            ++degrees[first];
            ++degrees[second];
        }

        final Set<String> expectedEdges = new TreeSet<>();
        for (int row = 0; row < OBJECTIVE_DIM; ++row)
        {
            for (int column = 0; column < OBJECTIVE_DIM; ++column)
            {
                final int objective = objective(row, column);
                final Set<Integer> expectedCorners = Set.of(
                    supply(row, column),
                    supply(row, column + 1),
                    supply(row + 1, column),
                    supply(row + 1, column + 1)
                );
                for (final Integer corner : expectedCorners)
                    expectedEdges.add(edgeKey(objective, corner.intValue()));

                if (degrees[objective] != 4)
                {
                    fail(
                        objectiveName(row, column) + " has degree "
                        + degrees[objective] + " instead of 4."
                    );
                }

                final Set<Integer> actualCorners = neighbours(
                    game, objective
                );
                if (!actualCorners.equals(expectedCorners))
                {
                    fail(
                        objectiveName(row, column) + " connects to "
                        + actualCorners + " instead of " + expectedCorners + "."
                    );
                }
            }
        }
        if (!actualEdges.equals(expectedEdges))
            fail("The complete Objective-to-Supply edge set differs.");

        final Context context = new Context(game, new Trial(game));
        game.start(context);
        final Map<String, int[]> regions = new HashMap<>();
        for (final Regions region : game.equipment().regions())
            regions.put(region.name(), region.eval(context));

        assertRegion(regions, "SupplyPoints", range(0, SUPPLY_COUNT));
        assertRegion(regions, "Objectives", range(SUPPLY_COUNT, SITE_COUNT));
        for (int row = 0; row < SUPPLY_DIM; ++row)
        {
            for (int column = 0; column < SUPPLY_DIM; ++column)
            {
                assertRegion(
                    regions, supplyName(row, column),
                    new int[] {supply(row, column)}
                );
            }
        }
        for (int row = 0; row < OBJECTIVE_DIM; ++row)
        {
            for (int column = 0; column < OBJECTIVE_DIM; ++column)
            {
                assertRegion(
                    regions, objectiveName(row, column),
                    new int[] {objective(row, column)}
                );
            }
        }
        validateSupplyGridLines(game, context);
    }

    private static void validateSupplyGridLines(
        final Game game, final Context context
    )
    {
        final Set<String> expectedLines = new TreeSet<>();
        for (int row = 0; row < SUPPLY_DIM; ++row)
        {
            for (int column = 0; column < OBJECTIVE_DIM; ++column)
            {
                expectedLines.add(edgeKey(
                    supply(row, column), supply(row, column + 1)
                ));
            }
        }
        for (int column = 0; column < SUPPLY_DIM; ++column)
        {
            for (int row = 0; row < OBJECTIVE_DIM; ++row)
            {
                expectedLines.add(edgeKey(
                    supply(row, column), supply(row + 1, column)
                ));
            }
        }

        final Set<String> actualLines = new TreeSet<>();
        final List<MetadataImageInfo> lineItems =
            game.metadata().graphics().drawLines(context);
        for (final MetadataImageInfo item : lineItems)
        {
            final Integer[] line = item.line();
            if (line == null || line.length != 2)
                fail("A Supply grid graphic is not a two-site line.");
            if (!actualLines.add(edgeKey(line[0].intValue(), line[1].intValue())))
                fail("A Supply grid graphic line is duplicated.");
        }
        if (lineItems.size() != 60 || !actualLines.equals(expectedLines))
        {
            fail(
                "Supply grid graphics differ: expected 60 exact adjacent lines, got "
                + lineItems.size() + "."
            );
        }
    }

    private static Set<Integer> neighbours(final Game game, final int site)
    {
        final Set<Integer> result = new TreeSet<>();
        for (final Edge edge : game.board().graph().edges())
        {
            final int first = edge.vertexA().id();
            final int second = edge.vertexB().id();
            if (first == site)
                result.add(Integer.valueOf(second));
            else if (second == site)
                result.add(Integer.valueOf(first));
        }
        return result;
    }

    private static void validateScoringWeights()
    {
        if (ADVANTAGE_WEIGHT <= PIECES_PER_PLAYER)
            fail("Advantage weight does not dominate all Objective Piece differences.");
        if (SECURED_WEIGHT
            <= OBJECTIVE_COUNT * ADVANTAGE_WEIGHT + PIECES_PER_PLAYER)
        {
            fail("Secured weight does not dominate all lower-order differences.");
        }
        if (ADVANTAGE_WEIGHT != PIECES_PER_PLAYER + 1)
            fail("Unexpected Advantage weight.");
        if (SECURED_WEIGHT
            != OBJECTIVE_COUNT * ADVANTAGE_WEIGHT + PIECES_PER_PLAYER + 1)
        {
            fail("Unexpected Secured weight.");
        }
    }

    private static void validateDeterministicMechanics(final Game game)
    {
        final Context context = new Context(game, new Trial(game));
        game.start(context);

        // P1 establishes S00 without receiving its state before placement three.
        applySupply(game, context, supply(0, 0));
        assertMover(context, 1);
        assertState(context, supply(0, 0), 0);
        applySupply(game, context, supply(0, 0));
        assertMover(context, 1);
        assertState(context, supply(0, 0), 0);
        assertUnavailable(game, context, supply(0, 0), -1);
        applySupply(game, context, supply(5, 5));
        assertMover(context, 2);
        assertState(context, supply(0, 0), 1);

        playFillerTurn(game, context, supply(5, 0), supply(5, 1));

        // S00 was Controlled at turn start, but the newly occupied S01 was not.
        applyObjective(game, context, objective(0, 0), supply(0, 0));
        assertMover(context, 1);
        assertState(context, objective(0, 0), 0);
        assertUnavailable(game, context, objective(0, 0), supply(0, 0));
        applySupply(game, context, supply(0, 1));
        assertState(context, supply(0, 1), 0);
        assertUnavailable(game, context, objective(0, 0), supply(0, 1));
        applySupply(game, context, supply(0, 1));
        assertMover(context, 2);
        assertState(context, objective(0, 0), 1);
        assertState(context, supply(0, 1), 1);

        playFillerTurn(game, context, supply(4, 0), supply(4, 1));

        // Supply usage reset, and S01 became usable only on this later turn.
        assertAvailable(game, context, objective(0, 0), supply(0, 0));
        assertAvailable(game, context, objective(0, 0), supply(0, 1));
        applyObjective(game, context, objective(0, 0), supply(0, 0));
        assertState(context, objective(0, 0), 1);
        applyObjective(game, context, objective(0, 0), supply(0, 1));
        assertState(context, objective(0, 0), 1);
        applySupply(game, context, supply(0, 2));
        assertMover(context, 2);
        assertState(context, objective(0, 0), 3);

        playFillerTurn(game, context, supply(3, 0), supply(3, 1));

        // A Secured Objective is closed.
        assertNoObjectiveTarget(game, context, objective(0, 0));

        // Secure S01, then show that it is closed for placement but still Controlled.
        applySupply(game, context, supply(0, 1));
        applySupply(game, context, supply(0, 3));
        applySupply(game, context, supply(0, 3));
        assertMover(context, 2);
        assertState(context, supply(0, 1), 3);

        playFillerTurn(game, context, supply(2, 0), supply(2, 1));

        assertUnavailable(game, context, supply(0, 1), -1);
        assertAvailable(game, context, objective(0, 1), supply(0, 1));

        if (context.trial().numMoves() != 24 || context.trial().numTurns() != 8)
            fail("Deterministic scenario did not preserve three placements per turn.");
    }

    private static void playFillerTurn(
        final Game game,
        final Context context,
        final int doubleTarget,
        final int singleTarget
    )
    {
        final int mover = context.state().mover();
        applySupply(game, context, doubleTarget);
        assertMover(context, mover);
        applySupply(game, context, doubleTarget);
        assertMover(context, mover);
        applySupply(game, context, singleTarget);
        if (context.state().mover() == mover)
            fail("Mover did not change after a three-placement filler turn.");
    }

    private static void validateRandomGames(final Game game, final int gameCount)
    {
        for (int gameIndex = 0; gameIndex < gameCount; ++gameIndex)
        {
            final long seed = 930000L + gameIndex;
            final SplittableRandom random = new SplittableRandom(seed);
            final Context context = new Context(game, new Trial(game));
            game.start(context);

            final Set<Integer> usedSupply = new HashSet<>();
            final Map<Integer, Integer> supplyPlacements = new HashMap<>();
            int[] turnStartStates = states(context);

            while (!context.trial().over())
            {
                final int phase = context.trial().numMoves() % 3;
                final int mover = context.state().mover();
                if (phase == 0)
                {
                    usedSupply.clear();
                    supplyPlacements.clear();
                    turnStartStates = states(context);
                }

                final FastArrayList<Move> legalMoves = game.moves(context).moves();
                if (legalMoves.isEmpty())
                    fail("No legal move before natural end in random game " + gameIndex);
                final Move selected = legalMoves.get(random.nextInt(legalMoves.size()));
                final Decision decision = decision(selected);

                if (decision.supplySource >= 0)
                {
                    final int sourceState = turnStartStates[decision.supplySource];
                    if (sourceState != mover && sourceState != mover + 2)
                        fail("Objective used Supply not Controlled at turn start.");
                    if (!usedSupply.add(Integer.valueOf(decision.supplySource)))
                        fail("A Supply Point was reused in one turn.");
                }
                else
                {
                    final int count = supplyPlacements.merge(
                        Integer.valueOf(decision.target), Integer.valueOf(1),
                        Integer::sum
                    ).intValue();
                    if (count > 2)
                        fail("More than two Pieces were placed on one Supply in a turn.");
                }

                final int[] statesBefore = states(context);
                final int piecesBefore = totalPieces(context);
                game.apply(context, selected);
                if (totalPieces(context) != piecesBefore + 1)
                    fail("A placement did not add exactly one Piece.");

                if (phase < 2)
                {
                    if (context.state().mover() != mover)
                        fail("Mover changed before the third placement.");
                    if (!Arrays.equals(statesBefore, states(context)))
                        fail("Point state changed before the third placement.");
                }
                else
                {
                    if (!context.trial().over() && context.state().mover() == mover)
                        fail("Mover did not change after the third placement.");
                    validateAllPointStates(context);
                }
            }
            validateFinishedGame(context, gameIndex);
        }
    }

    private static void validateFinishedGame(
        final Context context, final int gameIndex
    )
    {
        final Trial trial = context.trial();
        if (!"NaturalEnd".equals(trial.status().endType().toString()))
            fail("Random game " + gameIndex + " did not end naturally.");
        if (trial.numMoves() != TOTAL_PLACEMENTS || trial.numTurns() != TURNS)
            fail("Random game " + gameIndex + " ended at unexpected length.");

        final Metrics metrics = metrics(context);
        if (metrics.p1Total != PIECES_PER_PLAYER
            || metrics.p2Total != PIECES_PER_PLAYER)
        {
            fail("Random game " + gameIndex + " has an incorrect Piece total.");
        }

        final int p1Score = score(metrics.p1Secured, metrics.p1Advantage, metrics.p1Objective);
        final int p2Score = score(metrics.p2Secured, metrics.p2Advantage, metrics.p2Objective);
        if (context.score(1) != p1Score || context.score(2) != p2Score)
            fail("Random game " + gameIndex + " has an incorrect Ludii score.");

        final int expectedWinner = lexicographicWinner(metrics);
        if (trial.status().winner() != expectedWinner)
            fail("Random game " + gameIndex + " has an incorrect winner.");
    }

    private static Metrics metrics(final Context context)
    {
        final ContainerState board = context.containerState(0);
        final Metrics result = new Metrics();
        for (int site = 0; site < SITE_COUNT; ++site)
        {
            final int state = site >= SUPPLY_COUNT ? pointState(context, site) : 0;
            final int size = board.sizeStackVertex(site);
            for (int level = 0; level < size; ++level)
            {
                final int owner = board.whoVertex(site, level);
                if (owner == 1)
                    ++result.p1Total;
                else if (owner == 2)
                    ++result.p2Total;
                if (site >= SUPPLY_COUNT)
                {
                    if (owner == 1 && state == 1)
                        ++result.p1Objective;
                    else if (owner == 2 && state == 2)
                        ++result.p2Objective;
                }
            }

            if (site >= SUPPLY_COUNT)
            {
                if (state == 1)
                    ++result.p1Advantage;
                else if (state == 2)
                    ++result.p2Advantage;
                else if (state == 3)
                    ++result.p1Secured;
                else if (state == 4)
                    ++result.p2Secured;
            }
        }
        return result;
    }

    private static int lexicographicWinner(final Metrics metrics)
    {
        if (metrics.p1Secured != metrics.p2Secured)
            return metrics.p1Secured > metrics.p2Secured ? 1 : 2;
        if (metrics.p1Advantage != metrics.p2Advantage)
            return metrics.p1Advantage > metrics.p2Advantage ? 1 : 2;
        if (metrics.p1Objective != metrics.p2Objective)
            return metrics.p1Objective > metrics.p2Objective ? 1 : 2;
        return 0;
    }

    private static int score(
        final int secured,
        final int advantage,
        final int objectivePieces
    )
    {
        return SECURED_WEIGHT * secured
            + ADVANTAGE_WEIGHT * advantage
            + objectivePieces;
    }

    private static void validateAllPointStates(final Context context)
    {
        final ContainerState board = context.containerState(0);
        for (int site = 0; site < SITE_COUNT; ++site)
        {
            int p1 = 0;
            int p2 = 0;
            final int size = board.sizeStackVertex(site);
            for (int level = 0; level < size; ++level)
            {
                final int owner = board.whoVertex(site, level);
                if (owner == 1)
                    ++p1;
                else if (owner == 2)
                    ++p2;
            }
            if (p1 > 3 || p2 > 3)
                fail("A player has more than three Pieces on one Point.");

            final int expected;
            if (p1 == 3)
                expected = 3;
            else if (p2 == 3)
                expected = 4;
            else if (p1 > p2)
                expected = 1;
            else if (p2 > p1)
                expected = 2;
            else
                expected = 0;
            if (pointState(context, site) != expected)
                fail("Point state mismatch at site " + site + ".");
        }
    }

    private static void applySupply(
        final Game game, final Context context, final int target
    )
    {
        apply(game, context, target, -1);
    }

    private static void applyObjective(
        final Game game,
        final Context context,
        final int target,
        final int supplySource
    )
    {
        apply(game, context, target, supplySource);
    }

    private static void apply(
        final Game game,
        final Context context,
        final int target,
        final int supplySource
    )
    {
        final Move move = findMove(game, context, target, supplySource);
        if (move == null)
            fail("Expected legal decision " + target + "@" + supplySource + ".");
        game.apply(context, move);
    }

    private static Move findMove(
        final Game game,
        final Context context,
        final int target,
        final int supplySource
    )
    {
        for (final Move move : game.moves(context).moves())
        {
            final Decision candidate = decision(move);
            if (candidate.target == target
                && candidate.supplySource == supplySource)
            {
                return move;
            }
        }
        return null;
    }

    private static Decision decision(final Move move)
    {
        if (move.from() >= SUPPLY_COUNT)
            return new Decision(move.from(), move.to());
        return new Decision(move.to(), -1);
    }

    private static void assertAvailable(
        final Game game,
        final Context context,
        final int target,
        final int supplySource
    )
    {
        if (findMove(game, context, target, supplySource) == null)
            fail("Expected decision to be available: " + target + "@" + supplySource);
    }

    private static void assertUnavailable(
        final Game game,
        final Context context,
        final int target,
        final int supplySource
    )
    {
        if (findMove(game, context, target, supplySource) != null)
            fail("Expected decision to be unavailable: " + target + "@" + supplySource);
    }

    private static void assertNoObjectiveTarget(
        final Game game, final Context context, final int target
    )
    {
        for (final Move move : game.moves(context).moves())
        {
            final Decision candidate = decision(move);
            if (candidate.target == target && candidate.supplySource >= 0)
                fail("Secured Objective remains open: " + target);
        }
    }

    private static void assertMover(final Context context, final int expected)
    {
        if (context.state().mover() != expected)
            fail("Expected mover P" + expected + ".");
    }

    private static void assertState(
        final Context context, final int site, final int expected
    )
    {
        final int actual = pointState(context, site);
        if (actual != expected)
            fail("Site " + site + " has state " + actual + " instead of " + expected);
    }

    private static int pointState(final Context context, final int site)
    {
        final ContainerState board = context.containerState(0);
        final int size = board.sizeStackVertex(site);
        return size == 0 ? 0 : board.stateVertex(site, size - 1);
    }

    private static int[] states(final Context context)
    {
        final int[] result = new int[SITE_COUNT];
        for (int site = 0; site < SITE_COUNT; ++site)
            result[site] = pointState(context, site);
        return result;
    }

    private static int totalPieces(final Context context)
    {
        final ContainerState board = context.containerState(0);
        int result = 0;
        for (int site = 0; site < SITE_COUNT; ++site)
            result += board.sizeStackVertex(site);
        return result;
    }

    private static String edgeKey(final int first, final int second)
    {
        return Math.min(first, second) + ":" + Math.max(first, second);
    }

    private static int supply(final int row, final int column)
    {
        return row * SUPPLY_DIM + column;
    }

    private static int objective(final int row, final int column)
    {
        return SUPPLY_COUNT + row * OBJECTIVE_DIM + column;
    }

    private static String supplyName(final int row, final int column)
    {
        return "S" + row + column;
    }

    private static String objectiveName(final int row, final int column)
    {
        return "O" + row + column;
    }

    private static int[] range(final int first, final int limit)
    {
        final int[] result = new int[limit - first];
        for (int index = 0; index < result.length; ++index)
            result[index] = first + index;
        return result;
    }

    private static void assertRegion(
        final Map<String, int[]> regions,
        final String name,
        final int[] expected
    )
    {
        final int[] actual = regions.get(name);
        if (actual == null || !Arrays.equals(actual, expected))
        {
            fail(
                "Region " + name + " differs: "
                + (actual == null ? "missing" : Arrays.toString(actual))
            );
        }
    }

    private static void fail(final String message)
    {
        throw new IllegalStateException(message);
    }

    private static final class Decision
    {
        final int target;
        final int supplySource;

        Decision(final int target, final int supplySource)
        {
            this.target = target;
            this.supplySource = supplySource;
        }
    }

    private static final class Metrics
    {
        int p1Total;
        int p2Total;
        int p1Objective;
        int p2Objective;
        int p1Secured;
        int p2Secured;
        int p1Advantage;
        int p2Advantage;
    }
}
