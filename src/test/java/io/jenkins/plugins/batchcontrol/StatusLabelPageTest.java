package io.jenkins.plugins.batchcontrol;

import hudson.ExtensionList;
import hudson.model.FreeStyleProject;
import hudson.model.Item;
import hudson.model.Result;
import hudson.model.User;
import hudson.security.ACL;
import hudson.security.ACLContext;
import hudson.triggers.TimerTrigger;
import io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration;
import io.jenkins.plugins.batchcontrol.config.BatchControlJobProperty;
import io.jenkins.plugins.batchcontrol.model.CauseType;
import io.jenkins.plugins.batchcontrol.model.GrantAction;
import io.jenkins.plugins.batchcontrol.model.GrantRequest;
import io.jenkins.plugins.batchcontrol.model.GrantScope;
import io.jenkins.plugins.batchcontrol.model.Incident;
import io.jenkins.plugins.batchcontrol.model.IncidentStatus;
import io.jenkins.plugins.batchcontrol.model.RequestStatus;
import io.jenkins.plugins.batchcontrol.model.RunRequest;
import io.jenkins.plugins.batchcontrol.ops.ExpiryPeriodicWork;
import io.jenkins.plugins.batchcontrol.ops.IncidentService;
import io.jenkins.plugins.batchcontrol.policy.ActivationService;
import io.jenkins.plugins.batchcontrol.policy.GrantRequestService;
import io.jenkins.plugins.batchcontrol.policy.RunRequestService;
import io.jenkins.plugins.batchcontrol.security.BatchControlPermissions;
import io.jenkins.plugins.batchcontrol.store.BatchClock;
import java.net.URL;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.YearMonth;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.concurrent.Callable;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import jenkins.model.Jenkins;
import net.sf.json.JSONObject;
import org.htmlunit.HttpMethod;
import org.htmlunit.Page;
import org.htmlunit.WebRequest;
import org.htmlunit.html.DomElement;
import org.htmlunit.html.DomNode;
import org.htmlunit.html.HtmlPage;
import org.junit.jupiter.api.AfterEach;
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
import static org.junit.jupiter.api.Assertions.fail;

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
 *
 * <p><b>Colour badges</b> (matrix rows T-UI-260..267, note 361 point 7; contract "D2 colour
 * badges", #18.2, 2026-10-14). Every element that shows a request status or an incident status is
 * a badge: it keeps {@code data-batch-control-status} and its label text, has the class
 * {@code batch-control-status} and carries its tone in {@code data-batch-control-tone}
 * ({@code warning}, {@code info}, {@code success}, {@code danger} or {@code neutral}, by the enum
 * constant only). A run cause stays plain text. The badge has no {@code style} attribute: the
 * colours come from the plugin's stylesheet, which the page links and which takes them from core's
 * theme variables. CSV exports, filter values and the JSON summary gain no tone. Whether the
 * colours are readable (contrast, light and dark theme) is verified in e2e, not here. Written from
 * that contract and from pages rendered on this branch (8f4d38c8); no src/main knowledge.
 */
@WithJenkins
public class StatusLabelPageTest {

    /** The class every status badge has (contract point 2). */
    private static final String BADGE_CLASS = "batch-control-status";
    /** The attribute a badge carries its tone in (contract point 2). */
    private static final String TONE = "data-batch-control-tone";
    /** The five tones, each with the words core's theme variable for it is named by (point 4). */
    private static final Map<String, Pattern> TONES = tones();
    /** The contract's tone of every request and incident status, by enum name (point 2). */
    private static final Map<String, String> TONE_OF = toneOf();
    /** A hard-coded colour in a stylesheet rule. */
    private static final Pattern COLOUR_LITERAL = Pattern.compile("#[0-9a-fA-F]{3,8}\\b|\\b(?:rgba?|hsla?)\\(");
    /** A tone used as a word in data (lower case, as the attribute holds it). */
    private static final Pattern TONE_WORD =
            Pattern.compile("(?<![A-Za-z])(?:warning|info|success|danger|neutral)(?![A-Za-z])");

    private JenkinsRule j;
    private BatchControlGlobalConfiguration cfg;
    private JenkinsRule.WebClient adminClient;
    private final Map<String, String> fetched = new HashMap<>();

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

    @AfterEach
    public void resetClock() {
        BatchClock.reset();
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

    /**
     * T-UI-260 (#18.2, colour badges): run request statuses are badges. On the request page of a
     * request in each of the seven statuses, in the requests list (ended rows) and in History >
     * Requests, every status element has the class {@code batch-control-status}, the contract's
     * tone (PENDING warning, APPROVED info, EXECUTED success, REJECTED danger, CANCELLED, EXPIRED
     * and INVALIDATED neutral), its unchanged label as its whole text and no {@code style}
     * attribute; each row holds one badge and each list shows one badge per request.
     */
    @Test
    public void t_ui_260_runRequestStatusesAreToneBadges() throws Exception {
        RunRequests r = runRequestsInEveryStatus();
        Map<String, RunRequest> byStatus = new LinkedHashMap<>();
        byStatus.put("PENDING", r.pending());
        byStatus.put("APPROVED", r.approved());
        byStatus.put("EXECUTED", r.executed());
        byStatus.put("REJECTED", r.rejected());
        byStatus.put("CANCELLED", r.cancelled());
        byStatus.put("EXPIRED", r.expired());
        byStatus.put("INVALIDATED", r.invalidated());
        for (Map.Entry<String, RunRequest> e : byStatus.entrySet()) {
            String where = "the " + e.getKey() + " run request page";
            HtmlPage page = page(path(e.getValue()));
            assertBadges(page, where, e.getKey());
            assertOneBadgePerRow(page, where, List.of(e.getKey()));
        }

        List<String> ended = List.of("EXECUTED", "REJECTED", "CANCELLED", "EXPIRED", "INVALIDATED");
        HtmlPage list = page("batch-control/requests/");
        assertBadges(list, "the requests list", ended.toArray(new String[0]));
        assertOneBadgePerRow(list, "the requests list", ended);

        List<String> all = new ArrayList<>(byStatus.keySet());
        HtmlPage history = page("batch-control/history/?kind=requests");
        assertBadges(history, "History > Requests", all.toArray(new String[0]));
        assertOneBadgePerRow(history, "History > Requests", all);
    }

    /**
     * T-UI-261 (#18.2, colour badges): grant and activation request statuses are badges, as
     * T-UI-260: on the grant request pages (PENDING, APPROVED, REJECTED, CANCELLED, EXPIRED), the
     * grants list (ended rows), the activation request pages (the same and INVALIDATED) and the
     * activations list (ended rows). The tone follows the constant, not the wording of the page (the
     * grants list words its ended rows differently).
     */
    @Test
    public void t_ui_261_grantAndActivationStatusesAreToneBadges() throws Exception {
        j.createFreeStyleProject("batch-x");
        j.createFreeStyleProject("win-x");
        cfg.setRunControlEnabled(true);
        cfg.setPendingTimeoutHours(1);
        cfg.save();
        FreeStyleProject lateJob = j.createFreeStyleProject("act5-x"); // created under run control: not activated
        Map<String, String> grants = new LinkedHashMap<>();
        Map<String, String> activations = new LinkedHashMap<>();
        anHourAgo(() -> {
            grants.put("EXPIRED", ApproverFormFixtures.submitGrantOk(j, "u1", "batch-x", List.of("CONFIGURE"), 30,
                    "too late", null, "a1"));
            activations.put("EXPIRED", ActivationFixtures.submitActivationOk(j, "u1", lateJob, "ACTIVATE", "too late", "a1"));
            return null;
        });
        expireOverdue();

        grants.put("PENDING", as("u1", () -> GrantRequestService.get().create(
                new GrantScope(GrantScope.Type.ITEM, "batch-x"), List.of(GrantAction.CONFIGURE), 30, "fix it", "a1")).getId());
        grants.put("REJECTED", ApproverFormFixtures.submitGrantOk(j, "u1", "batch-x", List.of("DELETE"), 30,
                "remove it", null, "a1"));
        ApproverFormFixtures.assertSuccess(ApproverFormFixtures.decideGrant(j, "a1", grants.get("REJECTED"), "reject", "no"),
                "fixture: a1 rejects the grant request");
        grants.put("CANCELLED", ApproverFormFixtures.submitGrantOk(j, "u1", "batch-x", List.of("DELETE"), 30,
                "remove it after all", null, "a1"));
        ApproverFormFixtures.assertSuccess(ApproverFormFixtures.decideGrant(j, "u1", grants.get("CANCELLED"), "cancel", ""),
                "fixture: u1 cancels the grant request");
        grants.put("APPROVED", ApproverFormFixtures.submitGrantOk(j, "u1", "win-x", List.of("CONFIGURE"), 30,
                "tune it", null, "a1"));
        ApproverFormFixtures.assertSuccess(ApproverFormFixtures.decideGrant(j, "a1", grants.get("APPROVED"), "approve", "ok"),
                "fixture: a1 approves the grant request");
        for (Map.Entry<String, String> e : grants.entrySet()) {
            assertEquals(e.getKey(), GrantRequestService.get().load(e.getValue()).getStatus().name(), "fixture: the grant request");
        }

        activations.put("PENDING", activation("act-x"));
        activations.put("REJECTED", activation("act2-x"));
        ApproverFormFixtures.assertSuccess(ActivationFixtures.decideActivation(j, "a1", activations.get("REJECTED"), "reject", "no"),
                "fixture: a1 rejects the activation request");
        activations.put("CANCELLED", activation("act3-x"));
        ApproverFormFixtures.assertSuccess(ActivationFixtures.decideActivation(j, "u1", activations.get("CANCELLED"), "cancel", ""),
                "fixture: u1 cancels the activation request");
        activations.put("APPROVED", activation("act4-x"));
        ApproverFormFixtures.assertSuccess(ActivationFixtures.decideActivation(j, "a1", activations.get("APPROVED"), "approve", "ok"),
                "fixture: a1 approves the activation request");
        activations.put("INVALIDATED", activation("act6-x"));
        as("admin", () -> {
            j.jenkins.getItemByFullName("act6-x").delete();
            return null;
        });
        for (Map.Entry<String, String> e : activations.entrySet()) {
            assertEquals(e.getKey(), ActivationService.get().load(e.getValue()).getStatus().name(), "fixture: the activation request");
        }

        for (Map.Entry<String, String> e : grants.entrySet()) {
            String where = "the " + e.getKey() + " grant request page";
            HtmlPage page = page("batch-control/grants/" + e.getValue() + "/");
            assertBadges(page, where, e.getKey());
            assertOneBadgePerRow(page, where, List.of(e.getKey()));
        }
        List<String> endedGrants = List.of("REJECTED", "CANCELLED", "EXPIRED");
        HtmlPage grantList = page("batch-control/grants/");
        assertBadges(grantList, "the grants list", endedGrants.toArray(new String[0]));
        assertOneBadgePerRow(grantList, "the grants list", endedGrants);

        for (Map.Entry<String, String> e : activations.entrySet()) {
            String where = "the " + e.getKey() + " activation request page";
            HtmlPage page = page("batch-control/activations/" + e.getValue() + "/");
            assertBadges(page, where, e.getKey());
            assertOneBadgePerRow(page, where, List.of(e.getKey()));
        }
        List<String> endedActivations = List.of("REJECTED", "CANCELLED", "EXPIRED", "INVALIDATED");
        HtmlPage activationList = page("batch-control/activations/");
        assertBadges(activationList, "the activations list", endedActivations.toArray(new String[0]));
        assertOneBadgePerRow(activationList, "the activations list", endedActivations);
    }

    /**
     * T-UI-262 (#18.2, colour badges): incident statuses are badges (OPEN danger, ACKNOWLEDGED
     * warning, RESOLVED success), as T-UI-260: on the incident page, whose history rows show one
     * status each (the resolved incident's page shows RESOLVED and the rows OPEN, ACKNOWLEDGED,
     * RESOLVED), in the incidents list and in History > Incidents.
     */
    @Test
    public void t_ui_262_incidentStatusesAreToneBadges() throws Exception {
        Incidents i = incidentsInEveryStatus();

        HtmlPage open = page("batch-control/incidents/" + i.open().getId() + "/");
        assertBadges(open, "the OPEN incident page", "OPEN");
        assertOneBadgePerRow(open, "the OPEN incident page (its status and its history)", List.of("OPEN", "OPEN"));
        HtmlPage acknowledged = page("batch-control/incidents/" + i.acknowledged().getId() + "/");
        assertBadges(acknowledged, "the ACKNOWLEDGED incident page", "OPEN", "ACKNOWLEDGED");
        assertOneBadgePerRow(acknowledged, "the ACKNOWLEDGED incident page (its status and its history)",
                List.of("ACKNOWLEDGED", "OPEN", "ACKNOWLEDGED"));
        HtmlPage resolved = page("batch-control/incidents/" + i.resolved().getId() + "/");
        assertBadges(resolved, "the RESOLVED incident page", "OPEN", "ACKNOWLEDGED", "RESOLVED");
        assertOneBadgePerRow(resolved, "the RESOLVED incident page (its status and its history)",
                List.of("RESOLVED", "OPEN", "ACKNOWLEDGED", "RESOLVED"));

        List<String> all = List.of("OPEN", "ACKNOWLEDGED", "RESOLVED");
        HtmlPage list = page("batch-control/incidents/");
        assertBadges(list, "the incidents list", all.toArray(new String[0]));
        assertOneBadgePerRow(list, "the incidents list", all);
        HtmlPage history = page("batch-control/history/?kind=incidents");
        assertBadges(history, "History > Incidents", all.toArray(new String[0]));
        assertOneBadgePerRow(history, "History > Incidents", all);
    }

    /**
     * T-UI-263 (#18.2, colour badges; guard): a run cause is not a badge. On the run dashboard and
     * History > Runs the cause elements keep their label as plain text and carry neither the class
     * {@code batch-control-status} nor a tone, and nothing else on these screens is a badge.
     */
    @Test
    public void t_ui_263_runCausesStayPlainText() throws Exception {
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

        for (String path : List.of("batch-control/dashboard/", "batch-control/history/?kind=runs")) {
            HtmlPage page = page(path);
            Set<String> causes = new TreeSet<>();
            for (DomNode n : page.querySelectorAll("[data-batch-control-status]")) {
                DomElement e = (DomElement) n;
                String name = e.getAttribute("data-batch-control-status");
                CauseType cause = Arrays.stream(CauseType.values()).filter(c -> c.name().equals(name)).findFirst().orElse(null);
                if (cause == null) {
                    continue; // a request or incident status, judged below
                }
                causes.add(name);
                assertFalse(classes(e).contains(BADGE_CLASS), path + ": the run cause " + name + " is not a badge, it must not"
                        + " have the class \"" + BADGE_CLASS + "\": " + e.asXml().trim());
                assertEquals("", e.getAttribute(TONE), path + ": the run cause " + name + " carries no tone: " + e.asXml().trim());
                assertEquals(label(cause), text(e), path + ": the run cause " + name + " stays its label as plain text");
            }
            assertTrue(causes.containsAll(List.of("APPROVED_REQUEST", "TIMER")), path + ": premise (T-UI-258): the causes"
                    + " APPROVED_REQUEST and TIMER are shown in elements carrying data-batch-control-status, found " + causes);
            assertOnlyStatusesAreBadges(page, path);
        }
    }

    /**
     * T-UI-264 (#18.2, colour badges; guard, a Content-Security-Policy without inline styles): on
     * every screen of the contract, the run dashboard and History > Runs, no element carrying
     * {@code data-batch-control-status} has a {@code style} attribute, nor has anything inside it,
     * and no {@code style} element of the page styles the badge.
     */
    @Test
    public void t_ui_264_statusElementsCarryNoInlineStyle() throws Exception {
        List<Screen> screens = new ArrayList<>(aStatusOnEveryScreen());
        screens.add(new Screen("the run dashboard", "batch-control/dashboard/", List.of()));
        screens.add(new Screen("History > Runs", "batch-control/history/?kind=runs", List.of()));
        for (Screen screen : screens) {
            HtmlPage page = page(screen.path());
            List<DomNode> hooked = page.querySelectorAll("[data-batch-control-status]");
            assertFalse(hooked.isEmpty(), screen.where() + ": premise (T-UI-255..258): a status or a cause is shown in an"
                    + " element carrying data-batch-control-status; tables read: " + excerpt(tables(page)));
            for (DomNode n : hooked) {
                assertNoInlineStyle((DomElement) n, screen.where());
            }
            for (DomNode n : page.querySelectorAll("style")) {
                String css = n.getTextContent();
                assertFalse(css.contains(BADGE_CLASS) || css.contains(TONE), screen.where() + ": the badge must be styled by"
                        + " the plugin's stylesheet, not by a style element in the page: " + excerpt(css));
            }
        }
    }

    /**
     * T-UI-265 (#18.2, colour badges): the styling comes from the plugin's stylesheet and the
     * colours from the Jenkins theme. Every screen of the contract links a stylesheet of the plugin
     * (fetched over HTTP through the page's {@code link}); it has a rule for the class
     * {@code batch-control-status} and, for each of the five tones, a rule that selects
     * {@code [data-batch-control-tone="<tone>"]}, takes its colours from a CSS variable and uses
     * core's theme variable for that tone (warning, accent, success, error or destructive, secondary);
     * neither these rules nor the plugin's own variables they use hold a hard-coded colour.
     */
    @Test
    public void t_ui_265_tonesAreStyledByThePluginStylesheetFromThemeVariables() throws Exception {
        Set<String> problems = new LinkedHashSet<>();
        for (Screen screen : aStatusOnEveryScreen()) {
            HtmlPage page = page(screen.path());
            List<String> plugin = new ArrayList<>();
            List<String> other = new ArrayList<>();
            for (DomNode n : page.querySelectorAll("link[rel='stylesheet']")) {
                String href = ((DomElement) n).getAttribute("href");
                (href.matches(".*batch-?control.*") ? plugin : other).add(href);
            }
            if (plugin.isEmpty()) {
                problems.add(screen.where() + " links no stylesheet of the plugin (it links " + other + ")");
                continue;
            }
            StringBuilder pluginCss = new StringBuilder();
            for (String href : plugin) {
                pluginCss.append(fetch(page, href)).append('\n');
            }
            StringBuilder themeCss = new StringBuilder();
            for (String href : other) {
                themeCss.append(fetch(page, href)).append('\n');
            }
            for (String problem : toneRuleProblems(pluginCss.toString(), themeCss.toString())) {
                problems.add("the plugin's stylesheet " + plugin + ": " + problem);
            }
        }
        assertTrue(problems.isEmpty(), "every screen that shows a status badge must link the plugin's stylesheet, and that"
                + " stylesheet must style the five tones from core's theme variables:\n  - " + String.join("\n  - ", problems));
    }

    /**
     * T-UI-266 (#18.2, colour badges; guard, "data stays data"): the tones do not reach the data.
     * requests.csv, incidents.csv and runs.csv keep the enum names in their status and cause columns
     * and hold no tone column or tone word; the History status filters offer the enum names as
     * values and their options carry no tone; a tone is not a filter value; no link of the History
     * screens carries a tone; the monthly JSON summary carries none.
     */
    @Test
    public void t_ui_266_tonesStayOutOfExportsFiltersAndTheSummary() throws Exception {
        Incidents incidents = incidentsInEveryStatus();
        FreeStyleProject timer = j.createFreeStyleProject("timer-x");
        j.assertBuildStatusSuccess(timer.scheduleBuild2(0, new TimerTrigger.TimerTriggerCause()));
        RunRequests r = runRequestsInEveryStatus();

        assertCsvColumn("requests.csv", "status", names(RequestStatus.values()), names(RequestStatus.values()));
        assertCsvColumn("incidents.csv", "status", names(IncidentStatus.values()), names(IncidentStatus.values()));
        assertCsvColumn("runs.csv", "causeType", names(CauseType.values()), Set.of("APPROVED_REQUEST", "TIMER"));

        HtmlPage requests = page("batch-control/history/?kind=requests");
        assertEquals(names(RequestStatus.values()), filterValues(requests, "History > Requests"),
                "the request Status filter keeps the enum names as its values");
        HtmlPage incidentHistory = page("batch-control/history/?kind=incidents");
        assertEquals(names(IncidentStatus.values()), filterValues(incidentHistory, "History > Incidents"),
                "the incident Status filter keeps the enum names as its values");
        for (HtmlPage page : List.of(requests, incidentHistory, page("batch-control/history/?kind=runs"))) {
            for (DomNode n : page.querySelectorAll("#main-panel a[href]")) {
                String href = ((DomElement) n).getAttribute("href");
                assertFalse(TONE_WORD.matcher(href).find() || href.contains("tone="), page.getUrl() + ": no link may carry a"
                        + " tone: " + href);
            }
        }

        String byTone = tables(page("batch-control/history/?kind=requests&status=warning"));
        for (RunRequest request : List.of(r.pending(), r.approved(), r.executed(), r.rejected(), r.cancelled(), r.expired(),
                r.invalidated())) {
            assertFalse(byTone.contains(request.getId().substring(0, 8)), "a tone is not a value of the status filter:"
                    + " status=warning must list no request: " + excerpt(byTone));
        }
        String incidentsByTone = tables(page("batch-control/history/?kind=incidents&status=danger"));
        assertFalse(incidentsByTone.contains(incidents.open().getId()), "a tone is not a value of the status filter:"
                + " status=danger must list no incident: " + excerpt(incidentsByTone));

        Page summary = get("batch-control/history/summary?month=" + YearMonth.now(BatchClock.clock()));
        assertEquals(200, summary.getWebResponse().getStatusCode(), "the JSON summary answers");
        String json = summary.getWebResponse().getContentAsString();
        JSONObject parsed = JSONObject.fromObject(json);
        assertFalse(Pattern.compile("(?<![A-Za-z])(?:warning|info|danger|neutral|tone)(?![A-Za-z])").matcher(json).find()
                || json.contains("batch-control-status"), "the JSON summary must carry no tone: " + json);
        for (Object key : parsed.keySet()) {
            assertFalse(parsed.get(key) instanceof String value && TONE_WORD.matcher(value).matches(),
                    "the JSON summary must carry no tone as a value: " + key + " in " + json);
        }
    }

    /**
     * T-UI-267 (#18.2, colour badges): no duplicated badge. In the requests, grants, activations
     * and incidents lists, in History > Requests and History > Incidents, and on the request, grant,
     * activation and incident pages, a table row that shows a status holds exactly one element with
     * the class {@code batch-control-status}, and it is the row's one element carrying
     * {@code data-batch-control-status}; each record has one such row.
     */
    @Test
    public void t_ui_267_aRowHoldsExactlyOneBadge() throws Exception {
        for (Screen screen : aStatusOnEveryScreen()) {
            assertOneBadgePerRow(page(screen.path()), screen.where(), screen.statuses());
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

    // ------------------------------------------------------------------ colour badges (T-UI-260..267)

    /**
     * Every element of the page that shows a request or an incident status is a badge: the class,
     * the contract's tone, the unchanged label as its whole text, no inline style. The statuses in
     * {@code expected} must be shown; nothing but such a status is a badge.
     */
    private static void assertBadges(HtmlPage page, String where, String... expected) {
        for (String name : expected) {
            assertFalse(page.querySelectorAll("[data-batch-control-status='" + name + "']").isEmpty(), where
                    + ": premise (T-UI-255..257): the status " + name + " is shown in an element carrying"
                    + " data-batch-control-status=\"" + name + "\"; tables read: " + excerpt(tables(page)));
        }
        for (DomNode n : page.querySelectorAll("[data-batch-control-status]")) {
            DomElement e = (DomElement) n;
            String name = e.getAttribute("data-batch-control-status");
            Enum<?> status = status(name);
            if (status == null) {
                continue; // a run cause: T-UI-263
            }
            String tone = TONE_OF.get(name);
            assertNotNull(tone, "the contract names no tone for " + name + ": it needs one, and a line in this test's table");
            assertTrue(classes(e).contains(BADGE_CLASS), where + ": the element showing " + name + " must be a badge, with"
                    + " the class \"" + BADGE_CLASS + "\": " + e.asXml().trim());
            assertEquals(tone, e.getAttribute(TONE), where + ": the badge for " + name + " must carry " + TONE + "=\"" + tone
                    + "\": " + e.asXml().trim());
            String label = label(status);
            String text = text(e);
            boolean unchanged = text.equals(label)
                    || status == RequestStatus.APPROVED && text.equals("Approved, waiting to run")
                    || status == RequestStatus.EXPIRED && text.equals("Expired without a decision")
                    || text.matches(Pattern.quote(label) + " by \\S+");
            assertTrue(unchanged, where + ": the badge for " + name + " must hold its label and nothing else (\"" + label
                    + "\", or the wording this screen had before the badges), was \"" + text + "\"");
            assertNoInlineStyle(e, where);
        }
        assertOnlyStatusesAreBadges(page, where);
    }

    /**
     * Whatever has the badge class or a tone is an element carrying a request or an incident status
     * in {@code data-batch-control-status}, with both the class and that status's tone. An empty
     * tone attribute counts as no tone.
     */
    private static void assertOnlyStatusesAreBadges(HtmlPage page, String where) {
        for (DomNode n : page.querySelectorAll("." + BADGE_CLASS + ", [" + TONE + "]")) {
            DomElement e = (DomElement) n;
            if (!classes(e).contains(BADGE_CLASS) && e.getAttribute(TONE).isEmpty()) {
                continue;
            }
            String name = e.getAttribute("data-batch-control-status");
            assertNotNull(status(name), where + ": only an element that shows a request or an incident status (and keeps"
                    + " it in data-batch-control-status) is a badge: " + e.asXml().trim());
            assertTrue(classes(e).contains(BADGE_CLASS) && e.getAttribute(TONE).equals(TONE_OF.get(name)), where
                    + ": a badge has the class \"" + BADGE_CLASS + "\" and the tone of its status (" + name + " is "
                    + TONE_OF.get(name) + "): " + e.asXml().trim());
        }
    }

    /**
     * Each table row of the main panel that shows a status holds exactly one badge, which is the
     * row's one status element; the rows show exactly the statuses {@code expected} (in any order).
     */
    private static void assertOneBadgePerRow(HtmlPage page, String where, List<String> expected) {
        List<String> shown = new ArrayList<>();
        for (DomNode n : page.querySelectorAll("#main-panel table tr")) {
            DomElement row = (DomElement) n;
            List<DomElement> inRow = new ArrayList<>();
            inRow.add(row);
            for (DomNode d : row.querySelectorAll("*")) {
                inRow.add((DomElement) d);
            }
            List<DomElement> statuses = new ArrayList<>();
            List<DomElement> badges = new ArrayList<>();
            for (DomElement e : inRow) {
                if (status(e.getAttribute("data-batch-control-status")) != null) {
                    statuses.add(e);
                }
                if (classes(e).contains(BADGE_CLASS)) {
                    badges.add(e);
                }
            }
            if (statuses.isEmpty() && badges.isEmpty()) {
                continue;
            }
            assertTrue(statuses.size() == 1 && statuses.equals(badges), where + ": a row that shows a status must hold exactly"
                    + " one badge, the element carrying data-batch-control-status (found " + statuses.size()
                    + " status element(s) and " + badges.size() + " element(s) with the class \"" + BADGE_CLASS + "\"): "
                    + excerpt(row.asXml().trim()));
            shown.add(statuses.get(0).getAttribute("data-batch-control-status"));
        }
        List<String> wanted = new ArrayList<>(expected);
        wanted.sort(null);
        shown.sort(null);
        assertEquals(wanted, shown, where + ": each record's status must be shown once, in a row of its own");
    }

    private static void assertNoInlineStyle(DomElement e, String where) {
        assertFalse(e.hasAttribute("style"), where + ": a status element must have no style attribute (the styling comes"
                + " from the plugin's stylesheet): " + e.asXml().trim());
        assertTrue(e.querySelectorAll("[style]").isEmpty(), where + ": nothing inside a status element may have a style"
                + " attribute: " + e.asXml().trim());
    }

    /**
     * What is wrong with the tone rules of the plugin's stylesheet {@code css}; {@code themeCss} is
     * every other stylesheet the page links (core's), which defines the theme variables.
     */
    private static List<String> toneRuleProblems(String css, String themeCss) {
        List<String> problems = new ArrayList<>();
        List<String[]> rules = new ArrayList<>(); // selector, declarations; the innermost blocks, so rules inside @media count
        Matcher block = Pattern.compile("([^{}]+)\\{([^{}]*)\\}").matcher(css.replaceAll("(?s)/\\*.*?\\*/", " "));
        while (block.find()) {
            rules.add(new String[] {block.group(1).trim(), block.group(2).trim()});
        }
        Map<String, List<String>> defined = new HashMap<>(); // the plugin's own custom properties
        for (String[] rule : rules) {
            Matcher definition = Pattern.compile("(?:^|;)\\s*(--[A-Za-z0-9_-]+)\\s*:([^;]*)").matcher(rule[1]);
            while (definition.find()) {
                defined.computeIfAbsent(definition.group(1), k -> new ArrayList<>()).add(definition.group(2).trim());
            }
        }

        List<String> badge = declarations(rules, Pattern.compile("\\." + BADGE_CLASS + "(?![A-Za-z0-9_-])"));
        if (badge.isEmpty()) {
            problems.add("no rule styles the class ." + BADGE_CLASS);
        }
        addHardCoded(problems, "the ." + BADGE_CLASS + " rule", badge, defined);
        for (Map.Entry<String, Pattern> tone : TONES.entrySet()) {
            String selector = "[" + TONE + "=\"" + tone.getKey() + "\"]";
            List<String> declared = declarations(rules, Pattern.compile(
                    "\\[\\s*" + TONE + "\\s*[~|^$*]?=\\s*([\"']?)" + tone.getKey() + "\\1\\s*\\]"));
            if (declared.isEmpty()) {
                problems.add("no rule selects " + selector);
                continue;
            }
            if (declared.stream().noneMatch(d -> d.contains("var(--"))) {
                problems.add("the rule for " + selector + " must take its colours from a CSS variable (var(--...)): " + declared);
            }
            addHardCoded(problems, "the rule for " + selector, declared, defined);
            Set<String> used = variables(declared, defined);
            boolean themed = used.stream().anyMatch(v -> !defined.containsKey(v) && tone.getValue().matcher(v).find()
                    && Pattern.compile(Pattern.quote(v) + "\\s*:").matcher(themeCss).find());
            if (!themed) {
                problems.add("the rule for " + selector + " must use core's theme variable for this tone (a variable named /"
                        + tone.getValue() + "/ that core's stylesheet defines); it uses " + used);
            }
        }
        return problems;
    }

    /** The declaration blocks of the rules whose selector matches. */
    private static List<String> declarations(List<String[]> rules, Pattern selector) {
        List<String> out = new ArrayList<>();
        for (String[] rule : rules) {
            if (selector.matcher(rule[0]).find()) {
                out.add(rule[1]);
            }
        }
        return out;
    }

    /** The variables the declarations use, followed through the plugin's own custom properties. */
    private static Set<String> variables(List<String> declarations, Map<String, List<String>> defined) {
        Set<String> used = new TreeSet<>();
        List<String> todo = new ArrayList<>(declarations);
        while (!todo.isEmpty()) {
            Matcher use = Pattern.compile("var\\(\\s*(--[A-Za-z0-9_-]+)").matcher(todo.remove(todo.size() - 1));
            while (use.find()) {
                if (used.add(use.group(1))) {
                    todo.addAll(defined.getOrDefault(use.group(1), List.of()));
                }
            }
        }
        return used;
    }

    /** Hard-coded colours in the declarations, or in the plugin's own variables they use. */
    private static void addHardCoded(List<String> problems, String what, List<String> declarations,
                                     Map<String, List<String>> defined) {
        for (String declared : declarations) {
            if (COLOUR_LITERAL.matcher(declared).find()) {
                problems.add(what + " must not hard-code a colour: " + declared);
            }
        }
        for (String variable : variables(declarations, defined)) {
            for (String value : defined.getOrDefault(variable, List.of())) {
                if (COLOUR_LITERAL.matcher(value).find()) {
                    problems.add(what + " uses " + variable + ", which the plugin's stylesheet hard-codes: " + value);
                }
            }
        }
    }

    /** The stylesheet a page links, over HTTP. */
    private String fetch(HtmlPage page, String href) throws Exception {
        String url = page.getFullyQualifiedUrl(href).toString();
        if (!fetched.containsKey(url)) {
            Page css = admin().getPage(new WebRequest(new URL(url), HttpMethod.GET));
            assertEquals(200, css.getWebResponse().getStatusCode(), "the stylesheet the page links must be served: " + url);
            fetched.put(url, css.getWebResponse().getContentAsString());
        }
        return fetched.get(url);
    }

    /**
     * The export's {@code column} holds only names of {@code allowed} and at least {@code present};
     * the export has no tone column and no tone word.
     */
    private void assertCsvColumn(String file, String column, Set<String> allowed, Set<String> present) throws Exception {
        String csv = get("batch-control/history/" + file).getWebResponse().getContentAsString();
        List<String> lines = csv.lines().filter(l -> !l.isBlank()).toList();
        List<String> header = Arrays.asList(lines.get(0).split(",", -1));
        assertTrue(header.contains(column), "guard: " + file + " keeps its " + column + " column: " + header);
        assertTrue(header.stream().noneMatch(h -> h.toLowerCase().contains("tone")), file + " must gain no tone column: " + header);
        Set<String> values = new TreeSet<>();
        for (String line : lines.subList(1, lines.size())) {
            values.add(line.split(",", -1)[header.indexOf(column)]); // the fixture's cells hold no comma
        }
        assertTrue(allowed.containsAll(values), file + ": the " + column + " column keeps the enum names, was " + values);
        assertTrue(values.containsAll(present), file + ": fixture: the " + column + " column holds " + present + ", was " + values);
        assertFalse(TONE_WORD.matcher(csv).find(), file + " must hold no tone: " + excerpt(csv));
    }

    /** The values of the History Status filter but "Any"; its options carry no tone and no badge class. */
    private static Set<String> filterValues(HtmlPage page, String where) {
        Set<String> values = new TreeSet<>();
        for (DomNode n : page.querySelectorAll("select[name='status'] option")) {
            DomElement option = (DomElement) n;
            assertFalse(option.hasAttribute(TONE) || classes(option).contains(BADGE_CLASS), where + ": a filter option carries"
                    + " no tone: " + option.asXml().trim());
            if (!option.getAttribute("value").isEmpty()) {
                values.add(option.getAttribute("value"));
            }
        }
        assertFalse(values.isEmpty(), where + ": premise (T-UI-251, T-UI-252): the Status filter is a dropdown");
        return values;
    }

    // ------------------------------------------------------------------ fixtures of the badge rows

    private record RunRequests(RunRequest pending, RunRequest approved, RunRequest executed, RunRequest rejected,
                               RunRequest cancelled, RunRequest expired, RunRequest invalidated) {
    }

    private record Incidents(Incident open, Incident acknowledged, Incident resolved) {
    }

    /** A screen of contract point 1, with the statuses its rows show in the fixture. */
    private record Screen(String where, String path, List<String> statuses) {
    }

    /**
     * Turns run control on and leaves a run request in each of the seven statuses: EXPIRED (filed 61
     * minutes ago by the replaced clock, pending timeout one hour), EXECUTED, REJECTED, CANCELLED,
     * INVALIDATED (its job {@code gone-x} deleted), PENDING and APPROVED (no executor, so it waits).
     */
    private RunRequests runRequestsInEveryStatus() throws Exception {
        cfg.setRunControlEnabled(true);
        cfg.setPendingTimeoutHours(1);
        cfg.save();
        FreeStyleProject job = j.createFreeStyleProject("batch-x");
        BatchControlFixtures.setBatchControl(job, new BatchControlJobProperty(true));
        FreeStyleProject gone = j.createFreeStyleProject("gone-x");
        BatchControlFixtures.setBatchControl(gone, new BatchControlJobProperty(true));

        RunRequest expired = anHourAgo(() -> request(job, "expired one"));
        expireOverdue();
        RunRequest executed = request(job, "executed one");
        as("a1", () -> { RunRequestService.get().approve(executed.getId(), "ok"); return null; });
        j.waitUntilNoActivity();
        RunRequest rejected = request(job, "rejected one");
        as("a1", () -> { RunRequestService.get().reject(rejected.getId(), "not today"); return null; });
        RunRequest cancelled = request(job, "cancelled one");
        as("u1", () -> { RunRequestService.get().cancel(cancelled.getId()); return null; });
        RunRequest invalidated = request(gone, "invalidated one");
        as("admin", () -> { gone.delete(); return null; });
        RunRequest pending = request(job, "pending one");
        j.jenkins.setNumExecutors(0); // the next approved run waits in the queue
        RunRequest approved = request(job, "approved one");
        as("a1", () -> { RunRequestService.get().approve(approved.getId(), "ok"); return null; });

        RunRequests all = new RunRequests(pending, approved, executed, rejected, cancelled, expired, invalidated);
        Map<RunRequest, RequestStatus> statuses = new LinkedHashMap<>();
        statuses.put(pending, RequestStatus.PENDING);
        statuses.put(approved, RequestStatus.APPROVED);
        statuses.put(executed, RequestStatus.EXECUTED);
        statuses.put(rejected, RequestStatus.REJECTED);
        statuses.put(cancelled, RequestStatus.CANCELLED);
        statuses.put(expired, RequestStatus.EXPIRED);
        statuses.put(invalidated, RequestStatus.INVALIDATED);
        for (Map.Entry<RunRequest, RequestStatus> e : statuses.entrySet()) {
            assertEquals(e.getValue(), RunRequestService.get().load(e.getKey().getId()).getStatus(), "fixture: the run request");
        }
        return all;
    }

    /** Three failed runs (run control must be off): one incident OPEN, one ACKNOWLEDGED, one RESOLVED. */
    private Incidents incidentsInEveryStatus() throws Exception {
        Incident open = failingRun("fail-x");
        Incident acknowledged = failingRun("fail2-x");
        Incident resolved = failingRun("fail3-x");
        as("admin", () -> {
            IncidentService.get().acknowledge(acknowledged.getId(), "looking");
            IncidentService.get().acknowledge(resolved.getId(), "looking");
            IncidentService.get().resolve(resolved.getId(), "fixed");
            return null;
        });
        assertEquals(IncidentStatus.OPEN, IncidentService.get().load(open.getId()).getStatus(), "fixture");
        assertEquals(IncidentStatus.ACKNOWLEDGED, IncidentService.get().load(acknowledged.getId()).getStatus(), "fixture");
        assertEquals(IncidentStatus.RESOLVED, IncidentService.get().load(resolved.getId()).getStatus(), "fixture");
        return new Incidents(open, acknowledged, resolved);
    }

    /**
     * One status on every screen of contract point 1: an open incident, a timer run, and a rejected
     * run request, grant request and activation request. Returns the ten screens.
     */
    private List<Screen> aStatusOnEveryScreen() throws Exception {
        Incident open = failingRun("fail-x");
        FreeStyleProject timer = j.createFreeStyleProject("timer-x");
        j.assertBuildStatusSuccess(timer.scheduleBuild2(0, new TimerTrigger.TimerTriggerCause()));
        j.createFreeStyleProject("win-x");
        cfg.setRunControlEnabled(true);
        cfg.save();
        FreeStyleProject job = j.createFreeStyleProject("batch-x");
        BatchControlFixtures.setBatchControl(job, new BatchControlJobProperty(true));
        RunRequest rejected = request(job, "rejected one");
        as("a1", () -> { RunRequestService.get().reject(rejected.getId(), "not today"); return null; });
        String grant = ApproverFormFixtures.submitGrantOk(j, "u1", "win-x", List.of("DELETE"), 30, "remove it", null, "a1");
        ApproverFormFixtures.assertSuccess(ApproverFormFixtures.decideGrant(j, "a1", grant, "reject", "no"),
                "fixture: a1 rejects the grant request");
        String activation = activation("act-x");
        ApproverFormFixtures.assertSuccess(ActivationFixtures.decideActivation(j, "a1", activation, "reject", "no"),
                "fixture: a1 rejects the activation request");

        List<String> rejectedOnce = List.of("REJECTED");
        List<String> openOnce = List.of("OPEN");
        return List.of(
                new Screen("the run request page", path(rejected), rejectedOnce),
                new Screen("the requests list", "batch-control/requests/", rejectedOnce),
                new Screen("History > Requests", "batch-control/history/?kind=requests", rejectedOnce),
                new Screen("the grant request page", "batch-control/grants/" + grant + "/", rejectedOnce),
                new Screen("the grants list", "batch-control/grants/", rejectedOnce),
                new Screen("the activation request page", "batch-control/activations/" + activation + "/", rejectedOnce),
                new Screen("the activations list", "batch-control/activations/", rejectedOnce),
                new Screen("the incident page (its status and its history)", "batch-control/incidents/" + open.getId() + "/",
                        List.of("OPEN", "OPEN")),
                new Screen("the incidents list", "batch-control/incidents/", openOnce),
                new Screen("History > Incidents", "batch-control/history/?kind=incidents", openOnce));
    }

    /** A pending ACTIVATE request by u1 for a new job created under run control (so not activated). */
    private String activation(String jobName) throws Exception {
        return ActivationFixtures.submitActivationOk(j, "u1", j.createFreeStyleProject(jobName), "ACTIVATE", "go live", "a1");
    }

    /**
     * Runs {@code body} with the clock replaced by one 61 minutes back, so that what it files is
     * overdue under a pending timeout of one hour once the clock is the system's again.
     */
    private static <V> V anHourAgo(Callable<V> body) throws Exception {
        BatchClock.setForTest(Clock.fixed(Instant.now().minus(Duration.ofMinutes(61)), ZoneOffset.UTC));
        try {
            return body.call();
        } finally {
            BatchClock.reset();
        }
    }

    /** The periodic expiry pass, run now: no timer and no waiting. */
    private static void expireOverdue() throws Exception {
        ExtensionList.lookupSingleton(ExpiryPeriodicWork.class).doRun();
    }

    /** The request or incident status named {@code name}, or null (a run cause, or no status). */
    private static Enum<?> status(String name) {
        for (RequestStatus s : RequestStatus.values()) {
            if (s.name().equals(name)) {
                return s;
            }
        }
        for (IncidentStatus s : IncidentStatus.values()) {
            if (s.name().equals(name)) {
                return s;
            }
        }
        return null;
    }

    /** The label of a constant, from the view helper of T-UI-259 (called reflectively, as there). */
    private static String label(Enum<?> constant) {
        try {
            return (String) Class.forName("io.jenkins.plugins.batchcontrol.ui.StatusLabels").getMethod("of", Enum.class)
                    .invoke(null, constant);
        } catch (ReflectiveOperationException e) {
            return fail("premise (T-UI-259): io.jenkins.plugins.batchcontrol.ui.StatusLabels.of(Enum<?>) -> String (" + e + ")");
        }
    }

    /** The whole text content of an element, white space collapsed. */
    private static String text(DomElement e) {
        return e.getTextContent().replaceAll("\\s+", " ").trim();
    }

    private static Set<String> classes(DomElement e) {
        return new LinkedHashSet<>(Arrays.asList(e.getAttribute("class").trim().split("\\s+")));
    }

    private static Set<String> names(Enum<?>[] constants) {
        Set<String> names = new TreeSet<>();
        for (Enum<?> constant : constants) {
            names.add(constant.name());
        }
        return names;
    }

    private static Map<String, Pattern> tones() {
        Map<String, Pattern> tones = new LinkedHashMap<>();
        tones.put("warning", Pattern.compile("warning"));
        tones.put("info", Pattern.compile("accent"));
        tones.put("success", Pattern.compile("success"));
        tones.put("danger", Pattern.compile("error|destructive"));
        tones.put("neutral", Pattern.compile("secondary"));
        return tones;
    }

    private static Map<String, String> toneOf() {
        Map<String, String> tone = new LinkedHashMap<>();
        tone.put("PENDING", "warning");
        tone.put("APPROVED", "info");
        tone.put("EXECUTED", "success");
        tone.put("REJECTED", "danger");
        tone.put("CANCELLED", "neutral");
        tone.put("EXPIRED", "neutral");
        tone.put("INVALIDATED", "neutral");
        tone.put("OPEN", "danger");
        tone.put("ACKNOWLEDGED", "warning");
        tone.put("RESOLVED", "success");
        return tone;
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
        return admin().getPage(new WebRequest(new URL(j.getURL(), path), HttpMethod.GET));
    }

    /** One session of admin per test, without scripts. */
    private JenkinsRule.WebClient admin() throws Exception {
        if (adminClient == null) {
            adminClient = j.createWebClient().withThrowExceptionOnFailingStatusCode(false).login("admin");
            adminClient.getOptions().setJavaScriptEnabled(false);
        }
        return adminClient;
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
