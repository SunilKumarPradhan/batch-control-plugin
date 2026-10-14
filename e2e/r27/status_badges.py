"""e2e-27 D2, the status colour badges as a browser renders them on a running Jenkins (TEST-MATRIX note 361 point 7,
"not measured here, verified in e2e", and point 8): what the integration rows cannot see.

usage: python status_badges.py [ATGCH]   rows: out/status_badges.jsonl, shots: screenshots/run-27/R27-D2-S-*.png
Runs after r27/labels_filters.py in the unit r27-labels-filters and reads the same records (r27/d2_fixture.py, reused
when they are still in place). approver-1 reads the screens (Approve and ViewHistory: every screen with a badge).

A  arrangement: the fixture's states (store).
T  colours, in the light and in the dark theme (approver-1 chooses the theme on the Appearance page of the account, as
   a person does; "Default" is chosen again at the end). On History > Requests (all five tones in one table), the
   Incidents list, the Ended tables of the Grants and Activations lists and three request pages, per badge: the text
   colour (computed), the badge's background and the cell's background (pixels of a screenshot; the computed
   color-mix over the cell agrees with the pixel), the border (computed, over the cell). Checks: contrast of the text
   on the badge at least 4.5:1 (WCAG 1.4.3) for every badge; every tone seen in both themes; each badge differs from
   the cell around it (CIEDE2000 of background or border at least 2.3, one just-noticeable difference; the numbers are
   in the row); the colours come from the stylesheet (no style attribute). NOTE rows carry the measured colours,
   among them the neutral and the info badge side by side (the pair was accepted by the owner on 2026-10-14).
   Screenshots per theme: the History table with the five tones, the Ended tables, an approved request's page.
G  geometry in the light theme at 1280, 1024 and 768 px: every badge is a span laid out as an inline block with
   rounded corners and a solid border, inside its cell and smaller than it, with room on the left, above and below (a
   pill, not the painted cell; Jenkins' table cells have no padding on the right, so a badge that fills its line ends
   at the cell's edge, accepted by the owner on 2026-10-14); the badges add no sideways page scroll that the same page
   without the badge styling does not already have (owner decision of 2026-10-14: a badge may redistribute the column
   widths and make a row taller, at 768 px for example; the row heights are logged, not judged); the badges add no
   width to the page or a table (compared with the same page without the badge styling), and at 1280 px no screen
   scrolls sideways. The long wording "Revoked (its item was deleted) by <a 55-character user id>" is measured apart:
   it stays inside its cell at every width and its table grows by no more than the pill's own padding and border; a
   NOTE says how it wraps.
C  Content-Security-Policy: core 2.568.3 sends a report-only policy and can enforce it (Manage Jenkins > Security).
   Enforcement is switched on for this section (script console, the setting the page saves; switched off again), the
   screens are read again and the browser's securitypolicyviolation events and console messages are collected: none
   may concern a style or a resource of the plugin, and no badge has a style attribute.
H  forced colours (Playwright forced_colors=active, the Windows high-contrast emulation): on History > Requests every
   badge keeps a visible border (a solid border whose colour differs from the page) and readable text (contrast at
   least 4.5:1 on what is painted behind it).
cleanup: approver-1's theme back to the default, enforcement off, the requester's r27-d2 requests swept."""
import math
import re
import struct
import sys
import zlib

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import d2_fixture as F  # noqa: E402
import lib  # noqa: E402
from lib import api, check, note, Session, gv  # noqa: E402

lib.LOGNAME[0] = "status_badges"
P, J = F.P, F.J
S = {}
WHO = "approver-1"
TONES = ("warning", "info", "success", "danger", "neutral")


