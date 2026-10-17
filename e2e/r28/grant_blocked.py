"""e2e-28 #44: a user who may not request a permission window cannot make the plugin write GRANT_REQUEST_BLOCKED
records (TEST-MATRIX T-08-260/261, note 351). With change control off, POST batch-control/grants/create checks
BatchControl/RequestGrant first (Manage implies it): an Approve-only user is denied (403) and nothing is written; a
RequestGrant or Manage holder still gets the change-control refusal and its one record.

usage: python grant_blocked.py [AOGXN]   rows: r27/out/grant_blocked.jsonl, shots: screenshots/run-27/R28-44-*.png
Accounts (JCasC): approver-unlisted (Overall/Read, Job/Read, Approve only: the user of #44), requester (RequestGrant),
manager (BatchControl/Manage), auditor (ViewHistory: reads History > Changes and changes.csv). The item is r28-gb (a
freestyle job, created again by A). Records are read from the store (batch-control/changes/*.jsonl) and from the
auditor's changes.csv; "nothing written" means no change record and no grant request file after the request.
A check named "#44" fails without the fix; one named "guard" holds with and without it.

A  arrangement: r28-gb; change control off (the setting is put back at the end).
O  #44 approver-unlisted with change control off: the Grants page answers and offers no way to request a window (NOTE);
   a crafted POST to grants/create with a valid crumb answers 403; no GRANT_REQUEST_BLOCKED record, no record at all and
   no grant request is written; the auditor's History > Changes and changes.csv list nothing for it.
G  guards, change control off: requester and manager each get the change-control refusal (a 4xx that is not 403, the
   page saying change control is off) and exactly one GRANT_REQUEST_BLOCKED record naming them, nothing stored; the
   auditor's changes.csv and History > Changes list those records.
X  guards: an anonymous POST, approver-unlisted's POST without the crumb, and a GET of grants/create are refused (4xx)
   and write nothing.
N  change control on: approver-unlisted still gets 403 and nothing is written (T-08-261, green before the fix: guard);
   requester's request is accepted, exactly one grant request stored and no GRANT_REQUEST_BLOCKED record (guard); the
   request is cancelled.
cleanup: change control as it was; r28-gb deleted; the requester's pending r28 requests cancelled."""
import csv
import io
import json
import re
import sys

import requests

sys.path.insert(0, __file__.rsplit("/", 2)[0] + "/r27")
import lib  # noqa: E402
from lib import api, check, note, Session, gv  # noqa: E402

lib.LOGNAME[0] = "grant_blocked"
JOB = "r28-gb"
ONLY_APPROVE, REQUESTER, MANAGER, AUDITOR = "approver-unlisted", "requester", "manager", "auditor"
S = {}


def now_ms():
    return int(gv("return System.currentTimeMillis()"))


def written_since(mark):
    """What the store gained since `mark`: change records (type, user, target) and grant request files."""
    return lib.facts(f"""def root = new File(jenkins.model.Jenkins.get().rootDir, 'batch-control'); def recs = []
(new File(root, 'changes').listFiles() ?: []).findAll {{ it.name.endsWith('.jsonl') }}.each {{ it.eachLine('UTF-8') {{ l ->
  def m = new groovy.json.JsonSlurper().parseText(l); if ((m.at as long) >= {mark}L) recs << [type: m.type, user: m.user, target: m.target, detail: m.detail] }} }}
def reqs = (new File(root, 'requests/grant').listFiles() ?: []).findAll {{ it.name.endsWith('.xml') && it.lastModified() >= {mark}L }}.collect {{ it.name }}
return groovy.json.JsonOutput.toJson([records: recs, requests: reqs])""")


def blocked_csv():
    """GRANT_REQUEST_BLOCKED rows of the auditor's changes.csv: (user, target)."""
    r = api(AUDITOR, "/batch-control/history/changes.csv")
    return [(x.get("user"), x.get("target")) for x in csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")))
            if x.get("type") == "GRANT_REQUEST_BLOCKED"]


