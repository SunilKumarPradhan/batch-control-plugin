package io.jenkins.plugins.batchcontrol;

import hudson.security.ProjectMatrixAuthorizationStrategy;
import io.jenkins.plugins.batchcontrol.security.BatchControlMatrixAuthorizationStrategy;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import org.htmlunit.HttpMethod;
import org.htmlunit.Page;
import org.htmlunit.WebRequest;
import org.htmlunit.html.DomElement;
import org.htmlunit.html.DomNode;
import org.htmlunit.html.HtmlElement;
import org.htmlunit.html.HtmlForm;
import org.htmlunit.html.HtmlPage;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.jvnet.hudson.test.JenkinsRule;
import org.jvnet.hudson.test.junit.jupiter.WithJenkins;

import static org.junit.jupiter.api.Assertions.assertAll;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Wave D, group D1, issue #18 item 7 (matrix rows T-UI-234, T-UI-235, note 360): the red "Revert to
 * the plain strategy" control moves to the end of the Batch Control section of the global
 * configuration, inside core's Advanced control ({@code f:advanced}: a {@code button.advanced-button}
 * followed by a hidden {@code div.advancedBody} that core's script reveals on click). It is offered
 * to Overall/Administer only, as before; the endpoint
 * ({@code manage/administrativeMonitor/batch-control-strategy/revert}) and its permission check are
 * unchanged.
 *
 * <p>"The Batch Control section" is the closest {@code section} element around the control (core
 * renders each global configuration as a {@code section.jenkins-section}), else its form; "a Batch
 * Control field" is a named setting of that section ({@code name} starting with {@code _.}).
 *
 * <p>Row T-UI-239 (note 360 (9)): what a BatchControl/Manage holder, who is offered no revert, sees
 * in its place. On origin/main the Batch Control configuration page told that user "Only a Jenkins
 * administrator can change the authorization strategy." among the settings; that sentence must stay
 * readable without pressing anything, and an Advanced button that reveals nothing the user can use
 * must not be there.
 *
 * <p>Written from the Wave D contract (D1, frozen 2026-10-10), issue #18, core 2.568.3's
 * {@code lib/form/advanced.jelly} and pages rendered on origin/main (d80e5fe); no src/main
 * knowledge.
 */
@WithJenkins
public class RevertPlacementTest {

    private static final String REVERT = "administrativeMonitor/batch-control-strategy/revert";
    private static final List<String> PAGES = List.of("manage/configure", "manage/batch-control-configuration/");
    /** What a user who may not change the strategy is told where the administrator finds the revert. */
    private static final String ADMINISTRATOR_ONLY = "Only a Jenkins administrator can change the authorization strategy.";

    private JenkinsRule j;

    @BeforeEach
    public void setUp(JenkinsRule rule) {
        this.j = rule;
        j.jenkins.setSecurityRealm(j.createDummySecurityRealm());
        StrategyFixtures.changeControlOn();
        StrategyFixtures.configureBuildAuthenticator();
        // admin holds Administer; m1 holds BatchControl/Manage only (StrategyFixtures.matrix)
        j.jenkins.setAuthorizationStrategy(StrategyFixtures.matrix(new BatchControlMatrixAuthorizationStrategy()));
    }

