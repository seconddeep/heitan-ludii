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

/** Legally replays frozen trials and emits compact Objective snapshots. */
public final class HeitanLateGameReplay
{
    private static final Pattern INDEX = Pattern.compile(".*-(\\d{4})\\.trl");
    private static final List<String> REGIONS = List.of("LL","LM","LH","ML","MM","MH","HL","HM","HH");

    public static void main(String[] args) throws Exception
    {
        if (args.length != 8)
        {
            System.err.println("Usage: HeitanLateGameReplay <game> <board> <id> <iterations> <trials-dir> <turn-snapshots.csv> <objective-effects.csv> <append>");
            System.exit(2);
        }
        File gameFile = new File(args[0]).getCanonicalFile();
        String board = args[1], id = args[2];
        int iterations = Integer.parseInt(args[3]);
        int side = board.equals("3x3") ? 3 : board.equals("4x4") ? 4 : board.equals("6x6") ? 6 : 0;
        if (side == 0) throw new IllegalArgumentException("unknown board " + board);
        BoardSpec spec = new BoardSpec(side);
        Game game = GameLoader.loadGameFromFile(gameFile, List.of("Board/" + board));
        if (game == null || game.board().graph().vertices().size() != spec.sites) throw new IllegalStateException("wrong board loaded");
        boolean append = Boolean.parseBoolean(args[7]);
        try (BufferedWriter turns = writer(Path.of(args[5]), append); BufferedWriter effects = writer(Path.of(args[6]), append))
        {
            if (!append)
            {
                row(turns, List.of("board","experiment_id","iteration_limit","game_index","turn_number","progress","mover","p1_placements_so_far","p2_placements_so_far","objective_snapshot"));
                row(effects, List.of("board","experiment_id","iteration_limit","game_index","turn_number","progress","placement_number","mover","target","region","p1_placements_before","p2_placements_before","p1_placements_after","p2_placements_after","target_state_before","target_state_after_move","target_state_turn_end","target_p1_before","target_p2_before","target_p1_after_move","target_p2_after_move","target_p1_turn_end","target_p2_turn_end","objective_snapshot_before","objective_snapshot_after_move","objective_snapshot_turn_end"));
            }
            List<Path> files;
            try (Stream<Path> stream = Files.list(Path.of(args[4]))) { files = stream.filter(p -> p.toString().endsWith(".trl")).sorted().toList(); }
            if (files.isEmpty()) throw new IllegalStateException("no trials");
            for (Path file : files) replay(game, spec, board, id, iterations, file, turns, effects);
            System.out.printf(Locale.ROOT, "late-game replay %s/%s: %d games%n", board, id, files.size());
        }
    }

    private static void replay(Game game, BoardSpec spec, String board, String id, int iterations, Path path, BufferedWriter turns, BufferedWriter effects) throws Exception
    {
        Matcher matcher = INDEX.matcher(path.getFileName().toString());
        if (!matcher.matches()) throw new IllegalArgumentException("missing game index " + path);
        int gameIndex = Integer.parseInt(matcher.group(1));
        Trial source = MatchRecord.loadMatchRecordFromTextFile(path.toFile(), game).trial();
        if (source.numMoves() != spec.moves || source.numTurns() != spec.turns || !source.over() || !"NaturalEnd".equals(source.status().endType().toString())) throw new IllegalStateException("invalid source " + path);
        Trial replay = new Trial(game); Context context = new Context(game, replay); game.start(context);
        int sourceMove = 0; int[] placed = new int[2];
        for (int turn = 1; turn <= spec.turns; turn++)
        {
            int mover = context.state().mover(); double progress = turn / (double)spec.turns;
            List<Effect> pending = new ArrayList<>();
            for (int placement = 1; placement <= 3; placement++)
            {
                Move recorded = source.getMove(sourceMove++), legal = legal(game, context, recorded);
                if (legal == null || context.state().mover() != mover) throw new IllegalStateException("illegal replay move " + sourceMove + " in " + path);
                Decision d = decision(legal, spec); Snapshot before = snapshot(context, spec);
                int[] placedBefore = placed.clone();
                game.apply(context, legal); placed[mover - 1]++;
                Snapshot after = snapshot(context, spec);
                if (d.target >= spec.supplies) pending.add(new Effect(placement, mover, d.target, placedBefore, placed.clone(), before, after));
            }
            Snapshot end = snapshot(context, spec);
            row(turns, List.of(board,id,Integer.toString(iterations),Integer.toString(gameIndex),Integer.toString(turn),decimal(progress),Integer.toString(mover),Integer.toString(placed[0]),Integer.toString(placed[1]),end.objectiveSignature(spec)));
            for (Effect e : pending)
            {
                row(effects, List.of(board,id,Integer.toString(iterations),Integer.toString(gameIndex),Integer.toString(turn),decimal(progress),Integer.toString(e.placement),Integer.toString(e.mover),spec.name(e.target),REGIONS.get(spec.regionIndex(e.target)),Integer.toString(e.beforePlaced[0]),Integer.toString(e.beforePlaced[1]),Integer.toString(e.afterPlaced[0]),Integer.toString(e.afterPlaced[1]),Integer.toString(e.before.state[e.target]),Integer.toString(e.after.state[e.target]),Integer.toString(end.state[e.target]),Integer.toString(e.before.p1[e.target]),Integer.toString(e.before.p2[e.target]),Integer.toString(e.after.p1[e.target]),Integer.toString(e.after.p2[e.target]),Integer.toString(end.p1[e.target]),Integer.toString(end.p2[e.target]),e.before.objectiveSignature(spec),e.after.objectiveSignature(spec),end.objectiveSignature(spec)));
            }
        }
        if (sourceMove != spec.moves || !replay.over() || replay.status().winner() != source.status().winner()) throw new IllegalStateException("outcome mismatch " + path);
        if (placed[0] != spec.pieces || placed[1] != spec.pieces) throw new IllegalStateException("remaining-piece mismatch " + path);
        int[] score = spec.score(snapshot(context, spec));
        if (score[0] != context.score(1) || score[1] != context.score(2)) throw new IllegalStateException("score mismatch " + path);
    }