def history_blocked():
    """The rows of the auditor's History > Changes page that show GRANT_REQUEST_BLOCKED (their text)."""
    s = Session(AUDITOR)
    s.go(f"/batch-control/history/?kind=changes&job={JOB}")
    rows = [re.sub(r"\s+", " ", t) for t in s.page.locator("#main-panel table tbody tr").all_inner_texts()
            if "GRANT_REQUEST_BLOCKED" in t or "blocked" in t.lower()]
    s.shot("#main-panel", "R28-44-auditor-history-changes")
    s.done()
    return rows


def ask(user, crumb=True):
    data = [("scopeFullName", JOB), ("durationMinutes", "15"), ("reason", f"e2e-28 #44 {user}"), ("actions", "CONFIGURE"),
            ("approvers", "approver-1")]
    return api(user, "/batch-control/grants/create", "POST", data=data, crumb=crumb)


def set_change_control(on):
    return lib.gv(lib.L25.CFG + f"cfg.setChangeControlEnabled({str(on).lower()}); cfg.save(); return String.valueOf(cfg.changeControlEnabled)")


def sec_A():
    S["change"] = lib.gv(lib.L25.CFG + "return String.valueOf(cfg.changeControlEnabled)") == "true"
    if api("admin", lib.jpath(JOB) + "/api/json").status_code == 200:
        api("admin", lib.jpath(JOB) + "/doDelete", "POST")
    made = lib.ensure_item(JOB, lib.job_xml("fs", shell="echo e2e-28 #44"))
    off = set_change_control(False)
    perms = lib.facts("""def j = jenkins.model.Jenkins.get(); def p = io.jenkins.plugins.batchcontrol.security.BatchControlPermissions
def a = { u -> hudson.model.User.getById(u, false).impersonate2() }
return groovy.json.JsonOutput.toJson(['approver-unlisted', 'requester', 'manager'].collectEntries { u ->
  [(u): [approve: j.getACL().hasPermission2(a(u), p.APPROVE), requestGrant: j.getACL().hasPermission2(a(u), p.REQUEST_GRANT)]] })""")
    check("A", "arrangement: r28-gb created; change control off; approver-unlisted holds Approve but not RequestGrant, "
          "requester holds RequestGrant, manager (BatchControl/Manage) implies it", made is not None and off == "false"
          and perms[ONLY_APPROVE] == {"approve": True, "requestGrant": False} and perms[REQUESTER]["requestGrant"]
          and perms[MANAGER]["requestGrant"], change_control_before=S["change"], perms=perms)


def sec_O():
    s = Session(ONLY_APPROVE)
    r = s.go("/batch-control/grants/")
    offers = [re.sub(r"\s+", " ", t) for t in s.page.locator("#main-panel a, #main-panel button").all_inner_texts()
              if re.search(r"(?i)request|new", t)]
    lib.page_shot(s, "R28-44-O-grants-page-approver-unlisted")
    s.done()
    note("O", "what the Grants page offers approver-unlisted with change control off", status=r.status if r else None,
         controls=offers)
    csv_before = blocked_csv()
    mark = now_ms()
    resp = ask(ONLY_APPROVE)
    w = written_since(mark)
    csv_after = blocked_csv()
    check("O", "#44: approver-unlisted (Approve only) posting a well-formed window request to grants/create with a valid "
          "crumb, change control off, is answered 403", resp.status_code == 403, status=resp.status_code,
          text=lib.text_of(resp.text)[:200])
    check("O", "#44: that request writes nothing: no GRANT_REQUEST_BLOCKED record, no change record at all, no grant "
          "request (store)", not w["records"] and not w["requests"], written=w)
    hist = history_blocked()
    check("O", "#44: the auditor's changes.csv and History > Changes list no GRANT_REQUEST_BLOCKED record for "
          "approver-unlisted", csv_after == csv_before and not any(u == ONLY_APPROVE for u, _ in csv_after)
          and not any(ONLY_APPROVE in t for t in hist), csv_new=csv_after[len(csv_before):], history=hist[:3])