# ---------------------------------------------------------------- colour arithmetic
def png(data):
    """Decodes an 8-bit RGB or RGBA non-interlaced PNG (what a Playwright screenshot is): (width, height, pixel(x, y))."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, chunks, idat = 8, {}, b""
    while pos < len(data):
        n, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if kind == b"IDAT":
            idat += body
        else:
            chunks[kind] = body
        pos += 12 + n
    w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", chunks[b"IHDR"])
    assert depth == 8 and ctype in (2, 6) and interlace == 0, (depth, ctype, interlace)
    bpp = 3 if ctype == 2 else 4
    raw, stride, rows, prev = zlib.decompress(idat), w * bpp, [], bytearray(w * bpp)
    for y in range(h):
        f, line = raw[y * (stride + 1)], bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b, c = prev[i], (prev[i - bpp] if i >= bpp else 0)
            if f == 1:
                line[i] = (line[i] + a) & 255
            elif f == 2:
                line[i] = (line[i] + b) & 255
            elif f == 3:
                line[i] = (line[i] + ((a + b) >> 1)) & 255
            elif f == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    return w, h, lambda x, y: tuple(rows[int(y)][int(x) * bpp:int(x) * bpp + 3])


def luminance(rgb):
    c = [v / 255 for v in rgb]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


def lab(rgb):
    c = [v / 255 for v in rgb]
    r, g, b = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    x, y, z = (0.4124564 * r + 0.3575761 * g + 0.1804375 * b) / 0.95047, 0.2126729 * r + 0.7151522 * g + 0.0721750 * b, \
        (0.0193339 * r + 0.1191920 * g + 0.9503041 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 216 / 24389 else (24389 / 27 * t + 16) / 116  # noqa: E731
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def delta_e(rgb1, rgb2):
    """CIEDE2000 between two sRGB colours."""
    (l1, a1, b1), (l2, a2, b2) = lab(rgb1), lab(rgb2)
    c_bar = (math.hypot(a1, b1) + math.hypot(a2, b2)) / 2
    g = 0.5 * (1 - math.sqrt(c_bar ** 7 / (c_bar ** 7 + 25 ** 7)))
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h = lambda b_, a_: math.degrees(math.atan2(b_, a_)) % 360 if (a_ or b_) else 0.0  # noqa: E731
    h1p, h2p = h(b1, a1p), h(b2, a2p)
    dl, dc = l2 - l1, c2p - c1p
    dh = 0.0 if c1p * c2p == 0 else (h2p - h1p + 180) % 360 - 180
    dH = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dh / 2))
    l_bar, cp_bar = (l1 + l2) / 2, (c1p + c2p) / 2
    if c1p * c2p == 0:
        h_bar = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        h_bar = (h1p + h2p) / 2
    else:
        h_bar = (h1p + h2p + 360) / 2 if h1p + h2p < 360 else (h1p + h2p - 360) / 2
    t = (1 - 0.17 * math.cos(math.radians(h_bar - 30)) + 0.24 * math.cos(math.radians(2 * h_bar))
         + 0.32 * math.cos(math.radians(3 * h_bar + 6)) - 0.20 * math.cos(math.radians(4 * h_bar - 63)))
    sl = 1 + 0.015 * (l_bar - 50) ** 2 / math.sqrt(20 + (l_bar - 50) ** 2)
    sc, sh = 1 + 0.045 * cp_bar, 1 + 0.015 * cp_bar * t
    rt = -2 * math.sqrt(cp_bar ** 7 / (cp_bar ** 7 + 25 ** 7)) * math.sin(math.radians(60 * math.exp(-((h_bar - 275) / 25) ** 2)))
    return round(math.sqrt((dl / sl) ** 2 + (dc / sc) ** 2 + (dH / sh) ** 2 + rt * (dc / sc) * (dH / sh)), 2)


def over(rgba, base):
    """An sRGB colour with alpha painted over an opaque one."""
    return tuple(round(rgba[i] * rgba[3] + base[i] * (1 - rgba[3])) for i in range(3))


def hexc(rgb):
    return "#%02x%02x%02x" % tuple(rgb)


# One reading of the badges of a page: geometry and the computed colours, converted to sRGB by the browser itself (a
# 1x1 canvas), with the alpha a colour has.
BADGES_JS = """() => { const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', {willReadFrequently: true});
  const rgba = css => { cx.clearRect(0, 0, 1, 1); cx.fillStyle = 'rgba(0,0,0,0)'; cx.fillStyle = css; cx.fillRect(0, 0, 1, 1);
    const m = /\\/\\s*([0-9.]+%?)\\s*\\)$/.exec(css) || /rgba\\([^)]*,\\s*([0-9.]+)\\)$/.exec(css);
    let a = m ? (m[1].endsWith('%') ? parseFloat(m[1]) / 100 : parseFloat(m[1])) : (css === 'transparent' ? 0 : 1);
    cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#fff'; cx.fillRect(0, 0, 1, 1); cx.fillStyle = css; cx.fillRect(0, 0, 1, 1);
    const w = cx.getImageData(0, 0, 1, 1).data;
    cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillRect(0, 0, 1, 1); cx.fillStyle = css; cx.fillRect(0, 0, 1, 1);
    const k = cx.getImageData(0, 0, 1, 1).data;
    // over white w = c*a + 255(1-a), over black k = c*a: the colour itself is recovered where a > 0
    a = 1 - (w[0] - k[0] + w[1] - k[1] + w[2] - k[2]) / 765;
    const c = [0, 1, 2].map(i => a > 0 ? Math.round(Math.min(255, k[i] / a)) : 0);
    return [c[0], c[1], c[2], Math.round(a * 1000) / 1000]; };
  const n = t => (t || '').replace(/\\s+/g, ' ').trim();
  const box = e => { const r = e.getBoundingClientRect(); return {x: r.left, y: r.top, w: r.width, h: r.height, right: r.right, bottom: r.bottom}; };
  const root = getComputedStyle(document.documentElement);
  return {theme: document.documentElement.getAttribute('data-theme'), scheme: root.colorScheme,
    core: Object.fromEntries(['--warning-color', '--accent-color', '--success-color', '--error-color', '--text-color-secondary', '--text-color']
      .map(v => [v, root.getPropertyValue(v).trim()])),
    scroll: [window.scrollX, window.scrollY], viewport: [innerWidth, innerHeight],
    doc: [document.documentElement.scrollWidth, document.documentElement.clientWidth],
    badges: [...document.querySelectorAll('.batch-control-status')].map((e, i) => { const cs = getComputedStyle(e);
      const cell = e.closest('td, th') || e.parentElement; const tr = e.closest('tr'); const table = e.closest('table');
      e.setAttribute('data-r27-badge', String(i));
      return {i, enum: e.getAttribute('data-batch-control-status'), tone: e.getAttribute('data-batch-control-tone'), text: n(e.textContent),
        tag: e.tagName.toLowerCase(), display: cs.display, radius: parseFloat(cs.borderTopLeftRadius), lineHeight: parseFloat(cs.lineHeight),
        fontSize: parseFloat(cs.fontSize), borderStyle: cs.borderTopStyle, borderWidth: parseFloat(cs.borderTopWidth),
        color: rgba(cs.color), background: rgba(cs.backgroundColor), border: rgba(cs.borderTopColor),
        css: {color: cs.color, background: cs.backgroundColor, border: cs.borderTopColor},
        style: e.hasAttribute('style'), box: box(e), cell: box(cell), row: tr ? box(tr) : null,
        toneColor: cs.getPropertyValue('--batch-control-status-color').trim(),
        textIsCore: (() => { const q = document.createElement('span'); q.style.color = 'var(--text-color)'; cell.appendChild(q);
          const same = getComputedStyle(q).color === cs.color; q.remove(); return same; })(),
        list: table ? table.getAttribute('data-batch-control-list') : null,
        table: table ? {right: table.getBoundingClientRect().right, scrollWidth: table.scrollWidth, clientWidth: table.clientWidth} : null}; })}; }"""


def set_theme(theme):
    """approver-1 chooses the theme on the account's Appearance page ('none' is the default, light)."""
    s = Session(WHO)
    s.go(f"/user/{WHO}/appearance/")
    s.page.locator(f"input[data-theme={theme}]").check(force=True)
    with s.page.expect_navigation(timeout=20000):
        s.page.locator("button[name=Submit]").first.click()
    s.page.wait_for_load_state("load")
    s.go(f"/user/{WHO}/appearance/")
    chosen = s.page.evaluate("() => (document.querySelector('input[data-theme]:checked') || {dataset: {}}).dataset.theme")
    s.done()
    return chosen


