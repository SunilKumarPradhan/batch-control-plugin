package io.jenkins.plugins.batchcontrol.ui;

import io.jenkins.plugins.batchcontrol.model.CauseType;
import io.jenkins.plugins.batchcontrol.model.IncidentStatus;
import io.jenkins.plugins.batchcontrol.model.RequestStatus;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;
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
