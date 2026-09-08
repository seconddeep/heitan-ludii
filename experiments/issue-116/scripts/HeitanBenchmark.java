package heitan.experiments;

import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import org.apache.commons.rng.core.RandomProviderDefaultState;
import org.apache.commons.rng.core.source64.SplitMix64;
import game.Game;
import other.AI;
import other.GameLoader;
import other.context.Context;
import other.state.container.ContainerState;
import other.trial.Trial;
import utils.AIFactory;

/** Outcome-blind one-game execution harness for Issue #116. */
public final class HeitanBenchmark
{
    public static void main(final String[] args) throws Exception
    {
        if(args.length!=12){System.err.println("Usage: HeitanBenchmark <game> <board> <id> <seed> <iterations> <result.csv> <trial> <game-path> <sites> <pieces/player> <moves> <turns>");System.exit(2);}
        final File gameFile=new File(args[0]).getCanonicalFile();
        final String board=args[1],id=args[2],rawGamePath=args[7];
        final long seed=Long.parseLong(args[3]);
        final int iterations=Integer.parseInt(args[4]),sites=Integer.parseInt(args[8]),pieces=Integer.parseInt(args[9]),moves=Integer.parseInt(args[10]),turns=Integer.parseInt(args[11]);
        final Path result=Path.of(args[5]),trialPath=Path.of(args[6]);
        final List<String> options=List.of("Board/"+board);
        final Game game=GameLoader.loadGameFromFile(gameFile,options);
        if(game==null||game.board().graph().vertices().size()!=sites)throw new IllegalStateException("source-derived board site count did not load");
        Files.createDirectories(result.toAbsolutePath().getParent());Files.createDirectories(trialPath.toAbsolutePath().getParent());
        final long started=System.nanoTime();final Trial trial=new Trial(game);final Context context=new Context(game,trial);
        context.rng().restoreState(new SplitMix64(seed).saveState());final RandomProviderDefaultState rng=(RandomProviderDefaultState)context.rng().saveState();game.start(context);
        final List<AI> agents=new ArrayList<>(Arrays.asList(null,agent(game),agent(game)));
        for(int p=1;p<=2;p++){agents.get(p).setMaxIterationsPerMove(iterations);agents.get(p).setMaxSecondsPerMove(-1);agents.get(p).initAI(game,p);}
        try{while(!trial.over())context.model().startNewStep(context,agents,-1,iterations,-1,0);}finally{for(int p=1;p<=2;p++)agents.get(p).closeAI();}
        trial.saveTrialToTextFile(trialPath.toFile(),rawGamePath,new ArrayList<>(options),rng);
        if(!trial.over()||!"NaturalEnd".equals(trial.status().endType().toString())||trial.numMoves()!=moves||trial.numTurns()!=turns)throw new IllegalStateException("unexpected natural completion dimensions");
        int p1=0,p2=0;ContainerState state=context.containerState(0);
        for(int site=0;site<sites;site++)for(int level=0;level<state.sizeStackVertex(site);level++){if(state.whoVertex(site,level)==1)p1++;else if(state.whoVertex(site,level)==2)p2++;}
        if(p1!=pieces||p2!=pieces)throw new IllegalStateException("unexpected piece totals");
        try(BufferedWriter out=Files.newBufferedWriter(result,StandardCharsets.UTF_8)){
            out.write("experiment_id,board,seed,iteration_limit,completed,end_type,moves,turns,elapsed_seconds\n");
            out.write(String.format(Locale.ROOT,"%s,%s,%d,%d,true,NaturalEnd,%d,%d,%.3f%n",id,board,seed,iterations,trial.numMoves(),trial.numTurns(),(System.nanoTime()-started)/1e9));
        }
    }
    private static AI agent(Game game){AI ai=AIFactory.createAI("UCT");if(ai==null||!ai.supportsGame(game))throw new IllegalArgumentException("UCT does not support game");return ai;}
}
