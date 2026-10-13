"""e2e-27 D1 (Wave D, issue #18 items 4 and 7): request pages are titled by their subject and carry an ID row with
core's copy button; the "Revert to the plain strategy" entry sits at the end of the Batch Control section inside core's
Advanced control.

usage: python titles_revert.py [ATGVELNCDXRP]   rows: out/titles_revert.jsonl, shots: screenshots/run-27/R27-D1-*.png
Items (each name ends in -nightly-settlement, left out below: core cuts a breadcrumb wider than about 224 px and only
then gives it a tooltip, so the titles must be long): folder r27-d1 with r27-d1/batch, r27-d1/act (not activated),
r27-d1/hold (activated once through the real ACTIVATE flow, so a HOLD request can be filed), r27-d1/q"x'y{z} (core
accepts the quotes and braces, so the name reaches text and attributes) and "r27-d1/배치 a+b" (non-ASCII, a space and a
plus: a URL-encoded name would show), and the top-level job r27-d1-top; all need approval. The requester files the
requests over REST (the plugin's own endpoints); the pages are read in the browser, one new context per account and
page.

Every check looks at content (the text of the title, the heading and the breadcrumb, attributes, the position in the
DOM), never only at an HTTP status. A check named "D1 #18.4" / "D1 #18.7" fails on a plugin without the change; one
named "guard:" already holds there and must keep holding.

A  arrangement: the items; sweeps the requester's pending r27-d1 requests and windows of an earlier pass; files a run
   request on five jobs, a permission window request for CONFIGURE (job in the folder, odd name), CREATE (the folder
   itself) and DELETE (top-level job), an ACTIVATE request on three jobs and a HOLD request on r27-d1/hold.
T  #18.4 run request page, for the requester, the designated approver approver-1, manager (BatchControl/Manage), admin
   and approver-2 (reads the job, neither requester nor designated approver): <title>, app bar heading (the only h1)
   and last breadcrumb read "Run request: r27-d1/batch" and none of them holds the id; the breadcrumb, cut by core,
   carries the same text as its tooltip; exactly one "ID" row, in the summary table, shows the full id in code style
   with core's copy button (button.jenkins-copy-button, text=<id>, tooltip "Copy the ID"); pressing it puts the id on
   the clipboard and marks the button copied. Guards: the page answers 200 and still links the job.
G  #18.4 permission window (grant) request page, same four roles: "Grant request: r27-d1/batch" (CONFIGURE); for a
   CREATE request the scope is the folder: "Grant request: r27-d1" (short: the breadcrumb is not cut).
V  #18.4 activation request page, same four roles: "Activation request: r27-d1/act"; the HOLD request's page reads
   "Hold request: r27-d1/hold" or "Activation request: r27-d1/hold" (T-UI-232 accepts both) in all three places.
E  #18.4 escaping (approver-1): the run, grant and activation request pages of r27-d1/q"x'y{z} read the name exactly in
   the title, heading, breadcrumb and the breadcrumb's tooltip attribute; no attribute of the page holds the name cut
   off at a quote; nothing is shown double-escaped; the run request page of "r27-d1/배치 a+b" reads the name as it is (not URL-encoded).
L  #18.4 top-level job (approver-1): "Run request: r27-d1-top", "Grant request: r27-d1-top" (DELETE),
   "Activation request: r27-d1-top".
N  guards, who may not see a request: nobc (no Batch Control permission) and an anonymous visitor get an error page
   that names neither the subject nor the job for all four kinds, on the screen and over REST; approver-2 (Approve, not
   designated) gets the same for the grant and activation requests.
C  guard, classic job page (the experimental flag off for approver-1, as the classic passes of the suite set it): the
   run, grant, activation and hold request pages read the same titles and ID rows. The flag is put back.
D  guard, decided requests: the rejected run request, the approved grant request (window open) and the cancelled
   activation request keep their titles and ID rows.
X  guard, a subject renamed afterwards: r27-d1/ren-a is re-created, a run request, an ACTIVATE request and an approved
   CONFIGURE window name it, then the administrator renames it to r27-d1/ren-b. The three pages keep the name the
   request was made for in title, heading and breadcrumb (the run and activation requests are INVALIDATED; the window
   follows the item, and its Scope row, not the title, shows the new name to a viewer who may see the item).
R  #18.7 (administrator) on Manage Jenkins > System and on the Batch Control configuration page: the revert entry is
   inside core's Advanced control (div.advancedBody of the form item whose button is button.advanced-button) of the
   Batch Control section and not visible; pressing that Advanced button moves it out and shows it; no Batch Control
   field follows it. Guards: one entry per page, it keeps the destructive colour and posts to
   <context>/manage/administrativeMonitor/batch-control-strategy/revert; pressing it opens core's confirmation (Cancel
   changes nothing, OK posts once, below 400, and installs the plain strategy with every matrix entry kept; the page
   then offers neither the entry nor an Advanced button); the driver restores the Batch Control strategy through the
   monitor's migrate endpoint (entries unchanged) and repeats this on the second page. A refused save of the Batch
   Control page re-renders the entry inside Advanced; a save with Advanced open changes neither strategy nor switches.
   Who gets it: manager (BatchControl/Manage) opens the Batch Control page and finds no revert, not even hidden, and
   Advanced tells them to ask an administrator; manager cannot open Manage Jenkins > System; requester, approver-1 and
   nobc can open neither page. The endpoint: GET 405 for the administrator, POST 403 for everyone else and for the
   administrator without a crumb; the strategy stays installed after all of them.
P  #18.7 under the role strategy ("Batch Control: Role-Based Strategy" applied through JCasC for this section; the
   matrix strategy object is saved first and put back): the same placement on Manage Jenkins > System; OK installs the
   plain RoleBasedAuthorizationStrategy with every role kept; manager (a global role with BatchControl/Manage) is
   offered no revert and gets 403.
cleanup: the saved strategy put back if section P left the role profile; the Batch Control strategy restored if a
section left the plain one; approver-1's job page flag on; the requester's pending r27-d1 requests cancelled and windows
revoked."""
import json
import sys

import requests

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import lib  # noqa: E402
from lib import api, check, note, Session, norm, gv  # noqa: E402

