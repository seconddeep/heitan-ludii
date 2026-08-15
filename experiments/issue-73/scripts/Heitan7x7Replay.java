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

/** Legally replays 7x7 trials and emits all frozen scale-analysis raw tables. */
public final class Heitan7x7Replay
{
    private static final Pattern INDEX=Pattern.compile(".*-(\\d{4})\\.trl");
    private static final List<String> REGIONS=List.of("LL","LM","LH","ML","MM","MH","HL","HM","HH");

    public static void main(String[] args)throws Exception
    {
        if(args.length!=12){System.err.println("Usage: Heitan7x7Replay <game> <id> <iterations> <trials-dir> <games.csv> <placements.csv> <point-states.csv> <regional-states.csv> <opportunities.csv> <turn-snapshots.csv> <objective-effects.csv> <append>");System.exit(2);}
        File gameFile=new File(args[0]).getCanonicalFile();String id=args[1];int iterations=Integer.parseInt(args[2]);Path trials=Path.of(args[3]).toAbsolutePath().normalize();boolean append=Boolean.parseBoolean(args[11]);
        BoardSpec spec=new BoardSpec();Game game=GameLoader.loadGameFromFile(gameFile,List.of("Board/7x7"));if(game==null||game.board().graph().vertices().size()!=spec.sites)throw new IllegalStateException("Wrong 7x7 board loaded");
        try(BufferedWriter games=writer(Path.of(args[4]),append);BufferedWriter placements=writer(Path.of(args[5]),append);BufferedWriter pointStates=writer(Path.of(args[6]),append);BufferedWriter regionalStates=writer(Path.of(args[7]),append);BufferedWriter opportunities=writer(Path.of(args[8]),append);BufferedWriter turnSnapshots=writer(Path.of(args[9]),append);BufferedWriter effects=writer(Path.of(args[10]),append)){
            if(!append){
                row(games,List.of("board","experiment_id","iteration_limit","game_index","winner","moves","turns","end_type","final_p1_score","final_p2_score","p1_placements","p2_placements","trial_file"));
                row(placements,List.of("board","experiment_id","iteration_limit","game_index","turn_number","progress","placement_number","mover","target","target_type","supply_source","region"));
                row(pointStates,List.of("board","experiment_id","iteration_limit","game_index","turn_number","progress","mover","point","point_type","region","state_at_turn_start","p1_at_turn_start","p2_at_turn_start","state_at_turn_end","p1_at_turn_end","p2_at_turn_end"));
                row(regionalStates,List.of("board","experiment_id","iteration_limit","game_index","turn_number","progress","mover","region","turn_p1_placements","turn_p2_placements","cumulative_p1_placements","cumulative_p2_placements","p1_controlled_supply","p2_controlled_supply","p1_secured_supply","p2_secured_supply","p1_advantage_objective","p2_advantage_objective","p1_secured_objective","p2_secured_objective","p1_objective_pieces","p2_objective_pieces","p1_unsecured_presence","p2_unsecured_presence","local_lead","supply_points","objectives","total_points","regional_capacity_share"));
                row(opportunities,List.of("board","experiment_id","iteration_limit","game_index","turn_number","progress","mover","region","legal_target_count","total_legal_target_count","regional_opportunity_share"));
                row(turnSnapshots,List.of("board","experiment_id","iteration_limit","game_index","turn_number","progress","mover","p1_placements_so_far","p2_placements_so_far","objective_snapshot"));
                row(effects,List.of("board","experiment_id","iteration_limit","game_index","turn_number","progress","placement_number","mover","target","region","p1_placements_before","p2_placements_before","p1_placements_after","p2_placements_after","target_state_before","target_state_after_move","target_state_turn_end","target_p1_before","target_p2_before","target_p1_after_move","target_p2_after_move","target_p1_turn_end","target_p2_turn_end","objective_snapshot_before","objective_snapshot_after_move","objective_snapshot_turn_end"));
            }
            List<Path> files;try(Stream<Path> stream=Files.list(trials)){files=stream.filter(p->p.getFileName().toString().endsWith(".trl")).sorted().toList();}if(files.isEmpty())throw new IllegalStateException("No trials in "+trials);
            for(Path file:files)replay(game,spec,id,iterations,file,games,placements,pointStates,regionalStates,opportunities,turnSnapshots,effects);
            System.out.printf(Locale.ROOT,"legally replayed %s: %d games%n",id,files.size());
        }
    }

