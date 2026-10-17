package io.jenkins.plugins.batchcontrol;

import hudson.model.FreeStyleProject;
import hudson.model.Result;
import io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration;
import io.jenkins.plugins.batchcontrol.model.Incident;
import io.jenkins.plugins.batchcontrol.ops.IncidentService;
import io.jenkins.plugins.batchcontrol.security.BatchControlPermissions;
import io.jenkins.plugins.batchcontrol.store.BatchClock;
import java.io.ByteArrayInputStream;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.YearMonth;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.logging.Level;
import java.util.logging.LogRecord;
import java.util.logging.SimpleFormatter;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import jenkins.model.Jenkins;
import org.htmlunit.HttpMethod;
import org.htmlunit.Page;
import org.htmlunit.WebRequest;
import org.htmlunit.WebResponse;
import org.htmlunit.html.HtmlForm;
import org.htmlunit.html.HtmlPage;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.jvnet.hudson.test.JenkinsRule;
import org.jvnet.hudson.test.LogRecorder;
import org.jvnet.hudson.test.MockAuthorizationStrategy;
import org.jvnet.hudson.test.junit.jupiter.WithJenkins;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Issue #91 (matrix rows T-11-32..36, note 364; owner decisions of 2026-10-17): the global setting
 * "Results that open an incident" ({@code incidentResults}) accepts only FAILURE, UNSTABLE and
 * ABORTED (SPEC 11: default [FAILURE, UNSTABLE], ABORTED may be added; SPEC 5 table).
 * <ul>
 * <li>The field checks ({@code checkIncidentResults}, {@code checkIncidentResultsText}) and the form
 * save, on Manage Jenkins &gt; System and on the Batch Control configuration page, refuse SUCCESS and
 * NOT_BUILT with a field error, as they refuse a name that is not a build result; nothing is saved.</li>
 * <li>A value stored before the upgrade that holds SUCCESS or NOT_BUILT is read without them (the
 * allowed names keep their order); if none remain, the default [FAILURE, UNSTABLE] applies. One
 * warning names the dropped names; the next save stores the cleaned value; a SUCCESS or NOT_BUILT
 * build then opens no incident.</li>
 * <li>Guards: every combination of FAILURE, UNSTABLE and ABORTED is accepted, saved and used. JCasC
 * (SPEC 2: the global configuration round-trips through JCasC) follows the same rule.</li>
 * </ul>
 * "A stored value from before the upgrade" is produced by editing the saved configuration file
 * ({@code <id>.xml} in JENKINS_HOME, the element {@code incidentResults}) and reading it back with
 * {@code load()}, Jenkins' own read path. Written from SPEC 11, SPEC 2, issue #91 and the owner
 * decisions; no src/main knowledge.
 */
@WithJenkins
public class IncidentResultsSettingTest {

    private static final String DESCRIPTOR =
            "descriptorByName/io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration/";
    private static final List<String> DEFAULT = List.of("FAILURE", "UNSTABLE");
    private static final List<List<String>> ALLOWED_COMBINATIONS = List.of(
            List.of("FAILURE"), List.of("UNSTABLE"), List.of("ABORTED"), List.of("FAILURE", "UNSTABLE"),
            List.of("FAILURE", "ABORTED"), List.of("UNSTABLE", "ABORTED"), List.of("FAILURE", "UNSTABLE", "ABORTED"));

    private JenkinsRule j;

    @BeforeEach
    public void setUp(JenkinsRule rule) throws Exception {
        this.j = rule;
        j.jenkins.setSecurityRealm(j.createDummySecurityRealm());
        j.jenkins.setAuthorizationStrategy(new MockAuthorizationStrategy()
                .grant(Jenkins.ADMINISTER).everywhere().to("admin")
                .grant(Jenkins.READ, BatchControlPermissions.MANAGE).everywhere().to("manager"));
        BatchControlGlobalConfiguration cfg = BatchControlGlobalConfiguration.get();
        cfg.setApprovers(Arrays.asList("admin"));
        cfg.save();
    }

