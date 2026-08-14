package heitan.experiments;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
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

/** Headless runner for the validated Board/6x6 option. */
public final class Heitan6x6Experiment
{
    private static final int SUPPLIES = 49, OBJECTIVES = 36, SITES = 85;
    private static final int PIECES = 72, MOVES = 144, TURNS = 48;
    private static final int ADVANTAGE_WEIGHT = 73, SECURED_WEIGHT = 2701;

    public static void main(final String[] args) throws Exception
    {
        if (args.length != 9 && args.length != 10)
        {
            System.err.println("Usage: Heitan6x6Experiment <game> <id> <agent> <games> <base-seed> <iterations> <raw.csv> <trials-dir> <repo-root> [index-offset]");
            System.exit(2);
        }
        final File gameFile = new File(args[0]).getCanonicalFile();
        final String id = args[1], agentName = args[2];
        final int games = Integer.parseInt(args[3]);
        final long baseSeed = Long.parseLong(args[4]);
        final int iterations = Integer.parseInt(args[5]);
        final Path raw = Path.of(args[6]), trialsDir = Path.of(args[7]);
        final Path repo = Path.of(args[8]).toAbsolutePath().normalize();
        final int offset = args.length == 10 ? Integer.parseInt(args[9]) : 0;
        final List<String> options = List.of("Board/6x6");
        final Game game = GameLoader.loadGameFromFile(gameFile, options);
        if (game == null || game.board().graph().vertices().size() != SITES)
            throw new IllegalStateException("Board/6x6 did not load as an 85-site game.");
        Files.createDirectories(raw.toAbsolutePath().getParent());
        Files.createDirectories(trialsDir);
        try (BufferedWriter out = Files.newBufferedWriter(raw, StandardCharsets.UTF_8))
        {
            row(out, List.of("experiment_id","game_index","seed","agent","iteration_limit","completed","end_type","winner","moves","turns","p1_score","p2_score","p1_total_pieces","p2_total_pieces","p1_supply_pieces","p2_supply_pieces","p1_objective_pieces","p2_objective_pieces","p1_secured_supply","p2_secured_supply","p1_secured_objectives","p2_secured_objectives","p1_advantage_objectives","p2_advantage_objectives","deciding_criterion","final_board","trial_file"));
            for (int index = 0; index < games; ++index)
            {
                final int number = offset + index + 1;
                final long seed = baseSeed + index;
                final Trial trial = new Trial(game);
                final Context context = new Context(game, trial);
                context.rng().restoreState(new SplitMix64(seed).saveState());
                final RandomProviderDefaultState rng = (RandomProviderDefaultState) context.rng().saveState();
                game.start(context);
                final List<AI> agents = new ArrayList<>(Arrays.asList(null,
                    agent(agentName, seed, 1, game), agent(agentName, seed, 2, game)));
                for (int p = 1; p <= 2; ++p) { agents.get(p).setMaxIterationsPerMove(iterations); agents.get(p).setMaxSecondsPerMove(-1.0); agents.get(p).initAI(game, p); }
                while (!trial.over()) context.model().startNewStep(context, agents, -1.0, iterations, -1, 0.0);
                final Path trialPath = trialsDir.resolve(String.format(Locale.ROOT, "%s-%04d.trl", id, number));
                trial.saveTrialToTextFile(trialPath.toFile(), gameFile.getPath(), new ArrayList<>(options), rng);
                final Metrics m = metrics(context);
                validate(context, trial, m);
                row(out, List.of(id,Integer.toString(number),Long.toString(seed),agentName,Integer.toString(iterations),Boolean.toString(trial.over()),trial.status().endType().toString(),Integer.toString(trial.status().winner()),Integer.toString(trial.numMoves()),Integer.toString(trial.numTurns()),Integer.toString(context.score(1)),Integer.toString(context.score(2)),Integer.toString(m.p1Total),Integer.toString(m.p2Total),Integer.toString(m.p1Supply),Integer.toString(m.p2Supply),Integer.toString(m.p1Objective),Integer.toString(m.p2Objective),Integer.toString(m.p1SecSupply),Integer.toString(m.p2SecSupply),Integer.toString(m.p1SecObj),Integer.toString(m.p2SecObj),Integer.toString(m.p1AdvObj),Integer.toString(m.p2AdvObj),criterion(m),m.board,repo.relativize(trialPath.toAbsolutePath().normalize()).toString().replace('\\','/')));
                out.flush();
                for (int p = 1; p <= 2; ++p) agents.get(p).closeAI();
                System.out.printf(Locale.ROOT, "%s %d/%d winner=P%d%n", id, number, offset + games, trial.status().winner());
            }
        }
    }

