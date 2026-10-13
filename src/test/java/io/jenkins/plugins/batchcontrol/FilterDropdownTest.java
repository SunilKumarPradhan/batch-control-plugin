package io.jenkins.plugins.batchcontrol;

import hudson.model.FreeStyleProject;
import hudson.model.Item;
import hudson.model.Result;
import hudson.model.User;
import hudson.security.ACL;
import hudson.security.ACLContext;
import io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration;
import io.jenkins.plugins.batchcontrol.config.BatchControlJobProperty;
import io.jenkins.plugins.batchcontrol.model.RequestStatus;
import io.jenkins.plugins.batchcontrol.policy.RunRequestService;
import io.jenkins.plugins.batchcontrol.security.BatchControlPermissions;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import jenkins.model.Jenkins;
import org.htmlunit.HttpMethod;
import org.htmlunit.Page;
import org.htmlunit.WebRequest;
import org.htmlunit.html.DomElement;
import org.htmlunit.html.DomNode;
import org.htmlunit.html.HtmlElement;
import org.htmlunit.html.HtmlForm;
import org.htmlunit.html.HtmlOption;
import org.htmlunit.html.HtmlPage;
import org.htmlunit.html.HtmlSelect;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.jvnet.hudson.test.FailureBuilder;
import org.jvnet.hudson.test.JenkinsRule;
import org.jvnet.hudson.test.MockAuthorizationStrategy;
import org.jvnet.hudson.test.junit.jupiter.WithJenkins;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Wave D, group D2, issue #18 item 3 (matrix rows T-UI-250..254, note 361): the History filter's
 * Result and Status become {@code jenkins-select} dropdowns that start with "Any" (value empty).
 * The option values stay the enum names, so URLs, bookmarks and filter tokens are unchanged.
 * Result is offered for runs and incidents; Status for incidents (OPEN, ACKNOWLEDGED, RESOLVED)
 * and requests (every {@link RequestStatus}); neither for changes. A value from a hand-edited URL
 * that is not in the list stays selected as an extra option (SPEC 6: the user's input is kept),
 * escaped.
 *
 * <p>The filter form is the form holding the {@code from} date field (as HistoryUsabilityTest).
 * Written from the Wave D contract (D2, frozen 2026-10-10), issue #18 and pages rendered on
 * origin/main (d80e5fe); no src/main knowledge.
 */
@WithJenkins
public class FilterDropdownTest {

    private static final List<String> INCIDENT_STATUSES = List.of("OPEN", "ACKNOWLEDGED", "RESOLVED");
    private static final List<String> COMMON_RESULTS = List.of("SUCCESS", "UNSTABLE", "FAILURE", "ABORTED");

    private JenkinsRule j;

    @BeforeEach
    public void setUp(JenkinsRule rule) throws Exception {
        this.j = rule;
        j.jenkins.setSecurityRealm(j.createDummySecurityRealm());
        j.jenkins.setAuthorizationStrategy(new MockAuthorizationStrategy()
                .grant(Jenkins.ADMINISTER).everywhere().to("admin")
                .grant(Jenkins.READ, Item.READ, Item.BUILD, BatchControlPermissions.REQUEST).everywhere().to("u1")
                .grant(Jenkins.READ, Item.READ, BatchControlPermissions.APPROVE).everywhere().to("a1"));
        BatchControlGlobalConfiguration cfg = BatchControlGlobalConfiguration.get();
        cfg.setChangeControlEnabled(true); // recording on, run control off for the fixture builds
        cfg.setApprovers(Arrays.asList("a1"));
        cfg.save();
        FreeStyleProject ok = j.createFreeStyleProject("ok-x");
        j.buildAndAssertSuccess(ok);
        FreeStyleProject fail = j.createFreeStyleProject("fail-x");
        fail.getBuildersList().add(new FailureBuilder());
        j.buildAndAssertStatus(Result.FAILURE, fail);
        cfg.setRunControlEnabled(true);
        cfg.save();
        FreeStyleProject req = j.createFreeStyleProject("req-x");
        BatchControlFixtures.setBatchControl(req, new BatchControlJobProperty(true));
        try (ACLContext ignored = ACL.as2(User.getById("u1", true).impersonate2())) {
            RunRequestService.get().create(req, new LinkedHashMap<>(), "pending request", "a1");
        }
    }

    /**
     * T-UI-250 (#18.3): on History > Runs the Result filter is a {@code jenkins-select} dropdown
     * whose first option is "Any" with an empty value and selected; its other values are result
     * names (at least SUCCESS, UNSTABLE, FAILURE, ABORTED), each once. There is no Status filter and
     * no free-text Result or Status field.
     */
    @Test
    public void t_ui_250_runsOfferAResultDropdownStartingWithAny() throws Exception {
        HtmlForm form = filterForm(page("batch-control/history/?kind=runs"));
        assertNoTextField(form, "result");
        assertNoTextField(form, "status");
        HtmlSelect result = select(form, "result");
        assertDropdown(result, "result on runs");
        assertTrue(result.getSelectedOptions().size() == 1 && "".equals(result.getSelectedOptions().get(0).getValueAttribute()),
                "with no result in the URL, 'Any' must be selected");
        assertResultOptions(result);
        assertNull(control(form, "status"), "History > Runs must offer no Status filter");
    }

    /**
     * T-UI-251 (#18.3): on History > Incidents both the Result dropdown (as T-UI-250) and the Status
     * dropdown are offered; Status holds exactly Any (empty), OPEN, ACKNOWLEDGED, RESOLVED, in this
     * order.
     */
    @Test
    public void t_ui_251_incidentsOfferResultAndStatusDropdowns() throws Exception {
        HtmlForm form = filterForm(page("batch-control/history/?kind=incidents"));
        assertNoTextField(form, "result");
        assertNoTextField(form, "status");
        HtmlSelect result = select(form, "result");
        assertDropdown(result, "result on incidents");
        assertResultOptions(result);
        HtmlSelect status = select(form, "status");
        assertDropdown(status, "status on incidents");
        List<String> expected = new ArrayList<>();
        expected.add("");
        expected.addAll(INCIDENT_STATUSES);
        assertEquals(expected, values(status), "the incident Status dropdown must offer Any, OPEN, ACKNOWLEDGED, RESOLVED");
    }

    /**
     * T-UI-252 (#18.3): on History > Requests the Status dropdown offers Any (empty) and every
     * {@link RequestStatus} name, each once; there is no Result filter. History > Changes offers
     * neither filter.
     */
    @Test
    public void t_ui_252_requestsOfferEveryRequestStatusAndChangesOfferNeither() throws Exception {
        HtmlForm requests = filterForm(page("batch-control/history/?kind=requests"));
        assertNoTextField(requests, "status");
        HtmlSelect status = select(requests, "status");
        assertDropdown(status, "status on requests");
        List<String> values = values(status);
        Set<String> expected = new TreeSet<>();
        for (RequestStatus s : RequestStatus.values()) {
            expected.add(s.name());
        }
        assertEquals(expected, new TreeSet<>(values.subList(1, values.size())),
                "the request Status dropdown must offer every RequestStatus by its name");
        assertEquals(values.size() - 1, expected.size(), "each request status must be offered once: " + values);
        assertNull(control(requests, "result"), "History > Requests must offer no Result filter");

        HtmlForm changes = filterForm(page("batch-control/history/?kind=changes"));
        assertNull(control(changes, "result"), "History > Changes must offer no Result filter");
        assertNull(control(changes, "status"), "History > Changes must offer no Status filter");
    }

    /**
     * T-UI-253 (#18.3, SPEC 6 "the user's input is kept"): values from the URL are selected
     * ({@code result=FAILURE}, {@code status=ACKNOWLEDGED}); a hand-edited value that is not in the
     * list ({@code result=WEIRD<b>x</b>}, {@code status=bogus"q}) stays selected as one extra option
     * whose value is exactly the typed text, escaped (no element is injected into the select).
     */
    @Test
    public void t_ui_253_urlValuesAreSelectedAndUnknownOnesAreKept() throws Exception {
        HtmlForm known = filterForm(page("batch-control/history/?kind=incidents&result=FAILURE&status=ACKNOWLEDGED"));
        assertEquals(List.of("FAILURE"), selected(select(known, "result")), "result=FAILURE must be selected");
        assertEquals(List.of("ACKNOWLEDGED"), selected(select(known, "status")), "status=ACKNOWLEDGED must be selected");

        String oddResult = "WEIRD<b>x</b>";
        HtmlForm runs = filterForm(page("batch-control/history/?kind=runs&result=" + enc(oddResult)));
        HtmlSelect result = select(runs, "result");
        assertEquals(List.of(oddResult), selected(result), "the hand-edited result must stay selected as typed");
        assertEquals(1, values(result).stream().filter(oddResult::equals).count(), "the kept value must be one extra option");
        assertTrue(values(result).containsAll(COMMON_RESULTS), "the known results must still be offered: " + values(result));
        assertTrue(result.querySelectorAll("b").isEmpty(), "the kept value must be escaped, not markup: " + result.asXml());

        String oddStatus = "bogus\"q";
        HtmlForm requests = filterForm(page("batch-control/history/?kind=requests&status=" + enc(oddStatus)));
        HtmlSelect status = select(requests, "status");
        assertEquals(List.of(oddStatus), selected(status), "the hand-edited status must stay selected as typed (attribute escaped)");
        assertEquals(RequestStatus.values().length + 2, values(status).size(),
                "Any, every request status and the one kept value: " + values(status));
    }

    /**
     * T-UI-254 (#18.3, tokens unchanged): choosing FAILURE in the Result dropdown and submitting the
     * filter leads to a URL with {@code result=FAILURE} listing the failing run only; choosing Any
     * lists both runs again. On incidents, choosing OPEN leads to {@code status=OPEN}.
     */
    @Test
    public void t_ui_254_submittingADropdownFiltersWithTheEnumName() throws Exception {
        HtmlPage runs = page("batch-control/history/?kind=runs");
        assertTrue(table(runs).contains("ok-x") && table(runs).contains("fail-x"), "guard: both runs are listed unfiltered");
        HtmlForm form = filterForm(runs);
        select(form, "result").setSelectedAttribute("FAILURE", true);
        HtmlPage failed = submit(form);
        assertTrue(failed.getUrl().getQuery() != null && failed.getUrl().getQuery().contains("result=FAILURE"),
                "the filter URL must carry result=FAILURE: " + failed.getUrl());
        assertTrue(table(failed).contains("fail-x"), "the failing run must be listed: " + table(failed));
        assertFalse(table(failed).contains("ok-x"), "the successful run must be filtered out: " + table(failed));

        HtmlForm again = filterForm(failed);
        select(again, "result").setSelectedAttribute("", true);
        HtmlPage any = submit(again);
        assertTrue(table(any).contains("ok-x") && table(any).contains("fail-x"), "'Any' must list both runs: " + table(any));

        HtmlForm incidents = filterForm(page("batch-control/history/?kind=incidents"));
        select(incidents, "status").setSelectedAttribute("OPEN", true);
        HtmlPage open = submit(incidents);
        assertTrue(open.getUrl().getQuery() != null && open.getUrl().getQuery().contains("status=OPEN"),
                "the filter URL must carry status=OPEN: " + open.getUrl());
        assertTrue(table(open).contains("fail-x"), "the open incident must be listed: " + table(open));
    }

    // ------------------------------------------------------------------ helpers

    private static void assertResultOptions(HtmlSelect result) {
        List<String> values = values(result);
        assertTrue(values.containsAll(COMMON_RESULTS), "the Result dropdown must offer " + COMMON_RESULTS + ": " + values);
        Set<String> seen = new HashSet<>();
        for (String v : values.subList(1, values.size())) {
            assertTrue(seen.add(v), "each result must be offered once: " + values);
            assertEquals(v, Result.fromString(v).toString(), "every Result option value must be a result name: " + v);
        }
    }

    /** A jenkins-select dropdown whose first option is "Any" with an empty value. */
    private static void assertDropdown(HtmlSelect select, String what) {
        boolean styled = false;
        for (DomNode n = select; n instanceof DomElement e && !styled; n = n.getParentNode()) {
            styled = (" " + e.getAttribute("class") + " ").matches(".*\\sjenkins-select(__input)?\\s.*");
            if ("form".equals(e.getTagName())) {
                break;
            }
        }
        assertTrue(styled, what + ": the dropdown must be core's jenkins-select: " + select.getParentNode().asXml());
        assertFalse(select.getOptions().isEmpty(), what + ": the dropdown must have options");
        HtmlOption first = select.getOptions().get(0);
        assertEquals("", first.getValueAttribute(), what + ": the first option must have an empty value");
        assertEquals("Any", first.asNormalizedText().trim(), what + ": the first option must read 'Any'");
        assertFalse(select.isMultipleSelectEnabled(), what + ": one value at a time");
    }

    private static void assertNoTextField(HtmlForm form, String name) {
        for (DomNode n : form.querySelectorAll("input")) {
            DomElement input = (DomElement) n;
            String type = input.getAttribute("type");
            assertFalse(name.equals(input.getAttribute("name")) && !"hidden".equals(type),
                    "the " + name + " filter must not be a free-text field any more: " + input.asXml());
        }
    }

    private static HtmlSelect select(HtmlForm form, String name) {
        DomElement control = control(form, name);
        assertTrue(control instanceof HtmlSelect, "the " + name + " filter must be a dropdown (select), was: "
                + (control == null ? "absent" : control.asXml()));
        return (HtmlSelect) control;
    }

    /** The visible form control named {@code name}, or null. */
    private static DomElement control(HtmlForm form, String name) {
        for (DomNode n : form.querySelectorAll("input, select, textarea")) {
            DomElement e = (DomElement) n;
            if (name.equals(e.getAttribute("name")) && !"hidden".equals(e.getAttribute("type"))) {
                return e;
            }
        }
        return null;
    }

    private static List<String> values(HtmlSelect select) {
        List<String> out = new ArrayList<>();
        for (HtmlOption o : select.getOptions()) {
            out.add(o.getValueAttribute());
        }
        return out;
    }

    private static List<String> selected(HtmlSelect select) {
        List<String> out = new ArrayList<>();
        for (HtmlOption o : select.getSelectedOptions()) {
            out.add(o.getValueAttribute());
        }
        return out;
    }

    private static HtmlForm filterForm(HtmlPage page) {
        for (HtmlForm form : page.getForms()) {
            if (!form.getInputsByName("from").isEmpty()) {
                return form;
            }
        }
        throw new AssertionError("fixture: the History screen must have the filter form with the from field");
    }

    private static HtmlPage submit(HtmlForm form) throws Exception {
        for (DomNode n : form.querySelectorAll("button, input[type=submit]")) {
            Page next = ((HtmlElement) n).click();
            assertTrue(next instanceof HtmlPage, "the filter must answer a page");
            return (HtmlPage) next;
        }
        throw new AssertionError("fixture: the filter form must have a submit button");
    }

    /** The text of the page's listing tables (the History records). */
    private static String table(HtmlPage page) {
        StringBuilder out = new StringBuilder();
        for (DomNode n : page.querySelectorAll("#main-panel table tbody")) {
            out.append(n.asNormalizedText()).append('\n');
        }
        return out.toString();
    }

    private HtmlPage page(String path) throws Exception {
        JenkinsRule.WebClient wc = j.createWebClient().withThrowExceptionOnFailingStatusCode(false).login("admin");
        Page answer = wc.getPage(new WebRequest(new URL(j.getURL(), path), HttpMethod.GET));
        assertEquals(200, answer.getWebResponse().getStatusCode(), "admin GET " + path);
        assertNotNull(answer, path);
        return (HtmlPage) answer;
    }

    private static String enc(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }
}
