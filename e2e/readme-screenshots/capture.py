"""Recreates the demo data and the six README screenshots (docs/images/*.png). See README.md next to this file.

The screenshots follow the README's three steps, each taken as the account that does the step:
  1. set it up            global-config (admin)
  2. run a protected job  request-run (requester) -> approval (approver-1) -> history (approver-1)
  3. change a job safely  permission-window (requester) -> permission-window-approval (approver-1)
The request of step 2 and the window of step 3 are the same ones from form to decision: the form that is
photographed is submitted, its approver's page is photographed, and the run request is then approved so that
History shows it as EXECUTED. Every image is 1280 px wide and carries at most two highlight frames, drawn by
highlight() right before the capture (one style, see ACCENT); nothing is edited by hand afterwards.

Runs against a running e2e stack (scripts/up.sh, Jenkins at the root context), preferably a fresh one: the seed
is skipped when the folder `batch` already exists, the screenshots are always taken (each run adds one executed
run request and one pending permission window request, the ones the two forms submit). Reuses ../r6/lib.py:
Session (one browser context per account, real login form), api (basic auth + crumb) and groovy (script console).
The script console only arranges state (settings, the demo folder and jobs); every run request, decision, grant
and configuration change goes through the plugin's own HTTP endpoints as the account a person would use, the
screenshots through the browser.
"""
import json
import os
import pathlib
import re
import sys
import time
from urllib.parse import urlparse

HERE = pathlib.Path(__file__).resolve().parent
IMAGES = HERE.parent.parent / "docs" / "images"

# lib.py reads both at import. The regular stack serves Jenkins at the root context. Playwright's own Chromium
# formats <input type=date> from the context locale (en-US); Google Chrome would use the host's locale.
_port = "8080"
for _line in (HERE.parent / ".env").read_text().splitlines():
    if _line.startswith("BC_PORT="):
        _port = _line.split("=", 1)[1].strip() or _port
os.environ.setdefault("BC_BASE", f"http://localhost:{_port}")
os.environ.setdefault("BC_BROWSER_CHANNEL", "chromium")
sys.path.insert(0, str(HERE.parent / "r6"))
import lib  # noqa: E402

PREFIX = urlparse(lib.BASE).path.rstrip("/")
FOLDER = "batch"
SETTLEMENT = f"/job/{FOLDER}/job/daily-settlement"
LOAD = f"/job/{FOLDER}/job/nightly-load"
CLOSE = f"/job/{FOLDER}/job/month-end-close"
BOTH = ["approver-1", "approver-2"]

# ------------------------------------------------------------------------------------------------- seed

SEED = r"""
import jenkins.model.Jenkins
import com.cloudbees.hudson.plugins.folder.Folder

def j = Jenkins.get()
if (j.getItemByFullName('%(folder)s') != null) { println 'SEED-SKIPPED'; return }
j.setSystemMessage(null)
j.save()

// Production-like settings instead of the e2e minimums of casc/jenkins.yaml (JCasC restores those on a reboot).
def cfg = j.getExtensionList('io.jenkins.plugins.batchcontrol.config.BatchControlGlobalConfiguration')[0]
cfg.setApprovers(['approver-1', 'approver-2', 'admin'])
cfg.setPendingTimeoutHours(24)
cfg.setApprovedRunTimeoutMinutes(60)
cfg.setGrantDurationOptions([15, 30, 60, 120])
cfg.setMaxGrantMinutes(240)
cfg.setNotifyBeforeExpiryMinutes(10)
cfg.save()

def folder = j.createProject(Folder, '%(folder)s')
folder.setDescription('Settlement and data-warehouse batches. Runs need an approved run request.')
folder.save()
def jobs = %(jobs)s
jobs.each { name, xml -> folder.createProjectFromXML(name, new ByteArrayInputStream(xml.getBytes('UTF-8'))) }
println 'SEED-DONE'
"""


def _string(name, desc):
    return (f"<hudson.model.StringParameterDefinition><name>{name}</name><description>{desc}</description>"
            "<defaultValue></defaultValue><trim>true</trim></hudson.model.StringParameterDefinition>")