lib.LOGNAME[0] = "titles_revert"
FOLDER = "r27-d1"
# Core cuts a breadcrumb wider than about 224 px (ellipsis) and only then gives it a tooltip with the full text, so the
# names are long enough to be cut in any font; the folder alone ("Grant request: r27-d1") is the one that fits.
TAIL = "-nightly-settlement"
BATCH, ACT, HOLD = f"{FOLDER}/batch{TAIL}", f"{FOLDER}/act{TAIL}", f"{FOLDER}/hold{TAIL}"
ODD, UNI, TOP = FOLDER + "/q\"x'y{z}" + TAIL, FOLDER + "/배치 a+b" + TAIL, "r27-d1-top" + TAIL
JOBS = (BATCH, ACT, HOLD, ODD, UNI, TOP)
REN_A, REN_B = f"{FOLDER}/ren-a{TAIL}", f"{FOLDER}/ren-b{TAIL}"
VIEWERS = ("requester", "approver-1", "manager", "admin")
S = {}
REVERT = f"administrativeMonitor/{lib.STRATEGY_MONITOR}/revert"
REVERT_URL = f"{lib.PREFIX}/manage/{REVERT}"
REVERT_TEXT = "Revert to the plain strategy"
ASK_ADMIN = "Only a Jenkins administrator can change the authorization strategy."
CONFIG_PAGES = (("/manage/configure", "system", 1), ("/manage/batch-control-configuration/", "bc-config", 2))
REVERT_SEL = f"[data-url$='{REVERT}'], [formaction$='{REVERT}'], [href$='{REVERT}'], form[action$='{REVERT}'] button"
SNAPSHOT = "r27-d1-strategy.xml"
ROLE_YAML = """jenkins:
  authorizationStrategy:
    batchControlRoleBased:
      roles:
        global:
          - name: admin
            permissions: [Overall/Administer]
            entries: [{user: admin}]
          - name: bc-manager
            permissions: [Overall/Read, BatchControl/Manage]
            entries: [{user: manager}]
"""
# One reading of a request page: the three titles, what the last breadcrumb carries besides its text, every "ID" row of
# the main panel's tables, and (for a name with quotes) every attribute that holds the name's first part.
PAGE_JS = """([stem, full]) => { const n = t => (t || '').replace(/\\s+/g, ' ').trim();
  const crumbs = [...document.querySelectorAll('.jenkins-breadcrumbs__list-item')].filter(li => li.dataset.type === 'breadcrumb-item');
  const last = crumbs[crumbs.length - 1] || null;
  const tipNames = ['tooltip', 'title', 'aria-label', 'data-tippy-content', 'data-html-tooltip'];
  const tips = []; if (last) [last, ...last.querySelectorAll('*')].forEach(e => tipNames.forEach(a => {
    if (e.hasAttribute(a) && e.tagName.toLowerCase() !== 'title') tips.push({tag: e.tagName.toLowerCase(), attr: a, value: e.getAttribute(a)}); }));
  const rows = []; [...document.querySelectorAll('#main-panel table')].forEach((t, ti) => {
    const trs = [...t.querySelectorAll(':scope > tbody > tr')]; trs.forEach((tr, ri) => {
      const th = tr.querySelector(':scope > th'); if (!th || n(th.textContent) !== 'ID') return;
      const td = tr.querySelector(':scope > td');
      rows.push({table: ti, row: ri + 1, of: trs.length, headers: trs.map(x => n((x.querySelector(':scope > th') || {}).textContent)),
        cell: td ? n(td.textContent) : null, code: td && td.querySelector('code') ? n(td.querySelector('code').textContent) : null,
        buttons: td ? [...td.querySelectorAll('button')].map(b => ({cls: b.className, text: b.getAttribute('text'),
          tooltip: b.getAttribute('tooltip'), message: b.getAttribute('message')})) : []}); }); });
  const cut = []; let carrying = 0;
  if (stem) document.querySelectorAll('*').forEach(e => { for (const a of e.attributes) if (a.value.includes(stem)) {
    carrying++; if (!a.value.includes(full)) cut.push({tag: e.tagName.toLowerCase(), attr: a.name, value: a.value.slice(0, 120)}); } });
  const shown = document.body.innerText;
  return {title: document.title, h1: [...document.querySelectorAll('h1')].map(h => n(h.innerText)),
    crumbs: crumbs.map(li => n(li.innerText)), last_current: last ? last.getAttribute('aria-current') : null, tips, rows,
    carrying, cut, entities: ['&quot;', '&#39;', '&apos;', '&amp;', '&lt;', '&#'].filter(x => shown.includes(x))}; }"""


# ---------------------------------------------------------------- arrangement helpers (script console, REST)
def activation_of(job):
    """'activated' / 'not activated', as the job page's notice says it (names URL-encoded, unlike lib.activation)."""
    import re
    m = re.search(r"Batch Control: this (?:job|folder) is ([a-z ]+?)\.", lib.text_of(api("admin", lib.jpath(job) + "/").text))
    return m.group(1) if m else None


def set_flag(user, value):
    """Arrangement (as r14/set_flag.py): the new job page experimental flag of `user`; returns its value afterwards."""
    return gv("""import jenkins.model.experimentalflags.*
def u = hudson.model.User.getById(""" + json.dumps(user) + """, true)
def m = new HashMap(); m.put('new-job-page.flag', """ + json.dumps(value) + """)
u.addProperty(new UserExperimentalFlagsProperty(m)); u.save()
return String.valueOf(new NewJobPageUserExperimentalFlag().getFlagValue(u))""")


def entries():
    """Server state: the installed strategy's content without its class (the XStream form minus the root element), so
    the Batch Control strategy and its plain parent compare equal when every entry was kept. {lines, sha}."""
    return lib.facts("""def x = jenkins.model.Jenkins.XSTREAM2.toXML(jenkins.model.Jenkins.get().authorizationStrategy).readLines()
def inner = x.size() > 2 ? x[1..-2].collect { it.trim() } : []
def md = java.security.MessageDigest.getInstance('SHA-256')
return groovy.json.JsonOutput.toJson([lines: inner.size(), sha: md.digest(inner.join('|').getBytes('UTF-8')).encodeHex().toString()])""")


def settings():
    """Server state: the Batch Control settings the configuration form saves."""
    return lib.facts(lib.L25.CFG + """return groovy.json.JsonOutput.toJson([run: cfg.runControlEnabled,
  change: cfg.changeControlEnabled, approvers: cfg.approvers as List, pending: cfg.pendingTimeoutHours,
  approvedRun: cfg.approvedRunTimeoutMinutes, maxGrant: cfg.maxGrantMinutes, retention: cfg.retentionMonths,
  notify: cfg.notifyBeforeExpiryMinutes, selfApproval: cfg.allowAdminSelfApproval])""")


