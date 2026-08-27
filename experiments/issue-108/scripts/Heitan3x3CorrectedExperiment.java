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

/** Deterministic corrected-rule Board/3x3 self-play runner for Issue #108. */
public final class Heitan3x3CorrectedExperiment
{
    private static final int SUPPLIES=16, OBJECTIVES=9, SITES=25, PIECES=27, MOVES=54, TURNS=18;
    private static final int ADVANTAGE_WEIGHT=28, SECURED_WEIGHT=280;

    public static void main(final String[] args) throws Exception
    {
        if(args.length!=9){System.err.println("Usage: Heitan3x3CorrectedExperiment <game> <id> <agent> <seed> <iterations> <result.csv> <trial> <index> <raw-game-path>");System.exit(2);}
        final File gameFile=new File(args[0]).getCanonicalFile();
        final String id=args[1],agentName=args[2],rawGamePath=args[8];
        final long seed=Long.parseLong(args[3]);final int iterations=Integer.parseInt(args[4]),number=Integer.parseInt(args[7]);
        final Path result=Path.of(args[5]),trialPath=Path.of(args[6]);final List<String> options=List.of("Board/3x3");
        final Game game=GameLoader.loadGameFromFile(gameFile,options);
        if(game==null||game.board().graph().vertices().size()!=SITES)throw new IllegalStateException("Board/3x3 did not load as 25 sites");
        Files.createDirectories(result.toAbsolutePath().getParent());Files.createDirectories(trialPath.toAbsolutePath().getParent());
        final long started=System.nanoTime();final Trial trial=new Trial(game);final Context context=new Context(game,trial);
        context.rng().restoreState(new SplitMix64(seed).saveState());final RandomProviderDefaultState rng=(RandomProviderDefaultState)context.rng().saveState();game.start(context);
        final List<AI> agents=new ArrayList<>(Arrays.asList(null,agent(agentName,game),agent(agentName,game)));
        for(int p=1;p<=2;p++){agents.get(p).setMaxIterationsPerMove(iterations);agents.get(p).setMaxSecondsPerMove(-1);agents.get(p).initAI(game,p);}
        try{while(!trial.over())context.model().startNewStep(context,agents,-1,iterations,-1,0);}finally{for(int p=1;p<=2;p++)agents.get(p).closeAI();}
        trial.saveTrialToTextFile(trialPath.toFile(),rawGamePath,new ArrayList<>(options),rng);
        final Metrics m=metrics(context);validate(context,trial,m);
        try(BufferedWriter out=Files.newBufferedWriter(result,StandardCharsets.UTF_8)){
            row(out,List.of("experiment_id","game_index","seed","agent","iteration_limit","completed","end_type","winner","moves","turns","p1_score","p2_score","p1_total_pieces","p2_total_pieces","p1_supply_pieces","p2_supply_pieces","p1_total_objective_pieces","p2_total_objective_pieces","p1_corrected_objective_pieces","p2_corrected_objective_pieces","p1_secured_objectives","p2_secured_objectives","p1_advantage_objectives","p2_advantage_objectives","p1_excluded_own_secured","p2_excluded_own_secured","p1_excluded_opponent_secured","p2_excluded_opponent_secured","p1_excluded_opponent_advantage","p2_excluded_opponent_advantage","p1_excluded_neutral","p2_excluded_neutral","deciding_criterion","elapsed_seconds","final_board"));
            row(out,List.of(id,Integer.toString(number),Long.toString(seed),agentName,Integer.toString(iterations),Boolean.toString(trial.over()),trial.status().endType().toString(),Integer.toString(trial.status().winner()),Integer.toString(trial.numMoves()),Integer.toString(trial.numTurns()),Integer.toString(context.score(1)),Integer.toString(context.score(2)),Integer.toString(m.p1Total),Integer.toString(m.p2Total),Integer.toString(m.p1Supply),Integer.toString(m.p2Supply),Integer.toString(m.p1Objective),Integer.toString(m.p2Objective),Integer.toString(m.p1Corrected),Integer.toString(m.p2Corrected),Integer.toString(m.p1SecObj),Integer.toString(m.p2SecObj),Integer.toString(m.p1AdvObj),Integer.toString(m.p2AdvObj),Integer.toString(m.p1OwnSec),Integer.toString(m.p2OwnSec),Integer.toString(m.p1OppSec),Integer.toString(m.p2OppSec),Integer.toString(m.p1OppAdv),Integer.toString(m.p2OppAdv),Integer.toString(m.p1Neutral),Integer.toString(m.p2Neutral),criterion(m),String.format(Locale.ROOT,"%.3f",(System.nanoTime()-started)/1e9),m.board));
        }
    }

