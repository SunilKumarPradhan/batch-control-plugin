package io.jenkins.plugins.batchcontrol;

import hudson.model.FreeStyleProject;
import hudson.model.Item;
import io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration;
import io.jenkins.plugins.batchcontrol.config.BatchControlJobProperty;
import io.jenkins.plugins.batchcontrol.model.RequestStatus;
import io.jenkins.plugins.batchcontrol.policy.ActivationService;
import io.jenkins.plugins.batchcontrol.policy.GrantRequestService;
import io.jenkins.plugins.batchcontrol.policy.RunRequestService;
import io.jenkins.plugins.batchcontrol.security.BatchControlPermissions;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.function.Supplier;
import jenkins.model.Jenkins;
import org.htmlunit.HttpMethod;
import org.htmlunit.Page;
import org.htmlunit.WebRequest;
import org.htmlunit.WebResponse;
import org.htmlunit.html.DomNode;
import org.htmlunit.html.HtmlPage;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.jvnet.hudson.test.JenkinsRule;
import org.jvnet.hudson.test.MockAuthorizationStrategy;
import org.jvnet.hudson.test.junit.jupiter.WithJenkins;

import static io.jenkins.plugins.batchcontrol.ActivationFixtures.decideActivation;
import static io.jenkins.plugins.batchcontrol.ActivationFixtures.submitActivationOk;
import static io.jenkins.plugins.batchcontrol.ApproverFormFixtures.approverPairs;
import static io.jenkins.plugins.batchcontrol.ApproverFormFixtures.assertSuccess;
import static io.jenkins.plugins.batchcontrol.ApproverFormFixtures.changeGrantApprovers;
import static io.jenkins.plugins.batchcontrol.ApproverFormFixtures.changeRunApprovers;
import static io.jenkins.plugins.batchcontrol.ApproverFormFixtures.decideGrant;
import static io.jenkins.plugins.batchcontrol.ApproverFormFixtures.decideRun;
import static io.jenkins.plugins.batchcontrol.ApproverFormFixtures.excerpt;
import static io.jenkins.plugins.batchcontrol.ApproverFormFixtures.submitGrantOk;
import static io.jenkins.plugins.batchcontrol.ApproverFormFixtures.submitRunOk;
import static io.jenkins.plugins.batchcontrol.BatchControlFixtures.setBatchControl;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #1 (e2e-05 EX-01): a stale "change approvers" submission on a run, grant or activation request that is
 * already decided says so in plain words. Matrix row T-03-94 (note 358).
 *
 * <p>Basis: SPEC item 3 (the requester changes the designated approvers while the request is PENDING; D-26,
 * D-37); SPEC 6 usability ("every refusal ... tells the user in plain words why and what to do instead";
 * "invalid input is refused with a message next to the field" applies to a field that is wrong, and here no
 * field is); docs/reports/e2e-05.md EX-01; the #1 contract (frozen 2026-10-10): "a plain message that names
 * the request's current status, for example 'This request is already APPROVED; approvers can no longer be
 * changed.'"
 *
 * <p>Run and change control on; u1 holds Overall/Read, Item/Read, Job/Build, BatchControl/Request and
 * RequestGrant; a1 and a2 (both on the approver list) hold Approve. Each request designates a1; the stale
 * submission asks for a2 instead, as the requester's still-open form would.
 *
 * <p>Written from docs/SPEC.md, docs/DECISIONS.md D-26/D-37, docs/reports/e2e-05.md and the #1 contract only
 * (no src/main knowledge).
 */
@WithJenkins
public class DecidedRequestApproverChangeTest {

    private JenkinsRule j;