    private static void replay(Game game,BoardSpec spec,String id,int iterations,Path path,BufferedWriter games,BufferedWriter placements,BufferedWriter pointStates,BufferedWriter regionalStates,BufferedWriter opportunities,BufferedWriter turnSnapshots,BufferedWriter effects)throws Exception
    {
        Matcher matcher=INDEX.matcher(path.getFileName().toString());if(!matcher.matches())throw new IllegalArgumentException("No game index in "+path);int gameIndex=Integer.parseInt(matcher.group(1));
        Trial source=MatchRecord.loadMatchRecordFromTextFile(path.toFile(),game).trial();if(source.numMoves()!=spec.moves||source.numTurns()!=spec.turns||!source.over()||!"NaturalEnd".equals(source.status().endType().toString()))throw new IllegalStateException("Incomplete source "+path);
        Trial replay=new Trial(game);Context context=new Context(game,replay);game.start(context);int sourceMove=0;int[] placed=new int[2];int[][] cumulative=new int[2][REGIONS.size()];
        for(int turn=1;turn<=spec.turns;turn++){
            int mover=context.state().mover();double progress=turn/(double)spec.turns;writeOpportunities(game,context,spec,id,iterations,gameIndex,turn,progress,mover,opportunities);Snapshot before=snapshot(context,spec);int[][] turnPlacements=new int[2][REGIONS.size()];List<Effect> pending=new ArrayList<>();
            for(int placement=1;placement<=3;placement++){
                if(context.state().mover()!=mover)throw new IllegalStateException("Mover changed early in "+path);Move recorded=source.getMove(sourceMove++),legal=legal(game,context,recorded);if(legal==null)throw new IllegalStateException("Illegal recorded move "+sourceMove+" in "+path);Decision d=decision(legal,spec);int region=spec.regionIndex(d.target);Snapshot moveBefore=snapshot(context,spec);int[] placedBefore=placed.clone();turnPlacements[mover-1][region]++;cumulative[mover-1][region]++;
                row(placements,List.of("7x7",id,Integer.toString(iterations),Integer.toString(gameIndex),Integer.toString(turn),decimal(progress),Integer.toString(placement),Integer.toString(mover),spec.name(d.target),d.target<spec.supplies?"supply":"objective",d.source<0?"":spec.name(d.source),REGIONS.get(region)));
                game.apply(context,legal);placed[mover-1]++;Snapshot moveAfter=snapshot(context,spec);if(d.target>=spec.supplies)pending.add(new Effect(placement,mover,d.target,placedBefore,placed.clone(),moveBefore,moveAfter));
            }
            Snapshot after=snapshot(context,spec);if(after.total!=before.total+3)throw new IllegalStateException("Turn did not add three pieces "+path);
            for(int site=0;site<spec.sites;site++)row(pointStates,List.of("7x7",id,Integer.toString(iterations),Integer.toString(gameIndex),Integer.toString(turn),decimal(progress),Integer.toString(mover),spec.name(site),site<spec.supplies?"supply":"objective",REGIONS.get(spec.regionIndex(site)),Integer.toString(before.state[site]),Integer.toString(before.p1[site]),Integer.toString(before.p2[site]),Integer.toString(after.state[site]),Integer.toString(after.p1[site]),Integer.toString(after.p2[site])));
            for(int region=0;region<REGIONS.size();region++){RegionState r=spec.aggregate(after,region);row(regionalStates,List.of("7x7",id,Integer.toString(iterations),Integer.toString(gameIndex),Integer.toString(turn),decimal(progress),Integer.toString(mover),REGIONS.get(region),Integer.toString(turnPlacements[0][region]),Integer.toString(turnPlacements[1][region]),Integer.toString(cumulative[0][region]),Integer.toString(cumulative[1][region]),Integer.toString(r.p1ControlledSupply),Integer.toString(r.p2ControlledSupply),Integer.toString(r.p1SecuredSupply),Integer.toString(r.p2SecuredSupply),Integer.toString(r.p1AdvantageObjective),Integer.toString(r.p2AdvantageObjective),Integer.toString(r.p1SecuredObjective),Integer.toString(r.p2SecuredObjective),Integer.toString(r.p1ObjectivePieces),Integer.toString(r.p2ObjectivePieces),Integer.toString(r.p1UnsecuredPresence),Integer.toString(r.p2UnsecuredPresence),Integer.toString(r.lead()),Integer.toString(spec.supplyCapacity[region]),Integer.toString(spec.objectiveCapacity[region]),Integer.toString(spec.capacity[region]),decimal(spec.capacity[region]/(double)spec.sites)));}
            row(turnSnapshots,List.of("7x7",id,Integer.toString(iterations),Integer.toString(gameIndex),Integer.toString(turn),decimal(progress),Integer.toString(mover),Integer.toString(placed[0]),Integer.toString(placed[1]),after.objectiveSignature(spec)));
            for(Effect e:pending)row(effects,List.of("7x7",id,Integer.toString(iterations),Integer.toString(gameIndex),Integer.toString(turn),decimal(progress),Integer.toString(e.placement),Integer.toString(e.mover),spec.name(e.target),REGIONS.get(spec.regionIndex(e.target)),Integer.toString(e.beforePlaced[0]),Integer.toString(e.beforePlaced[1]),Integer.toString(e.afterPlaced[0]),Integer.toString(e.afterPlaced[1]),Integer.toString(e.before.state[e.target]),Integer.toString(e.after.state[e.target]),Integer.toString(after.state[e.target]),Integer.toString(e.before.p1[e.target]),Integer.toString(e.before.p2[e.target]),Integer.toString(e.after.p1[e.target]),Integer.toString(e.after.p2[e.target]),Integer.toString(after.p1[e.target]),Integer.toString(after.p2[e.target]),e.before.objectiveSignature(spec),e.after.objectiveSignature(spec),after.objectiveSignature(spec)));
        }
        if(sourceMove!=spec.moves||!replay.over()||replay.status().winner()!=source.status().winner())throw new IllegalStateException("Replay outcome differs "+path);if(placed[0]!=spec.pieces||placed[1]!=spec.pieces)throw new IllegalStateException("Piece totals differ "+path);Snapshot end=snapshot(context,spec);int[] score=spec.score(end);if(score[0]!=context.score(1)||score[1]!=context.score(2))throw new IllegalStateException("Replay score differs "+path);int winner=score[0]==score[1]?0:score[0]>score[1]?1:2;if(winner!=replay.status().winner())throw new IllegalStateException("Lexicographic winner differs "+path);
        row(games,List.of("7x7",id,Integer.toString(iterations),Integer.toString(gameIndex),Integer.toString(winner),Integer.toString(replay.numMoves()),Integer.toString(replay.numTurns()),replay.status().endType().toString(),Integer.toString(score[0]),Integer.toString(score[1]),Integer.toString(placed[0]),Integer.toString(placed[1]),relative(path)));
    }

