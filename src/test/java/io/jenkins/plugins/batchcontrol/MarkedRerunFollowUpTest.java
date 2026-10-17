package io.jenkins.plugins.batchcontrol;

import hudson.model.CauseAction;
import hudson.model.Item;
import hudson.model.Queue;
import hudson.model.Run;
import hudson.model.User;
import hudson.security.ACL;
import hudson.security.ACLContext;
import io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration;
import io.jenkins.plugins.batchcontrol.model.ChangeRecord;
import io.jenkins.plugins.batchcontrol.model.ChangeType;
import io.jenkins.plugins.batchcontrol.model.GrantAction;
import io.jenkins.plugins.batchcontrol.security.BatchControlMatrixAuthorizationStrategy;
import io.jenkins.plugins.batchcontrol.store.BatchClock;
import java.lang.reflect.Constructor;
import java.time.Clock;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import jenkins.model.Jenkins;
import org.htmlunit.HttpMethod;
import org.htmlunit.WebRequest;
import org.jenkinsci.plugins.matrixauth.PermissionEntry;
import org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition;
import org.jenkinsci.plugins.workflow.cps.replay.ReplayAction;
import org.jenkinsci.plugins.workflow.cps.replay.ReplayCause;
import org.jenkinsci.plugins.workflow.job.WorkflowJob;
import org.jenkinsci.plugins.workflow.job.WorkflowRun;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.jvnet.hudson.test.JenkinsRule;
import org.jvnet.hudson.test.junit.jupiter.WithJenkins;

