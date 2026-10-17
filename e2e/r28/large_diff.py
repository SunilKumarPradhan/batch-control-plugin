"""e2e-28 #35: the diff of a large job configuration on a real Jenkins (TEST-MATRIX T-09-90..92, note 350). The fix
computes the same unified diff in linear memory; what a person sees must be unchanged and saving a large configuration
must stay healthy.

usage: python large_diff.py [AFRSCM]   rows: r27/out/large_diff.jsonl, shots: screenshots/run-27/R28-35-*.png
Items (created again by A): r28-big (a description of 4,000 lines, one config.xml line each), r28-small (3 lines),
r28-huge (6,000 lines, beyond the existing cap), r28-control (4,000 lines, the unrecorded reference of M). The
administrator saves; the auditor (ViewHistory only) reads the Changes page; the expected diff is computed here with
difflib from the job's config.xml file before and after the save (a CR the form sends stays &#xd;), and the
three context lines, hunks compared header by header and line by line. The checks of F, R, S
and C hold on a build with and without the fix (the diff is unchanged by design): guards. Only M can be red.

A  arrangement: run control and change control on; the four jobs created over REST, one form save of r28-big and one
   REST save of r28-small and r28-huge so their snapshots hold what the forms and REST write.
F  the real configure form (administrator, browser): r28-big's description saved with every 100th line changed (40
   changes): the save answers below 400 and lands on the job page; changes.csv holds exactly one new CONFIGURE record for
   r28-big; its stored diff equals the difflib diff of the job's config.xml before and after, hunk by hunk;
   the auditor's Changes page shows that record with that diff, line by line, in its expandable Diff.
R  the same over REST (POST config.xml) with 40 other lines changed.
S  guard (T-09-91): r28-small's middle line changed: one record; one hunk removing the old line, adding the new one,
   the other two description lines as context.
C  guard (T-09-92, the existing cap): r28-huge saved with 60 changes: one record whose diff is the note "Diff too large
   to store (N lines); the change was recorded without the full diff.", shown as such to the auditor.
   Also in F, R, S, C: the controller log of the save window holds no OutOfMemoryError and no exception from the plugin.
M  #35 memory on the real controller (T-09-90's measure in the script console): the bytes the saving thread allocates
   for r28-big's description save (40 changes, after a warm-up save), minus the same save of r28-control while both
   switches are off (unrecorded), are below 16 MB. Red without the fix (about 64 MB of LCS table at this size).
cleanup: the four jobs deleted; the switches as they were."""
import difflib
import re
import subprocess
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 2)[0] + "/r27")
import lib  # noqa: E402
from lib import api, check, note, Session, gv  # noqa: E402

lib.LOGNAME[0] = "large_diff"
BIG, SMALL, HUGE, CONTROL = "r28-big", "r28-small", "r28-huge", "r28-control"
STORE = "/var/jenkins_home/batch-control"
NOTE_RE = re.compile(r"^Diff too large to store \((\d+) lines\); the change was recorded without the full diff\.$")
S = {}


def lines(n, tag="", every=0, offset=0):
    """`n` description lines; with `every`, line i (1-based) with (i + offset) % every == 0 says it was changed by `tag`."""
    return "\n".join(f"r28 line {i:05d}" + (f" changed {tag}" if every and (i + offset) % every == 0 else "")
                     for i in range(1, n + 1))


def xml(desc):
    from xml.sax.saxutils import escape
    return (f"<?xml version='1.1' encoding='UTF-8'?>\n<project>\n  <description>{escape(desc).replace(chr(13), '&#13;')}</description>\n"
            "  <keepDependencies>false</keepDependencies>\n  <properties/>\n  <scm class=\"hudson.scm.NullSCM\"/>\n"
            "  <canRoam>true</canRoam>\n  <disabled>false</disabled>\n  <triggers/>\n  <builders/>\n  <publishers/>\n"
            "  <buildWrappers/>\n</project>\n")


def config(job):
    """The job's config.xml file on disk (what the plugin diffs: GET config.xml re-serialises the declaration)."""
    return cat(f"/var/jenkins_home/jobs/{job}/config.xml")


def cat(path):
    rc, out = lib.L25.dexec("cat", path)
    return out if rc == 0 else None


