package io.jenkins.plugins.batchcontrol;

import hudson.model.User;
import hudson.security.ACL;
import hudson.security.ACLContext;
import hudson.security.HudsonPrivateSecurityRealm;
import io.jenkins.plugins.batchcontrol.model.GrantAction;
import io.jenkins.plugins.batchcontrol.security.BatchControlMatrixAuthorizationStrategy;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.htmlunit.html.DomElement;
import org.htmlunit.html.DomNode;
import org.htmlunit.html.HtmlPage;
import org.jenkinsci.plugins.workflow.cps.CpsFlowDefinition;
import org.jenkinsci.plugins.workflow.cps.replay.ReplayAction;
import org.jenkinsci.plugins.workflow.job.WorkflowJob;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.RegisterExtension;
import org.jvnet.hudson.test.JenkinsRule;
import org.jvnet.hudson.test.junit.jupiter.JenkinsSessionExtension;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #1 (security-31 follow-ups): the Manage Jenkins review list of items changed under a permission window
 * after a restart. Matrix rows T-02-190 and T-02-191 (notes 354 and 355).
 *
 * <p>Basis: SPEC item 2, the D-58b and D-58c lines ("the review surfaces list such runs"; "Guarding follows
 * renames and moves"; the state ends only through the explicit "Mark as reviewed" action); DECISIONS D-58a
 * (1) "Coverage and the 'changed under a grant' state follow renames and moves" and (4) "An administrator can
 * see which items are in the 'changed under a grant' state"; SPEC 6 usability (the list must not keep an
 * entry that no action on it can clear); docs/reports/security-31.md S-31-03; the #1 contract (frozen
 * 2026-10-10).
 *
 * <p>The list is read from Manage Jenkins as the administrator, in {@code div[data-monitor-id=
 * batch-control-strategy]}: one list item per listed item with its full name in {@code code}, the marked runs
 * as links in a nested list (the screen of T-GAP-319 .. 321). bob's CONFIGURE window on a Pipeline job lets
 * him replay #1 as the marked #2 (D-58b/D-58c), which lists the job and its run #2. Builds run as a fixed
 * low-privilege account (Authorize Project). The realm is Jenkins' own user database, so the accounts
 * survive the restart.
 *
 * <p>Written from docs/SPEC.md, docs/DECISIONS.md D-58a .. D-58c, docs/reports/security-31.md and the #1
 * contract only (no src/main knowledge).
 */
public class MarkedRunRestartFollowUpTest {

    @RegisterExtension
    final JenkinsSessionExtension session = new JenkinsSessionExtension();

    /**
     * T-02-190 (#1.3, S-31-03, D-58a (1), D-58c): Pipeline jobs {@code J} and {@code L}, each with a run #2
     * that bob replayed under his window. The administrator renames {@code J} to {@code K}; before the
     * restart the list shows {@code K} with the run {@code job/K/2/} (premise: in-session renames are
     * followed). After a restart the list still shows {@code K} with {@code job/K/2/}, and no run under
     * {@code job/J/}. On main the run is gone from {@code K}'s row after the restart (the index is rebuilt
     * under the old name). Guard: {@code L}, not renamed, lists {@code job/L/2/} after the restart.
     */
    @Test
    public void t_02_190_markedRunsAreListedUnderTheCurrentNameAfterARestart() throws Throwable {
        session.then(r -> {
            setUp(r);
            markedPipeline(r, "J");
            markedPipeline(r, "L");
            try (ACLContext ignored = ACL.as2(User.getById("admin", true).impersonate2())) {
                ((WorkflowJob) r.jenkins.getItemByFullName("J")).renameTo("K");
            }
            Map<String, Row> before = monitor(r);
            assertTrue(before.containsKey("K") && runs(before, "K").contains(path(r, "job/K/2/")),
                    "premise: before the restart the renamed job is listed as K with its marked run K#2: " + before);
        });
        session.then(r -> {
            Map<String, Row> after = monitor(r);
            assertTrue(runs(after, "L").contains(path(r, "job/L/2/")), "guard: after the restart L still lists its marked run L#2: " + after);
            assertTrue(after.containsKey("K"), "premise: after the restart the renamed job is still listed as K: " + after);
            assertFalse(after.values().stream().anyMatch(row -> row.runs.stream().anyMatch(run -> run.contains("/job/J/"))),
                    "no run may be listed under the old name J: " + after);
            assertTrue(runs(after, "K").contains(path(r, "job/K/2/")), "#1.3: after a rename and a restart the marked run must be listed"
                    + " under the current name K (job/K/2/): " + after);
        });
    }

