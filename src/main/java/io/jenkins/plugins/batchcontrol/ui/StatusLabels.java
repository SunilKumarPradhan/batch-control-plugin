package io.jenkins.plugins.batchcontrol.ui;

import edu.umd.cs.findbugs.annotations.CheckForNull;
import hudson.model.Result;
import io.jenkins.plugins.batchcontrol.model.CauseType;
import io.jenkins.plugins.batchcontrol.model.IncidentStatus;
import io.jenkins.plugins.batchcontrol.model.RequestStatus;
import java.util.ArrayList;
import java.util.Collection;
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
 * <p>A request, grant or activation status and an incident status are shown as a colour badge:
 * {@link #tone} names the badge's tone, which the element carries in
 * {@code data-batch-control-tone} and the plugin stylesheet colours from the theme. The tone
 * follows the constant, never a page's own wording of the label. A run cause has no tone and
 * stays plain text. The one exception is {@link #endedTone}: in the Ended table of the grants
 * list and of the activations list an approved request is no longer in effect, so it is neutral
 * there, whatever the cell words; the caller says where the badge is, the label is not looked at.
 *
 * <p>Each enum is mapped by a switch expression without a default branch, so a new constant
 * without a label or a tone does not compile. Views reach this class through
 * {@code BatchControlRootAction#statusLabel} and {@code #statusTone} (never
 * {@code j:invokeStatic}, which cannot see plugin classes in a real Jenkins).
 */
@Restricted(NoExternalUse.class)
public final class StatusLabels {

    /** Tone of a status that waits for someone: a pending request, an acknowledged incident. */
    private static final String TONE_WARNING = "warning";

    /** Tone of a status that is decided and under way: an approved request. */
    private static final String TONE_INFO = "info";

    /** Tone of a status that ended well: an executed request, a resolved incident. */
    private static final String TONE_SUCCESS = "success";

    /** Tone of a status that needs attention or was refused: a rejected request, an open incident. */
    private static final String TONE_DANGER = "danger";

    /** Tone of a status that ended without a decision or a run: cancelled, expired, invalidated. */
    private static final String TONE_NEUTRAL = "neutral";

    /** The run request page's wording for an approved request whose run has not started yet. */
    public static final String APPROVED_WAITING_TO_RUN = "Approved, waiting to run";

    /** The label of a build that has no result yet because it is still running. */
    public static final String IN_PROGRESS = "In progress";

    /** The results a run can carry, best first (core's order). */
    private static final List<Result> RESULTS =
            List.of(Result.SUCCESS, Result.UNSTABLE, Result.FAILURE, Result.NOT_BUILT, Result.ABORTED);

    /**
     * The results that can open an incident (SPEC 11): FAILURE and UNSTABLE by default, ABORTED
     * the one that may be added. Fixed, not read from {@code incidentResults}, so an incident
     * recorded under an earlier setting stays searchable.
     */
    private static final List<Result> INCIDENT_RESULTS = List.of(Result.FAILURE, Result.UNSTABLE, Result.ABORTED);

    private StatusLabels() {}

    /** The result names the runs' Result filter offers, best first. */
    public static List<String> resultNames() {
        return RESULTS.stream().map(Result::toString).toList();
    }

    /** The result names the incidents' Result filter offers: the results that can open an incident. */
    public static List<String> incidentResultNames() {
        return INCIDENT_RESULTS.stream().map(Result::toString).toList();
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
     * The tone of the badge showing {@code value}, in lower case ({@code warning}, {@code info},
     * {@code success}, {@code danger} or {@code neutral}), for a {@link RequestStatus} or an
     * {@link IncidentStatus}; {@code null} for anything else (a run cause, {@code null}), which is
     * not a badge.
     */
    @CheckForNull
    public static String tone(@CheckForNull Enum<?> value) {
        if (value instanceof RequestStatus s) {
            return requestTone(s);
        }
        if (value instanceof IncidentStatus s) {
            return incidentTone(s);
        }
        return null;
    }

    /**
     * The tone of the badge showing {@code value} in an Ended table (the grants list, the
     * activations list): an {@link RequestStatus#APPROVED} request listed there is no longer in
     * effect (its window expired or was revoked, or a later approval replaced it), so it is
     * {@code neutral}; every other value has its {@link #tone}. Everywhere else an approved
     * request is {@code info}.
     */
    @CheckForNull
    public static String endedTone(@CheckForNull Enum<?> value) {
        return value == RequestStatus.APPROVED ? TONE_NEUTRAL : tone(value);
    }

    /**
     * The label of a run request's status: an approved run request is one whose run has not
     * started yet (it becomes {@link RequestStatus#EXECUTED} when it does).
     */
    public static String ofRunRequest(@CheckForNull RequestStatus status) {
        return status == RequestStatus.APPROVED ? APPROVED_WAITING_TO_RUN : of(status);
    }

    /**
     * The label of a build result, worded as core's status icons in English: the one mapping
     * behind the Result filter options and every result cell (the incidents list, the incident
     * page, History, the dashboard, the run request page's Build table), so the two cannot drift
     * apart. A result is plain text, never a badge (no {@link #tone}). The name itself for a value
     * that is not a result name; an empty string for {@code null}. CSV exports keep the name.
     */
    public static String ofResult(@CheckForNull String result) {
        if (result == null) {
            return "";
        }
        return switch (result) {
            case "SUCCESS" -> "Success";
            case "UNSTABLE" -> "Unstable";
            case "FAILURE" -> "Failed";
            case "NOT_BUILT" -> "Not built";
            case "ABORTED" -> "Aborted";
            default -> result;
        };
    }

    /**
     * #6 (Wave D, D3): the build result named exactly {@code name} (one of {@link #resultNames}),
     * or {@code null} for anything else, which the Run cell shows as text without a status icon.
     */
    @CheckForNull
    public static Result resultOf(@CheckForNull String name) {
        for (Result r : RESULTS) {
            if (r.toString().equals(name)) {
                return r;
            }
        }
        return null;
    }

    /**
     * The opening of the incidents list's introduction: the configured {@code incidentResults}
     * that can open an incident, as their labels ({@link #ofResult}) in lower case after the first
     * word, in the order of {@link #incidentResultNames} whatever order the setting holds, joined
     * with commas and a final "and", then "builds" ({@code Failed and unstable builds} under the
     * default setting). An empty string when the setting names none of them (the configuration
     * never stores an empty list); the view then leaves the sentence out.
     */
    public static String incidentResultsOpening(@CheckForNull Collection<String> configured) {
        List<String> words = new ArrayList<>();
        if (configured != null) {
            for (String name : incidentResultNames()) {
                if (configured.stream().anyMatch(name::equalsIgnoreCase)) {
                    String label = ofResult(name);
                    words.add(words.isEmpty() ? label : label.toLowerCase(Locale.ROOT));
                }
            }
        }
        if (words.isEmpty()) {
            return "";
        }
        int last = words.size() - 1;
        String joined = last == 0
                ? words.get(0)
                : String.join(", ", words.subList(0, last)) + " and " + words.get(last);
        return joined + " builds";
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

    private static String requestTone(RequestStatus status) {
        return switch (status) {
            case PENDING -> TONE_WARNING;
            case APPROVED -> TONE_INFO;
            case EXECUTED -> TONE_SUCCESS;
            case REJECTED -> TONE_DANGER;
            case CANCELLED, EXPIRED, INVALIDATED -> TONE_NEUTRAL;
        };
    }

    private static String incidentTone(IncidentStatus status) {
        return switch (status) {
            case OPEN -> TONE_DANGER;
            case ACKNOWLEDGED -> TONE_WARNING;
            case RESOLVED -> TONE_SUCCESS;
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
