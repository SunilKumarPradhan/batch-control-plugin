"""e2e-27 D1 (Wave D, issue #18 items 4 and 7): request pages are titled by their subject and carry an ID row with
core's copy button; the "Revert to the plain strategy" entry sits at the end of the Batch Control section inside core's
Advanced control.

usage: python titles_revert.py [ATGVEFKLNCDXSHRP]   rows: out/titles_revert.jsonl, shots: screenshots/run-27/R27-D1-*.png
Items (each name ends in -nightly-settlement, left out below: core cuts a breadcrumb wider than about 224 px and only
then gives it a tooltip, so the titles must be long): folder r27-d1 with r27-d1/batch, r27-d1/act (not activated),
r27-d1/hold (activated once through the real ACTIVATE flow, so a HOLD request can be filed), r27-d1/q"x'y{z} (core
accepts the quotes and braces, so the name reaches text and attributes) and "r27-d1/배치 a+b" (non-ASCII, a space and a
plus: a URL-encoded name would show), and the top-level job r27-d1-top; all need approval. The requester files the
requests over REST (the plugin's own endpoints); the pages are read in the browser, one new context per account and
page.

Every check looks at content (the text of the title, the heading and the breadcrumb, attributes, the position in the
DOM), never only at an HTTP status. A check named "D1 #18.4" / "D1 #18.7" fails on a plugin without the change; one
named "guard" already holds there and must keep holding.

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
   off at a quote; nothing is shown double-escaped; the run request page of "r27-d1/배치 a+b" reads the name as it is
   (not URL-encoded). Guard: markup cannot become a subject at all: core refuses an item name with <, > or &, and the
   plugin refuses a permission window request whose scope names no existing item (both 400, nothing stored).
F  #18.4 a refusal re-rendered at the POST URL (approver-1 presses Reject without a comment on the run and on the
   ACTIVATE request, HTTP 400 at …/reject): title, heading, breadcrumb, tooltip and ID row as on the page itself; the
   breadcrumb links back to the request's page. Guard: the message, and the request still PENDING.
K  #18.4 other kinds of subject (approver-1): a Pipeline job as the subject of a run request and of an ACTIVATE
   request; a CONFIGURE window on the multibranch project team-mb ("Grant request: team-mb", cancelled afterwards).
L  #18.4 top-level job (approver-1): "Run request: r27-d1-top", "Grant request: r27-d1-top" (DELETE),
   "Activation request: r27-d1-top".
N  guards, who may not see a request: nobc (no Batch Control permission) and an anonymous visitor get an error page
   that names neither the subject nor the job for all four kinds, on the screen and over REST; approver-2 (Approve, not
   designated) gets the same for the grant and activation requests.
C  guard, classic job page (the experimental flag off for approver-1 and admin, as the classic passes of the suite set
   it): the run, grant, activation and hold request pages read the same titles and ID rows, and the revert entry is
   placed the same on both configuration pages. The flags are put back.
D  guard, decided requests: the rejected run request, the approved grant request (window open) and the cancelled
   activation request keep their titles and ID rows.
X  a subject renamed or moved afterwards (T-UI-236..238, SPEC 8 D-74/D-75 (1)): the page of a permission window is
   titled with the item its Scope row names for the same viewer. r27-d1/ren-a is re-created; a run request, an ACTIVATE
   request and an approved CONFIGURE window (designated approvers approver-1 and approver-disc, who holds no
   Item/Read) name it; the administrator renames it to ren-b, then to ren-c, then moves it into r27-d1-vault, a folder
   only administrators read. After each step, for a viewer who may read the item where it is (requester, approver-1,
   manager, admin; after the move admin only): title, heading, breadcrumb and tooltip read
   "Grant request: <current name>", no earlier name is in any of them, and the Scope row names the same item. For a
   viewer who may open the page but not read the item (approver-disc from the first rename on; requester, approver-1
   and manager after the move): the three read exactly "Grant request: r27-d1/ren-a", the name as approved, the Scope
   row adds the fixed "moved" note, and neither the new name nor the vault is anywhere in the page's HTML (as rendered
   and as served) or in the answers of the page's contextMenu, childrenContextMenu and api/json. Also: a PENDING
   request that was never approved keeps the name it was made for when its item is renamed (T-UI-238); a window on a
   job below a renamed folder follows; the run and activation requests, INVALIDATED by the rename, keep their name.
   (The same title after a restart: r27/title_restart.py, run inside the unit r16-durable.)
S  #18.4 requests that ran or expired: the run request approved in A on the activated job is EXECUTED; the run, window
   and ACTIVATE requests on r27-d1/exp, made two hours old in the store in A, were expired by the plugin's periodic
   work. Titles and ID rows as everywhere else.
H  #18.4 ID row over plain HTTP on a host that is not localhost (not a "secure context", where core's copy button
   cannot write the clipboard; a second browser reaches the same Jenkins as http://r27-plain-http.test): the row still
   shows the full id as text; core disables the button and its tooltip says "Copy is only supported with a secure
   (HTTPS) connection."
R  #18.7 (administrator) on Manage Jenkins > System and on the Batch Control configuration page: the revert entry is
   inside core's Advanced control (div.advancedBody of the form item whose button is button.advanced-button) of the
   Batch Control section and not visible; pressing that Advanced button moves it out and shows it; no Batch Control
   field follows it. Guards: one entry per page, it keeps the destructive colour (the class and the computed colour
   of var(--destructive-color)) and posts to
   <context>/manage/administrativeMonitor/batch-control-strategy/revert; pressing it opens core's confirmation (Cancel
   changes nothing, OK posts once, below 400, and installs the plain strategy with every matrix entry kept; the page
   then offers neither the entry nor an Advanced button); the driver restores the Batch Control strategy through the
   monitor's migrate endpoint (entries unchanged) and repeats this on the second page. A refused save of the Batch
   Control page re-renders the entry inside Advanced; a save with Advanced open changes neither strategy nor switches.
   Escape on the confirmation posts nothing either. Who gets it (T-UI-239): manager (BatchControl/Manage) opens the
   Batch Control page and reads "Only a Jenkins administrator can change the authorization strategy." as the page
   loads, in the section, outside any Advanced body; the section has no Advanced button for them; nothing of the
   revert is rendered, not even hidden; manager cannot open Manage Jenkins > System; requester, approver-1 and nobc
   can open neither page. The endpoint: GET 405 for the administrator, POST 403 for everyone else and for the
   administrator without a crumb; the strategy stays installed after all of them; the administrator's own crumbed POST
   (REST, no browser) installs the plain strategy with every entry kept (restored through migrate).
   (Holders of Overall/Manage and Overall/SystemRead: r27/revert_permissions.py.)
P  #18.7 under the role strategy ("Batch Control: Role-Based Strategy" applied through JCasC for this section; the
   matrix strategy object is saved first and put back): the same placement on both pages; pressed from each page, OK
   installs the plain RoleBasedAuthorizationStrategy with every role kept (the Batch Control role strategy is
   re-installed through migrate in between); manager (a global role with BatchControl/Manage) reads the sentence
   without Advanced, is offered no revert and gets 403.
cleanup: the saved strategy put back if section P left the role profile; the Batch Control strategy restored if a
section left the plain one; approver-1's job page flag on; the requester's pending r27-d1 requests cancelled and windows
revoked."""
import json
import os
import re
import sys
from urllib.parse import quote, urlsplit

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
EXP, PIPE, MB = f"{FOLDER}/exp{TAIL}", f"{FOLDER}/pipe{TAIL}", "team-mb"
JOBS = (BATCH, ACT, HOLD, ODD, UNI, TOP, EXP)
VAULT = "r27-d1-vault"
REN = tuple(f"{FOLDER}/ren-{x}{TAIL}" for x in "abc")
PEND = (f"{FOLDER}/pend-a{TAIL}", f"{FOLDER}/pend-b{TAIL}")
FOLD, FOLD_JOB = (f"{FOLDER}/fold-a", f"{FOLDER}/fold-b"), "job" + TAIL
MOVED = " (moved; its new location is not visible to you)"
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
    crumbs: crumbs.map(li => n(li.innerText)), last_current: last ? last.getAttribute('aria-current') : null,
    last_href: last && last.querySelector('a') ? last.querySelector('a').getAttribute('href') : null, tips, rows,
    scope: (() => { const th = [...document.querySelectorAll('#main-panel table tr > th')].find(x => n(x.textContent) === 'Scope');
      return th && th.parentElement.querySelector('td') ? n(th.parentElement.querySelector('td').innerText) : null; })(),
    carrying, cut, entities: ['&quot;', '&#39;', '&apos;', '&amp;', '&lt;', '&#'].filter(x => shown.includes(x))}; }"""


# ---------------------------------------------------------------- arrangement helpers (script console, REST)
def activation_of(job):
    """'activated' / 'not activated', as the job page's notice says it (names URL-encoded, unlike lib.activation)."""
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


