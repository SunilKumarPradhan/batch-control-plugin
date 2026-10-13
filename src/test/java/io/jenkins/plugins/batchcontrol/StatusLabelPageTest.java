package io.jenkins.plugins.batchcontrol;

import hudson.model.FreeStyleProject;
import hudson.model.Item;
import hudson.model.Result;
import hudson.model.User;
import hudson.security.ACL;
import hudson.security.ACLContext;
import hudson.triggers.TimerTrigger;
import io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration;
import io.jenkins.plugins.batchcontrol.config.BatchControlJobProperty;
import io.jenkins.plugins.batchcontrol.model.GrantAction;
import io.jenkins.plugins.batchcontrol.model.GrantRequest;
import io.jenkins.plugins.batchcontrol.model.GrantScope;
import io.jenkins.plugins.batchcontrol.model.Incident;
import io.jenkins.plugins.batchcontrol.model.IncidentStatus;
import io.jenkins.plugins.batchcontrol.model.RequestStatus;
import io.jenkins.plugins.batchcontrol.model.RunRequest;
import io.jenkins.plugins.batchcontrol.ops.IncidentService;
import io.jenkins.plugins.batchcontrol.policy.GrantRequestService;
import io.jenkins.plugins.batchcontrol.policy.RunRequestService;
import io.jenkins.plugins.batchcontrol.security.BatchControlPermissions;
import io.jenkins.plugins.batchcontrol.store.BatchClock;
import java.net.URL;
import java.time.YearMonth;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.regex.Pattern;
import jenkins.model.Jenkins;
import org.htmlunit.HttpMethod;
import org.htmlunit.Page;
import org.htmlunit.WebRequest;
import org.htmlunit.html.DomElement;
import org.htmlunit.html.DomNode;
import org.htmlunit.html.HtmlPage;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.jvnet.hudson.test.FailureBuilder;
import org.jvnet.hudson.test.JenkinsRule;
import org.jvnet.hudson.test.MockAuthorizationStrategy;
import org.jvnet.hudson.test.junit.jupiter.WithJenkins;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Wave D, group D2, issue #18 item 2 (matrix rows T-UI-255..258, note 361): the screens show
 * readable labels instead of raw enum names for run, grant and activation request statuses,
 * incident statuses and run causes, on the requests, request, grant, activation, incident,
 * history and dashboard pages. Every element that shows such a label carries the enum name in
 * {@code data-batch-control-status}; CSV exports, filters and the JSON summary keep the enum
 * names.
 *
 * <p>"Shows a label" is measured as: at least one element with
 * {@code data-batch-control-status="<ENUM>"} on the page, each such element's visible text is
 * non-blank and does not contain the raw name, it contains the contract's example label where the
 * contract gives one (PENDING "Pending", APPROVED on a run request "Approved, waiting to run",
 * EXECUTED "Executed", APPROVED_REQUEST "Approved request", TIMER "Timer"), and the raw name is
 * not visible as a word in any table of the page. Every row first checks the unchanged enum
 * names in the CSV export and the filter (guards).
 *
 * <p>Written from the Wave D contract (D2, frozen 2026-10-10), issue #18 and pages rendered on
 * origin/main (d80e5fe); no src/main knowledge.
 */
@WithJenkins
public class StatusLabelPageTest {

    private JenkinsRule j;
    private BatchControlGlobalConfiguration cfg;

    @BeforeEach
    public void setUp(JenkinsRule rule) throws Exception {
        this.j = rule;
        j.jenkins.setSecurityRealm(j.createDummySecurityRealm());
        j.jenkins.setAuthorizationStrategy(new MockAuthorizationStrategy()
                .grant(Jenkins.ADMINISTER).everywhere().to("admin")
                .grant(Jenkins.READ, Item.READ, Item.BUILD, BatchControlPermissions.REQUEST,
                        BatchControlPermissions.REQUEST_GRANT).everywhere().to("u1")
                .grant(Jenkins.READ, Item.READ, BatchControlPermissions.APPROVE).everywhere().to("a1"));
        cfg = BatchControlGlobalConfiguration.get();
        cfg.setChangeControlEnabled(true); // recording on; run control off for the fixture builds
        cfg.setApprovers(Arrays.asList("a1"));
        cfg.save();
    }

