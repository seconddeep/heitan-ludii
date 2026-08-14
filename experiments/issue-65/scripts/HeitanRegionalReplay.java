package heitan.experiments;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.regex.*;
import java.util.stream.Stream;
import game.Game;
import manager.utils.game_logs.MatchRecord;
import other.GameLoader;
import other.context.Context;
import other.move.Move;
import other.state.container.ContainerState;
import other.trial.Trial;

/** Legally replay validated Heitan trials into turn-level regional tables. */
public final class HeitanRegionalReplay
{
    private static final Pattern INDEX = Pattern.compile(".*-(\\d{4})\\.trl");
    private static final List<String> REGIONS = List.of("LL","LM","LH","ML","MM","MH","HL","HM","HH");

    public static void main(String[] args) throws Exception
    {
        if (args.length != 10)
        {
            System.err.println("Usage: HeitanRegionalReplay <game> <board> <id> <iterations> <trials-dir> <games.csv> <placements.csv> <regional-states.csv> <opportunities.csv> <append>");
            System.exit(2);
        }
        File gameFile = new File(args[0]).getCanonicalFile();
        String boardName = args[1], id = args[2];
        int iterations = Integer.parseInt(args[3]);
        Path trials = Path.of(args[4]).toAbsolutePath().normalize();
        boolean append = Boolean.parseBoolean(args[9]);
        int side = boardName.equals("3x3") ? 3 : boardName.equals("4x4") ? 4 : boardName.equals("6x6") ? 6 : 0;
        if (side == 0) throw new IllegalArgumentException("board must be 3x3, 4x4, or 6x6");
        BoardSpec spec = new BoardSpec(side);
        Game game = GameLoader.loadGameFromFile(gameFile, List.of("Board/" + boardName));
        if (game == null || game.board().graph().vertices().size() != spec.sites)
            throw new IllegalStateException("Wrong board loaded: " + boardName);

        try (BufferedWriter games = writer(Path.of(args[5]), append);
             BufferedWriter placements = writer(Path.of(args[6]), append);
             BufferedWriter states = writer(Path.of(args[7]), append);
             BufferedWriter opportunities = writer(Path.of(args[8]), append))
        {
            if (!append)
            {
                row(games, List.of("board","experiment_id","iteration_limit","game_index","winner","moves","turns","end_type","final_p1_score","final_p2_score","trial_file"));
                row(placements, List.of("board","experiment_id","iteration_limit","game_index","turn_number","progress","placement_number","mover","target","target_type","supply_source","region"));
                row(states, List.of("board","experiment_id","iteration_limit","game_index","turn_number","progress","mover","region","turn_p1_placements","turn_p2_placements","cumulative_p1_placements","cumulative_p2_placements","p1_controlled_supply","p2_controlled_supply","p1_secured_supply","p2_secured_supply","p1_advantage_objective","p2_advantage_objective","p1_secured_objective","p2_secured_objective","p1_objective_pieces","p2_objective_pieces","p1_unsecured_presence","p2_unsecured_presence","local_lead","supply_points","objectives","total_points","regional_capacity_share"));
                row(opportunities, List.of("board","experiment_id","iteration_limit","game_index","turn_number","progress","mover","region","legal_target_count","total_legal_target_count","regional_opportunity_share"));
            }
            List<Path> files;
            try (Stream<Path> stream = Files.list(trials))
            {
                files = stream.filter(p -> p.getFileName().toString().endsWith(".trl")).sorted().toList();
            }
            if (files.isEmpty()) throw new IllegalStateException("No trials in " + trials);
            for (Path file : files) replay(game, spec, boardName, id, iterations, file, games, placements, states, opportunities);
            System.out.printf(Locale.ROOT, "replayed %s/%s: %d games%n", boardName, id, files.size());
        }
    }