    /**
     * T-UI-234 (#18.7): on the global configuration page (and on the Batch Control configuration
     * page, where it is offered too) the administrator's revert control sits inside core's Advanced
     * control, no Batch Control field follows it in the section, it is hidden until the Advanced
     * button is pressed and shown after. Guard: it keeps the destructive colour and the endpoint.
     */
    @Test
    public void t_ui_234_revertSitsAtTheEndOfTheSectionInsideAdvanced() throws Exception {
        int offered = 0;
        for (String path : PAGES) {
            HtmlPage page = page("admin", path, true);
            HtmlElement control = revertControl(page);
            if (control == null) {
                assertFalse(path.equals("manage/configure"), "guard: the global configuration page must offer the"
                        + " administrator the revert while a Batch Control strategy is installed (T-02-37)");
                continue;
            }
            offered++;
            assertTrue(control.getAttribute("class").contains("jenkins-!-destructive-color"),
                    path + ": guard: the revert keeps the destructive colour (T-UI-52)");

            DomElement body = ancestorWithClass(control, "advancedBody");
            assertNotNull(body, path + ": the revert control must be inside core's Advanced control (f:advanced),"
                    + " not among the routine settings; it sits in: " + parentChain(control));
            DomElement item = (DomElement) body.getParentNode();
            DomNode advancedButton = item.querySelector("button.advanced-button");
            assertNotNull(advancedButton, path + ": the Advanced control must have core's Advanced button");

            DomElement section = section(control);
            for (DomNode n : section.querySelectorAll("input[name], select[name], textarea[name]")) {
                DomElement field = (DomElement) n;
                if (field.getAttribute("name").startsWith("_.") && follows(field, control)) {
                    throw new AssertionError(path + ": the revert must be the last entry of the Batch Control section,"
                            + " but the field " + field.getAttribute("name") + " follows it");
                }
            }

            // core's script reveals an Advanced control by moving its body's rows out of div.advancedBody
            ((HtmlElement) advancedButton).click();
            page.getWebClient().waitForBackgroundJavaScript(2000);
            HtmlElement shown = revertControl(page);
            assertNotNull(shown, path + ": the revert control must still be on the page after Advanced is pressed");
            assertTrue(ancestorWithClass(shown, "advancedBody") == null && shown.isDisplayed(),
                    path + ": pressing Advanced must show the revert control: " + parentChain(shown));
        }
        assertTrue(offered > 0, "the administrator must be offered the revert on " + PAGES);
    }

    /**
     * T-UI-235 (#18.7, negative path): a BatchControl/Manage holder (m1) is offered no revert on the
     * Batch Control configuration page, not even hidden inside an Advanced control, and is refused
     * the endpoint with 403; GET is refused with 405. The administrator's revert, revealed through
     * Advanced, still names the unchanged endpoint, which still works with the crumb.
     */
    @Test
    public void t_ui_235_revertStaysAdministerOnlyWithTheSameEndpoint() throws Exception {
        HtmlPage manager = page("m1", "manage/batch-control-configuration/", false);
        assertEquals(null, revertControl(manager), "a BatchControl/Manage holder must not be offered the revert");
        assertFalse(manager.getWebResponse().getContentAsString().contains("Revert to the plain strategy"),
                "the revert must not be in a Manage holder's page, not even hidden");
        assertEquals(403, post("m1"), "guard: the revert endpoint keeps its Overall/Administer check");
        JenkinsRule.WebClient admin = client("admin", false);
        assertEquals(405, admin.getPage(new WebRequest(new URL(j.getURL(), "manage/" + REVERT), HttpMethod.GET))
                .getWebResponse().getStatusCode(), "guard: GET of the revert endpoint is refused");

        HtmlPage page = page("admin", "manage/configure", true);
        HtmlElement control = revertControl(page);
        assertNotNull(control, "guard: the administrator is offered the revert");
        DomElement body = ancestorWithClass(control, "advancedBody");
        assertNotNull(body, "the revert control must be inside core's Advanced control: " + parentChain(control));
        ((HtmlElement) ((DomElement) body.getParentNode()).querySelector("button.advanced-button")).click();
        page.getWebClient().waitForBackgroundJavaScript(2000);
        control = revertControl(page);
        assertTrue(control != null && ancestorWithClass(control, "advancedBody") == null && control.isDisplayed(),
                "pressing Advanced must show the revert control");
        assertEquals(new URL(j.getURL(), "manage/" + REVERT).getPath(), new URL(page.getFullyQualifiedUrl(target(control))
                .toExternalForm()).getPath(), "the revert must still post to the monitor's revert endpoint");

        assertTrue(post("admin") < 400, "the administrator's crumbed revert must still work");
        assertSame(ProjectMatrixAuthorizationStrategy.class, j.jenkins.getAuthorizationStrategy().getClass(),
                "the revert installs the plain parent");
    }

