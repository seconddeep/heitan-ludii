package heitan.experiments;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import game.Game;
import manager.utils.game_logs.MatchRecord;
import other.GameLoader;
import other.context.Context;
import other.move.Move;
import other.state.container.ContainerState;
import other.trial.Trial;

/** Legal replay and turn-end state extraction for one Issue #108 trial. */
public final class Heitan3x3CorrectedReplay
{
    private static final int SUPPLIES=16,SITES=25,MOVES=54,TURNS=18;
    public static void main(String[] args)throws Exception{
        if(args.length!=6){System.err.println("Usage: Heitan3x3CorrectedReplay <game> <trial> <game-index> <games.csv> <placements.csv> <turn-states.csv>");System.exit(2);}
        File gameFile=new File(args[0]).getCanonicalFile();Path trialPath=Path.of(args[1]);int gameIndex=Integer.parseInt(args[2]);Game game=GameLoader.loadGameFromFile(gameFile,List.of("Board/3x3"));if(game==null||game.board().graph().vertices().size()!=SITES)throw new IllegalStateException("Wrong board");
        try(BufferedWriter games=writer(args[3]);BufferedWriter placements=writer(args[4]);BufferedWriter states=writer(args[5])){row(games,List.of("game_index","winner","moves","turns","end_type","final_p1_score","final_p2_score","final_board"));row(placements,List.of("game_index","turn_number","placement_number","mover","target","target_type","supply_source"));row(states,List.of("game_index","turn_number","mover","point","point_type","state_at_turn_end","p1_at_turn_end","p2_at_turn_end"));replay(game,trialPath,gameIndex,games,placements,states);}
    }
    private static void replay(Game game,Path path,int gameIndex,BufferedWriter games,BufferedWriter placements,BufferedWriter states)throws Exception{Trial source=MatchRecord.loadMatchRecordFromTextFile(path.toFile(),game).trial();if(source.numMoves()!=MOVES||source.numTurns()!=TURNS||!source.over()||!"NaturalEnd".equals(source.status().endType().toString()))throw new IllegalStateException("Incomplete source");Trial replay=new Trial(game);Context context=new Context(game,replay);game.start(context);int sourceMove=0;for(int turn=1;turn<=TURNS;turn++){int mover=context.state().mover();int before=total(context);for(int placement=1;placement<=3;placement++){if(context.state().mover()!=mover)throw new IllegalStateException("Mover changed before third placement");Move recorded=source.getMove(sourceMove++),legal=legal(game,context,recorded);if(legal==null)throw new IllegalStateException("Illegal recorded move "+sourceMove);int[] decision=decision(legal);row(placements,List.of(Integer.toString(gameIndex),Integer.toString(turn),Integer.toString(placement),Integer.toString(mover),name(decision[0]),decision[0]<SUPPLIES?"supply":"objective",decision[1]<0?"":name(decision[1])));game.apply(context,legal);}if(total(context)!=before+3)throw new IllegalStateException("Turn did not add exactly three Pieces");Snapshot snapshot=snapshot(context);for(int site=0;site<SITES;site++)row(states,List.of(Integer.toString(gameIndex),Integer.toString(turn),Integer.toString(mover),name(site),site<SUPPLIES?"supply":"objective",Integer.toString(snapshot.state[site]),Integer.toString(snapshot.p1[site]),Integer.toString(snapshot.p2[site])));}if(sourceMove!=MOVES||!replay.over()||replay.status().winner()!=source.status().winner())throw new IllegalStateException("Replay outcome differs");Snapshot end=snapshot(context);int[] score=score(end);if(score[0]!=context.score(1)||score[1]!=context.score(2))throw new IllegalStateException("Corrected replay score differs");row(games,List.of(Integer.toString(gameIndex),Integer.toString(replay.status().winner()),Integer.toString(replay.numMoves()),Integer.toString(replay.numTurns()),replay.status().endType().toString(),Integer.toString(score[0]),Integer.toString(score[1]),end.board));}
    private static Move legal(Game game,Context context,Move recorded){for(Move move:game.moves(context).moves())if(move.mover()==recorded.mover()&&move.from()==recorded.from()&&move.to()==recorded.to())return move;return null;}
    private static int[] decision(Move move){return move.from()>=SUPPLIES?new int[]{move.from(),move.to()}:new int[]{move.to(),-1};}
    private static int total(Context context){int value=0;ContainerState board=context.containerState(0);for(int site=0;site<SITES;site++)value+=board.sizeStackVertex(site);return value;}
    private static Snapshot snapshot(Context context){Snapshot s=new Snapshot();ContainerState board=context.containerState(0);StringBuilder encoded=new StringBuilder();for(int site=0;site<SITES;site++){int size=board.sizeStackVertex(site);for(int level=0;level<size;level++){if(board.whoVertex(site,level)==1)s.p1[site]++;else if(board.whoVertex(site,level)==2)s.p2[site]++;}s.state[site]=size==0?0:board.stateVertex(site,size-1);if(site>0)encoded.append('|');encoded.append(name(site)).append(':').append(s.state[site]).append(':').append(s.p1[site]).append(':').append(s.p2[site]);}s.board=encoded.toString();return s;}
    private static int[] score(Snapshot s){int[] result=new int[2];for(int site=SUPPLIES;site<SITES;site++){if(s.state[site]==3)result[0]+=280;else if(s.state[site]==4)result[1]+=280;else if(s.state[site]==1){result[0]+=28+s.p1[site];}else if(s.state[site]==2){result[1]+=28+s.p2[site];}}return result;}
    private static String name(int site){return site<SUPPLIES?"S"+(site/4)+(site%4):"O"+((site-SUPPLIES)/3)+((site-SUPPLIES)%3);}
    private static BufferedWriter writer(String value)throws IOException{Path path=Path.of(value);Files.createDirectories(path.toAbsolutePath().getParent());return Files.newBufferedWriter(path,StandardCharsets.UTF_8,StandardOpenOption.CREATE,StandardOpenOption.TRUNCATE_EXISTING);}
    private static void row(BufferedWriter out,List<String> values)throws IOException{for(int i=0;i<values.size();i++){if(i>0)out.write(',');out.write('"');out.write(values.get(i).replace("\"","\"\""));out.write('"');}out.newLine();}
    private static final class Snapshot{final int[] state=new int[SITES],p1=new int[SITES],p2=new int[SITES];String board;}
}
