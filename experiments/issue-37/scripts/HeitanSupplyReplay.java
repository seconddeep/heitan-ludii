package heitan.experiments;

import java.io.BufferedWriter;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Stream;

import game.Game;
import main.collections.FastArrayList;
import manager.utils.game_logs.MatchRecord;
import other.GameLoader;
import other.context.Context;
import other.move.Move;
import other.state.container.ContainerState;
import other.trial.Trial;

/** Legally replay Issue #32 trials and extract turn-level data for Issue #37. */
public final class HeitanSupplyReplay
{
    private static final String[] SITE_NAMES = {
        "S00", "S01", "S02", "S03", "S04",
        "S10", "S11", "S12", "S13", "S14",
        "S20", "S21", "S22", "S23", "S24",
        "S30", "S31", "S32", "S33", "S34",
        "S40", "S41", "S42", "S43", "S44",
        "O00", "O01", "O02", "O03",
        "O10", "O11", "O12", "O13",
        "O20", "O21", "O22", "O23",
        "O30", "O31", "O32", "O33"
    };
    private static final Pattern GAME_INDEX = Pattern.compile(".*-(\\d{4})\\.trl");

    private HeitanSupplyReplay()
    {
        // Utility class.
    }

    public static void main(final String[] args) throws Exception
    {
        if (args.length != 7)
        {
            System.err.println(
                "Usage: HeitanSupplyReplay <game.lud> <trials-root> <experiment-ids> "
                + "<summary.csv> <placements.csv> <supply-turns.csv> <objective-turns.csv>"
            );
            System.exit(2);
        }
        final File gameFile = new File(args[0]).getCanonicalFile();
        final Path trialsRoot = Path.of(args[1]).toRealPath();
        final String[] experimentIds = args[2].split(",");
        final Path summaryPath = Path.of(args[3]);
        final Path placementsPath = Path.of(args[4]);
        final Path supplyPath = Path.of(args[5]);
        final Path objectivePath = Path.of(args[6]);

        final Game game = GameLoader.loadGameFromFile(gameFile);
        if (game == null)
            throw new IllegalStateException("Ludii could not compile " + gameFile);
        for (final Path path : List.of(summaryPath, placementsPath, supplyPath, objectivePath))
            Files.createDirectories(path.toAbsolutePath().getParent());

        try (
            BufferedWriter summary = writer(summaryPath);
            BufferedWriter placements = writer(placementsPath);
            BufferedWriter supply = writer(supplyPath);
            BufferedWriter objectives = writer(objectivePath)
        )
        {
            summary.write("experiment_id,game_index,winner,moves,turns,end_type,final_board,trial_file");
            summary.newLine();
            placements.write(
                "experiment_id,game_index,turn_number,placement_number,mover,target,"
                + "target_type,supply_source"
            );
            placements.newLine();
            supply.write(
                "experiment_id,game_index,turn_number,mover,supply_point,"
                + "state_at_turn_start,p1_pieces_at_turn_start,p2_pieces_at_turn_start,"
                + "legal_max_additional_placements_this_turn,state_at_turn_end,"
                + "p1_pieces_at_turn_end,p2_pieces_at_turn_end"
            );
            supply.newLine();
            objectives.write(
                "experiment_id,game_index,turn_number,mover,objective,"
                + "state_at_turn_start,p1_pieces_at_turn_start,p2_pieces_at_turn_start,"
                + "state_at_turn_end,p1_pieces_at_turn_end,p2_pieces_at_turn_end"
            );
            objectives.newLine();

            int games = 0;
            for (final String experimentId : experimentIds)
            {
                final Path directory = trialsRoot.resolve(experimentId);
                final List<Path> trials;
                try (Stream<Path> paths = Files.list(directory))
                {
                    trials = paths.filter(path -> path.getFileName().toString().endsWith(".trl"))
                        .sorted(Comparator.comparing(Path::toString)).toList();
                }
                if (trials.isEmpty())
                    throw new IllegalStateException("No trials found in " + directory);
                for (final Path trialPath : trials)
                {
                    replayOne(game, trialPath, experimentId, summary, placements, supply, objectives);
                    ++games;
                }
            }
            System.out.printf(Locale.ROOT, "legally replayed %d Issue #32 games%n", games);
        }
    }