    private static void replay(Game game, BoardSpec spec, String boardName, String id, int iterations, Path path,
        BufferedWriter games, BufferedWriter placements, BufferedWriter states, BufferedWriter opportunities) throws Exception
    {
        Matcher matcher = INDEX.matcher(path.getFileName().toString());
        if (!matcher.matches()) throw new IllegalArgumentException("No game index in " + path);
        int gameIndex = Integer.parseInt(matcher.group(1));
        Trial source = MatchRecord.loadMatchRecordFromTextFile(path.toFile(), game).trial();
        if (source.numMoves() != spec.moves || source.numTurns() != spec.turns || !source.over() || !"NaturalEnd".equals(source.status().endType().toString()))
            throw new IllegalStateException("Incomplete source " + path);
        Trial replay = new Trial(game);
        Context context = new Context(game, replay);
        game.start(context);
        int sourceMove = 0;
        int[][] cumulative = new int[2][REGIONS.size()];

        for (int turn = 1; turn <= spec.turns; turn++)
        {
            int mover = context.state().mover();
            double progress = turn / (double) spec.turns;
            writeOpportunities(game, context, spec, boardName, id, iterations, gameIndex, turn, progress, mover, opportunities);
            Snapshot before = snapshot(context, spec);
            int[][] turnPlacements = new int[2][REGIONS.size()];
            for (int placement = 1; placement <= 3; placement++)
            {
                if (context.state().mover() != mover) throw new IllegalStateException("Mover changed early in " + path);
                Move recorded = source.getMove(sourceMove++);
                Move legal = legal(game, context, recorded);
                if (legal == null) throw new IllegalStateException("Illegal recorded move " + sourceMove + " in " + path);
                Decision decision = decision(legal, spec);
                int region = spec.regionIndex(decision.target);
                turnPlacements[mover - 1][region]++;
                cumulative[mover - 1][region]++;
                row(placements, List.of(boardName,id,Integer.toString(iterations),Integer.toString(gameIndex),Integer.toString(turn),decimal(progress),Integer.toString(placement),Integer.toString(mover),spec.name(decision.target),decision.target < spec.supplies ? "supply" : "objective",decision.source < 0 ? "" : spec.name(decision.source),REGIONS.get(region)));
                game.apply(context, legal);
            }
            Snapshot after = snapshot(context, spec);
            if (after.total != before.total + 3) throw new IllegalStateException("Turn did not add 3 pieces " + path);
            for (int region = 0; region < REGIONS.size(); region++)
            {
                RegionState r = spec.aggregate(after, region);
                row(states, List.of(boardName,id,Integer.toString(iterations),Integer.toString(gameIndex),Integer.toString(turn),decimal(progress),Integer.toString(mover),REGIONS.get(region),Integer.toString(turnPlacements[0][region]),Integer.toString(turnPlacements[1][region]),Integer.toString(cumulative[0][region]),Integer.toString(cumulative[1][region]),Integer.toString(r.p1ControlledSupply),Integer.toString(r.p2ControlledSupply),Integer.toString(r.p1SecuredSupply),Integer.toString(r.p2SecuredSupply),Integer.toString(r.p1AdvantageObjective),Integer.toString(r.p2AdvantageObjective),Integer.toString(r.p1SecuredObjective),Integer.toString(r.p2SecuredObjective),Integer.toString(r.p1ObjectivePieces),Integer.toString(r.p2ObjectivePieces),Integer.toString(r.p1UnsecuredPresence),Integer.toString(r.p2UnsecuredPresence),Integer.toString(r.lead()),Integer.toString(spec.supplyCapacity[region]),Integer.toString(spec.objectiveCapacity[region]),Integer.toString(spec.capacity[region]),decimal(spec.capacity[region] / (double) spec.sites)));
            }
        }
        if (sourceMove != spec.moves || !replay.over() || replay.status().winner() != source.status().winner())
            throw new IllegalStateException("Replay outcome differs " + path);
        Snapshot end = snapshot(context, spec);
        int[] score = spec.score(end);
        if (score[0] != context.score(1) || score[1] != context.score(2)) throw new IllegalStateException("Replay score differs " + path);
        row(games, List.of(boardName,id,Integer.toString(iterations),Integer.toString(gameIndex),Integer.toString(replay.status().winner()),Integer.toString(replay.numMoves()),Integer.toString(replay.numTurns()),replay.status().endType().toString(),Integer.toString(score[0]),Integer.toString(score[1]),relative(path)));
    }

