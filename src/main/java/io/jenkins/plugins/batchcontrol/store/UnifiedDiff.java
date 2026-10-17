package io.jenkins.plugins.batchcontrol.store;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import org.kohsuke.accmod.Restricted;
import org.kohsuke.accmod.restrictions.NoExternalUse;

/**
 * Minimal unified-diff generator for config.xml change records (SPEC item 9). LCS-based,
 * three context lines per hunk, standard {@code @@ -a,b +c,d @@} hunk headers. The LCS is found
 * in memory linear in the number of lines (#35): it runs on the saving thread.
 *
 * <p>Size guard: pathological inputs (huge configs or a diff longer than
 * {@value #MAX_DIFF_LINES} lines) are replaced by a short "diff too large" note so a single
 * change can never bloat the store or the UI.
 */
@Restricted(NoExternalUse.class)
public final class UnifiedDiff {

    /** Context lines before and after each change run (the unified-diff convention). */
    private static final int CONTEXT = 3;

    /** Upper bound on the emitted diff body; beyond it only a note is stored. */
    private static final int MAX_DIFF_LINES = 2000;

    /**
     * Upper bound on the work of one diff (old lines times new lines); beyond it only a note is
     * stored. No table of this size is allocated: it bounds the time spent on the saving thread.
     */
    private static final long MAX_LCS_CELLS = 20_000_000L;

    private UnifiedDiff() {
    }

    /**
     * Computes the unified diff between two texts.
     *
     * @return the diff text, or {@code null} when the texts are line-identical
     */
    public static String diff(String oldText, String newText) {
        Objects.requireNonNull(oldText, "oldText");
        Objects.requireNonNull(newText, "newText");
        List<String> oldLines = splitLines(oldText);
        List<String> newLines = splitLines(newText);
        if (oldLines.equals(newLines)) {
            return null;
        }
        if ((long) oldLines.size() * newLines.size() > MAX_LCS_CELLS) {
            return tooLarge(Math.max(oldLines.size(), newLines.size()));
        }

        boolean[] oldKept = new boolean[oldLines.size()];
        boolean[] newKept = new boolean[newLines.size()];
        markCommonLines(oldLines, newLines, oldKept, newKept);

        List<String> body = hunks(oldLines, newLines, oldKept, newKept);
        if (body.size() > MAX_DIFF_LINES) {
            return tooLarge(body.size());
        }
        StringBuilder sb = new StringBuilder();
        sb.append("--- before\n+++ after\n");
        for (String line : body) {
            sb.append(line).append('\n');
        }
        return sb.toString();
    }

    private static String tooLarge(int lines) {
        return "Diff too large to store (" + lines
                + " lines); the change was recorded without the full diff.";
    }

