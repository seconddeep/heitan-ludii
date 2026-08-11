package heitan.experiments;

import java.io.BufferedWriter;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

import org.apache.commons.rng.core.RandomProviderDefaultState;
import org.apache.commons.rng.core.source64.SplitMix64;

import game.Game;
import main.collections.FastArrayList;
import manager.utils.game_logs.MatchRecord;
import other.AI;
import other.GameLoader;
import other.context.Context;
import other.move.Move;
import other.state.container.ContainerState;
import other.trial.Trial;
import utils.AIFactory;

/** Run repeated UCT searches for exactly one three-placement Heitan turn. */
public final class HeitanPositionSearch
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

    private HeitanPositionSearch()
    {
        // Utility class.
    }

    public static void main(final String[] args) throws Exception
    {
        if (args.length != 14)
        {
            System.err.println(
                "Usage: HeitanPositionSearch <game.lud> <source.trl> <prefix> "
                + "<position-id> <mover> <iterations> <repetitions> <base-seed> "
                + "<max-seconds> <raw.csv> <trials-dir> <repetition-offset> "
                + "<source-sha256> <prefix-sha256>"
            );
            System.exit(2);
        }

        final File gameFile = new File(args[0]).getCanonicalFile();
        final File sourceFile = new File(args[1]).getCanonicalFile();
        final int prefix = Integer.parseInt(args[2]);
        final String positionId = args[3];
        final int expectedMover = Integer.parseInt(args[4]);
        final int iterations = Integer.parseInt(args[5]);
        final int repetitions = Integer.parseInt(args[6]);
        final long baseSeed = Long.parseLong(args[7]);
        final double maxSeconds = Double.parseDouble(args[8]);
        final Path rawOutput = Path.of(args[9]);
        final Path trialsDirectory = Path.of(args[10]);
        final int repetitionOffset = Integer.parseInt(args[11]);
        final String expectedSourceHash = args[12];
        final String expectedPrefixHash = args[13];

        if (!gameFile.isFile() || !sourceFile.isFile())
            throw new IllegalArgumentException("Game or source trial does not exist.");
        if (prefix <= 0 || prefix % 3 != 0)
            throw new IllegalArgumentException("Prefix must be a positive multiple of three.");
        if (expectedMover < 1 || expectedMover > 2 || iterations <= 0 || repetitions <= 0)
            throw new IllegalArgumentException("Invalid mover, iterations, or repetitions.");
        if (!sha256(sourceFile.toPath()).equals(expectedSourceHash))
            throw new IllegalStateException("Source trial hash mismatch: " + sourceFile);
        if (!prefixHash(sourceFile.toPath(), prefix).equals(expectedPrefixHash))
            throw new IllegalStateException("Source prefix hash mismatch: " + sourceFile);

        final Game game = GameLoader.loadGameFromFile(gameFile);
        if (game == null)
            throw new IllegalStateException("Ludii could not compile " + gameFile);
        final MatchRecord sourceRecord = MatchRecord.loadMatchRecordFromTextFile(sourceFile, game);
        final Trial sourceTrial = sourceRecord.trial();
        if (sourceTrial.numMoves() < prefix)
            throw new IllegalArgumentException("Prefix exceeds source trial length.");

        Files.createDirectories(rawOutput.toAbsolutePath().getParent());
        Files.createDirectories(trialsDirectory);
        try (BufferedWriter output = Files.newBufferedWriter(
            rawOutput, StandardCharsets.UTF_8, StandardOpenOption.CREATE,
            StandardOpenOption.TRUNCATE_EXISTING, StandardOpenOption.WRITE
        ))
        {
            output.write(csvHeader());
            output.newLine();
            for (int index = 0; index < repetitions; ++index)
            {
                final int repetition = repetitionOffset + index + 1;
                final long seed = baseSeed + index;
                output.write(runOne(
                    game, gameFile, sourceTrial, sourceFile.toPath(), prefix,
                    positionId, expectedMover, iterations, repetition, seed,
                    maxSeconds, trialsDirectory
                ));
                output.newLine();
                output.flush();
                System.out.printf(
                    Locale.ROOT, "%s %d iterations: repetition %d complete%n",
                    positionId, iterations, repetition
                );
            }
        }
    }

    private static String runOne(
        final Game game,
        final File gameFile,
        final Trial sourceTrial,
        final Path sourcePath,
        final int prefix,
        final String positionId,
        final int expectedMover,
        final int iterations,
        final int repetition,
        final long seed,
        final double maxSeconds,
        final Path trialsDirectory
    ) throws Exception
    {
        final Trial trial = new Trial(game);
        final Context context = new Context(game, trial);
        context.rng().restoreState(new SplitMix64(seed).saveState());
        final RandomProviderDefaultState initialRngState =
            (RandomProviderDefaultState) context.rng().saveState();
        game.start(context);

        for (int moveIndex = 0; moveIndex < prefix; ++moveIndex)
        {
            final Move recorded = sourceTrial.getMove(moveIndex);
            final Move legal = findLegalReplayMove(game, context, recorded);
            if (legal == null)
                throw new IllegalStateException("Illegal source prefix move at index " + moveIndex);
            game.apply(context, legal);
        }
        if (context.state().mover() != expectedMover)
            throw new IllegalStateException("Prefix is not the expected mover's turn boundary.");
        if (trial.numMoves() != prefix || trial.numTurns() != prefix / 3)
            throw new IllegalStateException("Prefix is not a complete Heitan-turn boundary.");

        final BoardSnapshot before = snapshot(context);
        final int piecesBefore = before.totalPieces;
        final int mover = context.state().mover();
        final List<String> ordered = new ArrayList<>();
        final List<String> targets = new ArrayList<>();
        final List<String> supplySources = new ArrayList<>();
        final List<String> spatialCategories = new ArrayList<>();
        final List<String> legalCounts = new ArrayList<>();
        final List<String> placementMillis = new ArrayList<>();
        final Set<Integer> usedSources = new HashSet<>();

        final AI uct = AIFactory.createAI("UCT");
        if (uct == null || !uct.supportsGame(game))
            throw new IllegalStateException("Ludii UCT does not support Heitan.");
        uct.setMaxIterationsPerMove(iterations);
        uct.setMaxSecondsPerMove(maxSeconds);
        uct.initAI(game, mover);
        final List<AI> agents = new ArrayList<>();
        agents.add(null);
        agents.add(uct);
        agents.add(uct);

        final long turnStarted = System.nanoTime();
        try
        {
            for (int placement = 0; placement < 3; ++placement)
            {
                if (context.state().mover() != mover)
                    throw new IllegalStateException("Mover changed before the third placement.");
                final FastArrayList<Move> legalMoves = game.moves(context).moves();
                legalCounts.add(Integer.toString(legalMoves.size()));
                final int movesBeforeStep = trial.numMoves();
                final long started = System.nanoTime();
                context.model().startNewStep(
                    context, agents, maxSeconds, iterations, -1, 0.0
                );
                final long elapsed = System.nanoTime() - started;
                if (trial.numMoves() != movesBeforeStep + 1)
                    throw new IllegalStateException("UCT step did not apply exactly one placement.");
                final Move selected = trial.lastMove();
                if (selected == null || !containsDecision(legalMoves, selected))
                    throw new IllegalStateException("UCT returned an illegal placement.");

                final Decision decision = decision(selected);
                if (decision.supplySource >= 0)
                {
                    final int sourceState = pointState(context, decision.supplySource);
                    if (sourceState != mover && sourceState != mover + 2)
                        throw new IllegalStateException("Objective used an uncontrolled Supply Point.");
                    if (!usedSources.add(Integer.valueOf(decision.supplySource)))
                        throw new IllegalStateException("Supply Point reused in one turn.");
                    supplySources.add(SITE_NAMES[decision.supplySource]);
                }
                targets.add(SITE_NAMES[decision.target]);
                spatialCategories.add(spatial(SITE_NAMES[decision.target]));
                ordered.add(
                    SITE_NAMES[decision.target]
                    + (decision.supplySource < 0 ? "" : "@" + SITE_NAMES[decision.supplySource])
                );
                placementMillis.add(String.format(Locale.ROOT, "%.3f", elapsed / 1_000_000.0));

                if (snapshot(context).totalPieces != piecesBefore + placement + 1)
                    throw new IllegalStateException("Placement did not add exactly one Piece.");
                if (placement < 2)
                {
                    if (context.state().mover() != mover)
                        throw new IllegalStateException("Mover changed within the turn.");
                    if (!samePointStates(before, snapshot(context)))
                        throw new IllegalStateException("Point state changed before the third placement.");
                }
            }
        }
        finally
        {
            uct.closeAI();
        }
        final long turnElapsed = System.nanoTime() - turnStarted;
        if (context.state().mover() == mover)
            throw new IllegalStateException("Mover did not change after the third placement.");

        final BoardSnapshot after = snapshot(context);
        if (after.totalPieces != piecesBefore + 3)
            throw new IllegalStateException("One turn did not add exactly three Pieces.");
        validateUpdatedStates(after, targets);

        final List<String> securedTransitions = new ArrayList<>();
        final List<String> unresolvedTransitions = new ArrayList<>();
        for (int site = 0; site < 25; ++site)
        {
            if (before.states[site] < 3 && after.states[site] >= 3)
            {
                securedTransitions.add(SITE_NAMES[site] + ":P" + (after.states[site] - 2));
            }
            else if (after.states[site] < 3
                && (before.states[site] != after.states[site]
                    || before.p1Counts[site] != after.p1Counts[site]
                    || before.p2Counts[site] != after.p2Counts[site]))
            {
                unresolvedTransitions.add(String.format(
                    Locale.ROOT, "%s:%d:%d:%d>%d:%d:%d", SITE_NAMES[site],
                    before.states[site], before.p1Counts[site], before.p2Counts[site],
                    after.states[site], after.p1Counts[site], after.p2Counts[site]
                ));
            }
        }

        final Path trialPath = trialsDirectory.resolve(String.format(
            Locale.ROOT, "%s-uct-%d-%04d.trl", positionId, iterations, repetition
        ));
        trial.saveTrialToTextFile(
            trialPath.toFile(), gameFile.getPath(), new ArrayList<String>(), initialRngState
        );

        final List<String> objectiveTargets = new ArrayList<>();
        final List<String> supplyTargets = new ArrayList<>();
        for (final String target : targets)
        {
            if (target.charAt(0) == 'O')
                objectiveTargets.add(target);
            else
                supplyTargets.add(target);
        }
        final List<String> fields = new ArrayList<>();
        fields.add(positionId);
        fields.add(Integer.toString(prefix));
        fields.add(relativePath(sourcePath));
        fields.add(Integer.toString(mover));
        fields.add(Integer.toString(context.state().mover()));
        fields.add(Integer.toString(iterations));
        fields.add(Integer.toString(iterations));
        fields.add(Integer.toString(repetition));
        fields.add(Long.toString(seed));
        fields.add(join(ordered));
        fields.add(join(targets));
        fields.add(join(supplyTargets));
        fields.add(join(objectiveTargets));
        fields.add(join(supplySources));
        fields.add(join(spatialCategories));
        fields.add(join(securedTransitions));
        fields.add(join(unresolvedTransitions));
        fields.add(join(legalCounts));
        fields.add(join(placementMillis));
        fields.add(String.format(Locale.ROOT, "%.3f", turnElapsed / 1_000_000.0));
        fields.add(before.serialized);
        fields.add(after.serialized);
        fields.add(relativePath(trialPath));
        return csv(fields);
    }

    private static Move findLegalReplayMove(
        final Game game, final Context context, final Move recorded
    )
    {
        final FastArrayList<Move> legalMoves = game.moves(context).moves();
        for (final Move candidate : legalMoves)
            if (sameDecision(candidate, recorded))
                return candidate;
        return null;
    }

    private static boolean containsDecision(final FastArrayList<Move> moves, final Move selected)
    {
        for (final Move legal : moves)
            if (sameDecision(legal, selected))
                return true;
        return false;
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

    private static BoardSnapshot snapshot(final Context context)
    {
        final ContainerState board = context.containerState(0);
        final BoardSnapshot result = new BoardSnapshot();
        final StringBuilder serialized = new StringBuilder();
        for (int site = 0; site < SITE_NAMES.length; ++site)
        {
            final int stackSize = board.sizeStackVertex(site);
            result.totalPieces += stackSize;
            for (int level = 0; level < stackSize; ++level)
            {
                final int owner = board.whoVertex(site, level);
                if (owner == 1)
                    ++result.p1Counts[site];
                else if (owner == 2)
                    ++result.p2Counts[site];
            }
            result.states[site] = stackSize == 0 ? 0 : board.stateVertex(site, stackSize - 1);
            if (site > 0)
                serialized.append('|');
            serialized.append(SITE_NAMES[site]).append(':').append(result.states[site])
                .append(':').append(result.p1Counts[site]).append(':').append(result.p2Counts[site]);
        }
        result.serialized = serialized.toString();
        return result;
    }

    private static boolean samePointStates(final BoardSnapshot left, final BoardSnapshot right)
    {
        for (int site = 0; site < SITE_NAMES.length; ++site)
            if (left.states[site] != right.states[site])
                return false;
        return true;
    }

    private static void validateUpdatedStates(final BoardSnapshot board, final List<String> targets)
    {
        final Set<Integer> touched = new HashSet<>();
        for (final String target : targets)
            touched.add(Integer.valueOf(siteIndex(target)));
        for (final Integer siteValue : touched)
        {
            final int site = siteValue.intValue();
            final int expected;
            if (board.p1Counts[site] == 3)
                expected = 3;
            else if (board.p2Counts[site] == 3)
                expected = 4;
            else if (board.p1Counts[site] > board.p2Counts[site])
                expected = 1;
            else if (board.p2Counts[site] > board.p1Counts[site])
                expected = 2;
            else
                expected = 0;
            if (board.states[site] != expected)
                throw new IllegalStateException("Third-placement Point update mismatch at " + SITE_NAMES[site]);
        }
    }

    private static int pointState(final Context context, final int site)
    {
        final ContainerState board = context.containerState(0);
        final int size = board.sizeStackVertex(site);
        return size == 0 ? 0 : board.stateVertex(site, size - 1);
    }

    private static int siteIndex(final String name)
    {
        for (int index = 0; index < SITE_NAMES.length; ++index)
            if (SITE_NAMES[index].equals(name))
                return index;
        throw new IllegalArgumentException("Unknown site " + name);
    }

    private static String spatial(final String name)
    {
        final int size = name.charAt(0) == 'S' ? 5 : 4;
        final int row = Character.digit(name.charAt(1), 10);
        final int column = Character.digit(name.charAt(2), 10);
        final int boundaries = (row == 0 || row == size - 1 ? 1 : 0)
            + (column == 0 || column == size - 1 ? 1 : 0);
        return boundaries == 2 ? "corner" : boundaries == 1 ? "edge" : "central";
    }

    private static String csvHeader()
    {
        return String.join(",",
            "position_id", "prefix_placement_count", "source_trial", "mover",
            "ending_mover",
            "requested_iteration_budget", "effective_iteration_budget",
            "repetition_id", "seed", "ordered_sequence", "placement_targets",
            "supply_placement_sites", "objective_placement_sites", "supply_source_sites",
            "spatial_categories", "secured_supply_transitions",
            "unresolved_supply_transitions", "legal_move_counts",
            "placement_runtime_ms", "turn_runtime_ms", "starting_board_state",
            "resulting_turn_state", "trial_path"
        );
    }

    private static String join(final List<String> values)
    {
        return String.join(";", values);
    }

    private static String csv(final List<String> fields)
    {
        final StringBuilder result = new StringBuilder();
        for (int index = 0; index < fields.size(); ++index)
        {
            if (index > 0)
                result.append(',');
            result.append('"').append(fields.get(index).replace("\"", "\"\"")).append('"');
        }
        return result.toString();
    }

    private static String relativePath(final Path path) throws Exception
    {
        final Path repository = Path.of("").toRealPath();
        return repository.relativize(path.toAbsolutePath().normalize()).toString().replace('\\', '/');
    }

    private static String sha256(final Path path) throws Exception
    {
        final MessageDigest digest = MessageDigest.getInstance("SHA-256");
        final byte[] bytes = Files.readAllBytes(path);
        final byte[] hash = digest.digest(bytes);
        final StringBuilder result = new StringBuilder();
        for (final byte value : hash)
            result.append(String.format(Locale.ROOT, "%02x", value & 0xff));
        return result.toString();
    }

    private static String prefixHash(final Path path, final int prefix) throws Exception
    {
        final StringBuilder value = new StringBuilder();
        int count = 0;
        for (final String line : Files.readAllLines(path, StandardCharsets.UTF_8))
        {
            if (line.startsWith("Move="))
            {
                value.append(line).append('\n');
                if (++count == prefix)
                    break;
            }
        }
        if (count != prefix)
            throw new IllegalStateException("Not enough moves for prefix hash.");
        final MessageDigest digest = MessageDigest.getInstance("SHA-256");
        final byte[] hash = digest.digest(value.toString().getBytes(StandardCharsets.UTF_8));
        final StringBuilder result = new StringBuilder();
        for (final byte item : hash)
            result.append(String.format(Locale.ROOT, "%02x", item & 0xff));
        return result.toString();
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

    private static final class BoardSnapshot
    {
        final int[] states = new int[SITE_NAMES.length];
        final int[] p1Counts = new int[SITE_NAMES.length];
        final int[] p2Counts = new int[SITE_NAMES.length];
        int totalPieces;
        String serialized;
    }
}