def _bool(name, desc, default):
    return (f"<hudson.model.BooleanParameterDefinition><name>{name}</name><description>{desc}</description>"
            f"<defaultValue>{str(default).lower()}</defaultValue></hudson.model.BooleanParameterDefinition>")


def _choice(name, desc, choices):
    items = "".join(f"<string>{c}</string>" for c in choices)
    return (f"<hudson.model.ChoiceParameterDefinition><name>{name}</name><description>{desc}</description>"
            f'<choices class="java.util.Arrays$ArrayList"><a class="string-array">{items}</a></choices>'
            "</hudson.model.ChoiceParameterDefinition>")


def _job(description, params, command):
    return ("<project><description>" + description + "</description><keepDependencies>false</keepDependencies>"
            "<properties><hudson.model.ParametersDefinitionProperty><parameterDefinitions>" + "".join(params)
            + "</parameterDefinitions></hudson.model.ParametersDefinitionProperty></properties>"
            '<scm class="hudson.scm.NullSCM"/><canRoam>true</canRoam><disabled>false</disabled>'
            "<builders><hudson.tasks.Shell><command>" + command.replace("&", "&amp;").replace("<", "&lt;")
            + "</command></hudson.tasks.Shell></builders><publishers/><buildWrappers/></project>")


JOBS = {
    "daily-settlement": _job(
        "Posts the day's card and transfer settlements to the general ledger.",
        [_string("BUSINESS_DATE", "Business date to settle (YYYY-MM-DD)."),
         _choice("SCOPE", "Settlement streams to process.", ["ALL", "CARD", "TRANSFER"]),
         _bool("DRY_RUN", "Validate and report only; nothing is posted to the ledger.", True)],
        'echo "Settling ${BUSINESS_DATE} (scope ${SCOPE}, dry run ${DRY_RUN})"\nsleep 3\necho "18240 entries balanced"\n'),
    "nightly-load": _job(
        "Loads the vendor extracts into the data warehouse.",
        [_string("LOAD_DATE", "Extract date to load (YYYY-MM-DD)."),
         _choice("TARGET", "Warehouse schema to load into.", ["dwh_prod", "dwh_replay"]),
         _bool("FULL_RELOAD", "Truncate and reload the day instead of merging.", False)],
        # The first run of a date fails (the extract "is missing"), the re-run succeeds: one incident.
        'SRC=/data/inbound/legacy-sftp\necho "Loading ${LOAD_DATE} from ${SRC} into ${TARGET}"\nsleep 1\n'
        'if [ ! -f "$WORKSPACE/.seen-${LOAD_DATE}" ]; then touch "$WORKSPACE/.seen-${LOAD_DATE}"; '
        'echo "ERROR: extract for ${LOAD_DATE} not found in ${SRC}"; exit 1; fi\nsleep 2\necho "Load complete"\n'),
    "month-end-close": _job(
        "Closes the accounting month: accruals, FX revaluation and the trial balance.",
        [_string("CLOSING_MONTH", "Month to close (YYYY-MM).")],
        'echo "Closing ${CLOSING_MONTH}"\nsleep 2\n'),
}


def rel(location):
    """A redirect target as a path relative to lib.BASE (Jenkins may answer with an absolute URL)."""
    path = urlparse(location).path
    return path[len(PREFIX):] if PREFIX and path.startswith(PREFIX) else path


def post(user, path, data, expect=(302, 303)):
    r = lib.api(user, path, "POST", data=data)
    if r.status_code not in expect:
        raise RuntimeError(f"POST {path} as {user}: HTTP {r.status_code}\n{r.text[:800]}")
    return r


def request_run(job, reason, params, approvers):
    """A run request as `requester`, posted urlencoded (the REST form of the request, D-37)."""
    body = {"reason": reason, "approvers": approvers,
            "parameter": [{"name": k, "value": v} for k, v in params.items()]}
    return rel(post("requester", f"{job}/batch-control/submit", {"json": json.dumps(body)}).headers["Location"])


