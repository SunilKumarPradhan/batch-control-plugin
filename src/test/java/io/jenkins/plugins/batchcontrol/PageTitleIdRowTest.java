package io.jenkins.plugins.batchcontrol;

import com.cloudbees.hudson.plugins.folder.Folder;
import hudson.model.FreeStyleProject;
import hudson.model.Item;
import hudson.model.User;
import hudson.security.ACL;
import hudson.security.ACLContext;
import io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration;
import io.jenkins.plugins.batchcontrol.config.BatchControlJobProperty;
import io.jenkins.plugins.batchcontrol.model.ActivationRequest;
import io.jenkins.plugins.batchcontrol.model.GrantAction;
import io.jenkins.plugins.batchcontrol.model.GrantRequest;
import io.jenkins.plugins.batchcontrol.model.GrantScope;
import io.jenkins.plugins.batchcontrol.model.RunRequest;
import io.jenkins.plugins.batchcontrol.policy.ActivationService;
import io.jenkins.plugins.batchcontrol.policy.GrantRequestService;
import io.jenkins.plugins.batchcontrol.policy.RunRequestService;
import io.jenkins.plugins.batchcontrol.security.BatchControlPermissions;
import java.net.URL;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.Callable;
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
 * Wave D, group D1, issue #18 item 4 (matrix rows T-UI-230..233, note 360): the detail page of a
 * run request, a permission window (grant) request and an activation request is titled with what
 * the request is about, not with its 36-character id. The page's {@code <title>}, the app bar
 * heading and the last breadcrumb read {@code Run request: <job full name>},
 * {@code Grant request: <scope>} and {@code Activation request: <job>}; the summary table gets an
 * {@code ID} row that shows the full id with core's copy button ({@code l:copyButton}, rendered as
 * a {@code button} whose class list holds {@code jenkins-copy-button} and whose {@code text}
 * attribute is the text it copies). The item name is escaped.
 *
 * <p>Viewers: the requester u1 and the designated approver a1 (each sees the request, SPEC 5/8).
 * Guard in every row: a user who may not see the request gets no page that names it (unchanged
 * P-09 behaviour).
 *
 * <p>Written from the Wave D contract (D1, frozen 2026-10-10), issue #18 and pages rendered on
 * origin/main (d80e5fe); no src/main knowledge.
 */
@WithJenkins
public class PageTitleIdRowTest {

    private static final String FOLDER = "ops";
    private static final String RUN_JOB = FOLDER + "/batch-x";
    private static final String ACTIVATE_JOB = FOLDER + "/act-x";
    private static final String HOLD_JOB = FOLDER + "/hold-x";
    /** Allowed by core's name check (which refuses ?*&#47;\%!@#$^&|<>[]:;), so it reaches every attribute. */
    private static final String ODD_NAME = "q\"x'y{z}";

    private JenkinsRule j;
    private Folder folder;

    @BeforeEach
    public void setUp(JenkinsRule rule) throws Exception {
        this.j = rule;
        j.jenkins.setSecurityRealm(j.createDummySecurityRealm());
        j.jenkins.setAuthorizationStrategy(new MockAuthorizationStrategy()
                .grant(Jenkins.ADMINISTER).everywhere().to("admin")
                .grant(Jenkins.READ, Item.READ, Item.BUILD, BatchControlPermissions.REQUEST,
                        BatchControlPermissions.REQUEST_GRANT).everywhere().to("u1")
                .grant(Jenkins.READ, Item.READ, BatchControlPermissions.APPROVE).everywhere().to("a1")
                // reads every item, holds no Batch Control permission: may not see the requests
                .grant(Jenkins.READ, Item.READ).everywhere().to("o1"));
        BatchControlGlobalConfiguration cfg = BatchControlGlobalConfiguration.get();
        cfg.setChangeControlEnabled(true);
        cfg.setApprovers(Arrays.asList("a1"));
        cfg.save();
        folder = j.jenkins.createProject(Folder.class, FOLDER);
        // created before run control is switched on, so it starts activated and can be held
        folder.createProject(FreeStyleProject.class, "hold-x");
        cfg.setRunControlEnabled(true);
        cfg.save();
    }

    /**
     * T-UI-230 (#18.4): the run request page's title, app bar heading and last breadcrumb read
     * {@code Run request: ops/batch-x}; the id is in none of them; the summary table has an ID row
     * with the full id and core's copy button carrying the id. Guard: o1 gets no page naming it.
     */
    @Test
    public void t_ui_230_runRequestPageIsTitledWithTheJobAndShowsTheIdRow() throws Exception {
        FreeStyleProject job = folder.createProject(FreeStyleProject.class, "batch-x");
        BatchControlFixtures.setBatchControl(job, new BatchControlJobProperty(true));
        RunRequest request = as("u1", () -> RunRequestService.get().create(job, new LinkedHashMap<>(),
                "month-end close", "a1"));
        String path = "batch-control/requests/" + request.getId() + "/";

        assertHiddenFrom("o1", path, "Run request: " + RUN_JOB);
        for (String viewer : List.of("u1", "a1")) {
            assertTitledPage(viewer, path, "Run request: " + RUN_JOB, request.getId());
        }
    }

