"""e2e-28 #1 follow-ups (security-31/32 LOW items, usability; TEST-MATRIX T-02-188/189/192, T-03-94, T-05-204..206,
notes 352..359) on a real Jenkins. A check named "#1.x" fails without the fix; one named "guard" holds with and without.

usage: python rerun_followups.py [PMNUDI]   (CI: PMNU in one unit, DI in another)   rows: r27/out/rerun_followups.jsonl, shots: screenshots/run-27/R28-1-*.png
Items (created again by A): r28-rp (Pipeline, `echo 'hello'`, free: no approval, timer and upstream not blocked), r28-rq
(approval-required, DATE), r28-act (not activated), r28-dup (approval-required, DATE defaulting to 2026-10-31). Accounts:
requester (RequestGrant: replays r28-rp #1 under an approved CONFIGURE window, so #2 is the marked run), r28-alice (added
for this unit: Overall/Read, Job/Read, Job/Build, Run/Replay natively), approver-1 and approver-2, admin; anonymous gets
Overall/Read, Job/Read and Run/Replay for section U. The matrix strategy is saved first and put back at the end.

P  arrangement of M, N, U: r28-rp; the strategy saved; r28-alice and anonymous's permissions; r28-rp #1 (admin); the requester's
   CONFIGURE window on r28-rp approved; the requester's Replay of #1 runs as #2 and is recorded as REPLAY_UNDER_GRANT.
M  #1.1 (T-02-188): change control off: r28-alice's Pipeline Rebuild of #2 and Replay of #2 build (guard); change control
   on: r28-alice's Rebuild of each of those two runs is refused (nothing queued, no build number used) and recorded as
   TRIGGER_BLOCKED naming r28-alice, because they carry the marker (#1.1). Guard: her Rebuild of the unmarked #1 builds.
N  #1.2 (T-02-189): the administrator's Pipeline Rebuild of the marked #2 builds and writes exactly one REPLAY_UNDER_GRANT
   record: user admin, naming the new run and 'requester' (who replayed under the window), not calling admin a grant-only
   replayer (#1.2). Guard: #2's record names the requester and says the permission came only from a permission window.
U  #1.5 (T-02-192): a Replay cause of an unmarked run of r28-rp, the run then deleted, submitted (script console,
   Queue#schedule2 under ACL.as2) by r28-alice and by anonymous: both refused, nothing queued; r28-alice's TRIGGER_BLOCKED
   says switch=unresolvedSource and "could not be identified" (guard); anonymous's single record says the same and not
   switch=replayedUnderGrant (#1.5).
D  #1.7 (T-03-94): the requester posts the stale Change Approvers form (approver-2) to her rejected run request, her
   approved window request and her approved activation request: each answer is a 4xx plain refusal, not "Correct the
   fields marked below", naming the request's status (#1.7); the approvers stay [approver-1] (guard).
I  #1.9 (T-05-204..206): the requester's identical Request Run form submitted twice in the browser: no second request,
   the browser lands on the first request's page with "An identical request of yours is already pending"; the same
   request from a script (Accept: application/json) answers a 4xx naming the first request; approver-1 is notified once
   (#1.9). Guards: another reason, another DATE and approver-2 instead each create a request and notify; after the first
   is cancelled the identical request is created again.
cleanup: the strategy put back; the switches as they were; the requester's pending r28 requests cancelled and windows
revoked; the items deleted."""
import json
import re
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 2)[0] + "/r27")
import lib  # noqa: E402
from lib import api, check, note, Session, gv  # noqa: E402

lib.LOGNAME[0] = "rerun_followups"
RP, RQ, ACT, DUP = "r28-rp", "r28-rq", "r28-act", "r28-dup"
ALICE = "r28-alice"
REPLAY = "hudson.model.Run.Replay"
S = {}
UUIDS = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def now_ms():
    return int(gv("return System.currentTimeMillis()"))


def records(types, since):
    return lib.facts(f"""def res = []
(new File(jenkins.model.Jenkins.get().rootDir, 'batch-control/changes').listFiles() ?: []).findAll {{ it.name.endsWith('.jsonl') }}.each {{
  it.eachLine('UTF-8') {{ l -> def m = new groovy.json.JsonSlurper().parseText(l)
    if ((m.at as long) >= {since}L && {json.dumps(list(types))}.contains(m.type)) res << [type: m.type, user: m.user, target: m.target, detail: String.valueOf(m.detail)] }} }}
return groovy.json.JsonOutput.toJson(res)""")


