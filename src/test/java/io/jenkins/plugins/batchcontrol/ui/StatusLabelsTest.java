package io.jenkins.plugins.batchcontrol.ui;

import io.jenkins.plugins.batchcontrol.model.CauseType;
import io.jenkins.plugins.batchcontrol.model.IncidentStatus;
import io.jenkins.plugins.batchcontrol.model.RequestStatus;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

/**
 * Wave D, group D2, issue #18 item 2 (matrix row T-UI-259, note 361), unit (no Jenkins): every
 * constant of every enum the screens label (request, grant and activation statuses share
 * {@link RequestStatus}; incident statuses; run causes) has a readable label, so a constant added
 * later without one fails here instead of showing its raw name on a screen.
 *
 * <p>Expected API (the view helper in {@code ui/}, owned by ui-dev):
 * {@code io.jenkins.plugins.batchcontrol.ui.StatusLabels.of(Enum<?>) -> String}, the label shown
 * for a constant; it is called reflectively so that the rest of the test tree compiles before the
 * helper exists. A label is non-blank, is not the constant's name and holds no underscore. The
 * contract's example labels that are not specific to one kind of request are pinned: PENDING
 * "Pending", EXECUTED "Executed", APPROVED_REQUEST "Approved request", TIMER "Timer" (APPROVED is
 * "Approved, waiting to run" on a run request; that one is pinned on the page, T-UI-255).
 *
 * <p>Colour badges (matrix row T-UI-268, note 361 point 7; contract "D2 colour badges", #18.2,
 * 2026-10-14). Expected API, next to the labels:
 * {@code io.jenkins.plugins.batchcontrol.ui.StatusLabels.tone(Enum<?>) -> String}, the lower-case
 * tone of a request or incident status ({@code warning}, {@code info}, {@code success},
 * {@code danger} or {@code neutral}) and {@code null} or an empty string for a run cause, which is
 * not a badge. Called reflectively, as {@code of}.
 */
public class StatusLabelsTest {

    private static final List<Class<? extends Enum<?>>> LABELLED =
            List.of(RequestStatus.class, IncidentStatus.class, CauseType.class);

    /** T-UI-259 (#18.2): every constant of every labelled enum has a readable label. */
    @Test
    public void t_ui_259_everyEnumConstantHasAReadableLabel() throws Exception {
        Method of = labelMethod();
        List<String> missing = new ArrayList<>();
        for (Class<? extends Enum<?>> type : LABELLED) {
            for (Enum<?> constant : type.getEnumConstants()) {
                String label = label(of, constant);
                if (label == null || label.isBlank() || label.equals(constant.name()) || label.contains("_")) {
                    missing.add(type.getSimpleName() + "." + constant.name() + " -> " + label);
                }
            }
        }
        assertTrue(missing.isEmpty(), "every enum constant shown on a screen must have a readable label;"
                + " missing or raw: " + missing);

        assertEquals("Pending", label(of, RequestStatus.PENDING), "the contract's label for PENDING");
        assertEquals("Executed", label(of, RequestStatus.EXECUTED), "the contract's label for EXECUTED");
        assertEquals("Approved request", label(of, CauseType.APPROVED_REQUEST), "the contract's label for APPROVED_REQUEST");
        assertEquals("Timer", label(of, CauseType.TIMER), "the contract's label for TIMER");
    }

    /**
     * T-UI-268 (#18.2, colour badges): every constant of {@link RequestStatus} and
     * {@link IncidentStatus} has the contract's tone, so a constant added later without one fails
     * here instead of showing an unstyled badge; a {@link CauseType} has none.
     */
    @Test
    public void t_ui_268_everyStatusHasItsToneAndRunCausesHaveNone() throws Exception {
        Map<Enum<?>, String> contract = new LinkedHashMap<>();
        contract.put(RequestStatus.PENDING, "warning");
        contract.put(RequestStatus.APPROVED, "info");
        contract.put(RequestStatus.EXECUTED, "success");
        contract.put(RequestStatus.REJECTED, "danger");
        contract.put(RequestStatus.CANCELLED, "neutral");
        contract.put(RequestStatus.EXPIRED, "neutral");
        contract.put(RequestStatus.INVALIDATED, "neutral");
        contract.put(IncidentStatus.OPEN, "danger");
        contract.put(IncidentStatus.ACKNOWLEDGED, "warning");
        contract.put(IncidentStatus.RESOLVED, "success");
        Set<String> tones = Set.of("warning", "info", "success", "danger", "neutral");

        Method tone = toneMethod();
        List<String> wrong = new ArrayList<>();
        for (Class<? extends Enum<?>> type : List.<Class<? extends Enum<?>>>of(RequestStatus.class, IncidentStatus.class)) {
            for (Enum<?> constant : type.getEnumConstants()) {
                String name = type.getSimpleName() + "." + constant.name();
                String actual = tone(tone, constant);
                if (actual == null || !tones.contains(actual)) {
                    wrong.add(name + " -> " + actual + " (not one of the five tones)");
                } else if (!contract.containsKey(constant)) {
                    wrong.add(name + " -> " + actual + " (the contract names no tone for it: it needs one, and a line here)");
                } else if (!contract.get(constant).equals(actual)) {
                    wrong.add(name + " -> " + actual + " (the contract says " + contract.get(constant) + ")");
                }
            }
        }
        assertTrue(wrong.isEmpty(), "every request and incident status must have the contract's tone, in lower case: " + wrong);

        List<String> toned = new ArrayList<>();
        for (CauseType cause : CauseType.values()) {
            String actual = tone(tone, cause);
            if (actual != null && !actual.isEmpty()) {
                toned.add("CauseType." + cause.name() + " -> " + actual);
            }
        }
        assertTrue(toned.isEmpty(), "a run cause is not a badge: its tone must be null or empty: " + toned);
    }

    private static Method toneMethod() {
        try {
            return Class.forName("io.jenkins.plugins.batchcontrol.ui.StatusLabels").getMethod("tone", Enum.class);
        } catch (ClassNotFoundException | NoSuchMethodException e) {
            fail("expected API: io.jenkins.plugins.batchcontrol.ui.StatusLabels.tone(Enum<?>) -> String, the lower-case tone"
                    + " of a request or incident status, null or \"\" for a run cause (" + e + ")");
            return null;
        }
    }

    /** The tone of a constant; a helper that throws for it counts as "threw", which is no tone and not "none" either. */
    private static String tone(Method tone, Enum<?> constant) throws Exception {
        try {
            Object value = tone.invoke(null, constant);
            return value == null ? null : value.toString();
        } catch (InvocationTargetException e) {
            return "threw " + e.getCause();
        }
    }

    private static Method labelMethod() {
        try {
            return Class.forName("io.jenkins.plugins.batchcontrol.ui.StatusLabels").getMethod("of", Enum.class);
        } catch (ClassNotFoundException | NoSuchMethodException e) {
            fail("expected API: io.jenkins.plugins.batchcontrol.ui.StatusLabels.of(Enum<?>) -> String (" + e + ")");
            return null;
        }
    }

    private static String label(Method of, Enum<?> constant) throws Exception {
        try {
            Object label = of.invoke(null, constant);
            return label == null ? null : label.toString();
        } catch (InvocationTargetException e) {
            return null; // a constant the helper cannot label counts as missing
        }
    }
}
