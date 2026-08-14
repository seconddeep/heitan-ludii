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

/** Deterministic headless runner for the validated Board/3x3 option. */
public final class Heitan3x3Experiment
{
    private static final int SUPPLIES=16, OBJECTIVES=9, SITES=25;
    private static final int PIECES=27, MOVES=54, TURNS=18;
    private static final int ADVANTAGE_WEIGHT=28, SECURED_WEIGHT=280;

    public static void main(final String[] args) throws Exception
    {
        if(args.length!=10){System.err.println("Usage: Heitan3x3Experiment <game> <id> <agent> <games> <seed-first> <iterations> <raw.csv> <trials-dir> <repo-root> <index-offset>");System.exit(2);}
        final File gameFile=new File(args[0]).getCanonicalFile();
        final String id=args[1],agentName=args[2];
        final int games=Integer.parseInt(args[3]),iterations=Integer.parseInt(args[5]),offset=Integer.parseInt(args[9]);
        final long seedFirst=Long.parseLong(args[4]);
        final Path raw=Path.of(args[6]),trialsDir=Path.of(args[7]),repo=Path.of(args[8]).toAbsolutePath().normalize();
        final List<String> options=List.of("Board/3x3");
        final Game game=GameLoader.loadGameFromFile(gameFile,options);
        if(game==null||game.board().graph().vertices().size()!=SITES)throw new IllegalStateException("Board/3x3 did not load as a 25-site game");
        Files.createDirectories(raw.toAbsolutePath().getParent());Files.createDirectories(trialsDir);
        try(BufferedWriter out=Files.newBufferedWriter(raw,StandardCharsets.UTF_8)){
            row(out,List.of("experiment_id","game_index","seed","agent","iteration_limit","completed","end_type","winner","moves","turns","p1_score","p2_score","p1_total_pieces","p2_total_pieces","p1_supply_pieces","p2_supply_pieces","p1_objective_pieces","p2_objective_pieces","p1_secured_supply","p2_secured_supply","p1_secured_objectives","p2_secured_objectives","p1_advantage_objectives","p2_advantage_objectives","deciding_criterion","elapsed_seconds","final_board","trial_file"));
            for(int index=0;index<games;index++){
                final long started=System.nanoTime(),seed=seedFirst+index;final int number=offset+index+1;
                final Trial trial=new Trial(game);final Context context=new Context(game,trial);
                context.rng().restoreState(new SplitMix64(seed).saveState());final RandomProviderDefaultState rng=(RandomProviderDefaultState)context.rng().saveState();game.start(context);
                final List<AI> agents=new ArrayList<>(Arrays.asList(null,agent(agentName,seed,1,game),agent(agentName,seed,2,game)));
                for(int p=1;p<=2;p++){agents.get(p).setMaxIterationsPerMove(iterations);agents.get(p).setMaxSecondsPerMove(-1);agents.get(p).initAI(game,p);}
                while(!trial.over())context.model().startNewStep(context,agents,-1,iterations,-1,0);
                final Path trialPath=trialsDir.resolve(String.format(Locale.ROOT,"%s-%04d.trl",id,number));
                trial.saveTrialToTextFile(trialPath.toFile(),gameFile.getPath(),new ArrayList<>(options),rng);
                final Metrics m=metrics(context);validate(context,trial,m);
                row(out,List.of(id,Integer.toString(number),Long.toString(seed),agentName,Integer.toString(iterations),Boolean.toString(trial.over()),trial.status().endType().toString(),Integer.toString(trial.status().winner()),Integer.toString(trial.numMoves()),Integer.toString(trial.numTurns()),Integer.toString(context.score(1)),Integer.toString(context.score(2)),Integer.toString(m.p1Total),Integer.toString(m.p2Total),Integer.toString(m.p1Supply),Integer.toString(m.p2Supply),Integer.toString(m.p1Objective),Integer.toString(m.p2Objective),Integer.toString(m.p1SecSupply),Integer.toString(m.p2SecSupply),Integer.toString(m.p1SecObj),Integer.toString(m.p2SecObj),Integer.toString(m.p1AdvObj),Integer.toString(m.p2AdvObj),criterion(m),String.format(Locale.ROOT,"%.3f",(System.nanoTime()-started)/1e9),m.board,repo.relativize(trialPath.toAbsolutePath().normalize()).toString().replace('\\','/')));
                out.flush();for(int p=1;p<=2;p++)agents.get(p).closeAI();
                System.out.printf(Locale.ROOT,"%s %d seed=%d %.3fs%n",id,number,seed,(System.nanoTime()-started)/1e9);
            }
        }
    }

