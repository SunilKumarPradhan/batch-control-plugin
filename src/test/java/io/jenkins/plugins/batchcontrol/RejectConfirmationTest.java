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
import java.util.Map;
import jenkins.model.Jenkins;
import org.htmlunit.HttpMethod;
import org.htmlunit.Page;
import org.htmlunit.WebRequest;
import org.htmlunit.html.HtmlElement;
import org.htmlunit.html.HtmlInput;
import org.htmlunit.html.HtmlPage;
import org.htmlunit.html.HtmlTextArea;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.jvnet.hudson.test.JenkinsRule;
import org.jvnet.hudson.test.MockAuthorizationStrategy;
import org.jvnet.hudson.test.junit.jupiter.WithJenkins;

import static io.jenkins.plugins.batchcontrol.DecisionAreaFixtures.button;
import static io.jenkins.plugins.batchcontrol.DecisionAreaFixtures.theCommentBox;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Issue #93, matrix rows T-UI-292 and T-UI-293 (note 365): rejecting a run request from the
 * request page asks for confirmation first.
 *
 * <p>The tests stub {@code window.dialog.confirm} — HtmlUnit has no real browser dialog, so they
 * assert the page <em>asks</em> for confirmation (one call, the page's sentence) and that the
 * form is posted only when the stub confirms. The dialog itself, in a real browser, is covered by
 * the e2e check in {@code e2e/r27/decision_tables.py} (section R93).
 *
 * <p>Written from the TEST-MATRIX rows and note 365; no src/main knowledge beyond the matrix.
 */
@WithJenkins
class RejectConfirmationTest {

    private JenkinsRule j;
    private FreeStyleProject job;

    @BeforeEach
    void setUp(JenkinsRule rule) throws Exception {
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
     * T-UI-292 (#93): pressing Reject with a comment opens core's confirmation first, carrying the
     * page's sentence; nothing is posted until the approver confirms.
     */
    @Test
    void t_ui_292_rejectOpensConfirmationWithThePageSentence() throws Exception {
        RunRequest request = request("order check");
        HtmlPage page = page("a1", request);
        stubDialog(page, true);
        typeComment(page, "wrong day");
        HtmlElement reject = button(page, "Reject");
        assertNotNull(reject, "the Decision section must offer Reject");
        reject.click();
        // dialog.confirm is called synchronously by the click handler, so the recording is already
        // there; the confirmation itself (and the post) resolves in background JavaScript.
        assertEquals(1, dialogCalls(page), "pressing Reject must open the confirmation exactly once");
        assertEquals("Reject this run request?", dialogTitle(page), "the dialog title");
        assertEquals("Rejection is final for this request; a rejected request cannot be reopened.",
                dialogMessage(page), "the dialog message must match the sentence on the page");
        page.getWebClient().waitForBackgroundJavaScript(2000);
    }

    /**
     * T-UI-292 (#93): dismissing the confirmation (Cancel or Escape) posts nothing and the request
     * stays PENDING.
     */
    @Test
    void t_ui_292_dismissingTheDialogPostsNothingAndRequestStaysPending() throws Exception {
        RunRequest request = request("order check");
        HtmlPage page = page("a1", request);
        stubDialog(page, false); // the stub rejects: Cancel / Escape
        typeComment(page, "wrong day");
        HtmlElement reject = button(page, "Reject");
        assertNotNull(reject, "the Decision section must offer Reject");
        reject.click();
        assertEquals(1, dialogCalls(page), "pressing Reject must open the confirmation exactly once");
        page.getWebClient().waitForBackgroundJavaScript(2000);
        Page current = page.getWebClient().getCurrentWindow().getEnclosedPage();
        assertSame(page, current, "dismissing the dialog must not post or navigate");
        assertEquals(RequestStatus.PENDING, RunRequestService.get().load(request.getId()).getStatus(),
                "the request must stay PENDING after the dialog is dismissed");
    }

    /**
     * T-UI-292 (#93): confirming the dialog rejects the request with the typed comment.
     */
    @Test
    void t_ui_292_confirmingTheDialogRejectsTheRequest() throws Exception {
        RunRequest request = request("order check");
        HtmlPage page = page("a1", request);
        stubDialog(page, true); // the stub confirms
        typeComment(page, "wrong day");
        HtmlElement reject = button(page, "Reject");
        assertNotNull(reject, "the Decision section must offer Reject");
        reject.click();
        page.getWebClient().waitForBackgroundJavaScript(2000);
        RunRequest decided = RunRequestService.get().load(request.getId());
        assertEquals(RequestStatus.REJECTED, decided.getStatus(),
                "confirming the dialog must reject the request");
        assertEquals("wrong day", decided.getDecisionComment(), "the typed comment is kept");
        assertEquals("a1", decided.getDecidedBy(), "the designated approver decides");
    }

    /**
     * T-UI-292 (#93): Approve still posts with a single click — it must never ask for
     * confirmation. The stub throws if it is called, so any confirmation on Approve fails loudly.
     */
    @Test
    void t_ui_292_approveIsStillSingleClick() throws Exception {
        RunRequest request = request("order check");
        HtmlPage page = page("a1", request);
        page.executeJavaScript("if (!window.dialog) { window.dialog = {}; }"
                + "window.dialog.confirm = function () {"
                + "  throw new Error('Approve must not ask for confirmation');"
                + "};");
        typeComment(page, "looks good");
        HtmlElement approve = button(page, "Approve");
        assertNotNull(approve, "the Decision section must offer Approve");
        approve.click();
        page.getWebClient().waitForBackgroundJavaScript(2000);
        RunRequest decided = RunRequestService.get().load(request.getId());
        assertEquals(RequestStatus.APPROVED, decided.getStatus(),
                "Approve must still post with a single click (no confirmation)");
        assertEquals("looks good", decided.getDecisionComment(), "the typed comment is kept");
    }

    /**
     * T-UI-293 (#93): pressing Reject with a blank comment skips the confirmation — the server
     * refuses the rejection anyway, so the dialog would only add a click. The form submits
     * directly (the click returns a new page), the server's error shows, and the request stays
     * PENDING.
     */
    @Test
    void t_ui_293_blankCommentSkipsTheDialog() throws Exception {
        RunRequest request = request("order check");
        HtmlPage page = page("a1", request);
        page.executeJavaScript("window.__bcDialogOpened = false;"
                + "if (!window.dialog) { window.dialog = {}; }"
                + "window.dialog.confirm = function () {"
                + "  window.__bcDialogOpened = true;"
                + "  return Promise.resolve();"
                + "};");
        typeComment(page, "   ");
        HtmlElement reject = button(page, "Reject");
        assertNotNull(reject, "the Decision section must offer Reject");
        Page clicked = reject.click();
        assertTrue(clicked != page,
                "with a blank comment Reject must submit directly without opening the confirmation");
        page.getWebClient().waitForBackgroundJavaScript(2000);
        assertEquals(RequestStatus.PENDING, RunRequestService.get().load(request.getId()).getStatus(),
                "the server refuses the blank-comment rejection; the request stays PENDING");
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

    private void typeComment(HtmlPage page, String comment) {
        HtmlElement box = theCommentBox(page);
        assertNotNull(box, "the Decision section must offer the comment box");
        if (box instanceof HtmlTextArea t) {
            t.setText(comment);
        } else {
            ((HtmlInput) box).setValue(comment);
        }
    }

    /**
     * Records {@code window.dialog.confirm} calls and resolves (confirm) or rejects (Cancel /
     * Escape) them.
     */
    private void stubDialog(HtmlPage page, boolean confirm) {
        page.executeJavaScript("window.__bcDialogCalls = [];"
                + "if (!window.dialog) { window.dialog = {}; }"
                + "window.dialog.confirm = function (title, opts) {"
                + "  window.__bcDialogCalls.push({"
                + "    title: String(title),"
                + "    message: opts && opts.message ? String(opts.message) : '',"
                + "    okText: opts && opts.okText ? String(opts.okText) : ''"
                + "  });"
                + "  return " + (confirm ? "Promise.resolve()" : "Promise.reject(new Error('dismissed'))") + ";"
                + "};");
    }

    private int dialogCalls(HtmlPage page) {
        Object result = page.executeJavaScript(
                "window.__bcDialogCalls ? window.__bcDialogCalls.length : -1").getJavaScriptResult();
        assertTrue(result instanceof Number, "the dialog stub must have recorded calls");
        return ((Number) result).intValue();
    }

    private String dialogTitle(HtmlPage page) {
        Object result = page.executeJavaScript(
                "window.__bcDialogCalls && window.__bcDialogCalls.length"
                        + " ? window.__bcDialogCalls[0].title : null").getJavaScriptResult();
        return result == null ? null : String.valueOf(result);
    }

    private String dialogMessage(HtmlPage page) {
        Object result = page.executeJavaScript(
                "window.__bcDialogCalls && window.__bcDialogCalls.length"
                        + " ? window.__bcDialogCalls[0].message : null").getJavaScriptResult();
        return result == null ? null : String.valueOf(result);
    }
}
