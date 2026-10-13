"""e2e-27 D1 (Wave D, issue #18 items 4 and 7): request pages are titled by their subject and carry an ID row with
core's copy button; the "Revert to the plain strategy" entry sits at the end of the Batch Control section inside core's
Advanced control.

usage: python titles_revert.py [ATGVER]   rows: out/titles_revert.jsonl, shots: screenshots/run-27/R27-D1-*.png
Items: folder r27-d1 with r27-d1/batch (approval required), r27-d1/act (approval required, not activated) and
r27-d1/q"x'y{z} (approval required; core accepts the quotes and braces, so the name reaches text and attributes). The
requester files the requests over REST (the plugin's own endpoints); the pages are read in the browser, one new context
per account and page.

A  arrangement: the items; sweeps the requester's pending r27-d1 requests of an earlier pass; files a run request on
   r27-d1/batch and on the odd name, a grant (permission window) request on both, an ACTIVATE request on r27-d1/act.
T  #18.4 run request page (requester, then approver-1): <title>, app bar heading and last breadcrumb read
   "Run request: r27-d1/batch" and none of them is the id; an "ID" row shows the full id with core's copy button
   (button.jenkins-copy-button, text=<id>); pressing it puts the id on the clipboard. Guards: the page answers 200 and
   still links the job; nobc (no Batch Control permission) gets no page naming the request.
G  #18.4 grant request page (approver-1): "Grant request: r27-d1/batch" and the ID row.
V  #18.4 activation request page (approver-1): "Activation request: r27-d1/act" and the ID row.
E  #18.4 escaping (approver-1): the run and grant request pages of r27-d1/q"x'y{z} read the name exactly in the title,
   heading and breadcrumb (and the breadcrumb's tooltip attribute), so it was escaped in text and attributes.
R  #18.7 (administrator) on Manage Jenkins > System and on the Batch Control configuration page: the red revert entry is
   not visible until the Batch Control section's Advanced button is pressed, then visible; no Batch Control field follows
   it in the section. Guards: it keeps the destructive colour; pressing it opens core's confirmation (Cancel changes
   nothing, OK installs the plain strategy: the unchanged endpoint works from its new place; the driver then restores
   the Batch Control strategy through the monitor's migrate endpoint); the BatchControl/Manage holder (manager) is
   offered no revert, not even hidden, and the endpoint answers 403 to them.
cleanup: the Batch Control strategy restored if a section left the plain one; the requester's pending r27-d1 requests
cancelled."""
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import lib  # noqa: E402
from lib import api, check, note, Session, norm  # noqa: E402

lib.LOGNAME[0] = "titles_revert"
FOLDER = "r27-d1"
BATCH, ACT, ODD = f"{FOLDER}/batch", f"{FOLDER}/act", FOLDER + "/q\"x'y{z}"
S = {}
REVERT = f"administrativeMonitor/{lib.STRATEGY_MONITOR}/revert"
REVERT_SEL = f"[data-url$='{REVERT}'], [formaction$='{REVERT}'], [href$='{REVERT}'], form[action$='{REVERT}'] button"
ID_ROW_JS = """() => { const th = [...document.querySelectorAll('#main-panel table tr > th')].find(t => t.textContent.trim() === 'ID');
  if (!th) return null; const td = th.parentElement.querySelector('td'); if (!td) return {cell: null};
  return {cell: td.textContent.replace(/\\s+/g, ' ').trim(),
          buttons: [...td.querySelectorAll('button')].map(b => ({cls: b.className, text: b.getAttribute('text')}))}; }"""