import static io.jenkins.plugins.batchcontrol.StrategyFixtures.T0;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #1 (security-31 and security-32 follow-ups): what a re-run of a run marked under a permission window
 * carries and records. Matrix rows T-02-188, T-02-189 and T-02-192 (notes 352, 353 and 356).
 *
 * <p>Basis: SPEC item 2, the D-58c line: "a run started by a Replay, Pipeline Rebuild or Restart from Stage
 * of a grant-only user carries a marker and a {@code REPLAY_UNDER_GRANT} record; ... re-running a marked run
 * ... is refused with a plain message for everyone but an Overall/Administer holder, before and after the
 * review; a re-run of a marked run (an administrator's included) is marked too, and a re-run whose source
 * cannot be resolved is refused"; DECISIONS D-58c ("the refusal is recorded like other refused re-runs");
 * CLAUDE.md (a feature does not change existing Jenkins behaviour while its switch is off); the #1 contract
 * (frozen 2026-10-10) and docs/reports/security-31.md S-31-01, S-31-02, security-32.md S-32-01.
 *
 * <p>The marked run is made as in GuardMarkedRerunGapTest: bob, whose Run/Replay comes only from his
 * CONFIGURE window on {@code replay-me}, replays #1 as #2. Change control on, run control off. alice holds
 * Run/Replay and Job/Build natively (not an administrator); anonymous holds Overall/Read, Job/Read and
 * Run/Replay.
 *
 * <p>Written from docs/SPEC.md, docs/DECISIONS.md D-58b/D-58c, docs/reports/security-31.md, security-32.md
 * and the #1 contract only (no src/main knowledge).
 */
@WithJenkins
public class MarkedRerunFollowUpTest {

    private JenkinsRule j;
    private WorkflowJob job;
    private BatchControlGlobalConfiguration cfg;

    @BeforeEach
    public void setUp(JenkinsRule rule) throws Exception {
        this.j = rule;
        j.jenkins.setSecurityRealm(j.createDummySecurityRealm());
        BatchControlMatrixAuthorizationStrategy strategy = StrategyFixtures.matrix(new BatchControlMatrixAuthorizationStrategy());
        strategy.add(ReplayAction.REPLAY, PermissionEntry.user("alice"));
        strategy.add(Item.BUILD, PermissionEntry.user("alice"));
        strategy.add(ReplayAction.REPLAY, PermissionEntry.user("anonymous"));
        strategy.add(Jenkins.READ, PermissionEntry.user("anonymous"));
        strategy.add(Item.READ, PermissionEntry.user("anonymous"));
        j.jenkins.setAuthorizationStrategy(strategy);
        cfg = StrategyFixtures.changeControlOn();
        BatchClock.setForTest(Clock.fixed(T0, ZoneOffset.UTC));
        job = j.jenkins.createProject(WorkflowJob.class, "replay-me");
        job.setDefinition(new CpsFlowDefinition("echo 'hello'", true));
        j.buildAndAssertSuccess(job);
        StrategyFixtures.grant("bob", "replay-me", Arrays.asList(GrantAction.CONFIGURE));
        replay("bob", 1, "echo 'planted'");
        j.waitUntilNoActivity();
        assertNotNull(job.getBuildByNumber(2), "fixture: bob's replay must have run as the marked #2");
    }

    @AfterEach
    public void resetClock() {
        BatchClock.reset();
    }

    /**
     * T-02-188 (#1.1, S-31-01, D-58c "a re-run of a marked run ... is marked too"): change control is
     * turned off; alice re-runs the marked #2 by Pipeline Rebuild (#3) and by Replay (#4), both of which
     * build (premise and guard: with the switch off nothing is refused). Change control is turned on again:
     * alice's Pipeline Rebuild of #3 and of #4 is refused (nothing queued, no build number used) and
     * recorded as a TRIGGER_BLOCKED naming alice, because #3 and #4 carry the marker. On main #3 and #4 are
     * not marked, so alice's re-run of #3 builds. Guard: alice's Pipeline Rebuild of the unmarked #1 builds.
     */
    @Test
    public void t_02_188_reRunOfAMarkedRunIsMarkedWhileChangeControlIsOff() throws Exception {
        switchChangeControl(false);
        post("alice", job.getUrl() + "2/replay/rebuild");
        j.waitUntilNoActivity();
        assertNotNull(job.getBuildByNumber(3), "guard: with change control off alice's Pipeline Rebuild of #2 runs as #3");
        replay("alice", 2, "echo 'replayed while off'");
        j.waitUntilNoActivity();
        assertNotNull(job.getBuildByNumber(4), "guard: with change control off alice's Replay of #2 runs as #4");

        switchChangeControl(true);
        int before = StrategyFixtures.records(ChangeType.TRIGGER_BLOCKED).size();
        for (int source : new int[] {3, 4}) {
            post("alice", job.getUrl() + source + "/replay/rebuild");
            j.waitUntilNoActivity();
            assertEquals(0, j.jenkins.getQueue().getItems().length, "nothing may be queued");
            assertEquals(5, job.getNextBuildNumber(), "#1.1: #" + source + ", a re-run of the marked #2 made while change control"
                    + " was off, must carry the marker, so alice's re-run of it is refused once change control is on");
        }
        List<ChangeRecord> refusals = newer(StrategyFixtures.records(ChangeType.TRIGGER_BLOCKED), before);
        assertTrue(refusals.stream().anyMatch(r -> "alice".equals(r.getUser()) && "replay-me".equals(r.getTarget())),
                "the refusal is recorded naming alice: " + describe(refusals));

        post("alice", job.getUrl() + "1/replay/rebuild");
        j.waitUntilNoActivity();
        assertNotNull(job.getBuildByNumber(5), "guard: alice's Pipeline Rebuild of the unmarked #1 builds");
    }

    /**
     * T-02-189 (#1.2, S-31-02, D-58c): the administrator re-runs the marked #2 by Pipeline Rebuild (#3,
     * allowed and marked). The REPLAY_UNDER_GRANT record of #3 names the administrator as the one who re-ran
     * it (its user), names bob as the user who originally replayed the script under the window, and does not
     * say that the administrator's permission came only from a permission window. On main the record names
     * only admin ("Run #3 was started by 'admin' as a re-run of run #2 ..."), so bob, the grant-only
     * replayer, is lost. Guard: bob's own record of #2 still names bob and says his permission came only from
     * a permission window.
     */
    @Test
    public void t_02_189_carriedMarkerRecordNamesTheReRunnerAndTheOriginalReplayer() throws Exception {
        int before = StrategyFixtures.records(ChangeType.REPLAY_UNDER_GRANT).size();
        post("admin", job.getUrl() + "2/replay/rebuild");
        j.waitUntilNoActivity();
        assertNotNull(job.getBuildByNumber(3), "premise: the administrator's re-run of the marked #2 runs as #3");

        List<ChangeRecord> marks = StrategyFixtures.records(ChangeType.REPLAY_UNDER_GRANT);
        ChangeRecord original = marks.stream().filter(r -> String.valueOf(r.getDetail()).contains("#2")
                && !String.valueOf(r.getDetail()).contains("#3")).findFirst().orElse(null);
        assertNotNull(original, "guard: the record of #2 is kept: " + describe(marks));
        assertEquals("bob", original.getUser(), "guard: the record of #2 names bob");
        assertTrue(String.valueOf(original.getDetail()).contains("only from a permission window"),
                "guard: the record of #2 says bob's permission came only from a permission window: " + original.getDetail());

        List<ChangeRecord> added = newer(marks, before);
        assertEquals(1, added.size(), "the administrator's re-run writes exactly one REPLAY_UNDER_GRANT record: " + describe(added));
        ChangeRecord carried = added.get(0);
        String detail = String.valueOf(carried.getDetail());
        assertEquals("admin", carried.getUser(), "the record of #3 names the administrator who re-ran it");
        assertTrue(detail.contains("#3"), "the record names run #3: " + detail);
        assertFalse(detail.matches("(?s).*'admin',? whose permission.*"),
                "#1.2: the record must not call the administrator a grant-only replayer: " + detail);
        assertTrue(detail.contains("'bob'"), "#1.2: the record of the carried marker must name bob, who replayed the script under"
                + " the permission window, not only the administrator who re-ran it: " + detail);
    }

    /**
     * T-02-192 (#1.5, S-32-01, D-58c "a re-run whose source cannot be resolved is refused"): a Replay cause
     * built from the unmarked build #3, which is then deleted, is submitted by anonymous (who holds
     * Run/Replay): nothing is queued, and the TRIGGER_BLOCKED record says what fired, as for a person: the
     * switch {@code unresolvedSource} and that the run it repeats could not be identified, not that a script
     * was replayed under a permission window. On main the anonymous record says {@code switch=replayedUnderGrant}
     * and "the run's script was replayed under a permission window". Guard: alice's same submission is
     * refused and recorded with {@code switch=unresolvedSource} and "could not be identified".
     */
    @Test
    public void t_02_192_unresolvedSourceIsRecordedAsUnresolvedForAnonymous() throws Exception {
        WorkflowRun third = j.buildAndAssertSuccess(job);
        hudson.model.Cause cause = replayCause(third);
        third.delete();
        org.junit.jupiter.api.Assertions.assertNull(job.getBuildByNumber(3), "premise: the source build #3 is deleted");

        int before = StrategyFixtures.records(ChangeType.TRIGGER_BLOCKED).size();
        try (ACLContext ignored = ACL.as2(User.getById("alice", true).impersonate2())) {
            schedule(new CauseAction(cause));
        }
        assertNothingQueued(4);
        List<ChangeRecord> person = newer(StrategyFixtures.records(ChangeType.TRIGGER_BLOCKED), before);
        assertTrue(person.stream().anyMatch(r -> "alice".equals(r.getUser()) && unresolvedWording(String.valueOf(r.getDetail()))),
                "guard: alice's refusal is recorded as an unresolved source: " + describe(person));

        before = StrategyFixtures.records(ChangeType.TRIGGER_BLOCKED).size();
        try (ACLContext ignored = ACL.as2(Jenkins.ANONYMOUS2)) {
            schedule(new CauseAction(cause));
        }
        assertNothingQueued(4);
        List<ChangeRecord> anonymous = newer(StrategyFixtures.records(ChangeType.TRIGGER_BLOCKED), before);
        assertEquals(1, anonymous.size(), "anonymous's refusal writes one TRIGGER_BLOCKED record: " + describe(anonymous));
        String detail = String.valueOf(anonymous.get(0).getDetail());
        assertFalse(detail.contains("replayed under a permission window") || detail.contains("switch=replayedUnderGrant"),
                "#1.5: a refused re-run whose source cannot be resolved must not be recorded as a replay under a permission window: " + detail);
        assertTrue(unresolvedWording(detail), "#1.5: anonymous's record must use the unresolved wording a person gets"
                + " (switch=unresolvedSource, the run it repeats could not be identified): " + detail);
    }

    // ---------------------------------------------------------------- helpers

    private static boolean unresolvedWording(String detail) {
        return detail.contains("switch=unresolvedSource") && detail.contains("could not be identified");
    }

    private void schedule(hudson.model.Action... actions) {
        try {
            Queue.getInstance().schedule2(job, 0, Arrays.asList(actions));
        } catch (RuntimeException refused) {
            // a refusal may surface as an exception; the queue is asserted either way
        }
    }

    private static ReplayCause replayCause(Run<?, ?> original) throws Exception {
        Constructor<ReplayCause> c = ReplayCause.class.getDeclaredConstructor(Run.class, boolean.class);
        c.setAccessible(true);
        return c.newInstance(original, false);
    }

    private void assertNothingQueued(int nextBuildNumber) throws Exception {
        assertEquals(0, j.jenkins.getQueue().getItems().length, "nothing may be queued");
        j.waitUntilNoActivity();
        assertEquals(nextBuildNumber, job.getNextBuildNumber(), "no build number may be consumed");
    }

    private void switchChangeControl(boolean on) {
        cfg.setChangeControlEnabled(on);
        cfg.save();
    }

    private void replay(String user, int number, String script) throws Exception {
        JenkinsRule.WebClient wc = j.createWebClient().withThrowExceptionOnFailingStatusCode(false).login(user);
        List<org.htmlunit.util.NameValuePair> params = new ArrayList<>();
        params.add(new org.htmlunit.util.NameValuePair("mainScript", script));
        params.add(new org.htmlunit.util.NameValuePair("json", "{\"mainScript\":\"" + script.replace("\"", "\\\"") + "\"}"));
        WebRequest req = new WebRequest(wc.createCrumbedUrl(job.getUrl() + number + "/replay/run"), HttpMethod.POST);
        req.setRequestParameters(params);
        wc.getPage(req);
    }

    private void post(String user, String path) throws Exception {
        JenkinsRule.WebClient wc = j.createWebClient().withThrowExceptionOnFailingStatusCode(false).login(user);
        wc.getPage(new WebRequest(wc.createCrumbedUrl(path), HttpMethod.POST));
    }

    private static List<ChangeRecord> newer(List<ChangeRecord> all, int before) {
        return new ArrayList<>(all.subList(Math.min(before, all.size()), all.size()));
    }

    private static String describe(List<ChangeRecord> records) {
        List<String> out = new ArrayList<>();
        records.forEach(r -> out.add(r.getType() + " user=" + r.getUser() + " target=" + r.getTarget() + " detail=" + r.getDetail()));
        return out.toString();
    }
}
