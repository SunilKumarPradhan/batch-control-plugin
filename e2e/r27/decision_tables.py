"""e2e-27 D3 (Wave D, issue #18 item 5, issues #6 and #18 item 1): on the run request page the Decision section comes
right after Parameters with ONE comment box and two buttons, Approve and Reject, on the unchanged endpoints; the run
tables (Run Dashboard, History > Runs, Incidents, History > Incidents) shrink to 7 columns with a Run cell holding the
status icon, the job link and the #n run link.

usage: python decision_tables.py [AOPJBXTLI]   rows: out/decision_tables.jsonl, shots: screenshots/run-27/R27-D3-*.png
Items (approval required): r27-d3-batch (DAY, MODE; succeeds), r27-d3-off (DAY; disabled in X), r27-d3-ten (P01..P10;
P02 is 300 characters, a's then b's then z's, P03 is markup), r27-d3-fail (fails: an incident), r27-d3-abort (sleeps;
aborted by admin). A run record of r27-d3-ghost#7 with the unknown result WEIRD is appended once through the store's own
method from the script console (arrangement: no job can produce an unknown result). The requester files the requests
over REST; approver-1 decides them in the browser; the server state is read from the store and Jenkins REST.

A  arrangement: the items; sweeps the requester's pending r27-d3 requests; one approved run each of r27-d3-batch,
   r27-d3-off, r27-d3-ten, r27-d3-fail (so the request pages have recent runs) and r27-d3-abort (stopped by admin while
   it runs); the ghost record once.
O  #18.5 (approver-1): with Approver Changes shown (the requester re-designated approver-1 and approver-2), the heading
   right after Parameters is Decision, before Recent Runs of This Job and Approver Changes; the Decision section has
   exactly one comment box and one Approve and one Reject button, posting to .../approve and .../reject. Guards: GET of
   both endpoints is refused, a POST without the crumb answers 403, the requester and approver-unlisted are refused (4xx),
   and the request stays PENDING.
P  #18.5 approve through the one box (browser): "e2e-27 D3 ship it" + Approve: the store says APPROVED/EXECUTED by
   approver-1 with that comment, the build runs (GET /job/r27-d3-batch/<n>/api/json 200) with the requested DAY and MODE.
J  #18.5 reject through the one box (browser): "e2e-27 D3 wrong day" + Reject: REJECTED by approver-1 with that comment;
   no build runs.
B  #18.5 a reject with only blanks in the box is refused: the store keeps PENDING, the page still shows the one box
   holding the blanks, an error naming the comment next to it, and both buttons; no bare error page.
X  #18.5 / D-55 with r27-d3-off disabled: Decision right after Parameters, the page says disabled, only Reject is
   offered; Reject through the one box works. Guard: a direct POST approve is refused and the request stays PENDING.
T  #6/#18.1 (administrator) the Run Dashboard and History > Runs (job=r27-d3-): exactly the columns Run, Cause, User,
   Parameters, Started, Duration, Request id, every row 7 cells; the Run cell of r27-d3-ten and r27-d3-fail holds a
   status icon whose tooltip names the result, the job link and the "#n" run link to the run's own URL, and the row does
   not print the result; the ghost's unknown result is text with no icon and no link; r27-d3-ten's Parameters cell shows
   P01..P03 with P04..P10 in one <details>, P02 cut (a's shown, no z's), P03's markup as text; r27-d3-abort's row still
   says "aborted by admin" with no Aborted by column; the Cause, User, Started and Duration cells of r27-d3-ten stay on
   one line at 1280 px. Guards: the full P02 in runs.csv, on the request page and on the build's parameters page.
L  #6 link rule: auditor (ViewHistory, no Item/Read) gets r27-d3-fail's row with "#n" and no link to the job or run on
   the four tables; approver-1 (Item/Read) gets the job link in the Run cell.
I  #6 (administrator) the Incidents list and History > Incidents: no Job or Result column; the Run cell of
   r27-d3-fail's incident holds the icon with a tooltip naming the failure, the job link and the #n run link.
cleanup: r27-d3-off enabled again; the requester's pending r27-d3 requests cancelled."""
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import lib  # noqa: E402
from lib import api, check, note, Session  # noqa: E402