    private static AI agent(String name,Game game){AI ai=AIFactory.createAI(name);if(ai==null||!ai.supportsGame(game))throw new IllegalArgumentException("Unsupported AI "+name);return ai;}
    private static Metrics metrics(Context c){Metrics m=new Metrics();StringBuilder b=new StringBuilder();ContainerState board=c.containerState(0);for(int site=0;site<SITES;site++){int p1=0,p2=0,size=board.sizeStackVertex(site);for(int level=0;level<size;level++){if(board.whoVertex(site,level)==1)p1++;else if(board.whoVertex(site,level)==2)p2++;}int state=size==0?0:board.stateVertex(site,size-1);m.p1Total+=p1;m.p2Total+=p2;if(site<SUPPLIES){m.p1Supply+=p1;m.p2Supply+=p2;}else{m.p1Objective+=p1;m.p2Objective+=p2;if(state==3){m.p1SecObj++;m.p1OwnSec+=p1;m.p2OppSec+=p2;}else if(state==4){m.p2SecObj++;m.p2OwnSec+=p2;m.p1OppSec+=p1;}else if(state==1){m.p1AdvObj++;m.p1Corrected+=p1;m.p2OppAdv+=p2;}else if(state==2){m.p2AdvObj++;m.p2Corrected+=p2;m.p1OppAdv+=p1;}else{m.p1Neutral+=p1;m.p2Neutral+=p2;}}if(site>0)b.append('|');b.append(name(site)).append(':').append(state).append(':').append(p1).append(':').append(p2);}m.board=b.toString();return m;}
    private static void validate(Context c,Trial t,Metrics m){if(!t.over()||!"NaturalEnd".equals(t.status().endType().toString())||t.numMoves()!=MOVES||t.numTurns()!=TURNS)throw new IllegalStateException("Unexpected game end");if(m.p1Total!=PIECES||m.p2Total!=PIECES)throw new IllegalStateException("Unexpected piece totals");if(m.p1Objective!=m.p1Corrected+m.p1OwnSec+m.p1OppSec+m.p1OppAdv+m.p1Neutral||m.p2Objective!=m.p2Corrected+m.p2OwnSec+m.p2OppSec+m.p2OppAdv+m.p2Neutral)throw new IllegalStateException("Objective partition mismatch");if(m.p1OwnSec!=3*m.p1SecObj||m.p2OwnSec!=3*m.p2SecObj)throw new IllegalStateException("Own-Secured identity mismatch");int s1=SECURED_WEIGHT*m.p1SecObj+ADVANTAGE_WEIGHT*m.p1AdvObj+m.p1Corrected,s2=SECURED_WEIGHT*m.p2SecObj+ADVANTAGE_WEIGHT*m.p2AdvObj+m.p2Corrected;if(c.score(1)!=s1||c.score(2)!=s2)throw new IllegalStateException("Score mismatch");int winner=s1==s2?0:s1>s2?1:2;if(t.status().winner()!=winner)throw new IllegalStateException("Winner mismatch");}
    private static String criterion(Metrics m){if(m.p1SecObj!=m.p2SecObj)return"secured_objectives";if(m.p1AdvObj!=m.p2AdvObj)return"advantage_objectives";if(m.p1Corrected!=m.p2Corrected)return"objective_pieces";return"draw";}
    private static String name(int site){return site<SUPPLIES?"S"+(site/4)+(site%4):"O"+((site-SUPPLIES)/3)+((site-SUPPLIES)%3);}
    private static void row(BufferedWriter out,List<String> values)throws IOException{for(int i=0;i<values.size();i++){if(i>0)out.write(',');out.write('"');out.write(values.get(i).replace("\"","\"\""));out.write('"');}out.newLine();}
    private static final class Metrics{int p1Total,p2Total,p1Supply,p2Supply,p1Objective,p2Objective,p1Corrected,p2Corrected,p1SecObj,p2SecObj,p1AdvObj,p2AdvObj,p1OwnSec,p2OwnSec,p1OppSec,p2OppSec,p1OppAdv,p2OppAdv,p1Neutral,p2Neutral;String board;}
}