    private static Move legal(Game game, Context context, Move recorded)
    {
        for (Move move : game.moves(context).moves()) if (move.mover()==recorded.mover() && move.from()==recorded.from() && move.to()==recorded.to()) return move;
        return null;
    }
    private static Decision decision(Move move, BoardSpec spec) { return move.from() >= spec.supplies ? new Decision(move.from()) : new Decision(move.to()); }
    private static Snapshot snapshot(Context context, BoardSpec spec)
    {
        Snapshot s = new Snapshot(spec.sites); ContainerState b = context.containerState(0);
        for (int site=0; site<spec.sites; site++)
        {
            int size=b.sizeStackVertex(site);
            for (int level=0; level<size; level++) { int who=b.whoVertex(site,level); if(who==1)s.p1[site]++; else if(who==2)s.p2[site]++; }
            s.state[site]=size==0?0:b.stateVertex(site,size-1);
        }
        return s;
    }
    private static BufferedWriter writer(Path path, boolean append) throws IOException { Files.createDirectories(path.toAbsolutePath().getParent()); return Files.newBufferedWriter(path,StandardCharsets.UTF_8,StandardOpenOption.CREATE,StandardOpenOption.WRITE,append?StandardOpenOption.APPEND:StandardOpenOption.TRUNCATE_EXISTING); }
    private static void row(BufferedWriter out,List<String> values)throws IOException { for(int i=0;i<values.size();i++){if(i>0)out.write(',');out.write('"');out.write(values.get(i).replace("\"","\"\""));out.write('"');}out.newLine(); }
    private static String decimal(double v){return String.format(Locale.ROOT,"%.6f",v);}

    private record Decision(int target) {}
    private record Effect(int placement,int mover,int target,int[] beforePlaced,int[] afterPlaced,Snapshot before,Snapshot after) {}
    private static final class Snapshot
    {
        final int[] state,p1,p2; Snapshot(int sites){state=new int[sites];p1=new int[sites];p2=new int[sites];}
        String objectiveSignature(BoardSpec spec){StringBuilder b=new StringBuilder();for(int i=spec.supplies;i<spec.sites;i++){if(i>spec.supplies)b.append('|');b.append(state[i]).append(':').append(p1[i]).append(':').append(p2[i]);}return b.toString();}
    }
    private static final class BoardSpec
    {
        final int side,supplySide,supplies,objectives,sites,moves,turns,pieces,advantageWeight,securedWeight;
        BoardSpec(int side){this.side=side;supplySide=side+1;supplies=supplySide*supplySide;objectives=side*side;sites=supplies+objectives;moves=side==3?54:side==4?72:144;turns=moves/3;pieces=moves/2;advantageWeight=pieces+1;securedWeight=objectives*advantageWeight+pieces+1;}
        String name(int site){return site<supplies?"S"+(site/supplySide)+(site%supplySide):"O"+((site-supplies)/side)+((site-supplies)%side);}
        int regionIndex(int site){boolean supply=site<supplies;int local=supply?site:site-supplies,s=supply?supplySide:side,row=local/s,col=local%s;double x=supply?col/(double)(supplySide-1):(col+.5)/side,y=supply?row/(double)(supplySide-1):(row+.5)/side;return axis(y)*3+axis(x);}
        int axis(double v){double l=Math.abs(v-1.0/6),m=Math.abs(v-.5),h=Math.abs(v-5.0/6);if(m<=l&&m<=h)return 1;return l<h?0:2;}
        int[] score(Snapshot s){int[] r=new int[2];for(int i=supplies;i<sites;i++){if(s.state[i]==3)r[0]+=securedWeight;else if(s.state[i]==4)r[1]+=securedWeight;else if(s.state[i]==1)r[0]+=advantageWeight;else if(s.state[i]==2)r[1]+=advantageWeight;r[0]+=s.p1[i];r[1]+=s.p2[i];}return r;}
    }
}