lib.LOGNAME[0] = "decision_tables"
P = "r27-d3-"
BATCH, OFF, TEN, FAIL, ABORT, GHOST = (P + x for x in ("batch", "off", "ten", "fail", "abort", "ghost"))
COLUMNS = ["Run", "Cause", "User", "Parameters", "Started", "Duration", "Request id"]
LONG = "a" * 100 + "b" * 100 + "z" * 100
MARKUP = "<img src=x onerror=alert(1)>"
TEN_VALUES = {f"P{i:02d}": (LONG if i == 2 else MARKUP if i == 3 else f"v{i}") for i in range(1, 11)}
S = {}

# The Decision section, read without assuming one form or two: everything whose nearest preceding h2 reads "Decision".
DECISION_JS = """() => { const out = {headings: [], boxes: [], buttons: []}; let h = null;
  const w = document.createTreeWalker(document.querySelector('#main-panel'), NodeFilter.SHOW_ELEMENT);
  for (let n = w.currentNode; n; n = w.nextNode()) {
    if (n.tagName === 'H2') { h = n.textContent.trim(); out.headings.push(h); continue; }
    if (h !== 'Decision') continue;
    if ((n.tagName === 'TEXTAREA' || n.tagName === 'INPUT') && n.name === 'comment' && n.type !== 'hidden')
      out.boxes.push({tag: n.tagName.toLowerCase(), value: n.value, visible: !!n.getClientRects().length});
    if (n.tagName === 'BUTTON' || (n.tagName === 'INPUT' && n.type === 'submit')) {
      const t = (n.tagName === 'INPUT' ? n.value : n.textContent).trim();
      const action = n.getAttribute('formaction') || (n.form ? n.form.getAttribute('action') : null);
      out.buttons.push({text: t, target: action ? new URL(action, location.href).pathname : null,
                        visible: !!n.getClientRects().length}); } }
  return out; }"""
# Marks the Decision section's comment box and buttons so Playwright can type and click like a person.
MARK_JS = """() => { let h = null; let i = 0;
  const w = document.createTreeWalker(document.querySelector('#main-panel'), NodeFilter.SHOW_ELEMENT);
  for (let n = w.currentNode; n; n = w.nextNode()) {
    if (n.tagName === 'H2') { h = n.textContent.trim(); continue; }
    if (h !== 'Decision') continue;
    if ((n.tagName === 'TEXTAREA' || n.tagName === 'INPUT') && n.name === 'comment' && n.type !== 'hidden')
      n.setAttribute('data-r27-box', String(i++));
    if (n.tagName === 'BUTTON' || (n.tagName === 'INPUT' && n.type === 'submit'))
      n.setAttribute('data-r27-btn', (n.tagName === 'INPUT' ? n.value : n.textContent).trim().toLowerCase()); } }"""
ERROR_JS = """() => { const box = document.querySelector('[data-r27-box="0"]'); if (!box) return null;
  const near = [box.parentElement, box.parentElement && box.parentElement.parentElement].filter(Boolean);
  const errs = [...document.querySelectorAll('[data-batch-control-field-error="comment"], .error, [role=alert]')]
    .filter(e => /comment/i.test(e.textContent) && near.some(p => p.contains(e)));
  return errs.map(e => ({text: e.textContent.replace(/\\s+/g, ' ').trim().slice(0, 160), visible: !!e.getClientRects().length})); }"""


def run_once(job, params=None, after=None):
    n = lib.next_build(job)
    st, rid = lib.submit_run("requester", job, f"e2e-27 D3 {job}", params=params)
    dec = lib.decide("approver-1", "requests", rid, "approve", "e2e-27 D3") if rid else None
    if after:
        after(n)
    result = lib.wait_build(job, n, timeout=240)[0]
    return {"id": rid, "submit": st, "approve": dec, "number": n, "result": result}


def stop_when_running(job):
    def stop(n):
        lib.wait_until(lambda: (api("admin", f"{lib.jpath(job)}/{n}/api/json?tree=building").json() or {}).get("building")
                       if api("admin", f"{lib.jpath(job)}/{n}/api/json").status_code == 200 else False, 120, 1)
        S["stop"] = api("admin", f"{lib.jpath(job)}/{n}/stop", "POST").status_code
    return stop