    /**
     * T-UI-255 (#18.2): run request statuses. The request pages show PENDING as "Pending", APPROVED
     * (not yet run) as "Approved, waiting to run", EXECUTED as "Executed" and REJECTED as a readable
     * label; the requests list (ended rows) and History > Requests show the same, each element
     * carrying the enum. Guards: requests.csv and the status filter use the enum names.
     */
    @Test
    public void t_ui_255_runRequestStatusesAreReadableLabels() throws Exception {
        cfg.setRunControlEnabled(true);
        cfg.save();
        FreeStyleProject job = j.createFreeStyleProject("batch-x");
        BatchControlFixtures.setBatchControl(job, new BatchControlJobProperty(true));
        RunRequest executed = request(job, "executed one");
        as("a1", () -> { RunRequestService.get().approve(executed.getId(), "ok"); return null; });
        j.waitUntilNoActivity();
        assertEquals(RequestStatus.EXECUTED, RunRequestService.get().load(executed.getId()).getStatus(), "fixture: executed");
        RunRequest rejected = request(job, "rejected one");
        as("a1", () -> { RunRequestService.get().reject(rejected.getId(), "not today"); return null; });
        RunRequest pending = request(job, "pending one");
        j.jenkins.setNumExecutors(0); // the next approved run waits in the queue
        RunRequest approved = request(job, "approved one");
        as("a1", () -> { RunRequestService.get().approve(approved.getId(), "ok"); return null; });
        assertEquals(RequestStatus.APPROVED, RunRequestService.get().load(approved.getId()).getStatus(),
                "fixture: approved and waiting in the queue");

        String csv = get("batch-control/history/requests.csv").getWebResponse().getContentAsString();
        for (String s : List.of("PENDING", "APPROVED", "EXECUTED", "REJECTED")) {
            assertTrue(csv.contains(s), "guard: requests.csv keeps the enum name " + s);
        }
        String filtered = tables(page("batch-control/history/?kind=requests&status=EXECUTED"));
        assertTrue(filtered.contains(executed.getId()) || filtered.contains(executed.getId().substring(0, 8)),
                "guard: the status filter still takes the enum name: " + filtered);
        assertFalse(filtered.contains(pending.getId().substring(0, 8)), "guard: the filter keeps PENDING out: " + filtered);

        assertLabelled(page(path(pending)), "PENDING", "Pending", "the PENDING request page");
        assertLabelled(page(path(approved)), "APPROVED", "Approved, waiting to run", "the APPROVED request page");
        assertLabelled(page(path(executed)), "EXECUTED", "Executed", "the EXECUTED request page");
        assertLabelled(page(path(rejected)), "REJECTED", null, "the REJECTED request page");

        HtmlPage list = page("batch-control/requests/");
        assertLabelled(list, "EXECUTED", "Executed", "the requests list");
        assertLabelled(list, "REJECTED", null, "the requests list");

        HtmlPage history = page("batch-control/history/?kind=requests");
        assertLabelled(history, "PENDING", "Pending", "History > Requests");
        assertLabelled(history, "APPROVED", null, "History > Requests");
        assertLabelled(history, "EXECUTED", "Executed", "History > Requests");
        assertLabelled(history, "REJECTED", null, "History > Requests");
    }