def window_of(rid):
    """Server state: the permission window of grant request `rid` ({} when it has none): the item it names now and
    whether it is open."""
    return lib.facts("""def f = new File(jenkins.model.Jenkins.get().rootDir, 'batch-control/grants/""" + rid + """.xml')
if (!f.exists()) return '{}'
def x = new XmlSlurper().parse(f)
return groovy.json.JsonOutput.toJson([scope: x.scope.fullName.text(), open: x.revokedAtMillis.text() == ''
  && ((x.expiresAtMillis.text() ?: '0') as long) > System.currentTimeMillis()])""")


def exists(item):
    return api("admin", lib.jpath(item) + "/api/json").status_code == 200


def remove(*items):
    """Arrangement: deletes the items that exist (administrator, REST)."""
    return {i: api("admin", lib.jpath(i) + "/doDelete", "POST").status_code for i in items if exists(i)}


def rename(item, leaf):
    """Arrangement: the administrator renames `item` (core's confirmRename, as the Rename page posts it)."""
    return api("admin", lib.jpath(item) + "/confirmRename", "POST", data={"newName": leaf}).status_code


def move(item, dest):
    """Arrangement: the administrator moves `item` into the folder `dest` (the folders plugin's move/move)."""
    return api("admin", lib.jpath(item) + "/move/move", "POST", data={"destination": "/" + dest}).status_code


def may_read(item, users):
    """Server state: who of `users` holds Item/Read on `item` (false when it does not exist)."""
    return lib.facts("""import hudson.model.*
def i = jenkins.model.Jenkins.get().getItemByFullName(""" + json.dumps(item) + """)
return groovy.json.JsonOutput.toJson(""" + json.dumps(list(users)) + """.collectEntries { u ->
  [u, i != null && i.getACL().hasPermission2(User.getById(u, true).impersonate2(), Item.READ)] })""")


def ensure_vault():
    """Arrangement (as r18/arrange.py): the folder r27-d1-vault, whose matrix blocks inheritance, so that only
    administrators read what is inside (D-75 (1))."""
    return gv("""def j = jenkins.model.Jenkins.get(); def vault = j.getItem('""" + VAULT + """')
if (vault == null) { vault = j.createProject(com.cloudbees.hudson.plugins.folder.Folder, '""" + VAULT + """')
  def uber = j.pluginManager.uberClassLoader
  def prop = uber.loadClass('com.cloudbees.hudson.plugins.folder.properties.AuthorizationMatrixProperty').getConstructor(List).newInstance([])
  prop.setInheritanceStrategy(uber.loadClass('org.jenkinsci.plugins.matrixauth.inheritance.NonInheritingStrategy').getConstructor().newInstance())
  vault.addProperty(prop); vault.save(); return 'created' }
return 'exists'""")