def sec_A():
    plain = lib.job_xml("fs", shell="echo e2e-27 D3")
    two = lib.job_xml("fs", shell='echo "DAY=$DAY MODE=$MODE"',
                      params=lib.string_p("DAY", "2026-10-01") + lib.string_p("MODE", "full"))
    ten = lib.job_xml("fs", shell="echo e2e-27 D3 ten", params="".join(lib.string_p(k, "d") for k in TEN_VALUES))
    created = {n: lib.ensure_item(n, x) for n, x in ((BATCH, two), (OFF, two), (TEN, ten),
                                                     (FAIL, lib.job_xml("fs", shell="echo e2e-27 D3; exit 1")),
                                                     (ABORT, lib.job_xml("fs", shell="sleep 300")))}
    props = {n: lib.set_property(n, approval=True) for n in (BATCH, OFF, TEN, FAIL, ABORT)}
    S["enable"] = api("admin", lib.jpath(OFF) + "/enable", "POST").status_code
    S["swept"] = lib.sweep("requester", P)
    S["batch"] = run_once(BATCH, {"DAY": "2026-10-02", "MODE": "full"})
    S["off"] = run_once(OFF, {"DAY": "2026-10-02"})
    S["ten"] = run_once(TEN, TEN_VALUES)
    S["fail"] = run_once(FAIL)
    S["abort"] = run_once(ABORT, after=stop_when_running(ABORT))
    ghost = lib.gv(f"""def csv = new File(jenkins.model.Jenkins.get().rootDir, 'batch-control/runs')
def seen = csv.exists() && csv.listFiles().any {{ it.isFile() && it.getText('UTF-8').contains('{GHOST}#7') }}
if (seen) return 'present'
{lib.BC}.store.FileStore.get().appendRunRecord(new {lib.BC}.model.RunRecord('{GHOST}#7', '{GHOST}', 7,
  {lib.BC}.model.CauseType.OTHER, 'WEIRD', {lib.BC}.store.BatchClock.clock().instant(), 10L))
return 'appended'""")
    ok = (all(p.startswith("approvalRequired=true") for p in props.values())
          and [S[k]["result"] for k in ("batch", "off", "ten", "fail", "abort")] == ["SUCCESS", "SUCCESS", "SUCCESS",
                                                                                    "FAILURE", "ABORTED"]
          and ghost in ("present", "appended"))
    check("A", "arrangement: one approved run each of r27-d3-batch, -off, -ten (SUCCESS), -fail (FAILURE) and -abort "
          "(ABORTED by admin); the WEIRD run record of r27-d3-ghost#7", ok, created=created, swept=S["swept"],
          runs={k: S[k] for k in ("batch", "off", "ten", "fail", "abort")}, stop=S.get("stop"), ghost=ghost,
          enable=S["enable"])


def decision(s):
    return s.page.evaluate(DECISION_JS)


def one_box(sec, d, who):
    return check(sec, f"D3 #18.5 the Decision section has ONE comment box ({who})", len(d["boxes"]) == 1,
                 boxes=d["boxes"], headings=d["headings"])


def press(s, caption, comment):
    """Types `comment` into the Decision section's one comment box and presses the button captioned `caption`."""
    s.page.evaluate(MARK_JS)
    s.page.locator("[data-r27-box='0']").fill(comment)
    btn = s.page.locator(f"[data-r27-btn='{caption.lower()}']").first
    btn.scroll_into_view_if_needed()
    before = s.page.url
    btn.click()
    return lib.react(s.page, before, timeout=20000)


