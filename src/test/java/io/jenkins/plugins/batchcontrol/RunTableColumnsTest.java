package io.jenkins.plugins.batchcontrol;

import com.cloudbees.hudson.plugins.folder.Folder;
import hudson.model.FreeStyleBuild;
import hudson.model.FreeStyleProject;
import hudson.model.Item;
import hudson.model.ParameterDefinition;
import hudson.model.ParametersDefinitionProperty;
import hudson.model.Result;
import hudson.model.StringParameterDefinition;
import hudson.model.User;
import hudson.security.ACL;
import hudson.security.ACLContext;
import io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration;
import io.jenkins.plugins.batchcontrol.config.BatchControlJobProperty;
import io.jenkins.plugins.batchcontrol.model.CauseType;
import io.jenkins.plugins.batchcontrol.model.RunRecord;
import io.jenkins.plugins.batchcontrol.model.RunRequest;
import io.jenkins.plugins.batchcontrol.policy.RunRequestService;
import io.jenkins.plugins.batchcontrol.security.BatchControlPermissions;
import io.jenkins.plugins.batchcontrol.store.BatchClock;
import io.jenkins.plugins.batchcontrol.store.FileStore;
import java.net.URL;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import jenkins.model.CauseOfInterruption;
import jenkins.model.Jenkins;
import org.htmlunit.HttpMethod;
import org.htmlunit.Page;
import org.htmlunit.WebRequest;
import org.htmlunit.html.DomElement;
import org.htmlunit.html.DomNode;
import org.htmlunit.html.DomText;
import org.htmlunit.html.HtmlPage;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.jvnet.hudson.test.FailureBuilder;
import org.jvnet.hudson.test.JenkinsRule;
import org.jvnet.hudson.test.MockAuthorizationStrategy;
import org.jvnet.hudson.test.SleepBuilder;
import org.jvnet.hudson.test.junit.jupiter.WithJenkins;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Wave D, group D3, issues #6 and #18 item 1 (matrix rows T-UI-276..284, note 362): the run tables
 * (Run Dashboard, History > Runs) shrink from 10 to 7 columns: Run (the core status icon with a
 * tooltip, the job link and the {@code #n} run link), Cause, User, Parameters (the first 3 lines,
 * the rest in {@code <details>}; each value cut at about 120 characters on screen), Started,
 * Duration, Request id. An unknown result is text without an icon; links are only for viewers
 * with Item/Read, using the resolved job's and run's own URLs; "Aborted by" is still shown; times,
 * causes, users and durations do not wrap; full values stay whole in the CSV, on the request page
 * and on the build page; names and values are escaped. The incident tables (Incidents list,
 * History > Incidents) use the same Run cell (T-UI-284, note 362 (3)).
 *
 * <p>Fixture: folder {@code ops}; {@code ops/fail-x} failed (an incident); {@code ops/abort-x} was
 * aborted by u1; run control on; approval-required {@code ops/batch-x} with ten string parameters
 * ran from u1's request approved by a2; a run record of {@code ops/ghost-x#7} with the unknown
 * result {@code WEIRD}. u1 holds Item/Read; a2 (Approve, ViewHistory) does not (as T-06-51).
 *
 * <p>Written from the Wave D contract (D3, frozen 2026-10-10), issues #6 and #18, SPEC 6 and 10,
 * and pages rendered on origin/main (d80e5fe); no src/main knowledge.
 */
@WithJenkins
public class RunTableColumnsTest {

    private static final List<String> COLUMNS =
            List.of("Run", "Cause", "User", "Parameters", "Started", "Duration", "Request id");
    private static final List<String> RUN_PAGES =
            List.of("batch-control/dashboard/", "batch-control/history/?kind=runs");
    private static final List<String> INCIDENT_PAGES =
            List.of("batch-control/incidents/", "batch-control/history/?kind=incidents");
    /** 300 characters: a cut at about 120 shows all the a's and never reaches the z's. */
    private static final String LONG = "a".repeat(100) + "b".repeat(100) + "z".repeat(100);
    private static final String MARKUP = "<img src=x onerror=alert(1)>";

    private JenkinsRule j;
    private FreeStyleProject batch;
    private RunRequest request;

    @BeforeEach
    public void setUp(JenkinsRule rule) throws Exception {
        this.j = rule;
        j.jenkins.setSecurityRealm(j.createDummySecurityRealm());
        j.jenkins.setAuthorizationStrategy(new MockAuthorizationStrategy()
                .grant(Jenkins.ADMINISTER).everywhere().to("admin")
                .grant(Jenkins.READ, Item.READ, Item.BUILD, BatchControlPermissions.REQUEST,
                        BatchControlPermissions.VIEW_HISTORY).everywhere().to("u1")
                .grant(Jenkins.READ, BatchControlPermissions.APPROVE, BatchControlPermissions.VIEW_HISTORY)
                        .everywhere().to("a2"));
        BatchControlGlobalConfiguration cfg = BatchControlGlobalConfiguration.get();
        cfg.setChangeControlEnabled(true);
        cfg.setApprovers(Arrays.asList("a2"));
        cfg.save();
        Folder ops = j.jenkins.createProject(Folder.class, "ops");
        FreeStyleProject fail = ops.createProject(FreeStyleProject.class, "fail-x");
        fail.getBuildersList().add(new FailureBuilder());
        j.buildAndAssertStatus(Result.FAILURE, fail);
        FreeStyleProject abort = ops.createProject(FreeStyleProject.class, "abort-x");
        abort.getBuildersList().add(new SleepBuilder(60_000));
        FreeStyleBuild aborted = abort.scheduleBuild2(0).waitForStart();
        long deadline = System.currentTimeMillis() + 10_000;
        while (aborted.getExecutor() == null && System.currentTimeMillis() < deadline) {
            Thread.sleep(50);
        }
        assertNotNull(aborted.getExecutor(), "fixture: the build runs");
        aborted.getExecutor().interrupt(Result.ABORTED, new CauseOfInterruption.UserInterruption("u1"));
        j.waitForCompletion(aborted);
        j.assertBuildStatus(Result.ABORTED, aborted);

        cfg.setRunControlEnabled(true);
        cfg.save();
        batch = ops.createProject(FreeStyleProject.class, "batch-x");
        List<ParameterDefinition> definitions = new ArrayList<>();
        Map<String, String> values = new LinkedHashMap<>();
        for (int i = 1; i <= 10; i++) {
            String name = String.format(Locale.ROOT, "P%02d", i);
            definitions.add(new StringParameterDefinition(name, "d"));
            values.put(name, i == 2 ? LONG : i == 3 ? MARKUP : "v" + i);
        }
        batch.addProperty(new ParametersDefinitionProperty(definitions));
        BatchControlFixtures.setBatchControl(batch, new BatchControlJobProperty(true));
        try (ACLContext ignored = as("u1")) {
            request = RunRequestService.get().create(batch, values, "ten parameters", "a2");
        }
        try (ACLContext ignored = as("a2")) {
            RunRequestService.get().approve(request.getId(), "ok");
        }
        j.waitUntilNoActivity();
        assertNotNull(batch.getBuildByNumber(1), "fixture: the approved run executed");
        FileStore.get().appendRunRecord(new RunRecord("ops/ghost-x#7", "ops/ghost-x", 7, CauseType.OTHER, "WEIRD",
                BatchClock.clock().instant(), 10L));
    }

    /** T-UI-276 (#6, #18.1): the Run Dashboard's run table has exactly the 7 columns, every row 7 cells. */
    @Test
    public void t_ui_276_dashboardHasSevenColumns() throws Exception {
        assertSevenColumns("batch-control/dashboard/");
    }

    /** T-UI-277 (#6, #18.1): History > Runs has exactly the 7 columns, every row 7 cells. */
    @Test
    public void t_ui_277_historyRunsHaveSevenColumns() throws Exception {
        assertSevenColumns("batch-control/history/?kind=runs");
    }

    /**
     * T-UI-278 (#6): the Run cell of {@code ops/batch-x#1} (SUCCESS) and {@code ops/fail-x#1}
     * (FAILURE) holds a status icon whose tooltip names the result, a link to the job's own URL and
     * a link reading {@code #1} to the run's own URL; the result is not printed as text in the row.
     * On the dashboard and History > Runs, for the administrator.
     */
    @Test
    public void t_ui_278_runCellHasIconJobLinkAndRunLink() throws Exception {
        for (String path : RUN_PAGES) {
            HtmlPage page = page("admin", path);
            assertRunCell(page, path, "ops/batch-x", 1, "success", "SUCCESS");
            assertRunCell(page, path, "ops/fail-x", 1, "fail", "FAILURE");
        }
    }

    /**
     * T-UI-279 (#6): the run record of {@code ops/ghost-x#7} with the unknown result {@code WEIRD}
     * shows the result as text in its Run cell and no icon, and no link to the missing job.
     */
    @Test
    public void t_ui_279_unknownResultIsTextWithoutIcon() throws Exception {
        for (String path : RUN_PAGES) {
            HtmlPage page = page("admin", path);
            DomElement row = rowWithText(page, "ghost-x");
            assertNotNull(row, path + ": the ghost run must be listed");
            assertEquals(COLUMNS.size(), cells(row).size(), path + ": the ghost row has the 7 cells: " + row.asNormalizedText());
            DomElement run = cells(row).get(0);
            assertTrue(run.asNormalizedText().contains("WEIRD"), path + ": an unknown result is shown as text in the Run cell: "
                    + run.asNormalizedText());
            assertTrue(run.querySelectorAll("svg, img").isEmpty(), path + ": an unknown result has no icon: " + run.asXml());
            for (DomNode a : run.querySelectorAll("a")) {
                assertFalse(((DomElement) a).getAttribute("href").contains("ghost-x"), path + ": no link to the missing job");
            }
        }
    }

    /**
     * T-UI-280 (#6, SPEC 6 link rule, D-44): u1 (Item/Read) gets the job link and the run link in
     * the Run cell on the dashboard, History > Runs, the Incidents list and History > Incidents; a2
     * (no Item/Read) gets the job name and {@code #1} as text with no link to the job or the run.
     */
    @Test
    public void t_ui_280_linksOnlyForViewersWhoCanReadTheJob() throws Exception {
        List<String> pages = new ArrayList<>(RUN_PAGES);
        pages.addAll(INCIDENT_PAGES);
        for (String path : pages) {
            HtmlPage blind = page("a2", path);
            DomElement row = rowWithText(blind, "fail-x");
            assertNotNull(row, path + ": a2 is shown the failed run as text: " + excerpt(blind));
            for (DomNode a : row.querySelectorAll("a")) {
                String href = ((DomElement) a).getAttribute("href");
                assertFalse(href.contains("job/ops/job/fail-x"), path + ": a2 must get no link to the job or the run: " + href);
            }
            assertTrue(row.asNormalizedText().contains("#1"), path + ": a2 still sees the run number: " + row.asNormalizedText());

            HtmlPage reader = page("u1", path);
            DomElement linked = runRow(reader, "ops/fail-x", 1);
            assertNotNull(linked, path + ": u1 gets the run link of ops/fail-x#1");
            assertTrue(hasLink(cells(linked).get(0), jobPath("ops/fail-x")), path + ": u1 gets the job link "
                    + jobPath("ops/fail-x") + " in the Run cell: " + cells(linked).get(0).asXml());
        }
    }

    /**
     * T-UI-281 (#6, #18.1, SPEC 6 escaping): the Parameters cell of {@code ops/batch-x#1} shows the
     * first 3 parameters (P01..P03) outside a {@code <details>} element and P04..P10 inside it; the
     * 300-character P02 is cut on screen (all a's shown, no z's); P03's markup is text, not an
     * element. Guards: the full P02 is in runs.csv, on the request page and on the build's
     * parameters page.
     */
    @Test
    public void t_ui_281_longParameterListsFoldAndLongValuesAreCut() throws Exception {
        assertTrue(get("admin", "batch-control/history/runs.csv").getWebResponse().getContentAsString().contains(LONG),
                "guard: runs.csv keeps the full value");
        assertTrue(get("admin", "batch-control/requests/" + request.getId() + "/").getWebResponse().getContentAsString()
                .contains(LONG), "guard: the request page keeps the full value");
        assertTrue(get("admin", batch.getUrl() + "1/parameters/").getWebResponse().getContentAsString().contains(LONG),
                "guard: the build page keeps the full value");

        for (String path : RUN_PAGES) {
            HtmlPage page = page("admin", path);
            DomElement row = runRow(page, "ops/batch-x", 1);
            assertNotNull(row, path + ": the approved run is listed");
            int index = headers(table(row)).indexOf("Parameters");
            assertTrue(index >= 0, path + ": the table has a Parameters column");
            DomElement cell = cells(row).get(index);
            List<DomNode> details = cell.querySelectorAll("details");
            assertEquals(1, details.size(), path + ": the parameters beyond the third must be in one <details>: " + cell.asXml());
            String outside = textOutsideDetails(cell);
            String inside = details.get(0).getTextContent();
            for (int i = 1; i <= 10; i++) {
                String name = String.format(Locale.ROOT, "P%02d", i);
                if (i <= 3) {
                    assertTrue(outside.contains(name), path + ": " + name + " is one of the first 3 lines: " + outside);
                } else {
                    assertFalse(outside.contains(name), path + ": " + name + " must not be among the first lines: " + outside);
                    assertTrue(inside.contains(name), path + ": " + name + " must be in the <details>: " + inside);
                }
            }
            String text = cell.getTextContent();
            assertTrue(text.contains("a".repeat(100)), path + ": the start of a long value is shown");
            assertFalse(text.contains("zzz"), path + ": a long value is cut at about 120 characters on screen");
            assertTrue(cell.querySelectorAll("img").isEmpty(), path + ": a value's markup must not become an element");
            assertTrue(text.contains("<img"), path + ": a value's markup is shown as text");
        }
    }

    /**
     * T-UI-282 (#6): with no "Aborted by" column, the row of {@code ops/abort-x#1} still says it was
     * aborted by u1.
     */
    @Test
    public void t_ui_282_abortedByIsStillShown() throws Exception {
        for (String path : RUN_PAGES) {
            HtmlPage page = page("admin", path);
            DomElement row = runRow(page, "ops/abort-x", 1);
            assertNotNull(row, path + ": the aborted run is listed");
            assertFalse(headers(table(row)).contains("Aborted by"), path + ": there is no Aborted by column any more");
            assertTrue(row.asNormalizedText().matches("(?is).*aborted by\\W+u1\\b.*"), path + ": the row must still say"
                    + " it was aborted by u1: " + row.asNormalizedText());
        }
    }

    /**
     * T-UI-283 (#6, #18.1): the Started, Duration, Cause and User cells of {@code ops/batch-x#1} do
     * not wrap (computed {@code white-space} nowrap or pre on the cell, or on every element holding
     * its text), so the row stays one line at 1280 px.
     */
    @Test
    public void t_ui_283_timesCausesUsersAndDurationsDoNotWrap() throws Exception {
        for (String path : RUN_PAGES) {
            JenkinsRule.WebClient wc = client("admin", true);
            HtmlPage page = (HtmlPage) wc.getPage(new WebRequest(new URL(j.getURL(), path), HttpMethod.GET));
            DomElement row = runRow(page, "ops/batch-x", 1);
            assertNotNull(row, path + ": the approved run is listed");
            List<String> headers = headers(table(row));
            for (String column : List.of("Cause", "User", "Started", "Duration")) {
                int index = headers.indexOf(column);
                assertTrue(index >= 0, path + ": the table has a " + column + " column: " + headers);
                DomElement cell = cells(row).get(index);
                assertTrue(noWrap(page, cell), path + ": the " + column + " cell must not wrap: " + cell.asXml());
            }
        }
    }

    /**
     * T-UI-284 (#6, note 362 (3)): the Incidents list and History > Incidents use the same Run cell:
     * no separate Job or Result column; the Run cell of {@code ops/fail-x#1} has the status icon with
     * a tooltip naming the failure, the job link and the {@code #1} run link (administrator).
     */
    @Test
    public void t_ui_284_incidentTablesUseTheSameRunCell() throws Exception {
        for (String path : INCIDENT_PAGES) {
            HtmlPage page = page("admin", path);
            DomElement row = runRow(page, "ops/fail-x", 1);
            assertNotNull(row, path + ": the incident's run is linked for the administrator");
            List<String> headers = headers(table(row));
            assertFalse(headers.contains("Job") || headers.contains("Result"), path + ": no separate Job or Result column: "
                    + headers);
            int index = headers.indexOf("Run");
            assertTrue(index >= 0, path + ": the table has a Run column: " + headers);
            assertRunCellContent(cells(row).get(index), path, "ops/fail-x", 1, "fail");
        }
    }

    // ------------------------------------------------------------------ helpers

    private void assertSevenColumns(String path) throws Exception {
        HtmlPage page = page("admin", path);
        DomElement row = runRow(page, "ops/batch-x", 1);
        assertNotNull(row, path + ": the approved run is listed");
        DomElement table = table(row);
        assertEquals(COLUMNS, headers(table), path + ": the run table's columns");
        for (DomNode n : table.querySelectorAll("tbody > tr")) {
            assertEquals(COLUMNS.size(), cells((DomElement) n).size(), path + ": every row has 7 cells: "
                    + ((DomElement) n).asNormalizedText());
        }
    }

    private void assertRunCell(HtmlPage page, String path, String job, int number, String tooltip, String result) throws Exception {
        DomElement row = runRow(page, job, number);
        assertNotNull(row, path + ": " + job + "#" + number + " is listed with its run link");
        int index = headers(table(row)).indexOf("Run");
        assertEquals(0, index, path + ": Run is the first column: " + headers(table(row)));
        assertRunCellContent(cells(row).get(index), path, job, number, tooltip);
        assertFalse(row.asNormalizedText().contains(result), path + ": the result is shown as an icon, not as the text "
                + result + ": " + row.asNormalizedText());
    }

    private void assertRunCellContent(DomElement cell, String path, String job, int number, String tooltip) throws Exception {
        assertFalse(cell.querySelectorAll("svg, img").isEmpty(), path + ": the Run cell must hold the status icon: " + cell.asXml());
        boolean named = false;
        for (DomNode n : cell.querySelectorAll("*")) {
            DomElement e = (DomElement) n;
            for (String attribute : new String[] {"tooltip", "title", "data-tooltip", "aria-label"}) {
                named |= e.getAttribute(attribute).toLowerCase(Locale.ROOT).contains(tooltip);
            }
        }
        assertTrue(named, path + ": the status icon must have a tooltip naming the result (" + tooltip + "): " + cell.asXml());
        assertTrue(hasLink(cell, jobPath(job)), path + ": the Run cell must link the job " + jobPath(job) + ": " + cell.asXml());
        boolean runLink = false;
        for (DomNode a : cell.querySelectorAll("a")) {
            DomElement anchor = (DomElement) a;
            runLink |= path(anchor).equals(jobPath(job) + number + "/") && anchor.asNormalizedText().trim().equals("#" + number);
        }
        assertTrue(runLink, path + ": the Run cell must link '#" + number + "' to " + jobPath(job) + number + "/: " + cell.asXml());
    }

    private String jobPath(String fullName) throws Exception {
        return new URL(j.getURL(), j.jenkins.getItemByFullName(fullName).getUrl()).getPath();
    }

    private static boolean hasLink(DomElement cell, String targetPath) throws Exception {
        for (DomNode a : cell.querySelectorAll("a")) {
            if (path((DomElement) a).equals(targetPath)) {
                return true;
            }
        }
        return false;
    }

    private static String path(DomElement anchor) throws Exception {
        String href = anchor.getAttribute("href");
        if (href.isEmpty() || href.startsWith("#")) {
            return "";
        }
        return ((HtmlPage) anchor.getPage()).getFullyQualifiedUrl(href).getPath();
    }

    /** The table row holding a link to run {@code number} of {@code job}, or null. */
    private DomElement runRow(HtmlPage page, String job, int number) throws Exception {
        String run = jobPath(job) + number + "/";
        for (DomNode n : page.querySelectorAll("#main-panel table tbody tr")) {
            for (DomNode a : ((DomElement) n).querySelectorAll("a")) {
                if (path((DomElement) a).equals(run)) {
                    return (DomElement) n;
                }
            }
        }
        return null;
    }

    private static DomElement rowWithText(HtmlPage page, String text) {
        for (DomNode n : page.querySelectorAll("#main-panel table tbody tr")) {
            if (n.asNormalizedText().contains(text)) {
                return (DomElement) n;
            }
        }
        return null;
    }

    private static DomElement table(DomElement row) {
        for (DomNode n = row.getParentNode(); n instanceof DomElement e; n = n.getParentNode()) {
            if ("table".equals(e.getTagName())) {
                return e;
            }
        }
        throw new AssertionError("fixture: a row outside a table");
    }

    private static List<String> headers(DomElement table) {
        List<String> out = new ArrayList<>();
        for (DomNode th : table.querySelectorAll("thead th")) {
            out.add(th.asNormalizedText().trim());
        }
        return out;
    }

    private static List<DomElement> cells(DomElement row) {
        List<DomElement> out = new ArrayList<>();
        for (DomElement child : row.getChildElements()) {
            if ("td".equals(child.getTagName()) || "th".equals(child.getTagName())) {
                out.add(child);
            }
        }
        return out;
    }

    private static String textOutsideDetails(DomNode node) {
        StringBuilder out = new StringBuilder();
        for (DomNode child : node.getChildren()) {
            if (child instanceof DomElement e && "details".equals(e.getTagName())) {
                continue;
            }
            if (child instanceof DomText t) {
                out.append(t.getData()).append(' ');
            } else {
                out.append(textOutsideDetails(child));
            }
        }
        return out.toString();
    }

    /** The cell does not wrap: nowrap/pre on the cell, or on an element around every non-blank text in it. */
    private static boolean noWrap(HtmlPage page, DomElement cell) {
        if (isNoWrap(page, cell)) {
            return true;
        }
        boolean sawText = false;
        for (DomNode n : cell.getDescendants()) {
            if (n instanceof DomText t && !t.getData().isBlank()) {
                sawText = true;
                boolean covered = false;
                for (DomNode p = t.getParentNode(); p != null && p != cell && !covered; p = p.getParentNode()) {
                    covered = p instanceof DomElement e && isNoWrap(page, e);
                }
                if (!covered) {
                    return false;
                }
            }
        }
        return sawText;
    }

    private static boolean isNoWrap(HtmlPage page, DomElement element) {
        String ws = page.getEnclosingWindow().getComputedStyle(element, null).getStyleAttribute("white-space");
        return "nowrap".equals(ws) || "pre".equals(ws);
    }

    private HtmlPage page(String user, String path) throws Exception {
        Page answer = get(user, path);
        assertEquals(200, answer.getWebResponse().getStatusCode(), user + " GET " + path);
        return (HtmlPage) answer;
    }

    private Page get(String user, String path) throws Exception {
        return client(user, false).getPage(new WebRequest(new URL(j.getURL(), path), HttpMethod.GET));
    }

    private JenkinsRule.WebClient client(String user, boolean javaScript) throws Exception {
        JenkinsRule.WebClient wc = j.createWebClient().withThrowExceptionOnFailingStatusCode(false).login(user);
        wc.getOptions().setJavaScriptEnabled(javaScript);
        wc.getOptions().setThrowExceptionOnScriptError(false);
        return wc;
    }

    private static ACLContext as(String user) {
        return ACL.as2(User.getById(user, true).impersonate2());
    }

    private static String excerpt(HtmlPage page) {
        String text = page.asNormalizedText();
        return text.length() > 1500 ? text.substring(0, 1500) + "..." : text;
    }
}