def measure(s, per_kind=2):
    """The badges of the open page with their painted colours: the badge's and the cell's background read from a
    screenshot of the badge's cell (scrolled to the middle of the viewport), the border computed over the cell. At most
    `per_kind` badges per status and table are read (the others are painted by the same rule)."""
    out, taken = [], {}
    p = s.page.evaluate(BADGES_JS)
    S.setdefault("core", {})[p["theme"] and "dark" if p["theme"] == "dark" else "light"] = p["core"]
    for b in p["badges"]:
        kind = (b["enum"], b["list"], b["tone"])
        taken[kind] = taken.get(kind, 0) + 1
        if taken[kind] > per_kind:
            continue
        loc = s.page.locator(f"[data-r27-badge='{b['i']}']")
        r = loc.evaluate("""e => { e.scrollIntoView({block: 'center', inline: 'center'});
          const b = e.getBoundingClientRect(); const c = (e.closest('td, th') || e.parentElement).getBoundingClientRect();
          return {x: b.left, y: b.top, w: b.width, h: b.height, right: b.right, cx: c.left, cy: c.top, cw: c.width, ch: c.height}; }""")
        clip = {"x": max(0, math.floor(r["cx"])), "y": max(0, math.floor(r["cy"])), "width": max(8, math.ceil(r["cw"])),
                "height": max(8, math.ceil(r["ch"]))}
        w, h, px = png(s.page.screenshot(clip=clip))
        bx, by = r["x"] - clip["x"], r["y"] - clip["y"] + r["h"] / 2
        inside = px(min(w - 1, bx + 4), min(h - 1, by))                 # in the left padding: background only
        gap = bx + r["w"] + 5 if bx + r["w"] + 6 < w else bx - 4
        around = px(gap, min(h - 1, by)) if 0 <= gap < w else None      # the cell next to the badge
        b.update(painted=inside, cell_painted=around)
        if around:
            b["computed_over_cell"] = over(b["background"], around)
            b["border_over_cell"] = over(b["border"], around)
        out.append(b)
    return p, out