    /**
     * T-UI-256 (#18.2): grant and activation request statuses. The pending grant request page and
     * the pending activation request page show "Pending"; the rejected ones show a readable label
     * in the grants and activations lists. Each element carries the enum.
     */
    @Test
    public void t_ui_256_grantAndActivationStatusesAreReadableLabels() throws Exception {
        j.createFreeStyleProject("batch-x");
        cfg.setRunControlEnabled(true);
        cfg.save();
        GrantRequest pendingGrant = as("u1", () -> GrantRequestService.get().create(
                new GrantScope(GrantScope.Type.ITEM, "batch-x"), List.of(GrantAction.CONFIGURE), 30, "fix it", "a1"));
        String rejectedGrant = ApproverFormFixtures.submitGrantOk(j, "u1", "batch-x", List.of("DELETE"), 30,
                "remove it", null, "a1");
        ApproverFormFixtures.assertSuccess(ApproverFormFixtures.decideGrant(j, "a1", rejectedGrant, "reject", "no"),
                "fixture: a1 rejects the grant request");
        FreeStyleProject act = j.createFreeStyleProject("act-x"); // created under run control: not activated
        FreeStyleProject act2 = j.createFreeStyleProject("act2-x");
        String pendingActivation = ActivationFixtures.submitActivationOk(j, "u1", act, "ACTIVATE", "go live", "a1");
        String rejectedActivation = ActivationFixtures.submitActivationOk(j, "u1", act2, "ACTIVATE", "go live", "a1");
        ApproverFormFixtures.assertSuccess(ActivationFixtures.decideActivation(j, "a1", rejectedActivation, "reject", "no"),
                "fixture: a1 rejects the activation request");

        assertLabelled(page("batch-control/grants/" + pendingGrant.getId() + "/"), "PENDING", "Pending",
                "the pending grant request page");
        assertLabelled(page("batch-control/grants/"), "REJECTED", null, "the grants list");
        assertLabelled(page("batch-control/activations/" + pendingActivation + "/"), "PENDING", "Pending",
                "the pending activation request page");
        assertLabelled(page("batch-control/activations/"), "REJECTED", null, "the activations list");
    }

    /**
     * T-UI-257 (#18.2): incident statuses. The incident page, the incidents list and History >
     * Incidents show OPEN and ACKNOWLEDGED as readable labels, each element carrying the enum.
     * Guards: incidents.csv and the status filter use the enum names.
     */
    @Test
    public void t_ui_257_incidentStatusesAreReadableLabels() throws Exception {
        Incident open = failingRun("fail-x");
        Incident acknowledged = failingRun("fail2-x");
        as("admin", () -> {
            IncidentService.get().acknowledge(acknowledged.getId(), "looking");
            return null;
        });
        assertEquals(IncidentStatus.ACKNOWLEDGED, IncidentService.get().load(acknowledged.getId()).getStatus(), "fixture");

        String csv = get("batch-control/history/incidents.csv").getWebResponse().getContentAsString();
        assertTrue(csv.contains("OPEN") && csv.contains("ACKNOWLEDGED"), "guard: incidents.csv keeps the enum names");
        String filtered = tables(page("batch-control/history/?kind=incidents&status=ACKNOWLEDGED"));
        assertTrue(filtered.contains("fail2-x") && !filtered.contains("fail-x#") && !filtered.matches("(?s).*\\bfail-x\\b.*"),
                "guard: the status filter still takes the enum name: " + filtered);

        assertLabelled(page("batch-control/incidents/" + open.getId() + "/"), "OPEN", null, "the incident page");
        HtmlPage list = page("batch-control/incidents/");
        assertLabelled(list, "OPEN", null, "the incidents list");
        assertLabelled(list, "ACKNOWLEDGED", null, "the incidents list");
        HtmlPage history = page("batch-control/history/?kind=incidents");
        assertLabelled(history, "OPEN", null, "History > Incidents");
        assertLabelled(history, "ACKNOWLEDGED", null, "History > Incidents");
    }

    /**
     * T-UI-258 (#18.2): run causes. The run dashboard and History > Runs show APPROVED_REQUEST as
     * "Approved request" and TIMER as "Timer", each element carrying the enum. Guards: runs.csv keeps
     * the enum names and the monthly JSON summary carries none of the screen labels.
     */
    @Test
    public void t_ui_258_runCausesAreReadableLabels() throws Exception {
        FreeStyleProject timer = j.createFreeStyleProject("timer-x");
        j.assertBuildStatusSuccess(timer.scheduleBuild2(0, new TimerTrigger.TimerTriggerCause()));
        cfg.setRunControlEnabled(true);
        cfg.save();
        FreeStyleProject job = j.createFreeStyleProject("batch-x");
        BatchControlFixtures.setBatchControl(job, new BatchControlJobProperty(true));
        RunRequest request = request(job, "approved run");
        as("a1", () -> { RunRequestService.get().approve(request.getId(), "ok"); return null; });
        j.waitUntilNoActivity();
        assertEquals(1, job.getBuilds().size(), "fixture: the approved run executed");

        String csv = get("batch-control/history/runs.csv").getWebResponse().getContentAsString();
        assertTrue(csv.contains("APPROVED_REQUEST") && csv.contains("TIMER"), "guard: runs.csv keeps the cause names: " + csv);
        String month = YearMonth.now(BatchClock.clock()).toString();
        Page summary = get("batch-control/history/summary?month=" + month);
        assertEquals(200, summary.getWebResponse().getStatusCode(), "guard: the JSON summary answers");
        String json = summary.getWebResponse().getContentAsString();
        for (String label : List.of("Approved request", "Approved, waiting to run", "Timer", "Pending", "Executed")) {
            assertFalse(json.contains(label), "guard: the JSON summary must not carry the screen label " + label);
        }

        for (String path : List.of("batch-control/dashboard/", "batch-control/history/?kind=runs")) {
            HtmlPage page = page(path);
            assertLabelled(page, "APPROVED_REQUEST", "Approved request", path);
            assertLabelled(page, "TIMER", "Timer", path);
        }
    }