    private static List<String> splitLines(String text) {
        List<String> lines = new ArrayList<>();
        int start = 0;
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (c == '\n') {
                int end = i > start && text.charAt(i - 1) == '\r' ? i - 1 : i;
                lines.add(text.substring(start, end));
                start = i + 1;
            }
        }
        if (start < text.length()) {
            lines.add(text.substring(start));
        }
        return lines;
    }

    /**
     * Marks the lines of one longest common subsequence, in linear space (#35).
     *
     * <p>The kept lines are exactly those of the classic {@code (m+1) x (n+1)} LCS table walked
     * from the top: a matching pair is kept at once; otherwise the old line is dropped when that
     * keeps the walk optimal, else the new line. So the emitted diff is the same as before, but
     * no table is allocated: the walk is found by divide and conquer (Hirschberg). For a box whose
     * corners both lie on the walk, one backward sweep over the box finds where the walk enters
     * the box's middle row, and the two halves are solved alone. The walk restricted to such a
     * box is the box's own walk, because every step of the walk stays optimal. Memory is a few
     * rows of {@code n+1} ints; time is about twice the old table fill.
     */
    private static void markCommonLines(List<String> oldLines, List<String> newLines,
                                        boolean[] oldKept, boolean[] newKept) {
        Map<String, Integer> ids = new HashMap<>();
        int[] a = intern(oldLines, ids);
        int[] b = intern(newLines, ids);
        new LcsWalk(a, b, oldKept, newKept).mark(0, 0, a.length, b.length);
    }

    /** Replaces every line by a small id; equal lines get the same id. */
    private static int[] intern(List<String> lines, Map<String, Integer> ids) {
        int[] out = new int[lines.size()];
        for (int i = 0; i < out.length; i++) {
            Integer id = ids.get(lines.get(i));
            if (id == null) {
                id = ids.size();
                ids.put(lines.get(i), id);
            }
            out[i] = id;
        }
        return out;
    }

    /**
     * The linear-space walk of {@link #markCommonLines}. Grid point {@code (i, j)} means
     * "{@code i} old and {@code j} new lines consumed"; {@code L(i, j)} is the LCS length of the
     * suffixes of a box from that point.
     */
    private static final class LcsWalk {
        private final int[] a;
        private final int[] b;
        private final boolean[] aKept;
        private final boolean[] bKept;
        /** Two rows of L and two rows of entry labels, reused by every sweep. */
        private int[] lBelow;
        private int[] lHere;
        private int[] entryBelow;
        private int[] entryHere;

        LcsWalk(int[] a, int[] b, boolean[] aKept, boolean[] bKept) {
            this.a = a;
            this.b = b;
            this.aKept = aKept;
            this.bKept = bKept;
            this.lBelow = new int[b.length + 1];
            this.lHere = new int[b.length + 1];
            this.entryBelow = new int[b.length + 1];
            this.entryHere = new int[b.length + 1];
        }

        /** Marks the walk from {@code (i0, j0)} to {@code (i1, j1)}; both lie on the walk. */
        void mark(int i0, int j0, int i1, int j1) {
            // A matching pair at the box's corner is always taken first.
            while (i0 < i1 && j0 < j1 && a[i0] == b[j0]) {
                aKept[i0++] = true;
                bKept[j0++] = true;
            }
            if (i0 >= i1 || j0 >= j1) {
                return;
            }
            if (i1 - i0 == 1) {
                // One old line: the walk moves right to its first match in the box, if any.
                for (int j = j0; j < j1; j++) {
                    if (b[j] == a[i0]) {
                        aKept[i0] = true;
                        bKept[j] = true;
                        return;
                    }
                }
                return;
            }
            int mid = (i0 + i1) >>> 1;
            int k = entryColumn(i0, j0, i1, j1, mid);
            mark(i0, j0, mid, k);
            mark(mid, k, i1, j1);
        }

        /**
         * One sweep from the box's last row up to its first: fills L row by row and, above
         * {@code mid}, carries for every point the column at which the walk from that point
         * first reaches row {@code mid}. Returns that column for {@code (i0, j0)}.
         */
        private int entryColumn(int i0, int j0, int i1, int j1, int mid) {
            int w = j1 - j0;
            Arrays.fill(lBelow, 0, w + 1, 0);
            for (int r = i1 - 1; r >= i0; r--) {
                if (r == mid - 1) {
                    for (int c = 0; c <= w; c++) {
                        entryBelow[c] = j0 + c;
                    }
                }
                boolean labelled = r < mid;
                int x = a[r];
                lHere[w] = 0;
                if (labelled) {
                    entryHere[w] = entryBelow[w];
                }
                for (int c = w - 1; c >= 0; c--) {
                    if (b[j0 + c] == x) {
                        lHere[c] = lBelow[c + 1] + 1;
                        if (labelled) {
                            entryHere[c] = entryBelow[c + 1];
                        }
                    } else if (lBelow[c] >= lHere[c + 1]) {
                        lHere[c] = lBelow[c];
                        if (labelled) {
                            entryHere[c] = entryBelow[c];
                        }
                    } else {
                        lHere[c] = lHere[c + 1];
                        if (labelled) {
                            entryHere[c] = entryHere[c + 1];
                        }
                    }
                }
                int[] t = lBelow;
                lBelow = lHere;
                lHere = t;
                if (labelled) {
                    t = entryBelow;
                    entryBelow = entryHere;
                    entryHere = t;
                }
            }
            return entryBelow[0];
        }
    }

    /** Emits hunks with {@value #CONTEXT} context lines; adjacent change runs merge naturally. */
    private static List<String> hunks(List<String> oldLines, List<String> newLines,
                                      boolean[] oldKept, boolean[] newKept) {
        List<String> out = new ArrayList<>();
        int i = 0;
        int j = 0;
        int m = oldLines.size();
        int n = newLines.size();
        // Old-side index just past the last line emitted by the previous hunk, so a new hunk's
        // leading context never overlaps the previous hunk's trailing context.
        int prevHunkOldEnd = 0;
        while (i < m || j < n) {
            // Skip a stretch of common lines.
            while (i < m && j < n && oldKept[i] && newKept[j]) {
                i++;
                j++;
            }
            if (i >= m && j >= n) {
                break;
            }
            // A change begins here; open a hunk with up to CONTEXT common lines before it.
            int hunkOldStart = Math.max(prevHunkOldEnd, i - CONTEXT);
            int hunkNewStart = j - (i - hunkOldStart);
            List<String> hunkBody = new ArrayList<>();
            for (int k = hunkOldStart; k < i; k++) {
                hunkBody.add(" " + oldLines.get(k));
            }
            int hunkOldCount = i - hunkOldStart;
            int hunkNewCount = i - hunkOldStart;
            // Alternate change runs and short common runs until a common run longer than
            // 2*CONTEXT (or the end) closes the hunk.
            while (i < m || j < n) {
                while (i < m && !oldKept[i]) {
                    hunkBody.add("-" + oldLines.get(i));
                    i++;
                    hunkOldCount++;
                }
                while (j < n && !newKept[j]) {
                    hunkBody.add("+" + newLines.get(j));
                    j++;
                    hunkNewCount++;
                }
                // Measure the following common run.
                int commonLen = 0;
                while (i + commonLen < m && j + commonLen < n
                        && oldKept[i + commonLen] && newKept[j + commonLen]) {
                    commonLen++;
                }
                boolean atEnd = i + commonLen >= m && j + commonLen >= n;
                if (commonLen > 2 * CONTEXT || atEnd) {
                    int trailing = Math.min(commonLen, CONTEXT);
                    for (int k = 0; k < trailing; k++) {
                        hunkBody.add(" " + oldLines.get(i + k));
                    }
                    hunkOldCount += trailing;
                    hunkNewCount += trailing;
                    prevHunkOldEnd = i + trailing;
                    i += commonLen;
                    j += commonLen;
                    break;
                }
                for (int k = 0; k < commonLen; k++) {
                    hunkBody.add(" " + oldLines.get(i + k));
                }
                hunkOldCount += commonLen;
                hunkNewCount += commonLen;
                i += commonLen;
                j += commonLen;
            }
            out.add("@@ -" + (hunkOldCount == 0 ? hunkOldStart : hunkOldStart + 1) + ","
                    + hunkOldCount + " +" + (hunkNewCount == 0 ? hunkNewStart : hunkNewStart + 1)
                    + "," + hunkNewCount + " @@");
            out.addAll(hunkBody);
        }
        return out;
    }
}
