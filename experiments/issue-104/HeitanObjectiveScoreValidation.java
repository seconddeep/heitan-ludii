package heitan.experiments;

import java.io.File;
import java.util.SplittableRandom;

import game.Game;
import main.collections.FastArrayList;
import other.GameLoader;
import other.context.Context;
import other.move.Move;
import other.state.container.ContainerState;
import other.trial.Trial;

/** Validates the corrected Objective-Piece tiebreak on complete 4x4 games. */
public final class HeitanObjectiveScoreValidation
{
    private static final int FIRST_OBJECTIVE = 25;
    private static final int SITE_COUNT = 41;
    private static final int ADVANTAGE_WEIGHT = 37;
    private static final int SECURED_WEIGHT = 629;
    private static final int DEFAULT_GAME_LIMIT = 200;

    private HeitanObjectiveScoreValidation()
    {
        // Utility class.
    }

    public static void main(final String[] args) throws Exception
    {
        if (args.length < 1 || args.length > 2)
        {
            System.err.println(
                "Usage: HeitanObjectiveScoreValidation <Heitan.lud> [game-limit]"
            );
            System.exit(2);
        }

        final int gameLimit = args.length == 2
            ? Integer.parseInt(args[1])
            : DEFAULT_GAME_LIMIT;
        if (gameLimit <= 0)
            throw new IllegalArgumentException("game-limit must be positive.");

        final Game game = load(args[0]);
        validateWeights();

        long securedSeed = -1L;
        long opponentAdvantageSeed = -1L;
        long neutralSeed = -1L;
        int gamesChecked = 0;

        for (int gameIndex = 0; gameIndex < gameLimit; ++gameIndex)
        {
            final long seed = 104000L + gameIndex;
            final Metrics metrics = playAndValidate(game, seed);
            ++gamesChecked;

            if (securedSeed < 0L && metrics.securedPieces > 0)
                securedSeed = seed;
            if (opponentAdvantageSeed < 0L && metrics.opponentAdvantagePieces > 0)
                opponentAdvantageSeed = seed;
            if (neutralSeed < 0L && metrics.neutralPieces > 0)
                neutralSeed = seed;

            if (securedSeed >= 0L
                && opponentAdvantageSeed >= 0L
                && neutralSeed >= 0L)
            {
                break;
            }
        }

        if (securedSeed < 0L)
            fail("No final position contained a Piece on a Secured Objective.");
        if (opponentAdvantageSeed < 0L)
            fail("No final position contained a Piece on an opponent-Advantage Objective.");
        if (neutralSeed < 0L)
            fail("No final position contained a Piece on a neutral Objective.");

        System.out.printf(
            "Issue 104 scoring validation passed after %d complete games: "
            + "Secured seed=%d, opponent-Advantage seed=%d, neutral seed=%d.%n",
            gamesChecked, securedSeed, opponentAdvantageSeed, neutralSeed
        );
    }

    private static Game load(final String path) throws Exception
    {
        final File file = new File(path).getCanonicalFile();
        final Game game = GameLoader.loadGameFromFile(file);
        if (game == null)
            fail("Ludii could not compile " + file);
        return game;
    }

    private static void validateWeights()
    {
        final int piecesPerPlayer = 36;
        final int objectiveCount = 16;
        if (ADVANTAGE_WEIGHT <= piecesPerPlayer)
            fail("Advantage weight does not dominate the Objective-Piece tiebreak.");
        if (SECURED_WEIGHT
            <= objectiveCount * ADVANTAGE_WEIGHT + piecesPerPlayer)
        {
            fail("Secured weight does not dominate the lower tiebreaks.");
        }
    }

    private static Metrics playAndValidate(final Game game, final long seed)
    {
        final SplittableRandom random = new SplittableRandom(seed);
        final Context context = new Context(game, new Trial(game));
        game.start(context);

        while (!context.trial().over())
        {
            final FastArrayList<Move> moves = game.moves(context).moves();
            if (moves.isEmpty())
                fail("No legal move before the natural end for seed " + seed + ".");
            game.apply(context, moves.get(random.nextInt(moves.size())));
        }

        final Metrics metrics = metrics(context);
        final int p1Score = score(
            metrics.p1Secured, metrics.p1Advantage, metrics.p1ScoringPieces
        );
        final int p2Score = score(
            metrics.p2Secured, metrics.p2Advantage, metrics.p2ScoringPieces
        );
        if (context.score(1) != p1Score || context.score(2) != p2Score)
        {
            fail(
                "Corrected score mismatch for seed " + seed + ": expected "
                + p1Score + "/" + p2Score + ", got "
                + context.score(1) + "/" + context.score(2) + "."
            );
        }

        final int expectedWinner = p1Score > p2Score ? 1 : p2Score > p1Score ? 2 : 0;
        if (context.trial().status().winner() != expectedWinner)
            fail("Winner mismatch for seed " + seed + ".");

        return metrics;
    }

    private static Metrics metrics(final Context context)
    {
        final ContainerState board = context.containerState(0);
        final Metrics result = new Metrics();

        for (int site = FIRST_OBJECTIVE; site < SITE_COUNT; ++site)
        {
            final int size = board.sizeStackVertex(site);
            final int state = size == 0 ? 0 : board.stateVertex(site, size - 1);

            if (state == 1)
                ++result.p1Advantage;
            else if (state == 2)
                ++result.p2Advantage;
            else if (state == 3)
                ++result.p1Secured;
            else if (state == 4)
                ++result.p2Secured;

            for (int level = 0; level < size; ++level)
            {
                final int owner = board.whoVertex(site, level);
                if (owner == 1 && state == 1)
                    ++result.p1ScoringPieces;
                else if (owner == 2 && state == 2)
                    ++result.p2ScoringPieces;
                else if (state == 0)
                    ++result.neutralPieces;
                else if (state == 3 || state == 4)
                    ++result.securedPieces;
                else if ((owner == 1 && state == 2) || (owner == 2 && state == 1))
                    ++result.opponentAdvantagePieces;
            }
        }
        return result;
    }

    private static int score(
        final int secured, final int advantage, final int scoringPieces
    )
    {
        return SECURED_WEIGHT * secured
            + ADVANTAGE_WEIGHT * advantage
            + scoringPieces;
    }

    private static void fail(final String message)
    {
        throw new IllegalStateException(message);
    }

    private static final class Metrics
    {
        int p1Secured;
        int p2Secured;
        int p1Advantage;
        int p2Advantage;
        int p1ScoringPieces;
        int p2ScoringPieces;
        int securedPieces;
        int opponentAdvantagePieces;
        int neutralPieces;
    }
}
