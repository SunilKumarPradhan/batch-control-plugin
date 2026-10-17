package io.jenkins.plugins.batchcontrol;

import com.cloudbees.hudson.plugins.folder.Folder;
import hudson.model.AbstractItem;
import hudson.model.FreeStyleProject;
import hudson.model.Item;
import hudson.security.AuthorizationMatrixProperty;
import io.jenkins.plugins.batchcontrol.model.ChangeType;
import io.jenkins.plugins.batchcontrol.model.GrantAction;
import io.jenkins.plugins.batchcontrol.security.BatchControlMatrixAuthorizationStrategy;
import io.jenkins.plugins.batchcontrol.store.BatchClock;
import java.time.Clock;
import java.time.ZoneOffset;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Locale;
import org.htmlunit.HttpMethod;
import org.htmlunit.Page;
import org.htmlunit.WebRequest;
import org.jenkinsci.plugins.matrixauth.PermissionEntry;
import org.jenkinsci.plugins.matrixauth.inheritance.InheritParentStrategy;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.jvnet.hudson.test.JenkinsRule;
import org.jvnet.hudson.test.junit.jupiter.WithJenkins;

import static io.jenkins.plugins.batchcontrol.StrategyFixtures.T0;
import static io.jenkins.plugins.batchcontrol.StrategyFixtures.has;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #1 (security-32 S-32-03): the 403 text of a reverted self-grant on a folder. Matrix row T-02-193 (note
 * 357).
 *
 * <p>Basis: SPEC item 2, the D-48 line (a save whose authorization part the guard reverts "answers 403 with a
 * plain message naming the item, saying the authorization entries were not kept ... that the other changes
 * were saved") and the D-58b line (the state ends through "Mark as reviewed" by a holder of native
 * Item/Configure or Overall/Administer, "not by a grant"); SPEC 6 usability (a refusal says what to do
 * instead; no link or pointer to a page that does not exist); docs/reports/security-32.md S-32-03; the #1
 * contract (frozen 2026-10-10): "the folder variant of the text does not mention the job's Batch Control page,
 * and says Configure must be held directly".
 *
 * <p>bob holds Configure on the item only through a CONFIGURE window on it (StrategyFixtures); the item
 * carries its own matrix property with alice's Configure entry and a Read entry for bob; bob's
 * {@code config.xml} POST adds Configure for himself, which the guard reverts.
 *
 * <p>Written from docs/SPEC.md, docs/DECISIONS.md D-48/D-58b, docs/reports/security-32.md and the #1
 * contract only (no src/main knowledge).
 */
@WithJenkins
public class FolderSelfGrantRefusalTextTest {

    private JenkinsRule j;

    @BeforeEach
    public void setUp(JenkinsRule rule) {
        this.j = rule;
        j.jenkins.setSecurityRealm(j.createDummySecurityRealm());
        j.jenkins.setAuthorizationStrategy(StrategyFixtures.matrix(new BatchControlMatrixAuthorizationStrategy()));
        StrategyFixtures.changeControlOn();
        BatchClock.setForTest(Clock.fixed(T0, ZoneOffset.UTC));
    }

    @AfterEach
    public void resetClock() {
        BatchClock.reset();
    }