    private static BufferedWriter writer(final Path path) throws Exception
    {
        return Files.newBufferedWriter(
            path, StandardCharsets.UTF_8, StandardOpenOption.CREATE,
            StandardOpenOption.TRUNCATE_EXISTING, StandardOpenOption.WRITE
        );
    }

    private static void replayOne(
        final Game game,
        final Path sourcePath,
        final String experimentId,
        final BufferedWriter summary,
        final BufferedWriter placements,
        final BufferedWriter supply,
        final BufferedWriter objectives
    ) throws Exception
    {
        final Matcher matcher = GAME_INDEX.matcher(sourcePath.getFileName().toString());
        if (!matcher.matches())
            throw new IllegalArgumentException("Cannot read game index from " + sourcePath);
        final int gameIndex = Integer.parseInt(matcher.group(1));
        final MatchRecord record = MatchRecord.loadMatchRecordFromTextFile(sourcePath.toFile(), game);
        final Trial source = record.trial();
        if (source.numMoves() != 72 || source.numTurns() != 24)
            throw new IllegalStateException("Source is not a complete 72-move/24-turn game: " + sourcePath);

        final Trial replay = new Trial(game);
        final Context context = new Context(game, replay);
        game.start(context);
        int sourceMove = 0;
        for (int turn = 1; turn <= 24; ++turn)
        {
            final int mover = context.state().mover();
            final Snapshot before = snapshot(context);
            final int[] legalCapacity = new int[25];
            for (int site = 0; site < 25; ++site)
                legalCapacity[site] = legalAdditionalSupplyPlacements(game, context, site);

            for (int placement = 1; placement <= 3; ++placement)
            {
                if (context.state().mover() != mover)
                    throw new IllegalStateException("Mover changed before third placement: " + sourcePath);
                final Move recorded = source.getMove(sourceMove++);
                final Move legal = findLegalReplayMove(game, context, recorded);
                if (legal == null)
                    throw new IllegalStateException(
                        "Illegal source move " + sourceMove + " in " + sourcePath
                    );
                final Decision decision = decision(legal);
                writeRow(placements, List.of(
                    experimentId, Integer.toString(gameIndex), Integer.toString(turn),
                    Integer.toString(placement), Integer.toString(mover),
                    SITE_NAMES[decision.target], decision.target < 25 ? "supply" : "objective",
                    decision.supplySource < 0 ? "" : SITE_NAMES[decision.supplySource]
                ));
                game.apply(context, legal);
                if (placement < 3 && context.state().mover() != mover)
                    throw new IllegalStateException("Mover changed within a turn: " + sourcePath);
            }
            final Snapshot after = snapshot(context);
            if (after.totalPieces != before.totalPieces + 3)
                throw new IllegalStateException("Turn did not add three Pieces: " + sourcePath);
            if (turn < 24 && context.state().mover() == mover)
                throw new IllegalStateException("Mover did not change at turn boundary: " + sourcePath);
            writeTurnRows(
                supply, experimentId, gameIndex, turn, mover, before, after, legalCapacity, 0, 25
            );
            writeTurnRows(
                objectives, experimentId, gameIndex, turn, mover, before, after, null, 25, 41
            );
        }
        if (!replay.over() || replay.numMoves() != 72 || replay.numTurns() != 24)
            throw new IllegalStateException("Replay did not finish naturally: " + sourcePath);
        if (replay.status().winner() != source.status().winner())
            throw new IllegalStateException("Replay winner differs from source: " + sourcePath);

        final Snapshot finalState = snapshot(context);
        writeRow(summary, List.of(
            experimentId, Integer.toString(gameIndex), Integer.toString(replay.status().winner()),
            Integer.toString(replay.numMoves()), Integer.toString(replay.numTurns()),
            replay.status().endType().toString(), finalState.serialized,
            relativePath(sourcePath)
        ));
    }