def backdate(pairs, hours=2):
    """Arrangement: makes the stored requests `pairs` ((kind, id), ...) `hours` old by rewriting createdAtMillis in
    their files, so that the plugin's own periodic work expires them (pendingTimeoutHours cannot be set below 1, and
    the plugin clock cannot be moved ahead on a shared Jenkins: the store refuses appends more than 60 s out of order)."""
    return gv("""def root = new File(jenkins.model.Jenkins.get().rootDir, 'batch-control'); def out = []
def old = System.currentTimeMillis() - """ + str(hours) + """ * 3600 * 1000L
""" + json.dumps([[lib.STORE_DIRS[k], v] for k, v in pairs]) + """.each { d, id -> def f = new File(root, d + '/' + id + '.xml')
  def t = f.getText('UTF-8'); def n = t.replaceFirst(/<createdAtMillis>\\d+<\\/createdAtMillis>/, '<createdAtMillis>' + old + '</createdAtMillis>')
  if (n != t) { f.setText(n, 'UTF-8'); out << id } }
return out.size()""")


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
    created[PIPE] = lib.ensure_item(PIPE, lib.job_xml("wf", script="echo 'e2e-27 D1'"))
    props = {n: lib.set_property(n, approval=True) for n in JOBS + (PIPE,)}
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
    S["run_pipe"] = lib.submit_run("requester", PIPE, "e2e-27 D1 titles (Pipeline job)")
    S["act_pipe"] = lib.submit_activation("requester", PIPE, "ACTIVATE", "e2e-27 D1 activation (Pipeline job)")
    S["grant_mb"] = lib.submit_grant("requester", MB, ["CONFIGURE"], reason="e2e-27 D1 window on a multibranch project")
    S["run_exp"] = lib.submit_run("requester", EXP, "e2e-27 D1 titles (left to expire)")
    S["grant_exp"] = lib.submit_grant("requester", EXP, ["CONFIGURE"], reason="e2e-27 D1 window (left to expire)")
    S["act_exp"] = lib.submit_activation("requester", EXP, "ACTIVATE", "e2e-27 D1 activation (left to expire)")
    keys = ("run", "run_odd", "run_uni", "run_top", "run_hold", "grant", "grant_odd", "grant_folder", "grant_top", "act",
            "act_odd", "act_top", "hold", "run_pipe", "act_pipe", "grant_mb", "run_exp", "grant_exp", "act_exp")
    ids = {k: S[k][1] for k in keys}
    kinds = {k: lib.stored("run" if k.startswith("run") else "grant" if k.startswith("grant") else "activation", v)
             for k, v in ids.items() if v}
    kind_of = {n: (api("admin", lib.jpath(n) + "/api/json?tree=_class").json() or {}).get("_class", "").rsplit(".", 1)[-1]
               for n in (BATCH, PIPE, MB)}
    check("A", "arrangement: seven Freestyle jobs and one Pipeline job that need approval (seven in the folder r27-d1, one "
          "top-level) and the multibranch project team-mb; r27-d1/hold is activated, r27-d1/act is not; seven run, six "
          "grant, five ACTIVATE and one HOLD request filed (REST, requester), each stored PENDING",
          all(ids.values()) and all("approvalRequired=true" in p for p in props.values())
          and kind_of == {BATCH: "FreeStyleProject", PIPE: "WorkflowJob", MB: "WorkflowMultiBranchProject"}
          and S["hold_state"] == "activated" and S["act_state"] == "not activated"
          and all(v.get("status") == "PENDING" and v.get("requester") == "requester" for v in kinds.values()),
          created=created, swept=swept, ids=ids, codes={k: S[k][0] for k in keys}, hold_before=S["hold_before"],
          hold_activated_by=S.get("hold_activated_by"), activation={"hold": S["hold_state"], "act": S["act_state"]},
          kinds=kind_of)
    # For section S, started now so that the unit does not wait for it: the run request on the activated job is approved
    # and runs; the three requests on r27-d1/exp are made two hours old, for the periodic work to expire them.
    S["ran"] = lib.decide("approver-1", "requests", S["run_hold"][1], "approve", "e2e-27 D1 run it") if S["run_hold"][1] else None
    S["backdated"] = backdate((("run", S["run_exp"][1]), ("grant", S["grant_exp"][1]), ("activation", S["act_exp"][1]))) \
        if all(S[k][1] for k in ("run_exp", "grant_exp", "act_exp")) else None


# ---------------------------------------------------------------- one request page
def titled(sec, who, kind, key, expected, what, shot, **kw):
    """Opens the request S[key] of `kind` (run | grant | activation) as `who` and judges the page (judge())."""
    rid = S[key][1]
    s = Session(who)
    r = s.go(f"/batch-control/{lib.KIND_URL[kind]}/{rid}/")
    shown = judge(sec, s, r.status if r else None, who, kind, rid, expected, what, shot, **kw)
    s.done()
    return shown


