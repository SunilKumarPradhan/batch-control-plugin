package io.jenkins.plugins.batchcontrol.ui;

import edu.umd.cs.findbugs.annotations.CheckForNull;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.kohsuke.accmod.Restricted;
import org.kohsuke.accmod.restrictions.NoExternalUse;

/**
 * #6, #18.1 (Wave D, D3): the Parameters cell of the run tables ({@code tags/parameters.jelly}):
 * one {@code name=value} line per parameter in the record's order, the first {@value #SHOWN} shown
 * and the rest folded into one {@code <details>}; each value cut at {@value #MAX_VALUE} characters
 * with an ellipsis. The full values stay whole in the CSV export, on the request page and on the
 * build page. Values arrive already masked from the store (D-72); the view escapes every line.
 */
@Restricted(NoExternalUse.class)
public final class ParameterLines {

    /** Lines shown before the fold. */
    public static final int SHOWN = 3;

    /** Characters (code points) of a value shown in a table cell. */
    public static final int MAX_VALUE = 120;

    private final List<String> shown;
    private final List<String> folded;

    private ParameterLines(List<String> shown, List<String> folded) {
        this.shown = shown;
        this.folded = folded;
    }

    public static ParameterLines of(@CheckForNull Map<String, String> parameters) {
        List<String> lines = new ArrayList<>();
        if (parameters != null) {
            for (Map.Entry<String, String> e : parameters.entrySet()) {
                lines.add(e.getKey() + "=" + cut(e.getValue()));
            }
        }
        int split = Math.min(SHOWN, lines.size());
        return new ParameterLines(List.copyOf(lines.subList(0, split)), List.copyOf(lines.subList(split, lines.size())));
    }

    static String cut(@CheckForNull String value) {
        if (value == null) {
            return "";
        }
        if (value.codePointCount(0, value.length()) <= MAX_VALUE) {
            return value;
        }
        return value.substring(0, value.offsetByCodePoints(0, MAX_VALUE)) + "…";
    }

    /** The lines shown in the cell. */
    public List<String> getShown() {
        return shown;
    }

    /** The lines folded into {@code <details>}; empty when there are at most {@value #SHOWN}. */
    public List<String> getFolded() {
        return folded;
    }
}
