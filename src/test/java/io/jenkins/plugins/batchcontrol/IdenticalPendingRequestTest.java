package io.jenkins.plugins.batchcontrol;

import hudson.model.FreeStyleProject;
import hudson.model.Item;
import hudson.model.ParametersDefinitionProperty;
import hudson.model.StringParameterDefinition;
import io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration;
import io.jenkins.plugins.batchcontrol.config.BatchControlJobProperty;
import io.jenkins.plugins.batchcontrol.model.RequestStatus;
import io.jenkins.plugins.batchcontrol.ops.BatchControlNotifier;
import io.jenkins.plugins.batchcontrol.ops.Notification;
import io.jenkins.plugins.batchcontrol.ops.NotificationEvent;
import io.jenkins.plugins.batchcontrol.policy.RunRequestService;
import io.jenkins.plugins.batchcontrol.security.BatchControlPermissions;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import jenkins.model.Jenkins;
import net.sf.json.JSONArray;
import net.sf.json.JSONObject;
import org.htmlunit.FormEncodingType;
import org.htmlunit.HttpMethod;
import org.htmlunit.Page;
import org.htmlunit.WebRequest;
import org.htmlunit.WebResponse;
import org.htmlunit.util.NameValuePair;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.jvnet.hudson.test.JenkinsRule;
import org.jvnet.hudson.test.MockAuthorizationStrategy;
import org.jvnet.hudson.test.TestExtension;
import org.jvnet.hudson.test.junit.jupiter.WithJenkins;