def wait_build(job, number, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        r = lib.api("admin", f"{job}/{number}/api/json?tree=building,result")
        if r.status_code == 200 and not r.json()["building"]:
            return r.json()["result"]
        time.sleep(1)
    raise RuntimeError(f"{job} #{number} did not finish")


def approve_and_run(job, number, req, approver, comment):
    post(approver, req + "approve", {"comment": comment})
    return wait_build(job, number)


def seed():
    jobs = "[" + ", ".join(f"'{n}': '''{x}'''" for n, x in JOBS.items()) + "]"
    out = lib.groovy(SEED % {"folder": FOLDER, "jobs": jobs})
    print("seed:", out.splitlines()[-1] if out else "(no output)")
    if "SEED-DONE" not in out:
        return
    r = request_run(SETTLEMENT, "Regular 01:30 settlement for 2026-10-07 was skipped during the DB maintenance "
                    "window (CHG-2291).", {"BUSINESS_DATE": "2026-10-07", "SCOPE": "ALL", "DRY_RUN": False}, BOTH)
    print("daily-settlement #1", approve_and_run(SETTLEMENT, 1, r, "approver-1", "Maintenance closed at 02:10, go ahead."))
    r = request_run(LOAD, "Nightly load aborted at 03:12 on a lock timeout; re-run for 2026-10-08.",
                    {"LOAD_DATE": "2026-10-08", "TARGET": "dwh_prod", "FULL_RELOAD": False}, BOTH)
    print("nightly-load #1", approve_and_run(LOAD, 1, r, "approver-2", "Approved."))
    r = request_run(CLOSE, "Re-close September after the late FX adjustment journal (FIN-118).",
                    {"CLOSING_MONTH": "2026-09"}, ["approver-1"])
    post("approver-1", r + "reject", {"comment": "Wait for the controller's sign-off, then resubmit."})
    r = request_run(LOAD, "Second attempt for 2026-10-08: the extract was re-delivered at 06:40.",
                    {"LOAD_DATE": "2026-10-08", "TARGET": "dwh_prod", "FULL_RELOAD": False}, BOTH)
    print("nightly-load #2", approve_and_run(LOAD, 2, r, "approver-1", "File confirmed on the SFTP host."))
    r = request_run(SETTLEMENT, "Dry run to check the 2026-10-08 totals before the real posting.",
                    {"BUSINESS_DATE": "2026-10-08", "SCOPE": "CARD", "DRY_RUN": True}, BOTH)
    print("daily-settlement #2", approve_and_run(SETTLEMENT, 2, r, "approver-2", "OK for a dry run."))
    r = request_run(CLOSE, "Submitted twice by mistake.", {"CLOSING_MONTH": "2026-09"}, ["approver-1"])
    post("requester", r + "cancel", {})
    request_run(LOAD, "Backfill 2026-10-05 so the new merchant dimension is populated.",
                {"LOAD_DATE": "2026-10-05", "TARGET": "dwh_prod", "FULL_RELOAD": True}, BOTH)

    # Permission window: CONFIGURE on nightly-load, approved, then a configuration change made inside it.
    r = post("requester", "/batch-control/grants/create", {
        "scopeFullName": f"{FOLDER}/nightly-load", "actions": "CONFIGURE", "durationMinutes": "30",
        "reason": "Point the extract path to the new SFTP host (CHG-2304).", "approvers": BOTH})
    grant = rel(r.headers["Location"])
    if not re.fullmatch(r"/batch-control/grants/[0-9a-f-]{36}/", grant):  # not the new request's page: the only one
        grant = re.findall(r'href="[^"]*(/batch-control/grants/[0-9a-f-]{36}/)"',
                           lib.api("requester", "/batch-control/grants/").text)[0]
    post("approver-2", grant + "approve", {"comment": "Approved for the CHG-2304 window."})
    xml = lib.api("requester", f"{LOAD}/config.xml").text
    r = lib.api("requester", f"{LOAD}/config.xml", "POST",
                data=xml.replace("/data/inbound/legacy-sftp", "/data/inbound/sftp-02").encode("utf-8"),
                headers={"Content-Type": "application/xml"})
    print("configuration change inside the window: HTTP", r.status_code)
    post("requester", "/batch-control/grants/create", {
        "scopeFullName": FOLDER, "actions": "CREATE", "createNamePattern": "fx-revaluation",
        "durationMinutes": "60", "reason": "Create the fx-revaluation job for the new FX revaluation batch (PRJ-77).",
        "approvers": ["approver-1"]})


# ------------------------------------------------------------------------------------------ screenshots

# The one highlight colour. A hue that these pages do not use themselves: Jenkins' blue is the primary button, the
# links and the checked boxes, red is Reject, orange the warnings and the tab badges, green the build results.
ACCENT = "#c026d3"
RING = 3  # px, line width of a highlight frame
GAP = 6   # px left free between the highlighted elements and their frame

# Frames in viewport coordinates in; one absolutely positioned <div> per frame out. Returns what a frame's line
# would cross (visible text, form controls, buttons, icons) and a frame that did not land where it was asked.
FRAMES_JS = r"""([frames, ring, colour]) => {
  const wrong = [];
  const lines = f => [[f.x, f.y, f.w, ring], [f.x, f.y + f.h - ring, f.w, ring],
                      [f.x, f.y, ring, f.h], [f.x + f.w - ring, f.y, ring, f.h]];
  const check = (r, what) => {
    if (r.width > 0 && r.height > 0 && frames.some(f => lines(f).some(
        ([x, y, w, h]) => x < r.right && r.left < x + w && y < r.bottom && r.top < y + h))) {
      wrong.push('crosses ' + what.trim().replace(/\s+/g, ' ').slice(0, 40));
    }
  };
  const shown = e => e.checkVisibility({visibilityProperty: true, opacityProperty: true});
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const range = document.createRange();
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (!n.data.trim() || !shown(n.parentElement)) continue;
    range.selectNodeContents(n);
    for (const r of range.getClientRects()) check(r, n.data);
  }
  const controls = 'input:not([type=hidden]), textarea, select, button, a.jenkins-button, label, svg';
  for (const e of document.querySelectorAll(controls)) {
    if (shown(e)) check(e.getBoundingClientRect(), `<${e.tagName.toLowerCase()}> ${e.name || e.innerText || ''}`);
  }
  for (const f of frames) {
    const d = document.createElement('div');
    d.style.cssText = `position: absolute; left: ${f.x + scrollX}px; top: ${f.y + scrollY}px; width: ${f.w}px; `
      + `height: ${f.h}px; box-sizing: border-box; border: ${ring}px solid ${colour}; border-radius: ${ring + 5}px; `
      + 'pointer-events: none; z-index: 2147483647;';
    document.body.appendChild(d);
    const r = d.getBoundingClientRect();
    if (Math.abs(r.x - f.x) > 0.5 || Math.abs(r.y - f.y) > 0.5) wrong.push(`is at ${r.x},${r.y}, not ${f.x},${f.y}`);
  }
  return wrong;
}"""


def highlight(page, *regions, gap=GAP):
    """Frames each region in the accent colour. A region is a locator, or a list of locators that get one frame
    around all of them. At most two regions per image, and no frame line may cross text or a control (it raises).
    Call it when the layout is final (after fit() or settle()), right before write()."""
    if not 1 <= len(regions) <= 2:
        raise ValueError("one or two highlighted regions per image")
    frames = []
    for region in regions:
        boxes = [loc.bounding_box() for loc in (region if isinstance(region, (list, tuple)) else [region])]
        x0, y0 = min(b["x"] for b in boxes), min(b["y"] for b in boxes)
        x1, y1 = max(b["x"] + b["width"] for b in boxes), max(b["y"] + b["height"] for b in boxes)
        out = gap + RING
        frames.append({"x": round(x0 - out), "y": round(y0 - out),
                       "w": round(x1 - x0 + 2 * out), "h": round(y1 - y0 + 2 * out)})
    wrong = page.evaluate(FRAMES_JS, [frames, RING, ACCENT])
    if wrong:
        raise RuntimeError(f"highlight frame: {wrong}")


def settle(page):
    """No focus ring in the picture (it fades out with a CSS transition) and no field check still on its way (its
    answer can add a line and move everything below it)."""
    page.evaluate("document.activeElement && document.activeElement.blur()")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(600)


def fit(page):
    """The viewport as tall as the document, so sticky bars (header, form buttons) sit where a reader sees them."""
    page.set_viewport_size({"width": 1280, "height": 900})
    h = page.evaluate("document.documentElement.scrollHeight")
    page.set_viewport_size({"width": 1280, "height": min(max(900, h), 2400)})
    settle(page)


def write(page, name, height):
    """Viewport clip from the top, full width; then (if Pillow is installed) 256 colours, which a flat UI does not
    show."""
    path = IMAGES / f"{name}.png"
    page.screenshot(path=str(path), clip={"x": 0, "y": 0, "width": 1280, "height": int(height)})
    try:
        from PIL import Image
        Image.open(path).convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT,
                                                 dither=Image.Dither.NONE).save(path, optimize=True)
    except ImportError:
        pass
    print(f"docs/images/{name}.png: {path.stat().st_size // 1024} KB")