def sec_A():
    lib.ensure_folder(FOLDER)
    xml = lib.job_xml("fs", shell="echo e2e-27 D1")
    created = {n: lib.ensure_item(n, xml) for n in (BATCH, ACT, ODD)}
    props = {n: lib.set_property(n, approval=True) for n in (BATCH, ACT, ODD)}
    swept = lib.sweep("requester", FOLDER + "/")
    S["run"] = lib.submit_run("requester", BATCH, "e2e-27 D1 titles")
    S["run_odd"] = lib.submit_run("requester", ODD, "e2e-27 D1 odd name")
    S["grant"] = lib.submit_grant("requester", BATCH, ["CONFIGURE"], reason="e2e-27 D1 window")
    S["grant_odd"] = lib.submit_grant("requester", ODD, ["CONFIGURE"], reason="e2e-27 D1 odd window")
    S["act_state"] = lib.activation(ACT)
    S["act"] = lib.submit_activation("requester", ACT, "ACTIVATE" if S["act_state"] != "activated" else "HOLD",
                                     "e2e-27 D1 activation")
    ids = {k: S[k][1] for k in ("run", "run_odd", "grant", "grant_odd", "act")}
    check("A", "arrangement: r27-d1/batch, r27-d1/act and r27-d1/q\"x'y{z} need approval; one run, grant and activation "
          "request filed (REST, requester)", all(ids.values()) and all("approvalRequired=true" in p for p in props.values()),
          created=created, swept=swept, ids=ids, codes={k: S[k][0] for k in ids}, activation=S["act_state"])


def id_row(sec, who, page, rid, what):
    """#18.4: the summary table's ID row shows the full id with core's copy button copying it."""
    row = page.evaluate(ID_ROW_JS)
    btn = [b for b in (row or {}).get("buttons", []) if "jenkins-copy-button" in (b.get("cls") or "")]
    check(sec, f"D1 #18.4 ID row: {who}'s {what} page has a summary row headed 'ID' showing the full id with core's copy "
          "button (button.jenkins-copy-button, text=<id>)", bool(row and rid in (row.get("cell") or "")
                                                                   and any(b.get("text") == rid for b in btn)),
          id=rid, row=row)
    return bool(btn)


def titled(sec, who, path, expected, rid, what, shot, copy=False):
    s = Session(who)
    r = s.go(path)
    t = lib.titles(s.page)
    tips = s.page.locator(".jenkins-breadcrumbs__list-item").last.locator("[tooltip]")
    tip = [tips.nth(i).get_attribute("tooltip") for i in range(tips.count())]
    lib.page_shot(s, f"{shot}-page")
    s.shot("#main-panel table", f"{shot}-summary")
    check(sec, f"guard: {who} opens the {what} page (200)", r is not None and r.status == 200,
          status=r.status if r else None)
    check(sec, f"D1 #18.4 title: the {what} page's <title>, app bar heading and last breadcrumb read '{expected}' "
          f"({who})", list(t) == [expected] * 3, expected=expected, shown=t)
    check(sec, f"D1 #18.4 title: the id is in none of the {what} page's title, heading and breadcrumb ({who})",
          all(x and rid not in x for x in t), id=rid, shown=t)
    if tip:
        check(sec, f"D1 #18.4 escaping: the last breadcrumb's tooltip carries '{expected}' unchanged ({who})",
              all(x == expected for x in tip), tooltip=tip)
    check(sec, f"D1 #18.4 the full id is still on the {what} page ({who})", rid in s.text(), id=rid)
    has_btn = id_row(sec, who, s.page, rid, what)
    if copy and has_btn:
        s.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=lib.ORIGIN)
        b = s.page.locator("#main-panel table tr:has(> th:text-is('ID')) button.jenkins-copy-button").first
        b.click()
        s.page.wait_for_timeout(300)  # core's copy button writes the clipboard asynchronously, then shows "Copied"
        s.shot("#main-panel table tr:has(> th:text-is('ID'))", f"{shot}-copied")
        try:
            clip = s.page.evaluate("navigator.clipboard.readText()")
        except Exception as e:  # noqa: a browser without clipboard access
            clip = f"unreadable: {e!r}"[:200]
        check(sec, f"D1 #18.4 ID row: pressing the copy button puts the full id on the clipboard ({who})", clip == rid,
              clipboard=clip, id=rid)
    s.done()


