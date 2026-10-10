package io.jenkins.plugins.batchcontrol.policy;

import io.jenkins.plugins.batchcontrol.model.RequestStatus;
import org.kohsuke.accmod.Restricted;
import org.kohsuke.accmod.restrictions.NoExternalUse;

/**
 * #1.7 (e2e-05 EX-01): the refusal of a change that applies only while a request is PENDING (its
 * designated approvers), when the request is already decided or otherwise ended. Nothing about
 * the submitted input is wrong, so a screen shows the message as a plain refusal of the whole
 * request, not next to a field. The message names the request's current status, for example
 * "This run request is already APPROVED; its approvers can no longer be changed."
 *
 * <p>An {@link IllegalStateException}, like every other state refusal of the services, so a
 * caller that does not know this type still refuses the change.
 */
@Restricted(NoExternalUse.class)
public final class RequestNotPendingException extends IllegalStateException {

    private static final long serialVersionUID = 1L;

    private final RequestStatus status;

    RequestNotPendingException(String kind, RequestStatus status) {
        super("This " + kind + " is already " + status + "; its approvers can no longer be changed.");
        this.status = status;
    }

    /** The request's status when the change was refused (never PENDING). */
    public RequestStatus getStatus() {
        return status;
    }
}
