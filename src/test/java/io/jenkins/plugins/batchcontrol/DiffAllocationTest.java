package io.jenkins.plugins.batchcontrol;

import hudson.model.FreeStyleProject;
import io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration;
import io.jenkins.plugins.batchcontrol.model.ChangeRecord;
import io.jenkins.plugins.batchcontrol.model.ChangeType;
import io.jenkins.plugins.batchcontrol.store.BatchClock;
import io.jenkins.plugins.batchcontrol.store.FileStore;
import java.lang.management.ManagementFactory;
import java.time.YearMonth;
import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.jvnet.hudson.test.JenkinsRule;
import org.jvnet.hudson.test.junit.jupiter.WithJenkins;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * #35: the diff of a changed save of a large job configuration must not allocate memory quadratic in the
 * number of lines on the saving thread. Matrix rows T-09-90 .. T-09-92 (note 350).
 *
 * <p>Basis: SPEC item 9 ("CONFIGURE 변경에 unified diff가 저장된다"; recording is active while either switch is
 * on); SPEC 6 (non-functional: the plugin must not endanger the controller); the #35 contract (frozen
 * 2026-10-10): "Saving a changed configuration of N lines allocates memory roughly linear in N, not N x N
 * ... The recorded diff is still correct. Beyond the existing size cap, the 'too large to diff' behaviour is
 * unchanged."
 *
 * <p>The measurement is {@code com.sun.management.ThreadMXBean#getThreadAllocatedBytes} of the test thread
 * around {@code setDescription}, which saves the job on that thread; a {@code SaveableListener} runs
 * synchronously inside the save. The plugin's share is the allocation of the recorded save minus the
 * allocation of the same save of a same-sized job while recording is off (both switches off), so Jenkins'
 * own XStream cost is not counted. Each measured save follows one warm-up save of the same size.
 *
 * <p>The large configuration is a freestyle job whose description holds {@value #LINES} lines (one
 * config.xml line each), with every 100th line changed (40 scattered changes). {@value #LINES} lines, not
 * the contract's example of 5,000: on main a configuration of about 4,800 lines or more is already beyond the
 * existing size cap ("Diff too large to store (N lines) ..."), so 5,000 lines cannot show the defect;
 * 4,000 stays clear of that cap.
 *
 * <p>Written from docs/SPEC.md, docs/TEST-MATRIX.md and the #35 contract only (no src/main knowledge).
 */
@WithJenkins
public class DiffAllocationTest {

    static final int LINES = 4000;
    /** The plugin's share of one changed save, in bytes (note 350). */
    static final long LIMIT = 16L * 1024 * 1024;

    private JenkinsRule j;
    private BatchControlGlobalConfiguration cfg;

    @BeforeEach
    public void setUp(JenkinsRule rule) throws Exception {
        this.j = rule;
        cfg = BatchControlGlobalConfiguration.get();
    }

    /**
     * T-09-90 (#35): run control on (recording active). A {@value #LINES}-line configuration with 40
     * scattered changed lines is saved: the plugin's share of the allocation on the saving thread (the
     * recorded save minus the same save with recording off) is under 16 MB. On main the diff allocates an
     * (m+1) x (n+1) table, about 64 MB for this size. Guard: exactly one new CONFIGURE record, and its diff
     * is a real diff (not the "too large" placeholder) that holds exactly the 40 changed lines.
     */
    @Test
    public void t_09_90_largeChangedSaveAllocatesLinearly() throws Exception {
        String base = text(LINES, 0);
        String warm = text(LINES, 1);
        String changed = text(LINES, 2);

        FreeStyleProject control = j.createFreeStyleProject("control-big");
        control.setDescription(base);
        control.setDescription(warm);
        long unrecorded = allocatedBy(() -> control.setDescription(changed));
        assertTrue(records("control-big").isEmpty(), "premise: with both switches off nothing is recorded");

        cfg.setRunControlEnabled(true);
        cfg.save();
        FreeStyleProject job = j.createFreeStyleProject("big");
        job.setDescription(base);
        job.setDescription(warm);
        int before = records("big").size();
        long recorded = allocatedBy(() -> job.setDescription(changed));
        long share = recorded - unrecorded;
        System.out.println("T-09-90 observation: recorded save " + recorded + " bytes, unrecorded save " + unrecorded
                + " bytes, plugin share " + share + " bytes, limit " + LIMIT);

        List<ChangeRecord> after = records("big");
        assertEquals(before + 1, after.size(), "guard: the changed save writes exactly one CONFIGURE record");
        assertChangedLines(after.get(after.size() - 1).getDiff(), LINES, 1, 2);
        assertTrue(share < LIMIT, "#35: the plugin's share of one changed save of a " + LINES + "-line configuration must stay"
                + " under " + LIMIT + " bytes (linear in the size, not N x N); measured " + share + " bytes (recorded save "
                + recorded + ", the same save unrecorded " + unrecorded + ")");
    }

    /**
     * T-09-91 (#35 guard, SPEC 9): a small change of a three-line description (the middle line changed) is
     * recorded with a unified diff that removes exactly the old middle line, adds exactly the new one, and
     * keeps the two other lines as context.
     */
    @Test
    public void t_09_91_smallChangeDiffIsStillCorrect() throws Exception {
        cfg.setRunControlEnabled(true);
        cfg.save();
        FreeStyleProject job = j.createFreeStyleProject("small");
        job.setDescription("alpha-line\nbravo-line\ncharlie-line");
        int before = records("small").size();
        job.setDescription("alpha-line\nBRAVO-CHANGED\ncharlie-line");
        List<ChangeRecord> after = records("small");
        assertEquals(before + 1, after.size(), "the change writes exactly one CONFIGURE record");
        String diff = after.get(after.size() - 1).getDiff();
        assertNotNull(diff, "the CONFIGURE record carries a diff");
        assertTrue(diff.contains("@@"), "the diff is unified (hunk header): " + diff);
        assertEquals(List.of("bravo-line"), contentLines(diff, '-'), "exactly the old middle line is removed: " + diff);
        assertEquals(List.of("BRAVO-CHANGED"), contentLines(diff, '+'), "exactly the new middle line is added: " + diff);
        assertTrue(contentLines(diff, ' ').stream().anyMatch(l -> l.endsWith("alpha-line"))
                && contentLines(diff, ' ').stream().anyMatch(l -> l.startsWith("charlie-line")),
                "the neighbouring lines are context: " + diff);
    }

    /**
     * T-09-92 (#35 guard, "beyond the existing size cap, the 'too large to diff' behaviour is unchanged"):
     * a 6,000-line configuration with scattered changes is saved: exactly one CONFIGURE record, whose diff is
     * the placeholder "Diff too large to store (N lines); the change was recorded without the full diff."
     * (the main behaviour, observed at 4,800 lines and more).
     */
    @Test
    public void t_09_92_beyondTheCapTheTooLargeNoteIsKept() throws Exception {
        cfg.setRunControlEnabled(true);
        cfg.save();
        FreeStyleProject job = j.createFreeStyleProject("huge");
        job.setDescription(text(6000, 0));
        int before = records("huge").size();
        job.setDescription(text(6000, 1));
        List<ChangeRecord> after = records("huge");
        assertEquals(before + 1, after.size(), "the change writes exactly one CONFIGURE record");
        String diff = String.valueOf(after.get(after.size() - 1).getDiff());
        assertTrue(diff.matches("Diff too large to store \\(\\d+ lines\\); the change was recorded without the full diff\\.\\s*"),
                "beyond the cap the record keeps the 'too large' note: " + diff.substring(0, Math.min(300, diff.length())));
    }

    // ------------------------------------------------------------------ helpers

    interface Step {
        void run() throws Exception;
    }

    /** Bytes allocated by the current thread while {@code step} runs. */
    static long allocatedBy(Step step) throws Exception {
        com.sun.management.ThreadMXBean mx = (com.sun.management.ThreadMXBean) ManagementFactory.getThreadMXBean();
        assertTrue(mx.isThreadAllocatedMemorySupported() && mx.isThreadAllocatedMemoryEnabled(),
                "premise: the JVM measures per-thread allocation");
        long id = Thread.currentThread().threadId();
        long before = mx.getThreadAllocatedBytes(id);
        step.run();
        return mx.getThreadAllocatedBytes(id) - before;
    }

    /** {@code lines} lines; when {@code salt > 0} every line numbered 50, 150, 250, ... carries {@code changed-<salt>}. */
    static String text(int lines, int salt) {
        StringBuilder sb = new StringBuilder();
        for (int i = 1; i <= lines; i++) {
            sb.append(line(i, salt)).append('\n');
        }
        return sb.toString();
    }

    private static String line(int i, int salt) {
        String n = String.valueOf(10000 + i).substring(1);
        String s = "line " + n + " of a large inline script, echo step " + n;
        return salt > 0 && i % 100 == 50 ? s + " changed-" + salt : s;
    }

    /** The diff removes exactly the changed lines of {@code oldSalt} and adds exactly those of {@code newSalt}. */
    private static void assertChangedLines(String diff, int lines, int oldSalt, int newSalt) {
        assertNotNull(diff, "the CONFIGURE record carries a diff");
        assertTrue(diff.contains("@@") && !diff.startsWith("Diff too large"),
                "guard: below the cap the record carries a real unified diff: " + diff.substring(0, Math.min(300, diff.length())));
        List<String> removed = new ArrayList<>();
        List<String> added = new ArrayList<>();
        for (int i = 50; i <= lines; i += 100) {
            removed.add(line(i, oldSalt));
            added.add(line(i, newSalt));
        }
        assertEquals(removed, contentLines(diff, '-'), "guard: the diff removes exactly the 40 old changed lines");
        assertEquals(added, contentLines(diff, '+'), "guard: the diff adds exactly the 40 new changed lines");
    }

    /** Content lines of a unified diff starting with {@code mark} (the header pair excluded), without the mark. */
    static List<String> contentLines(String diff, char mark) {
        List<String> out = new ArrayList<>();
        for (String l : diff.split("\n", -1)) {
            if (l.startsWith("---") || l.startsWith("+++") || l.startsWith("@@") || l.isEmpty()) {
                continue;
            }
            if (l.charAt(0) == mark) {
                out.add(l.substring(1));
            }
        }
        return out;
    }

    static List<ChangeRecord> records(String target) {
        return FileStore.get().listChangeRecords(YearMonth.now(BatchClock.clock())).stream()
                .filter(r -> r.getType() == ChangeType.CONFIGURE && target.equals(r.getTarget())).collect(Collectors.toList());
    }
}