import static io.jenkins.plugins.batchcontrol.ApproverFormFixtures.approverPairs;
import static io.jenkins.plugins.batchcontrol.ApproverFormFixtures.assertSuccess;
import static io.jenkins.plugins.batchcontrol.ApproverFormFixtures.excerpt;
import static io.jenkins.plugins.batchcontrol.ApproverFormFixtures.runRequestIds;
import static io.jenkins.plugins.batchcontrol.BatchControlFixtures.setBatchControl;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #1 (e2e-05 UX-3, owner decision D-88 of 2026-10-10): an identical pending run request is not created twice.
 * Matrix rows T-05-204 .. T-05-206 (note 359).
 *
 * <p>Basis: the #1 contract (frozen 2026-10-10), item 9, D-88: "When the same user submits a run request for
 * the same job with the same parameters, reason and approvers while an identical request of theirs is still
 * PENDING, no new request is created. The user is sent to the existing request's page with a notice: 'An
 * identical request of yours is already pending'. No second notification goes to the approvers. A script
 * (D-84 rules) gets a 4xx or 409 naming the existing request id. A request that differs in anything
 * (parameters, reason, approvers), or one whose earlier twin is no longer PENDING, is created normally."
 * SPEC 4 (run request), SPEC 13 (the designated approvers are notified of a new request); DECISIONS D-84 (a
 * request is a script when its Accept header does not include {@code text/html} and either there is no Accept
 * header, Accept does not include {@code *}{@code /*}, or an {@code Authorization} header is present); SPEC 7 (the
 * requester may cancel a PENDING request).
 *
 * <p>Run control on; u1 holds Overall/Read, Item/Read, Job/Build and BatchControl/Request; a1 and a2 (on the
 * approver list) hold Approve. The approval-required job {@code batch-p} has a string parameter {@code DATE}.
 * Submissions are shaped as the Request Run form posts them in a browser (multipart, core's name/value parts
 * and the structured {@code json} field, as {@code ApproverFormFixtures#submitRunMultipart}). A browser sends
 * {@code Accept: text/html,...}; a script sends {@code Accept: application/json}. Notifications are captured by
 * a test notifier ({@link NotificationCapture}).
 *
 * <p>Written from docs/SPEC.md, docs/DECISIONS.md D-84, docs/reports/e2e-05.md and the #1 contract only (no
 * src/main knowledge).
 */
@WithJenkins
public class IdenticalPendingRequestTest {

    private static final String BROWSER_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8";
    private static final String SCRIPT_ACCEPT = "application/json";
    private static final String REASON = "month-end close for October";
    private static final String DATE = "2026-10-31";

    private JenkinsRule j;
    private FreeStyleProject job;

    /** Records every event. */
    @TestExtension
    public static class CapturingNotifier extends BatchControlNotifier {
        @Override
        public void notify(NotificationEvent event, Notification notification) {
            NotificationCapture.record(event, notification);
        }
    }

    @BeforeEach
    public void setUp(JenkinsRule rule) throws Exception {
        this.j = rule;
        NotificationCapture.clear();
        j.jenkins.setSecurityRealm(j.createDummySecurityRealm());
        j.jenkins.setAuthorizationStrategy(new MockAuthorizationStrategy()
                .grant(Jenkins.ADMINISTER).everywhere().to("admin")
                .grant(Jenkins.READ, Item.READ, Item.BUILD, BatchControlPermissions.REQUEST).everywhere().to("u1")
                .grant(Jenkins.READ, Item.READ, BatchControlPermissions.APPROVE).everywhere().to("a1", "a2"));
        BatchControlGlobalConfiguration cfg = BatchControlGlobalConfiguration.get();
        cfg.setRunControlEnabled(true);
        cfg.setApprovers(Arrays.asList("a1", "a2"));
        cfg.save();
        job = j.createFreeStyleProject("batch-p");
        job.addProperty(new ParametersDefinitionProperty(new StringParameterDefinition("DATE", "2000-01-01")));
        setBatchControl(job, new BatchControlJobProperty(true));
    }

    @AfterEach
    public void tearDown() {
        NotificationCapture.clear();
    }

    /**
     * T-05-204 (#1.9, D-88, browser): u1's run request (DATE, reason, a1) is created and notified once. The
     * same submission again from a browser creates no request: the answer redirects (3xx) to the existing
     * request's page, which then shows the notice "An identical request of yours is already pending", and no
     * second REQUEST_CREATED notification is sent. On main a second PENDING request is created and notified.
     * Guard: the first submission creates exactly one request, PENDING, notified to a1.
     */
    @Test
    public void t_05_204_identicalBrowserSubmissionGoesToTheExistingRequest() throws Exception {
        JenkinsRule.WebClient wc = ApproverFormFixtures.client(j, "u1");
        String id = submitOk(wc, BROWSER_ACCEPT, REASON, DATE, "a1");
        assertEquals(1, NotificationCapture.await(NotificationEvent.REQUEST_CREATED, id).size(), "guard: the first request is notified once");

        Set<String> before = runRequestIds();
        WebResponse again = submit(wc, BROWSER_ACCEPT, REASON, DATE, "a1");
        assertEquals(before, runRequestIds(), "#1.9: an identical submission while u1's request " + id + " is PENDING must not create"
                + " a second request");
        int code = again.getStatusCode();
        String location = again.getResponseHeaderValue("Location");
        assertTrue(code >= 300 && code < 400 && location != null && location.contains("batch-control/requests/" + id),
                "#1.9: the browser is sent to the existing request's page, got " + code + " Location " + location + ": "
                + excerpt(again.getContentAsString()));
        Page landing = wc.getPage(new WebRequest(new URL(j.getURL(), location), HttpMethod.GET));
        assertEquals(200, landing.getWebResponse().getStatusCode(), "the existing request's page opens");
        String text = UsabilityFixtures.text(landing).toLowerCase(Locale.ROOT);
        assertTrue(text.contains("an identical request of yours is already pending"), "#1.9: the page shows the notice: "
                + excerpt(UsabilityFixtures.text(landing)));
        assertEquals(1, createdNotices().size(), "#1.9: no second notification goes to the approvers: " + NotificationCapture.describeAll());
    }

    /**
     * T-05-205 (#1.9, D-88, D-84 script): after u1's browser request, the same submission from a script
     * ({@code Accept: application/json}) gets a 4xx (409 allowed) whose body names the existing request id, no
     * request is created and no second notification is sent. On main the script's submission creates a second
     * PENDING request. Guard: the first request is notified once.
     */
    @Test
    public void t_05_205_identicalScriptSubmissionIsRefusedNamingTheExistingRequest() throws Exception {
        JenkinsRule.WebClient wc = ApproverFormFixtures.client(j, "u1");
        String id = submitOk(wc, BROWSER_ACCEPT, REASON, DATE, "a1");
        NotificationCapture.await(NotificationEvent.REQUEST_CREATED, id);

        Set<String> before = runRequestIds();
        WebResponse again = submit(wc, SCRIPT_ACCEPT, REASON, DATE, "a1");
        assertEquals(before, runRequestIds(), "#1.9: the script's identical submission must not create a second request");
        int code = again.getStatusCode();
        assertTrue(code >= 400 && code < 500, "#1.9: a script gets a 4xx (or 409), got " + code + ": " + excerpt(again.getContentAsString()));
        assertTrue(again.getContentAsString().contains(id), "#1.9: the answer names the existing request " + id + ": "
                + excerpt(again.getContentAsString()));
        assertEquals(1, createdNotices().size(), "#1.9: no second notification: " + NotificationCapture.describeAll());
    }

    /**
     * T-05-206 (#1.9, D-88 guard): while u1's request (DATE, reason, a1) is PENDING, a submission with another
     * reason, one with another DATE and one designating a2 instead are each created as a new PENDING request
     * and notified. After u1 cancels the first request, the identical submission is created as a new request
     * too. Green on main; it pins what the de-duplication must not swallow.
     */
    @Test
    public void t_05_206_requestsThatDifferOrWhoseTwinIsClosedAreCreated() throws Exception {
        JenkinsRule.WebClient wc = ApproverFormFixtures.client(j, "u1");
        String first = submitOk(wc, BROWSER_ACCEPT, REASON, DATE, "a1");
        String otherReason = submitOk(wc, BROWSER_ACCEPT, REASON + " (second batch)", DATE, "a1");
        String otherDate = submitOk(wc, BROWSER_ACCEPT, REASON, "2026-11-30", "a1");
        String otherApprover = submitOk(wc, BROWSER_ACCEPT, REASON, DATE, "a2");
        for (String id : new String[] {first, otherReason, otherDate, otherApprover}) {
            assertEquals(RequestStatus.PENDING, RunRequestService.get().load(id).getStatus(), "request " + id + " is PENDING");
            NotificationCapture.await(NotificationEvent.REQUEST_CREATED, id);
        }

        assertSuccess(ApproverFormFixtures.post(j, "u1", "batch-control/requests/" + first + "/cancel", List.of()),
                "fixture: u1 cancels the first request");
        assertEquals(RequestStatus.CANCELLED, RunRequestService.get().load(first).getStatus(), "premise: the first request is CANCELLED");
        String again = submitOk(wc, BROWSER_ACCEPT, REASON, DATE, "a1");
        NotificationCapture.await(NotificationEvent.REQUEST_CREATED, again);
    }

    // ---------------------------------------------------------------- helpers

    private List<NotificationCapture> createdNotices() throws InterruptedException {
        Thread.sleep(NotificationCapture.QUIET_PERIOD_MS); // bounded wait for a delivery that must NOT happen
        return NotificationCapture.matching(c -> c.event == NotificationEvent.REQUEST_CREATED);
    }

    /** {@link #submit} that must create exactly one request; returns its id. */
    private String submitOk(JenkinsRule.WebClient wc, String accept, String reason, String date, String... approvers) throws Exception {
        Set<String> before = runRequestIds();
        WebResponse answer = submit(wc, accept, reason, date, approvers);
        assertSuccess(answer, "fixture: the run request submission");
        Set<String> after = runRequestIds();
        after.removeAll(before);
        assertEquals(1, after.size(), "exactly one run request must be created by this submission, got " + after);
        String id = after.iterator().next();
        assertNotNull(RunRequestService.get().load(id), "the request loads");
        return id;
    }

    /** The Request Run form's multipart POST, as u1, with the given Accept header; redirects are not followed. */
    private WebResponse submit(JenkinsRule.WebClient wc, String accept, String reason, String date, String... approvers) throws Exception {
        List<NameValuePair> params = new ArrayList<>();
        params.add(new NameValuePair("reason", reason));
        params.addAll(approverPairs(approvers));
        params.add(new NameValuePair("name", "DATE"));
        params.add(new NameValuePair("value", date));
        JSONObject json = new JSONObject();
        json.put("reason", reason);
        json.put("approvers", JSONArray.fromObject(approvers));
        JSONArray parameters = new JSONArray();
        parameters.add(new JSONObject().element("name", "DATE").element("value", date));
        json.put("parameter", parameters);
        params.add(new NameValuePair("json", json.toString()));
        WebRequest request = new WebRequest(wc.createCrumbedUrl(job.getUrl() + "batch-control/submit"), HttpMethod.POST);
        request.setEncodingType(FormEncodingType.MULTIPART);
        request.setCharset(StandardCharsets.UTF_8);
        request.setRequestParameters(params);
        request.setAdditionalHeader("Accept", accept);
        return wc.getPage(request).getWebResponse();
    }
}