def sec_T():
    rid = S["run"][1]
    path = f"/batch-control/requests/{rid}/"
    for i, who in enumerate(("requester", "approver-1"), 1):
        titled("T", who, path, f"Run request: {BATCH}", rid, "run request", f"R27-D1-T-0{i}-run-request-{who}",
               copy=(who == "requester"))
    s = Session("requester")
    s.go(path)
    job_link = s.page.locator(f"#main-panel table a[href$='{lib.jpath(BATCH)}/']").count()
    s.done()
    check("T", "guard: the run request page still links its job in the summary table", job_link >= 1, links=job_link)
    r = api("nobc", path)
    check("T", "guard: nobc (no Batch Control permission) gets no page naming the run request (4xx, no subject)",
          r.status_code >= 400 and f"Run request: {BATCH}" not in r.text and rid not in lib.text_of(r.text),
          status=r.status_code)


def sec_G():
    rid = S["grant"][1]
    titled("G", "approver-1", f"/batch-control/grants/{rid}/", f"Grant request: {BATCH}", rid, "grant request",
           "R27-D1-G-01-grant-request-approver-1")


def sec_V():
    rid = S["act"][1]
    # The job is never activated by this driver, so the request is an ACTIVATE one; a HOLD request (an earlier pass
    # left the job activated) may also read "Hold request: <job>" (T-UI-232).
    want = f"Activation request: {ACT}"
    if S["act_state"] == "activated":
        s = Session("approver-1")
        s.go(f"/batch-control/activations/{rid}/")
        shown = lib.titles(s.page)[0]
        s.done()
        want = shown if shown == f"Hold request: {ACT}" else want
    titled("V", "approver-1", f"/batch-control/activations/{rid}/", want, rid, "activation request",
           "R27-D1-V-01-activation-request-approver-1")


def sec_E():
    titled("E", "approver-1", f"/batch-control/requests/{S['run_odd'][1]}/", f"Run request: {ODD}", S["run_odd"][1],
           "run request (odd name)", "R27-D1-E-01-run-request-odd-name")
    titled("E", "approver-1", f"/batch-control/grants/{S['grant_odd'][1]}/", f"Grant request: {ODD}", S["grant_odd"][1],
           "grant request (odd name)", "R27-D1-E-02-grant-request-odd-name")


STATE_JS = """(sel) => { const fieldSel = 'input[name^="_."], select[name^="_."], textarea[name^="_."]';
  const sec = document.querySelector('[name="_.runControlEnabled"]')?.closest('section') || null;
  const ctl = [...document.querySelectorAll(sel)];
  const vis = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
  const chain = e => { const out = []; for (let p = e.parentElement; p && out.length < 7; p = p.parentElement)
    out.push(p.tagName.toLowerCase() + (p.className && typeof p.className === 'string' ? '.' + p.className.trim().split(/\\s+/).join('.') : ''));
    return out.join(' < '); };
  return {section: !!sec, controls: ctl.map(e => ({visible: vis(e), inSection: !!(sec && sec.contains(e)), chain: chain(e),
      destructive: e.className.includes('jenkins-!-destructive-color'), text: e.textContent.trim(),
      fieldsAfter: sec ? [...sec.querySelectorAll(fieldSel)].filter(f => e.compareDocumentPosition(f) & Node.DOCUMENT_POSITION_FOLLOWING
        && !(e.compareDocumentPosition(f) & Node.DOCUMENT_POSITION_CONTAINED_BY)).map(f => f.name) : null})),
    advanced: sec ? [...sec.querySelectorAll('button.advanced-button, button.advancedButton')].map((b, i) => {
      b.setAttribute('data-r27-adv', String(i)); return vis(b); }) : []}; }"""


