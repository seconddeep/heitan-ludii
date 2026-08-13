package heitan.experiments;

import java.io.File;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.Stream;

import game.Game;
import manager.utils.game_logs.MatchRecord;
import other.GameLoader;
import other.context.Context;
import other.move.Move;
import other.state.container.ContainerState;
import other.trial.Trial;

/** Compares two Heitan definitions at every position in existing 4x4 trials. */
public final class HeitanRegression
{
    private static final int SITE_COUNT = 41;

    private HeitanRegression()
    {
        // Utility class.
    }

    public static void main(final String[] args) throws Exception
    {
        if (args.length < 3)
        {
            System.err.println(
                "Usage: HeitanRegression <baseline.lud> <candidate.lud> <trial-dir>..."
            );
            System.exit(2);
        }

        final Game baseline = load(args[0]);
        final Game candidate = load(args[1]);
        final List<Path> trials = new ArrayList<>();
        for (int index = 2; index < args.length; ++index)
        {
            try (Stream<Path> paths = Files.list(Path.of(args[index])))
            {
                paths.filter(path -> path.getFileName().toString().endsWith(".trl"))
                    .forEach(trials::add);
            }
        }
        trials.sort(Comparator.comparing(Path::toString));
        if (trials.isEmpty())
            throw new IllegalStateException("No trials supplied.");

        long comparedPositions = 0;
        for (final Path trial : trials)
            comparedPositions += compareTrial(baseline, candidate, trial);

        System.out.printf(
            "Compared %d games and %d positions: legal moves, board states, and results match.%n",
            trials.size(), comparedPositions
        );
    }

    private static Game load(final String path) throws Exception
    {
        final File file = new File(path).getCanonicalFile();
        final Game game = GameLoader.loadGameFromFile(file);
        if (game == null)
            throw new IllegalStateException("Ludii could not compile " + file);
        return game;
    }

    private static long compareTrial(
        final Game baseline,
        final Game candidate,
        final Path trialPath
    ) throws Exception
    {
        final Trial source = MatchRecord.loadMatchRecordFromTextFile(
            trialPath.toFile(), baseline
        ).trial();
        final Context baselineContext = new Context(baseline, new Trial(baseline));
        final Context candidateContext = new Context(candidate, new Trial(candidate));
        baseline.start(baselineContext);
        candidate.start(candidateContext);

        for (int ply = 0; ply < source.numMoves(); ++ply)
        {
            assertSamePosition(baseline, baselineContext, candidate, candidateContext, trialPath, ply);
            final Move recorded = source.getMove(ply);
            final Move baselineMove = matchingMove(baseline, baselineContext, recorded);
            final Move candidateMove = matchingMove(candidate, candidateContext, recorded);
            if (baselineMove == null || candidateMove == null)
                fail(trialPath, ply, "recorded decision is not legal in both definitions");
            baseline.apply(baselineContext, baselineMove);
            candidate.apply(candidateContext, candidateMove);
            if (!snapshot(baselineContext).equals(snapshot(candidateContext)))
                fail(trialPath, ply + 1, "board state differs after placement");
        }

        assertSamePosition(
            baseline, baselineContext, candidate, candidateContext, trialPath, source.numMoves()
        );
        final Trial baselineTrial = baselineContext.trial();
        final Trial candidateTrial = candidateContext.trial();
        if (!baselineTrial.over() || !candidateTrial.over())
            fail(trialPath, source.numMoves(), "game did not end naturally in both definitions");
        if (baselineTrial.numMoves() != candidateTrial.numMoves()
            || baselineTrial.numTurns() != candidateTrial.numTurns()
            || baselineTrial.status().winner() != candidateTrial.status().winner()
            || !baselineTrial.status().endType().equals(candidateTrial.status().endType())
            || baselineContext.score(1) != candidateContext.score(1)
            || baselineContext.score(2) != candidateContext.score(2))
        {
            fail(trialPath, source.numMoves(), "final result differs");
        }
        return source.numMoves() + 1L;
    }

    private static void assertSamePosition(
        final Game baseline,
        final Context baselineContext,
        final Game candidate,
        final Context candidateContext,
        final Path trialPath,
        final int ply
    )
    {
        if (baselineContext.state().mover() != candidateContext.state().mover())
            fail(trialPath, ply, "mover differs");
        if (!snapshot(baselineContext).equals(snapshot(candidateContext)))
            fail(trialPath, ply, "board state differs");
        final Set<String> baselineMoves = legalDecisions(baseline, baselineContext);
        final Set<String> candidateMoves = legalDecisions(candidate, candidateContext);
        if (!baselineMoves.equals(candidateMoves))
            fail(trialPath, ply, "legal decision set differs");
    }

    private static Set<String> legalDecisions(final Game game, final Context context)
    {
        final Set<String> result = new TreeSet<>();
        if (context.trial().over())
            return result;
        for (final Move move : game.moves(context).moves())
            result.add(decision(move));
        return result;
    }

    private static Move matchingMove(
        final Game game,
        final Context context,
        final Move recorded
    )
    {
        final String expected = decision(recorded);
        for (final Move move : game.moves(context).moves())
            if (decision(move).equals(expected))
                return move;
        return null;
    }

    private static String decision(final Move move)
    {
        return move.mover() + ":" + move.from() + ":" + move.to();
    }

    private static String snapshot(final Context context)
    {
        final ContainerState board = context.containerState(0);
        final StringBuilder result = new StringBuilder();
        for (int site = 0; site < SITE_COUNT; ++site)
        {
            if (site > 0)
                result.append('|');
            final int size = board.sizeStackVertex(site);
            result.append(site).append('[');
            for (int level = 0; level < size; ++level)
            {
                if (level > 0)
                    result.append(',');
                result.append(board.whoVertex(site, level)).append(':')
                    .append(board.stateVertex(site, level));
            }
            result.append(']');
        }
        return result.toString();
    }

    private static void fail(final Path trial, final int ply, final String message)
    {
        throw new IllegalStateException(trial + " at ply " + ply + ": " + message);
    }
}