def idle(job, timeout=120):
    return lib.wait_until(lambda: not lib.L25.L19.queue_items(job) and not any(b.get("building") for b in lib.builds(job)),
                          timeout, 1)


def post(user, path, data=None):
    return api(user, path, "POST", data=data or {}).status_code


def replay(user, job, number, script):
    return post(user, lib.jpath(job) + f"/{number}/replay/run",
                {"mainScript": script, "json": json.dumps({"mainScript": script})})


def set_change_control(on):
    return lib.gv(lib.L25.CFG + f"cfg.setChangeControlEnabled({str(on).lower()}); cfg.save(); return String.valueOf(cfg.changeControlEnabled)")


def fresh(job, xml):
    if api("admin", lib.jpath(job) + "/api/json").status_code == 200:
        api("admin", lib.jpath(job) + "/doDelete", "POST")
    return lib.ensure_item(job, xml)


def sec_P():
    S["change"] = lib.gv(lib.L25.CFG + "return String.valueOf(cfg.changeControlEnabled)") == "true"
    S["saved"] = gv("""import jenkins.model.Jenkins
def j = Jenkins.get(); System.getProperties().put('r28.1.strategy', Jenkins.XSTREAM2.toXML(j.authorizationStrategy)); return 'saved'""")
    made = {RP: fresh(RP, lib.job_xml("wf", script="echo 'hello'"))}
    props = {RP: lib.set_property(RP, approval=False, timer=False, upstream=False)}
    perms = lib.L25.ensure_account(ALICE, ["hudson.model.Hudson.Read", "hudson.model.Item.Read", "hudson.model.Item.Build", REPLAY])
    anon = gv(f"""import hudson.security.*; import org.jenkinsci.plugins.matrixauth.*
def j = jenkins.model.Jenkins.get(); def s = j.authorizationStrategy
['hudson.model.Hudson.Read', 'hudson.model.Item.Read', '{REPLAY}'].each {{ s.add(Permission.fromId(it), new PermissionEntry(AuthorizationType.USER, 'anonymous')) }}
j.save(); return 'anonymous added'""")
    on = set_change_control(True)
    n1 = lib.next_build(RP)
    first = post("admin", lib.jpath(RP) + "/build?delay=0")
    r1 = lib.wait_build(RP, n1, timeout=120)[0]
    st, gid = lib.submit_grant("requester", RP, ["CONFIGURE"], minutes=30, reason="e2e-28 #1 replay window")
    dec = lib.decide("approver-1", "grants", gid, "approve", "e2e-28 #1") if gid else None
    mark = now_ms()
    rp = replay("requester", RP, n1, "echo 'planted'")
    idle(RP)
    n2 = lib.next_build(RP) - 1
    marks = [r for r in records(["REPLAY_UNDER_GRANT"], mark) if r["target"] == RP]
    S.update(n1=n1, n2=n2)
    check("P", "arrangement: r28-rp; r28-alice holds Run/Replay natively; anonymous Overall/Read, Job/Read, Run/Replay; "
          "change control on; r28-rp #1 built; the requester's CONFIGURE window approved; her Replay of #1 ran as #2 and is "
          "recorded as REPLAY_UNDER_GRANT naming her", all(v is not None for v in made.values()) and REPLAY in perms
          and on == "true" and r1 == "SUCCESS" and dec in (200, 302) and n2 == n1 + 1 and len(marks) == 1
          and marks[0]["user"] == "requester", props=props, first=first, replay=rp, grant=(st, gid, dec), marks=marks,
          anon=anon, n2=n2)


