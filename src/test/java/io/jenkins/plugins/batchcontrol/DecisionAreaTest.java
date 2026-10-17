package io.jenkins.plugins.batchcontrol;

import hudson.model.FreeStyleProject;
import hudson.model.Item;
import hudson.model.ParametersDefinitionProperty;
import hudson.model.StringParameterDefinition;
import hudson.model.User;
import hudson.security.ACL;
import hudson.security.ACLContext;
import io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration;
import io.jenkins.plugins.batchcontrol.config.BatchControlJobProperty;
import io.jenkins.plugins.batchcontrol.model.RequestStatus;
import io.jenkins.plugins.batchcontrol.model.RunRequest;
import io.jenkins.plugins.batchcontrol.policy.RunRequestService;
import io.jenkins.plugins.batchcontrol.security.BatchControlPermissions;
import java.net.URL;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;
import jenkins.model.Jenkins;
import org.htmlunit.HttpMethod;
import org.htmlunit.Page;
import org.htmlunit.WebRequest;
import org.htmlunit.html.DomElement;
import org.htmlunit.html.DomNode;
import org.htmlunit.html.HtmlElement;
import org.htmlunit.html.HtmlPage;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.jvnet.hudson.test.JenkinsRule;
import org.jvnet.hudson.test.MockAuthorizationStrategy;
import org.jvnet.hudson.test.junit.jupiter.WithJenkins;

import static io.jenkins.plugins.batchcontrol.DecisionAreaFixtures.button;
import static io.jenkins.plugins.batchcontrol.DecisionAreaFixtures.commentBoxes;
import static io.jenkins.plugins.batchcontrol.DecisionAreaFixtures.decide;
import static io.jenkins.plugins.batchcontrol.DecisionAreaFixtures.headings;
import static io.jenkins.plugins.batchcontrol.DecisionAreaFixtures.target;
import static io.jenkins.plugins.batchcontrol.DecisionAreaFixtures.theCommentBox;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Wave D, group D3, issue #18 item 5 (matrix rows T-UI-270..275, note 362): on the run request
 * page the Decision section comes right after Parameters, before the recent runs and the approver
 * changes. It has one comment box and two buttons, Approve and Reject, posting to the unchanged
 * {@code /approve} and {@code /reject} endpoints with the {@code comment} field. A reject without a
 * comment is refused with the error next to the box and the text kept; while the job is disabled
 * only Reject is offered (D-55). Endpoints and permission checks are unchanged.
 *
 * <p>The section is read through {@link DecisionAreaFixtures}, which does not assume one form or
 * two. Decisions are made by pressing the buttons in a JavaScript-enabled client, so the crumb is
 * handled as in a browser.
 *
 * <p>Written from the Wave D contract (D3, frozen 2026-10-10), issue #18, SPEC 5 and D-55, and pages
 * rendered on origin/main (d80e5fe); no src/main knowledge.
 */
@WithJenkins
public class DecisionAreaTest {

    private JenkinsRule j;
    private FreeStyleProject job;

    @BeforeEach
    public void setUp(JenkinsRule rule) throws Exception {
        this.j = rule;
        j.jenkins.setSecurityRealm(j.createDummySecurityRealm());
        j.jenkins.setAuthorizationStrategy(new MockAuthorizationStrategy()
                .grant(Jenkins.ADMINISTER).everywhere().to("admin")
                .grant(Jenkins.READ, Item.READ, Item.BUILD, BatchControlPermissions.REQUEST).everywhere().to("u1")
                .grant(Jenkins.READ, Item.READ, BatchControlPermissions.APPROVE).everywhere().to("a1")
                .grant(Jenkins.READ, Item.READ, BatchControlPermissions.APPROVE).everywhere().to("a2"));
        BatchControlGlobalConfiguration cfg = BatchControlGlobalConfiguration.get();
        cfg.setChangeControlEnabled(true);
        cfg.setApprovers(Arrays.asList("a1", "a2"));
        cfg.save();
        job = j.createFreeStyleProject("batch-x");
        job.addProperty(new ParametersDefinitionProperty(new StringParameterDefinition("DAY", "2026-10-01"),
                new StringParameterDefinition("MODE", "full")));
        j.buildAndAssertSuccess(job); // a recent run, so the page has its recent-runs section
        cfg.setRunControlEnabled(true);
        cfg.save();
        BatchControlFixtures.setBatchControl(job, new BatchControlJobProperty(true));
    }