def anonymous(path, method="GET"):
    return requests.request(method, lib.BASE + path, allow_redirects=False, timeout=60)


def page_errors(s):
    """Uncaught script errors of the page, without core's known intermittent header.js one (e2e-13 U-1)."""
    return [c for c in s.console if c.startswith("pageerror") and "reading 'replace'" not in c]


# ---------------------------------------------------------------- A
def sec_A():
    lib.ensure_folder(FOLDER)
    xml = lib.job_xml("fs", shell="echo e2e-27 D1")
    created = {n: lib.ensure_item(n, xml) for n in JOBS}
    props = {n: lib.set_property(n, approval=True) for n in JOBS}
    swept = lib.sweep("requester", FOLDER)
    S["hold_before"] = activation_of(HOLD)
    if S["hold_before"] != "activated":  # the real flow, once per Jenkins: ACTIVATE requested and approved
        code, rid = lib.submit_activation("requester", HOLD, "ACTIVATE", "e2e-27 D1 activate, for the hold page")
        S["hold_activated_by"] = (code, rid, lib.decide("approver-1", "activations", rid, "approve", "e2e-27 D1") if rid else None)
    S["hold_state"], S["act_state"] = activation_of(HOLD), activation_of(ACT)
    for key, job in (("run", BATCH), ("run_odd", ODD), ("run_uni", UNI), ("run_top", TOP), ("run_hold", HOLD)):
        S[key] = lib.submit_run("requester", job, f"e2e-27 D1 titles ({key})")
    S["grant"] = lib.submit_grant("requester", BATCH, ["CONFIGURE"], reason="e2e-27 D1 window")
    S["grant_odd"] = lib.submit_grant("requester", ODD, ["CONFIGURE"], reason="e2e-27 D1 odd window")
    S["grant_folder"] = lib.submit_grant("requester", FOLDER, ["CREATE"], reason="e2e-27 D1 create window")
    S["grant_top"] = lib.submit_grant("requester", TOP, ["DELETE"], reason="e2e-27 D1 delete window")
    for key, job in (("act", ACT), ("act_odd", ODD), ("act_top", TOP)):
        S[key] = lib.submit_activation("requester", job, "ACTIVATE", f"e2e-27 D1 activation ({key})")
    S["hold"] = lib.submit_activation("requester", HOLD, "HOLD", "e2e-27 D1 hold")
    keys = ("run", "run_odd", "run_uni", "run_top", "run_hold", "grant", "grant_odd", "grant_folder", "grant_top", "act",
            "act_odd", "act_top", "hold")
    ids = {k: S[k][1] for k in keys}
    kinds = {k: lib.stored("run" if k.startswith("run") else "grant" if k.startswith("grant") else "activation", v)
             for k, v in ids.items() if v}
    check("A", "arrangement: six jobs that need approval (five in the folder r27-d1, one top-level); r27-d1/hold is "
          "activated, r27-d1/act is not; five run, four grant, three ACTIVATE and one HOLD request filed (REST, requester), "
          "each stored PENDING", all(ids.values()) and all("approvalRequired=true" in p for p in props.values())
          and S["hold_state"] == "activated" and S["act_state"] == "not activated"
          and all(v.get("status") == "PENDING" and v.get("requester") == "requester" for v in kinds.values()),
          created=created, swept=swept, ids=ids, codes={k: S[k][0] for k in keys}, hold_before=S["hold_before"],
          hold_activated_by=S.get("hold_activated_by"), activation={"hold": S["hold_state"], "act": S["act_state"]})


# ---------------------------------------------------------------- one request page
def titled(sec, who, kind, key, expected, what, shot, copy=False, either=None, name=None, cut=True):
    """Opens the request S[key] of `kind` (run | grant | activation) as `who` and checks the titles and the ID row.
    `either`: a second accepted title (T-UI-232: a HOLD page). `name`: (stem, full) of a job name with quotes.
    `cut`: the title is long, so core cuts the breadcrumb and gives it a tooltip."""
    rid = S[key][1]
    s = Session(who)
    r = s.go(f"/batch-control/{lib.KIND_URL[kind]}/{rid}/")
    if cut:  # core's script adds the tooltip after it measured the breadcrumb
        lib._r6.until(s.page, lambda: s.page.locator(".jenkins-breadcrumbs__list-item[aria-current] [tooltip]").count(), 3000)
    p = s.page.evaluate(PAGE_JS, list(name or ("", "")))
    t = lib.titles(s.page)
    lib.page_shot(s, f"{shot}-page")
    s.shot("#main-panel table", f"{shot}-summary")
    check(sec, f"guard: {who} opens the {what} page (200)", r is not None and r.status == 200,
          status=r.status if r else None)
    accepted = [expected] + ([either] if either else [])
    check(sec, f"D1 #18.4 title: the {what} page's <title>, app bar heading and last breadcrumb read "
          + " or ".join(f"'{x}'" for x in accepted) + f" ({who})",
          t[0] in accepted and list(t) == [t[0]] * 3 and p["title"] == t[0] + " - Jenkins",
          expected=accepted, shown=t, document_title=p["title"])
    check(sec, f"D1 #18.4 title: the id is in none of the {what} page's title, heading and breadcrumbs, the heading is "
          f"the page's only h1 and the last breadcrumb is the current page ({who})",
          all(x and rid not in x for x in t) and not any(rid in c for c in p["crumbs"]) and p["h1"] == [t[1]]
          and p["last_current"] == "page", id=rid, shown=t, h1=p["h1"], breadcrumbs=p["crumbs"])
    # Core 2.568.3 renders the current page's breadcrumb as a <span>; its script gives the span a `tooltip` (and
    # `title`) with the full text only when the text is wider than the breadcrumb's 224 px and is shown cut.
    tips = p["tips"]
    tooltip = [x["value"] for x in tips if x["attr"] == "tooltip"]
    if cut:
        check(sec, f"D1 #18.4 tooltip: the {what} page's last breadcrumb is shown cut and its tooltip carries the full "
              f"title unchanged, as does everything else it carries ({who})", tooltip == [t[0]] and t[0] in accepted
              and all(x["value"] == t[0] for x in tips), attributes=tips)
    else:
        check(sec, f"D1 #18.4 tooltip: nothing the {what} page's last breadcrumb carries besides its text differs from "
              f"the title ({who}); the short title fits, core adds {len(tooltip)} tooltip(s)",
              all(x["value"] == t[0] for x in tips), attributes=tips)
    rows = p["rows"]
    row = rows[0] if rows else {}
    btn = [b for b in row.get("buttons", []) if "jenkins-copy-button" in (b.get("cls") or "")]
    check(sec, f"D1 #18.4 ID row: {who}'s {what} page has exactly one row headed 'ID', in the summary table (the one with "
          "Status and Requester), showing only the full id, in code style, with core's copy button "
          "(button.jenkins-copy-button, text=<id>, tooltip 'Copy the ID')",
          len(rows) == 1 and row.get("table") == 0 and {"Status", "Requester"} <= set(row.get("headers", []))
          and row.get("cell") == rid and row.get("code") == rid and len(btn) == 1 and btn[0].get("text") == rid
          and btn[0].get("tooltip") == "Copy the ID", id=rid, rows=rows)
    if name:
        check(sec, f"D1 #18.4 escaping: on the {what} page no attribute holds the name cut off at a quote and nothing is "
              f"shown double-escaped ({who}); {p['carrying']} attribute(s) carry the name", not p["cut"] and not p["entities"],
              cut=p["cut"], entities=p["entities"])
    check(sec, f"guard: the {what} page raises no script error ({who})", not page_errors(s), errors=page_errors(s)[:3])
    if copy:
        # Core 2.568.3's copyButton.js: the click writes the `text` attribute to the clipboard and marks the button
        # "copied" (a check mark) for 2 s; it never shows the `message` attribute.
        clip, hover, marked, usable = None, [], False, None
        if btn:
            s.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=lib.ORIGIN)
            s.page.evaluate("navigator.clipboard.writeText('r27-d1 not copied yet')")
            b = s.page.locator("#main-panel table tr:has(> th:text-is('ID')) button.jenkins-copy-button").first
            usable = b.is_enabled()
            b.hover()
            lib._r6.until(s.page, lambda: s.page.locator(".tippy-box").count(), 3000)
            hover = [norm(x) for x in s.page.locator(".tippy-box").all_inner_texts()]
            b.click()
            marked = bool(lib._r6.until(s.page, lambda: "jenkins-copy-button--copied" in (b.get_attribute("class") or ""), 3000))
            s.shot("#main-panel table tr:has(> th:text-is('ID'))", f"{shot}-copied")
            try:
                clip = s.page.evaluate("navigator.clipboard.readText()")
            except Exception as e:  # noqa: a browser without clipboard access
                clip = f"unreadable: {e!r}"[:200]
        check(sec, f"D1 #18.4 ID row: the copy button is enabled, says 'Copy the ID' on hover, and pressing it puts the "
              f"full id on the clipboard and marks the button copied ({who}, {what})",
              bool(usable) and "Copy the ID" in hover and clip == rid and marked, clipboard=clip, id=rid, hover=hover,
              marked=marked, enabled=usable)
    s.done()
    return t[0]