def screens():
    return (("history-requests", f"/batch-control/history/?kind=requests&job={P}"),
            ("incidents-list", "/batch-control/incidents/"),
            ("grants-list", "/batch-control/grants/"),
            ("activations-list", "/batch-control/activations/"),
            ("run-request-approved", f"/batch-control/requests/{S['run']['APPROVED']}/"),
            ("grant-request-approved-window-revoked", f"/batch-control/grants/{S['window']['rev']}/"),
            ("incident-resolved", f"/batch-control/incidents/{S['incident']['RESOLVED']}/"))


# ---------------------------------------------------------------- A
def sec_A():
    S.update(F.arrange(reuse=True))
    st, ex = F.states(S), F.expected(S)
    check("A", "arrangement (d2_fixture): every request, window and incident state of the D2 contract is in place (server "
          "state)", st == ex, reused=S.get("reused"), wrong={k: (st.get(k), v) for k, v in ex.items() if st.get(k) != v})


# ---------------------------------------------------------------- T: colours in both themes
def sec_T():
    for theme, radio in (("light", "none"), ("dark", "dark")):
        chosen = set_theme(radio)
        s = Session(WHO)
        seen, rows, worst = {}, [], None
        for key, path in screens():
            r = s.go(path)
            p, badges = measure(s)
            for b in badges:
                if not b["cell_painted"]:
                    continue
                m = {"screen": key, "enum": b["enum"], "tone": b["tone"], "list": b["list"], "text": hexc(b["color"][:3]),
                     "badge": hexc(b["painted"]), "cell": hexc(b["cell_painted"]), "border": hexc(b["border_over_cell"]),
                     "text_on_badge": contrast(b["color"][:3], b["painted"]),
                     "badge_vs_cell": {"contrast": contrast(b["painted"], b["cell_painted"]), "dE": delta_e(b["painted"], b["cell_painted"])},
                     "border_vs_cell": {"contrast": contrast(b["border_over_cell"], b["cell_painted"]),
                                        "dE": delta_e(b["border_over_cell"], b["cell_painted"])},
                     "computed_agrees": max(abs(x - y) for x, y in zip(b["computed_over_cell"], b["painted"])) <= 3,
                     "alpha": [b["background"][3], b["border"][3]], "style": b["style"], "css": b["css"],
                     "tone_color": b["toneColor"], "text_is_core": b["textIsCore"]}
                rows.append(m)
                seen.setdefault(b["tone"], m)
                if worst is None or m["text_on_badge"] < worst["text_on_badge"]:
                    worst = m
            if key in ("history-requests", "grants-list", "activations-list", "incidents-list"):
                s.page.evaluate("window.scrollTo(0, 0)")
                table = "table[data-batch-control-list=ended]" if key in ("grants-list", "activations-list") else "#main-panel table"
                s.page.locator(table).first.screenshot(path=str(lib.SHOTS / f"R27-D2-S-{theme}-{key}.png"))
            else:
                s.page.evaluate("window.scrollTo(0, 0)")
                s.page.screenshot(path=str(lib.SHOTS / f"R27-D2-S-{theme}-{key}.png"))
            S.setdefault("pages", {})[(theme, key)] = (r.status if r else None, p["theme"], len(badges))
        s.done()
        S.setdefault("colours", {})[theme] = rows
        core = S.get("core", {}).get(theme, {})
        want = {"warning": "--warning-color", "info": "--accent-color", "success": "--success-color", "danger": "--error-color",
                "neutral": "--text-color-secondary"}
        mismatch = [m for m in rows if not core.get(want.get(m["tone"], "?")) or m["tone_color"] != core.get(want[m["tone"]])]
        check("T", f"D2 #18.2 the tones are core's theme colours ({theme} theme): each badge's tint colour is the value of "
              "core's variable for its tone on this page (warning --warning-color, info --accent-color, success "
              "--success-color, danger --error-color, neutral --text-color-secondary) and its text is --text-color",
              bool(rows) and bool(core) and not mismatch and all(m["css"]["color"] and m["text_is_core"] for m in rows),
              core=core, wrong=[{k: m[k] for k in ("screen", "tone", "tone_color")} for m in mismatch][:4])
        html_theme = sorted({v[1] or "none" for (t, _), v in S["pages"].items() if t == theme})
        check("T", f"arrangement: approver-1 chose the {theme} theme on the Appearance page and every screen is rendered "
              "with it", chosen == radio and html_theme == [radio]
              and all(v[0] == 200 for (t, _), v in S["pages"].items() if t == theme), chosen=chosen,
              html_data_theme=html_theme, pages={k[1]: v for k, v in S["pages"].items() if k[0] == theme})
        low = [m for m in rows if m["text_on_badge"] < 4.5]
        check("T", f"D2 #18.2 contrast ({theme} theme): on every badge the text has a contrast of at least 4.5:1 against the "
              f"badge's painted background ({len(rows)} badges on seven screens); all five tones are among them",
              len(rows) >= 20 and not low and set(seen) == set(TONES), badges=len(rows), tones=sorted(seen),
              lowest=worst and {k: worst[k] for k in ("screen", "enum", "tone", "text", "badge", "text_on_badge")},
              below=[{k: m[k] for k in ("screen", "enum", "text_on_badge")} for m in low][:5])
        same = [m for m in rows if max(m["badge_vs_cell"]["dE"], m["border_vs_cell"]["dE"]) < 2.3]
        check("T", f"D2 #18.2 a badge is not the cell ({theme} theme): every badge's background or border differs from the "
              "cell around it by at least one just-noticeable difference (CIEDE2000 2.3)", bool(rows) and not same,
              smallest=min(({"screen": m["screen"], "tone": m["tone"], "badge_dE": m["badge_vs_cell"]["dE"],
                             "border_dE": m["border_vs_cell"]["dE"]} for m in rows),
                           key=lambda x: max(x["badge_dE"], x["border_dE"])) if rows else None, same=same[:3])
        check("T", f"D2 #18.2 the colours come from the stylesheet ({theme} theme): no badge has a style attribute, the "
              "background and the border are translucent tints (alpha 0.2 and 0.5) over the cell, and the pixel painted "
              "agrees with the computed tint", bool(rows) and all(not m["style"] and abs(m["alpha"][0] - 0.2) <= 0.02
                                                                   and abs(m["alpha"][1] - 0.5) <= 0.02 and m["computed_agrees"]
                                                                   for m in rows),
              off=[{k: m[k] for k in ("screen", "enum", "alpha", "computed_agrees")} for m in rows
                   if m["style"] or abs(m["alpha"][0] - 0.2) > 0.02 or abs(m["alpha"][1] - 0.5) > 0.02 or not m["computed_agrees"]][:4])
        per_tone = {t: {k: seen[t][k] for k in ("text", "badge", "cell", "border", "text_on_badge", "badge_vs_cell",
                                                "border_vs_cell")} for t in TONES if t in seen}
        note("T", f"measured colours, {theme} theme (first badge of each tone; sRGB hex as painted)", tones=per_tone)
        # neutral next to info: measured for the owner, no verdict
        hist = [m for m in rows if m["screen"] == "history-requests"]
        neutral = next((m for m in hist if m["tone"] == "neutral"), None)
        info = next((m for m in hist if m["tone"] == "info"), None)
        if neutral and info:
            note("T", f"measured for the record (the pair was accepted by the owner on 2026-10-14): neutral against info on "
                 f"History > Requests, {theme} theme",
                 neutral={k: neutral[k] for k in ("badge", "border", "cell")}, info={k: info[k] for k in ("badge", "border", "cell")},
                 badge_dE2000=delta_e(tuple(int(neutral["badge"][i:i + 2], 16) for i in (1, 3, 5)),
                                      tuple(int(info["badge"][i:i + 2], 16) for i in (1, 3, 5))),
                 border_dE2000=delta_e(tuple(int(neutral["border"][i:i + 2], 16) for i in (1, 3, 5)),
                                       tuple(int(info["border"][i:i + 2], 16) for i in (1, 3, 5))),
                 badge_contrast=contrast(tuple(int(neutral["badge"][i:i + 2], 16) for i in (1, 3, 5)),
                                         tuple(int(info["badge"][i:i + 2], 16) for i in (1, 3, 5))))
        ended = [m for m in rows if m["list"] == "ended" and m["enum"] == "APPROVED"]
        page = [m for m in rows if m["screen"] in ("run-request-approved", "grant-request-approved-window-revoked") and m["enum"] == "APPROVED"]
        check("T", f"D2 #18.2 point 8 ({theme} theme): an approved request is painted neutral in the Ended tables and info on "
              "its own page, and the two paints differ", bool(ended) and bool(page)
              and all(m["tone"] == "neutral" for m in ended) and all(m["tone"] == "info" for m in page)
              and all(m["badge"] != page[0]["badge"] for m in ended),
              ended=sorted({m["badge"] for m in ended}), page=sorted({m["badge"] for m in page}))
    back = set_theme("none")
    check("T", "arrangement: approver-1's theme is the default again", back == "none", chosen=back)