    /**
     * T-02-193 (#1.6, S-32-03): bob, whose Configure on folder {@code team} comes only from his window, adds
     * Configure for himself through {@code POST team/config.xml}: 403 (premise, with one GRANT_VIOLATION
     * record) naming {@code team}. The text does not mention a Batch Control page (folders have none) and says
     * in one sentence that Configure must be held directly. On main the folder text is the job text: "... or on
     * the job's Batch Control page (a user with Configure permission on it and Batch Control/Request)". Guard:
     * the same save on the job {@code job-j} answers 403 naming {@code job-j} and still points to the job's
     * Batch Control page.
     */
    @Test
    public void t_02_193_folderSelfGrantTextNamesNoJobPageAndSaysConfigureMustBeDirect() throws Exception {
        FreeStyleProject job = j.createFreeStyleProject("job-j");
        AuthorizationMatrixProperty amp = new AuthorizationMatrixProperty(new HashMap<>(), new InheritParentStrategy());
        amp.add(Item.CONFIGURE, PermissionEntry.user("alice"));
        amp.add(Item.READ, PermissionEntry.user("bob"));
        job.addProperty(amp);
        String jobText = selfGrant(job, "</hudson.security.AuthorizationMatrixProperty>");
        assertTrue(jobText.contains("job-j"), "guard: the job text names the job: " + jobText);
        assertTrue(jobText.toLowerCase(Locale.ROOT).contains("batch control page"),
                "guard: the job text still points to the job's Batch Control page: " + jobText);

        Folder folder = j.jenkins.createProject(Folder.class, "team");
        com.cloudbees.hudson.plugins.folder.properties.AuthorizationMatrixProperty fp =
                new com.cloudbees.hudson.plugins.folder.properties.AuthorizationMatrixProperty(new HashMap<>());
        fp.add(Item.CONFIGURE, PermissionEntry.user("alice"));
        fp.add(Item.READ, PermissionEntry.user("bob"));
        folder.addProperty(fp);
        String text = selfGrant(folder, "</com.cloudbees.hudson.plugins.folder.properties.AuthorizationMatrixProperty>");
        assertTrue(text.contains("team"), "the folder text names the folder: " + text);
        assertFalse(text.toLowerCase(Locale.ROOT).contains("batch control page"),
                "#1.6: a folder has no Batch Control page, so the folder text must not mention one: " + text);
        assertTrue(Arrays.stream(text.split("(?<=[.;:])\\s+")).map(s -> s.toLowerCase(Locale.ROOT))
                        .anyMatch(s -> s.contains("configure") && s.contains("directly")),
                "#1.6: the folder text must say that Configure must be held directly (not from a permission window): " + text);
    }

    /** bob's CONFIGURE window on {@code item}, then his config.xml POST adding Configure for himself; the 403 text. */
    private String selfGrant(AbstractItem item, String close) throws Exception {
        assertFalse(has(item, "bob", Item.CONFIGURE), "premise: bob holds no native Configure on " + item.getFullName());
        StrategyFixtures.grant("bob", item.getFullName(), Arrays.asList(GrantAction.CONFIGURE));
        assertTrue(has(item, "bob", Item.CONFIGURE), "premise: the window confers Configure on " + item.getFullName());
        String xml = item.getConfigFile().asString();
        assertTrue(xml.contains(close), "fixture: unexpected config.xml: " + xml);
        int violations = StrategyFixtures.records(ChangeType.GRANT_VIOLATION).size();
        Page answer = postConfigXml("bob", item, xml.replace(close, "<permission>USER:hudson.model.Item.Configure:bob</permission>" + close));
        assertEquals(violations + 1, StrategyFixtures.records(ChangeType.GRANT_VIOLATION).size(),
                "premise: the guard reverted the self-grant on " + item.getFullName() + " and recorded it");
        assertEquals(403, answer.getWebResponse().getStatusCode(), "premise: the reverted save answers 403");
        String text = UsabilityFixtures.text(answer);
        UsabilityFixtures.assertPlainRefusal("the self-grant refusal on " + item.getFullName(), text, null);
        return text;
    }

    private Page postConfigXml(String user, AbstractItem item, String xml) throws Exception {
        JenkinsRule.WebClient wc = j.createWebClient().withThrowExceptionOnFailingStatusCode(false).login(user);
        WebRequest req = new WebRequest(wc.createCrumbedUrl(item.getUrl() + "config.xml"), HttpMethod.POST);
        req.setAdditionalHeader("Content-Type", "application/xml");
        req.setRequestBody(xml);
        return wc.getPage(req);
    }
}
