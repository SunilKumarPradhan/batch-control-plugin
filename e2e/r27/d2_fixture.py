"""e2e-27 D2: the arrangement shared by r27/labels_filters.py and r27/status_badges.py (not a driver).

arrange() produces, for the requester and through the plugin's own endpoints (REST; the script console only where a
person could not do it in a test's time), one record in every state the D2 contract names, on items named r27-d2-*:

  run requests       PENDING, CANCELLED, REJECTED, EXPIRED and EXECUTED on r27-d2-ok; APPROVED on r27-d2-wait (bound to a
                     label no node has, so the approved run waits in the queue); INVALIDATED on r27-d2-gone (deleted)
  window requests    PENDING (r27-d2-ok), REJECTED (r27-d2-fail), CANCELLED (r27-d2-fail2), EXPIRED (r27-d2-fail3);
                     APPROVED with an open window (r27-d2-w-live); APPROVED whose window ended: expired (a one-minute
                     window, r27-d2-w-exp), revoked by admin (r27-d2-w-rev), its item deleted by an administrator with a
                     long user id (r27-d2-w-del)
  activation requests PENDING (r27-d2-act), REJECTED (act2), CANCELLED (act3), EXPIRED (act4), INVALIDATED
                     (r27-d2-gone, deleted); on r27-d2-sup ACTIVATE, HOLD, ACTIVATE each approved, so the last is in
                     effect and the ones before it are "Approved (superseded)"
  incidents          OPEN (r27-d2-fail), ACKNOWLEDGED (fail2), RESOLVED (fail3), and an OPEN one with the result
                     UNSTABLE (r27-d2-unst)
  runs               SUCCESS, FAILURE and UNSTABLE through approved requests (cause APPROVED_REQUEST); ABORTED and
                     NOT_BUILT (two Pipeline jobs that set their result, built by admin: cause USER); on r27-d2-timer
                     (no approval, activated, triggers unblocked) one run each with a timer, an upstream, an SCM and a
                     remote cause, scheduled from the script console (TIMER, UPSTREAM, SCM, OTHER)

EXPIRED: pendingTimeoutHours cannot be set below 1 and ci/arrange_ci.py sets 24, so the three requests are made one hour
older than the setting in the store (createdAtMillis) and the plugin's own periodic work expires them, as in
r27/titles_revert.py. The expiring window lasts one minute. Both are started first and awaited last.

The states are read back from the store (lib.stored, the grant files, incidents.csv), never from a screen label. The
result is written to out/d2_fixture.json; arrange(reuse=True) returns it unchanged when every stored state is still the
expected one (the second D2 unit of a shard does not arrange again)."""
import csv
import io
import json
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import titles_revert as D  # noqa: E402  (helpers only; its sections run under __main__)
import lib  # noqa: E402
from lib import api, gv  # noqa: E402

P = "r27-d2-"
NAMES = ("ok", "fail", "fail2", "fail3", "unst", "wait", "gone", "act", "act2", "act3", "act4", "sup", "w-live", "w-exp",
         "w-rev", "w-del", "timer", "aborted", "notbuilt")
J = {n: P + n for n in NAMES}
LONG_ADMIN = "r27-d2-administrator-with-a-rather-long-user-identifier"
STATE = lib.OUT / "d2_fixture.json"
REQUEST_STATUSES = ["PENDING", "APPROVED", "REJECTED", "CANCELLED", "EXPIRED", "EXECUTED", "INVALIDATED"]
INCIDENT_STATUSES = ["OPEN", "ACKNOWLEDGED", "RESOLVED"]


def csv_text(path, who="admin"):
    r = api(who, path)
    return r.content.decode("utf-8-sig", errors="replace") if r.status_code == 200 else ""


def csv_rows(path, who="admin"):
    return list(csv.DictReader(io.StringIO(csv_text(path, who))))


def decide(kind, rid, verb, comment="e2e-27 D2"):
    return lib.decide("approver-1", kind, rid, verb, comment) if rid else None


def cancel(kind, rid):
    return api("requester", f"/batch-control/{kind}/{rid}/cancel", "POST").status_code if rid else None


def incident_of(job, number):
    for r in csv_rows(f"/batch-control/history/incidents.csv?job={job}"):
        if r.get("runId") == f"{job}#{number}":
            return r.get("id")
    return None


