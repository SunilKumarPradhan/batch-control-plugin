package io.jenkins.plugins.batchcontrol;

import hudson.Launcher;
import hudson.model.AbstractBuild;
import hudson.model.BuildListener;
import hudson.model.Result;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import org.jvnet.hudson.test.TestBuilder;

/**
 * Build results for the Wave D D2 follow-up rows (T-UI-269b..269i, note 361 point 9, owner decisions
 * of 2026-10-14): a build step that ends the build with a chosen result, a build step that holds a
 * build running until the test releases it, and the readable label of every build result.
 */
final class ResultFixtures {

    /**
     * The readable label of every build result: the words the History Result dropdown uses for its
     * options (owner decision 2, 2026-10-14). Keyed by the {@code hudson.model.Result} name, in the
     * order of {@link Result#ordinal}.
     */
    static final Map<String, String> RESULT_LABELS = labels();

    /** Every build result name. */
    static final List<String> ALL_RESULTS = List.copyOf(RESULT_LABELS.keySet());

    /**
     * The Result filter of History &gt; Incidents: "Any" (empty) and exactly the results that can
     * open an incident, in this order (owner decision 1, 2026-10-14; the order follows SPEC 11, which
     * names FAILURE, UNSTABLE and then ABORTED as the one that may be added).
     */
    static final List<String> INCIDENT_RESULT_OPTIONS = List.of("", "FAILURE", "UNSTABLE", "ABORTED");

    private ResultFixtures() {
    }

    private static Map<String, String> labels() {
        Map<String, String> labels = new LinkedHashMap<>();
        labels.put("SUCCESS", "Success");
        labels.put("UNSTABLE", "Unstable");
        labels.put("FAILURE", "Failed");
        labels.put("NOT_BUILT", "Not built");
        labels.put("ABORTED", "Aborted");
        return labels;
    }

    /** Ends the build with the given result (any result: SUCCESS, UNSTABLE, FAILURE, NOT_BUILT, ABORTED). */
    public static class SetResult extends TestBuilder {

        private final String result;

        public SetResult(String result) {
            this.result = result;
        }

        public String getResult() {
            return result;
        }

        @Override
        public boolean perform(AbstractBuild<?, ?> build, Launcher launcher, BuildListener listener) {
            build.setResult(Result.fromString(result));
            return true;
        }
    }

    /**
     * Holds the build running until {@link #release()}: a build that has no result yet. One hold at
     * a time; {@link #arm()} before the build is scheduled.
     */
    public static class Hold extends TestBuilder {

        private static volatile CountDownLatch started = new CountDownLatch(1);
        private static volatile CountDownLatch released = new CountDownLatch(1);

        static void arm() {
            started = new CountDownLatch(1);
            released = new CountDownLatch(1);
        }

        static boolean awaitStarted() throws InterruptedException {
            return started.await(60, TimeUnit.SECONDS);
        }

        static void release() {
            released.countDown();
        }

        @Override
        public boolean perform(AbstractBuild<?, ?> build, Launcher launcher, BuildListener listener)
                throws InterruptedException {
            started.countDown();
            return released.await(120, TimeUnit.SECONDS);
        }
    }
}