    private static AI agent(final String name, final long seed, final int player, final Game game)
    {
        final AI result = name.equalsIgnoreCase("SeededRandom") ? new SeededRandom(seed ^ (0x9E3779B97F4A7C15L * player)) : AIFactory.createAI(name);
        if (result == null || !result.supportsGame(game)) throw new IllegalArgumentException("Unsupported AI: " + name);
        return result;
    }

    private static Metrics metrics(final Context context)
    {
        final Metrics m = new Metrics(); final StringBuilder board = new StringBuilder();
        final ContainerState state = context.containerState(0);
        for (int site = 0; site < SITES; ++site)
        {
            int p1 = 0, p2 = 0; final int size = state.sizeStackVertex(site);
            for (int level = 0; level < size; ++level) { if (state.whoVertex(site, level) == 1) ++p1; else if (state.whoVertex(site, level) == 2) ++p2; }
            final int value = size == 0 ? 0 : state.stateVertex(site, size - 1);
            m.p1Total += p1; m.p2Total += p2;
            if (site < SUPPLIES) { m.p1Supply += p1; m.p2Supply += p2; if (value == 3) ++m.p1SecSupply; else if (value == 4) ++m.p2SecSupply; }
            else { m.p1Objective += p1; m.p2Objective += p2; if (value == 3) ++m.p1SecObj; else if (value == 4) ++m.p2SecObj; else if (value == 1) ++m.p1AdvObj; else if (value == 2) ++m.p2AdvObj; }
            if (site > 0) board.append('|'); board.append(name(site)).append(':').append(value).append(':').append(p1).append(':').append(p2);
        }
        m.board = board.toString(); return m;
    }

    private static void validate(final Context c, final Trial t, final Metrics m)
    {
        if (!t.over() || t.numMoves() != MOVES || t.numTurns() != TURNS || m.p1Total != PIECES || m.p2Total != PIECES) throw new IllegalStateException("Natural-end invariant failed.");
        final int p1 = SECURED_WEIGHT*m.p1SecObj + ADVANTAGE_WEIGHT*m.p1AdvObj + m.p1Objective;
        final int p2 = SECURED_WEIGHT*m.p2SecObj + ADVANTAGE_WEIGHT*m.p2AdvObj + m.p2Objective;
        if (c.score(1) != p1 || c.score(2) != p2 || t.status().winner() != (p1 > p2 ? 1 : p2 > p1 ? 2 : 0)) throw new IllegalStateException("Score/winner invariant failed.");
    }
    private static String criterion(final Metrics m) { return m.p1SecObj != m.p2SecObj ? "secured_objectives" : m.p1AdvObj != m.p2AdvObj ? "advantage_objectives" : m.p1Objective != m.p2Objective ? "objective_pieces" : "draw"; }
    private static String name(final int site) { return site < SUPPLIES ? "S"+(site/7)+(site%7) : "O"+((site-SUPPLIES)/6)+((site-SUPPLIES)%6); }
    private static void row(final BufferedWriter out, final List<String> values) throws IOException { for (int i=0;i<values.size();++i) { if(i>0)out.write(','); out.write('"'); out.write(values.get(i).replace("\"","\"\"")); out.write('"'); } out.newLine(); }
    private static final class SeededRandom extends AI { private final SplittableRandom random; SeededRandom(long seed){random=new SplittableRandom(seed);friendlyName="SeededRandom";} @Override public Move selectAction(Game g,Context c,double s,int i,int d){FastArrayList<Move> moves=g.moves(c).moves();return moves.get(random.nextInt(moves.size()));} }
    private static final class Metrics { int p1Total,p2Total,p1Supply,p2Supply,p1Objective,p2Objective,p1SecSupply,p2SecSupply,p1SecObj,p2SecObj,p1AdvObj,p2AdvObj; String board; }
}