def sec_O():
    st, rid = lib.submit_run("requester", BATCH, "e2e-27 D3 order", params={"DAY": "2026-10-09", "MODE": "delta"})
    chg = api("requester", f"/batch-control/requests/{rid}/changeApprover", "POST",
              data=[("approvers", "approver-1"), ("approvers", "approver-2")]).status_code
    S["order"] = rid
    s = Session("approver-1")
    s.go(f"/batch-control/requests/{rid}/")
    d = decision(s)
    lib.page_shot(s, "R27-D3-O-01-request-page-approver-1")
    s.shot("#main-panel", "R27-D3-O-02-request-main-panel")
    s.done()
    h = d["headings"]
    idx = {k: (h.index(k) if k in h else -1) for k in ("Parameters", "Decision", "Recent Runs of This Job",
                                                        "Approver Changes")}
    check("O", "guard: the request page shows Parameters, Recent Runs of This Job and Approver Changes (the requester "
          "re-designated the approvers)", min(idx["Parameters"], idx["Recent Runs of This Job"],
                                              idx["Approver Changes"]) >= 0, headings=h, change=chg)
    check("O", "D3 #18.5 the heading right after Parameters is Decision, before Recent Runs of This Job and Approver "
          "Changes", idx["Decision"] == idx["Parameters"] + 1 and idx["Decision"] < idx["Recent Runs of This Job"]
          and idx["Decision"] < idx["Approver Changes"], headings=h)
    one_box("O", d, "approver-1")
    caps = [b["text"].lower() for b in d["buttons"]]
    base = f"{lib.PREFIX}/batch-control/requests/{rid}/"
    tgt = {b["text"].lower(): b["target"] for b in d["buttons"]}
    check("O", "D3 #18.5 the Decision section offers one Approve and one Reject button, posting to the existing "
          ".../approve and .../reject endpoints", caps.count("approve") == 1 and caps.count("reject") == 1
          and tgt.get("approve") == base + "approve" and tgt.get("reject") == base + "reject", buttons=d["buttons"])
    codes = {}
    for verb in ("approve", "reject"):
        codes[f"GET {verb}"] = api("approver-1", f"/batch-control/requests/{rid}/{verb}").status_code
        codes[f"POST {verb} no crumb"] = api("approver-1", f"/batch-control/requests/{rid}/{verb}", "POST", crumb=False,
                                             data={"comment": "no crumb"}).status_code
        for who in ("requester", "approver-unlisted"):
            codes[f"{who} {verb}"] = lib.decide(who, "requests", rid, verb, "not mine")
    state = lib.stored("run", rid).get("status")
    check("O", "guard: GET approve/reject refused, a POST without the crumb answers 403, the requester and "
          "approver-unlisted are refused (4xx); the request stays PENDING",
          all(v >= 400 for k, v in codes.items() if k.startswith("GET")) and all(
              v == 403 for k, v in codes.items() if "no crumb" in k) and all(
              400 <= v < 500 for k, v in codes.items() if k.split()[0] in ("requester", "approver-unlisted"))
          and state == "PENDING", codes=codes, state=state)


def sec_P():
    rid = S["order"]
    n = lib.next_build(BATCH)
    s = Session("approver-1")
    s.go(f"/batch-control/requests/{rid}/")
    d = decision(s)
    if one_box("P", d, "approver-1"):
        how = press(s, "Approve", "e2e-27 D3 ship it")
        s.page.wait_for_load_state("load")
        lib.page_shot(s, "R27-D3-P-01-after-approve")
        landed = s.page.url
    else:
        how = landed = None
    s.done()
    result, _ = lib.wait_build(BATCH, n, timeout=180) if how else (None, None)
    st = lib.stored("run", rid)
    b = api("admin", f"{lib.jpath(BATCH)}/{n}/api/json?tree=result,actions[parameters[name,value]]")
    params = {p["name"]: p["value"] for a in (b.json().get("actions", []) if b.status_code == 200 else [])
              for p in (a or {}).get("parameters", []) or []}
    check("P", "D3 #18.5 approve through the one box: the store says APPROVED/EXECUTED by approver-1 with the typed "
          "comment", st.get("status") in ("APPROVED", "EXECUTED") and st.get("decidedBy") == "approver-1"
          and st.get("decisionComment") == "e2e-27 D3 ship it", stored=st, reaction=how, landed=landed)
    check("P", "D3 #18.5 the approved run executed: GET /job/r27-d3-batch/<n>/api/json answers 200, SUCCESS, with the "
          "requested DAY and MODE", b.status_code == 200 and result == "SUCCESS"
          and params.get("DAY") == "2026-10-09" and params.get("MODE") == "delta", build=n, status=b.status_code,
          result=result, params=params)


def sec_J():
    st, rid = lib.submit_run("requester", BATCH, "e2e-27 D3 reject", params={"DAY": "2026-10-09", "MODE": "delta"})
    n = lib.next_build(BATCH)
    s = Session("approver-1")
    s.go(f"/batch-control/requests/{rid}/")
    d = decision(s)
    how = None
    if one_box("J", d, "approver-1"):
        how = press(s, "Reject", "e2e-27 D3 wrong day")
        s.page.wait_for_load_state("load")
        lib.page_shot(s, "R27-D3-J-01-after-reject")
    s.done()
    stored = lib.stored("run", rid)
    lib.wait_until(lambda: not lib.L25.queue_items(BATCH), 10, 1)
    check("J", "D3 #18.5 reject through the one box: REJECTED by approver-1 with the typed comment, and no build runs",
          stored.get("status") == "REJECTED" and stored.get("decidedBy") == "approver-1"
          and stored.get("decisionComment") == "e2e-27 D3 wrong day" and lib.next_build(BATCH) == n,
          stored=stored, reaction=how, next_build=lib.next_build(BATCH), expected_next=n)