def revert_place(path, tag, n):
    """#18.7 on one page: hidden until the section's Advanced is pressed, then visible; nothing after it. Returns the
    Session with the revert visible (or None when the page offers no revert)."""
    s = Session("admin")
    s.go(path)
    before = s.page.evaluate(STATE_JS, REVERT_SEL)
    s.shot("section:has([name='_.runControlEnabled'])", f"R27-D1-R-{n}1-{tag}-section-before-advanced")
    if not before["section"]:
        check("R", f"guard: {path} shows the Batch Control section", False, state=before)
        s.done()
        return None
    visible_before = [c for c in before["controls"] if c["visible"]]
    check("R", f"D1 #18.7 {path}: the revert entry is not visible before Advanced is pressed (it is inside core's "
          "Advanced control, not among the routine settings)", before["controls"] and not visible_before,
          controls=before["controls"], advanced_buttons=before["advanced"])
    pressed = []
    for i, vis in enumerate(before["advanced"]):
        now = s.page.evaluate(STATE_JS, REVERT_SEL)
        if any(c["visible"] for c in now["controls"]):
            break
        b = s.page.locator(f"[data-r27-adv='{i}']")
        if vis and b.count() and b.is_visible():
            b.scroll_into_view_if_needed()
            b.click()
            s.page.wait_for_timeout(200)  # core's advanced.js reveals the body synchronously; let layout settle
            pressed.append(i)
    after = s.page.evaluate(STATE_JS, REVERT_SEL)
    shown = [c for c in after["controls"] if c["visible"] and c["inSection"]]
    s.shot("section:has([name='_.runControlEnabled'])", f"R27-D1-R-{n}2-{tag}-section-after-advanced")
    check("R", f"D1 #18.7 {path}: pressing the Batch Control section's Advanced button shows the revert entry",
          bool(pressed) and len(shown) == 1, pressed=pressed, controls=after["controls"])
    ctl = shown[0] if shown else (after["controls"][0] if after["controls"] else {})
    check("R", f"D1 #18.7 {path}: the revert entry is the last entry of the Batch Control section (no Batch Control "
          "field follows it)", ctl.get("fieldsAfter") == [], fields_after=ctl.get("fieldsAfter"), chain=ctl.get("chain"))
    check("R", f"guard: {path}: the revert entry keeps the destructive colour", bool(ctl.get("destructive")),
          text=ctl.get("text"))
    return s


def sec_R():
    s = revert_place("/manage/configure", "system", 1)
    if s is not None:
        before = lib.strategy()
        ctl = s.page.locator(REVERT_SEL).filter(visible=True).first
        ctl.click()
        ok = lib.opened(s.page)
        s.shot("dialog[open]", "R27-D1-R-13-system-revert-confirmation")
        dlg_text = norm(s.page.locator("dialog[open]").first.inner_text()) if ok else None
        if ok:
            s.page.locator("dialog[open] button[data-id=cancel]").click()
            lib.gone(s.page)
        after_cancel = lib.strategy()
        ctl.click()
        ok2 = lib.opened(s.page)
        nav = None
        if ok2:
            before_url = s.page.url
            s.page.locator("dialog[open] button[data-id=ok]").click()
            nav = lib.react(s.page, before_url, timeout=15000)
        after_ok = lib.strategy()
        lib.page_shot(s, "R27-D1-R-14-system-after-revert")
        s.done()
        check("R", "guard: the revert entry, pressed from its place, opens core's confirmation; Cancel keeps the Batch "
              "Control strategy, OK installs the plain strategy (the unchanged endpoint)",
              ok and before.startswith("BatchControl") and after_cancel == before and ok2
              and after_ok == "ProjectMatrixAuthorizationStrategy", dialog=dlg_text, before=before,
              after_cancel=after_cancel, after_ok=after_ok, reaction=nav)
        restored = lib.restore_strategy()
        check("R", "arrangement: the Batch Control strategy restored through the monitor's migrate endpoint",
              restored[1].startswith("BatchControl"), restored=restored)
    s = revert_place("/manage/batch-control-configuration/", "bc-config", 2)
    if s is not None:
        s.done()
    m = Session("manager")
    r = m.go("/manage/batch-control-configuration/")
    html = m.page.content()
    lib.page_shot(m, "R27-D1-R-31-manager-bc-config")
    m.done()
    post = api("manager", "/manage/" + REVERT, "POST")
    check("R", "guard: the BatchControl/Manage holder (manager) is offered no revert, not even hidden, and the endpoint "
          "answers 403", r is not None and r.status == 200 and REVERT not in html
          and "Revert to the plain strategy" not in html and post.status_code == 403,
          page=r.status if r else None, post=post.status_code)


def cleanup():
    note("cleanup", "restore", strategy=lib.restore_strategy(), swept=lib.sweep("requester", FOLDER + "/"))


lib.run(sys.argv, {"A": sec_A, "T": sec_T, "G": sec_G, "V": sec_V, "E": sec_E, "R": sec_R}, cleanup)