    private static void writeOpportunities(Game game,Context context,BoardSpec spec,String id,int iterations,int gameIndex,int turn,double progress,int mover,BufferedWriter out)throws IOException{Set<Integer> targets=new HashSet<>();for(Move move:game.moves(context).moves())targets.add(decision(move,spec).target);if(targets.isEmpty())throw new IllegalStateException("No legal target at turn start");int[] counts=new int[REGIONS.size()];for(int target:targets)counts[spec.regionIndex(target)]++;if(Arrays.stream(counts).sum()!=targets.size())throw new IllegalStateException("Regional opportunity mismatch");for(int region=0;region<REGIONS.size();region++)row(out,List.of("7x7",id,Integer.toString(iterations),Integer.toString(gameIndex),Integer.toString(turn),decimal(progress),Integer.toString(mover),REGIONS.get(region),Integer.toString(counts[region]),Integer.toString(targets.size()),decimal(counts[region]/(double)targets.size())));}
    private static Move legal(Game game,Context context,Move recorded){for(Move move:game.moves(context).moves())if(move.mover()==recorded.mover()&&move.from()==recorded.from()&&move.to()==recorded.to())return move;return null;}
    private static Decision decision(Move move,BoardSpec spec){return move.from()>=spec.supplies?new Decision(move.from(),move.to()):new Decision(move.to(),-1);}
    private static Snapshot snapshot(Context context,BoardSpec spec){Snapshot s=new Snapshot(spec.sites);ContainerState board=context.containerState(0);for(int site=0;site<spec.sites;site++){int size=board.sizeStackVertex(site);s.total+=size;for(int level=0;level<size;level++){int who=board.whoVertex(site,level);if(who==1)s.p1[site]++;else if(who==2)s.p2[site]++;}s.state[site]=size==0?0:board.stateVertex(site,size-1);}return s;}
    private static BufferedWriter writer(Path path,boolean append)throws IOException{Files.createDirectories(path.toAbsolutePath().getParent());return Files.newBufferedWriter(path,StandardCharsets.UTF_8,StandardOpenOption.CREATE,StandardOpenOption.WRITE,append?StandardOpenOption.APPEND:StandardOpenOption.TRUNCATE_EXISTING);}
    private static void row(BufferedWriter out,List<String> values)throws IOException{for(int i=0;i<values.size();i++){if(i>0)out.write(',');out.write('"');out.write(values.get(i).replace("\"","\"\""));out.write('"');}out.newLine();}
    private static String decimal(double value){return String.format(Locale.ROOT,"%.6f",value);}private static String relative(Path path){return Path.of("").toAbsolutePath().normalize().relativize(path.toAbsolutePath().normalize()).toString().replace('\\','/');}

