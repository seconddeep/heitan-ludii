package heitan.experiments;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import game.Game;
import manager.utils.game_logs.MatchRecord;
import other.GameLoader;
import other.context.Context;
import other.move.Move;
import other.state.container.ContainerState;
import other.trial.Trial;

/** Outcome-blind legal replay validator for Issue #116. */
public final class HeitanBenchmarkReplay
{
    public static void main(String[] args)throws Exception
    {
        if(args.length!=8){System.err.println("Usage: HeitanBenchmarkReplay <game> <board> <trial> <sites> <pieces/player> <moves> <turns> <stamp>");System.exit(2);}
        File gameFile=new File(args[0]).getCanonicalFile();String board=args[1];Path trialPath=Path.of(args[2]),stamp=Path.of(args[7]);
        int sites=Integer.parseInt(args[3]),pieces=Integer.parseInt(args[4]),moves=Integer.parseInt(args[5]),turns=Integer.parseInt(args[6]);
        Game game=GameLoader.loadGameFromFile(gameFile,List.of("Board/"+board));if(game==null||game.board().graph().vertices().size()!=sites)throw new IllegalStateException("wrong board");
        Trial source=MatchRecord.loadMatchRecordFromTextFile(trialPath.toFile(),game).trial();
        if(!source.over()||!"NaturalEnd".equals(source.status().endType().toString())||source.numMoves()!=moves||source.numTurns()!=turns)throw new IllegalStateException("incomplete source trial");
        Trial replay=new Trial(game);Context context=new Context(game,replay);game.start(context);int cursor=0;
        for(int turn=0;turn<turns;turn++){
            int mover=context.state().mover(),before=total(context,sites);
            for(int placement=0;placement<3;placement++){
                if(context.state().mover()!=mover)throw new IllegalStateException("mover changed before third placement");
                Move recorded=source.getMove(cursor++),legal=legal(game,context,recorded);if(legal==null)throw new IllegalStateException("illegal recorded move");game.apply(context,legal);
            }
            if(total(context,sites)!=before+3)throw new IllegalStateException("turn did not add three Pieces");
        }
        int p1=0,p2=0;ContainerState state=context.containerState(0);for(int site=0;site<sites;site++)for(int level=0;level<state.sizeStackVertex(site);level++){if(state.whoVertex(site,level)==1)p1++;else if(state.whoVertex(site,level)==2)p2++;}
        if(cursor!=moves||!replay.over()||p1!=pieces||p2!=pieces)throw new IllegalStateException("replay completion differs");
        Files.createDirectories(stamp.toAbsolutePath().getParent());Files.writeString(stamp,"validated\n");
    }
    private static Move legal(Game game,Context context,Move recorded){for(Move move:game.moves(context).moves())if(move.mover()==recorded.mover()&&move.from()==recorded.from()&&move.to()==recorded.to())return move;return null;}
    private static int total(Context context,int sites){int value=0;ContainerState state=context.containerState(0);for(int site=0;site<sites;site++)value+=state.sizeStackVertex(site);return value;}
}
