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

/** Legally replay one 4x4 or 6x6 data set and append normalized raw data. */
public final class HeitanScaleReplay
{
    private static final Pattern INDEX = Pattern.compile(".*-(\\d{4})\\.trl");

    public static void main(final String[] args) throws Exception
    {
        if (args.length != 9)
        {
            System.err.println("Usage: HeitanScaleReplay <game> <board> <id> <iterations> <trials-dir> <games.csv> <placements.csv> <turn-states.csv> <append>");
            System.exit(2);
        }
        final File gameFile = new File(args[0]).getCanonicalFile();
        final String boardName = args[1], id = args[2];
        final int iterations = Integer.parseInt(args[3]);
        final Path trials = Path.of(args[4]).toRealPath();
        final boolean append = Boolean.parseBoolean(args[8]);
        final BoardSpec spec = boardName.equals("6x6") ? new BoardSpec(6) : boardName.equals("4x4") ? new BoardSpec(4) : null;
        if (spec == null) throw new IllegalArgumentException("board must be 4x4 or 6x6");
        final List<String> options = boardName.equals("6x6") ? List.of("Board/6x6") : List.of("Board/4x4");
        final Game game = GameLoader.loadGameFromFile(gameFile, options);
        if (game == null || game.board().graph().vertices().size() != spec.sites) throw new IllegalStateException("Wrong board loaded");
        try (BufferedWriter games = writer(Path.of(args[5]), append);
             BufferedWriter placements = writer(Path.of(args[6]), append);
             BufferedWriter states = writer(Path.of(args[7]), append))
        {
            if (!append)
            {
                row(games, List.of("board","experiment_id","iteration_limit","game_index","winner","moves","turns","end_type","final_p1_score","final_p2_score","trial_file"));
                row(placements, List.of("board","experiment_id","iteration_limit","game_index","turn_number","progress","placement_number","mover","target","target_type","supply_source","region"));
                row(states, List.of("board","experiment_id","iteration_limit","game_index","turn_number","progress","mover","point","point_type","region","state_at_turn_start","p1_at_turn_start","p2_at_turn_start","state_at_turn_end","p1_at_turn_end","p2_at_turn_end"));
            }
            final List<Path> files;
            try (Stream<Path> stream = Files.list(trials)) { files = stream.filter(p -> p.getFileName().toString().endsWith(".trl")).sorted().toList(); }
            if (files.isEmpty()) throw new IllegalStateException("No trials in " + trials);
            for (final Path file : files) replay(game, spec, boardName, id, iterations, file, games, placements, states);
            System.out.printf(Locale.ROOT, "replayed %s/%s: %d games%n", boardName, id, files.size());
        }
    }

    private static void replay(final Game game, final BoardSpec spec, final String boardName,
        final String id, final int iterations, final Path path, final BufferedWriter games,
        final BufferedWriter placements, final BufferedWriter states) throws Exception
    {
        final Matcher matcher = INDEX.matcher(path.getFileName().toString());
        if (!matcher.matches()) throw new IllegalArgumentException("No game index in " + path);
        final int gameIndex = Integer.parseInt(matcher.group(1));
        final Trial source = MatchRecord.loadMatchRecordFromTextFile(path.toFile(), game).trial();
        if (source.numMoves() != spec.moves || source.numTurns() != spec.turns || !source.over()) throw new IllegalStateException("Incomplete source " + path);
        final Trial replay = new Trial(game); final Context context = new Context(game, replay); game.start(context);
        int sourceMove = 0;
        for (int turn = 1; turn <= spec.turns; ++turn)
        {
            final int mover = context.state().mover(); final Snapshot before = snapshot(context, spec);
            for (int placement = 1; placement <= 3; ++placement)
            {
                if (context.state().mover() != mover) throw new IllegalStateException("Mover changed early in " + path);
                final Move recorded = source.getMove(sourceMove++); final Move legal = legal(game, context, recorded);
                if (legal == null) throw new IllegalStateException("Illegal recorded move " + sourceMove + " in " + path);
                final Decision decision = decision(legal, spec);
                row(placements, List.of(boardName,id,Integer.toString(iterations),Integer.toString(gameIndex),Integer.toString(turn),decimal(turn/(double)spec.turns),Integer.toString(placement),Integer.toString(mover),spec.name(decision.target),decision.target < spec.supplies ? "supply" : "objective",decision.source < 0 ? "" : spec.name(decision.source),spec.region(decision.target)));
                game.apply(context, legal);
            }
            final Snapshot after = snapshot(context, spec);
            if (after.total != before.total + 3) throw new IllegalStateException("Turn did not add 3 pieces " + path);
            for (int site = 0; site < spec.sites; ++site)
                row(states, List.of(boardName,id,Integer.toString(iterations),Integer.toString(gameIndex),Integer.toString(turn),decimal(turn/(double)spec.turns),Integer.toString(mover),spec.name(site),site < spec.supplies ? "supply" : "objective",spec.region(site),Integer.toString(before.state[site]),Integer.toString(before.p1[site]),Integer.toString(before.p2[site]),Integer.toString(after.state[site]),Integer.toString(after.p1[site]),Integer.toString(after.p2[site])));
        }
        if (!replay.over() || replay.status().winner() != source.status().winner()) throw new IllegalStateException("Replay outcome differs " + path);
        final Snapshot end = snapshot(context, spec); final int[] score = spec.score(end);
        if (score[0] != context.score(1) || score[1] != context.score(2)) throw new IllegalStateException("Replay score differs " + path);
        row(games, List.of(boardName,id,Integer.toString(iterations),Integer.toString(gameIndex),Integer.toString(replay.status().winner()),Integer.toString(replay.numMoves()),Integer.toString(replay.numTurns()),replay.status().endType().toString(),Integer.toString(score[0]),Integer.toString(score[1]),relative(path)));
    }