    /**
     * T-11-32: both field checks answer an error for SUCCESS, NOT_BUILT, {@code FAILURE, SUCCESS} and
     * {@code UNSTABLE, NOT_BUILT}. Guard first: every combination of FAILURE, UNSTABLE and ABORTED
     * answers no error, and {@code FAILURE, BOGUS} an error (unchanged, T-CFG-04).
     */
    @Test
    public void t_11_32_fieldChecksRefuseSuccessAndNotBuilt() throws Exception {
        for (String check : List.of("checkIncidentResults", "checkIncidentResultsText")) {
            for (List<String> allowed : ALLOWED_COMBINATIONS) {
                assertFalse(isError(check(check, String.join(", ", allowed))), "guard: " + check + " accepts " + allowed);
            }
            assertTrue(isError(check(check, "FAILURE, BOGUS")), "guard: " + check + " refuses a name that is not a build result");
        }
        for (String check : List.of("checkIncidentResults", "checkIncidentResultsText")) {
            for (String value : List.of("SUCCESS", "NOT_BUILT", "FAILURE, SUCCESS", "UNSTABLE, NOT_BUILT")) {
                WebResponse r = check(check, value);
                assertTrue(isError(r), check + " must answer an error next to the field for '" + value
                        + "' (only FAILURE, UNSTABLE and ABORTED can open an incident): "
                        + UsabilityFixtures.excerpt(r.getContentAsString()));
            }
        }
    }

    /**
     * T-11-33: the administrator's save of Manage Jenkins &gt; System with {@code FAILURE, SUCCESS}
     * and the manager's save of the Batch Control configuration page with {@code UNSTABLE, NOT_BUILT}
     * are not answered as a successful save and store nothing: the setting stays [FAILURE, UNSTABLE].
     * Guard first: the same two saves with {@code FAILURE, ABORTED} and {@code UNSTABLE, ABORTED}
     * store exactly those.
     */
    @Test
    public void t_11_33_formSavesRefuseSuccessAndNotBuilt() throws Exception {
        assertEquals(DEFAULT, BatchControlGlobalConfiguration.get().getIncidentResults(), "fixture: the default");
        assertTrue(save("admin", "configure", "FAILURE, ABORTED").getWebResponse().getStatusCode() < 400,
                "guard: the System page saves FAILURE, ABORTED");
        assertEquals(List.of("FAILURE", "ABORTED"), BatchControlGlobalConfiguration.get().getIncidentResults(),
                "guard: the System page stores FAILURE, ABORTED");
        assertTrue(save("manager", "manage/batch-control-configuration/", "UNSTABLE, ABORTED").getWebResponse()
                .getStatusCode() < 400, "guard: the Batch Control page saves UNSTABLE, ABORTED");
        assertEquals(List.of("UNSTABLE", "ABORTED"), BatchControlGlobalConfiguration.get().getIncidentResults(),
                "guard: the Batch Control page stores UNSTABLE, ABORTED");
        BatchControlGlobalConfiguration.get().setIncidentResults(new ArrayList<>(DEFAULT));
        BatchControlGlobalConfiguration.get().save();

        Page system = save("admin", "configure", "FAILURE, SUCCESS");
        assertRefusedSave("the System page with FAILURE, SUCCESS", system);
        Page page = save("manager", "manage/batch-control-configuration/", "UNSTABLE, NOT_BUILT");
        assertRefusedSave("the Batch Control page with UNSTABLE, NOT_BUILT", page);
    }

    /**
     * T-11-34: a value stored before the upgrade, [FAILURE, SUCCESS, NOT_BUILT, ABORTED], reads as
     * [FAILURE, ABORTED]; exactly one warning names SUCCESS and NOT_BUILT; the next save stores the
     * cleaned value (the file no longer holds SUCCESS or NOT_BUILT). With change control on, a SUCCESS
     * and a NOT_BUILT build then open no incident. Guard: an ABORTED build opens one.
     */
    @Test
    public void t_11_34_storedSuccessAndNotBuiltAreDroppedOnRead() throws Exception {
        List<String> read = readStored("FAILURE", "SUCCESS", "NOT_BUILT", "ABORTED");
        assertEquals(List.of("FAILURE", "ABORTED"), read, "a stored SUCCESS and NOT_BUILT must be dropped on read,"
                + " the allowed names kept in their order");

        BatchControlGlobalConfiguration cfg = BatchControlGlobalConfiguration.get();
        cfg.save();
        String xml = Files.readString(configFile(), StandardCharsets.UTF_8);
        assertFalse(xml.contains("SUCCESS") || xml.contains("NOT_BUILT"), "the next save must store the cleaned value: "
                + incidentElement(xml));

        cfg.setChangeControlEnabled(true); // recording on, so incidents are opened
        cfg.save();
        assertNotNull(incidentAfter("aborted-x", "ABORTED"), "guard: ABORTED stays in the setting and opens an incident");
        assertNull(incidentAfter("success-x", "SUCCESS"), "a SUCCESS build must open no incident after the read");
        assertNull(incidentAfter("not-built-x", "NOT_BUILT"), "a NOT_BUILT build must open no incident after the read");
    }