    /**
     * T-UI-239 (#18.7): m1 (BatchControl/Manage only) reads "Only a Jenkins administrator can
     * change the authorization strategy." on the Batch Control configuration page without pressing
     * anything: the sentence is in the page and not inside core's {@code div.advancedBody}, and
     * the Batch Control section shows m1 no Advanced button at all (there is nothing behind it for
     * this user). With JavaScript on the sentence is displayed as the page loads. Guards (T-UI-235):
     * no revert control in the DOM, no "Revert to the plain strategy" in the HTML, POST 403.
     */
    @Test
    public void t_ui_239_manageHolderReadsTheAdministratorOnlySentenceWithoutAnAdvancedButton() throws Exception {
        String path = "manage/batch-control-configuration/";
        HtmlPage manager = page("m1", path, false);
        DomElement sentence = elementReading(manager, ADMINISTRATOR_ONLY);
        assertNotNull(sentence, "m1's Batch Control configuration page must say '" + ADMINISTRATOR_ONLY + "': "
                + excerpt(manager));

        List<DomElement> sections = batchControlSections(manager);
        assertFalse(sections.isEmpty(), "fixture: the page has a section with Batch Control settings (name=\"_.…\")");
        List<String> advancedButtons = new ArrayList<>();
        for (DomElement section : sections) {
            for (DomNode b : section.querySelectorAll("button.advanced-button")) {
                advancedButtons.add(b.asNormalizedText().trim() + " in " + parentChain(b));
            }
        }

        HtmlPage live = page("m1", path, true);
        live.getWebClient().waitForBackgroundJavaScript(2000);
        DomElement liveSentence = elementReading(live, ADMINISTRATOR_ONLY);

        assertAll(
                () -> assertEquals(null, ancestorWithClass(sentence, "advancedBody"), "m1 must read the sentence"
                        + " without pressing Advanced, so it must not be inside core's div.advancedBody; it sits in: "
                        + parentChain(sentence)),
                () -> assertEquals(List.of(), advancedButtons, "the Batch Control section must show m1 no Advanced"
                        + " button: there is nothing behind it that m1 may use"),
                () -> assertTrue(liveSentence != null && liveSentence.isDisplayed(), "with JavaScript on, the sentence"
                        + " must be displayed to m1 as the page loads (no click)"));

        assertEquals(null, revertControl(manager), "guard (T-UI-235): m1 is offered no revert");
        assertFalse(manager.getWebResponse().getContentAsString().contains("Revert to the plain strategy"),
                "guard (T-UI-235): the revert is not in m1's page, not even hidden");
        assertEquals(403, post("m1"), "guard (T-UI-235): the revert endpoint keeps its Overall/Administer check");
        assertSame(BatchControlMatrixAuthorizationStrategy.class, j.jenkins.getAuthorizationStrategy().getClass(),
                "guard: m1's refused POST leaves the Batch Control strategy installed");
    }

    // ------------------------------------------------------------------ helpers

    /** The innermost element whose text holds {@code text}, or null. */
    private static DomElement elementReading(HtmlPage page, String text) {
        DomElement found = null;
        for (DomElement e : page.getBody().getDomElementDescendants()) {
            if (!"script".equals(e.getTagName()) && e.getTextContent().replaceAll("\\s+", " ").contains(text)) {
                found = e; // document order: a descendant comes after its ancestors
                if (!e.getChildElements().iterator().hasNext()) {
                    break;
                }
            }
        }
        return found;
    }