    // ------------------------------------------------------------------ helpers

    /**
     * The page shows {@code enumName} as a readable label in at least one element carrying
     * {@code data-batch-control-status="<enumName>"}, and nowhere as a raw word in a table.
     */
    static void assertLabelled(HtmlPage page, String enumName, String expected, String where) {
        List<DomNode> hooked = page.querySelectorAll("[data-batch-control-status='" + enumName + "']");
        assertFalse(hooked.isEmpty(), where + ": the status " + enumName + " must be shown in an element carrying"
                + " data-batch-control-status=\"" + enumName + "\"; tables read: " + excerpt(tables(page)));
        for (DomNode n : hooked) {
            String text = n.asNormalizedText().trim();
            assertFalse(text.isEmpty(), where + ": the element for " + enumName + " must show a label: " + ((DomElement) n).asXml());
            assertFalse(text.contains(enumName), where + ": " + enumName + " must be shown as a readable label, not"
                    + " the raw name: '" + text + "'");
            if (expected != null) {
                assertTrue(text.contains(expected), where + ": " + enumName + " must read '" + expected + "', was '" + text + "'");
            }
        }
        Pattern raw = Pattern.compile("(?<![A-Za-z_])" + enumName + "(?![A-Za-z_])");
        assertFalse(raw.matcher(tables(page)).find(), where + ": no table may show the raw name " + enumName + ": "
                + excerpt(tables(page)));
    }

    /** The visible text of every table in the main panel. */
    static String tables(HtmlPage page) {
        StringBuilder out = new StringBuilder();
        for (DomNode n : page.querySelectorAll("#main-panel table")) {
            out.append(n.asNormalizedText()).append('\n');
        }
        return out.toString();
    }

    private Incident failingRun(String name) throws Exception {
        FreeStyleProject job = j.createFreeStyleProject(name);
        job.getBuildersList().add(new FailureBuilder());
        j.buildAndAssertStatus(Result.FAILURE, job);
        Incident incident = IncidentService.get().list(YearMonth.now(BatchClock.clock())).stream()
                .filter(i -> (name + "#1").equals(i.getRunId())).findFirst().orElse(null);
        assertNotNull(incident, "fixture: the failed run of " + name + " opens an incident");
        return incident;
    }

    private RunRequest request(FreeStyleProject job, String reason) throws Exception {
        return as("u1", () -> RunRequestService.get().create(job, new LinkedHashMap<>(), reason, "a1"));
    }

    private static String path(RunRequest request) {
        return "batch-control/requests/" + request.getId() + "/";
    }

    private HtmlPage page(String path) throws Exception {
        Page answer = get(path);
        assertEquals(200, answer.getWebResponse().getStatusCode(), "admin GET " + path);
        return (HtmlPage) answer;
    }

    private Page get(String path) throws Exception {
        JenkinsRule.WebClient wc = j.createWebClient().withThrowExceptionOnFailingStatusCode(false).login("admin");
        wc.getOptions().setJavaScriptEnabled(false);
        return wc.getPage(new WebRequest(new URL(j.getURL(), path), HttpMethod.GET));
    }

    private static <V> V as(String user, Callable<V> body) throws Exception {
        try (ACLContext ignored = ACL.as2(User.getById(user, true).impersonate2())) {
            return body.call();
        }
    }

    private static String excerpt(String text) {
        return text.length() > 1500 ? text.substring(0, 1500) + "..." : text;
    }
}
