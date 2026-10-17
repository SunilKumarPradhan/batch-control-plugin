package io.jenkins.plugins.batchcontrol.ui;

import edu.umd.cs.findbugs.annotations.CheckForNull;
import hudson.model.Item;
import hudson.model.Job;
import hudson.model.Result;
import org.kohsuke.accmod.Restricted;
import org.kohsuke.accmod.restrictions.NoExternalUse;

/**
 * #6, #18.1 (Wave D, D3): the Run cell of the run tables (the Run Dashboard, History &gt; Runs) and
 * of the incident tables (the Incidents list, History &gt; Incidents), rendered by
 * {@code tags/runCell.jelly}: core's status icon of the result, the job, the {@code #n} run and the
 * result's readable label as visible plain text ({@link StatusLabels#ofResult}, the same words as
 * the Result filter; owner decision 2026-10-15). The result is never a badge. A result that is not
 * a build result (a record written by something else) has no icon and is shown as it is.
 *
 * <p>Links follow the one run-link rule (D-44): the job and the run link only for a viewer holding
 * {@code Item/Read} on the job, each to its own URL ({@link Job#getUrl()},
 * {@link Visibility#runUrl}, so a matrix configuration links where it lives, #42). A run deleted
 * since it was recorded is plain text while its job still links. Every value is text for the view,
 * which escapes it.
 */
@Restricted(NoExternalUse.class)
public final class RunCell {

    private final String jobFullName;
    private final String runText;
    private final String resultLabel;
    @CheckForNull
    private final String iconSrc;
    @CheckForNull
    private final String jobUrl;
    @CheckForNull
    private final String runUrl;
    @CheckForNull
    private final String abortedBy;

    private RunCell(String jobFullName, String runText, String resultLabel, @CheckForNull String iconSrc,
            @CheckForNull String jobUrl, @CheckForNull String runUrl, @CheckForNull String abortedBy) {
        this.jobFullName = jobFullName;
        this.runText = runText;
        this.resultLabel = resultLabel;
        this.iconSrc = iconSrc;
        this.jobUrl = jobUrl;
        this.runUrl = runUrl;
        this.abortedBy = abortedBy;
    }

    /**
     * The cell of a run, for the user the calling thread runs as (never under {@code ACL.SYSTEM2}).
     *
     * @param jobFullName the job's full name as recorded
     * @param number the build number, or 0 or less when only {@code runId} is known
     * @param runId the recorded {@code jobFullName#number}, read when {@code number} is not given
     * @param result the recorded result name, possibly not a build result
     * @param abortedBy who aborted the run, or null
     */
    public static RunCell of(@CheckForNull String jobFullName, int number, @CheckForNull String runId,
            @CheckForNull String result, @CheckForNull String abortedBy) {
        int n = number > 0 ? number : numberOf(runId);
        String runText = n > 0 ? "#" + n : (runId == null ? "" : runId);
        String jobUrl = null;
        Job<?, ?> job = Visibility.findVisibleJob(jobFullName);
        if (job != null && job.hasPermission(Item.READ)) {
            jobUrl = job.getUrl();
        }
        String runUrl = jobUrl == null ? null : Visibility.runUrl(jobFullName, n);
        Result known = StatusLabels.resultOf(result);
        String iconSrc = known == null ? null : "symbol-status-" + known.color.getIconName();
        return new RunCell(jobFullName == null ? "" : jobFullName, runText, StatusLabels.ofResult(result), iconSrc,
                jobUrl, runUrl, abortedBy == null || abortedBy.isEmpty() ? null : abortedBy);
    }

    private static int numberOf(@CheckForNull String runId) {
        if (runId == null) {
            return 0;
        }
        int hash = runId.lastIndexOf('#');
        if (hash < 0 || hash == runId.length() - 1) {
            return 0;
        }
        try {
            return Integer.parseInt(runId.substring(hash + 1));
        } catch (NumberFormatException e) {
            return 0;
        }
    }

    public String getJobFullName() {
        return jobFullName;
    }

    /** {@code #n}, or the recorded run id when it holds no number. */
    public String getRunText() {
        return runText;
    }

    /** The result's readable label ({@code Failed}), or the recorded text of an unknown result; may be empty. */
    public String getResultLabel() {
        return resultLabel;
    }

    /** Core's status symbol ({@code symbol-status-red}), or null for a result that is not a build result. */
    @CheckForNull
    public String getIconSrc() {
        return iconSrc;
    }

    /** Root-relative job URL for a viewer with Item/Read, else null (plain text). */
    @CheckForNull
    public String getJobUrl() {
        return jobUrl;
    }

    /** Root-relative run URL for a viewer with Item/Read on a run that still exists, else null (plain text). */
    @CheckForNull
    public String getRunUrl() {
        return runUrl;
    }

    /** Who aborted the run, or null. */
    @CheckForNull
    public String getAbortedBy() {
        return abortedBy;
    }
}
