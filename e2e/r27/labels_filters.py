"""e2e-27 D2 (Wave D, issue #18 items 3 and 2): the History filter's Result and Status are jenkins-select dropdowns that
start with "Any" and carry the enum names; screens show readable labels instead of raw enum names for request, grant and
activation statuses, incident statuses and run causes, each label element keeping the enum in data-batch-control-status.

usage: python labels_filters.py [AWLNICFG]   rows: out/labels_filters.jsonl, shots: screenshots/run-27/R27-D2-*.png
Items (approval required unless said): r27-d2-ok (succeeds), r27-d2-fail and r27-d2-fail2 (fail, so each run opens an
incident), r27-d2-wait (bound to the label r27-nowhere, so an approved run waits in the queue), r27-d2-act and
r27-d2-act2 (activation requests), r27-d2-timer (no approval; one run with a timer cause, scheduled from the script
console). The requester files the requests over REST, approver-1 decides them over REST; the screens are read in the
browser, one new context per account and page. The request states are read from the store, not from a screen.

A  arrangement: sweeps the requester's pending r27-d2 requests and queue items of an earlier pass; one EXECUTED run
   request (r27-d2-ok), two failed runs (incidents; the second acknowledged by approver-1), a REJECTED and a PENDING run
   request, a PENDING and a REJECTED grant request, a PENDING and a REJECTED activation request, a timer run, and last
   an APPROVED run request of r27-d2-wait (its run waits in the queue; approvedRunTimeoutMinutes is 1 in CI, so W runs
   next).
W  #18.2 the APPROVED (waiting) run request page (requester) shows "Approved, waiting to run"; History > Requests
   (approver-1) labels APPROVED. Guard: the store says APPROVED while the page is read.
L  #18.2 run request pages (requester): PENDING "Pending", EXECUTED "Executed", REJECTED a readable label; the requests
   list (requester) and History > Requests (approver-1) label PENDING, EXECUTED and REJECTED. On every page each element
   with data-batch-control-status=<ENUM> shows a non-blank label without the raw name, and no table shows the raw name
   as a word. Guards: requests.csv and the status filter keep the enum names.
N  #18.2 the PENDING grant and activation request pages (approver-1) read "Pending"; the grants and activations lists
   (requester) label REJECTED.
I  #18.2 the incident page (approver-1) labels OPEN; the incidents list and History > Incidents label OPEN and
   ACKNOWLEDGED. Guard: incidents.csv keeps the enum names.
C  #18.2 the Run Dashboard and History > Runs (approver-1) show APPROVED_REQUEST as "Approved request" and TIMER as
   "Timer". Guards: runs.csv keeps the cause names; the monthly JSON summary carries no screen label.
F  #18.3 History filter (approver-1): Runs offers a Result dropdown (jenkins-select, first option "Any" with an empty
   value and selected, the result names each once, no Status filter, no free-text field); Incidents offers Result and
   Status (Any, OPEN, ACKNOWLEDGED, RESOLVED); Requests offers Status (Any and every RequestStatus); Changes neither.
   Choosing FAILURE and pressing Filter leads to result=FAILURE listing only r27-d2-fail; choosing Any lists both again;
   choosing OPEN on Incidents leads to status=OPEN. A hand-edited value not in the list (result=WEIRD<b>x</b>,
   status=bogus"q) stays selected as one extra option, escaped (SPEC 6: the user's input is kept).
G  guards: the filter URL tokens are unchanged (?result=FAILURE lists only the failing runs; runs.csv with the same
   filter keeps the enum names).
cleanup: the requester's pending r27-d2 requests cancelled, r27-d2-wait's queue item cancelled."""
import csv
import io
import re
import sys
from urllib.parse import quote, urlparse, parse_qs

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import lib  # noqa: E402
from lib import api, check, note, Session  # noqa: E402