    private static void writeOpportunities(Game game, Context context, BoardSpec spec, String boardName, String id,
        int iterations, int gameIndex, int turn, double progress, int mover, BufferedWriter out) throws IOException
    {
        Set<Integer> targets = new HashSet<>();
        for (Move move : game.moves(context).moves()) targets.add(decision(move, spec).target);
        if (targets.isEmpty()) throw new IllegalStateException("No legal target at turn start");
        int[] counts = new int[REGIONS.size()];
        for (int target : targets) counts[spec.regionIndex(target)]++;
        for (int region = 0; region < REGIONS.size(); region++)
            row(out, List.of(boardName,id,Integer.toString(iterations),Integer.toString(gameIndex),Integer.toString(turn),decimal(progress),Integer.toString(mover),REGIONS.get(region),Integer.toString(counts[region]),Integer.toString(targets.size()),decimal(counts[region] / (double) targets.size())));
    }

    private static Move legal(Game game, Context context, Move recorded)
    {
        for (Move move : game.moves(context).moves())
            if (move.mover() == recorded.mover() && move.from() == recorded.from() && move.to() == recorded.to()) return move;
        return null;
    }
    private static Decision decision(Move move, BoardSpec spec) { return move.from() >= spec.supplies ? new Decision(move.from(), move.to()) : new Decision(move.to(), -1); }
    private static Snapshot snapshot(Context context, BoardSpec spec)
    {
        Snapshot s = new Snapshot(spec.sites);
        ContainerState board = context.containerState(0);
        for (int site = 0; site < spec.sites; site++)
        {
            int size = board.sizeStackVertex(site);
            s.total += size;
            for (int level = 0; level < size; level++)
            {
                if (board.whoVertex(site, level) == 1) s.p1[site]++;
                else if (board.whoVertex(site, level) == 2) s.p2[site]++;
            }
            s.state[site] = size == 0 ? 0 : board.stateVertex(site, size - 1);
        }
        return s;
    }
    private static BufferedWriter writer(Path path, boolean append) throws IOException
    {
        Files.createDirectories(path.toAbsolutePath().getParent());
        return Files.newBufferedWriter(path, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.WRITE, append ? StandardOpenOption.APPEND : StandardOpenOption.TRUNCATE_EXISTING);
    }
    private static void row(BufferedWriter out, List<String> values) throws IOException
    {
        for (int i = 0; i < values.size(); i++)
        {
            if (i > 0) out.write(',');
            out.write('"'); out.write(values.get(i).replace("\"", "\"\"")); out.write('"');
        }
        out.newLine();
    }
    private static String decimal(double value) { return String.format(Locale.ROOT, "%.6f", value); }
    private static String relative(Path path) { return Path.of("").toAbsolutePath().normalize().relativize(path.toAbsolutePath().normalize()).toString().replace('\\','/'); }

