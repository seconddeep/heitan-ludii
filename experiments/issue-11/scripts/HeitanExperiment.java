package heitan.experiments;

import java.io.BufferedWriter;
import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.SplittableRandom;

import org.apache.commons.rng.core.RandomProviderDefaultState;
import org.apache.commons.rng.core.source64.SplitMix64;

import game.Game;
import main.collections.FastArrayList;
import other.AI;
import other.GameLoader;
import other.context.Context;
import other.move.Move;
import other.state.container.ContainerState;
import other.trial.Trial;
import utils.AIFactory;

/** Reproducible, headless experiment runner for Heitan on Ludii 1.3.14. */
public final class HeitanExperiment
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

    private HeitanExperiment()
    {
        // Utility class.
    }

    public static void main(final String[] args) throws Exception
    {
        if (args.length != 10 && args.length != 11)
        {
            System.err.println(
                "Usage: HeitanExperiment <game.lud> <experiment-id> <black-agent> "
                + "<white-agent> <games> <base-seed> <iteration-limit> "
                + "<max-seconds> <raw.csv> <trials-dir> [game-index-offset]"
            );
            System.exit(2);
        }

        final File gameFile = new File(args[0]).getCanonicalFile();
        final String experimentId = args[1];
        final String blackAgentName = args[2];
        final String whiteAgentName = args[3];
        final int numGames = Integer.parseInt(args[4]);
        final long baseSeed = Long.parseLong(args[5]);
        final int iterationLimit = Integer.parseInt(args[6]);
        final double maxSeconds = Double.parseDouble(args[7]);
        final Path rawOutput = Path.of(args[8]);
        final Path trialsDirectory = Path.of(args[9]);
        final int gameIndexOffset = args.length == 11 ? Integer.parseInt(args[10]) : 0;

        if (!gameFile.isFile())
            throw new IllegalArgumentException("Game file not found: " + gameFile);
        if (numGames <= 0)
            throw new IllegalArgumentException("Number of games must be positive.");

        Files.createDirectories(rawOutput.toAbsolutePath().getParent());
        Files.createDirectories(trialsDirectory);

        final Game game = GameLoader.loadGameFromFile(gameFile);
        if (game == null)
            throw new IllegalStateException("Ludii could not compile " + gameFile);
        if (game.players().count() != 2)
            throw new IllegalStateException("Heitan experiment requires exactly two players.");

        try (BufferedWriter output = Files.newBufferedWriter(
            rawOutput,
            StandardCharsets.UTF_8,
            StandardOpenOption.CREATE,
            StandardOpenOption.TRUNCATE_EXISTING,
            StandardOpenOption.WRITE
        ))
        {
            output.write(csvHeader());
            output.newLine();

            for (int gameIndex = 0; gameIndex < numGames; ++gameIndex)
            {
                final int gameNumber = gameIndexOffset + gameIndex + 1;
                final long seed = baseSeed + gameIndex;
                final Trial trial = new Trial(game);
                final Context context = new Context(game, trial);

                // Seed all randomness owned by the game engine. SeededRandom below has
                // its own deterministic stream because Ludii's RandomAI uses
                // ThreadLocalRandom and cannot be seeded by callers.
                context.rng().restoreState(new SplitMix64(seed).saveState());
                final RandomProviderDefaultState initialRngState =
                    (RandomProviderDefaultState) context.rng().saveState();

                game.start(context);

                final List<AI> agents = new ArrayList<>();
                agents.add(null);
                agents.add(createAgent(blackAgentName, seed, 1, game));
                agents.add(createAgent(whiteAgentName, seed, 2, game));

                for (int player = 1; player <= 2; ++player)
                {
                    agents.get(player).setMaxIterationsPerMove(iterationLimit);
                    agents.get(player).setMaxSecondsPerMove(maxSeconds);
                    agents.get(player).initAI(game, player);
                }

                while (!trial.over())
                {
                    context.model().startNewStep(
                        context,
                        agents,
                        maxSeconds,
                        iterationLimit,
                        -1,
                        0.0
                    );
                }

                final Path trialPath = trialsDirectory.resolve(
                    String.format(Locale.ROOT, "%s-%04d.trl", experimentId, gameNumber)
                );
                trial.saveTrialToTextFile(
                    trialPath.toFile(),
                    gameFile.getPath(),
                    new ArrayList<String>(),
                    initialRngState
                );

                output.write(resultRow(
                    experimentId,
                    gameNumber,
                    seed,
                    blackAgentName,
                    whiteAgentName,
                    iterationLimit,
                    maxSeconds,
                    gameFile.toPath().getParent().getParent(),
                    context,
                    trial,
                    trialPath
                ));
                output.newLine();
                output.flush();

                for (int player = 1; player <= 2; ++player)
                    agents.get(player).closeAI();

                System.out.printf(
                    Locale.ROOT,
                    "%s: %d/%d winner=P%d moves=%d%n",
                    experimentId,
                    gameNumber,
                    gameIndexOffset + numGames,
                    trial.status().winner(),
                    trial.numMoves()
                );
            }
        }
    }

    private static AI createAgent(
        final String name,
        final long gameSeed,
        final int player,
        final Game game
    )
    {
        final AI ai;
        if (name.equalsIgnoreCase("SeededRandom"))
        {
            final long playerSeed = gameSeed ^ (0x9E3779B97F4A7C15L * player);
            ai = new SeededRandomAI(playerSeed);
        }
        else
        {
            ai = AIFactory.createAI(name);
        }

        if (ai == null)
            throw new IllegalArgumentException("Unknown Ludii AI: " + name);
        if (!ai.supportsGame(game))
            throw new IllegalArgumentException("AI does not support Heitan: " + name);
        return ai;
    }

    private static String csvHeader()
    {
        return String.join(",",
            "experiment_id", "game_index", "seed", "black_agent", "white_agent",
            "iteration_limit", "max_seconds_per_move", "completed", "end_type",
            "winner", "moves", "turns", "p1_score", "p2_score",
            "p1_total_pieces", "p2_total_pieces", "p1_supply_pieces",
            "p2_supply_pieces", "p1_objective_pieces", "p2_objective_pieces",
            "p1_secured_supply", "p2_secured_supply", "p1_secured_objectives",
            "p2_secured_objectives", "p1_advantage_objectives",
            "p2_advantage_objectives", "deciding_criterion", "final_board",
            "trial_file"
        );
    }

    private static String resultRow(
        final String experimentId,
        final int gameIndex,
        final long seed,
        final String blackAgent,
        final String whiteAgent,
        final int iterationLimit,
        final double maxSeconds,
        final Path repositoryRoot,
        final Context context,
        final Trial trial,
        final Path trialPath
    ) throws IOException
    {
        final BoardMetrics metrics = boardMetrics(context);
        final int calculatedP1Score = 629 * metrics.p1SecuredObjectives
            + 37 * metrics.p1AdvantageObjectives + metrics.p1ObjectivePieces;
        final int calculatedP2Score = 629 * metrics.p2SecuredObjectives
            + 37 * metrics.p2AdvantageObjectives + metrics.p2ObjectivePieces;

        if (context.score(1) != calculatedP1Score || context.score(2) != calculatedP2Score)
        {
            throw new IllegalStateException(String.format(
                Locale.ROOT,
                "Score mismatch in game %d: Ludii=%d/%d calculated=%d/%d",
                gameIndex,
                context.score(1),
                context.score(2),
                calculatedP1Score,
                calculatedP2Score
            ));
        }

        final List<String> fields = new ArrayList<>();
        fields.add(experimentId);
        fields.add(Integer.toString(gameIndex));
        fields.add(Long.toString(seed));
        fields.add(blackAgent);
        fields.add(whiteAgent);
        fields.add(Integer.toString(iterationLimit));
        fields.add(Double.toString(maxSeconds));
        fields.add(Boolean.toString(trial.over()));
        fields.add(trial.status().endType().toString());
        fields.add(Integer.toString(trial.status().winner()));
        fields.add(Integer.toString(trial.numMoves()));
        fields.add(Integer.toString(trial.numTurns()));
        fields.add(Integer.toString(context.score(1)));
        fields.add(Integer.toString(context.score(2)));
        fields.add(Integer.toString(metrics.p1TotalPieces));
        fields.add(Integer.toString(metrics.p2TotalPieces));
        fields.add(Integer.toString(metrics.p1SupplyPieces));
        fields.add(Integer.toString(metrics.p2SupplyPieces));
        fields.add(Integer.toString(metrics.p1ObjectivePieces));
        fields.add(Integer.toString(metrics.p2ObjectivePieces));
        fields.add(Integer.toString(metrics.p1SecuredSupply));
        fields.add(Integer.toString(metrics.p2SecuredSupply));
        fields.add(Integer.toString(metrics.p1SecuredObjectives));
        fields.add(Integer.toString(metrics.p2SecuredObjectives));
        fields.add(Integer.toString(metrics.p1AdvantageObjectives));
        fields.add(Integer.toString(metrics.p2AdvantageObjectives));
        fields.add(decidingCriterion(metrics));
        fields.add(metrics.finalBoard);
        fields.add(repositoryRoot.toAbsolutePath().normalize()
            .relativize(trialPath.toAbsolutePath().normalize())
            .toString().replace('\\', '/'));
        return csv(fields);
    }

    private static BoardMetrics boardMetrics(final Context context)
    {
        final ContainerState board = context.containerState(0);
        final BoardMetrics result = new BoardMetrics();
        final StringBuilder finalBoard = new StringBuilder();

        for (int site = 0; site < SITE_NAMES.length; ++site)
        {
            int p1Count = 0;
            int p2Count = 0;
            final int stackSize = board.sizeStackVertex(site);
            for (int level = 0; level < stackSize; ++level)
            {
                final int owner = board.whoVertex(site, level);
                if (owner == 1)
                    ++p1Count;
                else if (owner == 2)
                    ++p2Count;
            }

            final int state = stackSize == 0 ? 0 : board.stateVertex(site, stackSize - 1);
            result.p1TotalPieces += p1Count;
            result.p2TotalPieces += p2Count;

            if (site < 25)
            {
                result.p1SupplyPieces += p1Count;
                result.p2SupplyPieces += p2Count;
                if (state == 3)
                    ++result.p1SecuredSupply;
                else if (state == 4)
                    ++result.p2SecuredSupply;
            }
            else
            {
                result.p1ObjectivePieces += p1Count;
                result.p2ObjectivePieces += p2Count;
                if (state == 3)
                    ++result.p1SecuredObjectives;
                else if (state == 4)
                    ++result.p2SecuredObjectives;
                else if (state == 1)
                    ++result.p1AdvantageObjectives;
                else if (state == 2)
                    ++result.p2AdvantageObjectives;
            }

            if (site > 0)
                finalBoard.append('|');
            finalBoard.append(SITE_NAMES[site]).append(':')
                .append(state).append(':').append(p1Count).append(':').append(p2Count);
        }
        result.finalBoard = finalBoard.toString();
        return result;
    }

    private static String decidingCriterion(final BoardMetrics metrics)
    {
        if (metrics.p1SecuredObjectives != metrics.p2SecuredObjectives)
            return "secured_objectives";
        if (metrics.p1AdvantageObjectives != metrics.p2AdvantageObjectives)
            return "advantage_objectives";
        if (metrics.p1ObjectivePieces != metrics.p2ObjectivePieces)
            return "objective_pieces";
        return "draw";
    }

    private static String csv(final List<String> fields)
    {
        final StringBuilder result = new StringBuilder();
        for (int i = 0; i < fields.size(); ++i)
        {
            if (i > 0)
                result.append(',');
            final String value = fields.get(i);
            result.append('"').append(value.replace("\"", "\"\"")).append('"');
        }
        return result.toString();
    }

    private static final class SeededRandomAI extends AI
    {
        private final SplittableRandom random;

        SeededRandomAI(final long seed)
        {
            random = new SplittableRandom(seed);
            friendlyName = "SeededRandom";
        }

        @Override
        public Move selectAction(
            final Game game,
            final Context context,
            final double maxSeconds,
            final int maxIterations,
            final int maxDepth
        )
        {
            final FastArrayList<Move> legalMoves = game.moves(context).moves();
            return legalMoves.get(random.nextInt(legalMoves.size()));
        }
    }

    private static final class BoardMetrics
    {
        int p1TotalPieces;
        int p2TotalPieces;
        int p1SupplyPieces;
        int p2SupplyPieces;
        int p1ObjectivePieces;
        int p2ObjectivePieces;
        int p1SecuredSupply;
        int p2SecuredSupply;
        int p1SecuredObjectives;
        int p2SecuredObjectives;
        int p1AdvantageObjectives;
        int p2AdvantageObjectives;
        String finalBoard;
    }
}