lib.LOGNAME[0] = "labels_filters"
P = "r27-d2-"
OK, FAIL, FAIL2, WAIT, ACT, ACT2, TIMER = (P + x for x in ("ok", "fail", "fail2", "wait", "act", "act2", "timer"))
S = {}
COMMON_RESULTS = ["SUCCESS", "UNSTABLE", "FAILURE", "ABORTED"]
INCIDENT_STATUSES = ["OPEN", "ACKNOWLEDGED", "RESOLVED"]
LABELS = {"PENDING": "Pending", "EXECUTED": "Executed", "APPROVED_REQUEST": "Approved request", "TIMER": "Timer"}
HOOK_JS = """(e) => [...document.querySelectorAll(`[data-batch-control-status="${e}"]`)].map(x => x.textContent.replace(/\\s+/g, ' ').trim())"""
TABLES_JS = """() => [...document.querySelectorAll('#main-panel table')].map(t => t.innerText).join('\\n')"""
FORM_JS = """() => { const from = document.querySelector('#main-panel input[name="from"]'); const f = from && from.form;
  if (!f) return null;
  const ctl = n => { const e = [...f.querySelectorAll(`input[name="${n}"], select[name="${n}"], textarea[name="${n}"]`)]
      .find(x => x.type !== 'hidden'); if (!e) return null;
    let styled = false; for (let p = e; p && p !== f && !styled; p = p.parentElement)
      styled = /(^|\\s)jenkins-select(__input)?(\\s|$)/.test(p.className || '');
    return {tag: e.tagName.toLowerCase(), type: e.type, styled, multiple: !!e.multiple,
      options: e.tagName === 'SELECT' ? [...e.options].map(o => ({value: o.value, text: o.textContent.trim(), selected: o.selected})) : null,
      bold: e.querySelectorAll('b').length, value: e.value}; };
  return {result: ctl('result'), status: ctl('status')}; }"""


def csv_text(path):
    r = api("admin", path)
    return r.content.decode("utf-8-sig", errors="replace") if r.status_code == 200 else ""


def csv_rows(path):
    return list(csv.DictReader(io.StringIO(csv_text(path))))


def run_once(job, verb="approve", comment="e2e-27 D2"):
    n = lib.next_build(job)
    st, rid = lib.submit_run("requester", job, f"e2e-27 D2 {job} {verb}")
    dec = lib.decide("approver-1", "requests", rid, verb, comment) if rid and verb else None
    result = lib.wait_build(job, n, timeout=240)[0] if verb == "approve" else None
    return {"id": rid, "submit": st, "decide": dec, "number": n, "result": result}