    /**
     * T-11-35: a value stored before the upgrade that holds only [SUCCESS, NOT_BUILT] reads as the
     * default [FAILURE, UNSTABLE]; exactly one warning names both dropped names.
     */
    @Test
    public void t_11_35_storedValueWithNothingAllowedFallsBackToTheDefault() throws Exception {
        assertEquals(DEFAULT, readStored("SUCCESS", "NOT_BUILT"), "with no allowed name left the default"
                + " [FAILURE, UNSTABLE] applies");
    }

    /**
     * T-11-36 (SPEC 2: the global configuration round-trips through JCasC): a JCasC apply of
     * {@code incidentResultsText: "FAILURE, SUCCESS"} leaves no SUCCESS in the setting, which holds
     * only allowed names (whether the apply is refused, keeping the previous value, or cleaned is not
     * pinned). Guard first: {@code "FAILURE, ABORTED"} is applied exactly.
     */
    @Test
    public void t_11_36_cascFollowsTheSameRule() throws Exception {
        casc("FAILURE, ABORTED");
        assertEquals(List.of("FAILURE", "ABORTED"), BatchControlGlobalConfiguration.get().getIncidentResults(),
                "guard: a JCasC apply of FAILURE, ABORTED is applied");
        try {
            casc("FAILURE, SUCCESS, NOT_BUILT");
        } catch (Exception refused) {
            // a refusal is one of the two outcomes the row allows
        }
        List<String> after = BatchControlGlobalConfiguration.get().getIncidentResults();
        assertFalse(after.isEmpty(), "the setting keeps at least one result: " + after);
        assertTrue(Set.of("FAILURE", "UNSTABLE", "ABORTED").containsAll(after), "a JCasC apply must not bring SUCCESS"
                + " or NOT_BUILT into the setting: " + after);
    }

    // ------------------------------------------------------------------ helpers

    /**
     * Stores {@code names} as the saved incidentResults, reads the configuration back with
     * {@code load()}, asserts exactly one warning naming the dropped names (SUCCESS and NOT_BUILT
     * among {@code names}) and returns what the setting reads.
     */
    private List<String> readStored(String... names) throws Exception {
        BatchControlGlobalConfiguration cfg = BatchControlGlobalConfiguration.get();
        cfg.save();
        Path file = configFile();
        String xml = Files.readString(file, StandardCharsets.UTF_8);
        Matcher element = Pattern.compile("(?s)<incidentResults\\b[^>]*>.*?</incidentResults>").matcher(xml);
        assertTrue(element.find(), "premise: the saved configuration holds the incidentResults element: " + xml);
        StringBuilder stored = new StringBuilder("<incidentResults>");
        for (String name : names) {
            stored.append("<string>").append(name).append("</string>");
        }
        stored.append("</incidentResults>");
        Files.writeString(file, element.replaceFirst(Matcher.quoteReplacement(stored.toString())), StandardCharsets.UTF_8);

        List<String> read;
        List<String> warnings = new ArrayList<>();
        try (LogRecorder log = new LogRecorder().record("io.jenkins.plugins.batchcontrol", Level.WARNING).capture(100)) {
            cfg.load();
            read = new ArrayList<>(BatchControlGlobalConfiguration.get().getIncidentResults());
            BatchControlGlobalConfiguration.get().getIncidentResults(); // a second read logs nothing more
            for (LogRecord r : log.getRecords()) {
                String message = new SimpleFormatter().formatMessage(r);
                if (r.getLevel().intValue() >= Level.WARNING.intValue()
                        && (message.contains("SUCCESS") || message.contains("NOT_BUILT"))) {
                    warnings.add(message);
                }
            }
        }
        List<String> dropped = new ArrayList<>();
        for (String name : names) {
            if (name.equals("SUCCESS") || name.equals("NOT_BUILT")) {
                dropped.add(name);
            }
        }
        assertEquals(1, warnings.size(), "reading a stored value holding " + dropped + " must log exactly one warning"
                + " naming the dropped names, got " + warnings);
        for (String name : dropped) {
            assertTrue(warnings.get(0).contains(name), "the warning must name " + name + ": " + warnings.get(0));
        }
        return read;
    }