    /**
     * T-UI-270 (#18.5): for the designated approver a1 the heading right after "Parameters" is
     * "Decision", which comes before "Recent Runs of This Job" and "Approver Changes" (u1 changed
     * the approvers from a1 to a1, a2, so that section is shown).
     */
    @Test
    public void t_ui_270_decisionComesRightAfterParameters() throws Exception {
        RunRequest request = request("order check");
        as("u1", () -> RunRequestService.get().changeApprovers(request.getId(), List.of("a1", "a2")));
        List<String> h2 = headings(page("a1", request));
        int parameters = h2.indexOf("Parameters");
        int decision = h2.indexOf("Decision");
        int recent = h2.indexOf("Recent Runs of This Job");
        int changes = h2.indexOf("Approver Changes");
        assertTrue(parameters >= 0 && recent >= 0 && changes >= 0, "guard: the page shows Parameters, Recent Runs of This"
                + " Job and Approver Changes: " + h2);
        assertTrue(decision >= 0, "the approver must be offered the Decision section: " + h2);
        assertEquals(parameters + 1, decision, "the Decision section must come right after Parameters: " + h2);
        assertTrue(decision < recent && decision < changes, "the Decision section must come before the recent runs and"
                + " the approver changes: " + h2);
    }

    /**
     * T-UI-271 (#18.5, endpoints and permission checks unchanged): guards first — GET of
     * {@code /approve} and {@code /reject} is refused, a POST without the crumb answers 403, the
     * requester u1 and a2 (an approver on the list, not designated on this request) are refused
     * with 4xx, and the request stays PENDING. Then the Decision section has exactly one comment box
     * and one Approve and one Reject button, posting to {@code .../approve} and {@code .../reject}.
     */
    @Test
    public void t_ui_271_oneCommentBoxAndTwoButtonsOnTheSameEndpoints() throws Exception {
        RunRequest request = request("endpoint check");
        String base = "batch-control/requests/" + request.getId() + "/";
        JenkinsRule.WebClient a1 = client("a1", false);
        for (String verb : List.of("approve", "reject")) {
            int get = a1.getPage(new WebRequest(new URL(j.getURL(), base + verb), HttpMethod.GET)).getWebResponse().getStatusCode();
            assertTrue(get >= 400, "guard: GET " + verb + " must be refused, got " + get);
            int noCrumb = a1.getPage(new WebRequest(new URL(j.getURL(), base + verb), HttpMethod.POST)).getWebResponse().getStatusCode();
            assertEquals(403, noCrumb, "guard: a POST " + verb + " without the crumb must answer 403");
            for (String other : List.of("u1", "a2")) {
                int code = ApproverFormFixtures.decideRun(j, other, request.getId(), verb, "not mine").getStatusCode();
                assertTrue(code >= 400 && code < 500, "guard: " + other + " may not " + verb + ", got " + code);
            }
        }
        assertEquals(RequestStatus.PENDING, RunRequestService.get().load(request.getId()).getStatus(), "guard: still PENDING");

        HtmlPage page = page("a1", request);
        assertEquals(1, commentBoxes(page).size(), "the Decision section must have ONE comment box, found "
                + commentBoxes(page).size());
        HtmlElement approve = button(page, "Approve");
        HtmlElement reject = button(page, "Reject");
        assertNotNull(approve, "the Decision section must offer Approve");
        assertNotNull(reject, "the Decision section must offer Reject");
        String expected = new URL(j.getURL(), base).getPath();
        assertEquals(expected + "approve", target(page, approve), "Approve must post to the existing approve endpoint");
        assertEquals(expected + "reject", target(page, reject), "Reject must post to the existing reject endpoint");
    }

    /**
     * T-UI-272 (#18.5): a1 types "ship it" into the one box and presses Approve: the request is
     * approved by a1 with that comment (with the crumb, as a browser does).
     */
    @Test
    public void t_ui_272_approveThroughTheOneBox() throws Exception {
        RunRequest request = request("approve check");
        HtmlPage page = page("a1", request);
        theCommentBox(page);
        decide(page, "Approve", "ship it");
        RunRequest after = RunRequestService.get().load(request.getId());
        assertTrue(after.getStatus() == RequestStatus.APPROVED || after.getStatus() == RequestStatus.EXECUTED,
                "Approve must approve the request, status " + after.getStatus());
        assertEquals("a1", after.getDecidedBy());
        assertEquals("ship it", after.getDecisionComment(), "the comment typed in the one box goes with the approval");
    }

    /**
     * T-UI-273 (#18.5): a1 types "wrong day" into the one box and presses Reject: the request is
     * rejected by a1 with that comment and no build runs.
     */
    @Test
    public void t_ui_273_rejectThroughTheOneBox() throws Exception {
        RunRequest request = request("reject check");
        int next = job.getNextBuildNumber();
        HtmlPage page = page("a1", request);
        theCommentBox(page);
        decide(page, "Reject", "wrong day");
        RunRequest after = RunRequestService.get().load(request.getId());
        assertEquals(RequestStatus.REJECTED, after.getStatus(), "Reject must reject the request");
        assertEquals("a1", after.getDecidedBy());
        assertEquals("wrong day", after.getDecisionComment(), "the comment typed in the one box goes with the rejection");
        j.waitUntilNoActivity();
        assertEquals(next, job.getNextBuildNumber(), "no build may run after a rejection");
    }