def sec_A():
    xml_ok, xml_fail = lib.job_xml("fs", shell="echo e2e-27 D2"), lib.job_xml("fs", shell="echo e2e-27 D2; exit 1")
    xml_wait = xml_ok.replace("<canRoam>true</canRoam>", "<assignedNode>r27-nowhere</assignedNode><canRoam>false</canRoam>")
    for name, xml in ((OK, xml_ok), (FAIL, xml_fail), (FAIL2, xml_fail), (WAIT, xml_wait), (ACT, xml_ok), (ACT2, xml_ok),
                      (TIMER, xml_ok)):
        lib.ensure_item(name, xml)
    props = {n: lib.set_property(n, approval=True) for n in (OK, FAIL, FAIL2, WAIT, ACT, ACT2)}
    # a job created under run control starts with blockTimer on (creation-time lock): cleared, so its timer run starts
    props_timer = lib.set_property(TIMER, approval=False, timer=False, upstream=False)
    S["swept"] = lib.sweep("requester", P)
    S["executed"] = run_once(OK)
    S["fail"] = run_once(FAIL)
    S["fail2"] = run_once(FAIL2)
    incs = {r.get("runId"): r for r in csv_rows(f"/batch-control/history/incidents.csv?job={P}")}
    S["inc_open"] = (incs.get(f"{FAIL}#{S['fail']['number']}") or {}).get("id")
    S["inc_ack"] = (incs.get(f"{FAIL2}#{S['fail2']['number']}") or {}).get("id")
    ack = api("approver-1", f"/batch-control/incidents/{S['inc_ack']}/acknowledge", "POST",
              data={"comment": "e2e-27 D2 looking"}).status_code if S["inc_ack"] else None
    S["rejected"] = run_once(OK, "reject", "e2e-27 D2 not today")
    S["pending"] = run_once(OK, None)
    st, gp = lib.submit_grant("requester", OK, ["CONFIGURE"], reason="e2e-27 D2 pending window")
    st2, gr = lib.submit_grant("requester", OK, ["DELETE"], reason="e2e-27 D2 rejected window")
    grd = lib.decide("approver-1", "grants", gr, "reject", "e2e-27 D2 no") if gr else None
    act_state = lib.activation(ACT), lib.activation(ACT2)
    st3, ap = lib.submit_activation("requester", ACT, "ACTIVATE" if act_state[0] != "activated" else "HOLD", "e2e-27 D2")
    st4, ar = lib.submit_activation("requester", ACT2, "ACTIVATE" if act_state[1] != "activated" else "HOLD", "e2e-27 D2")
    ard = lib.decide("approver-1", "activations", ar, "reject", "e2e-27 D2 no") if ar else None
    S.update(grant_pending=gp, grant_rejected=gr, act_pending=ap, act_rejected=ar)
    timer_act = None
    if lib.activation(TIMER) != "activated":  # a job created under run control runs on a timer once activated
        st5, tid = lib.submit_activation("requester", TIMER, "ACTIVATE", "e2e-27 D2 timer job into service")
        timer_act = {"submit": st5, "approve": lib.decide("approver-1", "activations", tid, "approve", "e2e-27 D2")
                     if tid else None, "state": lib.wait_until(lambda: lib.activation(TIMER) == "activated", 20, 1)}
    tn = lib.next_build(TIMER)
    lib.gv(f"""jenkins.model.Jenkins.get().getItemByFullName('{TIMER}').scheduleBuild2(0,
  new hudson.triggers.TimerTrigger.TimerTriggerCause()); return 'scheduled'""")
    timer = lib.wait_build(TIMER, tn, timeout=120)[0]
    S["approved"] = run_once(WAIT, None)
    dec = lib.decide("approver-1", "requests", S["approved"]["id"], "approve", "e2e-27 D2 waits") \
        if S["approved"]["id"] else None
    states = {k: lib.stored("run", S[k]["id"]).get("status") for k in ("executed", "rejected", "pending", "approved")}
    states.update(grant_pending=lib.stored("grant", gp).get("status"), grant_rejected=lib.stored("grant", gr).get("status"),
                  act_pending=lib.stored("activation", ap).get("status"),
                  act_rejected=lib.stored("activation", ar).get("status"))
    want = {"executed": "EXECUTED", "rejected": "REJECTED", "pending": "PENDING", "approved": "APPROVED",
            "grant_pending": "PENDING", "grant_rejected": "REJECTED", "act_pending": "PENDING", "act_rejected": "REJECTED"}
    check("A", "arrangement: EXECUTED, REJECTED, PENDING and APPROVED (waiting) run requests, PENDING and REJECTED grant "
          "and activation requests (store)", states == want and all(p.startswith("approvalRequired=true")
                                                                       for p in props.values()),
          states=states, ids={k: S[k]["id"] for k in ("executed", "rejected", "pending", "approved")}, swept=S["swept"],
          decide=dec, grant_reject=grd, act_reject=ard, codes=[st, st2, st3, st4])
    check("A", "arrangement: r27-d2-fail's run opened an OPEN incident and r27-d2-fail2's an ACKNOWLEDGED one; the timer "
          "run of r27-d2-timer finished", S["fail"]["result"] == "FAILURE" and S["inc_open"] and S["inc_ack"]
          and ack is not None and ack < 400 and timer == "SUCCESS", incidents=[S["inc_open"], S["inc_ack"]], ack=ack,
          timer=timer, timer_property=props_timer, timer_activation=timer_act, fail=S["fail"])