    private static AI agent(String name,long seed,int player,Game game){final AI ai;if(name.equalsIgnoreCase("SeededRandom"))ai=new SeededRandom(seed^(0x9E3779B97F4A7C15L*player));else ai=AIFactory.createAI(name);if(ai==null||!ai.supportsGame(game))throw new IllegalArgumentException("Unsupported AI "+name);return ai;}
    private static Metrics metrics(Context c){Metrics m=new Metrics();StringBuilder b=new StringBuilder();ContainerState board=c.containerState(0);for(int site=0;site<SITES;site++){int p1=0,p2=0,size=board.sizeStackVertex(site);for(int level=0;level<size;level++){if(board.whoVertex(site,level)==1)p1++;else if(board.whoVertex(site,level)==2)p2++;}int state=size==0?0:board.stateVertex(site,size-1);m.p1Total+=p1;m.p2Total+=p2;if(site<SUPPLIES){m.p1Supply+=p1;m.p2Supply+=p2;if(state==3)m.p1SecSupply++;else if(state==4)m.p2SecSupply++;}else{m.p1Objective+=p1;m.p2Objective+=p2;if(state==3)m.p1SecObj++;else if(state==4)m.p2SecObj++;else if(state==1)m.p1AdvObj++;else if(state==2)m.p2AdvObj++;}if(site>0)b.append('|');b.append(name(site)).append(':').append(state).append(':').append(p1).append(':').append(p2);}m.board=b.toString();return m;}
    private static void validate(Context c,Trial t,Metrics m){if(!t.over()||!"NaturalEnd".equals(t.status().endType().toString())||t.numMoves()!=MOVES||t.numTurns()!=TURNS)throw new IllegalStateException("Unexpected game end");if(m.p1Total!=PIECES||m.p2Total!=PIECES)throw new IllegalStateException("Unexpected piece totals");int s1=SECURED_WEIGHT*m.p1SecObj+ADVANTAGE_WEIGHT*m.p1AdvObj+m.p1Objective,s2=SECURED_WEIGHT*m.p2SecObj+ADVANTAGE_WEIGHT*m.p2AdvObj+m.p2Objective;if(c.score(1)!=s1||c.score(2)!=s2)throw new IllegalStateException("Score mismatch");int winner=s1==s2?0:s1>s2?1:2;if(t.status().winner()!=winner)throw new IllegalStateException("Winner mismatch");}
    private static String criterion(Metrics m){if(m.p1SecObj!=m.p2SecObj)return"Secured";if(m.p1AdvObj!=m.p2AdvObj)return"Advantage";if(m.p1Objective!=m.p2Objective)return"Pieces";return"Draw";}
    private static String name(int site){return site<SUPPLIES?"S"+(site/4)+(site%4):"O"+((site-SUPPLIES)/3)+((site-SUPPLIES)%3);}
    private static void row(BufferedWriter out,List<String> values)throws IOException{for(int i=0;i<values.size();i++){if(i>0)out.write(',');out.write('"');out.write(values.get(i).replace("\"","\"\""));out.write('"');}out.newLine();}
    private static final class SeededRandom extends AI{private final SplittableRandom random;SeededRandom(long seed){random=new SplittableRandom(seed);friendlyName="SeededRandom";}@Override public Move selectAction(Game g,Context c,double s,int i,int d){FastArrayList<Move> moves=g.moves(c).moves();return moves.get(random.nextInt(moves.size()));}}
    private static final class Metrics{int p1Total,p2Total,p1Supply,p2Supply,p1Objective,p2Objective,p1SecSupply,p2SecSupply,p1SecObj,p2SecObj,p1AdvObj,p2AdvObj;String board;}
}