    @BeforeEach
    public void setUp(JenkinsRule rule) throws Exception {
        this.j = rule;
        j.jenkins.setSecurityRealm(j.createDummySecurityRealm());
        j.jenkins.setAuthorizationStrategy(new MockAuthorizationStrategy()
                .grant(Jenkins.ADMINISTER).everywhere().to("admin")
                .grant(Jenkins.READ, Item.READ, Item.BUILD, BatchControlPermissions.REQUEST,
                        BatchControlPermissions.REQUEST_GRANT).everywhere().to("u1")
                .grant(Jenkins.READ, Item.READ, BatchControlPermissions.APPROVE).everywhere().to("a1", "a2"));
        BatchControlGlobalConfiguration cfg = BatchControlGlobalConfiguration.get();
        cfg.setRunControlEnabled(true);
        cfg.setChangeControlEnabled(true);
        cfg.setApprovers(Arrays.asList("a1", "a2"));
        cfg.save();
    }

    /**
     * T-03-94 (#1.7, EX-01, SPEC 3, SPEC 6 usability): for a run request a1 rejected, a grant request a1
     * approved and an activation request a1 approved, u1 (the requester) posts {@code changeApprover} with
     * a2. Each answer is a 4xx whose text names the request's current status (read from the service:
     * REJECTED, APPROVED, APPROVED) and does not say "Correct the fields marked below"; the designated
     * approvers stay [a1]. On main each answers 400 "Correct the fields marked below" without the status.
     * Guard: on a PENDING request of each kind the same post succeeds and the approvers become [a2].
     */
    @Test
    public void t_03_94_staleApproverChangeOnADecidedRequestNamesItsStatus() throws Exception {
        FreeStyleProject job = j.createFreeStyleProject("batch-x");
        setBatchControl(job, new BatchControlJobProperty(true));
        FreeStyleProject inactive = j.createFreeStyleProject("new-x");
        BatchControlJobProperty cleared = new BatchControlJobProperty(true);
        cleared.setBlockTimer(false);
        cleared.setBlockUpstream(false);
        setBatchControl(inactive, cleared);
        assertFalse(ActivationService.get().isActivated(inactive), "fixture: new-x starts not activated");

        // guards: PENDING requests of each kind accept the change
        String pendingRun = submitRunOk(j, "u1", job, "pending run", "a1");
        assertSuccess(changeRunApprovers(j, "u1", pendingRun, "a2"), "guard: the pending run request's approvers change");
        assertEquals(List.of("a2"), RunRequestService.get().load(pendingRun).getApprovers(), "guard: the run request now names a2");
        String pendingGrant = submitGrantOk(j, "u1", "batch-x", List.of("CONFIGURE"), 30, "pending grant", null, "a1");
        assertSuccess(changeGrantApprovers(j, "u1", pendingGrant, "a2"), "guard: the pending grant request's approvers change");
        assertEquals(List.of("a2"), GrantRequestService.get().load(pendingGrant).getApprovers(), "guard: the grant request now names a2");
        String pendingActivation = submitActivationOk(j, "u1", inactive, "ACTIVATE", "pending activation", "a1");
        assertSuccess(changeActivationApprovers(pendingActivation, "a2"), "guard: the pending activation request's approvers change");
        assertEquals(List.of("a2"), ActivationService.get().load(pendingActivation).getApprovers(),
                "guard: the activation request now names a2");
        assertSuccess(ApproverFormFixtures.post(j, "u1", "batch-control/requests/" + pendingRun + "/cancel", List.of()),
                "fixture: u1 cancels the pending run request");
        assertSuccess(ApproverFormFixtures.post(j, "u1", "batch-control/grants/" + pendingGrant + "/cancel", List.of()),
                "fixture: u1 cancels the pending grant request");
        assertSuccess(ApproverFormFixtures.post(j, "u1", "batch-control/activations/" + pendingActivation + "/cancel", List.of()),
                "fixture: u1 cancels the pending activation request");

        String run = submitRunOk(j, "u1", job, "run to be rejected", "a1");
        assertSuccess(decideRun(j, "a1", run, "reject", "not this month"), "fixture: a1 rejects the run request");
        assertStaleChangeNamesStatus("run request", staleChange("requests", run),
                () -> RunRequestService.get().load(run).getStatus(), () -> RunRequestService.get().load(run).getApprovers());

        String grant = submitGrantOk(j, "u1", "batch-x", List.of("CONFIGURE"), 30, "grant to be approved", null, "a1");
        assertSuccess(decideGrant(j, "a1", grant, "approve", "ok"), "fixture: a1 approves the grant request");
        assertStaleChangeNamesStatus("grant request", staleChange("grants", grant),
                () -> GrantRequestService.get().load(grant).getStatus(), () -> GrantRequestService.get().load(grant).getApprovers());

        String activation = submitActivationOk(j, "u1", inactive, "ACTIVATE", "activation to be approved", "a1");
        assertSuccess(decideActivation(j, "a1", activation, "approve", "ok"), "fixture: a1 approves the activation request");
        assertStaleChangeNamesStatus("activation request", staleChange("activations", activation),
                () -> ActivationService.get().load(activation).getStatus(), () -> ActivationService.get().load(activation).getApprovers());
    }