def labelled(sec, s, enum, expected, where):
    """#18.2 on the open page: elements with data-batch-control-status=<enum> show a readable label; no raw name in a
    table."""
    texts = s.page.evaluate(HOOK_JS, enum)
    tables = s.page.evaluate(TABLES_JS)
    raw = re.findall(r"(?<![A-Za-z_])" + enum + r"(?![A-Za-z_])", tables)
    ok = bool(texts) and all(t and enum not in t and (expected is None or expected in t) for t in texts) and not raw
    want = f"'{expected}'" if expected else "a readable label"
    return check(sec, f"D2 #18.2 {where}: {enum} is shown as {want} in elements carrying data-batch-control-status, and "
                 f"no table shows the raw name", ok, labels=sorted(set(texts))[:6], hooked=len(texts), raw_in_tables=len(raw),
                 excerpt=tables[:300] if not texts else None)


def view(sec, who, path, shot, checks, table_shot=True):
    s = Session(who)
    r = s.go(path)
    lib.page_shot(s, shot)
    if table_shot:
        s.shot("#main-panel table", shot + "-table")
    check(sec, f"guard: {who} opens {path} (200)", r is not None and r.status == 200, status=r.status if r else None)
    for enum, expected, where in checks:
        labelled(sec, s, enum, expected, where)
    s.done()


def sec_W():
    rid = S["approved"]["id"]
    before = lib.stored("run", rid).get("status")
    view("W", "requester", f"/batch-control/requests/{rid}/", "R27-D2-W-01-approved-waiting-request",
         [("APPROVED", "Approved, waiting to run", "the APPROVED (waiting) run request page")])
    view("W", "approver-1", f"/batch-control/history/?kind=requests&job={P}", "R27-D2-W-02-history-requests-approved",
         [("APPROVED", None, "History > Requests")])
    after = lib.stored("run", rid).get("status")
    check("W", "guard: the request was APPROVED with its run waiting in the queue while the pages were read (store)",
          before == after == "APPROVED", before=before, after=after, queue=len(lib.L25.queue_items(WAIT)))


def sec_L():
    req = lambda k: f"/batch-control/requests/{S[k]['id']}/"  # noqa: E731
    view("L", "requester", req("pending"), "R27-D2-L-01-pending-request",
         [("PENDING", "Pending", "the PENDING run request page")])
    view("L", "requester", req("executed"), "R27-D2-L-02-executed-request",
         [("EXECUTED", "Executed", "the EXECUTED run request page")])
    view("L", "requester", req("rejected"), "R27-D2-L-03-rejected-request",
         [("REJECTED", None, "the REJECTED run request page")])
    view("L", "requester", "/batch-control/requests/", "R27-D2-L-04-requests-list",
         [("EXECUTED", "Executed", "the Run Requests list"), ("REJECTED", None, "the Run Requests list")])
    view("L", "approver-1", f"/batch-control/history/?kind=requests&job={P}", "R27-D2-L-05-history-requests",
         [(e, LABELS.get(e), "History > Requests") for e in ("PENDING", "EXECUTED", "REJECTED")])
    text = csv_text(f"/batch-control/history/requests.csv?job={P}")
    check("L", "guard: requests.csv keeps the enum names (PENDING, APPROVED, EXECUTED, REJECTED)",
          all(re.search(r"(?<![A-Za-z_])" + e + r"(?![A-Za-z_])", text) for e in ("PENDING", "APPROVED", "EXECUTED",
                                                                                   "REJECTED")), head=text[:200])
    r = api("approver-1", f"/batch-control/history/?kind=requests&job={P}&status=EXECUTED")
    t = lib.text_of(r.text)
    check("L", "guard: the status filter still takes the enum name (status=EXECUTED lists the executed request, not the "
          "pending one)", r.status_code == 200 and S["executed"]["id"][:8] in t and S["pending"]["id"][:8] not in t,
          status=r.status_code)