def post_config(job, desc):
    return api("admin", lib.jpath(job) + "/config.xml", "POST", data=xml(desc).encode("utf-8"),
               headers={"Content-Type": "application/xml"}).status_code


def csv_count(job):
    """The CONFIGURE records of `job` in changes.csv (the export the auditor downloads)."""
    import csv as _csv
    import io
    r = api("auditor", "/batch-control/history/changes.csv")
    return sum(1 for x in _csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")))
               if x.get("target") == job and x.get("type") == "CONFIGURE")


def configure_since(job, since_ms):
    """The CONFIGURE records of `job` written at or after `since_ms`, read from the store (id, at)."""
    out = gv(f"""def f = new File('{STORE}/changes'); def res = []
(f.listFiles() ?: []).findAll {{ it.name.endsWith('.jsonl') }}.each {{ it.eachLine('UTF-8') {{ l ->
  def m = new groovy.json.JsonSlurper().parseText(l)
  if (m.type == 'CONFIGURE' && m.target == '{job}' && (m.at as long) >= {since_ms}L) res << m.id }} }}
return res.join(',')""")
    return [x for x in out.split(",") if x]


def hunks(text):
    """[(old start, old count, new start, new count), [body lines]] of a unified diff (counts default to 1)."""
    out, cur = [], None
    for ln in text.splitlines():
        m = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", ln)
        if m:
            cur = [(int(m[1]), int(m[2] or 1), int(m[3]), int(m[4] or 1)), []]
            out.append(cur)
        elif cur is not None:
            cur[1].append(ln)
    return out


def expected(before, after):
    # SPEC 9: the plugin compares the user-editable content of config.xml, without the plugin="name@version"
    # attributes, the root's <actions> child and integer <configVersion> leaves; the same is left out here, on both sides
    keep = lambda text: [re.sub(r' plugin="[^"]*"', "", ln) for ln in text.splitlines()  # noqa: E731
                         if ln.strip() != "<actions/>" and not re.fullmatch(r"\s*<configVersion>\d+</configVersion>", ln)]
    return "\n".join(difflib.unified_diff(keep(before), keep(after), "before", "after", n=3, lineterm=""))


def log_issues(since_s):
    p = subprocess.run(["docker", "logs", "--since", str(int(since_s)), lib.L25.CONTAINER], capture_output=True, text=True)
    text = p.stdout + p.stderr
    return [ln[:200] for ln in text.splitlines() if "OutOfMemoryError" in ln or (
        "batchcontrol" in ln and re.search(r"Exception|SEVERE", ln))][:5]


def auditor_diff(job, rid, shot):
    """The auditor's Changes page: the row of record `rid`'s job, newest first; the text of its expanded Diff."""
    s = Session("auditor")
    s.go("/batch-control/changes/")
    row = s.page.locator("#main-panel table tbody tr", has_text=job).first
    shown = {"found": bool(row.count())}
    if row.count():
        summ = row.locator("details summary").first
        shown["summary"] = re.sub(r"\s+", " ", summ.inner_text()).strip() if summ.count() else None
        if summ.count():
            summ.click()
        pre = row.locator("details pre").first
        shown["diff"] = pre.inner_text() if pre.count() else (re.sub(r"\s+", " ", row.inner_text()))
        row.scroll_into_view_if_needed()
        s.shot(row, shot)
    s.done()
    return shown


