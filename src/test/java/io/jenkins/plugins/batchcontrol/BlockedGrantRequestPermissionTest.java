package io.jenkins.plugins.batchcontrol;

import hudson.model.Item;
import io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration;
import io.jenkins.plugins.batchcontrol.model.ChangeRecord;
import io.jenkins.plugins.batchcontrol.model.ChangeType;
import io.jenkins.plugins.batchcontrol.security.BatchControlMatrixAuthorizationStrategy;
import io.jenkins.plugins.batchcontrol.security.BatchControlPermissions;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import jenkins.model.Jenkins;
import org.htmlunit.WebResponse;
import org.jenkinsci.plugins.matrixauth.PermissionEntry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.jvnet.hudson.test.JenkinsRule;
import org.jvnet.hudson.test.junit.jupiter.WithJenkins;

import static io.jenkins.plugins.batchcontrol.ApproverFormFixtures.excerpt;
import static io.jenkins.plugins.batchcontrol.ApproverFormFixtures.grantRequestIds;
import static io.jenkins.plugins.batchcontrol.ApproverFormFixtures.submitGrant;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #44: a POST to {@code batch-control/grants/create} by a user without BatchControl/RequestGrant is refused
 * with 403 and writes no {@code GRANT_REQUEST_BLOCKED} record, whatever the change control switch. Matrix
 * rows T-08-260 and T-08-261 (note 351).
 *
 * <p>Basis: SPEC item 2 (the five permissions; BatchControl/RequestGrant is the permission to request a
 * window); SPEC item 8 and LIMITATIONS 29 (with change control off a window request "is refused with a
 * message that says why, plus a GRANT_REQUEST_BLOCKED record"); CLAUDE.md (a state-changing web method
 * checks the permission before anything else); the #44 contract (frozen 2026-10-10): "A user without
 * RequestGrant gets 403, and no record is written, whatever the switch. A user with RequestGrant still gets
 * the 4xx 'Change control is off' refusal and one GRANT_REQUEST_BLOCKED record (guard)."
 *
 * <p>Batch Control matrix strategy; u1 holds Overall/Read, Item/Read and RequestGrant; a1 (the designated
 * approver) holds Overall/Read, Item/Read and Approve only; admin holds Overall/Administer. Change control is
 * off and run control on (the closed Grants screen, as in T-GAP-346) unless a step says otherwise.
 *
 * <p>The contract's second user, a Manage-only user, is not a row: BatchControl/Manage implies RequestGrant
 * (USER-GUIDE "Manage ... implies the other four"; DECISIONS P-02; note 269; observed on main: a Manage-only
 * user passes {@code hasPermission(RequestGrant)}), so such a user holds RequestGrant and is the guard case,
 * not the refused one (note 351).
 *
 * <p>Written from docs/SPEC.md, docs/DECISIONS.md, docs/LIMITATIONS.md, docs/USER-GUIDE.md and the #44
 * contract only (no src/main knowledge).
 */
@WithJenkins
public class BlockedGrantRequestPermissionTest {

    private static final String REASON = "blocked-grant-44";

    private JenkinsRule j;
    private BatchControlGlobalConfiguration cfg;

    @BeforeEach
    public void setUp(JenkinsRule rule) throws Exception {
        this.j = rule;
        j.jenkins.setSecurityRealm(j.createDummySecurityRealm());
        BatchControlMatrixAuthorizationStrategy strategy = new BatchControlMatrixAuthorizationStrategy();
        strategy.add(Jenkins.ADMINISTER, PermissionEntry.user("admin"));
        for (String userId : new String[] {"u1", "a1"}) {
            strategy.add(Jenkins.READ, PermissionEntry.user(userId));
            strategy.add(Item.READ, PermissionEntry.user(userId));
        }
        strategy.add(BatchControlPermissions.REQUEST_GRANT, PermissionEntry.user("u1"));
        strategy.add(BatchControlPermissions.APPROVE, PermissionEntry.user("a1"));
        j.jenkins.setAuthorizationStrategy(strategy);
        cfg = BatchControlGlobalConfiguration.get();
        cfg.setChangeControlEnabled(true);
        cfg.setApprovers(Arrays.asList("a1"));
        cfg.save();
        j.createFreeStyleProject("job-k");
        assertFalse(StrategyFixtures.has(j.jenkins, "a1", BatchControlPermissions.REQUEST_GRANT), "premise: a1 lacks RequestGrant");
        assertTrue(StrategyFixtures.has(j.jenkins, "a1", BatchControlPermissions.APPROVE), "premise: a1 holds Approve");
    }