def sec_T():
    for i, who in enumerate(VIEWERS + ("approver-2",), 1):
        titled("T", who, "run", "run", f"Run request: {BATCH}", "run request", f"R27-D1-T-0{i}-run-request-{who}",
               copy=(who == "requester"))
    s = Session("requester")
    s.go(f"/batch-control/requests/{S['run'][1]}/")
    job_link = s.page.locator(f"#main-panel table a[href$='{lib.jpath(BATCH)}/']").count()
    s.done()
    check("T", "guard: the run request page still links its job in the summary table", job_link >= 1, links=job_link)


def sec_G():
    for i, who in enumerate(VIEWERS, 1):
        titled("G", who, "grant", "grant", f"Grant request: {BATCH}", "grant request (CONFIGURE)",
               f"R27-D1-G-0{i}-grant-request-{who}", copy=(who == "approver-1"))
    titled("G", "approver-1", "grant", "grant_folder", f"Grant request: {FOLDER}", "grant request (CREATE in the folder)",
           "R27-D1-G-05-grant-request-create-folder", cut=False)


def sec_V():
    for i, who in enumerate(VIEWERS, 1):
        titled("V", who, "activation", "act", f"Activation request: {ACT}", "activation request (ACTIVATE)",
               f"R27-D1-V-0{i}-activation-request-{who}", copy=(who == "approver-1"))
    shown = set()
    for i, who in enumerate(VIEWERS, 5):
        shown.add(titled("V", who, "activation", "hold", f"Hold request: {HOLD}", "activation request (HOLD)",
                         f"R27-D1-V-0{i}-hold-request-{who}", either=f"Activation request: {HOLD}", copy=(who == "requester")))
    note("V", "the HOLD request's page is titled", titles=sorted(shown))
    check("V", "D1 #18.4 title: every viewer gets the same title for the HOLD request", len(shown) == 1, titles=sorted(shown))


def sec_E():
    odd = (FOLDER + "/q", ODD)
    titled("E", "approver-1", "run", "run_odd", f"Run request: {ODD}", "run request (odd name)",
           "R27-D1-E-01-run-request-odd-name", name=odd, copy=True)
    titled("E", "approver-1", "grant", "grant_odd", f"Grant request: {ODD}", "grant request (odd name)",
           "R27-D1-E-02-grant-request-odd-name", name=odd)
    titled("E", "approver-1", "activation", "act_odd", f"Activation request: {ODD}", "activation request (odd name)",
           "R27-D1-E-03-activation-request-odd-name", name=odd)
    titled("E", "approver-1", "run", "run_uni", f"Run request: {UNI}", "run request (non-ASCII name with a space and a plus)",
           "R27-D1-E-04-run-request-non-ascii-name", name=(FOLDER + "/배치", UNI))


def sec_L():
    titled("L", "approver-1", "run", "run_top", f"Run request: {TOP}", "run request (top-level job)",
           "R27-D1-L-01-run-request-top-level")
    titled("L", "approver-1", "grant", "grant_top", f"Grant request: {TOP}", "grant request (DELETE, top-level job)",
           "R27-D1-L-02-grant-request-top-level")
    titled("L", "approver-1", "activation", "act_top", f"Activation request: {TOP}", "activation request (top-level job)",
           "R27-D1-L-03-activation-request-top-level")