def save(page, name, bottom, *regions, gap=GAP, pad=24):
    """From the top of the page (header and breadcrumb) to the bottom edge of `bottom`, `regions` highlighted."""
    fit(page)
    highlight(page, *regions, gap=gap)
    loc = page.locator(bottom).last if isinstance(bottom, str) else bottom
    box = loc.bounding_box()
    write(page, name, box["y"] + box["height"] + pad)


def entry(scope, control):
    """The form entry (label, description and control) in `scope` that holds the element `control` selects."""
    return scope.locator(".jenkins-form-item", has=scope.page.locator(control))


def param(page, name):
    return page.locator('[name="parameter"]').filter(has=page.locator(f'input[name="name"][value="{name}"]'))


def tick(checkbox, on=True):
    """Sets a checkbox with a real click event (Jenkins draws its own box over the input)."""
    if checkbox.is_checked() != on:
        checkbox.evaluate("el => el.click()")


def decision_buttons(page, what):
    approve = page.get_by_role("button", name="Approve", exact=True)
    reject = page.get_by_role("button", name="Reject", exact=True)
    if approve.count() != 1 or reject.count() != 1:
        raise RuntimeError(f"approver-1 sees no Approve and Reject on {what}")
    return approve, reject


def shot_global_config():
    """Step 1, administrator: the two switches and the Approvers list."""
    s = lib.Session("admin")
    s.go("/manage/configure")
    p = s.page
    section = p.locator(".jenkins-section", has=p.locator(".jenkins-section__title", has_text="Batch Control")).first
    # The sections above scroll under the translucent header and would show through it, blurred: hide them.
    section.evaluate("""sec => { for (const el of document.querySelectorAll('#main-panel *')) {
        if (!el.contains(sec) && (el.compareDocumentPosition(sec) & Node.DOCUMENT_POSITION_FOLLOWING)) {
            el.style.visibility = 'hidden'; } } }""")
    header = p.locator("#page-header").bounding_box()["height"]
    box = section.bounding_box()
    p.set_viewport_size({"width": 1280, "height": int(header + box["height"] + 160)})
    p.evaluate(f"window.scrollTo(0, {box['y'] - header - 16})")
    settle(p)

    def switch(field):  # the checkbox with its caption and help button, not the whole (page-wide) entry
        return entry(section, f'[name="_.{field}"]').locator(".setting-main")
    highlight(p, [switch("runControlEnabled"), switch("changeControlEnabled")],
              entry(section, '[name="_.approversText"]'))
    # The picture ends below the last setting. What follows it in the section is not a setting: the "Batch Control
    # strategy" entry with the red "Revert to the plain strategy" button, which drew the eye away from the switches
    # (issue #85).
    last = section.locator(":scope > .jenkins-form-item", has=p.locator('[name^="_."]')).last.bounding_box()
    write(p, "global-config", last["y"] + last["height"] + 13)  # 13: half of the space between two entries
    s.done()