# ---------------------------------------------------------------- G: geometry
PLAIN_JS = """(on) => { document.querySelectorAll('[data-r27-badge]').forEach(e => e.classList.toggle('batch-control-status', on));
  const t = [...document.querySelectorAll('#main-panel table')];
  return {doc: document.documentElement.scrollWidth, client: document.documentElement.clientWidth,
    tables: t.map(x => Math.round(x.getBoundingClientRect().width)), main: Math.round(document.querySelector('#main-panel').getBoundingClientRect().right),
    rows: [...document.querySelectorAll('[data-r27-badge]')].map(e => { const tr = e.closest('tr'); return tr ? Math.round(tr.getBoundingClientRect().height * 10) / 10 : null; }),
    cells: [...document.querySelectorAll('[data-r27-badge]')].map(e => { const tr = e.closest('tr'); return tr ? [...tr.children].map(c => {
      const r = c.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height), c.contains(e) ? 'badge' : (c.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 30)]; }) : null; })}; }"""


def sec_G():
    set_theme("none")
    s = Session(WHO)
    long_seen = {}
    for width in (1280, 1024, 768):
        s.page.set_viewport_size({"width": width, "height": 900})
        bad_pill, outside, taller, wider, sideways, new_scroll, count, long_wider = [], [], [], [], [], [], 0, None
        for key, path in screens():
            s.go(path)
            p = s.page.evaluate(BADGES_JS)
            with_ = s.page.evaluate(PLAIN_JS, True)
            without = s.page.evaluate(PLAIN_JS, False)
            s.page.evaluate(PLAIN_JS, True)
            for b, h1, h0, c1, c0 in zip(p["badges"], with_["rows"], without["rows"], with_["cells"], without["cells"]):
                count += 1
                bx, c = b["box"], b["cell"]
                room = [round(bx["x"] - c["x"], 1), round(bx["y"] - c["y"], 1), round(c["right"] - bx["right"], 1), round(c["bottom"] - bx["bottom"], 1)]
                lines = round(bx["h"] / b["lineHeight"]) if b["lineHeight"] else None
                if min(room) < -0.5:
                    outside.append({"screen": key, "text": b["text"][:40], "room": room})
                if not (b["tag"] == "span" and b["display"] == "inline-block" and b["radius"] >= 4 and min(room) >= -0.5
                        and room[0] >= 1 and room[1] >= 1 and room[3] >= 1 and bx["w"] < c["w"] and bx["h"] < c["h"]
                        and b["borderStyle"] == "solid" and b["borderWidth"] >= 1):
                    bad_pill.append({"screen": key, "text": b["text"][:40], "room": room, "display": b["display"], "radius": b["radius"]})
                if h1 is not None and h0 is not None and abs(h1 - h0) > 1 and lines == 1:  # logged: accepted 2026-10-14
                    taller.append({"screen": key, "text": b["text"][:40], "row": h1, "row_plain": h0,
                                   "cells_with_badge": c1, "cells_plain": c0})
                if b["text"].startswith("Revoked (its item was deleted) by " + F.LONG_ADMIN):
                    long_seen[width] = {"lines": lines, "badge": [round(bx["w"]), round(bx["h"])], "cell": [round(c["w"]), round(c["h"])],
                                        "room": room, "row": h1, "row_plain": h0}
                    s.page.locator(f"[data-r27-badge='{b['i']}']").evaluate("e => e.scrollIntoView({block: 'center'})")
                    s.page.screenshot(path=str(lib.SHOTS / f"R27-D2-S-long-wording-{width}.png"))
            grown = [a - b_ for a, b_ in zip(with_["tables"], without["tables"])]
            if key == "grants-list":  # its Ended table holds the long wording, an unbreakable 55-character user id
                long_wider = {"page": with_["doc"] - without["doc"], "tables": grown}
                grown = grown[:-1]
            if with_["doc"] > without["doc"] + 1 or any(g > 1 for g in grown):
                wider.append({"screen": key, "with": [with_["doc"], with_["tables"]], "without": [without["doc"], without["tables"]]})
            if with_["doc"] > with_["client"] + 2:
                sideways.append({"screen": key, "scroll_width": with_["doc"], "client_width": with_["client"], "plain": without["doc"]})
                if without["doc"] <= without["client"] + 2:
                    new_scroll.append(sideways[-1])
        check("G", f"D2 #18.2 geometry at {width} px: every badge is a span laid out as an inline block with rounded corners "
              "and a solid border, inside its cell and smaller than it, with room on the left, above and below (a pill, not "
              f"the painted cell) ({count} badges on seven screens)", count >= 20 and not bad_pill, wrong=bad_pill[:4])
        check("G", f"D2 #18.2 geometry at {width} px (owner decision 2026-10-14): every badge stays inside its cell, and the "
              "badges add no sideways page scroll that the same page without the badge styling does not already have",
              count >= 20 and not outside and not new_scroll, outside=outside[:4], new_sideways_scroll=new_scroll[:3],
              rows_taller_with_a_one_line_badge=len(taller))
        if taller:
            note("G", f"rows a one-line badge makes taller at {width} px (accepted by the owner on 2026-10-14; logged, not "
                 "judged)", rows=taller[:4])
        check("G", f"D2 #18.2 geometry at {width} px: the badges add no width: the page and each table are no wider than "
              "with the badge styling taken away (the table with the long wording is judged apart)", count >= 20 and not wider,
              wider=wider[:3])
        S.setdefault("long_wider", {})[width] = long_wider
        if width == 1280:
            check("G", "guard: at 1280 px no screen with badges scrolls sideways", not sideways, sideways=sideways)
        else:
            note("G", f"sideways scrolling at {width} px (with the badges, and the same page without their styling)",
                 sideways=sideways)
    s.done()
    grown = S.get("long_wider", {})
    check("G", "D2 #18.2 geometry: the long wording 'Revoked (its item was deleted) by <a 55-character user id>' stays inside "
          "its cell at 1280, 1024 and 768 px, wrapped or not, and its table grows by no more than the pill's own padding "
          "and border (18 px) and the page not at all",
          set(long_seen) == {1280, 1024, 768} and all(min(v["room"]) >= -0.5 for v in long_seen.values())
          and all(g and g["page"] <= 1 and max(g["tables"]) <= 18 for g in grown.values()), measured=long_seen, grown=grown)
    note("G", "the long wording per width: lines of the badge, its size, its cell, the row with and without the styling, "
         "and how much wider its table and the page are with the badge than without", measured=long_seen, grown=grown)


