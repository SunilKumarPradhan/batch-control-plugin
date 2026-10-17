package io.jenkins.plugins.batchcontrol.policy;

import org.kohsuke.accmod.Restricted;
import org.kohsuke.accmod.restrictions.NoExternalUse;

/**
 * D-88 (#1.9): a run request submission identical to a PENDING request of the same user was not
 * created. Nothing was stored, the submission's temporary files were disposed of and no approver
 * was notified. {@link #getExistingRequestId()} names the request the user already has; a browser
 * is sent to its page, a script is answered 409 naming it.
 *
 * <p>An {@link IllegalStateException}, like every other state refusal of the service, so a caller
 * that does not know this type still refuses the submission.
 */
@Restricted(NoExternalUse.class)
public final class IdenticalPendingRequestException extends IllegalStateException {

    private static final long serialVersionUID = 1L;

    private final String existingRequestId;

    IdenticalPendingRequestException(String existingRequestId) {
        super("An identical request of yours is already pending: " + existingRequestId
                + ". It was not submitted again.");
        this.existingRequestId = existingRequestId;
    }

    /** The id of the user's identical PENDING run request. */
    public String getExistingRequestId() {
        return existingRequestId;
    }
}