    private static final class Decision { final int target, source; Decision(int target, int source) { this.target = target; this.source = source; } }
    private static final class Snapshot { final int[] state, p1, p2; int total; Snapshot(int sites) { state = new int[sites]; p1 = new int[sites]; p2 = new int[sites]; } }
    private static final class RegionState
    {
        int p1ControlledSupply, p2ControlledSupply, p1SecuredSupply, p2SecuredSupply;
        int p1AdvantageObjective, p2AdvantageObjective, p1SecuredObjective, p2SecuredObjective;
        int p1ObjectivePieces, p2ObjectivePieces, p1UnsecuredPresence, p2UnsecuredPresence;
        int lead()
        {
            int c = Integer.compare(p1SecuredObjective, p2SecuredObjective);
            if (c == 0) c = Integer.compare(p1AdvantageObjective, p2AdvantageObjective);
            if (c == 0) c = Integer.compare(p1ObjectivePieces, p2ObjectivePieces);
            return Integer.compare(c, 0);
        }
    }
    private static final class BoardSpec
    {
        final int objectiveSide, supplySide, supplies, objectives, sites, moves, turns, advantageWeight, securedWeight;
        final int[] supplyCapacity = new int[REGIONS.size()], objectiveCapacity = new int[REGIONS.size()], capacity = new int[REGIONS.size()];
        BoardSpec(int objectiveSide)
        {
            this.objectiveSide = objectiveSide;
            supplySide = objectiveSide + 1; supplies = supplySide * supplySide; objectives = objectiveSide * objectiveSide; sites = supplies + objectives;
            moves = objectiveSide == 3 ? 54 : objectiveSide == 4 ? 72 : 144; turns = moves / 3;
            int pieces = moves / 2; advantageWeight = pieces + 1; securedWeight = objectives * advantageWeight + pieces + 1;
            for (int site = 0; site < sites; site++) { int r = regionIndex(site); capacity[r]++; if (site < supplies) supplyCapacity[r]++; else objectiveCapacity[r]++; }
        }
        String name(int site) { return site < supplies ? "S" + (site / supplySide) + (site % supplySide) : "O" + ((site - supplies) / objectiveSide) + ((site - supplies) % objectiveSide); }
        int regionIndex(int site)
        {
            boolean supply = site < supplies; int local = supply ? site : site - supplies, side = supply ? supplySide : objectiveSide, row = local / side, column = local % side;
            double x = supply ? column / (double)(supplySide - 1) : (column + .5) / objectiveSide;
            double y = supply ? row / (double)(supplySide - 1) : (row + .5) / objectiveSide;
            return axis(y) * 3 + axis(x);
        }
        private int axis(double value)
        {
            double low = Math.abs(value - 1.0/6), middle = Math.abs(value - .5), high = Math.abs(value - 5.0/6);
            if (middle <= low && middle <= high) return 1;
            return low < high ? 0 : 2;
        }
        RegionState aggregate(Snapshot s, int region)
        {
            RegionState r = new RegionState();
            for (int site = 0; site < sites; site++)
            {
                if (regionIndex(site) != region) continue;
                int state = s.state[site];
                if (state != 3 && state != 4) { r.p1UnsecuredPresence += s.p1[site]; r.p2UnsecuredPresence += s.p2[site]; }
                if (site < supplies)
                {
                    if (state == 1) r.p1ControlledSupply++; else if (state == 2) r.p2ControlledSupply++;
                    else if (state == 3) r.p1SecuredSupply++; else if (state == 4) r.p2SecuredSupply++;
                }
                else
                {
                    if (state == 1) r.p1AdvantageObjective++; else if (state == 2) r.p2AdvantageObjective++;
                    else if (state == 3) r.p1SecuredObjective++; else if (state == 4) r.p2SecuredObjective++;
                    r.p1ObjectivePieces += s.p1[site]; r.p2ObjectivePieces += s.p2[site];
                }
            }
            return r;
        }
        int[] score(Snapshot s)
        {
            int[] result = new int[2];
            for (int site = supplies; site < sites; site++)
            {
                if (s.state[site] == 3) result[0] += securedWeight; else if (s.state[site] == 4) result[1] += securedWeight;
                else if (s.state[site] == 1) result[0] += advantageWeight; else if (s.state[site] == 2) result[1] += advantageWeight;
                result[0] += s.p1[site]; result[1] += s.p2[site];
            }
            return result;
        }
    }
}
