package io.jenkins.plugins.batchcontrol.ui;

import edu.umd.cs.findbugs.annotations.CheckForNull;
import hudson.model.Result;
import io.jenkins.plugins.batchcontrol.model.CauseType;
import io.jenkins.plugins.batchcontrol.model.IncidentStatus;
import io.jenkins.plugins.batchcontrol.model.RequestStatus;
import java.util.List;
import java.util.Locale;
import org.kohsuke.accmod.Restricted;
import org.kohsuke.accmod.restrictions.NoExternalUse;

/**
 * #18.2 (Wave D, D2): the readable label a screen shows for a request, grant or activation status,
 * an incident status or a run cause, instead of the enum name. The enum name stays the data:
 * the element showing a label carries it in {@code data-batch-control-status}
 * ({@code tags/status.jelly}), and CSV exports, filter tokens and the JSON summary keep it.
 *
 * <p>Each enum is mapped by a switch expression without a default branch, so a new constant
 * without a label does not compile. Views reach this class through
 * {@code BatchControlRootAction#statusLabel} (never {@code j:invokeStatic}, which cannot see
 * plugin classes in a real Jenkins).
 */
@Restricted(NoExternalUse.class)
public final class StatusLabels {

    /** The run request page's wording for an approved request whose run has not started yet. */
    public static final String APPROVED_WAITING_TO_RUN = "Approved, waiting to run";

    /** The results a run or an incident can carry, best first (core's order). */
    private static final List<Result> RESULTS =
            List.of(Result.SUCCESS, Result.UNSTABLE, Result.FAILURE, Result.NOT_BUILT, Result.ABORTED);

    private StatusLabels() {}

    /** The result names a Result filter offers, best first. */
    public static List<String> resultNames() {
        return RESULTS.stream().map(Result::toString).toList();
    }

    /**
     * The label of {@code value}; an empty string for {@code null}. An enum this class does not
     * know is shown as its name in sentence case, without underscores.
     */
    public static String of(@CheckForNull Enum<?> value) {
        if (value == null) {
            return "";
        }
        if (value instanceof RequestStatus s) {
            return request(s);
        }
        if (value instanceof IncidentStatus s) {
            return incident(s);
        }
        if (value instanceof CauseType c) {
            return cause(c);
        }
        return sentenceCase(value.name());
    }

    /**
     * The label of a run request's status: an approved run request is one whose run has not
     * started yet (it becomes {@link RequestStatus#EXECUTED} when it does).
     */
    public static String ofRunRequest(@CheckForNull RequestStatus status) {
        return status == RequestStatus.APPROVED ? APPROVED_WAITING_TO_RUN : of(status);
    }

    /**
     * A build result for a filter option or a tooltip, worded as core's status icons
     * ({@code BallColor#getDescription}); the name itself for a token that is not a result.
     */
    public static String ofResult(@CheckForNull String result) {
        if (result == null) {
            return "";
        }
        for (Result r : RESULTS) {
            if (r.toString().equals(result)) {
                return r.color.getDescription();
            }
        }
        return result;
    }


    private static String request(RequestStatus status) {
        return switch (status) {
            case PENDING -> "Pending";
            case APPROVED -> "Approved";
            case REJECTED -> "Rejected";
            case CANCELLED -> "Cancelled";
            case EXPIRED -> "Expired";
            case EXECUTED -> "Executed";
            case INVALIDATED -> "Invalidated";
        };
    }

    private static String incident(IncidentStatus status) {
        return switch (status) {
            case OPEN -> "Open";
            case ACKNOWLEDGED -> "Acknowledged";
            case RESOLVED -> "Resolved";
        };
    }

    private static String cause(CauseType cause) {
        return switch (cause) {
            case USER -> "User";
            case TIMER -> "Timer";
            case UPSTREAM -> "Upstream job";
            case APPROVED_REQUEST -> "Approved request";
            case SCM -> "SCM change";
            case OTHER -> "Other";
        };
    }

    private static String sentenceCase(String name) {
        String words = name.replace('_', ' ').toLowerCase(Locale.ROOT).trim();
        return words.isEmpty() ? name : Character.toUpperCase(words.charAt(0)) + words.substring(1);
    }
}