def sec_B():
    st, rid = lib.submit_run("requester", BATCH, "e2e-27 D3 blank reject", params={"DAY": "2026-10-09", "MODE": "x"})
    s = Session("approver-1")
    s.go(f"/batch-control/requests/{rid}/")
    d = decision(s)
    after, errors, status, how = None, None, None, None
    if one_box("B", d, "approver-1"):
        how = press(s, "Reject", "   ")
        s.page.wait_for_load_state("load")
        s.page.evaluate(MARK_JS)
        after = decision(s)
        errors = s.page.evaluate(ERROR_JS)
        status = s.page.locator("#main-panel").count() and s.page.locator(".jenkins-breadcrumbs__list-item").count()
        lib.page_shot(s, "R27-D3-B-01-blank-reject-refused")
        s.shot("[data-r27-box='0']", "R27-D3-B-02-blank-reject-box", pad=120)
    s.done()
    stored = lib.stored("run", rid)
    check("B", "D3 #18.5 a reject with only blanks is refused: the store keeps PENDING", stored.get("status") == "PENDING"
          and how is not None, stored=stored, reaction=how)
    caps = [b["text"].lower() for b in (after or {}).get("buttons", [])]
    check("B", "D3 #18.5 after the refused reject the page (not a bare error page) still shows the one box holding the "
          "blanks, and both Approve and Reject", bool(status) and after is not None and len(after["boxes"]) == 1
          and after["boxes"][0]["value"] == "   " and "approve" in caps and "reject" in caps,
          after=after, page_chrome=status)
    check("B", "D3 #18.5 the error naming the comment is shown next to the box", bool(errors)
          and any(e["visible"] for e in errors), errors=errors)


def sec_X():
    api("admin", lib.jpath(OFF) + "/enable", "POST")
    st, rid = lib.submit_run("requester", OFF, "e2e-27 D3 disabled job", params={"DAY": "2026-10-09"})
    dis = api("admin", lib.jpath(OFF) + "/disable", "POST").status_code
    direct = lib.decide("approver-1", "requests", rid, "approve", "e2e-27 D3 direct")
    state = lib.stored("run", rid).get("status")
    check("X", "guard: approving while the job is disabled is refused (4xx) and the request stays PENDING (D-55)",
          direct is not None and 400 <= direct < 500 and state == "PENDING", direct=direct, state=state, disable=dis)
    s = Session("approver-1")
    s.go(f"/batch-control/requests/{rid}/")
    d = decision(s)
    text = s.text()
    lib.page_shot(s, "R27-D3-X-01-disabled-job-decision")
    h = d["headings"]
    caps = [b["text"].lower() for b in d["buttons"]]
    check("X", "D3 #18.5 with the job disabled the Decision section comes right after Parameters",
          "Decision" in h and "Parameters" in h and h.index("Decision") == h.index("Parameters") + 1, headings=h)
    check("X", "D3 #18.5 / D-55 with the job disabled the page says so and offers only Reject next to the one box",
          "disabled" in text.lower() and "approve" not in caps and caps.count("reject") == 1 and len(d["boxes"]) == 1,
          buttons=d["buttons"], boxes=d["boxes"])
    how = None
    if len(d["boxes"]) == 1 and "reject" in caps:
        how = press(s, "Reject", "e2e-27 D3 job is retired")
        s.page.wait_for_load_state("load")
        lib.page_shot(s, "R27-D3-X-02-disabled-job-rejected")
    s.done()
    stored = lib.stored("run", rid)
    check("X", "D3 #18.5 Reject through the one box works while the job is disabled: REJECTED with the typed comment",
          stored.get("status") == "REJECTED" and stored.get("decisionComment") == "e2e-27 D3 job is retired",
          stored=stored, reaction=how)
    api("admin", lib.jpath(OFF) + "/enable", "POST")