def judge_save(sec, job, how, status, before, mark_ms, mark_s, csv_before, cap=False):
    ids = configure_since(job, mark_ms)
    csv_now = csv_count(job)
    after = config(job)
    patch = cat(f"{STORE}/changes/diff/{ids[0]}.patch") if len(ids) == 1 else None
    issues = log_issues(mark_s)
    check(sec, f"guard ({how}): the save of {job} answers below 400, exactly one new CONFIGURE record is written (store and the auditor's changes.csv), and the "
          "controller log of the save holds no OutOfMemoryError and no exception from the plugin",
          status is not None and status < 400 and len(ids) == 1 and csv_now == csv_before + 1 and not issues,
          status=status, records=ids, changes_csv=[csv_before, csv_now], log=issues)
    if cap:
        m = NOTE_RE.match((patch or "").strip())
        check(sec, f"guard (T-09-92, the existing cap; {how}): the record's diff is the note 'Diff too large to store (N "
              "lines); the change was recorded without the full diff.'", bool(m), diff=(patch or "")[:200])
        shown = auditor_diff(job, ids[0] if ids else None, f"R28-35-{sec}-auditor")
        check(sec, f"guard ({how}): the auditor's Changes page shows that note for {job}",
              shown.get("found") and (patch or "").strip() in (shown.get("diff") or ""), shown={k: (v or "")[:200] if isinstance(v, str) else v for k, v in shown.items()})
        return
    want = expected(before or "", after or "")
    got_h, want_h = hunks(patch or ""), hunks(want)
    check(sec, f"guard (diff unchanged by design; {how}): the stored diff of {job} equals the diff computed with difflib from "
          f"the job's config.xml before and after: {len(want_h)} hunks, headers and lines identical",
          bool(want_h) and got_h == want_h and (patch or "").startswith("--- before\n+++ after\n"),
          hunks=len(got_h), expected_hunks=len(want_h), first_difference=next((
              {"got": g, "want": w} for g, w in zip(got_h, want_h) if g != w), None) if got_h != want_h else None)
    shown = auditor_diff(job, ids[0] if ids else None, f"R28-35-{sec}-auditor")
    check(sec, f"guard ({how}): the auditor (ViewHistory) sees that record for {job} on the Changes page, and its expanded "
          "Diff shows the stored diff line by line", shown.get("found") and (shown.get("diff") or "").splitlines()
          == (patch or "").rstrip("\n").splitlines(), summary=shown.get("summary"),
          lines=[len((shown.get("diff") or "").splitlines()), len((patch or "").splitlines())])
    S.setdefault("hunks", {})[f"{sec} {job}"] = len(got_h)


def sec_A():
    S["switches"] = lib.facts(lib.L25.CFG + "return groovy.json.JsonOutput.toJson([run: cfg.runControlEnabled, "
                              "change: cfg.changeControlEnabled])")
    for j in (BIG, SMALL, HUGE, CONTROL):
        if api("admin", lib.jpath(j) + "/api/json").status_code == 200:
            api("admin", lib.jpath(j) + "/doDelete", "POST")
    made = {j: lib.ensure_item(j, xml(lines(n))) for j, n in ((BIG, 4000), (SMALL, 3), (HUGE, 6000), (CONTROL, 4000))}
    s = Session("admin")
    s.go(lib.jpath(BIG) + "/configure")
    with s.page.expect_navigation(timeout=60000):
        s.page.locator("button[name=Submit]").first.click()
    s.done()
    warm = {j: post_config(j, lines(n)) for j, n in ((SMALL, 3), (HUGE, 6000))}
    snaps = {j: cat(f"{STORE}/snapshots/{j}.xml") is not None for j in (BIG, SMALL, HUGE)}
    check("A", "arrangement: run control and change control on; r28-big (4,000 description lines), r28-small (3), r28-huge "
          "(6,000) and r28-control (4,000) created; r28-big saved once through the form, r28-small and r28-huge once over "
          "REST; each has a snapshot", S["switches"] == {"run": True, "change": True} and all(made.values())
          and all(v < 400 for v in warm.values()) and all(snaps.values()), switches=S["switches"], created=made,
          warm=warm, snapshots=snaps)


def sec_F():
    before, n0 = config(BIG), csv_count(BIG)
    desc = lines(4000, "by the form", every=100)
    s = Session("admin")
    s.go(lib.jpath(BIG) + "/configure")
    mark_ms, mark_s = int(gv("return System.currentTimeMillis()")), time.time() - 2
    s.page.locator("textarea[name=description]").first.fill(desc)
    t0 = time.time()
    with s.page.expect_navigation(timeout=120000) as nav:
        s.page.locator("button[name=Submit]").first.click()
    status, took = (nav.value.status if nav.value else None), round(time.time() - t0, 1)
    landed = s.page.url.replace(lib.BASE, "")
    s.done()
    note("F", "the form save", status=status, seconds=took, landed=landed)
    judge_save("F", BIG, "configure form", status if landed.rstrip("/").endswith(BIG) else None, before, mark_ms, mark_s, n0)