# ---------------------------------------------------------------- N: who may not see a request
def sec_N():
    cases = (("run", "run", BATCH, ("nobc", None)), ("grant", "grant", BATCH, ("nobc", "approver-2", None)),
             ("activation", "act", ACT, ("nobc", "approver-2", None)), ("activation", "hold", HOLD, ("nobc", "approver-2", None)))
    for kind, key, job, users in cases:
        path = f"/batch-control/{lib.KIND_URL[kind]}/{S[key][1]}/"
        for who in users:
            r = api(who, path) if who else anonymous(path)
            check("N", f"guard: {who or 'an anonymous visitor'} gets no {key} request page: an error status and a body that "
                  "names neither the subject nor the job", r.status_code >= 400 and "request: " + job not in r.text
                  and job not in r.text, status=r.status_code, text=lib.text_of(r.text)[:160])
    for i, (kind, key, job, _) in enumerate(cases, 1):
        s = Session("nobc")
        r = s.go(f"/batch-control/{lib.KIND_URL[kind]}/{S[key][1]}/")
        t = lib.titles(s.page)
        text = norm(s.page.locator("body").inner_text())
        lib.page_shot(s, f"R27-D1-N-0{i}-nobc-{key}-request")
        s.done()
        check("N", f"guard (screen): nobc's browser shows an error page for the {key} request whose title, heading and text "
              "do not name the job", r is not None and r.status >= 400 and job not in " ".join(x or "" for x in t)
              and job not in text and S[key][1] not in text, status=r.status if r else None, shown=t)


# ---------------------------------------------------------------- C: classic job page flag
def sec_C():
    S["flag"] = set_flag("approver-1", "false")
    try:
        check("C", "arrangement: the new job page flag is off for approver-1 (classic job pages)", S["flag"] == "false",
              flag=S["flag"])
        titled("C", "approver-1", "run", "run", f"Run request: {BATCH}", "run request (classic flag)",
               "R27-D1-C-01-run-request-classic")
        titled("C", "approver-1", "grant", "grant", f"Grant request: {BATCH}", "grant request (classic flag)",
               "R27-D1-C-02-grant-request-classic")
        titled("C", "approver-1", "activation", "act", f"Activation request: {ACT}", "activation request (classic flag)",
               "R27-D1-C-03-activation-request-classic")
        titled("C", "approver-1", "activation", "hold", f"Hold request: {HOLD}", "hold request (classic flag)",
               "R27-D1-C-04-hold-request-classic", either=f"Activation request: {HOLD}")
    finally:
        S["flag"] = set_flag("approver-1", "true")
    check("C", "arrangement: the flag is on again for approver-1", S["flag"] == "true", flag=S["flag"])


# ---------------------------------------------------------------- D: decided requests
def sec_D():
    done = {"run_top": lib.decide("approver-1", "requests", S["run_top"][1], "reject", "e2e-27 D1 rejected"),
            "grant_top": lib.decide("approver-1", "grants", S["grant_top"][1], "approve", "e2e-27 D1 approved"),
            "act_top": api("requester", f"/batch-control/activations/{S['act_top'][1]}/cancel", "POST").status_code}
    state = {"run_top": lib.stored("run", S["run_top"][1]).get("status"),
             "grant_top": lib.stored("grant", S["grant_top"][1]).get("status"),
             "act_top": lib.stored("activation", S["act_top"][1]).get("status")}
    check("D", "arrangement: approver-1 rejected the run request and approved the DELETE window on r27-d1-top, the requester "
          "cancelled the ACTIVATE request (server state)",
          state == {"run_top": "REJECTED", "grant_top": "APPROVED", "act_top": "CANCELLED"}, codes=done, state=state)
    titled("D", "requester", "run", "run_top", f"Run request: {TOP}", "rejected run request",
           "R27-D1-D-01-run-request-rejected")
    titled("D", "requester", "grant", "grant_top", f"Grant request: {TOP}", "approved grant request (window open)",
           "R27-D1-D-02-grant-request-approved")
    titled("D", "approver-1", "activation", "act_top", f"Activation request: {TOP}", "cancelled activation request",
           "R27-D1-D-03-activation-request-cancelled")


# ---------------------------------------------------------------- X: the subject renamed afterwards
def sec_X():
    for n in (REN_A, REN_B):
        if api("admin", lib.jpath(n) + "/api/json").status_code == 200:
            api("admin", lib.jpath(n) + "/doDelete", "POST")
    lib.ensure_item(REN_A, lib.job_xml("fs", shell="echo e2e-27 D1"))
    lib.set_property(REN_A, approval=True)
    S["run_ren"] = lib.submit_run("requester", REN_A, "e2e-27 D1 renamed later")
    S["act_ren"] = lib.submit_activation("requester", REN_A, "ACTIVATE", "e2e-27 D1 renamed later")
    S["grant_ren"] = lib.submit_grant("requester", REN_A, ["CONFIGURE"], reason="e2e-27 D1 renamed later")
    approved = lib.decide("approver-1", "grants", S["grant_ren"][1], "approve", "e2e-27 D1") if S["grant_ren"][1] else None
    renamed = api("admin", lib.jpath(REN_A) + "/confirmRename", "POST", data={"newName": REN_B.rsplit("/", 1)[1]}).status_code
    state = {"run": lib.stored("run", S["run_ren"][1]).get("status"), "activation": lib.stored("activation", S["act_ren"][1]).get("status"),
             "grant": lib.stored("grant", S["grant_ren"][1]).get("status"),
             "old": api("admin", lib.jpath(REN_A) + "/api/json").status_code, "new": api("admin", lib.jpath(REN_B) + "/api/json").status_code}
    check("X", "arrangement: a run request, an ACTIVATE request and an approved CONFIGURE window name r27-d1/ren-a; the "
          "administrator renamed it to r27-d1/ren-b (the two requests are INVALIDATED, the window stays APPROVED)",
          state == {"run": "INVALIDATED", "activation": "INVALIDATED", "grant": "APPROVED", "old": 404, "new": 200},
          approved=approved, renamed=renamed, state=state)
    titled("X", "approver-1", "run", "run_ren", f"Run request: {REN_A}", "run request (job renamed afterwards)",
           "R27-D1-X-01-run-request-renamed")
    titled("X", "approver-1", "activation", "act_ren", f"Activation request: {REN_A}",
           "activation request (job renamed afterwards)", "R27-D1-X-02-activation-request-renamed")
    titled("X", "requester", "grant", "grant_ren", f"Grant request: {REN_A}", "grant request (item renamed under its window)",
           "R27-D1-X-03-grant-request-renamed")
    r = api("requester", f"/batch-control/grants/{S['grant_ren'][1]}/")
    note("X", "UX: after the rename the permission window page is titled with the name the request was made for, while "
         "its Scope row shows the item's new name to a viewer who may see it", title=f"Grant request: {REN_A}",
         scope_row_names_new=REN_B in lib.text_of(r.text), scope_row_names_old=lib.text_of(r.text).count(REN_A))


