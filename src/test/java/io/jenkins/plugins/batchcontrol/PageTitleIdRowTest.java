package io.jenkins.plugins.batchcontrol;

import com.cloudbees.hudson.plugins.folder.Folder;
import hudson.model.FreeStyleProject;
import hudson.model.Item;
import hudson.model.TopLevelItem;
import hudson.model.User;
import hudson.security.ACL;
import hudson.security.ACLContext;
import hudson.security.Permission;
import io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration;
import io.jenkins.plugins.batchcontrol.config.BatchControlJobProperty;
import io.jenkins.plugins.batchcontrol.model.ActivationRequest;
import io.jenkins.plugins.batchcontrol.model.Grant;
import io.jenkins.plugins.batchcontrol.model.GrantAction;
import io.jenkins.plugins.batchcontrol.model.GrantRequest;
import io.jenkins.plugins.batchcontrol.model.GrantScope;
import io.jenkins.plugins.batchcontrol.model.RunRequest;
import io.jenkins.plugins.batchcontrol.policy.ActivationService;
import io.jenkins.plugins.batchcontrol.policy.GrantRequestService;
import io.jenkins.plugins.batchcontrol.policy.RunRequestService;
import io.jenkins.plugins.batchcontrol.security.BatchControlMatrixAuthorizationStrategy;
import io.jenkins.plugins.batchcontrol.security.BatchControlPermissions;
import io.jenkins.plugins.batchcontrol.security.GrantService;
import java.net.URL;
import java.util.Arrays;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.Callable;
import jenkins.model.Jenkins;
import org.htmlunit.HttpMethod;
import org.htmlunit.Page;
import org.htmlunit.WebRequest;
import org.htmlunit.WebResponse;
import org.htmlunit.html.DomAttr;
import org.htmlunit.html.DomElement;
import org.htmlunit.html.DomNode;
import org.htmlunit.html.HtmlPage;
import org.htmlunit.util.NameValuePair;
import org.jenkinsci.plugins.matrixauth.PermissionEntry;
import org.jenkinsci.plugins.matrixauth.inheritance.NonInheritingStrategy;
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
 * <p>Rows T-UI-236..238 (note 360 (7), (8)): the grant request page of a window whose item was
 * renamed or moved. SPEC 8, D-74: "a window applies to its item, not to a name ... the window
 * follows it"; D-75: "the grant pages ... show the item's current full name only to a viewer with
 * Item/Read on it; anyone else sees the approved name with a fixed note that the item was moved and
 * its new location is not visible to them. Administrators see the current name." The title is part
 * of the grant page, so it names the item's current full name for a viewer who may read the item
 * and the approved name for anyone else. The fixture of those rows is the one of the D-75 rows
 * (T-SEC-96, T-SEC-114; WindowFollowedNameVisibilityTest): the Batch Control matrix strategy and
 * the folder {@code vault-q9}, which blocks inheritance and gives Item/Read to admin only.
 *
 * <p>The breadcrumb's {@code tooltip} (note 360 (10)): in the pages these tests fetch (JavaScript
 * off) core 2.568.3 renders the attribute only on a last breadcrumb longer than 26 characters. So
 * the comparison "the tooltip carries the same text" happens for the ACTIVATE page of T-UI-232 and
 * the grant page of T-UI-233 (and, by the same length, for the administrator's moved window of
 * T-UI-236), and compares nothing for the shorter titles of T-UI-230, T-UI-231 and the run page
 * of T-UI-233. A tooltip that a browser shows on a breadcrumb it cuts is checked in e2e (unit
 * r27-titles-revert), not here.
 *
 * <p>Written from the Wave D contract (D1, frozen 2026-10-10), issue #18, docs/SPEC.md item 8 and
 * pages rendered on origin/main (d80e5fe); no src/main knowledge.
 */
@WithJenkins
public class PageTitleIdRowTest {

