package io.jenkins.plugins.batchcontrol;

import hudson.model.Item;
import io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration;
import io.jenkins.plugins.batchcontrol.model.ChangeRecord;
import io.jenkins.plugins.batchcontrol.model.ChangeType;
import io.jenkins.plugins.batchcontrol.model.GrantAction;
import io.jenkins.plugins.batchcontrol.security.BatchControlMatrixAuthorizationStrategy;
import io.jenkins.plugins.batchcontrol.store.BatchClock;
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
import org.jenkinsci.plugins.workflow.job.WorkflowJob;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.jvnet.hudson.test.JenkinsRule;
import org.jvnet.hudson.test.junit.jupiter.WithJenkins;

import static io.jenkins.plugins.batchcontrol.StrategyFixtures.T0;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #1 (security-31 and security-32 follow-ups): what a re-run of a run marked under a permission window
 * carries and records. Matrix rows T-02-188 .. (notes 352 ..).
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

    // ---------------------------------------------------------------- helpers

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
