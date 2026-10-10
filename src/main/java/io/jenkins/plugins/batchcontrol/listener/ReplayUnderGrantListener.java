package io.jenkins.plugins.batchcontrol.listener;

import hudson.Extension;
import hudson.model.Run;
import hudson.model.listeners.RunListener;
import io.jenkins.plugins.batchcontrol.model.ChangeRecord;
import io.jenkins.plugins.batchcontrol.model.ChangeType;
import io.jenkins.plugins.batchcontrol.queue.ReplayUnderGrantAction;
import io.jenkins.plugins.batchcontrol.security.GrantService;
import io.jenkins.plugins.batchcontrol.store.Store;
import java.util.logging.Level;
import java.util.logging.Logger;
import org.kohsuke.accmod.Restricted;
import org.kohsuke.accmod.restrictions.NoExternalUse;

/**
 * D-58c: when a run marked {@link ReplayUnderGrantAction} starts, a {@code REPLAY_UNDER_GRANT}
 * change record names the user, the run and the grant, and the run is added to the marked runs
 * the review surfaces list. Never throws.
 *
 * <p>#1.1: a re-run of a marked run is marked whatever the switches say. The record follows the
 * activity gate of every other record (D-13, SPEC item 9: written while either switch is on), so
 * with both switches off the run is marked and listed but nothing is written.
 */
@Extension
@Restricted(NoExternalUse.class)
public class ReplayUnderGrantListener extends RunListener<Run<?, ?>> {

    private static final Logger LOGGER = Logger.getLogger(ReplayUnderGrantListener.class.getName());

    @Override
    public void onStarted(Run<?, ?> run, hudson.model.TaskListener listener) {
        ReplayUnderGrantAction marker = run.getAction(ReplayUnderGrantAction.class);
        if (marker == null) {
            return;
        }
        String job = run.getParent().getFullName();
        String runId = job + "#" + run.getNumber();
        if (!ChangeRecording.isActive()) {
            GrantService.get().noteMarkedRun(job, runId);
            return;
        }
        try {
            // #1.2 (S-31-02): a carried mark names the re-runner as the record's user and the
            // grant-only user who replayed the script in the text; it never says the re-runner's
            // permission came from a window.
            String replayedBy = marker.getReplayedBy();
            String detail = marker.getInheritedFrom() != null
                    ? "Run #" + run.getNumber() + " was started by '" + marker.getUser() + "' as a re-run of run #"
                            + marker.getInheritedFrom() + (replayedBy != null
                                    ? ", which goes back to a script '" + replayedBy + "' replayed under a permission window;"
                                    : ", whose script was replayed under a permission window;")
                            + " it carries the same mark and cannot be re-run except by an administrator."
                    :"Run #" + run.getNumber() + " was started by a Replay, Pipeline Rebuild or Restart from Stage"
                            + " by '" + marker.getUser() + "' whose permission came only from a permission window;"
                            + " it cannot be re-run except by an administrator.";
            ChangeRecord record = ChangeRecord.create(ChangeType.REPLAY_UNDER_GRANT, job, marker.getUser(), detail);
            record.setGrantId(marker.getGrantId());
            Store.get().appendChangeRecord(record);
        } catch (RuntimeException e) {
            LOGGER.log(Level.SEVERE, "Could not record the replay under a grant of " + runId, e);
        }
        GrantService.get().noteMarkedRun(job, runId);
    }
}