def sec_R():
    before, n0 = config(BIG), csv_count(BIG)
    mark_ms, mark_s = int(gv("return System.currentTimeMillis()")), time.time() - 2
    # CRLF, as the form's textarea left the description: only the 40 changed lines differ
    status = post_config(BIG, lines(4000, "over REST", every=100, offset=50).replace("\n", "\r\n"))
    judge_save("R", BIG, "REST config.xml", status, before, mark_ms, mark_s, n0)


def sec_S():
    before, n0 = config(SMALL), csv_count(SMALL)
    mark_ms, mark_s = int(gv("return System.currentTimeMillis()")), time.time() - 2
    status = post_config(SMALL, "r28 line 00001\nr28 line 00002 changed\nr28 line 00003")
    judge_save("S", SMALL, "small change, REST", status, before, mark_ms, mark_s, n0)
    ids = configure_since(SMALL, mark_ms)
    patch = cat(f"{STORE}/changes/diff/{ids[0]}.patch") if ids else ""
    h = hunks(patch or "")
    body = h[0][1] if len(h) == 1 else []
    check("S", "guard (T-09-91): the small change's diff has one hunk that removes exactly the old middle line, adds exactly "
          "the new one and keeps the other two description lines as context",
          len(h) == 1 and [x for x in body if x.startswith("-")] == ["-r28 line 00002"]
          and [x for x in body if x.startswith("+")] == ["+r28 line 00002 changed"]
          and any(x.startswith(" ") and "r28 line 00001" in x for x in body)
          and any(x.startswith(" ") and "r28 line 00003" in x for x in body), hunks=h)


def sec_C():
    before, n0 = config(HUGE), csv_count(HUGE)
    mark_ms, mark_s = int(gv("return System.currentTimeMillis()")), time.time() - 2
    status = post_config(HUGE, lines(6000, "beyond the cap", every=100))
    judge_save("C", HUGE, "6,000 lines, REST", status, before, mark_ms, mark_s, n0, cap=True)


MEASURE = """import java.lang.management.ManagementFactory
def mx = ManagementFactory.threadMXBean; def t = Thread.currentThread().id
def j = jenkins.model.Jenkins.get().getItemByFullName('%s')
def lines = { tag -> (1..4000).collect { i -> String.format('r28 line %%05d', i) + (i %% 100 == 0 ? ' ' + tag : '') }.join('\\n') }
j.setDescription(lines('warm-up %s'))
def a0 = mx.getThreadAllocatedBytes(t); j.setDescription(lines('measured %s')); def a1 = mx.getThreadAllocatedBytes(t)
return String.valueOf(a1 - a0)"""


def sec_M():
    stamp = str(int(time.time()))
    recorded = int(gv(MEASURE % (BIG, stamp, stamp)))
    off = lib.gv(lib.L25.CFG + "cfg.setChangeControlEnabled(false); cfg.setRunControlEnabled(false); cfg.save(); return 'off'")
    try:
        unrecorded = int(gv(MEASURE % (CONTROL, stamp, stamp)))
    finally:
        on = lib.gv(lib.L25.CFG + f"cfg.setRunControlEnabled({str(S['switches']['run']).lower()}); "
                    f"cfg.setChangeControlEnabled({str(S['switches']['change']).lower()}); cfg.save(); return 'restored'")
    share = recorded - unrecorded
    mb = lambda b: round(b / 1048576, 1)  # noqa: E731
    check("M", "#35 memory (T-09-90 on the real controller): the saving thread's allocation for r28-big's 4,000-line "
          "description save with 40 changes, minus the same save of r28-control while both switches are off, is below "
          "16 MB", share < 16 * 1048576, recorded_mb=mb(recorded), unrecorded_mb=mb(unrecorded), plugin_share_mb=mb(share),
          switches=[off, on])


def cleanup():
    note("cleanup", "restore", deleted={j: api("admin", lib.jpath(j) + "/doDelete", "POST").status_code
                                         for j in (BIG, SMALL, HUGE, CONTROL)})


if __name__ == "__main__":
    lib.run(sys.argv, {"A": sec_A, "F": sec_F, "R": sec_R, "S": sec_S, "C": sec_C, "M": sec_M}, cleanup)
