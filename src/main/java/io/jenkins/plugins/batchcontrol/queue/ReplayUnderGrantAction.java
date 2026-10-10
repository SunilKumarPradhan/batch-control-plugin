package io.jenkins.plugins.batchcontrol.queue;

import edu.umd.cs.findbugs.annotations.CheckForNull;
import hudson.model.InvisibleAction;
import org.kohsuke.accmod.Restricted;
import org.kohsuke.accmod.restrictions.NoExternalUse;

/**
 * D-58c: the hidden marker of a run started by a Replay, Pipeline Rebuild or Restart from Stage
 * that a user whose permission for it came only from a grant submitted. It travels with the queue
 * item onto the run and is saved in the run's {@code build.xml}. A later re-run whose source is a
 * marked run is refused for everyone but an administrator, before and after the review, because
 * the replayed script is not part of the job's configuration a reviewer looks at.
 */
@Restricted(NoExternalUse.class)
public final class ReplayUnderGrantAction extends InvisibleAction {

    private final String user;
    private final String grantId;
    /**
     * e2e-03 DEF-40: the number of the marked run this run re-runs, when the marker was inherited
     * (for example an administrator's allowed re-run); {@code null} when the submitter's own
     * grant-only permission caused the mark.
     */
    private final Integer inheritedFrom;
    /**
     * #1.2 (S-31-02): for an inherited marker, the grant-only user who replayed the script the
     * chain of re-runs goes back to; {@code null} for an own mark (that is {@link #user}) and for
     * an inherited marker saved before this field existed.
     */
    @CheckForNull
    private final String replayedBy;

    public ReplayUnderGrantAction(String user, String grantId) {
        this(user, grantId, null, null);
    }

    public ReplayUnderGrantAction(String user, String grantId, Integer inheritedFrom) {
        this(user, grantId, inheritedFrom, null);
    }

    public ReplayUnderGrantAction(String user, String grantId, Integer inheritedFrom, @CheckForNull String replayedBy) {
        this.user = user;
        this.grantId = grantId;
        this.inheritedFrom = inheritedFrom;
        this.replayedBy = inheritedFrom == null ? null : replayedBy;
    }

    public Integer getInheritedFrom() {
        return inheritedFrom;
    }

    /** Who started this run: the grant-only replayer for an own mark, the re-runner for an inherited one. */
    public String getUser() {
        return user;
    }

    public String getGrantId() {
        return grantId;
    }

    /**
     * #1.2: the grant-only user who replayed the script this mark goes back to: {@link #getUser()}
     * for an own mark, the original replayer for an inherited one, {@code null} when an inherited
     * marker saved before #1.2 does not say.
     */
    @CheckForNull
    public String getReplayedBy() {
        return inheritedFrom == null ? user : replayedBy;
    }
}