    private static final String FOLDER = "ops";
    private static final String RUN_JOB = FOLDER + "/batch-x";
    private static final String ACTIVATE_JOB = FOLDER + "/act-x";
    private static final String HOLD_JOB = FOLDER + "/hold-x";
    /** Allowed by core's name check (which refuses ?*&#47;\%!@#$^&|<>[]:;), so it reaches every attribute. */
    private static final String ODD_NAME = "q\"x'y{z}";
    /** As in the D-75 rows: a folder that blocks inheritance and gives Item/Read to admin only. */
    private static final String VAULT = "vault-q9";

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
     * title, heading and last breadcrumb read the name exactly, so it was escaped in text; the
     * grant page's breadcrumb carries a {@code tooltip} attribute (its title is longer than 26
     * characters) that reads the same text, so the name was escaped in that attribute; no attribute
     * of either page is cut or split by the name's quotes; the ID row still carries the id. The run
     * page's breadcrumb is shorter and has no tooltip to compare (note 360 (10)).
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

        String runPath = "batch-control/requests/" + run.getId() + "/";
        String grantPath = "batch-control/grants/" + grant.getId() + "/";
        assertTitledPage("a1", runPath, "Run request: " + job.getFullName(), run.getId());
        assertTitledPage("a1", grantPath, "Grant request: " + job.getFullName(), grant.getId());
        assertEquals(1, assertTooltipIfAny("a1", grantPath, page("a1", grantPath), "Grant request: " + job.getFullName()),
                "premise (core 2.568.3 renders a tooltip on a last breadcrumb longer than 26 characters): the grant"
                        + " page's breadcrumb carries one tooltip; without it this row compares no title attribute");
        assertNoAttributeBrokenByTheOddName("a1", runPath, page("a1", runPath));
        assertNoAttributeBrokenByTheOddName("a1", grantPath, page("a1", grantPath));
    }

    /**
     * T-UI-236 (SPEC 8, D-74 and D-75; #18.4): u1 holds an APPROVED CONFIGURE window on
     * {@code ops/batch-x} (approved by a1). After the administrator renames the job to
     * {@code ops/batch-y} the window follows, and for u1 (holder), a1 (approver) and admin, who may
     * read the renamed item, the {@code <title>}, the app bar heading and the last breadcrumb of
     * the grant request page each read exactly {@code Grant request: ops/batch-y}; none names
     * {@code ops/batch-x}. A second rename to {@code ops/batch-z} is followed too. After the
     * administrator moves the job into {@code vault-q9}, the administrator's three read
     * {@code Grant request: vault-q9/batch-z}.
     */
    @Test
    public void t_ui_236_grantTitleFollowsARenamedItemForViewersWhoMayReadIt() throws Exception {
        installWindowFixture();
        String[] ids = openConfigureWindow("batch-x");
        String path = "batch-control/grants/" + ids[0] + "/";
        assertTitles("u1", path, "Grant request: " + RUN_JOB, "guard: before the rename");

        renameAsAdmin(RUN_JOB, "batch-y", ids[1]);
        for (String viewer : List.of("u1", "a1", "admin")) {
            assertTrue(can(viewer, FOLDER + "/batch-y", Item.READ), "premise: " + viewer + " may read ops/batch-y");
            assertTitles(viewer, path, "Grant request: " + FOLDER + "/batch-y",
                    "SPEC 8 (D-74, D-75): the window followed its item to ops/batch-y, which " + viewer + " may read",
                    RUN_JOB);
        }

        renameAsAdmin(FOLDER + "/batch-y", "batch-z", ids[1]);
        for (String viewer : List.of("u1", "a1", "admin")) {
            assertTitles(viewer, path, "Grant request: " + FOLDER + "/batch-z",
                    "SPEC 8 (D-74, D-75): the window followed its item a second time, to ops/batch-z, which "
                            + viewer + " may read", RUN_JOB, FOLDER + "/batch-y");
        }

        moveIntoVaultAsAdmin(FOLDER + "/batch-z", ids[1]);
        assertTitles("admin", path, "Grant request: " + VAULT + "/batch-z",
                "SPEC 8 (D-75): administrators see the current name of a moved item", FOLDER + "/batch-");
    }

    /**
     * T-UI-237 (SPEC 8, D-75; #18.4; negative twin of T-UI-236): the title never shows a followed
     * name to a viewer who may open the grant request page but may not read the item. u1's APPROVED
     * CONFIGURE window on {@code ops/batch-x}; n1 holds Overall/Read and BatchControl/Manage and
     * Item/Read on nothing; m1 holds Overall/Read, Item/Read and BatchControl/Manage (as T-SEC-114).
     * After the administrator renames the job to {@code ops/batch-y}, n1's three titles read
     * exactly {@code Grant request: ops/batch-x} (the approved name) and n1's page holds
     * {@code batch-y} nowhere in its HTML. After the administrator moves the job into
     * {@code vault-q9} (as T-SEC-96), u1, a1, m1 and n1, none of whom may read it there, each read
     * exactly {@code Grant request: ops/batch-x}, and no page holds {@code vault-q9} in its HTML.
     */
    @Test
    public void t_ui_237_grantTitleKeepsTheApprovedNameForAViewerWhoMayNotReadTheItem() throws Exception {
        BatchControlMatrixAuthorizationStrategy strategy = installWindowFixture();
        strategy.add(Jenkins.READ, PermissionEntry.user("n1"));
        strategy.add(BatchControlPermissions.MANAGE, PermissionEntry.user("n1"));
        strategy.add(Jenkins.READ, PermissionEntry.user("m1"));
        strategy.add(Item.READ, PermissionEntry.user("m1"));
        strategy.add(BatchControlPermissions.MANAGE, PermissionEntry.user("m1"));
        String[] ids = openConfigureWindow("batch-x");
        String path = "batch-control/grants/" + ids[0] + "/";
        String approved = "Grant request: " + RUN_JOB;

        renameAsAdmin(RUN_JOB, "batch-y", ids[1]);
        assertFalse(can("n1", FOLDER + "/batch-y", Item.READ), "premise: n1 may not read ops/batch-y");
        assertTitles("n1", path, approved, "SPEC 8 (D-75): n1 may not read the renamed item and sees the approved"
                + " name", FOLDER + "/batch-y");
        assertNotInHtml("n1", path, "batch-y");

        moveIntoVaultAsAdmin(FOLDER + "/batch-y", ids[1]);
        for (String viewer : List.of("u1", "a1", "m1", "n1")) {
            assertFalse(can(viewer, VAULT + "/batch-y", Item.READ), "premise: " + viewer + " may not read "
                    + VAULT + "/batch-y");
            assertTitles(viewer, path, approved, "SPEC 8 (D-75): " + viewer + " may not read the moved item and"
                    + " sees the approved name", VAULT);
            assertNotInHtml(viewer, path, VAULT);
        }
        assertNotInHtml("n1", path, "batch-y");
    }

    /**
     * T-UI-238 (guard; SPEC 8 "approval is refused when no item exists at that name any more"): a
     * PENDING request has no window, so nothing follows the item. u1's request for a CONFIGURE
     * window on {@code ops/batch-x}, never approved; after the administrator renames the job to
     * {@code ops/batch-y} the request page still reads {@code Grant request: ops/batch-x} for u1
     * and a1, the name the request was made for, and none of the three names {@code ops/batch-y}.
     */
    @Test
    public void t_ui_238_pendingGrantRequestKeepsTheNameItWasRequestedFor() throws Exception {
        folder.createProject(FreeStyleProject.class, "batch-x");
        GrantRequest request = as("u1", () -> GrantRequestService.get().create(
                new GrantScope(GrantScope.Type.ITEM, RUN_JOB), List.of(GrantAction.CONFIGURE), 30,
                "fix the schedule", "a1"));
        String path = "batch-control/grants/" + request.getId() + "/";

        renameAsAdmin(RUN_JOB, "batch-y", null);
        assertTrue(GrantService.get().listActive().stream().noneMatch(g -> "u1".equals(g.getUser())),
                "premise: the request was never approved, u1 holds no window");
        for (String viewer : List.of("u1", "a1")) {
            assertTitles(viewer, path, "Grant request: " + RUN_JOB, "guard: a pending request names the item it was"
                    + " made for; no window exists that could follow the rename", FOLDER + "/batch-y");
        }
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
        assertTooltipIfAny(viewer, path, page, expected);
        assertIdRow(viewer, page, id);
    }

    /**
     * Compares the last breadcrumb's {@code tooltip} with the title, where there is one, and
     * returns how many were compared. This bites only when a tooltip is present: in a page fetched
     * with JavaScript off, core 2.568.3 renders one only on a last breadcrumb longer than 26
     * characters, so for a shorter title the loop compares nothing (note 360 (10)).
     */
    private static int assertTooltipIfAny(String viewer, String path, HtmlPage page, String expected) {
        List<DomElement> crumbs = crumbs(page);
        int compared = 0;
        for (DomNode n : crumbs.get(crumbs.size() - 1).querySelectorAll("[tooltip]")) {
            assertEquals(expected, ((DomElement) n).getAttribute("tooltip"),
                    viewer + " " + path + ": the breadcrumb tooltip must carry the subject unchanged");
            compared++;
        }
        return compared;
    }

    /**
     * The three titles of {@code path} as {@code viewer} sees them each read exactly
     * {@code expected} and none contains any of {@code absent}.
     */
    private void assertTitles(String viewer, String path, String expected, String what, String... absent)
            throws Exception {
        HtmlPage page = page(viewer, path);
        List<String> shown = titles(page);
        String[] part = {"<title>", "app bar heading", "last breadcrumb"};
        for (int i = 0; i < part.length; i++) {
            assertEquals(expected, shown.get(i), what + ": " + viewer + "'s " + part[i] + " of " + path);
            for (String name : absent) {
                assertFalse(shown.get(i).contains(name), what + ": " + viewer + "'s " + part[i] + " of " + path
                        + " must not name " + name + ": " + shown.get(i));
            }
        }
        assertTooltipIfAny(viewer, path, page, expected);
    }

    /** The answer to {@code viewer}'s GET of {@code path} holds {@code name} nowhere (text, links, attributes). */
    private void assertNotInHtml(String viewer, String path, String name) throws Exception {
        String raw = page(viewer, path).getWebResponse().getContentAsString();
        int at = raw.indexOf(name);
        assertFalse(at >= 0, "SPEC 8 (D-75): " + viewer + " may not read the item, so " + path + " must not hold "
                + name + " anywhere in its HTML: ..." + (at < 0 ? "" : raw.substring(Math.max(0, at - 200),
                Math.min(raw.length(), at + 200))) + "...");
    }

    /**
     * No attribute of the page was cut or split by the quotes of {@link #ODD_NAME}: an unescaped
     * {@code "} or {@code '} inside an attribute value ends the value early and turns the rest of
     * the name into attribute names. So no attribute name holds a piece of the name, and an
     * attribute value that holds its tail holds the whole name.
     */
    private static void assertNoAttributeBrokenByTheOddName(String viewer, String path, HtmlPage page) {
        for (DomElement e : page.getDomElementDescendants()) {
            for (DomAttr a : e.getAttributesMap().values()) {
                String where = viewer + " " + path + ": <" + e.getTagName() + " " + a.getName() + "=\"" + a.getValue() + "\">";
                assertFalse(a.getName().contains("{z}") || a.getName().contains("x'y") || a.getName().contains("y{z"),
                        where + ": the item name's quote ended an attribute value early");
                if (a.getValue().contains("y{z}") || a.getValue().contains("q\"x")) {
                    assertTrue(a.getValue().contains(ODD_NAME), where + ": the attribute holds only a piece of the"
                            + " item name " + ODD_NAME);
                }
            }
        }
    }

    // ------------------------------------------------------------------ fixture of T-UI-236, 237

    /**
     * The fixture of the D-75 rows (T-SEC-96, WindowFollowedNameVisibilityTest): the Batch Control
     * matrix strategy with admin (Overall/Administer), u1 (Overall/Read, Item/Read, RequestGrant)
     * and a1 (Overall/Read, Item/Read, Approve); the folder {@code vault-q9}, whose authorization
     * property blocks inheritance and gives Item/Read to admin only.
     */
    private BatchControlMatrixAuthorizationStrategy installWindowFixture() throws Exception {
        BatchControlMatrixAuthorizationStrategy strategy = new BatchControlMatrixAuthorizationStrategy();
        strategy.add(Jenkins.ADMINISTER, PermissionEntry.user("admin"));
        for (String userId : new String[] {"u1", "a1"}) {
            strategy.add(Jenkins.READ, PermissionEntry.user(userId));
            strategy.add(Item.READ, PermissionEntry.user(userId));
        }
        strategy.add(BatchControlPermissions.REQUEST_GRANT, PermissionEntry.user("u1"));
        strategy.add(BatchControlPermissions.APPROVE, PermissionEntry.user("a1"));
        j.jenkins.setAuthorizationStrategy(strategy);

        Folder vault = j.jenkins.createProject(Folder.class, VAULT);
        com.cloudbees.hudson.plugins.folder.properties.AuthorizationMatrixProperty adminOnly =
                new com.cloudbees.hudson.plugins.folder.properties.AuthorizationMatrixProperty(
                        new HashMap<Permission, Set<String>>());
        adminOnly.setInheritanceStrategy(new NonInheritingStrategy());
        adminOnly.add(Item.READ, PermissionEntry.user("admin"));
        vault.addProperty(adminOnly);
        for (String userId : new String[] {"u1", "a1"}) {
            assertFalse(can(userId, VAULT, Item.READ), "fixture: " + userId + " may not read " + VAULT);
        }
        return strategy;
    }

    /**
     * Creates {@code ops/<name>}; u1 requests a 30-minute CONFIGURE window on it through the form
     * and a1 approves. Returns the request id and the window's id.
     */
    private String[] openConfigureWindow(String name) throws Exception {
        folder.createProject(FreeStyleProject.class, name);
        String fullName = FOLDER + "/" + name;
        String requestId = ApproverFormFixtures.submitGrantOk(j, "u1", fullName, List.of("CONFIGURE"), 30,
                "quarterly maintenance", null, "a1");
        ApproverFormFixtures.assertSuccess(ApproverFormFixtures.decideGrant(j, "a1", requestId, "approve", "ok"),
                "fixture: approval by a1");
        return new String[] {requestId, WindowStateFixtures.windowId("u1", fullName)};
    }

    /**
     * The administrator renames {@code fullName} (core's {@code confirmRename}); with a window id,
     * premise (D-74): that window is still active and names the item's new full name.
     */
    private void renameAsAdmin(String fullName, String newName, String windowId) throws Exception {
        assertRedirect(ApproverFormFixtures.post(j, "admin", itemUrl(fullName) + "confirmRename",
                List.of(new NameValuePair("newName", newName))), "the administrator renames " + fullName + " to " + newName);
        String renamed = fullName.substring(0, fullName.lastIndexOf('/') + 1) + newName;
        assertNotNull(j.jenkins.getItemByFullName(renamed), "premise: " + fullName + " is now " + renamed);
        assertFollowed(windowId, renamed);
    }

    /** The administrator moves {@code fullName} into {@code vault-q9} (folders plugin {@code move/move}). */
    private void moveIntoVaultAsAdmin(String fullName, String windowId) throws Exception {
        assertRedirect(ApproverFormFixtures.post(j, "admin", itemUrl(fullName) + "move/move",
                List.of(new NameValuePair("destination", "/" + VAULT))), "the administrator moves " + fullName
                + " into " + VAULT);
        String moved = VAULT + fullName.substring(fullName.lastIndexOf('/'));
        assertNotNull(j.jenkins.getItemByFullName(moved), "premise: " + fullName + " is now " + moved);
        assertFollowed(windowId, moved);
    }

    private static void assertFollowed(String windowId, String fullName) {
        if (windowId == null) {
            return;
        }
        Grant window = WindowStateFixtures.active(windowId);
        assertNotNull(window, "premise (D-74): the window is still active after its item became " + fullName);
        assertEquals(fullName, window.getScope().getFullName(), "premise (D-74): the window follows its item");
    }

    private static String itemUrl(String fullName) {
        return "job/" + fullName.replace("/", "/job/") + "/";
    }

    private static void assertRedirect(WebResponse response, String what) {
        int code = response.getStatusCode();
        assertTrue(code >= 300 && code < 400, what + " must go through (redirect), got HTTP " + code);
    }

    private boolean can(String userId, String fullName, Permission permission) {
        TopLevelItem item = j.jenkins.getItemByFullName(fullName, TopLevelItem.class);
        assertNotNull(item, "fixture: the item " + fullName + " exists");
        return item.getACL().hasPermission2(User.getById(userId, true).impersonate2(), permission);
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