    private Path configFile() {
        Path file = j.jenkins.getRootDir().toPath().resolve(BatchControlGlobalConfiguration.class.getName() + ".xml");
        assertTrue(Files.isRegularFile(file), "premise: the configuration is saved as " + file);
        return file;
    }

    private static String incidentElement(String xml) {
        Matcher m = Pattern.compile("(?s)<incidentResults\\b.*?</incidentResults>").matcher(xml);
        return m.find() ? m.group() : xml;
    }

    /** A plain build of a new job ending with {@code result}; the incident it opened, or null. */
    private Incident incidentAfter(String name, String result) throws Exception {
        FreeStyleProject job = j.createFreeStyleProject(name);
        job.getBuildersList().add(new ResultFixtures.SetResult(result));
        j.buildAndAssertStatus(Result.fromString(result), job);
        j.waitUntilNoActivity();
        return IncidentService.get().list(YearMonth.now(BatchClock.clock())).stream()
                .filter(i -> (name + "#1").equals(i.getRunId())).findFirst().orElse(null);
    }

    private WebResponse check(String field, String value) throws Exception {
        JenkinsRule.WebClient wc = j.createWebClient().withThrowExceptionOnFailingStatusCode(false).login("manager");
        URL url = new URL(wc.createCrumbedUrl(DESCRIPTOR + field).toExternalForm() + "&value="
                + URLEncoder.encode(value, StandardCharsets.UTF_8));
        WebResponse r = wc.getPage(new WebRequest(url, HttpMethod.POST)).getWebResponse();
        assertEquals(200, r.getStatusCode(), field + " must be served to the manager");
        return r;
    }

    private static boolean isError(WebResponse r) {
        String body = r.getContentAsString();
        return body.contains("class=\"error\"") || body.contains("class=error") || body.contains("class='error'");
    }

    /** {@code user} opens {@code path}, types {@code value} into the incident results field and saves. */
    private Page save(String user, String path, String value) throws Exception {
        JenkinsRule.WebClient wc = j.createWebClient().withThrowExceptionOnFailingStatusCode(false).login(user);
        Page opened = wc.getPage(new WebRequest(new URL(j.getURL(), path), HttpMethod.GET));
        assertEquals(200, opened.getWebResponse().getStatusCode(), "fixture: " + user + " opens " + path);
        HtmlForm form = null;
        for (HtmlForm candidate : ((HtmlPage) opened).getForms()) {
            if (UsabilityFixtures.hasField(candidate, "pendingTimeoutHours")) {
                form = candidate;
            }
        }
        assertNotNull(form, "fixture: " + path + " carries the Batch Control settings");
        UsabilityFixtures.setField(form, "incidentResults", value);
        return j.submit(form);
    }

    /** A refused save: not answered as a success, and the setting is still the default. */
    private static void assertRefusedSave(String what, Page answer) {
        int code = answer.getWebResponse().getStatusCode();
        String landed = UsabilityFixtures.stripQueryAndSlash(answer.getUrl().toExternalForm());
        assertTrue(code >= 400 || !(landed.endsWith("/manage") || landed.endsWith("/batch-control-configuration")
                        || landed.endsWith("/batch-control")), what + ": must not be answered as a successful save (HTTP "
                + code + ", landed on " + landed + ")");
        List<String> after = BatchControlGlobalConfiguration.get().getIncidentResults();
        assertEquals(DEFAULT, after, what + ": nothing may be saved; the setting must stay [FAILURE, UNSTABLE]");
    }

    private static void casc(String value) throws Exception {
        String yaml = "unclassified:\n  batchControl:\n    incidentResultsText: \"" + value + "\"\n";
        io.jenkins.plugins.casc.ConfigurationAsCode.get().configureWith(io.jenkins.plugins.casc.yaml.YamlSource.of(
                new ByteArrayInputStream(yaml.getBytes(StandardCharsets.UTF_8))));
    }
}
