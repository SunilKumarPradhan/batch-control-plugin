package io.jenkins.plugins.batchcontrol.ui;

import edu.umd.cs.findbugs.annotations.CheckForNull;
import io.jenkins.plugins.batchcontrol.model.IncidentStatus;
import io.jenkins.plugins.batchcontrol.model.RequestStatus;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.function.Function;
import org.kohsuke.accmod.Restricted;
import org.kohsuke.accmod.restrictions.NoExternalUse;

/**
 * #18.3 (Wave D, D2): the options of the History filter's Result and Status dropdowns. The first
 * option is "Any" (empty value, no filter); the others are the enum or result names, so the URL,
 * bookmarks and {@link FilterParser} tokens are unchanged, labelled with {@link StatusLabels}.
 *
 * <p>The current token selects the option it names (case-insensitively, as
 * {@link FilterParser.Filter#matchesResult} and {@link FilterParser.Filter#matchesStatus} compare).
 * A value from a hand-edited URL that names no option is kept as one extra, selected option whose
 * value and text are that value (SPEC 6: the user's input is kept); the view escapes both. A value
 * that is not a token at all ({@link FilterParser} ignores it, so it filters nothing) is kept the
 * same way, as typed, and the view says that it is not applied.
 */
@Restricted(NoExternalUse.class)
public final class FilterOptions {

    /** One dropdown option. */
    public static final class Option {
        private final String value;
        private final String label;
        private final boolean selected;

        Option(String value, String label, boolean selected) {
            this.value = value;
            this.label = label;
            this.selected = selected;
        }

        public String getValue() {
            return value;
        }

        public String getLabel() {
            return label;
        }

        public boolean isSelected() {
            return selected;
        }
    }

    private FilterOptions() {}

    /** The Result dropdown: Any, then every build result. */
    public static List<Option> results(@CheckForNull String current, @CheckForNull String ignored) {
        return options(StatusLabels.resultNames(), StatusLabels::ofResult, current, ignored);
    }

    /** The Status dropdown of the incidents: Any, then every incident status. */
    public static List<Option> incidentStatuses(@CheckForNull String current, @CheckForNull String ignored) {
        List<String> names = new ArrayList<>();
        for (IncidentStatus s : IncidentStatus.values()) {
            names.add(s.name());
        }
        return options(names, name -> StatusLabels.of(IncidentStatus.valueOf(name)), current, ignored);
    }

    /** The Status dropdown of the run requests: Any, then every request status. */
    public static List<Option> runRequestStatuses(@CheckForNull String current, @CheckForNull String ignored) {
        List<String> names = new ArrayList<>();
        for (RequestStatus s : RequestStatus.values()) {
            names.add(s.name());
        }
        return options(names, name -> StatusLabels.ofRunRequest(RequestStatus.valueOf(name)), current, ignored);
    }

    /**
     * @param current the filter token ({@link FilterParser.Filter#getResult} or {@code getStatus}), or null
     * @param ignored the value as given when it is not a token and so not applied
     *     ({@link FilterParser.Filter#getIgnoredResult}), or null
     */
    private static List<Option> options(List<String> names, Function<String, String> label,
            @CheckForNull String current, @CheckForNull String ignored) {
        String token = current == null || current.isBlank() ? null : current;
        String kept = token != null ? token : (ignored == null || ignored.isBlank() ? null : ignored);
        List<Option> out = new ArrayList<>();
        out.add(new Option("", "Any", kept == null));
        boolean matched = kept == null;
        for (String name : names) {
            boolean selected = token != null && !matched && name.equalsIgnoreCase(token);
            matched |= selected;
            out.add(new Option(name, label.apply(name), selected));
        }
        if (!matched) {
            out.add(new Option(kept, kept, true));
        }
        return Collections.unmodifiableList(out);
    }
}