def sec_G():
    for who in (REQUESTER, MANAGER):
        before = blocked_csv()
        mark = now_ms()
        resp = ask(who)
        w = written_since(mark)
        text = lib.text_of(resp.text)
        recs = [x for x in w["records"] if x["type"] == "GRANT_REQUEST_BLOCKED"]
        check("G", f"guard: {who} posting the same request with change control off gets the change-control refusal (a 4xx "
              "that is not 403, the page saying change control is off) and exactly one GRANT_REQUEST_BLOCKED record naming "
              f"{who}, and no grant request is stored", 400 <= resp.status_code < 500 and resp.status_code != 403
              and re.search(r"(?i)change control", text) is not None and len(recs) == 1 and recs[0]["user"] == who
              and len(w["records"]) == 1 and not w["requests"], status=resp.status_code, text=text[:240], written=w)
        after = blocked_csv()
        check("G", f"guard: the auditor's changes.csv lists that one new record for {who}",
              after[len(before):] == [(who, JOB)] or (len(after) == len(before) + 1 and (who, JOB) in after),
              new=after[len(before):])
    hist = history_blocked()
    check("G", "guard: the auditor's History > Changes shows the records of requester and manager",
          any(REQUESTER in t for t in hist) and any(MANAGER in t for t in hist), rows=hist[:4])


def sec_X():
    mark = now_ms()
    anon = requests.post(lib.BASE + "/batch-control/grants/create", data={"scopeFullName": JOB, "durationMinutes": "15",
                                                                          "reason": "anonymous", "actions": "CONFIGURE"})
    nocrumb = ask(ONLY_APPROVE, crumb=False).status_code
    get = api(ONLY_APPROVE, "/batch-control/grants/create").status_code
    w = written_since(mark)
    check("X", "guard: an anonymous POST, approver-unlisted's POST without the crumb and a GET of grants/create are refused "
          "(4xx) and write nothing", 400 <= anon.status_code < 500 and 400 <= nocrumb < 500 and 400 <= get < 500
          and not w["records"] and not w["requests"], anonymous=anon.status_code, no_crumb=nocrumb, get=get, written=w)


def sec_N():
    on = set_change_control(True)
    mark = now_ms()
    a = ask(ONLY_APPROVE)
    w1 = written_since(mark)
    check("N", "guard (T-08-261): with change control on, approver-unlisted is answered 403 and nothing is written",
          on == "true" and a.status_code == 403 and not w1["records"] and not w1["requests"], status=a.status_code, written=w1)
    mark = now_ms()
    st, rid = lib.submit_grant(REQUESTER, JOB, ["CONFIGURE"], reason="e2e-28 #44 change control on")
    w2 = written_since(mark)
    check("N", "guard: with change control on, requester's request is accepted: exactly one grant request stored, no "
          "GRANT_REQUEST_BLOCKED record", st in (200, 302) and rid is not None and len(w2["requests"]) == 1
          and not [x for x in w2["records"] if x["type"] == "GRANT_REQUEST_BLOCKED"], status=st, id=rid, written=w2)
    S["cancel"] = api(REQUESTER, f"/batch-control/grants/{rid}/cancel", "POST").status_code if rid else None


def cleanup():
    back = set_change_control(S.get("change", True))
    note("cleanup", "restore", change_control=back, cancelled=S.get("cancel"), swept=lib.sweep(REQUESTER, "r28-"),
         deleted=api("admin", lib.jpath(JOB) + "/doDelete", "POST").status_code)


if __name__ == "__main__":
    lib.run(sys.argv, {"A": sec_A, "O": sec_O, "G": sec_G, "X": sec_X, "N": sec_N}, cleanup)