    /**
     * T-02-191 (#1.4, S-30-06 = S-31-04, D-58b, SPEC 6 usability): Pipeline jobs {@code gone} and
     * {@code kept}, each with a run bob replayed under his window, are listed. While Jenkins is down the
     * directory of {@code gone} is removed. After the restart the list still names {@code gone} (premise),
     * and its row offers a "Mark as reviewed" control (a POST to {@code markReviewed} for the item
     * {@code gone}), as {@code kept}'s row does (guard). Using it as the administrator succeeds, writes one
     * GUARD_REVIEWED record and removes {@code gone} from the list; {@code kept} stays listed (guard). On main
     * the row of {@code gone} is a bare {@code <code>gone</code>} with no control.
     */
    @Test
    public void t_02_191_staleListedNameCanBeMarkedReviewedFromTheList() throws Throwable {
        session.then(r -> {
            setUp(r);
            markedPipeline(r, "gone");
            markedPipeline(r, "kept");
            Map<String, Row> before = monitor(r);
            assertTrue(before.containsKey("gone") && before.containsKey("kept"), "premise: both jobs are listed: " + before);
        });
        java.nio.file.Path dir = session.getHome().toPath().resolve("jobs/gone");
        assertTrue(java.nio.file.Files.isDirectory(dir), "premise: the job directory is " + dir);
        try (java.util.stream.Stream<java.nio.file.Path> walk = java.nio.file.Files.walk(dir)) {
            walk.sorted(java.util.Comparator.reverseOrder()).forEach(p -> p.toFile().delete());
        }
        session.then(r -> {
            assertTrue(r.jenkins.getItemByFullName("gone") == null, "premise: gone no longer exists");
            Map<String, Row> listed = monitor(r);
            assertTrue(listed.containsKey("gone"), "premise (S-30-06): after the restart the list still names gone: " + listed);
            assertTrue(listed.containsKey("kept") && reviewTarget(listed, "kept") != null,
                    "guard: kept's row offers Mark as reviewed: " + listed);
            String target = reviewTarget(listed, "gone");
            assertNotNull(target, "#1.4: the listed stale name gone must offer a Mark as reviewed control (a POST to markReviewed"
                    + " for gone), like every other row: " + listed);

            int reviews = StrategyFixtures.records(io.jenkins.plugins.batchcontrol.model.ChangeType.GUARD_REVIEWED).size();
            JenkinsRule.WebClient wc = r.createWebClient().withThrowExceptionOnFailingStatusCode(false).login("admin", "admin");
            wc.getOptions().setRedirectEnabled(false);
            org.htmlunit.WebRequest post = new org.htmlunit.WebRequest(new java.net.URL(r.getURL(), target), org.htmlunit.HttpMethod.POST);
            wc.addCrumb(post);
            int code = wc.getPage(post).getWebResponse().getStatusCode();
            assertTrue(code < 400, "using the control must succeed, got " + code);
            assertEquals(reviews + 1, StrategyFixtures.records(io.jenkins.plugins.batchcontrol.model.ChangeType.GUARD_REVIEWED).size(),
                    "the review writes one GUARD_REVIEWED record");
            Map<String, Row> after = monitor(r);
            assertFalse(after.containsKey("gone"), "after the review gone is no longer listed: " + after);
            assertTrue(after.containsKey("kept"), "guard: kept stays listed: " + after);
        });
    }

    // ---------------------------------------------------------------- helpers

    /** The target of the row's review control that names {@code name} as its item, or null. */
    static String reviewTarget(Map<String, Row> listed, String name) {
        Row row = listed.get(name);
        if (row == null) {
            return null;
        }
        for (String target : row.reviewTargets) {
            String query = target.contains("?") ? target.substring(target.indexOf('?') + 1) : "";
            for (String pair : query.split("&")) {
                if (pair.equals("item=" + java.net.URLEncoder.encode(name, java.nio.charset.StandardCharsets.UTF_8))) {
                    return target;
                }
            }
        }
        return null;
    }

    /** One listed item: the paths of its run links and the targets of its review controls. */
    static final class Row {
        final List<String> runs = new ArrayList<>();
        final List<String> reviewTargets = new ArrayList<>();