# ---------------------------------------------------------------- C: Content-Security-Policy
CSP_INIT = """window.__r27csp = []; document.addEventListener('securitypolicyviolation', e => window.__r27csp.push(
  {directive: e.violatedDirective, effective: e.effectiveDirective, blocked: e.blockedURI, source: e.sourceFile, line: e.lineNumber,
   sample: (e.sample || '').slice(0, 80), disposition: e.disposition}));"""
ENFORCE = """def c = jenkins.model.Jenkins.get().getExtensionList(jenkins.security.csp.impl.CspConfiguration).get(0)
def before = c.isEnforce(); c.setEnforce(%s); c.save(); return String.valueOf(before) + ' -> ' + c.isEnforce()"""


def sec_C():
    S["csp_before"] = gv(ENFORCE % "true")
    try:
        s = Session(WHO)
        s.context.add_init_script(CSP_INIT)
        found, headers, styled, badges = [], {}, [], {}
        for key, path in screens() + (("requests-list", "/batch-control/requests/"), ("history-incidents", f"/batch-control/history/?kind=incidents&job={P}"),
                                      ("dashboard", "/batch-control/dashboard/"), ("history-runs", f"/batch-control/history/?kind=runs&job={P}")):
            before = len(s.console)
            r = s.go(path)
            s.page.wait_for_timeout(300)  # violation events are delivered asynchronously after load
            h = r.headers if r else {}
            headers[key] = [k for k in ("content-security-policy", "content-security-policy-report-only") if k in h]
            S.setdefault("csp_policy", h.get("content-security-policy", ""))
            v = s.page.evaluate("window.__r27csp || []")
            cons = [c for c in s.console[before:] if "Content Security Policy" in c or "Content-Security-Policy" in c]
            found += [dict(x, screen=key) for x in v] + [{"screen": key, "console": c[:200]} for c in cons]
            styled += s.page.evaluate("""() => [...document.querySelectorAll('.batch-control-status')].filter(e => e.hasAttribute('style') || e.querySelector('[style]')).map(e => e.outerHTML.slice(0, 120))""")
            badges[key] = s.page.locator(".batch-control-status").count()
        s.done()
    finally:
        S["csp_after"] = gv(ENFORCE % "false")
    ours = [x for x in found if "style" in str(x.get("directive", "")) + str(x.get("effective", "")) or "batch" in str(x).lower()
            or "style" in str(x.get("console", "")).lower()]
    check("C", "arrangement: Content-Security-Policy enforcement was switched on for the pass (every screen answered with "
          "the header Content-Security-Policy, not the report-only one) and off again",
          S["csp_before"].endswith("-> true") and S["csp_after"].endswith("-> false")
          and all(v == ["content-security-policy"] for v in headers.values()), before=S["csp_before"], after=S["csp_after"],
          headers=headers, policy=S.get("csp_policy", "")[:300])
    causes_only = ("dashboard", "history-runs")
    check("C", "D2 #18.2 under the enforced policy the nine screens with badges and the two with run causes raise no "
          "Content-Security-Policy violation at all (securitypolicyviolation events and console messages), each badge "
          "screen shows badges, and no badge has a style attribute on or in it",
          len(headers) == 11 and not found and not styled and all(n >= 1 for k, n in badges.items() if k not in causes_only),
          violations_of_ours=ours[:4], all_violations=len(found), styled=styled[:3], badges=badges)
    note("C", "every Content-Security-Policy violation the browser reported during the pass (none means none at all); core's "
         "enforced policy allows inline styles (style-src 'unsafe-inline'), so the pass cannot catch a style attribute: "
         "the DOM check above (no style attribute on or in a badge) is what guards it", violations=found[:10], count=len(found),
         style_src=re.search(r"style-src[^;]*", S.get("csp_policy", "")).group(0) if "style-src" in S.get("csp_policy", "") else None)