    private WebResponse changeActivationApprovers(String id, String... approvers) throws Exception {
        return ApproverFormFixtures.post(j, "u1", "batch-control/activations/" + id + "/changeApprover", approverPairs(approvers));
    }

    /** {@code POST <kind>/<id>/changeApprover} with {@code a2} as u1, as a page (redirects not followed). */
    private Page staleChange(String kind, String id) throws Exception {
        JenkinsRule.WebClient wc = ApproverFormFixtures.client(j, "u1");
        WebRequest request = new WebRequest(wc.createCrumbedUrl("batch-control/" + kind + "/" + id + "/changeApprover"), HttpMethod.POST);
        request.setCharset(StandardCharsets.UTF_8);
        request.setRequestParameters(new ArrayList<>(approverPairs("a2")));
        return wc.getPage(request);
    }

    /**
     * The refusal's own message: the texts of the answer's {@code role="alert"} elements (the convention of
     * this plugin's refusals, see {@code ApproverFormFixtures#alerts}); the whole text when it has none. The
     * request page around it shows the status in its detail table, so the whole page cannot tell whether the
     * message names it.
     */
    private static String message(Page answer) {
        if (answer instanceof HtmlPage page) {
            List<String> alerts = new ArrayList<>();
            for (DomNode alert : page.querySelectorAll("[role=alert]")) {
                String text = alert.asNormalizedText().trim();
                if (!text.isEmpty()) {
                    alerts.add(text);
                }
            }
            return alerts.isEmpty() ? page.asNormalizedText() : String.join(" | ", alerts);
        }
        return answer.getWebResponse().getContentAsString();
    }

    private static void assertStaleChangeNamesStatus(String what, Page answer, Supplier<RequestStatus> status,
                                                     Supplier<List<String>> approvers) {
        RequestStatus now = status.get();
        assertNotEquals(RequestStatus.PENDING, now, "premise: the " + what + " is decided");
        int code = answer.getWebResponse().getStatusCode();
        String text = UsabilityFixtures.text(answer);
        String message = message(answer);
        assertTrue(code >= 400 && code < 500, "the stale change of the " + what + "'s approvers is refused with a 4xx, got " + code
                + ": " + excerpt(text));
        assertEquals(List.of("a1"), approvers.get(), "the decided " + what + " keeps its approvers");
        UsabilityFixtures.assertPlainRefusal("the stale approver change of the " + what, text, null);
        assertFalse(text.contains("Correct the fields marked below"), "#1.7: no field is wrong, so the answer for the decided " + what
                + " must not say 'Correct the fields marked below': " + excerpt(message));
        assertTrue(message.toLowerCase(Locale.ROOT).contains(now.name().toLowerCase(Locale.ROOT)), "#1.7: the refusal message must name"
                + " the " + what + "'s current status " + now + " (it is already decided): " + excerpt(message));
    }
}