    private static Move legal(final Game game, final Context context, final Move recorded)
    { for (final Move move : game.moves(context).moves()) if (move.mover()==recorded.mover() && move.from()==recorded.from() && move.to()==recorded.to()) return move; return null; }
    private static Decision decision(final Move move, final BoardSpec spec) { return move.from() >= spec.supplies ? new Decision(move.from(), move.to()) : new Decision(move.to(), -1); }
    private static Snapshot snapshot(final Context context, final BoardSpec spec)
    {
        final Snapshot s = new Snapshot(spec.sites); final ContainerState board = context.containerState(0);
        for (int site=0;site<spec.sites;++site) { final int size=board.sizeStackVertex(site); s.total+=size; for(int level=0;level<size;++level){if(board.whoVertex(site,level)==1)++s.p1[site];else if(board.whoVertex(site,level)==2)++s.p2[site];} s.state[site]=size==0?0:board.stateVertex(site,size-1); }
        return s;
    }
    private static BufferedWriter writer(final Path path, final boolean append) throws IOException { Files.createDirectories(path.toAbsolutePath().getParent()); return Files.newBufferedWriter(path,StandardCharsets.UTF_8,StandardOpenOption.CREATE,StandardOpenOption.WRITE,append?StandardOpenOption.APPEND:StandardOpenOption.TRUNCATE_EXISTING); }
    private static void row(final BufferedWriter out, final List<String> values) throws IOException { for(int i=0;i<values.size();++i){if(i>0)out.write(',');out.write('"');out.write(values.get(i).replace("\"","\"\""));out.write('"');}out.newLine(); }
    private static String decimal(double value){return String.format(Locale.ROOT,"%.6f",value);}
    private static String relative(final Path path) throws IOException{return Path.of("").toRealPath().relativize(path.toRealPath()).toString().replace('\\','/');}

    private static final class Decision { final int target,source; Decision(int target,int source){this.target=target;this.source=source;} }
    private static final class Snapshot { final int[] state,p1,p2; int total; Snapshot(int sites){state=new int[sites];p1=new int[sites];p2=new int[sites];} }
    private static final class BoardSpec
    {
        final int objectiveSide,supplySide,supplies,objectives,sites,moves,turns,advantageWeight,securedWeight;
        BoardSpec(int objectiveSide){this.objectiveSide=objectiveSide;supplySide=objectiveSide+1;supplies=supplySide*supplySide;objectives=objectiveSide*objectiveSide;sites=supplies+objectives;moves=objectiveSide==4?72:144;turns=moves/3;int pieces=moves/2;advantageWeight=pieces+1;securedWeight=objectives*advantageWeight+pieces+1;}
        String name(int site){return site<supplies?"S"+(site/supplySide)+(site%supplySide):"O"+((site-supplies)/objectiveSide)+((site-supplies)%objectiveSide);}
        String region(int site){final boolean supply=site<supplies;final int local=supply?site:site-supplies;final int side=supply?supplySide:objectiveSide;final int row=local/side,column=local%side;final double x=supply?column/(double)(supplySide-1):(column+0.5)/objectiveSide;final double y=supply?row/(double)(supplySide-1):(row+0.5)/objectiveSide;return axis(y)+axis(x);}
        private String axis(double value){final double low=Math.abs(value-1.0/6.0),middle=Math.abs(value-0.5),high=Math.abs(value-5.0/6.0);if(middle<=low&&middle<=high)return"M";return low<high?"L":"H";}
        int[] score(Snapshot s){int[] result=new int[2];for(int site=supplies;site<sites;++site){if(s.state[site]==3)result[0]+=securedWeight;else if(s.state[site]==4)result[1]+=securedWeight;else if(s.state[site]==1)result[0]+=advantageWeight;else if(s.state[site]==2)result[1]+=advantageWeight;result[0]+=s.p1[site];result[1]+=s.p2[site];}return result;}
    }
}