# ---------------------------------------------------------------- R, P: the revert entry
STATE_JS = """(sel) => { const fieldSel = 'input[name^="_."], select[name^="_."], textarea[name^="_."]';
  const sec = document.querySelector('[name="_.runControlEnabled"]')?.closest('section') || null;
  const ctl = [...document.querySelectorAll(sel)];
  const vis = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
  const chain = e => { const out = []; for (let p = e.parentElement; p && out.length < 7; p = p.parentElement)
    out.push(p.tagName.toLowerCase() + (p.className && typeof p.className === 'string' ? '.' + p.className.trim().split(/\\s+/).join('.') : ''));
    return out.join(' < '); };
  return {section: !!sec, controls: ctl.map(e => { const body = e.closest('.advancedBody');
      const item = body ? body.parentElement : null; const btn = item ? item.querySelector(':scope > .advancedLink button.advanced-button') : null;
      if (btn) btn.setAttribute('data-r27-adv', '1');
      return {visible: vis(e), inSection: !!(sec && sec.contains(e)), chain: chain(e), inAdvancedBody: !!body,
        itemInSection: !!(item && sec && sec.contains(item)), advancedButton: btn ? btn.textContent.replace(/\\s+/g, ' ').trim() : null,
        advancedButtonVisible: btn ? vis(btn) : null, url: e.getAttribute('data-url') || e.getAttribute('formaction') || e.getAttribute('href'),
        destructive: e.className.includes('jenkins-!-destructive-color'), text: e.textContent.replace(/\\s+/g, ' ').trim(),
        fieldsAfter: sec ? [...sec.querySelectorAll(fieldSel)].filter(f => e.compareDocumentPosition(f) & Node.DOCUMENT_POSITION_FOLLOWING
          && !(e.compareDocumentPosition(f) & Node.DOCUMENT_POSITION_CONTAINED_BY)).map(f => f.name) : null}; }),
    advanced: sec ? [...sec.querySelectorAll('button.advanced-button, button.advancedButton')].map(b => (
      {visible: vis(b), expanded: b.dataset.expanded || null, marked: b.hasAttribute('data-r27-adv')})) : [],
    fields: sec ? sec.querySelectorAll(fieldSel).length : 0,
    hiddenText: sec ? [...sec.querySelectorAll('.advancedBody')].map(b => b.textContent.replace(/\\s+/g, ' ').trim()) : []}; }"""
SECTION = "section:has([name='_.runControlEnabled'])"


def end_shot(s, name):
    """A screenshot of the 1280 x 900 viewport with the end of the Batch Control section in its middle (the section is
    taller than a screen; r6's clipped shot assumes an unscrolled page): the Advanced button, or the last setting."""
    for sel in (f"{SECTION} button.advanced-button", f"{SECTION} [name='_.notifyBeforeExpiryMinutes']"):
        loc = s.page.locator(sel)
        if loc.count():
            loc.last.evaluate("e => e.scrollIntoView({block: 'center'})")
            break
    s.page.screenshot(path=str(lib.SHOTS / f"{name}.png"))


def revert_place(sec, path, tag, n, strategy_name):
    """#18.7 on one page: inside core's Advanced control and not visible until that Advanced button is pressed, then
    out of it and visible (core's script moves the rows out of div.advancedBody; the button stays and toggles them);
    nothing after it. Returns the Session with the entry revealed (None: no section)."""
    s = Session("admin")
    r = s.go(path)
    before = s.page.evaluate(STATE_JS, REVERT_SEL)
    end_shot(s, f"R27-D1-{sec}-{n}1-{tag}-section-end-before-advanced")
    if not before["section"]:
        check(sec, f"guard: {path} shows the Batch Control section", False, status=r.status if r else None, state=before)
        s.done()
        return None
    ctls = before["controls"]
    c = ctls[0] if ctls else {}
    check(sec, f"guard: {path} offers the administrator exactly one revert entry, in the Batch Control section, labelled "
          f"'{REVERT_TEXT}', posting to {REVERT_URL} ({strategy_name})",
          len(ctls) == 1 and c.get("inSection") and c.get("text") == REVERT_TEXT and c.get("url") == REVERT_URL,
          controls=ctls)
    check(sec, f"D1 #18.7 {path}: the revert entry is inside core's Advanced control (div.advancedBody of a form item of "
          "the Batch Control section whose button is button.advanced-button 'Advanced')",
          bool(c.get("inAdvancedBody") and c.get("itemInSection") and c.get("advancedButton") == "Advanced"
               and c.get("advancedButtonVisible") and len(before["advanced"]) == 1), chain=c.get("chain"),
          advanced_button=c.get("advancedButton"), advanced_buttons=before["advanced"])
    check(sec, f"D1 #18.7 {path}: the revert entry is not visible before Advanced is pressed (not among the routine "
          "settings)", bool(ctls) and not any(x["visible"] for x in ctls), controls=ctls)
    b = s.page.locator("[data-r27-adv='1']")
    pressed = False
    if b.count() == 1 and b.is_visible():
        b.scroll_into_view_if_needed()
        b.click()
        lib._r6.until(s.page, lambda: s.page.locator(REVERT_SEL).filter(visible=True).count(), 3000)
        pressed = True
    after = s.page.evaluate(STATE_JS, REVERT_SEL)
    shown = [x for x in after["controls"] if x["visible"] and x["inSection"]]
    end_shot(s, f"R27-D1-{sec}-{n}2-{tag}-section-end-after-advanced")
    check(sec, f"D1 #18.7 {path}: pressing that Advanced button (and no other) moves the revert entry out of the "
          "Advanced body and shows it", pressed and len(shown) == 1 and len(after["controls"]) == 1
          and not shown[0]["inAdvancedBody"] and [x["expanded"] for x in after["advanced"] if x["marked"]] == ["true"],
          pressed=pressed, controls=after["controls"], advanced_buttons=after["advanced"])
    if pressed:  # core's Advanced is a toggle: a second press hides the entry again, a third shows it for what follows
        b.click()
        lib._r6.until(s.page, lambda: not s.page.locator(REVERT_SEL).filter(visible=True).count(), 3000)
        folded = s.page.evaluate(STATE_JS, REVERT_SEL)
        b.click()
        lib._r6.until(s.page, lambda: s.page.locator(REVERT_SEL).filter(visible=True).count(), 3000)
        again = s.page.evaluate(STATE_JS, REVERT_SEL)
        check(sec, f"D1 #18.7 {path}: pressing Advanced again hides the revert entry, once more shows it",
              len(folded["controls"]) == 1 and not folded["controls"][0]["visible"]
              and len(again["controls"]) == 1 and again["controls"][0]["visible"],
              folded=[x["visible"] for x in folded["controls"]], again=[x["visible"] for x in again["controls"]])
    ctl = shown[0] if shown else (after["controls"][0] if after["controls"] else {})
    check(sec, f"D1 #18.7 {path}: the revert entry is the last entry of the Batch Control section (none of its "
          f"{after['fields']} fields follows it)", ctl.get("fieldsAfter") == [] and after["fields"] >= 10,
          fields_after=ctl.get("fieldsAfter"), chain=ctl.get("chain"))
    check(sec, f"guard: {path}: the revert entry keeps the destructive colour", bool(ctl.get("destructive")),
          text=ctl.get("text"))
    return s