TABLE_JS = """(arg) => { const [jobPath, number] = arg;
  const row = [...document.querySelectorAll('#main-panel table tbody tr')].find(tr =>
    [...tr.querySelectorAll('a[href]')].some(a => new URL(a.href).pathname === jobPath + number + '/'));
  if (!row) return null; const table = row.closest('table');
  const cells = [...row.children].filter(c => c.tagName === 'TD' || c.tagName === 'TH');
  const headers = [...table.querySelectorAll('thead th')].map(th => th.textContent.replace(/\\s+/g, ' ').trim());
  const run = cells[headers.indexOf('Run')] || null;
  const tips = run ? [...run.querySelectorAll('*')].flatMap(e => ['tooltip', 'title', 'data-tooltip', 'aria-label']
    .map(a => (e.getAttribute(a) || '').toLowerCase())).filter(Boolean) : [];
  const links = run ? [...run.querySelectorAll('a[href]')].map(a => ({path: new URL(a.href).pathname, text: a.textContent.trim()})) : [];
  return {headers, cellCount: cells.length, rowText: row.innerText.replace(/\\s+/g, ' '),
    rowCells: [...table.querySelectorAll('tbody > tr')].map(tr => [...tr.children].filter(c => c.tagName === 'TD' || c.tagName === 'TH').length),
    icon: run ? run.querySelectorAll('svg, img').length : 0, tips, links}; }"""
PARAMS_JS = """(arg) => { const [jobPath, number] = arg;
  const row = [...document.querySelectorAll('#main-panel table tbody tr')].find(tr =>
    [...tr.querySelectorAll('a[href]')].some(a => new URL(a.href).pathname === jobPath + number + '/'));
  if (!row) return null; const table = row.closest('table');
  const headers = [...table.querySelectorAll('thead th')].map(th => th.textContent.replace(/\\s+/g, ' ').trim());
  const cells = [...row.children].filter(c => c.tagName === 'TD' || c.tagName === 'TH');
  const cell = cells[headers.indexOf('Parameters')]; if (!cell) return {headers};
  const outside = n => [...n.childNodes].map(c => c.nodeType === 3 ? c.data : (c.tagName === 'DETAILS' ? '' : outside(c))).join(' ');
  const lines = col => { const c = cells[headers.indexOf(col)]; if (!c) return null;
    const tops = []; const w = document.createTreeWalker(c, NodeFilter.SHOW_TEXT);
    for (let t = w.nextNode(); t; t = w.nextNode()) { if (!t.data.trim()) continue; const r = document.createRange();
      r.selectNodeContents(t); for (const b of r.getClientRects()) tops.push(b.top); }
    const lh = parseFloat(getComputedStyle(c).lineHeight) || 16;
    return {text: c.textContent.replace(/\\s+/g, ' ').trim(), spread: tops.length ? Math.max(...tops) - Math.min(...tops) : null,
            lineHeight: lh, whiteSpace: getComputedStyle(c).whiteSpace}; };
  return {headers, details: cell.querySelectorAll('details').length, outside: outside(cell),
    inside: [...cell.querySelectorAll('details')].map(d => d.textContent).join(' '), text: cell.textContent,
    imgs: cell.querySelectorAll('img').length, requestCell: (cells[headers.indexOf('Request id')] || {}).textContent || null,
    wrap: Object.fromEntries(['Cause', 'User', 'Started', 'Duration'].map(c => [c, lines(c)]))}; }"""


def run_row(s, job, number):
    return s.page.evaluate(TABLE_JS, [f"{lib.PREFIX}{lib.jpath(job)}/", str(number)])


def run_cell_ok(sec, where, row, job, number, tip, result):
    jp = f"{lib.PREFIX}{lib.jpath(job)}/"
    ok_cols = bool(row) and row["headers"] == COLUMNS
    check(sec, f"D3 #6/#18.1 {where}: the run table has exactly the columns {COLUMNS} and every row 7 cells",
          ok_cols and set(row["rowCells"]) == {7}, headers=(row or {}).get("headers"),
          cells=sorted(set((row or {}).get("rowCells") or [])))
    links = (row or {}).get("links") or []
    check(sec, f"D3 #6 {where}: the Run cell of {job}#{number} holds a status icon whose tooltip names the result "
          f"('{tip}'), the job link and the '#{number}' link to the run's own URL",
          bool(row) and row["icon"] > 0 and any(tip in t for t in row["tips"]) and any(l["path"] == jp for l in links)
          and any(l["path"] == f"{jp}{number}/" and l["text"] == f"#{number}" for l in links),
          icon=(row or {}).get("icon"), tips=(row or {}).get("tips", [])[:6], links=links, found=bool(row))
    if result:
        check(sec, f"D3 #6 {where}: {job}#{number}'s row shows the result as the icon, not the text {result}",
              bool(row) and result not in row["rowText"], row=(row or {}).get("rowText", "")[:200])