    /**
     * T-UI-231 (#18.4, same pattern): the permission window request page reads
     * {@code Grant request: ops/batch-x} (the scope's full name) with the ID row and copy button.
     */
    @Test
    public void t_ui_231_grantRequestPageIsTitledWithTheScopeAndShowsTheIdRow() throws Exception {
        folder.createProject(FreeStyleProject.class, "batch-x");
        GrantRequest request = as("u1", () -> GrantRequestService.get().create(
                new GrantScope(GrantScope.Type.ITEM, RUN_JOB), List.of(GrantAction.CONFIGURE), 30,
                "fix the schedule", "a1"));
        String path = "batch-control/grants/" + request.getId() + "/";

        assertHiddenFrom("o1", path, "Grant request: " + RUN_JOB);
        for (String viewer : List.of("u1", "a1")) {
            assertTitledPage(viewer, path, "Grant request: " + RUN_JOB, request.getId());
        }
    }

    /**
     * T-UI-232 (#18.4, same pattern): an ACTIVATE request page reads
     * {@code Activation request: ops/act-x} with the ID row and copy button. A HOLD request page is
     * titled after its job too ({@code Activation request: ops/hold-x} or
     * {@code Hold request: ops/hold-x}; the contract names only the first) and carries the ID row.
     */
    @Test
    public void t_ui_232_activationRequestPageIsTitledWithTheJobAndShowsTheIdRow() throws Exception {
        FreeStyleProject act = folder.createProject(FreeStyleProject.class, "act-x");
        FreeStyleProject hold = (FreeStyleProject) j.jenkins.getItemByFullName(HOLD_JOB);
        ActivationRequest activate = as("u1", () -> ActivationService.get().create(act,
                ActivationRequest.Action.ACTIVATE, "bring it into service", List.of("a1")));
        ActivationRequest held = as("u1", () -> ActivationService.get().create(hold,
                ActivationRequest.Action.HOLD, "take it out of service", List.of("a1")));
        String activatePath = "batch-control/activations/" + activate.getId() + "/";
        String holdPath = "batch-control/activations/" + held.getId() + "/";

        assertHiddenFrom("o1", activatePath, "Activation request: " + ACTIVATE_JOB);
        for (String viewer : List.of("u1", "a1")) {
            assertTitledPage(viewer, activatePath, "Activation request: " + ACTIVATE_JOB, activate.getId());

            HtmlPage page = page(viewer, holdPath);
            for (String shown : titles(page)) {
                assertFalse(shown.contains(held.getId()), viewer + ": the HOLD request's title must not be its id: " + shown);
                String lower = shown.toLowerCase(Locale.ROOT);
                assertTrue((lower.startsWith("activation request: ") || lower.startsWith("hold request: "))
                        && shown.endsWith(": " + HOLD_JOB), viewer + ": the HOLD request page must be titled"
                        + " 'Activation request: " + HOLD_JOB + "' (or 'Hold request: ...'), was '" + shown + "'");
            }
            assertIdRow(viewer, page, held.getId());
        }
    }

    /**
     * T-UI-233 (#18.4, escaping): with a job and a window scope named {@code ops/q"x'y{z}} the
     * title, heading and last breadcrumb (text and tooltip attribute) read the name exactly, so
     * it was escaped in text and in attributes; the ID row still carries the id.
     */
    @Test
    public void t_ui_233_titlesEscapeTheItemName() throws Exception {
        FreeStyleProject job = folder.createProject(FreeStyleProject.class, ODD_NAME);
        assertEquals(FOLDER + "/" + ODD_NAME, job.getFullName(), "fixture: core accepts the name");
        BatchControlFixtures.setBatchControl(job, new BatchControlJobProperty(true));
        RunRequest run = as("u1", () -> RunRequestService.get().create(job, new LinkedHashMap<>(),
                "odd name", "a1"));
        GrantRequest grant = as("u1", () -> GrantRequestService.get().create(
                new GrantScope(GrantScope.Type.ITEM, job.getFullName()), List.of(GrantAction.CONFIGURE), 30,
                "odd name", "a1"));

        assertTitledPage("a1", "batch-control/requests/" + run.getId() + "/",
                "Run request: " + job.getFullName(), run.getId());
        assertTitledPage("a1", "batch-control/grants/" + grant.getId() + "/",
                "Grant request: " + job.getFullName(), grant.getId());
    }

    // ------------------------------------------------------------------ helpers