def states(S):
    """Server state of everything the fixture made: {name: state}."""
    out = {f"run {k}": lib.stored("run", v).get("status") for k, v in S["run"].items()}
    out.update({f"grant {k}": lib.stored("grant", v).get("status") for k, v in S["grant"].items()})
    out.update({f"window {k}": D.window_of(v).get("open") for k, v in S["window"].items()})
    out.update({f"activation {k}": lib.stored("activation", v).get("status") for k, v in S["activation"].items()})
    out.update({f"superseded {i}": lib.stored("activation", v).get("status") for i, v in enumerate(S["superseded"])})
    inc = {r.get("id"): r.get("status") for r in csv_rows(f"/batch-control/history/incidents.csv?job={P}")}
    out.update({f"incident {k}": inc.get(v) for k, v in S["incident"].items()})
    return out


def expected(S):
    out = {f"run {k}": k for k in S["run"]}
    out.update({f"grant {k}": ("APPROVED" if k.startswith("APPROVED") else k) for k in S["grant"]})
    out.update({f"window {k}": k == "live" for k in S["window"]})
    out.update({f"activation {k}": k for k in S["activation"]})
    out.update({f"superseded {i}": "APPROVED" for i in range(len(S["superseded"]))})
    out.update({"incident OPEN": "OPEN", "incident ACKNOWLEDGED": "ACKNOWLEDGED", "incident RESOLVED": "RESOLVED",
                "incident UNSTABLE": "OPEN"})
    return out


def build_and_wait(job, cause=None, who="admin"):
    """One build of `job`: by `who` over REST (cause USER) or, with `cause` (Groovy), scheduled from the script console."""
    n = lib.next_build(job)
    if cause is None:
        code = api(who, lib.jpath(job) + "/build?delay=0", "POST").status_code
    else:
        code = gv(f"""def j = jenkins.model.Jenkins.get(); def job = j.getItemByFullName('{job}')
def f = job.scheduleBuild2(0, new hudson.model.CauseAction({cause})); return f == null ? 'refused' : 'scheduled'""")
    result = lib.wait_build(job, n, timeout=120)[0]
    return {"number": n, "result": result, "how": code}


def run_request(job, verb=None, comment="e2e-27 D2"):
    n = lib.next_build(job)
    st, rid = lib.submit_run("requester", job, f"e2e-27 D2 {job} {verb or 'left pending'}")
    return {"id": rid, "submit": st, "decide": decide("requests", rid, verb, comment) if verb else None, "number": n}