def sec_T():
    for path, tag in (("/batch-control/dashboard/", "dashboard"), (f"/batch-control/history/?kind=runs&job={P}", "history")):
        s = Session("admin")
        s.go(path)
        lib.page_shot(s, f"R27-D3-T-{tag}-01-page")
        ten = run_row(s, TEN, S["ten"]["number"])
        run_cell_ok("T", tag, ten, TEN, S["ten"]["number"], "success", "SUCCESS")
        fail = run_row(s, FAIL, S["fail"]["number"])
        run_cell_ok("T", tag, fail, FAIL, S["fail"]["number"], "fail", "FAILURE")
        ghost = s.page.evaluate("""(g) => { const tr = [...document.querySelectorAll('#main-panel table tbody tr')]
            .find(r => r.textContent.includes(g)); if (!tr) return null;
          const cells = [...tr.children].filter(c => c.tagName === 'TD' || c.tagName === 'TH');
          return {cells: cells.length, run: cells[0].textContent.replace(/\\s+/g, ' ').trim(),
                  icon: cells[0].querySelectorAll('svg, img').length,
                  ghostLinks: [...tr.querySelectorAll('a[href]')].filter(a => a.getAttribute('href').includes(g)).length}; }""",
                                GHOST)
        check("T", f"D3 #6 {tag}: the unknown result WEIRD of r27-d3-ghost#7 is text in its Run cell, with no icon and no "
              "link to the missing job, in a 7-cell row", bool(ghost) and ghost["cells"] == 7 and "WEIRD" in ghost["run"]
              and ghost["icon"] == 0 and ghost["ghostLinks"] == 0, ghost=ghost)
        pr = s.page.evaluate(PARAMS_JS, [f"{lib.PREFIX}{lib.jpath(TEN)}/", str(S["ten"]["number"])]) or {}
        outside, inside = pr.get("outside") or "", pr.get("inside") or ""
        check("T", f"D3 #6/#18.1 {tag}: r27-d3-ten's Parameters cell shows P01..P03 and puts P04..P10 in one <details>",
              pr.get("details") == 1 and all(f"P0{i}" in outside for i in (1, 2, 3))
              and not any(k in outside for k in [f"P{i:02d}" for i in range(4, 11)])
              and all(f"P{i:02d}" in inside for i in range(4, 11)), details=pr.get("details"), outside=outside[:300])
        text = pr.get("text") or ""
        check("T", f"D3 #18.1 {tag}: the 300-character P02 is cut on screen (all a's shown, no z's)",
              "a" * 100 in text and "zzz" not in text, sample=text[:400])
        check("T", f"D3 #6 escaping {tag}: P03's markup is text, not an element", pr.get("imgs") == 0 and "<img" in text,
              imgs=pr.get("imgs"))
        check("T", f"D3 #6 {tag}: the Request id cell names r27-d3-ten's request",
              S["ten"]["id"][:8] in (pr.get("requestCell") or ""), cell=pr.get("requestCell"))
        wrap = pr.get("wrap") or {}
        check("T", f"D3 #6/#18.1 {tag}: the Cause, User, Started and Duration cells of r27-d3-ten stay on one line at "
              "1280 px", wrap and all(v and v["spread"] is not None and v["spread"] < 0.5 * v["lineHeight"]
                                      for v in wrap.values()), wrap=wrap)
        ab = run_row(s, ABORT, S["abort"]["number"])
        check("T", f"D3 #6 {tag}: with no Aborted by column, r27-d3-abort's row still says it was aborted by admin",
              bool(ab) and "Aborted by" not in ab["headers"] and re.search(r"aborted by\W+admin\b", ab["rowText"], re.I),
              headers=(ab or {}).get("headers"), row=(ab or {}).get("rowText", "")[:240])
        det = s.page.locator(f"#main-panel tr:has(a[href$='{lib.jpath(TEN)}/{S['ten']['number']}/']) details summary")
        if det.count():
            det.first.click()
        s.shot(f"#main-panel tr:has(a[href$='{lib.jpath(TEN)}/{S['ten']['number']}/'])", f"R27-D3-T-{tag}-02-ten-row")
        s.shot("#main-panel table", f"R27-D3-T-{tag}-03-table")
        width = s.page.evaluate("() => { const t = document.querySelector('#main-panel table'); "
                                "return t ? [t.scrollWidth, t.parentElement.clientWidth, innerWidth] : null; }")
        note("T", f"{tag}: table scroll width vs container and viewport", widths=width)
        s.done()
    csv = api("admin", f"/batch-control/history/runs.csv?job={TEN}")
    req = api("admin", f"/batch-control/requests/{S['ten']['id']}/")
    build = api("admin", f"{lib.jpath(TEN)}/{S['ten']['number']}/parameters/")
    check("T", "guard: the full 300-character P02 stays whole in runs.csv, on the request page and on the build's "
          "parameters page", LONG in csv.content.decode("utf-8-sig", "replace") and LONG in req.text and LONG in build.text,
          csv=csv.status_code, request=req.status_code, build=build.status_code)