        @Override
        public String toString() {
            return "runs=" + runs + " review=" + reviewTargets;
        }
    }

    static void setUp(JenkinsRule r) throws Exception {
        HudsonPrivateSecurityRealm realm = new HudsonPrivateSecurityRealm(false, false, null);
        for (String id : new String[] {"admin", "alice", "bob", "carol", "a1", "m1", "c1"}) {
            realm.createAccount(id, id);
        }
        r.jenkins.setSecurityRealm(realm);
        r.jenkins.setAuthorizationStrategy(StrategyFixtures.matrix(new BatchControlMatrixAuthorizationStrategy()));
        r.jenkins.save();
        StrategyFixtures.changeControlOn();
        StrategyFixtures.configureBuildAuthenticator();
    }

    /** Pipeline {@code name} with #1; bob's CONFIGURE window on it; bob replays #1 as the marked #2. */
    static void markedPipeline(JenkinsRule r, String name) throws Exception {
        WorkflowJob p = r.jenkins.createProject(WorkflowJob.class, name);
        p.setDefinition(new CpsFlowDefinition("echo 'hello'", true));
        r.buildAndAssertSuccess(p);
        StrategyFixtures.grant("bob", name, Arrays.asList(GrantAction.CONFIGURE));
        try (ACLContext ignored = ACL.as2(User.getById("bob", true).impersonate2())) {
            p.getBuildByNumber(1).getAction(ReplayAction.class).run("echo 'replayed'", new LinkedHashMap<>());
        }
        r.waitUntilNoActivity();
        assertNotNull(p.getBuildByNumber(2), "fixture: bob's replay ran as " + name + " #2");
    }

    static String path(JenkinsRule r, String relative) throws Exception {
        return new java.net.URL(r.getURL(), relative).getPath();
    }

    static List<String> runs(Map<String, Row> listed, String name) {
        Row row = listed.get(name);
        return row == null ? List.of() : row.runs;
    }

    /**
     * Listed item full name -> its row, as the administrator sees the list. An item is a list item of the
     * monitor's outer list whose name is in a {@code code} element (linked or not); review controls are
     * elements with a {@code data-url} naming {@code markReviewed}, or forms posting to it with an
     * {@code item} field.
     */
    static Map<String, Row> monitor(JenkinsRule r) throws Exception {
        JenkinsRule.WebClient wc = r.createWebClient().withThrowExceptionOnFailingStatusCode(false).login("admin", "admin");
        HtmlPage manage = wc.goTo("manage/");
        assertEquals(200, manage.getWebResponse().getStatusCode(), "Manage Jenkins must render");
        Map<String, Row> out = new LinkedHashMap<>();
        DomNode monitor = manage.querySelector("div[data-monitor-id=batch-control-strategy]");
        if (monitor == null) {
            return out;
        }
        for (DomNode li : monitor.querySelectorAll("li")) {
            DomNode code = null;
            for (DomNode child : li.getChildren()) {
                if (child instanceof DomElement e && "code".equals(e.getTagName())) {
                    code = e;
                } else if (child instanceof DomElement e && "a".equals(e.getTagName()) && e.querySelector("code") != null) {
                    code = e.querySelector("code");
                }
            }
            if (code == null) {
                continue;
            }
            Row row = new Row();
            for (DomNode child : li.getChildren()) {
                if (child instanceof DomElement e && "ul".equals(e.getTagName())) {
                    for (DomElement a : e.getElementsByTagName("a")) {
                        if (a.hasAttribute("href")) {
                            row.runs.add(manage.getFullyQualifiedUrl(a.getAttribute("href")).getPath());
                        }
                    }
                }
            }
            for (DomNode control : li.querySelectorAll("[data-url]")) {
                String url = ((DomElement) control).getAttribute("data-url");
                if (url.contains("markReviewed")) {
                    row.reviewTargets.add(url);
                }
            }
            for (DomNode form : li.querySelectorAll("form")) {
                DomElement f = (DomElement) form;
                DomNode item = f.querySelector("input[name=item]");
                if (f.getAttribute("action").contains("markReviewed") && item != null) {
                    row.reviewTargets.add(f.getAttribute("action") + "?item=" + ((DomElement) item).getAttribute("value"));
                }
            }
            out.put(code.asNormalizedText().trim(), row);
        }
        return out;
    }
}