    private static int legalAdditionalSupplyPlacements(
        final Game game, final Context original, final int supplySite
    )
    {
        final Context copy = new Context(original);
        final int mover = copy.state().mover();
        int count = 0;
        while (!copy.trial().over() && copy.state().mover() == mover)
        {
            Move supplyMove = null;
            for (final Move move : game.moves(copy).moves())
            {
                final Decision candidate = decision(move);
                if (candidate.supplySource < 0 && candidate.target == supplySite)
                {
                    supplyMove = move;
                    break;
                }
            }
            if (supplyMove == null)
                break;
            game.apply(copy, supplyMove);
            ++count;
            if (count > 3)
                throw new IllegalStateException("Supply placement capacity exceeds a Heitan turn.");
        }
        return count;
    }

    private static Move findLegalReplayMove(
        final Game game, final Context context, final Move recorded
    )
    {
        for (final Move candidate : game.moves(context).moves())
            if (sameDecision(candidate, recorded))
                return candidate;
        return null;
    }

    private static boolean sameDecision(final Move left, final Move right)
    {
        return left.mover() == right.mover()
            && left.from() == right.from()
            && left.to() == right.to();
    }

    private static Decision decision(final Move move)
    {
        if (move.from() >= 25)
            return new Decision(move.from(), move.to());
        return new Decision(move.to(), -1);
    }

    private static Snapshot snapshot(final Context context)
    {
        final ContainerState board = context.containerState(0);
        final Snapshot result = new Snapshot();
        final StringBuilder serialized = new StringBuilder();
        for (int site = 0; site < SITE_NAMES.length; ++site)
        {
            final int size = board.sizeStackVertex(site);
            result.totalPieces += size;
            for (int level = 0; level < size; ++level)
            {
                final int owner = board.whoVertex(site, level);
                if (owner == 1)
                    ++result.p1[site];
                else if (owner == 2)
                    ++result.p2[site];
            }
            result.states[site] = size == 0 ? 0 : board.stateVertex(site, size - 1);
            if (site > 0)
                serialized.append('|');
            serialized.append(SITE_NAMES[site]).append(':').append(result.states[site])
                .append(':').append(result.p1[site]).append(':').append(result.p2[site]);
        }
        result.serialized = serialized.toString();
        return result;
    }

    private static void writeTurnRows(
        final BufferedWriter output,
        final String experimentId,
        final int gameIndex,
        final int turn,
        final int mover,
        final Snapshot before,
        final Snapshot after,
        final int[] legalCapacity,
        final int firstSite,
        final int lastSite
    ) throws Exception
    {
        for (int site = firstSite; site < lastSite; ++site)
        {
            final List<String> values = new ArrayList<>();
            values.add(experimentId);
            values.add(Integer.toString(gameIndex));
            values.add(Integer.toString(turn));
            values.add(Integer.toString(mover));
            values.add(SITE_NAMES[site]);
            values.add(Integer.toString(before.states[site]));
            values.add(Integer.toString(before.p1[site]));
            values.add(Integer.toString(before.p2[site]));
            if (legalCapacity != null)
                values.add(Integer.toString(legalCapacity[site]));
            values.add(Integer.toString(after.states[site]));
            values.add(Integer.toString(after.p1[site]));
            values.add(Integer.toString(after.p2[site]));
            writeRow(output, values);
        }
    }

    private static void writeRow(final BufferedWriter output, final List<String> fields)
        throws Exception
    {
        for (int index = 0; index < fields.size(); ++index)
        {
            if (index > 0)
                output.write(',');
            output.write('"');
            output.write(fields.get(index).replace("\"", "\"\""));
            output.write('"');
        }
        output.newLine();
    }

    private static String relativePath(final Path path) throws Exception
    {
        final Path repository = Path.of("").toRealPath();
        return repository.relativize(path.toRealPath()).toString().replace('\\', '/');
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

    private static final class Snapshot
    {
        final int[] states = new int[SITE_NAMES.length];
        final int[] p1 = new int[SITE_NAMES.length];
        final int[] p2 = new int[SITE_NAMES.length];
        int totalPieces;
        String serialized;
    }
}
