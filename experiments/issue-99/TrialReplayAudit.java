package heitan.experiments;

import java.io.File;
import java.util.List;

import game.Game;
import manager.utils.game_logs.MatchRecord;
import other.GameLoader;
import other.context.Context;
import other.move.Move;
import other.trial.Trial;

/** Read-only legal replay check for representative public-release audit trials. */
public final class TrialReplayAudit
{
    private TrialReplayAudit()
    {
        // Utility class.
    }

    public static void main(final String[] args) throws Exception
    {
        if (args.length < 3)
        {
            System.err.println(
                "Usage: TrialReplayAudit <game.lud> <board-option> <trial.trl> [trial.trl ...]"
            );
            System.exit(2);
        }

        final File gameFile = new File(args[0]).getCanonicalFile();
        final String boardOption = args[1];
        final Game game = GameLoader.loadGameFromFile(gameFile, List.of(boardOption));
        if (game == null)
            throw new IllegalStateException("Could not load the game for " + boardOption);

        int validated = 0;
        for (int i = 2; i < args.length; ++i)
        {
            replay(game, new File(args[i]));
            ++validated;
        }

        System.out.println("Validated " + validated + " trial(s) for " + boardOption + ".");
    }

    private static void replay(final Game game, final File trialFile) throws Exception
    {
        final Trial source = MatchRecord.loadMatchRecordFromTextFile(trialFile, game).trial();
        final Trial replay = new Trial(game);
        final Context context = new Context(game, replay);
        game.start(context);
        for (int i = 0; i < source.numMoves(); ++i)
        {
            final Move recorded = source.getMove(i);
            final Move legal = findLegalMove(game, context, recorded);
            if (legal == null)
                throw new IllegalStateException("Recorded move " + (i + 1) + " is not legal.");
            game.apply(context, legal);
        }

        if (replay.numMoves() != source.numMoves() || replay.numTurns() != source.numTurns())
            throw new IllegalStateException("Replay outcome differs from the source trial.");

        if (source.over())
        {
            if (!replay.over()
                || !"NaturalEnd".equals(source.status().endType().toString())
                || replay.status().winner() != source.status().winner()
                || !replay.status().endType().equals(source.status().endType()))
                throw new IllegalStateException("Replay outcome differs from the source trial.");
        }
        else if (replay.over())
        {
            throw new IllegalStateException("A partial source unexpectedly reached an end state.");
        }
    }

    private static Move findLegalMove(
        final Game game, final Context context, final Move recorded
    )
    {
        for (final Move candidate : game.moves(context).moves())
            if (candidate.mover() == recorded.mover()
                && candidate.from() == recorded.from()
                && candidate.to() == recorded.to())
                return candidate;
        return null;
    }
}
