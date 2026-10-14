package io.jenkins.plugins.batchcontrol;

import hudson.model.FreeStyleProject;
import hudson.model.Item;
import hudson.model.Result;
import hudson.model.User;
import hudson.security.ACL;
import hudson.security.ACLContext;
import io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration;
import io.jenkins.plugins.batchcontrol.config.BatchControlJobProperty;
import io.jenkins.plugins.batchcontrol.model.Incident;
import io.jenkins.plugins.batchcontrol.model.RequestStatus;
import io.jenkins.plugins.batchcontrol.model.RunRequest;
import io.jenkins.plugins.batchcontrol.ops.IncidentService;
import io.jenkins.plugins.batchcontrol.policy.RunRequestService;
import io.jenkins.plugins.batchcontrol.security.BatchControlPermissions;
import io.jenkins.plugins.batchcontrol.store.BatchClock;
import java.net.URL;
import java.time.YearMonth;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
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
import org.jvnet.hudson.test.JenkinsRule;
import org.jvnet.hudson.test.MockAuthorizationStrategy;
import org.jvnet.hudson.test.junit.jupiter.WithJenkins;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Wave D, group D2, follow-up of issue #18 items 2 and 3 (matrix rows T-UI-269e..269i, note 361
 * point 9; owner decision 2 of 2026-10-14): build results are shown with readable labels, as plain
 * text and not as badges, on the six places that show one: the incidents list, the incident page's
 * Result row, History &gt; Incidents, History &gt; Runs, the run dashboard and the Build table of a
 * run request page (Build / Result / Started / Duration). The labels are the words of the History
 * Result dropdown: SUCCESS "Success", UNSTABLE "Unstable", FAILURE "Failed", NOT_BUILT "Not built",
 * ABORTED "Aborted" ({@link ResultFixtures#RESULT_LABELS}).
 *
 * <p>"Shows the label" is measured on the result cell (the cell under the table's "Result" heading,
 * in the row naming the job; on the incident page the cell of the row headed "Result"): its whole
 * text, white space collapsed, is the label, so the raw enum word is not the cell text; neither the
 * cell nor anything inside it has the class {@code batch-control-status} or a
 * {@code data-batch-control-tone} attribute (a result is not a badge, point 7 of note 361). Guards:
 * {@code incidents.csv} and {@code runs.csv} keep the raw names; a build that is still running
 * keeps today's rendering (the request page reads {@code IN PROGRESS} with an empty duration; the
 * dashboard and History &gt; Runs do not list it until it completes).
 *
 * <p>Written from that decision and from pages rendered on this branch (f2e150bc); no src/main
 * knowledge.
 */
@WithJenkins
public class ResultLabelPageTest {

    private static final String BADGE_CLASS = "batch-control-status";
    private static final String TONE = "data-batch-control-tone";
    /** The results that open an incident in the fixture (incidentResults holds ABORTED). */
    private static final List<String> INCIDENT_RESULTS = List.of("FAILURE", "UNSTABLE", "ABORTED");

    private JenkinsRule j;
    private BatchControlGlobalConfiguration cfg;
    private JenkinsRule.WebClient adminClient;

    @BeforeEach
    public void setUp(JenkinsRule rule) throws Exception {
        this.j = rule;
        j.jenkins.setSecurityRealm(j.createDummySecurityRealm());
        j.jenkins.setAuthorizationStrategy(new MockAuthorizationStrategy()
                .grant(Jenkins.ADMINISTER).everywhere().to("admin")
                .grant(Jenkins.READ, Item.READ, Item.BUILD, BatchControlPermissions.REQUEST).everywhere().to("u1")
                .grant(Jenkins.READ, Item.READ, BatchControlPermissions.APPROVE).everywhere().to("a1"));
        cfg = BatchControlGlobalConfiguration.get();
        cfg.setChangeControlEnabled(true);
        cfg.setApprovers(Arrays.asList("a1"));
        cfg.setIncidentResults(Arrays.asList("FAILURE", "UNSTABLE", "ABORTED"));
        cfg.save();
    }

    /**
     * T-UI-269e (owner decision 2 of 2026-10-14): the incidents list, each incident page's Result row
     * and History &gt; Incidents show the result of the FAILURE, UNSTABLE and ABORTED incidents as
     * Failed, Unstable and Aborted, as plain text (not a badge), never the raw enum word.
     */
    @Test
    public void t_ui_269e_incidentScreensShowResultLabels() throws Exception {
        Map<String, RunRequest> runs = approvedRunInEveryResult();
        Map<String, Incident> incidents = new LinkedHashMap<>();
        for (String result : INCIDENT_RESULTS) {
            String runId = job(result) + "#1";
            Incident incident = IncidentService.get().list(YearMonth.now(BatchClock.clock())).stream()
                    .filter(i -> runId.equals(i.getRunId())).findFirst().orElse(null);
            assertNotNull(incident, "premise (SPEC 11, incidentResults with ABORTED): the " + result + " run opens an incident");
            assertEquals(result, incident.getResult(), "premise: the incident keeps the raw result");
            incidents.put(result, incident);
        }
        assertEquals(5, runs.size(), "premise: one approved run per result");

        for (String path : List.of("batch-control/incidents/", "batch-control/history/?kind=incidents")) {
            HtmlPage page = page(path);
            for (String result : INCIDENT_RESULTS) {
                assertResultCell(tableResultCell(page, job(result), path), result, path + ", the incident of " + job(result));
            }
        }
        for (Map.Entry<String, Incident> e : incidents.entrySet()) {
            String path = "batch-control/incidents/" + e.getValue().getId() + "/";
            assertResultCell(rowHeadedResult(page(path), path), e.getKey(), "the incident page of " + job(e.getKey()));
        }
    }

    /**
     * T-UI-269f (owner decision 2 of 2026-10-14): History &gt; Runs and the run dashboard show the
     * result of each of the five runs (SUCCESS, UNSTABLE, FAILURE, NOT_BUILT, ABORTED) as its label,
     * as plain text, never the raw enum word.
     */
    @Test
    public void t_ui_269f_runScreensShowResultLabels() throws Exception {
        approvedRunInEveryResult();
        for (String path : List.of("batch-control/history/?kind=runs", "batch-control/dashboard/")) {
            HtmlPage page = page(path);
            for (String result : ResultFixtures.ALL_RESULTS) {
                assertResultCell(tableResultCell(page, job(result), path), result, path + ", the run of " + job(result));
            }
        }
    }

    /**
     * T-UI-269g (owner decision 2 of 2026-10-14): the Build table of a run request page (Build /
     * Result / Started / Duration) shows the result of the request's build as its label, as plain
     * text, for each of the five results.
     */
    @Test
    public void t_ui_269g_runRequestBuildTableShowsResultLabels() throws Exception {
        Map<String, RunRequest> runs = approvedRunInEveryResult();
        for (Map.Entry<String, RunRequest> e : runs.entrySet()) {
            String path = "batch-control/requests/" + e.getValue().getId() + "/";
            DomElement row = buildTableRow(page(path), path);
            assertResultCell(cellUnder(row, "Result", path), e.getKey(), "the request page of " + job(e.getKey())
                    + ", Build table");
        }
    }

    /**
     * T-UI-269h (guard, owner decision 2 of 2026-10-14: a build with no result yet keeps today's
     * rendering): while the approved run of a request is still running, the request page's Build
     * table lists it with the Result cell reading {@code IN PROGRESS} (not a badge) and an empty
     * Duration; the dashboard and History &gt; Runs do not list it.
     */
    @Test
    public void t_ui_269h_runningBuildKeepsTodaysRendering() throws Exception {
        cfg.setRunControlEnabled(true);
        cfg.save();
        FreeStyleProject job = j.createFreeStyleProject("hold-x");
        BatchControlFixtures.setBatchControl(job, new BatchControlJobProperty(true));
        job.getBuildersList().add(new ResultFixtures.Hold());
        ResultFixtures.Hold.arm();
        try {
            RunRequest request = as("u1", () -> RunRequestService.get().create(job, new LinkedHashMap<>(), "hold it", "a1"));
            as("a1", () -> { RunRequestService.get().approve(request.getId(), "ok"); return null; });
            assertTrue(ResultFixtures.Hold.awaitStarted(), "fixture: the approved run starts and is held");
            assertTrue(job.getLastBuild() != null && job.getLastBuild().isBuilding(), "fixture: the build is still running");

            String path = "batch-control/requests/" + request.getId() + "/";
            DomElement row = buildTableRow(page(path), path);
            DomElement result = cellUnder(row, "Result", path);
            assertNotBadge(result, path + ", the running build");
            assertEquals("IN PROGRESS", text(result), path + ": a build with no result yet keeps today's text");
            assertEquals("", text(cellUnder(row, "Duration", path)), path + ": a running build has no duration yet");

            for (String listing : List.of("batch-control/dashboard/", "batch-control/history/?kind=runs")) {
                String tables = tables(page(listing));
                assertFalse(Pattern.compile("(?<![\\w-])hold-x(?![\\w-])").matcher(tables).find(), listing
                        + ": a run that has not completed is not listed yet: " + excerpt(tables));
            }
        } finally {
            ResultFixtures.Hold.release();
            j.waitUntilNoActivity();
        }
    }

    /**
     * T-UI-269i (guard, owner decision 2 of 2026-10-14): the CSV exports keep the raw enum names:
     * the {@code result} column of {@code incidents.csv} holds FAILURE, UNSTABLE, ABORTED and that of
     * {@code runs.csv} the five result names, and no label.
     */
    @Test
    public void t_ui_269i_csvExportsKeepRawResultNames() throws Exception {
        approvedRunInEveryResult();
        assertEquals(new TreeSet<>(INCIDENT_RESULTS), csvColumn("incidents.csv", "result"),
                "incidents.csv keeps the raw result names");
        assertEquals(new TreeSet<>(ResultFixtures.ALL_RESULTS), csvColumn("runs.csv", "result"),
                "runs.csv keeps the raw result names");
    }

    // ------------------------------------------------------------------ assertions

    /**
     * The result cell shows {@code raw}'s label as its whole text and is not a badge: neither it
     * nor anything inside it has the class {@code batch-control-status} or a tone attribute.
     */
    private static void assertResultCell(DomElement cell, String raw, String where) {
        assertNotBadge(cell, where);
        String text = text(cell);
        assertFalse(text.equals(raw) || Pattern.compile("(?<![A-Za-z_])" + raw + "(?![A-Za-z_])").matcher(text).find(),
                where + ": the result must be shown as a readable label, not the raw enum word: '" + text + "'");
        assertEquals(ResultFixtures.RESULT_LABELS.get(raw), text, where + ": the result " + raw + " reads its label");
    }

    private static void assertNotBadge(DomElement cell, String where) {
        List<DomElement> all = new ArrayList<>();
        all.add(cell);
        for (DomNode n : cell.querySelectorAll("*")) {
            all.add((DomElement) n);
        }
        for (DomElement e : all) {
            assertFalse(classes(e).contains(BADGE_CLASS), where + ": a result is not a badge, nothing in its cell may have"
                    + " the class \"" + BADGE_CLASS + "\": " + cell.asXml().trim());
            assertFalse(e.hasAttribute(TONE), where + ": a result is not a badge, nothing in its cell may carry " + TONE
                    + ": " + cell.asXml().trim());
        }
    }

    // ------------------------------------------------------------------ locating the cells

    /**
     * The cell under the "Result" heading in the one row of a listing table whose Job cell reads
     * {@code job}.
     */
    private static DomElement tableResultCell(HtmlPage page, String job, String where) {
        List<DomElement> cells = new ArrayList<>();
        for (DomNode t : page.querySelectorAll("#main-panel table")) {
            List<String> headings = headings((DomElement) t);
            int index = headings.indexOf("Result");
            int jobIndex = headings.indexOf("Job");
            if (index < 0 || jobIndex < 0) {
                continue;
            }
            for (DomNode r : t.querySelectorAll("tbody tr")) {
                List<DomElement> tds = cellsOf((DomElement) r);
                if (index < tds.size() && jobIndex < tds.size() && job.equals(text(tds.get(jobIndex)))) {
                    cells.add(tds.get(index));
                }
            }
        }
        assertEquals(1, cells.size(), where + ": premise: one row of a table with a Result column has the Job cell " + job + "; tables"
                + " read: " + excerpt(tables(page)));
        return cells.get(0);
    }

    /** The cell of the incident page's row headed "Result". */
    private static DomElement rowHeadedResult(HtmlPage page, String where) {
        List<DomElement> cells = new ArrayList<>();
        for (DomNode r : page.querySelectorAll("#main-panel table tr")) {
            DomElement row = (DomElement) r;
            List<DomNode> th = row.querySelectorAll("th");
            List<DomElement> td = cellsOf(row);
            if (th.size() == 1 && "Result".equals(collapse(th.get(0).getTextContent())) && td.size() == 1) {
                cells.add(td.get(0));
            }
        }
        assertEquals(1, cells.size(), where + ": premise: the incident page has one row headed Result; tables read: "
                + excerpt(tables(page)));
        return cells.get(0);
    }

    /** The one body row of the request page's Build table (headed Build, Result, Started, Duration). */
    private static DomElement buildTableRow(HtmlPage page, String where) {
        for (DomNode t : page.querySelectorAll("#main-panel table")) {
            List<String> headings = headings((DomElement) t);
            if (headings.containsAll(List.of("Build", "Result", "Started", "Duration"))) {
                List<DomNode> rows = t.querySelectorAll("tbody tr");
                assertEquals(1, rows.size(), where + ": premise: the request's Build table lists its one build: "
                        + excerpt(((DomElement) t).asNormalizedText()));
                return (DomElement) rows.get(0);
            }
        }
        throw new AssertionError(where + ": premise: the request page has a Build table (Build / Result / Started /"
                + " Duration); tables read: " + excerpt(tables(page)));
    }

    /** The cell of {@code row} under the heading {@code heading} of its table. */
    private static DomElement cellUnder(DomElement row, String heading, String where) {
        DomNode t = row;
        while (t != null && !(t instanceof DomElement e && "table".equals(e.getTagName()))) {
            t = t.getParentNode();
        }
        assertNotNull(t, where + ": the row is in a table");
        int index = headings((DomElement) t).indexOf(heading);
        List<DomElement> tds = cellsOf(row);
        assertTrue(index >= 0 && index < tds.size(), where + ": premise: the table has a " + heading + " column: "
                + excerpt(row.asXml()));
        return tds.get(index);
    }

    private static List<String> headings(DomElement table) {
        List<String> out = new ArrayList<>();
        for (DomNode th : table.querySelectorAll("thead th")) {
            out.add(collapse(th.getTextContent()));
        }
        return out;
    }

    private static List<DomElement> cellsOf(DomElement row) {
        List<DomElement> out = new ArrayList<>();
        for (DomNode n : row.getChildNodes()) {
            if (n instanceof DomElement e && "td".equals(e.getTagName())) {
                out.add(e);
            }
        }
        return out;
    }

    // ------------------------------------------------------------------ fixtures

    /** The job of the fixture whose approved run ends with {@code result}. */
    private static String job(String result) {
        return result.toLowerCase().replace('_', '-') + "-x";
    }

    /**
     * Run control on; for each of the five results an approval-required job (success-x, unstable-x,
     * failure-x, not-built-x, aborted-x) whose approved run ends with that result. With ABORTED in
     * incidentResults, the UNSTABLE, FAILURE and ABORTED runs open incidents. Returns the requests by
     * result.
     */
    private Map<String, RunRequest> approvedRunInEveryResult() throws Exception {
        cfg.setRunControlEnabled(true);
        cfg.save();
        Map<String, RunRequest> out = new LinkedHashMap<>();
        for (String result : ResultFixtures.ALL_RESULTS) {
            FreeStyleProject job = j.createFreeStyleProject(job(result));
            BatchControlFixtures.setBatchControl(job, new BatchControlJobProperty(true));
            job.getBuildersList().add(new ResultFixtures.SetResult(result));
            RunRequest request = as("u1", () -> RunRequestService.get().create(job, new LinkedHashMap<>(), "run " + result, "a1"));
            as("a1", () -> { RunRequestService.get().approve(request.getId(), "ok"); return null; });
            j.waitUntilNoActivity();
            assertEquals(RequestStatus.EXECUTED, RunRequestService.get().load(request.getId()).getStatus(),
                    "fixture: the request on " + job.getName() + " executed");
            assertNotNull(job.getLastBuild(), "fixture: " + job.getName() + " ran");
            assertEquals(Result.fromString(result), job.getLastBuild().getResult(), "fixture: " + job.getName() + " ended " + result);
            out.put(result, request);
        }
        return out;
    }

    /** The distinct values of the export's {@code column} (the fixture's cells hold no comma). */
    private Set<String> csvColumn(String file, String column) throws Exception {
        Page csv = get("batch-control/history/" + file);
        assertEquals(200, csv.getWebResponse().getStatusCode(), "GET " + file);
        List<String> lines = csv.getWebResponse().getContentAsString().replace("﻿", "").lines()
                .filter(l -> !l.isBlank()).toList();
        List<String> header = Arrays.asList(lines.get(0).split(",", -1));
        assertTrue(header.contains(column), file + " keeps its " + column + " column: " + header);
        Set<String> values = new TreeSet<>();
        for (String line : lines.subList(1, lines.size())) {
            values.add(line.split(",", -1)[header.indexOf(column)]);
        }
        return values;
    }

    // ------------------------------------------------------------------ plumbing

    private static String text(DomElement e) {
        return collapse(e.getTextContent());
    }

    private static String collapse(String s) {
        return s.replaceAll("\\s+", " ").trim();
    }

    private static Set<String> classes(DomElement e) {
        return new LinkedHashSet<>(Arrays.asList(e.getAttribute("class").trim().split("\\s+")));
    }

    private static String tables(HtmlPage page) {
        StringBuilder out = new StringBuilder();
        for (DomNode n : page.querySelectorAll("#main-panel table")) {
            out.append(n.asNormalizedText()).append('\n');
        }
        return out.toString();
    }

    private HtmlPage page(String path) throws Exception {
        Page answer = get(path);
        assertEquals(200, answer.getWebResponse().getStatusCode(), "admin GET " + path);
        return (HtmlPage) answer;
    }

    private Page get(String path) throws Exception {
        if (adminClient == null) {
            adminClient = j.createWebClient().withThrowExceptionOnFailingStatusCode(false).login("admin");
            adminClient.getOptions().setJavaScriptEnabled(false);
        }
        return adminClient.getPage(new WebRequest(new URL(j.getURL(), path), HttpMethod.GET));
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