def sec_L():
    pages = [("/batch-control/dashboard/", "dashboard"), (f"/batch-control/history/?kind=runs&job={P}", "history-runs"),
             ("/batch-control/incidents/", "incidents"), (f"/batch-control/history/?kind=incidents&job={P}",
                                                          "history-incidents")]
    n = S["fail"]["number"]
    for path, tag in pages:
        s = Session("auditor")
        r = s.go(path)
        row = s.page.evaluate("""(arg) => { const [job, n] = arg; const tr = [...document.querySelectorAll('#main-panel table tbody tr')]
            .find(r => r.textContent.includes(job) && r.textContent.includes('#' + n)); if (!tr) return null;
          return {text: tr.innerText.replace(/\\s+/g, ' '), hrefs: [...tr.querySelectorAll('a[href]')].map(a => a.getAttribute('href'))}; }""",
                              [FAIL, str(n)])
        s.shot("#main-panel table", f"R27-D3-L-auditor-{tag}")
        s.done()
        check("L", f"D3 #6 link rule {tag}: auditor (no Item/Read) sees r27-d3-fail's row with '#{n}' and no link to the "
              "job or the run", r is not None and r.status == 200 and bool(row)
              and not any(f"job/{FAIL}" in h for h in row["hrefs"]), row=row, status=r.status if r else None)
        s = Session("approver-1")
        s.go(path)
        rr = run_row(s, FAIL, n)
        s.done()
        jp = f"{lib.PREFIX}{lib.jpath(FAIL)}/"
        check("L", f"D3 #6 link rule {tag}: approver-1 (Item/Read) gets the job link and the '#{n}' run link in the Run "
              "cell", bool(rr) and any(l["path"] == jp for l in rr["links"])
              and any(l["path"] == f"{jp}{n}/" for l in rr["links"]), links=(rr or {}).get("links"))


def sec_I():
    n = S["fail"]["number"]
    for path, tag in (("/batch-control/incidents/", "incidents"),
                      (f"/batch-control/history/?kind=incidents&job={P}", "history-incidents")):
        s = Session("admin")
        s.go(path)
        row = run_row(s, FAIL, n)
        lib.page_shot(s, f"R27-D3-I-{tag}-01-page")
        s.shot("#main-panel table", f"R27-D3-I-{tag}-02-table")
        s.done()
        h = (row or {}).get("headers") or []
        check("I", f"D3 #6 {tag}: no separate Job or Result column, a Run column", bool(row) and "Job" not in h
              and "Result" not in h and "Run" in h, headers=h)
        jp = f"{lib.PREFIX}{lib.jpath(FAIL)}/"
        links = (row or {}).get("links") or []
        check("I", f"D3 #6 {tag}: the Run cell of r27-d3-fail#{n} holds the icon with a tooltip naming the failure, the "
              f"job link and the '#{n}' run link", bool(row) and row["icon"] > 0 and any("fail" in t for t in row["tips"])
              and any(l["path"] == jp for l in links)
              and any(l["path"] == f"{jp}{n}/" and l["text"] == f"#{n}" for l in links),
              icon=(row or {}).get("icon"), tips=(row or {}).get("tips", [])[:6], links=links)


def cleanup():
    note("cleanup", "restore", enable=api("admin", lib.jpath(OFF) + "/enable", "POST").status_code,
         swept=lib.sweep("requester", P))


lib.run(sys.argv, {"A": sec_A, "O": sec_O, "P": sec_P, "J": sec_J, "B": sec_B, "X": sec_X, "T": sec_T, "L": sec_L,
                   "I": sec_I}, cleanup)