def sec_M():
    n2 = S["n2"]
    off = set_change_control(False)
    b3 = lib.next_build(RP)
    st3 = post(ALICE, lib.jpath(RP) + f"/{n2}/replay/rebuild")
    idle(RP)
    st4 = replay(ALICE, RP, n2, "echo 'replayed while off'")
    idle(RP)
    built = lib.next_build(RP) - b3
    check("M", "guard: with change control off r28-alice's Pipeline Rebuild and Replay of the marked run both build",
          off == "false" and built == 2, rebuild=st3, replay=st4, builds=built)
    on = set_change_control(True)
    mark, nb = now_ms(), lib.next_build(RP)
    sts = {src: post(ALICE, lib.jpath(RP) + f"/{src}/replay/rebuild") for src in (b3, b3 + 1)}
    idle(RP, 30)
    blocked = [r for r in records(["TRIGGER_BLOCKED"], mark) if r["user"] == ALICE and r["target"] == RP]
    check("M", "#1.1 (T-02-188): with change control on, r28-alice's Pipeline Rebuild of the two runs made from the marked run "
          "while change control was off is refused (nothing queued, no build number used) and recorded as TRIGGER_BLOCKED "
          "naming her: those runs carry the marker", on == "true" and lib.next_build(RP) == nb
          and not lib.L25.L19.queue_items(RP) and len(blocked) >= 2, statuses=sts, next_build=[nb, lib.next_build(RP)],
          blocked=blocked[:2])
    nb = lib.next_build(RP)
    post(ALICE, lib.jpath(RP) + f"/{S['n1']}/replay/rebuild")
    idle(RP)
    check("M", "guard: r28-alice's Pipeline Rebuild of the unmarked #1 builds", lib.next_build(RP) == nb + 1,
          next_build=[nb, lib.next_build(RP)])


def sec_N():
    mark, nb = now_ms(), lib.next_build(RP)
    st = post("admin", lib.jpath(RP) + f"/{S['n2']}/replay/rebuild")
    idle(RP)
    added = [r for r in records(["REPLAY_UNDER_GRANT"], mark) if r["target"] == RP]
    original = [r for r in records(["REPLAY_UNDER_GRANT"], 0) if r["target"] == RP and f"#{S['n2']}" in r["detail"]
                and f"#{nb}" not in r["detail"]]
    check("N", "guard: the record of the marked run names the requester and says her permission came only from a permission "
          "window", bool(original) and original[0]["user"] == "requester" and "only from a permission window" in original[0]["detail"],
          original=original[:1])
    d = added[0]["detail"] if len(added) == 1 else ""
    check("N", "#1.2 (T-02-189): the administrator's Pipeline Rebuild of the marked run builds and writes exactly one "
          "REPLAY_UNDER_GRANT record: user admin, naming the new run and 'requester' who replayed under the window, not "
          "calling admin a grant-only replayer", lib.next_build(RP) == nb + 1 and len(added) == 1 and added[0]["user"] == "admin"
          and f"#{nb}" in d and "'requester'" in d and not re.search(r"'admin',? whose permission", d), status=st, added=added)


UNRESOLVED = """import hudson.model.*; import hudson.security.ACL; import jenkins.model.Jenkins
def j = Jenkins.get(); def job = j.getItemByFullName('%s'); def run = job.getBuildByNumber(%d)
def c = j.pluginManager.uberClassLoader.loadClass('org.jenkinsci.plugins.workflow.cps.replay.ReplayCause').getDeclaredConstructor(Run.class, boolean.class)
c.accessible = true; def cause = c.newInstance(run, false); run.delete()
def out = [:]
[['%s', hudson.model.User.getById('%s', false).impersonate2()], ['anonymous', Jenkins.ANONYMOUS2]].each { p ->
  def ctx = ACL.as2(p[1])
  try { out[p[0]] = 'accepted=' + j.queue.schedule2(job, 0, new CauseAction(cause)).isAccepted() }
  catch (hudson.model.Failure f) { out[p[0]] = 'refused: ' + f.message } finally { ctx.close() } }
return groovy.json.JsonOutput.toJson(out)"""


def sec_U():
    n = lib.next_build(RP)
    post("admin", lib.jpath(RP) + "/build?delay=0")
    lib.wait_build(RP, n, timeout=120)
    mark, nb = now_ms(), lib.next_build(RP)
    accepted = lib.facts(UNRESOLVED % (RP, n, ALICE, ALICE))
    time.sleep(2)
    recs = [r for r in records(["TRIGGER_BLOCKED"], mark) if r["target"] == RP]
    mine = [r for r in recs if r["user"] == ALICE]
    anon = [r for r in recs if r["user"] in ("anonymous", "ANONYMOUS", "SYSTEM") or r["user"] is None or r["user"] == ""]
    check("U", "guard: the Replay cause of a deleted run is refused for r28-alice and anonymous (not accepted, nothing queued, "
          "no build number used); r28-alice's TRIGGER_BLOCKED record says switch=unresolvedSource and 'could not be "
          "identified'", set(accepted) == {ALICE, "anonymous"} and all(v == "accepted=false" or v.startswith("refused")
                                                                      for v in accepted.values()) and lib.next_build(RP) == nb
          and len(mine) == 1 and "switch=unresolvedSource" in mine[0]["detail"] and "could not be identified" in mine[0]["detail"],
          accepted=accepted, records=recs)
    others = [r for r in recs if r["user"] != ALICE]
    check("U", "#1.5 (T-02-192): anonymous's single record says switch=unresolvedSource and 'could not be identified', not "
          "switch=replayedUnderGrant nor 'replayed under a permission window'", len(others) == 1
          and "switch=unresolvedSource" in others[0]["detail"] and "could not be identified" in others[0]["detail"]
          and "replayedUnderGrant" not in others[0]["detail"] and "replayed under a permission window" not in others[0]["detail"],
          anonymous=others, users=sorted({r["user"] for r in recs}), anon_named=anon[:1])


