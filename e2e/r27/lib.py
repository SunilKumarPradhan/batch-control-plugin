"""e2e-27: CI units for the UI groups of Wave D, one driver per group, on top of ../r25/lib.py:

    D1 titles_revert.py     #18.4 request pages titled by their subject with an ID row; #18.7 revert inside Advanced
    D2 labels_filters.py    #18.3 History filter dropdowns; #18.2 readable status and cause labels
    D3 decision_tables.py   #18.5 one Decision area right after Parameters; #6/#18.1 the 7-column run tables
    D4 admin_checks.py      #7 (D-86) the "Administrator checks" section on the overview

Screenshots in screenshots/run-27/ (never committed; the browser viewport is 1280 px wide, r6/lib.py), rows in
r27/out/<driver>.jsonl. The rules of every e2e pass hold: one new browser context per page and account (real login
form), the server state read separately (REST with basic auth; the script console only arranges or reads state, never
performs the behaviour under test). Each driver arranges its own items (named r27-*) idempotently in its first section,
sweeps what an earlier pass left pending, and restores what it changes globally, so it can be rerun on the same Jenkins.
Verdict lines as in r16..r25: "PASS {...}" / "FAIL {...}" per assertion (ci/shard.py fails a step on a FAIL line or a
non-zero exit), "NOTE {...}" for an observation without a verdict. Every check names the contract item it verifies
(docs: the Wave D contract, groups D1..D4) or says "guard:" for a case that already works and must keep working.

The server state never depends on a screen label: request states are read from the store (stored()), not from the
request page's Status row, whose text Wave D D2 changes.

This file is shared by the four drivers and kept identical on every branch that adds one."""
import importlib.util
import json
import re
from urllib.parse import quote

HERE = __import__("pathlib").Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("r25lib", HERE.parent / "r25" / "lib.py")
L25 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(L25)
# r25/lib.py points the shared libraries at run-25 and r25/out; this pass writes its own.
for _m in (L25.L19._r6, L25.L19._l):
    _m.SHOTS = HERE.parent / "screenshots" / "run-27"
    _m.OUT = HERE / "out"
L25.L19._r6.SHOTS.mkdir(parents=True, exist_ok=True)
L25.L19._r6.OUT.mkdir(parents=True, exist_ok=True)
SHOTS, OUT = L25.L19._r6.SHOTS, L25.L19._r6.OUT

Session, close, api, gv, ENV, BASE, pw = L25.Session, L25.close, L25.api, L25.gv, L25.ENV, L25.BASE, L25.pw
check, note, text_of, J, decide, loc_id, facts, Poster = (L25.check, L25.note, L25.text_of, L25.J, L25.decide,
                                                          L25.loc_id, L25.facts, L25.Poster)
job_xml, set_property, wait_until, wait_build, next_build, string_p = (L25.job_xml, L25.set_property, L25.wait_until,
                                                                       L25.wait_build, L25.next_build, L25.string_p)
activation, builds, run = L25.activation, L25.builds, L25.run
UUID, LOGNAME, PREFIX, ORIGIN, BC = L25.UUID, L25.LOGNAME, L25.PREFIX, L25.ORIGIN, L25.BC
_r6 = L25.L19._r6
opened, gone, react = _r6.opened, _r6.gone, _r6.react
STRATEGY_MONITOR = "batch-control-strategy"
CWG_MONITOR = BC + ".ops.ConfigureWithoutGrantMonitor"
STORE_DIRS = {"run": "requests/run", "grant": "requests/grant", "activation": "activation-requests"}
KIND_URL = {"run": "requests", "grant": "grants", "activation": "activations"}


def jpath(full):
    """/job/a/job/b for the full name a/b, each segment URL-encoded (names with quotes, braces or spaces)."""
    return "".join(f"/job/{quote(p, safe='')}" for p in full.split("/"))


def ensure_folder(full):
    """Arrangement (script console): the folder `full` (one level under the root or an existing folder)."""
    return gv("""def j = jenkins.model.Jenkins.get(); def n = """ + json.dumps(full) + """
if (j.getItemByFullName(n) != null) return 'exists'
def i = n.lastIndexOf('/'); def parent = i < 0 ? j : j.getItemByFullName(n.substring(0, i))
parent.createProject(com.cloudbees.hudson.plugins.folder.Folder, n.substring(i + 1)); return 'created'""")


def ensure_item(full, xml):
    """Creates the job `full` from `xml` when it does not exist (REST createItem, names URL-encoded). True when created."""
    parent, _, leaf = full.rpartition("/")
    if api("admin", jpath(full) + "/api/json").status_code == 200:
        return False
    r = api("admin", (jpath(parent) if parent else "") + f"/createItem?name={quote(leaf, safe='')}", "POST",
            data=xml.encode("utf-8"), headers={"Content-Type": "application/xml"})
    assert r.status_code == 200, (full, r.status_code, text_of(r.text)[:300])
    return True


def submit_run(user, job, reason, approvers=("approver-1",), params=None):
    """A run request through the plugin's own POST endpoint (json form, as the browser form posts it).
    Returns (HTTP status, request id or None)."""
    body = {"reason": reason, "approvers": list(approvers),
            "parameter": [{"name": k, "value": v} for k, v in (params or {}).items()]}
    r = api(user, jpath(job) + "/batch-control/submit", "POST", data={"json": json.dumps(body)})
    return r.status_code, loc_id(r)


def submit_activation(user, job, action, reason, approvers=("approver-1",)):
    data = [("action", action), ("reason", reason)] + [("approvers", a) for a in approvers]
    r = api(user, jpath(job) + "/batch-control-activation/submit", "POST", data=data)
    return r.status_code, loc_id(r)