def arrange(reuse=False):
    if reuse and STATE.exists():
        S = json.loads(STATE.read_text())
        try:
            if states(S) == expected(S):
                S["reused"] = True
                return S
        except Exception:  # noqa: a stale file of another Jenkins
            pass
    S = {"reused": False, "run": {}, "grant": {}, "window": {}, "activation": {}, "superseded": [], "incident": {},
         "build": {}, "codes": {}}
    xml_ok = lib.job_xml("fs", shell="echo e2e-27 D2")
    xml_fail = lib.job_xml("fs", shell="echo e2e-27 D2; exit 1")
    xml_unst = lib.job_xml("fs", shell="echo e2e-27 D2; exit 2").replace("</command>", "</command><unstableReturn>2</unstableReturn>")
    xml_wait = xml_ok.replace("<canRoam>true</canRoam>", "<assignedNode>r27-nowhere</assignedNode><canRoam>false</canRoam>")
    wf = lambda result: lib.job_xml("wf", script=f"currentBuild.result = '{result}'")  # noqa: E731
    S["removed"] = D.remove(J["gone"], J["w-del"])
    xmls = {"fail": xml_fail, "fail2": xml_fail, "fail3": xml_fail, "unst": xml_unst, "wait": xml_wait,
            "aborted": wf("ABORTED"), "notbuilt": wf("NOT_BUILT")}
    for n in NAMES:
        lib.ensure_item(J[n], xmls.get(n, xml_ok))
    free = ("timer", "aborted", "notbuilt")
    S["props"] = {n: lib.set_property(J[n], approval=True) for n in NAMES if n not in free}
    # jobs created under run control start locked (approval, timer and upstream blocked): cleared for these three
    S["props_free"] = {n: lib.set_property(J[n], approval=False, timer=False, upstream=False) for n in free}
    S["swept"] = lib.sweep("requester", P)
    hours = D.settings()["pending"] + 1

    # ---- what needs time first: the one-minute window and the three requests left to expire
    st, wexp = lib.submit_grant("requester", J["w-exp"], ["CONFIGURE"], minutes=1, reason="e2e-27 D2 one-minute window")
    S["codes"]["w-exp"] = (st, decide("grants", wexp, "approve"))
    S["grant"]["APPROVED expired"] = wexp
    S["window"]["exp"] = wexp
    rexp = run_request(J["ok"])
    st, gexp = lib.submit_grant("requester", J["fail3"], ["CONFIGURE"], reason="e2e-27 D2 window request left to expire")
    st2, aexp = lib.submit_activation("requester", J["act4"], "ACTIVATE", "e2e-27 D2 activation left to expire")
    S["run"]["EXPIRED"], S["grant"]["EXPIRED"], S["activation"]["EXPIRED"] = rexp["id"], gexp, aexp
    S["backdated"] = D.backdate((("run", rexp["id"]), ("grant", gexp), ("activation", aexp)), hours)

    # ---- runs: results and causes
    S["build"]["ok"] = run_request(J["ok"], "approve")
    S["run"]["EXECUTED"] = S["build"]["ok"]["id"]
    for n in ("fail", "fail2", "fail3", "unst"):
        S["build"][n] = run_request(J[n], "approve")
    for n in ("ok", "fail", "fail2", "fail3", "unst"):
        S["build"][n]["result"] = lib.wait_build(J[n], S["build"][n]["number"], timeout=240)[0]
    for n in ("aborted", "notbuilt"):
        S["build"][n] = build_and_wait(J[n])
    if lib.activation(J["timer"]) != "activated":  # a job created under run control runs unattended only once activated
        st, tid = lib.submit_activation("requester", J["timer"], "ACTIVATE", "e2e-27 D2 timer job into service")
        S["codes"]["timer"] = (st, decide("activations", tid, "approve"),
                               lib.wait_until(lambda: lib.activation(J["timer"]) == "activated", 20, 1))
    up = f"new hudson.model.Cause.UpstreamCause(j.getItemByFullName('{J['ok']}').getLastBuild())"
    for key, cause in (("TIMER", "new hudson.triggers.TimerTrigger.TimerTriggerCause()"), ("UPSTREAM", up),
                       ("SCM", "new hudson.triggers.SCMTrigger.SCMTriggerCause('e2e-27 D2')"),
                       ("OTHER", "new hudson.model.Cause.RemoteCause('e2e.local', 'e2e-27 D2')")):
        S["build"]["cause " + key] = build_and_wait(J["timer"], cause)
    S["build"]["cause USER"] = build_and_wait(J["timer"])

    # ---- incidents
    S["incident"] = {"OPEN": incident_of(J["fail"], S["build"]["fail"]["number"]),
                     "ACKNOWLEDGED": incident_of(J["fail2"], S["build"]["fail2"]["number"]),
                     "RESOLVED": incident_of(J["fail3"], S["build"]["fail3"]["number"]),
                     "UNSTABLE": incident_of(J["unst"], S["build"]["unst"]["number"])}
    post = lambda iid, verb: api("approver-1", f"/batch-control/incidents/{iid}/{verb}", "POST",  # noqa: E731
                                 data={"comment": f"e2e-27 D2 {verb}"}).status_code if iid else None
    S["codes"]["incidents"] = (post(S["incident"]["ACKNOWLEDGED"], "acknowledge"), post(S["incident"]["RESOLVED"], "acknowledge"),
                               post(S["incident"]["RESOLVED"], "resolve"))

    # ---- run requests
    S["run"]["REJECTED"] = run_request(J["ok"], "reject", "e2e-27 D2 not today")["id"]
    canc = run_request(J["ok"])
    S["run"]["CANCELLED"] = canc["id"]
    S["codes"]["run cancel"] = cancel("requests", canc["id"])
    S["run"]["PENDING"] = run_request(J["ok"])["id"]
    S["run"]["INVALIDATED"] = run_request(J["gone"])["id"]
    S["run"]["APPROVED"] = run_request(J["wait"], "approve", "e2e-27 D2 waits in the queue")["id"]

    # ---- window requests and windows
    g = {}
    for key, item, action in (("PENDING", "ok", "CONFIGURE"), ("REJECTED", "fail", "DELETE"), ("CANCELLED", "fail2", "CONFIGURE")):
        st, g[key] = lib.submit_grant("requester", J[item], [action], reason=f"e2e-27 D2 window request on {item}")
    S["codes"]["grant"] = (decide("grants", g["REJECTED"], "reject", "e2e-27 D2 no"), cancel("grants", g["CANCELLED"]))
    for key, item in (("live", "w-live"), ("rev", "w-rev"), ("del", "w-del")):
        st, wid = lib.submit_grant("requester", J[item], ["CONFIGURE"], minutes=30, reason=f"e2e-27 D2 window ({key})")
        S["codes"]["window " + key] = (st, decide("grants", wid, "approve"))
        S["window"][key] = wid
        g["APPROVED " + {"live": "open", "rev": "revoked", "del": "item deleted"}[key]] = wid
    S["grant"].update(g)
    S["codes"]["revoke"] = api("admin", f"/batch-control/grants/{S['window']['rev']}/revoke", "POST").status_code
    # the deletion by an administrator with a long user id (the longest wording of the Ended table); the account's
    # matrix entry and the account go again at once
    S["codes"]["long admin"] = gv("""import jenkins.model.Jenkins
def j = Jenkins.get(); def snap = Jenkins.XSTREAM2.toXML(j.authorizationStrategy)
System.getProperties().put('r27.d2.strategy', snap); return 'saved'""")
    lib.L25.ensure_account(LONG_ADMIN, ["hudson.model.Hudson.Administer"])
    S["codes"]["delete w-del"] = api(LONG_ADMIN, lib.jpath(J["w-del"]) + "/doDelete", "POST").status_code
    S["codes"]["long admin gone"] = gv("""import jenkins.model.Jenkins
def j = Jenkins.get(); def snap = System.getProperties().remove('r27.d2.strategy')
if (snap != null) { j.setAuthorizationStrategy(Jenkins.XSTREAM2.fromXML(snap)); j.save() }
def u = hudson.model.User.getById('""" + LONG_ADMIN + """', false); if (u != null) u.delete()
return j.authorizationStrategy.getClass().simpleName""")

    # ---- activation requests
    a = {}
    for key, item in (("PENDING", "act"), ("REJECTED", "act2"), ("CANCELLED", "act3"), ("INVALIDATED", "gone")):
        action = "HOLD" if lib.activation(J[item]) == "activated" else "ACTIVATE"
        st, a[key] = lib.submit_activation("requester", J[item], action, f"e2e-27 D2 activation request on {item}")
    S["codes"]["activation"] = (decide("activations", a["REJECTED"], "reject", "e2e-27 D2 no"), cancel("activations", a["CANCELLED"]))
    S["codes"]["delete gone"] = api("admin", lib.jpath(J["gone"]) + "/doDelete", "POST").status_code
    chain = (["ACTIVATE"] if lib.activation(J["sup"]) != "activated" else []) + ["HOLD", "ACTIVATE"]
    ids = []
    for action in chain:  # each approved; the last is in effect, the ones before it were replaced
        st, rid = lib.submit_activation("requester", J["sup"], action, "e2e-27 D2 one of a chain, each approved")
        ids.append((rid, decide("activations", rid, "approve")))
    a["APPROVED"] = ids[-1][0]
    S["superseded"] = [i for i, _ in ids[:-1]]
    S["codes"]["sup"] = [c for _, c in ids]
    S["activation"].update(a)

    # ---- awaited last
    lib.wait_until(lambda: all(lib.stored(k, v).get("status") == "EXPIRED" for k, v in
                               (("run", rexp["id"]), ("grant", gexp), ("activation", aexp))), timeout=180, step=5)
    lib.wait_until(lambda: not D.window_of(wexp).get("open"), timeout=150, step=5)
    S["hours"] = hours
    STATE.write_text(json.dumps(S))
    return S