def shot_request_run():
    """Step 2, requester: the reason and the approver choice. Submits the form and returns the request's page."""
    s = lib.Session("requester")
    s.go(f"{SETTLEMENT}/batch-control/")
    p = s.page
    form = p.locator('form[name="batch-control-request"]')
    p.fill('textarea[name="reason"]', "Re-run for 2026-10-08 after upstream file arrived late (vendor ticket INC-5521).")
    tick(p.locator("#batch-control-approver-0"))
    param(p, "BUSINESS_DATE").locator('input[name="value"]').fill("2026-10-08")
    param(p, "SCOPE").locator('select[name="value"]').select_option("ALL")
    tick(param(p, "DRY_RUN").locator('input[name="value"]'), on=False)
    save(p, "request-run", 'button[name="Submit"]',
         [entry(form, 'textarea[name="reason"]'), entry(form, "#batch-control-approver-0")])
    with p.expect_navigation():
        p.locator('button[name="Submit"]').click()
    req = rel(p.url)
    if not re.fullmatch(r"/batch-control/requests/[0-9a-f-]{36}/", req):
        raise RuntimeError(f"the run request was not created: {req}\n{s.text()[:800]}")
    s.done()
    return req


def shot_approval(req):
    """Step 2, approver: Approve and Reject on the pending run request."""
    s = lib.Session("approver-1")
    s.go(req)
    save(s.page, "approval", "#main-panel", *decision_buttons(s.page, req))
    s.done()