def approvers(kind, rid):
    d = {"run": "requests/run", "grant": "requests/grant", "activation": "activation-requests"}[kind]
    return gv(f"""def f = new File(jenkins.model.Jenkins.get().rootDir, 'batch-control/{d}/{rid}.xml')
return f.exists() ? new XmlSlurper().parse(f).approvers.'*'*.text().join(',') : 'missing'""")


def sec_D():
    fresh(RQ, lib.job_xml("fs", shell="echo r28", params=lib.string_p("DATE", "2026-10-01")))
    fresh(ACT, lib.job_xml("fs", shell="echo r28"))
    lib.set_property(RQ, approval=True)
    st, run_id = lib.submit_run("requester", RQ, "e2e-28 #1.7 run", params={"DATE": "2026-10-02"})
    lib.decide("approver-1", "requests", run_id, "reject", "e2e-28 #1.7 no")
    st, grant_id = lib.submit_grant("requester", RQ, ["CONFIGURE"], reason="e2e-28 #1.7 window")
    lib.decide("approver-1", "grants", grant_id, "approve", "e2e-28 #1.7")
    st, act_id = lib.submit_activation("requester", ACT, "ACTIVATE", "e2e-28 #1.7 activation")
    lib.decide("approver-1", "activations", act_id, "approve", "e2e-28 #1.7")
    S["revoke"] = grant_id
    for kind, url, rid, status in (("run", "requests", run_id, "REJECTED"), ("grant", "grants", grant_id, "APPROVED"),
                                   ("activation", "activations", act_id, "APPROVED")):
        stored = lib.stored(kind, rid).get("status")
        r = api("requester", f"/batch-control/{url}/{rid}/changeApprover", "POST", data=[("approvers", "approver-2")])
        alerts = re.findall(r'role="alert"[^>]*>(.*?)</', r.text, re.S)
        msg = " ".join(lib.text_of(a) for a in alerts) if alerts else lib.text_of(r.text)
        after = approvers(kind, rid)
        check("D", f"#1.7 (T-03-94): the stale Change Approvers form posted to the requester's {stored} {kind} request is "
              f"refused with a 4xx plain refusal (not 'Correct the fields marked below') that names its status {status}",
              stored == status and 400 <= r.status_code < 500 and "Correct the fields marked below" not in lib.text_of(r.text)
              and re.search(status, msg, re.I) is not None, status=r.status_code, message=msg[:240], stored=stored)
        check("D", f"guard: the {kind} request's approvers stay [approver-1]", after == "approver-1", approvers=after)


def form_submit(reason, shot=None):
    """The requester's Request Run form for r28-dup, approver-1 alone ticked, DATE left at its default: (landing URL, text)."""
    s = Session("requester", fresh=True)
    s.go(lib.jpath(DUP) + "/batch-control/")
    form = s.page.locator("form[name=batch-control-request]")
    form.locator("textarea[name=reason]").fill(reason)
    s.page.evaluate("""() => document.querySelectorAll('form[name=batch-control-request] input[name=approvers]')
      .forEach(b => { b.checked = b.value === 'approver-1'; b.dispatchEvent(new Event('change', {bubbles: true})); })""")
    with s.page.expect_navigation(timeout=60000):
        form.locator("button[name=Submit]").first.click()
    s.page.wait_for_load_state("load")
    url, text = s.page.url.replace(lib.BASE, ""), re.sub(r"\s+", " ", s.text())
    if shot:
        lib.page_shot(s, shot)
    s.done()
    return url, text


def pending(job):
    return gv(f"""def d = new File(jenkins.model.Jenkins.get().rootDir, 'batch-control/requests/run')
return (d.listFiles() ?: []).findAll {{ it.name ==~ /[0-9a-f-]{{36}}\\.xml/ }}.collect {{ new XmlSlurper().parse(it) }}
  .findAll {{ it.status.text() == 'PENDING' && it.jobFullName.text() == '{job}' }}.collect {{ it.id.text() }}.sort().join(',')""").split(",")