# ---------------------------------------------------------------- H: forced colours
def sec_H():
    b = lib._r6.browser()
    ctx = b.new_context(viewport={"width": 1280, "height": 900}, locale="en-US", forced_colors="active")
    try:
        page = ctx.new_page()
        page.set_default_timeout(20000)
        page.goto(lib.BASE + "/login")
        page.fill("#j_username", WHO)
        page.fill('input[name="j_password"]', lib.pw(WHO))
        page.click('button[name="Submit"], button[type="submit"]')
        page.wait_for_load_state("load")
        r = page.goto(lib.BASE + f"/batch-control/history/?kind=requests&job={P}")
        page.wait_for_load_state("load")
        active = page.evaluate("matchMedia('(forced-colors: active)').matches")

        class Shim:  # measure() needs .page only
            pass
        shim = Shim()
        shim.page = page
        p, badges = measure(shim)
        page.evaluate("window.scrollTo(0, 0)")
        page.locator("#main-panel table").first.screenshot(path=str(lib.SHOTS / "R27-D2-S-forced-colours-history-requests.png"))
        rows = []
        for x in badges:
            if not x["cell_painted"]:
                continue
            rows.append({"enum": x["enum"], "tone": x["tone"], "text": hexc(x["color"][:3]), "badge": hexc(x["painted"]),
                         "cell": hexc(x["cell_painted"]), "border": hexc(x["border"][:3]), "border_alpha": x["border"][3],
                         "border_style": x["borderStyle"], "border_width": x["borderWidth"],
                         "text_on_badge": contrast(x["color"][:3], x["painted"]),
                         "border_vs_cell": contrast(over(x["border"], x["cell_painted"]), x["cell_painted"])})
    finally:
        ctx.close()
    weak = [m for m in rows if m["border_style"] != "solid" or m["border_width"] < 1 or m["border_vs_cell"] < 3 or m["text_on_badge"] < 4.5]
    check("H", "D2 #18.2 forced colours (forced-colors: active): on History > Requests every badge keeps a solid border of "
          "at least 1 px whose colour stands out from the cell (contrast at least 3:1) and text with a contrast of at least "
          "4.5:1 on what is painted behind it; all five tones are among the badges", (r.status if r else None) == 200 and active
          and len(rows) >= 7 and not weak and {m["tone"] for m in rows} == set(TONES), forced_colors_active=active,
          badges=len(rows), weak=weak[:3], sample=rows[:2])
    note("H", "forced colours: what the five tones look like (the tints are replaced by the system colours)",
         per_tone={t: next(({k: m[k] for k in ("text", "badge", "cell", "border", "text_on_badge", "border_vs_cell")}
                            for m in rows if m["tone"] == t), None) for t in TONES})


def cleanup():
    theme = set_theme("none")
    csp = gv(ENFORCE % "false")
    check("cleanup", "approver-1's theme is the default and Content-Security-Policy enforcement is off", theme == "none"
          and csp.endswith("-> false"), theme=theme, enforcement=csp)
    note("cleanup", "restore", swept=lib.sweep("requester", P))


if __name__ == "__main__":
    lib.run(sys.argv, {"A": sec_A, "T": sec_T, "G": sec_G, "C": sec_C, "H": sec_H}, cleanup)