    /**
     * T-08-260 (#44): change control off, run control on. a1 (Approve only) posts a well-formed window
     * request for {@code job-k}: HTTP 403, no new GRANT_REQUEST_BLOCKED record, no grant request stored. On
     * main the post answers 400 with the change-control refusal and writes one record naming a1. Guard: u1
     * (RequestGrant) posts the same request: a 4xx that is not 403, a plain refusal naming change control,
     * exactly one new GRANT_REQUEST_BLOCKED record naming u1, and no grant request stored.
     */
    @Test
    public void t_08_260_userWithoutRequestGrantWritesNoBlockedRecordWhileSwitchIsOff() throws Exception {
        switchChangeControl(false);
        Set<String> requests = grantRequestIds();
        int blocked = blocked().size();

        WebResponse refused = create("a1");
        List<ChangeRecord> afterA1 = blocked();
        assertEquals(blocked, afterA1.size(), "#44: a user without RequestGrant must not write a GRANT_REQUEST_BLOCKED record: "
                + describe(afterA1.subList(Math.min(blocked, afterA1.size()), afterA1.size())));
        assertEquals(403, refused.getStatusCode(), "#44: a user without RequestGrant must get 403, got "
                + refused.getStatusCode() + ": " + excerpt(refused.getContentAsString()));
        assertEquals(requests, grantRequestIds(), "nothing may be stored for a1");

        WebResponse guard = create("u1");
        int code = guard.getStatusCode();
        assertTrue(code >= 400 && code < 500 && code != 403, "guard: u1 (RequestGrant) gets the 4xx change-control refusal, not 403;"
                + " got " + code + ": " + excerpt(guard.getContentAsString()));
        UsabilityFixtures.assertPlainRefusal("guard: u1's request while change control is off", textOf(guard),
                java.util.regex.Pattern.compile("(?i)change control"));
        List<ChangeRecord> afterU1 = blocked();
        assertEquals(blocked + 1, afterU1.size(), "guard: exactly one GRANT_REQUEST_BLOCKED record for u1's refused request: "
                + describe(afterU1));
        assertEquals("u1", afterU1.get(afterU1.size() - 1).getUser(), "guard: the record names u1");
        assertEquals(requests, grantRequestIds(), "guard: nothing is stored for u1 either");
    }

    /**
     * T-08-261 (#44 "whatever the switch"): change control on. a1 (Approve only) posts the same request:
     * HTTP 403, no GRANT_REQUEST_BLOCKED record, no grant request stored. Guard: u1's same request is
     * accepted and stores exactly one grant request, with no GRANT_REQUEST_BLOCKED record.
     */
    @Test
    public void t_08_261_userWithoutRequestGrantGets403WhileSwitchIsOn() throws Exception {
        Set<String> requests = grantRequestIds();
        int blocked = blocked().size();

        WebResponse refused = create("a1");
        assertEquals(403, refused.getStatusCode(), "#44: a user without RequestGrant must get 403 with change control on, got "
                + refused.getStatusCode() + ": " + excerpt(refused.getContentAsString()));
        assertEquals(blocked, blocked().size(), "no GRANT_REQUEST_BLOCKED record for a1");
        assertEquals(requests, grantRequestIds(), "nothing may be stored for a1");

        ApproverFormFixtures.assertSuccess(create("u1"), "guard: u1's request with change control on");
        Set<String> created = grantRequestIds();
        created.removeAll(requests);
        assertEquals(1, created.size(), "guard: exactly one grant request is stored for u1: " + created);
        assertEquals(blocked, blocked().size(), "guard: an accepted request writes no GRANT_REQUEST_BLOCKED record");
    }

    // ------------------------------------------------------------------ helpers

    private void switchChangeControl(boolean on) throws Exception {
        cfg.setRunControlEnabled(true);
        cfg.setChangeControlEnabled(on);
        cfg.save();
    }

    private WebResponse create(String userId) throws Exception {
        return submitGrant(j, userId, "job-k", List.of("CONFIGURE"), 30, REASON, null, "a1");
    }

    private static String textOf(WebResponse response) {
        return response.getContentAsString().replaceAll("<[^>]*>", " ").replace("&#039;", "'").replace("&#39;", "'")
                .replace("&quot;", "\"").replace("&amp;", "&").replaceAll("\\s+", " ").trim();
    }

    private static List<ChangeRecord> blocked() {
        return ApproverFormFixtures.records(ChangeType.GRANT_REQUEST_BLOCKED);
    }

    private static String describe(List<ChangeRecord> records) {
        List<String> out = new ArrayList<>();
        records.forEach(r -> out.add("user=" + r.getUser() + " target=" + r.getTarget() + " detail="
                + String.valueOf(r.getDetail()).toLowerCase(Locale.ROOT)));
        return out.toString();
    }
}