def revert_through(sec, s, path, tag, n, plain):
    """Guard: the entry, pressed where it now is, still reverts. Cancel keeps the strategy; OK posts once to the
    unchanged endpoint and installs `plain` with every entry kept; the page then offers no revert. Closes `s`."""
    before, kept = lib.strategy(), entries()
    posts = []
    s.page.on("response", lambda r: posts.append((r.status, r.url)) if r.request.method == "POST" else None)
    ctl = s.page.locator(REVERT_SEL).filter(visible=True).first
    ctl.click()
    ok = lib.opened(s.page)
    s.shot("dialog[open]", f"R27-D1-{sec}-{n}3-{tag}-revert-confirmation")
    dlg_text = norm(s.page.locator("dialog[open]").first.inner_text()) if ok else None
    if ok:
        s.page.locator("dialog[open] button[data-id=cancel]").click()
        lib.gone(s.page)
    after_cancel, posts_cancel = lib.strategy(), list(posts)
    ctl.click()
    ok2 = lib.opened(s.page)
    nav = None
    if ok2:
        before_url = s.page.url
        s.page.locator("dialog[open] button[data-id=ok]").click()
        nav = lib.react(s.page, before_url, timeout=15000)
        lib.wait_until(lambda: lib.strategy() != before, timeout=15, step=1)
    after_ok, after_entries = lib.strategy(), entries()
    end_shot(s, f"R27-D1-{sec}-{n}4-{tag}-after-revert")
    mine = [p for p in posts if p[1].split("?")[0].endswith(REVERT_URL)]
    check(sec, f"guard: {path}: the revert entry opens core's confirmation naming the revert; Cancel posts nothing and "
          f"keeps {before}", bool(ok) and "Revert to the plain strategy?" in (dlg_text or "") and not posts_cancel
          and after_cancel == before, dialog=dlg_text, after_cancel=after_cancel, posts=posts_cancel)
    check(sec, f"guard: {path}: OK posts once to {REVERT_URL}, answered below 400, and installs the plain {plain} with "
          "every entry kept", bool(ok2) and len(mine) == 1 and mine[0][0] < 400 and after_ok == plain
          and after_entries == kept and kept["lines"] > 0, posts=mine, before=before, after_ok=after_ok,
          entries_before=kept, entries_after=after_entries, reaction=nav, landed=s.page.url.replace(lib.BASE, ""))
    s.go(path)
    gone = s.page.evaluate(STATE_JS, REVERT_SEL)
    html = s.page.content()
    end_shot(s, f"R27-D1-{sec}-{n}5-{tag}-section-end-plain-strategy")
    s.done()
    check(sec, f"guard: {path}: with the plain strategy installed the Batch Control section offers neither the revert "
          "entry nor an Advanced button", gone["section"] and not gone["controls"] and not gone["advanced"]
          and REVERT_TEXT not in html, controls=gone["controls"], advanced_buttons=gone["advanced"])
    return kept


def refused(who, method="POST", crumb=True):
    r = (api(who, "/manage/" + REVERT, method, crumb=crumb) if who else anonymous("/manage/" + REVERT, method))
    return r.status_code