    /** The page title (without core's " - Jenkins" suffix), the app bar heading and the last breadcrumb. */
    private static List<String> titles(HtmlPage page) {
        String title = page.getTitleText() == null ? "" : page.getTitleText().trim();
        if (title.endsWith(" - Jenkins")) {
            title = title.substring(0, title.length() - " - Jenkins".length());
        }
        DomNode heading = page.querySelector("#main-panel h1");
        assertNotNull(heading, "the page must have an app bar heading: " + excerpt(page));
        List<DomElement> crumbs = crumbs(page);
        assertFalse(crumbs.isEmpty(), "the page must render breadcrumbs");
        DomElement last = crumbs.get(crumbs.size() - 1);
        return List.of(title, heading.asNormalizedText().trim(), last.asNormalizedText().trim());
    }

    private void assertTitledPage(String viewer, String path, String expected, String id) throws Exception {
        HtmlPage page = page(viewer, path);
        List<String> shown = titles(page);
        assertEquals(expected, shown.get(0), viewer + " " + path + ": the <title> must read the request's subject");
        assertEquals(expected, shown.get(1), viewer + " " + path + ": the app bar heading must read the request's subject");
        assertEquals(expected, shown.get(2), viewer + " " + path + ": the last breadcrumb must read the request's subject");
        for (String s : shown) {
            assertFalse(s.contains(id), viewer + " " + path + ": the title must not be the id: " + s);
        }
        List<DomElement> crumbs = crumbs(page);
        for (DomNode n : crumbs.get(crumbs.size() - 1).querySelectorAll("[tooltip]")) {
            assertEquals(expected, ((DomElement) n).getAttribute("tooltip"),
                    viewer + " " + path + ": the breadcrumb tooltip must carry the escaped subject unchanged");
        }
        assertIdRow(viewer, page, id);
    }

    /** The summary table row headed "ID" shows the full id and core's copy button copying it. */
    private static void assertIdRow(String viewer, HtmlPage page, String id) {
        DomElement row = null;
        for (DomNode th : page.querySelectorAll("#main-panel table tr > th")) {
            if ("ID".equals(th.asNormalizedText().trim())) {
                row = (DomElement) th.getParentNode();
                break;
            }
        }
        assertNotNull(row, viewer + ": the summary table must have a row headed 'ID': " + excerpt(page));
        DomNode cell = row.querySelector("td");
        assertNotNull(cell, viewer + ": the ID row must have a value cell");
        assertTrue(cell.getTextContent().contains(id), viewer + ": the ID row must show the full id " + id + ": "
                + cell.asXml());
        boolean copies = false;
        for (DomNode b : cell.querySelectorAll("button")) {
            DomElement button = (DomElement) b;
            if ((" " + button.getAttribute("class") + " ").contains(" jenkins-copy-button ")
                    && id.equals(button.getAttribute("text"))) {
                copies = true;
            }
        }
        assertTrue(copies, viewer + ": the ID row must carry core's copy button with text=\"" + id + "\": " + cell.asXml());
    }

    /** A user who may not see the request gets an error status, and the answer does not name the subject. */
    private void assertHiddenFrom(String user, String path, String subject) throws Exception {
        Page answer = client(user).getPage(new WebRequest(new URL(j.getURL(), path), HttpMethod.GET));
        assertTrue(answer.getWebResponse().getStatusCode() >= 400, "guard: " + user + " may not open " + path
                + ", got HTTP " + answer.getWebResponse().getStatusCode());
        assertFalse(answer.getWebResponse().getContentAsString().contains(subject),
                "guard: the refusal must not name the request's subject");
    }

    private static List<DomElement> crumbs(HtmlPage page) {
        return page.getByXPath("//li[contains(concat(' ', normalize-space(@class), ' '),"
                + " ' jenkins-breadcrumbs__list-item ')]");
    }

    private HtmlPage page(String user, String path) throws Exception {
        Page answer = client(user).getPage(new WebRequest(new URL(j.getURL(), path), HttpMethod.GET));
        assertEquals(200, answer.getWebResponse().getStatusCode(), user + " GET " + path);
        assertTrue(answer instanceof HtmlPage, user + " GET " + path + " must be an HTML page");
        return (HtmlPage) answer;
    }

    private JenkinsRule.WebClient client(String user) throws Exception {
        JenkinsRule.WebClient wc = j.createWebClient().withThrowExceptionOnFailingStatusCode(false).login(user);
        wc.getOptions().setJavaScriptEnabled(false);
        return wc;
    }

    private static <V> V as(String user, Callable<V> body) throws Exception {
        try (ACLContext ignored = ACL.as2(User.getById(user, true).impersonate2())) {
            return body.call();
        }
    }

    private static String excerpt(HtmlPage page) {
        String text = page.asNormalizedText();
        return text.length() > 1500 ? text.substring(0, 1500) + "..." : text;
    }
}