def submit_grant(user, scope, actions, minutes=15, reason="e2e-27", approvers=("approver-1",)):
    data = [("scopeFullName", scope), ("durationMinutes", str(minutes)), ("reason", reason)]
    data += [("actions", a) for a in actions] + [("approvers", a) for a in approvers]
    r = api(user, "/batch-control/grants/create", "POST", data=data)
    return r.status_code, loc_id(r)


def stored(kind, rid):
    """The stored request (kind run | grant | activation) as {status, decidedBy, decisionComment, ...} read from its
    XML file in the store (server state; independent of any screen label). {} when there is no such file."""
    return facts("""def f = new File(jenkins.model.Jenkins.get().rootDir, 'batch-control/""" + STORE_DIRS[kind] + "/"
                 + rid + """.xml')
if (!f.exists()) return '{}'
def x = new XmlSlurper().parse(f)
return groovy.json.JsonOutput.toJson([status: x.status.text(), decidedBy: x.decidedBy.text(),
  decisionComment: x.decisionComment.text(), requester: x.requester.text(), job: x.jobFullName.text(),
  scope: x.scope.fullName.text()])""")


def strategy():
    """The simple class name of the installed authorization strategy (server state)."""
    return gv("return jenkins.model.Jenkins.get().getAuthorizationStrategy().getClass().simpleName")


def monitors():
    """{id: {enabled, activated}} of the two Batch Control monitors of D-86 (server state)."""
    return facts("""def j = jenkins.model.Jenkins.get(); def out = [:]
['""" + STRATEGY_MONITOR + "', '" + CWG_MONITOR + """'].each { id -> def m = j.getAdministrativeMonitor(id)
  out[id] = m == null ? null : [enabled: m.isEnabled(), activated: m.isActivated()] }
return groovy.json.JsonOutput.toJson(out)""")


def enable_monitors():
    """Restores: re-enables every Batch Control administrative monitor a driver dismissed (as ci/arrange_ci.py)."""
    return gv("""def out = []
jenkins.model.Jenkins.get().administrativeMonitors.findAll { it.class.name.startsWith('""" + BC + """.') }.each { m ->
  if (!m.isEnabled()) { m.disable(false); out << m.id + ' re-enabled' } }
return out.join(',')""")


def restore_strategy():
    """Restores the Batch Control matrix strategy with the monitor's own migrate endpoint (admin, crumbed POST) when a
    driver left the plain strategy installed. Returns (before, after)."""
    before = strategy()
    if not before.startswith("BatchControl"):
        api("admin", f"/manage/administrativeMonitor/{STRATEGY_MONITOR}/migrate", "POST")
    return before, strategy()


def sweep(user, prefix):
    """Cancels `user`'s PENDING run, activation and grant requests on items whose full name starts with `prefix`,
    revokes `user`'s active windows on them and cancels their queue items. Returns the counts."""
    rows = facts("""def root = new File(jenkins.model.Jenkins.get().rootDir, 'batch-control')
def now = System.currentTimeMillis(); def p = """ + json.dumps(prefix) + """
def out = [run: [], activation: [], grant: [], window: []]
[['requests/run', 'run'], ['activation-requests', 'activation'], ['requests/grant', 'grant']].each { d, k ->
  def f = new File(root, d); if (f.exists()) f.listFiles().findAll { it.name ==~ /[0-9a-f-]{36}\\.xml/ }.each { x ->
    def r = new XmlSlurper().parse(x); def name = k == 'grant' ? r.scope.fullName.text() : r.jobFullName.text()
    if (r.requester.text() == """ + json.dumps(user) + """ && r.status.text() == 'PENDING' && name.startsWith(p)) out[k] << r.id.text() } }
def g = new File(root, 'grants'); if (g.exists()) g.listFiles().findAll { it.name.endsWith('.xml') }.each { x ->
  def r = new XmlSlurper().parse(x)
  if (r.user.text() == """ + json.dumps(user) + """ && r.scope.fullName.text().startsWith(p) && r.revokedAtMillis.text() == ''
      && ((r.expiresAtMillis.text() ?: '0') as long) > now) out.window << r.id.text() }
return groovy.json.JsonOutput.toJson(out)""")
    done = {}
    for k, ids in rows.items():
        if k == "window":
            done[k] = [api("admin", f"/batch-control/grants/{i}/revoke", "POST").status_code for i in ids]
        else:
            done[k] = [api(user, f"/batch-control/{KIND_URL[k]}/{i}/cancel", "POST").status_code for i in ids]
    q = api("admin", "/queue/api/json?tree=items[id,task[url]]")
    items = [i["id"] for i in (q.json().get("items", []) if q.status_code == 200 else [])
             if jpath(prefix) in ((i.get("task") or {}).get("url") or "")]
    done["queue"] = [api("admin", f"/queue/cancelItem?id={i}", "POST").status_code for i in items]
    return {k: len(v) for k, v in done.items()}


def page_shot(s, name):
    """A full-page screenshot of the 1280 px wide viewport (what the owner looks at), next to the clipped ones."""
    f = SHOTS / f"{name}.png"
    s.page.screenshot(path=str(f), full_page=True)
    return f.name


def titles(page):
    """(document title without core's " - Jenkins", the app bar heading, the last breadcrumb's text)."""
    t = page.title().strip()
    t = t[: -len(" - Jenkins")] if t.endswith(" - Jenkins") else t
    h1 = page.locator("#main-panel h1").first
    crumbs = page.locator(".jenkins-breadcrumbs__list-item")
    last = crumbs.nth(crumbs.count() - 1) if crumbs.count() else None
    return (t, re.sub(r"\s+", " ", h1.inner_text()).strip() if h1.count() else None,
            re.sub(r"\s+", " ", last.inner_text()).strip() if last is not None else None)


def norm(text):
    return re.sub(r"\s+", " ", text or "").strip()
