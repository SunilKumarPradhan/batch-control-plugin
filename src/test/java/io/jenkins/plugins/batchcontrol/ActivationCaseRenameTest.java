package io.jenkins.plugins.batchcontrol;

import com.cloudbees.hudson.plugins.folder.Folder;
import hudson.model.Cause;
import hudson.model.FreeStyleBuild;
import hudson.model.FreeStyleProject;
import hudson.model.Item;
import hudson.security.ACL;
import hudson.security.ACLContext;
import hudson.triggers.TimerTrigger;
import io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration;
import io.jenkins.plugins.batchcontrol.config.BatchControlJobProperty;
import io.jenkins.plugins.batchcontrol.security.BatchControlPermissions;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicReference;
import jenkins.model.Jenkins;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.RegisterExtension;
import org.jvnet.hudson.test.JenkinsRule;
import org.jvnet.hudson.test.MockAuthorizationStrategy;
import org.jvnet.hudson.test.junit.jupiter.JenkinsSessionExtension;

import static io.jenkins.plugins.batchcontrol.ActivationFixtures.isActivated;
import static io.jenkins.plugins.batchcontrol.ApproverFormFixtures.get;
import static io.jenkins.plugins.batchcontrol.BatchControlFixtures.activate;
import static io.jenkins.plugins.batchcontrol.BatchControlFixtures.setBatchControl;
import static io.jenkins.plugins.batchcontrol.BatchControlFixtures.token;
import static io.jenkins.plugins.batchcontrol.BatchControlFixtures.uncontrolled;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Issue #32 (TEST-MATRIX note 342, rows T-06a-112 and T-06a-113): a case-only rename keeps the job's activation.
 * After {@code Job.renameTo} / {@code AbstractItem.renameTo} changes only the case of a job's or a folder's name
 * (a script or Job DSL can; the UI refuses it), the job is still activated, also after a restart, and its timer
 * and upstream runs still pass when it was activated with both switches cleared.
 *
 * <p>The defect needs a case-insensitive file system (default APFS on macOS, NTFS on Windows), where
 * {@code Nightly.xml} and {@code nightly.xml} name the same file. Each row reports which kind of file system
 * {@code JENKINS_HOME} is on (a probe file looked up under another case) and asserts the same behaviour on both:
 * on a case-sensitive file system (the Linux CI groups) the rows are the guard. Each row also renames a second
 * activated job to a different name (not case-only), which must keep its activation everywhere (SPEC 6a), so a
 * red row is red because the rename was case-only.
 *
 * <p>Basis: SPEC 6a ("an activation is per job and survives configuration edits; renaming or moving a job keeps
 * its activation"; "for any unattended cause ... the queue gate passes only if the job is activated AND its
 * {@code blockTimer}/{@code blockUpstream} does not block the cause"; the job page shows the state), SPEC 4
 * (restart durability), ARCHITECTURE 5 ("Rename/move relocates the state file"), issue #32 and the wave-B
 * contract (main session, 2026-10-10).
 *
 * <p>Written from docs/SPEC.md items 4 and 6a, docs/ARCHITECTURE.md section 5, issue #32 and the wave-B contract
 * only (no src/main knowledge).
 */
public class ActivationCaseRenameTest {

    @RegisterExtension
    final JenkinsSessionExtension session = new JenkinsSessionExtension();

    /**
     * T-06a-112 (P0, #32): {@code Nightly} and {@code Weekly} are activated with cleared switches. A script renames
     * {@code Nightly} to {@code nightly} (case only) and {@code Weekly} to {@code weekly-renamed}. In the same
     * session {@code nightly} is activated and its timer runs; after a restart {@code nightly} is still activated,
     * its timer and an upstream run pass and its page says it is activated. Guard: {@code weekly-renamed} is
     * activated after the restart.
     */
    @Test
    public void t_06a_112_caseOnlyJobRenameKeepsTheActivationAcrossARestart() throws Throwable {
        AtomicReference<String> fileSystem = new AtomicReference<>();
        session.then(r -> {
            secure(r);
            fileSystem.set(fileSystemKind(r));
            FreeStyleProject job = cleared(r.createFreeStyleProject("Nightly"));
            activate(job, "u1", "a1");
            FreeStyleProject guard = cleared(r.createFreeStyleProject("Weekly"));
            activate(guard, "u1", "a1");

            job.renameTo("nightly");
            guard.renameTo("weekly-renamed");

            assertEquals("nightly", job.getFullName(), "premise: the case-only rename was applied");
            assertTrue(isActivated(job), "#32 (" + fileSystem.get() + "): nightly is activated right after the case-only rename");
            r.assertBuildStatusSuccess(job.scheduleBuild2(0, new TimerTrigger.TimerTriggerCause()));
        });
        session.then(r -> {
            secure(r);
            FreeStyleProject guard = r.jenkins.getItemByFullName("weekly-renamed", FreeStyleProject.class);
            assertNotNull(guard, "premise: weekly-renamed exists after the restart");
            assertTrue(isActivated(guard), "guard (SPEC 6a): a renamed job keeps its activation across a restart");
            FreeStyleProject job = r.jenkins.getItemByFullName("nightly", FreeStyleProject.class);
            assertNotNull(job, "premise: nightly exists after the restart");
            assertKeepsActivation(r, job, fileSystem.get(), "the job was renamed from Nightly");
        });
    }

    /**
     * T-06a-113 (P0, #32): folder {@code Team} holds {@code etl}, activated with cleared switches; folder
     * {@code Ops} holds {@code etl}, activated too. A script renames {@code Team} to {@code team} (case only) and
     * {@code Ops} to {@code ops-renamed}. In the same session {@code team/etl} is activated; after a restart it is
     * still activated, its timer and an upstream run pass and its page says it is activated. Guard:
     * {@code ops-renamed/etl} is activated after the restart.
     */
    @Test
    public void t_06a_113_caseOnlyFolderRenameKeepsTheActivationOfItsJobsAcrossARestart() throws Throwable {
        AtomicReference<String> fileSystem = new AtomicReference<>();
        session.then(r -> {
            secure(r);
            fileSystem.set(fileSystemKind(r));
            Folder team = r.jenkins.createProject(Folder.class, "Team");
            FreeStyleProject job = cleared(team.createProject(FreeStyleProject.class, "etl"));
            activate(job, "u1", "a1");
            Folder ops = r.jenkins.createProject(Folder.class, "Ops");
            FreeStyleProject guard = cleared(ops.createProject(FreeStyleProject.class, "etl"));
            activate(guard, "u1", "a1");

            team.renameTo("team");
            ops.renameTo("ops-renamed");

            assertEquals("team/etl", job.getFullName(), "premise: the case-only folder rename was applied");
            assertTrue(isActivated(job), "#32 (" + fileSystem.get() + "): team/etl is activated right after the case-only folder rename");
            r.assertBuildStatusSuccess(job.scheduleBuild2(0, new TimerTrigger.TimerTriggerCause()));
        });
        session.then(r -> {
            secure(r);
            FreeStyleProject guard = r.jenkins.getItemByFullName("ops-renamed/etl", FreeStyleProject.class);
            assertNotNull(guard, "premise: ops-renamed/etl exists after the restart");
            assertTrue(isActivated(guard), "guard (SPEC 6a): a job in a renamed folder keeps its activation across a restart");
            FreeStyleProject job = r.jenkins.getItemByFullName("team/etl", FreeStyleProject.class);
            assertNotNull(job, "premise: team/etl exists after the restart");
            assertKeepsActivation(r, job, fileSystem.get(), "its folder was renamed from Team");
        });
    }

    // ------------------------------------------------------------------ helpers

    private static void assertKeepsActivation(JenkinsRule r, FreeStyleProject job, String fileSystem, String how) throws Exception {
        String what = "#32 (" + fileSystem + "): " + job.getFullName() + ", activated before " + how + " by a case-only rename,";
        assertTrue(isActivated(job), what + " must still be activated after the restart");
        assertTrue(job.scheduleBuild2(0, new TimerTrigger.TimerTriggerCause()) != null, what + " must still accept its timer run");
        r.waitUntilNoActivity();
        assertNotNull(job.scheduleBuild2(0, new Cause.UpstreamCause(upstreamBuild(r, job.getName() + "-feeder"))),
                what + " must still accept an upstream run");
        r.waitUntilNoActivity();
        String page = get(r, "u1", job.getUrl()).getContentAsString().toLowerCase(Locale.ROOT);
        assertTrue(page.contains("activated") && !page.contains("not activated") && !page.contains("on hold"),
                what + " must say on its page that it is activated");
    }

    /** A finished build of an uncontrolled helper job, started by the administrator (a human cause). */
    private static FreeStyleBuild upstreamBuild(JenkinsRule r, String name) throws Exception {
        FreeStyleProject upstream = uncontrolled(r.createFreeStyleProject(name));
        try (ACLContext ignored = ACL.as2(token("admin"))) {
            return r.assertBuildStatusSuccess(upstream.scheduleBuild2(0, new Cause.UserIdCause()));
        }
    }

    /**
     * Whether {@code JENKINS_HOME} is on a case-insensitive file system: a probe file is looked up under its
     * lower-case name. Printed, and named in every assertion message of the row.
     */
    private static String fileSystemKind(JenkinsRule r) throws Exception {
        Path home = r.jenkins.getRootDir().toPath();
        Path probe = home.resolve("CaseProbe-" + System.nanoTime());
        Files.createFile(probe);
        boolean insensitive;
        try {
            Path other = home.resolve(probe.getFileName().toString().toLowerCase(Locale.ROOT));
            insensitive = Files.exists(other) && Files.isSameFile(probe, other);
        } finally {
            Files.delete(probe);
        }
        String kind = insensitive ? "case-insensitive file system" : "case-sensitive file system";
        System.out.println("ActivationCaseRenameTest: JENKINS_HOME " + home + " is on a " + kind);
        assertFalse(Files.exists(probe), "fixture: the probe file is removed");
        return kind;
    }

    /** Run control on, approvers a1 (applied in every session). */
    private static void secure(JenkinsRule r) throws Exception {
        r.jenkins.setSecurityRealm(r.createDummySecurityRealm());
        r.jenkins.setAuthorizationStrategy(new MockAuthorizationStrategy()
                .grant(Jenkins.ADMINISTER).everywhere().to("admin")
                .grant(Jenkins.READ, Item.READ, BatchControlPermissions.REQUEST).everywhere().to("u1")
                .grant(Jenkins.READ, Item.READ, BatchControlPermissions.APPROVE).everywhere().to("a1"));
        BatchControlGlobalConfiguration cfg = BatchControlGlobalConfiguration.get();
        cfg.setRunControlEnabled(true);
        cfg.setApprovers(Arrays.asList("a1"));
        cfg.save();
    }

    /** Timer and upstream unblocked, so only the activation decides (D-46). */
    private static FreeStyleProject cleared(FreeStyleProject job) throws Exception {
        BatchControlJobProperty property = new BatchControlJobProperty(true);
        property.setBlockTimer(false);
        property.setBlockUpstream(false);
        setBatchControl(job, property);
        return job;
    }
}