def judge(sec, s, status, who, kind, rid, expected, what, shot, copy=False, either=None, name=None, cut=True,
          want_status=200, absent=(), scope=None, raw_absent=()):
    """The checks of one request page as `s` shows it now: the titles and the ID row.
    `either`: a second accepted title (T-UI-232: a HOLD page). `name`: (stem, full) of a job name with quotes.
    `cut`: the title is long, so core cuts the breadcrumb and gives it a tooltip. `want_status`: the HTTP status the
    page was answered with (400: a refusal re-rendered at a POST URL). `absent`: names that title, heading,
    breadcrumbs and tooltip must not hold. `scope`: the exact text of the Scope row, whose item the title must name.
    `raw_absent`: strings that the page's HTML (as rendered and as served) and the answers of the page's
    contextMenu, childrenContextMenu and api/json must not hold. Returns the title shown."""
    if cut:  # core's script adds the tooltip after it measured the breadcrumb
        lib._r6.until(s.page, lambda: s.page.locator(".jenkins-breadcrumbs__list-item").last.locator("[tooltip]").count(), 3000)
    p = s.page.evaluate(PAGE_JS, list(name or ("", "")))
    t = lib.titles(s.page)
    lib.page_shot(s, f"{shot}-page")
    s.shot("#main-panel table", f"{shot}-summary")
    check(sec, f"guard: {who} opens the {what} page (200)" if want_status == 200 else
          f"guard: {who} is answered the {what} page with HTTP {want_status}", status == want_status, status=status)
    accepted = [expected] + ([either] if either else [])
    check(sec, f"D1 #18.4 title: the {what} page's <title>, app bar heading and last breadcrumb read "
          + " or ".join(f"'{x}'" for x in accepted) + f" ({who})",
          t[0] in accepted and list(t) == [t[0]] * 3 and p["title"] == t[0] + " - Jenkins",
          expected=accepted, shown=t, document_title=p["title"])
    # At the page's own URL core marks the last breadcrumb as the current page; a refusal is rendered at the POST URL
    # below it (…/reject), where core keeps that breadcrumb a link back to the request's page.
    own_url = want_status == 200
    check(sec, f"D1 #18.4 title: the id is in none of the {what} page's title, heading and breadcrumbs, the heading is "
          "the page's only h1 and the last breadcrumb is " + ("the current page" if own_url else "a link to the request's "
          "page") + f" ({who})", all(x and rid not in x for x in t) and not any(rid in c for c in p["crumbs"])
          and p["h1"] == [t[1]] and (p["last_current"] == "page" if own_url else (p["last_href"] or "").endswith(f"/{rid}/")),
          id=rid, shown=t, h1=p["h1"], breadcrumbs=p["crumbs"], last=[p["last_current"], p["last_href"]])
    # Core 2.568.3 renders the current page's breadcrumb as a <span> and gives it a `tooltip` (and `title`) with the
    # full text only when the text is long (27 characters and more were seen with one, 26 and fewer without) and the
    # breadcrumb, at most 224 px wide, shows it cut.
    tips = p["tips"]
    tooltip = [x["value"] for x in tips if x["attr"] == "tooltip"]
    if cut:
        check(sec, f"D1 #18.4 tooltip: the {what} page's last breadcrumb is shown cut and its tooltip carries the full "
              f"title unchanged, as does everything else it carries ({who})", tooltip == [t[0]] and t[0] in accepted
              and all(x["value"] == t[0] for x in tips), attributes=tips)
    else:
        check(sec, f"guard (tooltip): nothing the {what} page's last breadcrumb carries besides its text differs from "
              f"the title ({who}); a short title fits and gets no tooltip from core (here: {len(tooltip)})",
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
    crumb_texts = list(t) + list(p["crumbs"]) + [x["value"] for x in tips]
    if absent:
        check(sec, f"guard (T-UI-236/237): none of the {what} page's title, heading, breadcrumbs and tooltip holds "
              + " or ".join(f"'{x}'" for x in absent) + f" ({who})",
              not [x for x in crumb_texts for a in absent if x and a in x], shown=t, tooltips=[x["value"] for x in tips])
    if scope is not None:
        check(sec, f"D1 #18.4 (T-UI-236/237): the {what} page's title names the item its Scope row names for {who}: "
              f"'{scope}'", p["scope"] == scope and t[0] == expected and scope.startswith("Freestyle project ")
              and scope[len("Freestyle project "):].split(" (moved")[0] == t[0][len("Grant request: "):],
              scope_row=p["scope"], title=t[0])
    if raw_absent:
        page = f"/batch-control/{lib.KIND_URL[kind]}/{rid}/"
        served = {"page": api(who, page)}
        served.update({x: api(who, page + x) for x in ("contextMenu", "childrenContextMenu", "api/json")})
        html = s.page.content()
        found = {a: [k for k, v in served.items() if a in v.text] + (["rendered"] if a in html else []) for a in raw_absent}
        check(sec, f"guard (D-75 (1), T-UI-237): the HTML of {who}'s {what} page, as rendered and as served, and the "
              "answers of its contextMenu, childrenContextMenu and api/json hold none of "
              + ", ".join(f"'{x}'" for x in raw_absent), served["page"].status_code == 200 and len(html) > 2000
              and not any(found.values()), found=found, status={k: v.status_code for k, v in served.items()})
    if name:
        check(sec, f"guard (escaping): on the {what} page no attribute holds the name cut off at a quote and nothing is "
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
    check("V", "guard: every viewer gets the same title for the HOLD request", len(shown) == 1, titles=sorted(shown))


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


    # Guard: the boundary of the escaping checks. Markup never gets into a subject: core refuses such an item name and
    # the plugin refuses a window request for an item that does not exist (so no free text becomes a scope).
    count = """def d = new File(jenkins.model.Jenkins.get().rootDir, 'batch-control/requests/grant')
return groovy.json.JsonOutput.toJson([n: d.exists() ? d.listFiles().length : 0])"""
    before = lib.facts(count)["n"]
    hostile = ("<b>x</b>", "a&b", "<img src=x onerror=window.__r27=1>")
    made = {leaf: api("admin", f"{lib.jpath(FOLDER)}/createItem?name={quote(leaf, safe='')}", "POST",
                      data=lib.job_xml("fs", shell="echo e2e-27 D1").encode("utf-8"),
                      headers={"Content-Type": "application/xml"}).status_code for leaf in hostile}
    asked = {leaf: lib.submit_grant("requester", f"{FOLDER}/{leaf}", ["CONFIGURE"], reason="e2e-27 D1 markup scope")
             for leaf in hostile + ("no-such-item",)}
    after = lib.facts(count)["n"]
    exists = {leaf: api("admin", f"{lib.jpath(FOLDER + '/' + leaf)}/api/json").status_code for leaf in hostile}
    check("E", "guard (escaping): markup cannot become a subject: core refuses to create an item named with <, > or & "
          "(400, no item) and the plugin refuses a permission window request whose scope names no existing item (400, "
          "no request stored)", all(v == 400 for v in made.values()) and all(v == 404 for v in exists.values())
          and all(tuple(v) == (400, None) for v in asked.values()) and after == before, create=made, items=exists,
          window_requests={k: list(v) for k, v in asked.items()}, stored_before=before, stored_after=after)


# ---------------------------------------------------------------- F: a refusal re-rendered at the POST URL
def sec_F():
    cases = (("run", "run", f"Run request: {BATCH}", "run request"),
             ("activation", "act", f"Activation request: {ACT}", "activation request"))
    for i, (kind, key, expected, what) in enumerate(cases, 1):
        rid = S[key][1]
        s = Session("approver-1")
        s.go(f"/batch-control/{lib.KIND_URL[kind]}/{rid}/")
        form = s.page.locator("form[name=reject]")
        status = None
        if form.count():  # Reject without a comment: the plugin refuses and re-renders the page inside the POST
            with s.page.expect_navigation() as nav:
                form.locator("button[name=Submit], button[type=submit], input[type=submit]").first.click()
            s.page.wait_for_load_state("load")
            status = nav.value.status if nav.value else None
        url, text = s.page.url.replace(lib.BASE, ""), norm(s.text())
        judge("F", s, status, "approver-1", kind, rid, expected, f"refused rejection of the {what}",
              f"R27-D1-F-0{i}-{key}-request-rejection-refused", want_status=400)
        s.done()
        check("F", f"guard: the refusal of the {what}'s rejection is the request's own page at the POST URL …/reject, "
              "says 'Enter a rejection comment', and the request is still PENDING",
              url == f"/batch-control/{lib.KIND_URL[kind]}/{rid}/reject" and "Enter a rejection comment" in text
              and lib.stored(kind, rid).get("status") == "PENDING", url=url,
              state=lib.stored(kind, rid).get("status"), text=text[:300])


# ---------------------------------------------------------------- K: other kinds of subject
def sec_K():
    titled("K", "approver-1", "run", "run_pipe", f"Run request: {PIPE}", "run request (Pipeline job)",
           "R27-D1-K-01-run-request-pipeline")
    titled("K", "approver-1", "activation", "act_pipe", f"Activation request: {PIPE}", "activation request (Pipeline job)",
           "R27-D1-K-02-activation-request-pipeline")
    titled("K", "approver-1", "grant", "grant_mb", f"Grant request: {MB}", "grant request (CONFIGURE, multibranch project)",
           "R27-D1-K-03-grant-request-multibranch", cut=False)
    gone = api("requester", f"/batch-control/grants/{S['grant_mb'][1]}/cancel", "POST").status_code
    check("K", "arrangement: the requester cancelled the window request on team-mb (an item this unit does not own)",
          lib.stored("grant", S["grant_mb"][1]).get("status") == "CANCELLED", code=gone)


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
    S["flag"] = [set_flag(u, "false") for u in ("approver-1", "admin")]
    try:
        check("C", "arrangement: the new job page flag is off for approver-1 and admin (classic job pages)",
              S["flag"] == ["false", "false"], flag=S["flag"])
        titled("C", "approver-1", "run", "run", f"Run request: {BATCH}", "run request (classic flag)",
               "R27-D1-C-01-run-request-classic")
        titled("C", "approver-1", "grant", "grant", f"Grant request: {BATCH}", "grant request (classic flag)",
               "R27-D1-C-02-grant-request-classic")
        titled("C", "approver-1", "activation", "act", f"Activation request: {ACT}", "activation request (classic flag)",
               "R27-D1-C-03-activation-request-classic")
        titled("C", "approver-1", "activation", "hold", f"Hold request: {HOLD}", "hold request (classic flag)",
               "R27-D1-C-04-hold-request-classic", either=f"Activation request: {HOLD}")
        for path, tag, n in CONFIG_PAGES:
            s = revert_place("C", path, tag + "-classic", n, lib.strategy())
            if s is not None:
                s.done()
    finally:
        S["flag"] = [set_flag(u, "true") for u in ("approver-1", "admin")]
    check("C", "arrangement: the flag is on again for approver-1 and admin", S["flag"] == ["true", "true"], flag=S["flag"])


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
    leaf = lambda full: full.rsplit("/", 1)[1]  # noqa: E731
    in_vault = f"{VAULT}/{leaf(REN[2])}"
    removed = remove(in_vault, *REN, *PEND, *FOLD)
    vault = ensure_vault()
    xml = lib.job_xml("fs", shell="echo e2e-27 D1")
    for n in (REN[0], PEND[0]):
        lib.ensure_item(n, xml)
    lib.set_property(REN[0], approval=True)
    lib.ensure_folder(FOLD[0])
    lib.ensure_item(f"{FOLD[0]}/{FOLD_JOB}", xml)
    S["run_ren"] = lib.submit_run("requester", REN[0], "e2e-27 D1 renamed later")
    S["act_ren"] = lib.submit_activation("requester", REN[0], "ACTIVATE", "e2e-27 D1 renamed later")
    S["grant_ren"] = lib.submit_grant("requester", REN[0], ["CONFIGURE"], minutes=30, reason="e2e-27 D1 renamed later",
                                      approvers=("approver-1", "approver-disc"))
    S["grant_pend"] = lib.submit_grant("requester", PEND[0], ["CONFIGURE"], reason="e2e-27 D1 never approved, renamed")
    S["grant_fold"] = lib.submit_grant("requester", f"{FOLD[0]}/{FOLD_JOB}", ["CONFIGURE"], minutes=30,
                                       reason="e2e-27 D1 folder renamed later")
    gid, pid, fid = S["grant_ren"][1], S["grant_pend"][1], S["grant_fold"][1]
    approved = [lib.decide("approver-1", "grants", x, "approve", "e2e-27 D1") if x else None for x in (gid, fid)]
    check("X", "arrangement: approved CONFIGURE windows on r27-d1/ren-a (designated approvers approver-1 and approver-disc, "
          "who holds no Item/Read) and on r27-d1/fold-a/job, a PENDING window request on r27-d1/pend-a, a run and an ACTIVATE "
          "request on r27-d1/ren-a; the vault folder lets only administrators read",
          window_of(gid) == {"scope": REN[0], "open": True} and window_of(fid) == {"scope": f"{FOLD[0]}/{FOLD_JOB}", "open": True}
          and window_of(pid) == {} and lib.stored("grant", pid).get("status") == "PENDING"
          and may_read(REN[0], VIEWERS + ("approver-disc",)) == {**{u: True for u in VIEWERS}, "approver-disc": False},
          approved=approved, removed=removed, vault=vault, window=window_of(gid))
    reader = lambda name: "Freestyle project " + name  # noqa: E731
    elsewhere = reader(REN[0]) + MOVED
    titled("X", "requester", "grant", "grant_ren", f"Grant request: {REN[0]}", "window request before the rename",
           "R27-D1-X-01-window-before-rename", scope=reader(REN[0]))

    # ---- the first rename: the window follows; a pending request does not; a folder above the item counts as well
    done = {"ren": rename(REN[0], leaf(REN[1])), "pend": rename(PEND[0], leaf(PEND[1])), "fold": rename(FOLD[0], leaf(FOLD[1]))}
    state = {"window": window_of(gid), "folder_window": window_of(fid), "pending": lib.stored("grant", pid).get("status"),
             "pending_window": window_of(pid), "run": lib.stored("run", S["run_ren"][1]).get("status"),
             "activation": lib.stored("activation", S["act_ren"][1]).get("status"),
             "read": may_read(REN[1], VIEWERS + ("approver-disc",))}
    check("X", "arrangement: the administrator renamed ren-a to ren-b, pend-a to pend-b and the folder fold-a to fold-b: "
          "both windows are open and name the new full names, the pending request is still PENDING without a window, "
          "the run and ACTIVATE requests are INVALIDATED; approver-disc may not read ren-b, the other four may",
          state == {"window": {"scope": REN[1], "open": True}, "folder_window": {"scope": f"{FOLD[1]}/{FOLD_JOB}", "open": True},
                    "pending": "PENDING", "pending_window": {}, "run": "INVALIDATED", "activation": "INVALIDATED",
                    "read": {**{u: True for u in VIEWERS}, "approver-disc": False}}, codes=done, state=state)
    for i, who in enumerate(VIEWERS, 2):
        titled("X", who, "grant", "grant_ren", f"Grant request: {REN[1]}", "window whose item was renamed (a reader)",
               f"R27-D1-X-0{i}-window-renamed-{who}", absent=(REN[0],), scope=reader(REN[1]))
    titled("X", "approver-disc", "grant", "grant_ren", f"Grant request: {REN[0]}",
           "window whose item was renamed (a viewer who may not read the item)", "R27-D1-X-06-window-renamed-approver-disc",
           absent=(REN[1],), scope=elsewhere, raw_absent=("ren-b",))
    for i, who in enumerate(("requester", "approver-1"), 7):
        titled("X", who, "grant", "grant_pend", f"Grant request: {PEND[0]}", "never approved window request whose item was "
               "renamed", f"R27-D1-X-0{i}-pending-renamed-{who}", absent=(PEND[1],))
    for i, who in enumerate(("requester", "admin"), 9):
        titled("X", who, "grant", "grant_fold", f"Grant request: {FOLD[1]}/{FOLD_JOB}", "window on an item below a renamed "
               "folder", f"R27-D1-X-{i:02d}-window-folder-renamed-{who}", absent=(FOLD[0] + "/",),
               scope=reader(f"{FOLD[1]}/{FOLD_JOB}"))
    titled("X", "approver-1", "run", "run_ren", f"Run request: {REN[0]}", "run request (job renamed afterwards)",
           "R27-D1-X-11-run-request-renamed")
    titled("X", "approver-1", "activation", "act_ren", f"Activation request: {REN[0]}",
           "activation request (job renamed afterwards)", "R27-D1-X-12-activation-request-renamed")

    # ---- a second rename is followed
    done = rename(REN[1], leaf(REN[2]))
    check("X", "arrangement: the administrator renamed ren-b to ren-c; the window is open and names ren-c",
          window_of(gid) == {"scope": REN[2], "open": True}, code=done, window=window_of(gid))
    for i, who in enumerate(("requester", "approver-1", "admin"), 13):
        titled("X", who, "grant", "grant_ren", f"Grant request: {REN[2]}", "window whose item was renamed twice (a reader)",
               f"R27-D1-X-{i}-window-renamed-twice-{who}", absent=(REN[0], REN[1]), scope=reader(REN[2]))
    titled("X", "approver-disc", "grant", "grant_ren", f"Grant request: {REN[0]}",
           "window whose item was renamed twice (a viewer who may not read the item)",
           "R27-D1-X-16-window-renamed-twice-approver-disc", absent=(REN[1], REN[2]), scope=elsewhere,
           raw_absent=("ren-b", "ren-c"))

    # ---- moved to where only administrators read
    done = move(REN[2], VAULT)
    read = may_read(in_vault, VIEWERS + ("approver-disc",))
    check("X", "arrangement: the administrator moved ren-c into r27-d1-vault; the window is open and names it there; only "
          "admin may read it", window_of(gid) == {"scope": in_vault, "open": True}
          and read == {"requester": False, "approver-1": False, "manager": False, "admin": True, "approver-disc": False},
          code=done, window=window_of(gid), read=read)
    for i, who in enumerate(("requester", "approver-1", "manager", "approver-disc"), 17):
        titled("X", who, "grant", "grant_ren", f"Grant request: {REN[0]}",
               "window whose item was moved out of the viewer's sight", f"R27-D1-X-{i}-window-moved-{who}",
               absent=(VAULT, REN[2]), scope=elsewhere,
               raw_absent=(VAULT,) + (("ren-b", "ren-c") if who == "approver-disc" else ()))
    titled("X", "admin", "grant", "grant_ren", f"Grant request: {in_vault}", "window whose item was moved (administrator)",
           "R27-D1-X-21-window-moved-admin", absent=(FOLDER + "/ren-",), scope=reader(in_vault))


# ---------------------------------------------------------------- S: requests that ran or expired
def sec_S():
    ran = lib.wait_until(lambda: lib.stored("run", S["run_hold"][1]).get("status") == "EXECUTED", timeout=120, step=3)
    exp = {"run": S["run_exp"][1], "grant": S["grant_exp"][1], "activation": S["act_exp"][1]}
    lib.wait_until(lambda: all(lib.stored(k, v).get("status") == "EXPIRED" for k, v in exp.items()), timeout=180, step=5)
    state = {k: lib.stored(k, v).get("status") for k, v in exp.items()}
    check("S", "arrangement: the approved run request on the activated job ran (EXECUTED); the run, window and ACTIVATE "
          "requests on r27-d1/exp, made two hours old in the store, were expired by the plugin's periodic work "
          "(pendingTimeoutHours is 1, its minimum)", bool(ran) and state == {k: "EXPIRED" for k in exp},
          approve=S.get("ran"), backdated=S.get("backdated"), executed=lib.stored("run", S["run_hold"][1]).get("status"),
          expired=state)
    titled("S", "requester", "run", "run_hold", f"Run request: {HOLD}", "executed run request",
           "R27-D1-S-01-run-request-executed")
    titled("S", "requester", "run", "run_exp", f"Run request: {EXP}", "expired run request",
           "R27-D1-S-02-run-request-expired")
    titled("S", "approver-1", "grant", "grant_exp", f"Grant request: {EXP}", "expired grant request",
           "R27-D1-S-03-grant-request-expired")
    titled("S", "requester", "activation", "act_exp", f"Activation request: {EXP}", "expired activation request",
           "R27-D1-S-04-activation-request-expired")


# ---------------------------------------------------------------- H: plain HTTP, not a secure context
INSECURE_JS = """() => { const th = [...document.querySelectorAll('#main-panel table tr > th')].find(t => t.textContent.trim() === 'ID');
  const td = th ? th.parentElement.querySelector('td') : null; const b = td ? td.querySelector('button.jenkins-copy-button') : null;
  return {secure: window.isSecureContext, title: document.title, row: !!th, code: td && td.querySelector('code') ? td.querySelector('code').textContent.trim() : null,
    button: !!b, disabled: b ? b.disabled : null, button_tooltip: b ? b.getAttribute('tooltip') : null,
    why: b ? b.parentElement.getAttribute('tooltip') : null}; }"""
INSECURE_WHY = "Copy is only supported with a secure (HTTPS) connection."


def sec_H():
    host, alias = urlsplit(lib.BASE).hostname, "r27-plain-http.test"
    if host not in ("localhost", "127.0.0.1"):
        note("H", "skipped: BC_BASE is not on this machine, so the alias host cannot be mapped to it", base=lib.BASE)
        return
    base = lib.BASE.replace(f"//{host}", f"//{alias}", 1)
    rid = S["run"][1]
    lib._r6.browser()  # starts Playwright; the second browser resolves the alias to this machine
    channel = os.environ.get("BC_BROWSER_CHANNEL", "chrome")
    b = lib._r6._pw.chromium.launch(channel=None if channel in ("", "chromium") else channel,
                                    headless=os.environ.get("BC_HEADED") != "1",
                                    args=[f"--host-resolver-rules=MAP {alias} 127.0.0.1"])
    try:
        ctx = b.new_context(viewport={"width": 1280, "height": 900}, locale="en-US")
        p = ctx.new_page()
        p.set_default_timeout(20000)
        p.goto(base + "/login")
        p.fill("#j_username", "approver-1")
        p.fill('input[name="j_password"]', lib.pw("approver-1"))
        p.click('button[name="Submit"], button[type="submit"]')
        p.wait_for_load_state("load")
        r = p.goto(base + f"/batch-control/requests/{rid}/")
        p.wait_for_load_state("load")
        st = p.evaluate(INSECURE_JS)
        p.screenshot(path=str(lib.SHOTS / "R27-D1-H-01-run-request-plain-http.png"))
        status = r.status if r else None
    finally:
        b.close()
    check("H", "D1 #18.4 ID row over plain HTTP on another host name (not a secure context): approver-1's run request page "
          "still shows the full id as text in the ID row; core disables the copy button and its tooltip says why",
          status == 200 and st["secure"] is False and st["title"] == f"Run request: {BATCH} - Jenkins" and st["code"] == rid
          and st["button"] and st["disabled"] is True and st["why"] == INSECURE_WHY, status=status, page=st, base=base)


# ---------------------------------------------------------------- R, P: the revert entry
STATE_JS = """(sel) => { const fieldSel = 'input[name^="_."], select[name^="_."], textarea[name^="_."]';
  const sec = document.querySelector('[name="_.runControlEnabled"]')?.closest('section') || null;
  const ctl = [...document.querySelectorAll(sel)];
  const vis = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
  const probe = host => { const p = document.createElement('span'); p.setAttribute('style', 'color: var(--destructive-color)');
    p.textContent = 'probe'; host.appendChild(p); const c = getComputedStyle(p).color; p.remove(); return c; };
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
        color: getComputedStyle(e).color, probe: probe(e.parentElement), around: getComputedStyle(e.parentElement).color,
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
    check(sec, f"guard (#18.7 keeps it last): {path}: the revert entry is the last entry of the Batch Control section "
          f"(none of its {after['fields']} fields follows it)", ctl.get("fieldsAfter") == [] and after["fields"] >= 10,
          fields_after=ctl.get("fieldsAfter"), chain=ctl.get("chain"))
    check(sec, f"guard: {path}: the revert entry keeps the destructive colour: the class jenkins-!-destructive-color "
          "and, shown, the computed colour of var(--destructive-color), which is not the colour of the text around it",
          bool(ctl.get("destructive")) and ctl.get("color") == ctl.get("probe") and ctl.get("probe") != ctl.get("around"),
          text=ctl.get("text"), color=ctl.get("color"), probe=ctl.get("probe"), around=ctl.get("around"))
    return s


def revert_through(sec, s, path, tag, n, plain):
    """Guard: the entry, pressed where it now is, still reverts. Cancel keeps the strategy; OK posts once to the
    unchanged endpoint and installs `plain` with every entry kept; the page then offers no revert. Closes `s`."""
    before, kept = lib.strategy(), entries()
    posts = []
    s.page.on("response", lambda r: posts.append((r.status, r.url)) if r.request.method == "POST" else None)
    ctl = s.page.locator(REVERT_SEL).filter(visible=True).first
    ctl.click()
    esc = lib.opened(s.page)
    closed = False
    if esc:
        s.page.keyboard.press("Escape")
        closed = lib.gone(s.page)
    check(sec, f"guard: {path}: Escape closes the revert confirmation, posts nothing and keeps {before}",
          bool(esc) and closed and not posts and lib.strategy() == before, opened=esc, closed=closed, posts=list(posts),
          strategy=lib.strategy())
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


HOLDER_JS = """(sentence) => { const n = t => (t || '').replace(/\\s+/g, ' ').trim();
  const vis = e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length) && getComputedStyle(e).visibility !== 'hidden';
  const sec = document.querySelector('[name="_.runControlEnabled"]')?.closest('section') || null;
  const holds = [...document.querySelectorAll('#main-panel *')].filter(e => n(e.textContent).includes(sentence));
  const inner = holds.filter(e => !holds.some(o => o !== e && e.contains(o)));
  return {section: !!sec, sentence: inner.map(e => ({text: n(e.textContent), displayed: vis(e), inSection: !!(sec && sec.contains(e)),
      inAdvancedBody: !!e.closest('.advancedBody')})),
    advancedButtons: sec ? sec.querySelectorAll('button.advanced-button, button.advancedButton').length : null,
    advancedBodies: sec ? sec.querySelectorAll('.advancedBody').length : null,
    fields: sec ? sec.querySelectorAll('[name^="_."]').length : 0}; }"""


def told_without_advanced(sec, who, path, shot, what):
    """T-UI-239 for a viewer who is no administrator and is shown the Batch Control section on `path`: the sentence
    naming whom to ask is displayed as the page loads, in the section, outside any Advanced body; the section has no
    Advanced control; nothing of the revert is rendered. Nothing is pressed."""
    s = Session(who)
    r = s.go(path)
    h = s.page.evaluate(HOLDER_JS, ASK_ADMIN)
    st = s.page.evaluate(STATE_JS, REVERT_SEL)
    html = s.page.content()
    end_shot(s, shot)
    s.done()
    one = h["sentence"][0] if len(h["sentence"]) == 1 else {}
    check(sec, f"guard (T-UI-239): {what} opens {path} (200) and reads '{ASK_ADMIN}' as the page loads, nothing pressed: "
          "displayed, in the Batch Control section, not inside div.advancedBody; the section has no Advanced button and "
          "no Advanced body", r is not None and r.status == 200 and h["section"] and one.get("text") == ASK_ADMIN
          and one.get("displayed") is True and one.get("inSection") is True and one.get("inAdvancedBody") is False
          and h["advancedButtons"] == 0 and h["advancedBodies"] == 0, status=r.status if r else None, page=h)
    check(sec, f"guard: {what} is offered no revert on {path}, not even hidden: no control in the DOM, neither its URL "
          "nor its caption in the HTML", r is not None and r.status == 200 and not st["controls"] and REVERT not in html
          and REVERT_TEXT not in html, controls=st["controls"])


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
    told_without_advanced("R", "manager", CONFIG_PAGES[1][0], "R27-D1-R-41-manager-bc-config",
                          "the BatchControl/Manage holder (manager)")
    r2 = api("manager", CONFIG_PAGES[0][0])
    check("R", "guard: the manager cannot open Manage Jenkins > System (403) and its page names no revert",
          r2.status_code == 403 and REVERT not in r2.text and REVERT_TEXT not in r2.text, status=r2.status_code)
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
    # the endpoint itself, without a browser: the administrator's POST with a crumb
    kept = entries()
    r = api("admin", "/manage/" + REVERT, "POST")
    after, after_entries = lib.strategy(), entries()
    restored = lib.restore_strategy()
    check("R", "guard: the administrator's own POST of the revert endpoint with a crumb (REST, no browser) is answered "
          "below 400 and installs the plain ProjectMatrixAuthorizationStrategy with every entry kept; the Batch Control "
          "strategy is then restored through migrate", r.status_code < 400 and after == "ProjectMatrixAuthorizationStrategy"
          and after_entries == kept and restored[1] == matrix and entries() == kept, status=r.status_code, after=after,
          restored=restored)


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
        told_without_advanced("P", "manager", CONFIG_PAGES[1][0], "R27-D1-P-41-manager-bc-config-role",
                              "under the role strategy the holder of a role with BatchControl/Manage (manager)")
        post = refused("manager")
        check("P", "guard: under the role strategy the manager's POST of the revert answers 403 and the role strategy "
              "stays", post == 403 and lib.strategy() == role, post=post, strategy=lib.strategy())
        for path, tag, n in CONFIG_PAGES:  # pressed from each page; the Batch Control role strategy re-installed between
            s = revert_place("P", path, tag + "-role", n, role)
            if s is None:
                continue
            kept = revert_through("P", s, path, tag + "-role", n, "RoleBasedAuthorizationStrategy")
            again = lib.restore_strategy()
            check("P", "arrangement: the Batch Control role strategy installed again through the monitor's migrate "
                  "endpoint, every role kept", again[1] == role and entries() == kept, restored=again)
    finally:
        back = role_profile(False)
    check("P", "arrangement: the saved matrix strategy is installed again with its entries", back == matrix
          and entries() == matrix_entries, restored=back, entries=entries(), before=matrix_entries)


def cleanup():
    note("cleanup", "restore", saved_strategy=role_profile(False), strategy=lib.restore_strategy(),
         flag=[set_flag(u, "true") for u in ("approver-1", "admin")], swept=lib.sweep("requester", FOLDER),
         team_mb_request=api("requester", f"/batch-control/grants/{S['grant_mb'][1]}/cancel", "POST").status_code
         if S.get("grant_mb", (0, None))[1] and lib.stored("grant", S["grant_mb"][1]).get("status") == "PENDING" else None)


if __name__ == "__main__":  # r27/title_restart.py and r27/revert_permissions.py import this file for its helpers
    lib.run(sys.argv, {"A": sec_A, "T": sec_T, "G": sec_G, "V": sec_V, "E": sec_E, "F": sec_F, "K": sec_K, "L": sec_L,
                       "N": sec_N, "C": sec_C, "D": sec_D, "X": sec_X, "S": sec_S, "H": sec_H, "R": sec_R, "P": sec_P},
            cleanup)