    private record Decision(int target,int source){}
    private record Effect(int placement,int mover,int target,int[] beforePlaced,int[] afterPlaced,Snapshot before,Snapshot after){}
    private static final class Snapshot{final int[] state,p1,p2;int total;Snapshot(int sites){state=new int[sites];p1=new int[sites];p2=new int[sites];}String objectiveSignature(BoardSpec spec){StringBuilder b=new StringBuilder();for(int i=spec.supplies;i<spec.sites;i++){if(i>spec.supplies)b.append('|');b.append(state[i]).append(':').append(p1[i]).append(':').append(p2[i]);}return b.toString();}}
    private static final class RegionState{int p1ControlledSupply,p2ControlledSupply,p1SecuredSupply,p2SecuredSupply,p1AdvantageObjective,p2AdvantageObjective,p1SecuredObjective,p2SecuredObjective,p1ObjectivePieces,p2ObjectivePieces,p1UnsecuredPresence,p2UnsecuredPresence;int lead(){int c=Integer.compare(p1SecuredObjective,p2SecuredObjective);if(c==0)c=Integer.compare(p1AdvantageObjective,p2AdvantageObjective);if(c==0)c=Integer.compare(p1ObjectivePieces,p2ObjectivePieces);return Integer.compare(c,0);}}
    private static final class BoardSpec{
        final int objectiveSide=7,supplySide=8,supplies=64,objectives=49,sites=113,moves=144,turns=48,pieces=72,advantageWeight=73,securedWeight=3650;final int[] supplyCapacity=new int[9],objectiveCapacity=new int[9],capacity=new int[9];
        BoardSpec(){for(int site=0;site<sites;site++){int r=regionIndex(site);capacity[r]++;if(site<supplies)supplyCapacity[r]++;else objectiveCapacity[r]++;}int[] expected={13,12,13,12,13,12,13,12,13};if(!Arrays.equals(capacity,expected)||Arrays.stream(capacity).sum()!=sites)throw new IllegalStateException("7x7 region mapping differs from preregistration");}
        String name(int site){return site<supplies?"S"+(site/supplySide)+(site%supplySide):"O"+((site-supplies)/objectiveSide)+((site-supplies)%objectiveSide);}
        int regionIndex(int site){if(site<0||site>=sites)throw new IllegalArgumentException("target outside board: "+site);boolean supply=site<supplies;int local=supply?site:site-supplies,side=supply?supplySide:objectiveSide,row=local/side,column=local%side;double x=supply?column/(double)(supplySide-1):(column+.5)/objectiveSide,y=supply?row/(double)(supplySide-1):(row+.5)/objectiveSide;return axis(y)*3+axis(x);}
        private int axis(double value){double low=Math.abs(value-1.0/6),middle=Math.abs(value-.5),high=Math.abs(value-5.0/6);if(middle<=low&&middle<=high)return 1;return low<high?0:2;}
        RegionState aggregate(Snapshot s,int region){RegionState r=new RegionState();for(int site=0;site<sites;site++){if(regionIndex(site)!=region)continue;int state=s.state[site];if(state!=3&&state!=4){r.p1UnsecuredPresence+=s.p1[site];r.p2UnsecuredPresence+=s.p2[site];}if(site<supplies){if(state==1)r.p1ControlledSupply++;else if(state==2)r.p2ControlledSupply++;else if(state==3)r.p1SecuredSupply++;else if(state==4)r.p2SecuredSupply++;}else{if(state==1)r.p1AdvantageObjective++;else if(state==2)r.p2AdvantageObjective++;else if(state==3)r.p1SecuredObjective++;else if(state==4)r.p2SecuredObjective++;r.p1ObjectivePieces+=s.p1[site];r.p2ObjectivePieces+=s.p2[site];}}return r;}
        int[] score(Snapshot s){int[] result=new int[2];for(int site=supplies;site<sites;site++){if(s.state[site]==3)result[0]+=securedWeight;else if(s.state[site]==4)result[1]+=securedWeight;else if(s.state[site]==1)result[0]+=advantageWeight;else if(s.state[site]==2)result[1]+=advantageWeight;result[0]+=s.p1[site];result[1]+=s.p2[site];}return result;}
    }
}