def sec_N():
    view("N", "approver-1", f"/batch-control/grants/{S['grant_pending']}/", "R27-D2-N-01-pending-grant-request",
         [("PENDING", "Pending", "the PENDING grant request page")])
    view("N", "requester", "/batch-control/grants/", "R27-D2-N-02-grants-list",
         [("REJECTED", None, "the Grants list")])
    view("N", "approver-1", f"/batch-control/activations/{S['act_pending']}/", "R27-D2-N-03-pending-activation-request",
         [("PENDING", "Pending", "the PENDING activation request page")])
    view("N", "requester", "/batch-control/activations/", "R27-D2-N-04-activations-list",
         [("REJECTED", None, "the Activations list")])


def sec_I():
    view("I", "approver-1", f"/batch-control/incidents/{S['inc_open']}/", "R27-D2-I-01-open-incident",
         [("OPEN", None, "the OPEN incident page")])
    view("I", "approver-1", "/batch-control/incidents/", "R27-D2-I-02-incidents-list",
         [("OPEN", None, "the Incidents list"), ("ACKNOWLEDGED", None, "the Incidents list")])
    view("I", "approver-1", f"/batch-control/history/?kind=incidents&job={P}", "R27-D2-I-03-history-incidents",
         [("OPEN", None, "History > Incidents"), ("ACKNOWLEDGED", None, "History > Incidents")])
    text = csv_text(f"/batch-control/history/incidents.csv?job={P}")
    check("I", "guard: incidents.csv keeps the enum names (OPEN, ACKNOWLEDGED)", "OPEN" in text and "ACKNOWLEDGED" in text,
          head=text[:200])


def sec_C():
    view("C", "approver-1", "/batch-control/dashboard/", "R27-D2-C-01-dashboard-causes",
         [("APPROVED_REQUEST", "Approved request", "the Run Dashboard"), ("TIMER", "Timer", "the Run Dashboard")])
    view("C", "approver-1", f"/batch-control/history/?kind=runs&job={P}", "R27-D2-C-02-history-runs-causes",
         [("APPROVED_REQUEST", "Approved request", "History > Runs"), ("TIMER", "Timer", "History > Runs")])
    text = csv_text(f"/batch-control/history/runs.csv?job={P}")
    check("C", "guard: runs.csv keeps the cause names (APPROVED_REQUEST, TIMER)",
          "APPROVED_REQUEST" in text and "TIMER" in text, head=text[:200])
    month = lib.gv("return java.time.YearMonth.now().toString()")
    r = api("admin", f"/batch-control/history/summary?month={month}")
    leaked = [x for x in ("Approved request", "Approved, waiting to run", "Timer", "Pending", "Executed") if x in r.text]
    check("C", "guard: the monthly JSON summary answers and carries no screen label", r.status_code == 200 and not leaked,
          status=r.status_code, leaked=leaked)


def form_state(who, path, shot):
    s = Session(who)
    r = s.go(path)
    st = s.page.evaluate(FORM_JS)
    s.shot("#main-panel form:has(input[name=from])", shot)
    s.done()
    return (r.status if r else None), st


def is_dropdown(c):
    o = (c or {}).get("options") or []
    return bool(c and c["tag"] == "select" and c["styled"] and not c["multiple"] and o and o[0]["value"] == ""
                and o[0]["text"] == "Any")