def sec_R():
    matrix = lib.strategy()
    for path, tag, n in CONFIG_PAGES:
        s = revert_place("R", path, tag, n, matrix)
        if s is None:
            continue
        kept = revert_through("R", s, path, tag, n, "ProjectMatrixAuthorizationStrategy")
        restored = lib.restore_strategy()
        check("R", "arrangement: the Batch Control strategy restored through the monitor's migrate endpoint, every entry "
              "kept", restored[1] == matrix and entries() == kept, restored=restored, entries=entries())
    # a refused save re-renders the form inside the POST (e2e-04 FD-15): the entry is inside Advanced there as well
    cfg = settings()
    s = Session("admin")
    s.go(CONFIG_PAGES[1][0])
    s.page.locator("input[name='_.pendingTimeoutHours']").first.fill("-5")
    with s.page.expect_navigation() as nav:
        s.page.click("button[name=Submit]")
    s.page.wait_for_load_state("load")
    st = s.page.evaluate(STATE_JS, REVERT_SEL)
    end_shot(s, "R27-D1-R-31-bc-config-refused-save")
    status = nav.value.status if nav.value else None
    c = st["controls"][0] if st["controls"] else {}
    check("R", "D1 #18.7 a refused save of the Batch Control page (pending timeout -5, HTTP 400, nothing saved) re-renders "
          "the revert entry inside the Advanced control, not visible", status == 400 and settings() == cfg
          and len(st["controls"]) == 1 and bool(c.get("inAdvancedBody")) and not c.get("visible")
          and c.get("advancedButton") == "Advanced", status=status, controls=st["controls"])
    # a save with Advanced open: the entry is not a form field
    s.go(CONFIG_PAGES[1][0])
    st = s.page.evaluate(STATE_JS, REVERT_SEL)
    b = s.page.locator("[data-r27-adv='1']")
    if b.count() == 1:
        b.click()
        lib._r6.until(s.page, lambda: s.page.locator(REVERT_SEL).filter(visible=True).count(), 3000)
    open_ = s.page.locator(REVERT_SEL).filter(visible=True).count()
    with s.page.expect_navigation() as nav:
        s.page.click("button[name=Submit]")
    s.page.wait_for_load_state("load")
    status = nav.value.status if nav.value else None
    s.done()
    check("R", "guard: saving the Batch Control page with Advanced open (revert entry shown) keeps the strategy and the "
          "settings", open_ == 1 and status is not None and status < 400 and lib.strategy() == matrix
          and settings() == cfg, status=status, strategy=lib.strategy(), before=cfg, after=settings())
    # who gets it
    m = Session("manager")
    r = m.go(CONFIG_PAGES[1][0])
    html = m.page.content()
    st = m.page.evaluate(STATE_JS, REVERT_SEL)
    hidden = list(st["hiddenText"])
    adv = m.page.locator(f"{SECTION} button.advanced-button")
    pressed = adv.count()
    if pressed:
        adv.first.click()
        lib._r6.until(m.page, lambda: m.page.get_by_text(ASK_ADMIN).first.is_visible(), 3000)
    told = m.page.get_by_text(ASK_ADMIN).first.is_visible() if m.page.get_by_text(ASK_ADMIN).count() else False
    after = m.page.evaluate(STATE_JS, REVERT_SEL)
    end_shot(m, "R27-D1-R-41-manager-bc-config-advanced-open")
    r2 = m.go(CONFIG_PAGES[0][0])
    html2 = m.page.content()
    m.done()
    check("R", "guard: the BatchControl/Manage holder (manager) opens the Batch Control page (200) and is offered no "
          "revert, not even hidden, before or after pressing Advanced", r is not None and r.status == 200
          and not st["controls"] and not after["controls"] and REVERT not in html and REVERT_TEXT not in html,
          page=r.status if r else None, advanced_buttons=pressed)
    check("R", "guard: the manager is told whom to ask ('" + ASK_ADMIN + "')", told, shown=told, advanced_buttons=pressed,
          advanced_text=hidden)
    note("R", "UX: the manager reads that sentence only after pressing Advanced, which then holds no setting and no "
         "button for them", advanced_buttons=pressed, advanced_text=hidden)
    check("R", "guard: the manager cannot open Manage Jenkins > System (403) and its page names no revert",
          r2 is not None and r2.status == 403 and REVERT not in html2 and REVERT_TEXT not in html2,
          status=r2.status if r2 else None)
    pages = {f"{who or 'anonymous'} {path}": (api(who, path) if who else anonymous(path))
             for who in ("requester", "approver-1", "nobc", None) for path, _, _ in CONFIG_PAGES}
    check("R", "guard: requester, approver-1, nobc and an anonymous visitor open neither configuration page (403) and are "
          "shown no revert", all(v.status_code == 403 and REVERT not in v.text and REVERT_TEXT not in v.text
                                 for v in pages.values()), status={k: v.status_code for k, v in pages.items()})
    codes = {"admin GET": refused("admin", "GET"), "admin POST without a crumb": refused("admin", crumb=False),
             "manager POST": refused("manager"), "requester POST": refused("requester"),
             "approver-1 POST": refused("approver-1"), "nobc POST": refused("nobc"), "anonymous POST": refused(None)}
    check("R", "guard: the revert endpoint answers 405 to the administrator's GET and 403 to a POST by manager, requester, "
          "approver-1, nobc, an anonymous visitor and the administrator without a crumb; the Batch Control strategy is "
          "still installed", codes.pop("admin GET") == 405 and all(v == 403 for v in codes.values())
          and lib.strategy() == matrix, codes=codes, strategy=lib.strategy())


def role_profile(apply):
    """Arrangement (script console, as r22/rename_queue.py): saves the installed strategy (XStream) and applies the
    role profile through JCasC, or puts the saved strategy back. Returns the strategy's simple class name."""
    if apply:
        return gv("""import jenkins.model.Jenkins
def j = Jenkins.get(); def snap = new File(j.rootDir, '""" + SNAPSHOT + """')
// a pass that died before its restore left the snapshot of the original strategy: keep it
if (!snap.exists()) snap.setText(Jenkins.XSTREAM2.toXML(j.authorizationStrategy), 'UTF-8')
def yaml = new File(j.rootDir, 'r27-d1-role.yaml'); yaml.setText(""" + json.dumps(ROLE_YAML) + """, 'UTF-8')
io.jenkins.plugins.casc.ConfigurationAsCode.get().configure(yaml.absolutePath)
return j.authorizationStrategy.getClass().simpleName""")
    return gv("""import jenkins.model.Jenkins
def j = Jenkins.get(); def snap = new File(j.rootDir, '""" + SNAPSHOT + """')
if (!snap.exists()) return 'no snapshot: ' + j.authorizationStrategy.getClass().simpleName
j.setAuthorizationStrategy(Jenkins.XSTREAM2.fromXML(snap.getText('UTF-8'))); j.save()
snap.delete(); new File(j.rootDir, 'r27-d1-role.yaml').delete()
return j.authorizationStrategy.getClass().simpleName""")


def sec_P():
    matrix, matrix_entries = lib.strategy(), entries()
    try:
        role = role_profile(True)
        check("P", "arrangement: 'Batch Control: Role-Based Strategy' installed through JCasC (admin: Administer; "
              "manager: Overall/Read + BatchControl/Manage)", role == "BatchControlRoleBasedAuthorizationStrategy",
              before=matrix, strategy=role)
        path, tag, _ = CONFIG_PAGES[0]
        s = revert_place("P", path, tag + "-role", 1, role)
        m = Session("manager")
        r = m.go(CONFIG_PAGES[1][0])
        html = m.page.content()
        st = m.page.evaluate(STATE_JS, REVERT_SEL)
        m.done()
        post = refused("manager")
        check("P", "guard: under the role strategy the BatchControl/Manage holder opens the Batch Control page (200), is "
              "offered no revert, not even hidden, and the endpoint answers 403; the role strategy stays",
              r is not None and r.status == 200 and not st["controls"] and REVERT not in html and REVERT_TEXT not in html
              and post == 403 and lib.strategy() == role, page=r.status if r else None, post=post, strategy=lib.strategy())
        if s is not None:
            revert_through("P", s, path, tag + "-role", 1, "RoleBasedAuthorizationStrategy")
    finally:
        back = role_profile(False)
    check("P", "arrangement: the saved matrix strategy is installed again with its entries", back == matrix
          and entries() == matrix_entries, restored=back, entries=entries(), before=matrix_entries)


def cleanup():
    note("cleanup", "restore", saved_strategy=role_profile(False), strategy=lib.restore_strategy(),
         flag=set_flag("approver-1", "true"), swept=lib.sweep("requester", FOLDER))


lib.run(sys.argv, {"A": sec_A, "T": sec_T, "G": sec_G, "V": sec_V, "E": sec_E, "L": sec_L, "N": sec_N, "C": sec_C,
                   "D": sec_D, "X": sec_X, "R": sec_R, "P": sec_P}, cleanup)