def mails_for(rid, to):
    lib.wait_until(lambda: lib.L25.L19.mails(to=to, contains=rid), 20, 2)
    time.sleep(3)  # the quiet period: a second notification would arrive in it (it is sent at once)
    return len(lib.L25.L19.mails(to=to, contains=rid))


def sec_I():
    fresh(DUP, lib.job_xml("fs", shell="echo r28", params=lib.string_p("DATE", "2026-10-31")))
    lib.set_property(DUP, approval=True)
    lib.sweep("requester", DUP)
    url1, _ = form_submit("e2e-28 #1.9 the same request")
    first = (re.search(UUIDS, url1) or [None])[0]
    url2, text2 = form_submit("e2e-28 #1.9 the same request", shot="R28-1-I-identical-pending")
    now = [x for x in pending(DUP) if x]
    check("I", "#1.9 (T-05-204): the identical Request Run form submitted again from the browser creates no second request; "
          "the browser lands on the first request's page, which says 'An identical request of yours is already pending'",
          first is not None and now == [first] and f"/batch-control/requests/{first}/" in url2
          and "An identical request of yours is already pending" in text2, first=first, landed=url2, pending=now,
          text=text2[:200])
    body = {"reason": "e2e-28 #1.9 the same request", "approvers": ["approver-1"], "parameter": [{"name": "DATE", "value": "2026-10-31"}]}
    r = api("requester", lib.jpath(DUP) + "/batch-control/submit", "POST", data={"json": json.dumps(body)},
            headers={"Accept": "application/json"})
    check("I", "#1.9 (T-05-205): the same request from a script (Accept: application/json) is answered with a 4xx naming the "
          "first request, and no request is created", 400 <= r.status_code < 500 and first in r.text
          and [x for x in pending(DUP) if x] == [first], status=r.status_code, body=r.text[:200])
    n = mails_for(first, "approver-1@e2e.local")
    check("I", "#1.9: approver-1 is notified of the first request once, not again for the identical submissions", n == 1, mails=n)
    made = {}
    for key, reason, params, appr in (("reason", "e2e-28 #1.9 another reason", {"DATE": "2026-10-31"}, "approver-1"),
                                      ("date", "e2e-28 #1.9 the same request", {"DATE": "2026-11-01"}, "approver-1"),
                                      ("approver", "e2e-28 #1.9 the same request", {"DATE": "2026-10-31"}, "approver-2")):
        st, rid = lib.submit_run("requester", DUP, reason, approvers=(appr,), params=params)
        made[key] = (st, rid, mails_for(rid, f"{appr}@e2e.local") if rid else 0)
    check("I", "guard (T-05-206): another reason, another DATE and approver-2 instead each create a request that is notified",
          all(v[1] and v[2] >= 1 for v in made.values()), made=made)
    api("requester", f"/batch-control/requests/{first}/cancel", "POST")
    st, again = lib.submit_run("requester", DUP, "e2e-28 #1.9 the same request", params={"DATE": "2026-10-31"})
    check("I", "guard (T-05-206): after the first request is cancelled the identical request is created again",
          again is not None and again != first and again in pending(DUP), created=again, status=st)


def cleanup():
    back = gv("""import jenkins.model.Jenkins
def j = Jenkins.get(); def snap = System.getProperties().remove('r28.1.strategy')
if (snap != null) { j.setAuthorizationStrategy(Jenkins.XSTREAM2.fromXML(snap)); j.save() }
def u = hudson.model.User.getById('""" + ALICE + """', false); if (u != null) u.delete()
return j.authorizationStrategy.getClass().simpleName""")
    cc = set_change_control(S.get("change", True))
    note("cleanup", "restore", strategy=back, change_control=cc, swept=lib.sweep("requester", "r28-"),
         revoked=api("admin", f"/batch-control/grants/{S['revoke']}/revoke", "POST").status_code if S.get("revoke") else None,
         deleted={j: api("admin", lib.jpath(j) + "/doDelete", "POST").status_code for j in (RP, RQ, ACT, DUP)})


if __name__ == "__main__":
    lib.run(sys.argv, {"P": sec_P, "M": sec_M, "N": sec_N, "U": sec_U, "D": sec_D, "I": sec_I}, cleanup)