def sec_F():
    statuses = lib.facts(f"return groovy.json.JsonOutput.toJson({lib.BC}.model.RequestStatus.values()*.name())")
    code, st = form_state("approver-1", "/batch-control/history/?kind=runs", "R27-D2-F-01-filter-runs")
    res = (st or {}).get("result")
    vals = [o["value"] for o in (res or {}).get("options") or []]
    check("F", "D2 #18.3 History > Runs: Result is a jenkins-select dropdown whose first option is 'Any' (empty value), "
          "selected with no result in the URL", is_dropdown(res) and res["options"][0]["selected"], result=res,
          status=code)
    check("F", "D2 #18.3 History > Runs: the Result options are result names, SUCCESS, UNSTABLE, FAILURE and ABORTED "
          "among them, each once", set(COMMON_RESULTS) <= set(vals) and len(vals) == len(set(vals)), values=vals)
    check("F", "D2 #18.3 History > Runs: no Status filter and no free-text Result field",
          (st or {}).get("status") is None and res is not None and res["tag"] == "select", form=st)
    code, st = form_state("approver-1", "/batch-control/history/?kind=incidents", "R27-D2-F-02-filter-incidents")
    res, sta = (st or {}).get("result"), (st or {}).get("status")
    check("F", "D2 #18.3 History > Incidents: Result and Status are jenkins-select dropdowns starting with 'Any'",
          is_dropdown(res) and is_dropdown(sta), form=st)
    check("F", "D2 #18.3 History > Incidents: Status offers exactly Any, OPEN, ACKNOWLEDGED, RESOLVED",
          [o["value"] for o in (sta or {}).get("options") or []] == [""] + INCIDENT_STATUSES, status=sta)
    code, st = form_state("approver-1", "/batch-control/history/?kind=requests", "R27-D2-F-03-filter-requests")
    sta = (st or {}).get("status")
    vals = [o["value"] for o in (sta or {}).get("options") or []]
    check("F", "D2 #18.3 History > Requests: Status is a dropdown offering Any and every RequestStatus by name, each "
          "once; no Result filter", is_dropdown(sta) and sorted(vals[1:]) == sorted(statuses)
          and len(vals) == len(statuses) + 1 and (st or {}).get("result") is None,
          values=vals, request_statuses=statuses)
    code, st = form_state("approver-1", "/batch-control/history/?kind=changes", "R27-D2-F-04-filter-changes")
    check("F", "D2 #18.3 History > Changes offers neither a Result nor a Status filter",
          st is not None and st.get("result") is None and st.get("status") is None, form=st)

    # choose in the dropdown and press Filter, as a person does
    s = Session("approver-1")
    s.go(f"/batch-control/history/?kind=runs&job={P}")
    rows0 = s.page.locator("#main-panel table tbody tr").all_inner_texts()
    sel = s.page.locator("#main-panel form:has(input[name=from]) select[name=result]")
    url1 = rows1 = url2 = rows2 = None
    if sel.count():
        sel.select_option("FAILURE")
        with s.page.expect_navigation(timeout=20000):
            s.page.locator("#main-panel form:has(input[name=from]) button[type=submit]").first.click()
        url1, rows1 = s.page.url, s.page.locator("#main-panel table tbody tr").all_inner_texts()
        s.shot("#main-panel", "R27-D2-F-05-runs-filtered-failure")
        s.page.locator("#main-panel form:has(input[name=from]) select[name=result]").select_option("")
        with s.page.expect_navigation(timeout=20000):
            s.page.locator("#main-panel form:has(input[name=from]) button[type=submit]").first.click()
        url2, rows2 = s.page.url, s.page.locator("#main-panel table tbody tr").all_inner_texts()
    dropdown = sel.count()
    s.done()
    q1 = parse_qs(urlparse(url1 or "").query)
    has = lambda rows, job: any(re.search(rf"(?<![\w-]){re.escape(job)}(?![\w-])", r) for r in rows or [])  # noqa: E731
    check("F", "D2 #18.3 choosing FAILURE in the Result dropdown and pressing Filter leads to result=FAILURE listing "
          "r27-d2-fail and not r27-d2-ok", bool(dropdown) and q1.get("result") == ["FAILURE"] and has(rows1, FAIL)
          and not has(rows1, OK), url=url1, rows=len(rows1 or []), dropdown=dropdown)
    check("F", "D2 #18.3 choosing Any again lists both runs", has(rows2, FAIL) and has(rows2, OK),
          url=url2, rows=len(rows2 or []))
    check("F", "guard: unfiltered, History > Runs lists r27-d2-ok and r27-d2-fail", has(rows0, FAIL) and has(rows0, OK),
          rows=len(rows0))
    s = Session("approver-1")
    s.go(f"/batch-control/history/?kind=incidents&job={P}")
    sel = s.page.locator("#main-panel form:has(input[name=from]) select[name=status]")
    url3 = rows3 = None
    if sel.count():
        sel.select_option("OPEN")
        with s.page.expect_navigation(timeout=20000):
            s.page.locator("#main-panel form:has(input[name=from]) button[type=submit]").first.click()
        url3, rows3 = s.page.url, s.page.locator("#main-panel table tbody tr").all_inner_texts()
        s.shot("#main-panel", "R27-D2-F-06-incidents-filtered-open")
    s.done()
    check("F", "D2 #18.3 choosing OPEN in the incidents' Status dropdown leads to status=OPEN listing r27-d2-fail and "
          "not the acknowledged r27-d2-fail2", parse_qs(urlparse(url3 or "").query).get("status") == ["OPEN"]
          and has(rows3, FAIL) and not has(rows3, FAIL2), url=url3, rows=len(rows3 or []))

    odd_r, odd_s = "WEIRD<b>x</b>", 'bogus"q'
    code, st = form_state("approver-1", f"/batch-control/history/?kind=runs&result={quote(odd_r)}",
                          "R27-D2-F-07-runs-kept-value")
    res = (st or {}).get("result") or {}
    opts = res.get("options") or []
    check("F", "D2 #18.3 a hand-edited result=WEIRD<b>x</b> stays selected as one extra option, escaped (no element in "
          "the select), the known results still offered (SPEC 6)", res.get("tag") == "select"
          and [o["value"] for o in opts if o["selected"]] == [odd_r] and sum(o["value"] == odd_r for o in opts) == 1
          and res.get("bold") == 0 and set(COMMON_RESULTS) <= {o["value"] for o in opts}, result=res)
    code, st = form_state("approver-1", f"/batch-control/history/?kind=requests&status={quote(odd_s)}",
                          "R27-D2-F-08-requests-kept-value")
    sta = (st or {}).get("status") or {}
    opts = sta.get("options") or []
    check("F", "D2 #18.3 a hand-edited status=bogus\"q stays selected as typed (attribute escaped), next to Any and every "
          "request status", sta.get("tag") == "select" and [o["value"] for o in opts if o["selected"]] == [odd_s]
          and len(opts) == len(statuses) + 2, status=sta)


def sec_G():
    r = api("approver-1", f"/batch-control/history/?kind=runs&job={P}&result=FAILURE")
    t = lib.text_of(r.text)
    check("G", "guard: the URL token result=FAILURE still filters History > Runs (r27-d2-fail listed, r27-d2-ok not)",
          r.status_code == 200 and re.search(rf"(?<![\w-]){FAIL}(?![\w-])", t)
          and not re.search(rf"(?<![\w-]){OK}(?![\w-])", t), status=r.status_code)
    rows = csv_rows(f"/batch-control/history/runs.csv?job={P}&result=FAILURE")
    check("G", "guard: runs.csv with result=FAILURE keeps the enum names (every row FAILURE)",
          rows and all("FAILURE" in r.values() for r in rows), rows=len(rows), first=rows[0] if rows else None)


def cleanup():
    note("cleanup", "restore", swept=lib.sweep("requester", P))


lib.run(sys.argv, {"A": sec_A, "W": sec_W, "L": sec_L, "N": sec_N, "I": sec_I, "C": sec_C, "F": sec_F, "G": sec_G},
        cleanup)