    /**
     * T-UI-274 (#18.5, SPEC 5 and 6): a1 presses Reject with only blanks ("   ") in the one box: the
     * request stays PENDING; the page still shows the one box holding "   " (the text is kept), an
     * error naming the comment right next to it, and both buttons; no bare error page.
     */
    @Test
    public void t_ui_274_rejectWithoutACommentIsRefusedNextToTheBoxAndKeepsTheText() throws Exception {
        RunRequest request = request("refusal check");
        HtmlPage page = page("a1", request);
        theCommentBox(page);
        Page answer = decide(page, "Reject", "   ");
        assertEquals(RequestStatus.PENDING, RunRequestService.get().load(request.getId()).getStatus(),
                "a reject without a comment must be refused (SPEC 5)");
        assertTrue(answer instanceof HtmlPage, "the refusal must be a page");
        HtmlPage refused = (HtmlPage) answer;
        UsabilityFixtures.assertNotBareErrorPage("reject without a comment", refused);
        HtmlElement box = theCommentBox(refused);
        assertEquals("   ", DecisionAreaFixtures.value(box), "the text in the box must be kept");
        DomElement error = null;
        for (DomNode n : refused.querySelectorAll("[data-batch-control-field-error='comment'], .error, [role=alert]")) {
            if (Pattern.compile("(?i)comment").matcher(n.asNormalizedText()).find()
                    && DecisionAreaFixtures.nextTo(box, (DomElement) n)) {
                error = (DomElement) n;
            }
        }
        assertNotNull(error, "an error naming the comment must be shown next to the one box: "
                + ((DomElement) box.getParentNode()).asXml());
        assertNotNull(button(refused, "Approve"), "Approve must still be offered");
        assertNotNull(button(refused, "Reject"), "Reject must still be offered");
    }

    /**
     * T-UI-275 (#18.5, D-55): while the job is disabled the Decision section, right after
     * Parameters, says so and offers only Reject next to the one box; Reject through it works.
     * Guard: a direct POST of approve is refused and the request stays PENDING.
     */
    @Test
    public void t_ui_275_disabledJobOffersOnlyReject() throws Exception {
        RunRequest request = request("disabled check");
        job.disable();
        assertTrue(ApproverFormFixtures.decideRun(j, "a1", request.getId(), "approve", "ok").getStatusCode() >= 400,
                "guard: approving while the job is disabled is refused (D-55)");
        assertEquals(RequestStatus.PENDING, RunRequestService.get().load(request.getId()).getStatus(), "guard: still PENDING");

        HtmlPage page = page("a1", request);
        List<String> h2 = headings(page);
        assertEquals(h2.indexOf("Parameters") + 1, h2.indexOf("Decision"), "the Decision section must come right after"
                + " Parameters: " + h2);
        assertTrue(page.asNormalizedText().toLowerCase(java.util.Locale.ROOT).contains("disabled"),
                "the page must say the job is disabled");
        assertNull(button(page, "Approve"), "Approve must not be offered while the job is disabled");
        assertNotNull(button(page, "Reject"), "Reject must be offered while the job is disabled");
        theCommentBox(page);
        decide(page, "Reject", "job is retired");
        RunRequest after = RunRequestService.get().load(request.getId());
        assertEquals(RequestStatus.REJECTED, after.getStatus(), "Reject must work while the job is disabled");
        assertEquals("job is retired", after.getDecisionComment());
    }

    // ------------------------------------------------------------------ helpers

    private RunRequest request(String reason) throws Exception {
        Map<String, String> params = new LinkedHashMap<>();
        params.put("DAY", "2026-10-09");
        params.put("MODE", "delta");
        try (ACLContext ignored = ACL.as2(User.getById("u1", true).impersonate2())) {
            return RunRequestService.get().create(job, params, reason, "a1");
        }
    }

    private HtmlPage page(String user, RunRequest request) throws Exception {
        Page answer = client(user, true).getPage(new WebRequest(
                new URL(j.getURL(), "batch-control/requests/" + request.getId() + "/"), HttpMethod.GET));
        assertEquals(200, answer.getWebResponse().getStatusCode(), user + " opens the request page");
        return (HtmlPage) answer;
    }

    private JenkinsRule.WebClient client(String user, boolean javaScript) throws Exception {
        JenkinsRule.WebClient wc = j.createWebClient().withThrowExceptionOnFailingStatusCode(false).login(user);
        wc.getOptions().setJavaScriptEnabled(javaScript);
        wc.getOptions().setThrowExceptionOnScriptError(false);
        return wc;
    }

    private interface Body {
        void run() throws Exception;
    }

    private static void as(String user, Body body) throws Exception {
        try (ACLContext ignored = ACL.as2(User.getById(user, true).impersonate2())) {
            body.run();
        }
    }
}