    /** The {@code section} elements of the main panel that hold a Batch Control setting ({@code name="_.…"}). */
    private static List<DomElement> batchControlSections(HtmlPage page) {
        List<DomElement> out = new ArrayList<>();
        for (DomNode n : page.querySelectorAll("#main-panel section")) {
            for (DomNode f : n.querySelectorAll("input[name], select[name], textarea[name]")) {
                if (((DomElement) f).getAttribute("name").startsWith("_.")) {
                    out.add((DomElement) n);
                    break;
                }
            }
        }
        return out;
    }

    private static String excerpt(HtmlPage page) {
        String text = page.asNormalizedText();
        return text.length() > 1500 ? text.substring(0, 1500) + "..." : text;
    }

    /** The element that triggers the revert: a link, a confirmation link (data-url) or a form button. */
    static HtmlElement revertControl(HtmlPage page) {
        for (HtmlElement e : page.getHtmlElementDescendants()) {
            if (e instanceof HtmlForm f) {
                if (f.getActionAttribute().endsWith(REVERT)) {
                    for (DomNode n : f.querySelectorAll("button, input[type=submit]")) {
                        return (HtmlElement) n;
                    }
                }
                continue;
            }
            if (target(e).endsWith(REVERT)) {
                return e;
            }
        }
        return null;
    }

    private static String target(HtmlElement e) {
        for (String attribute : new String[] {"data-url", "formaction", "href"}) {
            String value = e.getAttribute(attribute);
            if (value != null && value.endsWith(REVERT)) {
                return value;
            }
        }
        return "";
    }

    private static DomElement ancestorWithClass(DomNode node, String cls) {
        for (DomNode n = node.getParentNode(); n instanceof DomElement e; n = n.getParentNode()) {
            if ((" " + e.getAttribute("class") + " ").contains(" " + cls + " ")) {
                return e;
            }
        }
        return null;
    }

    private static DomElement section(DomNode node) {
        DomElement form = null;
        for (DomNode n = node.getParentNode(); n instanceof DomElement e; n = n.getParentNode()) {
            if ("section".equals(e.getTagName())) {
                return e;
            }
            if (form == null && "form".equals(e.getTagName())) {
                form = e;
            }
        }
        assertNotNull(form, "fixture: the revert control must be inside the configuration form");
        return form;
    }

    private static boolean follows(DomNode candidate, DomNode reference) {
        return (reference.compareDocumentPosition(candidate) & DomNode.DOCUMENT_POSITION_FOLLOWING) != 0
                && (reference.compareDocumentPosition(candidate) & DomNode.DOCUMENT_POSITION_CONTAINED_BY) == 0;
    }

    private static String parentChain(DomNode node) {
        List<String> out = new ArrayList<>();
        for (DomNode n = node.getParentNode(); n instanceof DomElement e && out.size() < 8; n = n.getParentNode()) {
            out.add(e.getTagName() + "." + e.getAttribute("class").trim().replace(' ', '.'));
        }
        return String.join(" < ", out);
    }

    private int post(String user) throws Exception {
        JenkinsRule.WebClient wc = client(user, false);
        return wc.getPage(new WebRequest(wc.createCrumbedUrl("manage/" + REVERT), HttpMethod.POST))
                .getWebResponse().getStatusCode();
    }

    private HtmlPage page(String user, String path, boolean javaScript) throws Exception {
        Page answer = client(user, javaScript).getPage(new WebRequest(new URL(j.getURL(), path), HttpMethod.GET));
        assertEquals(200, answer.getWebResponse().getStatusCode(), user + " GET " + path);
        return (HtmlPage) answer;
    }

    private JenkinsRule.WebClient client(String user, boolean javaScript) throws Exception {
        JenkinsRule.WebClient wc = j.createWebClient().withThrowExceptionOnFailingStatusCode(false).login(user);
        wc.getOptions().setJavaScriptEnabled(javaScript);
        return wc;
    }
}