def shot_history(req):
    """Step 2, anyone with ViewHistory: the row of the request of the two pictures before, now EXECUTED."""
    s = lib.Session("approver-1")
    p = s.page
    row = p.locator("#main-panel tbody tr", has=p.locator(f'a[href$="{req}"]'))

    def executed():
        s.go("/batch-control/history/?kind=requests")
        return "EXECUTED" in row.inner_text()
    if not lib.poll(executed, timeout=30, what=f"{req} is EXECUTED in History"):
        raise RuntimeError(f"History does not show {req} as EXECUTED")
    # gap=1: a table row has no room for the default; with it the line would run through the text of the rows above
    # and below, and highlight() refuses that.
    save(p, "history", p.get_by_text(re.compile(r"matching records")).first, row, gap=1)
    s.done()


def shot_permission_window():
    """Step 3, requester: the actions with the duration, and the reason. Submits the form and returns the
    window request's page."""
    s = lib.Session("requester")
    s.go(f"/batch-control/grants/new?scopeFullName={FOLDER}/nightly-load")
    p = s.page
    form = p.locator('form[name="createGrantRequest"]')
    form.locator(".ok").wait_for()  # the answer of the name check ("Freestyle project ...") adds a line
    tick(p.locator("#grant-action-configure"))
    p.select_option('select[name="durationMinutes"]', "60")
    p.fill('textarea[name="reason"]', "Add the new SFTP host as a fallback source for the vendor extract (CHG-2311).")
    tick(p.locator("#grant-approver-0"))
    tick(p.locator("#grant-approver-1"))
    save(p, "permission-window", 'button[name="Submit"]',
         [entry(form, "#grant-action-configure"), entry(form, 'select[name="durationMinutes"]')],
         entry(form, 'textarea[name="reason"]'))
    with p.expect_navigation():
        p.locator('button[name="Submit"]').click()
    grant = rel(p.url)
    if not re.fullmatch(r"/batch-control/grants/[0-9a-f-]{36}/", grant):
        raise RuntimeError(f"the permission window request was not created: {grant}\n{s.text()[:800]}")
    s.done()
    return grant


def shot_window_approval(grant):
    """Step 3, approver: Approve and Reject on the pending permission window request."""
    s = lib.Session("approver-1")
    s.go(grant)
    save(s.page, "permission-window-approval", "#main-panel", *decision_buttons(s.page, grant))
    s.done()


def main():
    IMAGES.mkdir(parents=True, exist_ok=True)
    seed()
    shot_global_config()
    req = shot_request_run()
    shot_approval(req)
    number = lib.api("admin", f"{SETTLEMENT}/api/json?tree=nextBuildNumber").json()["nextBuildNumber"]
    print(f"daily-settlement #{number}",
          approve_and_run(SETTLEMENT, number, req, "approver-1", "Vendor confirmed the late delivery, go ahead."))
    shot_history(req)
    shot_window_approval(shot_permission_window())
    lib.close()


if __name__ == "__main__":
    main()
