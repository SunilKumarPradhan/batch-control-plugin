"""e2e-27 D2 (Wave D, issue #18 items 3 and 2; TEST-MATRIX T-UI-250..269a, note 361): the History filter's Result and
Status are jenkins-select dropdowns; every request, grant, activation and incident status and every run cause is shown
as a readable label in an element carrying data-batch-control-status=<ENUM>; request and incident statuses are colour
badges (class batch-control-status, data-batch-control-tone), run causes are plain text.

usage: python labels_filters.py [ABRDFGK]   rows: out/labels_filters.jsonl, shots: screenshots/run-27/R27-D2-*.png
The records come from r27/d2_fixture.py (every RequestStatus for run requests, the reachable ones for window and
activation requests, the three IncidentStatus values, every CauseType, five results). What only a browser's rendering
shows (colours in both themes, geometry, Content-Security-Policy, forced colours) is r27/status_badges.py.

Each account reads its screens in one browser context of its own (one login, the screens one after the other); the
server state is read from the store and the CSV exports. A check named "D2 #18.x" fails on a plugin without D2; one
named "guard" holds there too.

A  arrangement (d2_fixture): every state reached, read from the store.
B  #18.2 as admin, every screen that shows a status: the seven run request pages, the eight window request pages, the
   seven activation request pages, the three incident pages (with their history rows), the four lists, History >
   Requests and > Incidents, the Run Dashboard and History > Runs. Per screen: every status element shows its label as
   its whole text (the contract's wording: "Pending", "Approved, waiting to run" for a run request, "Executed",
   "Approved request", "Timer"; in the Ended tables the list's own wording) and no table shows a raw enum name; every
   request and incident status is a badge with the contract's tone (PENDING warning, APPROVED info, EXECUTED success,
   REJECTED danger, CANCELLED/EXPIRED/INVALIDATED neutral; OPEN danger, ACKNOWLEDGED warning, RESOLVED success; an
   APPROVED request in the Ended table of the grants and activations lists neutral), a run cause is plain (no class, no
   tone) and nothing else has the class or a tone; one badge per row, no style attribute on or in a badge, the plugin's
   stylesheet linked; the screen shows the statuses the fixture made.
R  the same checks as manager, approver-1, requester and auditor (ViewHistory only) on one screen of each kind they may
   open; on a screen they may not open they get an error status and nothing of a status (no hook, no badge class).
D  guards, data stays data: requests.csv, incidents.csv and runs.csv hold enum names in their status and cause columns
   and no tone word; the monthly JSON summary answers 200 without a label or a tone; status=warning lists nothing.
F  #18.3 the filter form per kind and per account that may open History: no free-text result or status field; Result
   (runs, incidents) and Status (incidents, requests) are jenkins-select dropdowns starting with "Any"; the option
   values are the enum names and the texts readable labels (a status option reads what the table shows for it).
G  #18.3 the dropdowns in use (approver-1): every option of every dropdown, chosen and submitted with the Filter button,
   leads to a URL carrying the token and a table whose rows all carry it (premise: without the filter there are rows
   that do not), the same rows as the CSV export link of that view; "Any" lists everything again; a filter combined
   with from/to dates; paging under a filter (the pager links keep the token and page 2 holds only matching rows);
   keyboard use (Tab to the dropdown, type to select, Enter submits); the form submits with GET, without a crumb in the
   URL and without any POST.
K  #18.3 kept input: a hand-edited value with markup stays one extra selected option, escaped, is not applied (the
   page says so) and filters nothing; a token-shaped unknown value is kept and lists nothing; a known value in lower
   case selects its option. Guard: the URL tokens of before still filter.
cleanup: the requester's pending r27-d2 requests cancelled, windows revoked, queue items cancelled."""
import os
import re
import sys
from urllib.parse import quote, urlparse, parse_qs

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import d2_fixture as F  # noqa: E402
import lib  # noqa: E402
from lib import api, check, note, Session, norm  # noqa: E402

lib.LOGNAME[0] = "labels_filters"
P, J = F.P, F.J
S = {}
LABEL = {"PENDING": "Pending", "APPROVED": "Approved", "REJECTED": "Rejected", "CANCELLED": "Cancelled",
         "EXPIRED": "Expired", "EXECUTED": "Executed", "INVALIDATED": "Invalidated", "OPEN": "Open",
         "ACKNOWLEDGED": "Acknowledged", "RESOLVED": "Resolved", "USER": "User", "TIMER": "Timer",
         "UPSTREAM": "Upstream job", "APPROVED_REQUEST": "Approved request", "SCM": "SCM change", "OTHER": "Other"}
WAITING = "Approved, waiting to run"
TONE = {"PENDING": "warning", "APPROVED": "info", "EXECUTED": "success", "REJECTED": "danger", "CANCELLED": "neutral",
        "EXPIRED": "neutral", "INVALIDATED": "neutral", "OPEN": "danger", "ACKNOWLEDGED": "warning", "RESOLVED": "success"}
CAUSES = ("USER", "TIMER", "UPSTREAM", "APPROVED_REQUEST", "SCM", "OTHER")
TONES = ("warning", "info", "success", "danger", "neutral")
RESULTS = ["SUCCESS", "UNSTABLE", "FAILURE", "NOT_BUILT", "ABORTED"]
# The wording of the Ended tables (note 361 points 7 and 8): the grants list says how a request or its window ended.
GRANTS_ENDED = {"REJECTED": r"Rejected by \S+", "CANCELLED": r"Cancelled by \S+", "EXPIRED": r"Expired without a decision",
                "APPROVED": r"Expired|Revoked by \S+|Revoked \(its item was deleted\) by \S+"}
ACTIVATIONS_ENDED = {"APPROVED": r"Approved \(superseded\)"}
PAGE_JS = """() => { const n = t => (t || '').replace(/\\s+/g, ' ').trim();
  const hooked = [...document.querySelectorAll('[data-batch-control-status]')].map(e => { const tr = e.closest('tr'), table = e.closest('table');
    return {enum: e.getAttribute('data-batch-control-status'), text: n(e.textContent), tag: e.tagName.toLowerCase(),
      badge: e.classList.contains('batch-control-status'), tone: e.getAttribute('data-batch-control-tone'),
      style: e.hasAttribute('style') || !!e.querySelector('[style]'), elements: e.querySelectorAll('*').length,
      list: table ? table.getAttribute('data-batch-control-list') : null,
      rowStatuses: tr ? tr.querySelectorAll('[data-batch-control-status]').length : 1,
      rowBadges: tr ? tr.querySelectorAll('.batch-control-status').length : (e.classList.contains('batch-control-status') ? 1 : 0)}; });
  const stray = [...document.querySelectorAll('.batch-control-status, [data-batch-control-tone]')]
    .filter(e => !e.hasAttribute('data-batch-control-status') || !e.classList.contains('batch-control-status') || !e.getAttribute('data-batch-control-tone'))
    .filter(e => e.classList.contains('batch-control-status') || e.getAttribute('data-batch-control-tone'))
    .map(e => e.outerHTML.slice(0, 160));
  const outside = [...document.querySelectorAll('#main-panel table')].map(t => { const c = t.cloneNode(true);
    c.querySelectorAll('[data-batch-control-status]').forEach(e => e.remove()); return n(c.textContent); }).join(' | ');
  return {hooked, stray, tables: outside,
    styleElements: [...document.querySelectorAll('style')].filter(s => /batch-control-status|data-batch-control-tone/.test(s.textContent)).length,
    sheets: [...document.querySelectorAll('link[rel=stylesheet]')].map(l => l.getAttribute('href')).filter(h => /batchcontrol|batch-control/.test(h || '')),
    markers: document.documentElement.outerHTML.includes('data-batch-control-status') || document.documentElement.outerHTML.includes('batch-control-status')}; }"""


def wording(e, path):
    """The accepted whole text of a status element: the contract's wording by screen (a regular expression)."""
    enum, ended = e["enum"], e["list"] == "ended"
    if ended and path == "/batch-control/grants/" and enum in GRANTS_ENDED:
        return GRANTS_ENDED[enum]
    if ended and path == "/batch-control/activations/" and enum in ACTIVATIONS_ENDED:
        return ACTIVATIONS_ENDED[enum]
    run = path.startswith("/batch-control/requests/") or "kind=requests" in path
    if enum == "APPROVED" and run:
        return re.escape(WAITING)
    return re.escape(LABEL.get(enum, "\0"))


def tone_of(e, path):
    """The contract's tone: by the constant; APPROVED is neutral in the Ended table of the grants and activations lists."""
    if e["enum"] == "APPROVED" and e["list"] == "ended" and path in ("/batch-control/grants/", "/batch-control/activations/"):
        return "neutral"
    return TONE.get(e["enum"])


def judge(sec, who, path, what, s, want, status=200):
    """The D2 checks of one screen as `s` shows it. `want`: the enum names the screen must show at least once."""
    p = s.page.evaluate(PAGE_JS)
    hooked = p["hooked"]
    bad_label = [e for e in hooked if not re.fullmatch(wording(e, path), e["text"]) or e["elements"]]
    raw = sorted({x for x in re.findall(r"(?<![A-Za-z_])(" + "|".join(sorted(LABEL, key=len, reverse=True)) + r")(?![A-Za-z_])",
                                        p["tables"])})
    for e in hooked:  # an observation, not a verdict: a label that holds its constant's name as a word ("SCM change")
        if re.search(r"(?<![A-Za-z_])" + re.escape(e["enum"]) + r"(?![A-Za-z_])", e["text"]):
            S.setdefault("label_holds_name", set()).add(f"{e['enum']}={e['text']}")
    # The Grants list's Ended table showed its own wording ("Rejected by ...", "Expired without a decision") in a hooked cell
    # before D2 as well, so on that screen the label check is a guard; the badge checks below are D2's.
    name = "guard (the Grants list's wording predates D2)" if path == "/batch-control/grants/" else "D2 #18.2"
    check(sec, f"{name} labels: {what} shows every status and cause as its readable label, the whole text of an element "
          f"carrying data-batch-control-status, and no table shows a raw enum name outside such an element ({who})",
          status == 200 and bool(hooked) and not bad_label and not raw, status=status, hooked=len(hooked),
          labels=sorted({f"{e['enum']}={e['text']}" for e in hooked})[:12], wrong=bad_label[:3], raw_in_tables=raw)
    statuses = [e for e in hooked if e["enum"] in TONE]
    causes = [e for e in hooked if e["enum"] in CAUSES]
    not_badge = [e for e in statuses if not e["badge"] or e["tone"] != tone_of(e, path)]
    cause_badge = [e for e in causes if e["badge"] or e["tone"]]
    unknown = [e for e in hooked if e["enum"] not in TONE and e["enum"] not in CAUSES]
    check(sec, f"D2 #18.2 badges: on {what} every request and incident status is a badge with the contract's tone "
          "(APPROVED neutral in an Ended table of the grants or activations list), a run cause has neither the class nor "
          f"a tone, and nothing else has the class or a tone ({who})",
          status == 200 and bool(hooked) and not not_badge and not cause_badge and not p["stray"] and not unknown,
          tones=sorted({f"{e['enum']}{'/ended' if e['list'] == 'ended' else ''}={e['tone']}" for e in statuses})[:12],
          wrong=not_badge[:3], cause_badges=cause_badge[:3], stray=p["stray"][:3], unknown=unknown[:3])
    rows = [e for e in statuses if e["rowStatuses"] != 1 or e["rowBadges"] != 1]
    styled = [e for e in statuses if e["style"]]
    check(sec, f"D2 #18.2 badges: on {what} each row holds one badge, no badge has a style attribute on or inside it, no "
          f"style element names the badge, and the page links the plugin's stylesheet ({who})",
          status == 200 and bool(hooked) and not rows and not styled and p["styleElements"] == 0
          and (not statuses or len(p["sheets"]) >= 1),
          badges=len(statuses), rows_with_more=rows[:3], styled=styled[:3], style_elements=p["styleElements"],
          stylesheets=p["sheets"][:2])
    shown = {e["enum"] for e in hooked if e["badge"] or (e["enum"] in CAUSES and e not in bad_label)}
    check(sec, f"D2 #18.2 {what} shows " + ", ".join(sorted(want)) + f", each as a badge (a cause as its label) ({who})",
          set(want) <= shown,
          missing=sorted(set(want) - shown), shown=sorted(shown))
    return p


# ---------------------------------------------------------------- A
def sec_A():
    S.update(F.arrange())
    st, ex = F.states(S), F.expected(S)
    check("A", "arrangement (d2_fixture): a run request in each of the seven statuses, window requests PENDING, REJECTED, "
          "CANCELLED, EXPIRED and four APPROVED (window open, expired, revoked, item deleted), activation requests PENDING, "
          "REJECTED, CANCELLED, EXPIRED, INVALIDATED, APPROVED in effect and superseded ones, incidents OPEN, ACKNOWLEDGED, "
          "RESOLVED (server state)", st == ex and len(S["superseded"]) >= 1,
          wrong={k: (st.get(k), v) for k, v in ex.items() if st.get(k) != v}, reused=S.get("reused"), codes=S.get("codes"))
    rows = F.csv_rows(f"/batch-control/history/runs.csv?job={P}")
    causes, results = {r.get("causeType") for r in rows}, {r.get("result") for r in rows}
    check("A", "arrangement: the run history of the r27-d2 jobs holds every cause (USER, TIMER, UPSTREAM, APPROVED_REQUEST, "
          "SCM, OTHER) and the results SUCCESS, UNSTABLE, FAILURE, NOT_BUILT, ABORTED (runs.csv)",
          set(CAUSES) <= causes and set(RESULTS) <= results, causes=sorted(causes), results=sorted(results),
          builds={k: v.get("result") for k, v in S["build"].items()})


# ---------------------------------------------------------------- the screens
def screens():
    """(key, path, what, statuses it must show) for every screen of the badge contract's point 1."""
    out = []
    for st, rid in S["run"].items():
        out.append((f"run-{st}", f"/batch-control/requests/{rid}/", f"the {st} run request page", {st}))
    for st, rid in S["grant"].items():
        out.append((f"grant-{st.replace(' ', '-')}", f"/batch-control/grants/{rid}/", f"the window request page ({st})",
                    {st.split()[0]}))
    for st, rid in S["activation"].items():
        out.append((f"activation-{st}", f"/batch-control/activations/{rid}/", f"the {st} activation request page", {st}))
    out.append(("activation-superseded", f"/batch-control/activations/{S['superseded'][0]}/",
                "the page of an approved activation request that was replaced", {"APPROVED"}))
    for st in F.INCIDENT_STATUSES:
        trail = {"OPEN": {"OPEN"}, "ACKNOWLEDGED": {"OPEN", "ACKNOWLEDGED"}, "RESOLVED": set(F.INCIDENT_STATUSES)}[st]
        out.append((f"incident-{st}", f"/batch-control/incidents/{S['incident'][st]}/", f"the {st} incident page", trail))
    out += [("list-requests", "/batch-control/requests/", "the Run Requests list",
             {"REJECTED", "CANCELLED", "EXPIRED", "EXECUTED", "INVALIDATED"}),
            ("list-grants", "/batch-control/grants/", "the Grants list", {"REJECTED", "CANCELLED", "EXPIRED", "APPROVED"}),
            ("list-activations", "/batch-control/activations/", "the Activations list",
             {"REJECTED", "CANCELLED", "EXPIRED", "INVALIDATED", "APPROVED"}),
            ("list-incidents", "/batch-control/incidents/", "the Incidents list", set(F.INCIDENT_STATUSES)),
            ("history-requests", f"/batch-control/history/?kind=requests&job={P}", "History > Requests", set(F.REQUEST_STATUSES)),
            ("history-incidents", f"/batch-control/history/?kind=incidents&job={P}", "History > Incidents",
             set(F.INCIDENT_STATUSES)),
            ("dashboard", "/batch-control/dashboard/", "the Run Dashboard", {"APPROVED_REQUEST"}),
            ("history-runs", f"/batch-control/history/?kind=runs&job={P}", "History > Runs", set(CAUSES))]
    return out


def sec_B():
    s = Session("admin")
    for key, path, what, want in screens():
        r = s.go(path)
        p = judge("B", "admin", path, what, s, want, r.status if r else None)
        if key in ("history-requests", "list-grants", "list-activations", "incident-RESOLVED", "history-runs", "run-APPROVED"):
            lib.page_shot(s, f"R27-D2-B-{key}")
        if key == "list-grants":
            ended = [e for e in p["hooked"] if e["list"] == "ended" and e["enum"] == "APPROVED"]
            texts = sorted({e["text"] for e in ended})
            check("B", "D2 #18.2 (T-UI-269): in the Ended table of the Grants list the windows that expired, were revoked "
                  "and ended with their item read 'Expired', 'Revoked by admin' and 'Revoked (its item was deleted) by "
                  f"{F.LONG_ADMIN}', each one neutral badge carrying APPROVED; the open window's row has no badge",
                  {"Expired", "Revoked by admin", f"Revoked (its item was deleted) by {F.LONG_ADMIN}"} <= set(texts)
                  and all(e["tone"] == "neutral" and e["badge"] for e in ended)
                  and not [e for e in p["hooked"] if e["list"] not in ("ended",)], texts=texts,
                  outside_ended=[e for e in p["hooked"] if e["list"] != "ended"][:3])
        if key == "list-activations":
            sup = [e for e in p["hooked"] if e["list"] == "ended" and e["enum"] == "APPROVED"]
            check("B", "D2 #18.2 (T-UI-269a): in the Ended table of the Activations list an approved request that a later "
                  "one replaced reads 'Approved (superseded)' in one neutral badge carrying APPROVED",
                  len(sup) >= len(S["superseded"]) and all(e["text"] == "Approved (superseded)" and e["tone"] == "neutral"
                                                           and e["badge"] for e in sup), found=sup[:3])
    s.done()
    note("B", "the labels as shown (admin)", labels=LABEL, run_request_approved=WAITING,
         labels_holding_their_constant_as_a_word=sorted(S.get("label_holds_name", ())))


# ---------------------------------------------------------------- R: the other accounts
ROLE_SCREENS = ("run-PENDING", "grant-PENDING", "activation-PENDING", "incident-ACKNOWLEDGED", "list-requests",
                "list-grants", "list-activations", "list-incidents", "history-requests", "history-incidents",
                "dashboard", "history-runs")
REQUEST_SIDE = ("run-", "grant-", "activation-", "list-requests", "list-grants", "list-activations")


def may_open(who, key):
    """SPEC 2: the request screens need Request, RequestGrant or Approve (or Manage); the history family (incidents,
    History, dashboard) needs ViewHistory (or Manage). D-38c: the Activations list opens for everyone admitted to
    Batch Control, with the rows the viewer may see, possibly none ("empty")."""
    request_side = key.startswith(REQUEST_SIDE)
    if who == "auditor" and key == "list-activations":
        return "empty"
    return {"manager": True, "approver-1": True, "requester": request_side, "auditor": not request_side}[who]


def sec_R():
    table = {k: (path, what, want) for k, path, what, want in screens()}
    for who in ("manager", "approver-1", "requester", "auditor"):
        s = Session(who)
        opened, refused = [], []
        for key in ROLE_SCREENS:
            path, what, want = table[key]
            r = s.go(path)
            status = r.status if r else None
            if may_open(who, key) == "empty":
                p = s.page.evaluate(PAGE_JS)
                opened.append(key + " (no rows)")
                check("R", f"guard (D-38c): {who} opens {what} (200) and is shown none of the requester's requests: no "
                      "element carrying a status and no badge", status == 200 and not p["hooked"] and not p["stray"],
                      status=status, hooked=len(p["hooked"]))
            elif may_open(who, key):
                opened.append(key)
                judge("R", who, path, what, s, want, status)
            else:
                refused.append((key, status))
                p = s.page.evaluate(PAGE_JS)
                check("R", f"guard: {who} may not open {what}: an error status and nothing of a status in the page (no "
                      "element carrying data-batch-control-status, no badge class)", status is not None and status >= 400
                      and not p["hooked"] and not p["stray"] and not p["markers"], status=status, hooked=len(p["hooked"]))
        lib.page_shot(s, f"R27-D2-R-{who}-last-screen")
        s.done()
        note("R", f"{who}: screens read", opened=opened, refused=refused)


# ---------------------------------------------------------------- D: data stays data
def sec_D():
    req, inc, runs = (F.csv_rows(f"/batch-control/history/{n}.csv?job={P}") for n in ("requests", "incidents", "runs"))
    texts = {n: F.csv_text(f"/batch-control/history/{n}.csv?job={P}") for n in ("requests", "incidents", "runs")}
    words = lambda t: sorted({w for w in ("warning", "info", "danger", "neutral", "batch-control-status", "tone")  # noqa: E731
                              if re.search(r"(?<![A-Za-z-])" + w + r"(?![A-Za-z-])", t)})
    labels = [x for x in (WAITING, "Approved request", "Approved (superseded)", "Upstream job", "SCM change")
              if any(x in t for t in texts.values())]
    check("D", "guard: requests.csv, incidents.csv and runs.csv keep the enum names in their status and causeType columns "
          "(all seven request statuses, the three incident statuses, the six causes) and hold no label and no tone word",
          {r.get("status") for r in req} == set(F.REQUEST_STATUSES) and {r.get("status") for r in inc} == set(F.INCIDENT_STATUSES)
          and {r.get("causeType") for r in runs} == set(CAUSES) and not any(words(t) for t in texts.values()) and not labels,
          request_statuses=sorted({r.get("status") for r in req}), incident_statuses=sorted({r.get("status") for r in inc}),
          causes=sorted({r.get("causeType") for r in runs}), tone_words={k: words(v) for k, v in texts.items()}, labels=labels)
    month = lib.gv("return java.time.YearMonth.now().toString()")
    r = api("admin", f"/batch-control/history/summary?month={month}")
    leaked = [x for x in list(LABEL.values()) + [WAITING] if re.search(r"(?<![A-Za-z])" + re.escape(x) + r"(?![A-Za-z])", r.text)]
    tones = [w for w in ("warning", "info", "danger", "neutral", "tone") if re.search(r"(?<![A-Za-z])" + w + r"(?![A-Za-z])", r.text)]
    check("D", "guard: the monthly JSON summary answers 200 and carries neither a screen label nor a tone",
          r.status_code == 200 and not leaked and not tones, status=r.status_code, labels=leaked, tones=tones,
          head=r.text[:160])
    a = api("approver-1", f"/batch-control/history/?kind=requests&job={P}&status=warning")
    b = api("approver-1", f"/batch-control/history/?kind=incidents&job={P}&status=danger")
    hooks = lambda t: len(re.findall(r'<td[^>]*>\s*<span[^>]*data-batch-control-status=', t))  # noqa: E731
    check("D", "guard: a tone is not a filter value: status=warning lists no request and status=danger no incident",
          a.status_code == 200 and b.status_code == 200 and hooks(a.text) == 0 and hooks(b.text) == 0,
          requests=hooks(a.text), incidents=hooks(b.text))


# ---------------------------------------------------------------- F, G, K: the filter
FORM = "#main-panel form:has(input[name=from])"
FORM_JS = """() => { const from = document.querySelector('#main-panel input[name="from"]'); const f = from && from.form;
  if (!f) return null; const n = t => (t || '').replace(/\\s+/g, ' ').trim();
  const ctl = name => { const all = [...f.querySelectorAll(`[name="${name}"]`)]; const e = all.find(x => x.type !== 'hidden');
    if (!e) return null; let styled = false;
    for (let p = e; p && p !== f && !styled; p = p.parentElement) styled = /(^|\\s)jenkins-select(__input)?(\\s|$)/.test(p.className || '');
    const label = e.id ? document.querySelector(`label[for="${e.id}"]`) : null;
    return {tag: e.tagName.toLowerCase(), type: e.type, styled, multiple: !!e.multiple, label: label ? n(label.textContent) : null,
      options: e.tagName === 'SELECT' ? [...e.options].map(o => ({value: o.value, text: n(o.textContent), selected: o.selected})) : null,
      elements: e.querySelectorAll(':not(option)').length, value: e.value}; };
  const hidden = name => [...f.querySelectorAll(`input[type=hidden][name="${name}"]`)].map(x => x.value);
  return {method: (f.getAttribute('method') || 'get').toLowerCase(), result: ctl('result'), status: ctl('status'),
    hidden: {result: hidden('result'), status: hidden('status')},
    free_text: [...f.querySelectorAll('input:not([type=hidden])')].filter(x => ['result', 'status'].includes(x.name)).length,
    notes: [...f.querySelectorAll('[data-batch-control-field-error]')].map(x => [x.getAttribute('data-batch-control-field-error'), n(x.textContent)])}; }"""
ROWS_JS = """() => { const n = t => (t || '').replace(/\\s+/g, ' ').trim();
  const t = [...document.querySelectorAll('#main-panel table')].find(x => x.querySelector('thead th'));  // not the Monthly Summary
  const headers = t ? [...t.querySelectorAll('thead th')].map(h => n(h.textContent)) : [];
  const ri = headers.indexOf('Result');
  return {headers, rows: [...(t ? t.querySelectorAll('tbody tr') : [])].map(tr => { const tds = [...tr.children];
      const h = tr.querySelector('[data-batch-control-status]');
      return {status: h ? h.getAttribute('data-batch-control-status') : null, result: ri >= 0 && tds[ri] ? n(tds[ri].textContent) : null,
              text: n(tr.innerText).slice(0, 140)}; }),
    summary: n(([...document.querySelectorAll('#main-panel *')].find(e => e.children.length === 0 && /matching record/.test(e.textContent)) || {}).textContent),
    empty: t ? null : n(document.querySelector('#main-panel').innerText).replace(/.*Filter /, '').replace(/ Download.*/, '').slice(0, 200),
    csv: [...document.querySelectorAll('#main-panel a')].map(a => a.getAttribute('href') || '').filter(h => /\\.csv/.test(h)),
    pager: [...document.querySelectorAll('#main-panel a')].filter(a => /[?&]page=\\d+/.test(a.getAttribute('href') || '')).map(a => [n(a.textContent), a.getAttribute('href')])}; }"""
KINDS = {"runs": ("result",), "incidents": ("result", "status"), "requests": ("status",), "changes": ()}


def is_dropdown(c):
    o = (c or {}).get("options") or []
    return bool(c and c["tag"] == "select" and c["styled"] and not c["multiple"] and o and o[0]["value"] == ""
                and o[0]["text"] == "Any" and c["elements"] == 0)


def readable(text, value):
    return bool(text) and value not in text and "_" not in text and text[0].isupper() and text != text.upper()


def sec_F():
    statuses = lib.facts(f"return groovy.json.JsonOutput.toJson({lib.BC}.model.RequestStatus.values()*.name())")
    want_values = {("runs", "result"): None, ("incidents", "result"): None,
                   ("incidents", "status"): F.INCIDENT_STATUSES, ("requests", "status"): statuses}
    for who in ("approver-1", "admin", "manager", "auditor"):
        s = Session(who)
        forms = {}
        for kind in KINDS:
            r = s.go(f"/batch-control/history/?kind={kind}")
            forms[kind] = (r.status if r else None, s.page.evaluate(FORM_JS))
            if who == "approver-1":
                s.shot(FORM, f"R27-D2-F-filter-{kind}")
        s.done()
        ok = all(code == 200 and st and st["free_text"] == 0 and st["method"] == "get"
                 and all(is_dropdown(st[c]) and st[c]["options"][0]["selected"] for c in KINDS[kind])
                 and all(st[c] is None for c in ("result", "status") if c not in KINDS[kind]) for kind, (code, st) in forms.items())
        check("F", f"D2 #18.3 the filter form ({who}): no free-text result or status field on any kind; Result is a "
              "jenkins-select dropdown on Runs and Incidents and Status on Incidents and Requests, single-valued, first "
              "option 'Any' with an empty value, selected when the URL names none; Changes has neither", ok,
              forms={k: {"status": c, "result": (st or {}).get("result") and st["result"]["tag"],
                         "status_control": (st or {}).get("status") and st["status"]["tag"],
                         "free_text": (st or {}).get("free_text")} for k, (c, st) in forms.items()})
        if who != "approver-1":
            continue
        opts = {(k, c): forms[k][1][c]["options"] for k in KINDS for c in KINDS[k]
                if forms[k][1] and forms[k][1][c] and forms[k][1][c]["options"]}
        for (kind, c), o in opts.items():
            values = [x["value"] for x in o[1:]]
            want = want_values[(kind, c)]
            if want is None:
                good = {"SUCCESS", "UNSTABLE", "FAILURE", "ABORTED"} <= set(values) and set(values) <= set(RESULTS)
            else:
                good = values == want if kind == "incidents" else sorted(values) == sorted(want)
            check("F", f"D2 #18.3 History > {kind.capitalize()}: the {c.capitalize()} dropdown's values are the enum names, each "
                  "once (result names with SUCCESS, UNSTABLE, FAILURE and ABORTED among them; exactly OPEN, ACKNOWLEDGED, "
                  "RESOLVED in this order for incidents; every RequestStatus for requests) and its texts are readable "
                  "labels, each once", good and len(values) == len(set(values))
                  and all(readable(x["text"], x["value"]) for x in o[1:]) and len({x["text"] for x in o}) == len(o),
                  options=[(x["value"], x["text"]) for x in o])
        st_req = {x["value"]: x["text"] for x in opts.get(("requests", "status"), [])}
        st_inc = {x["value"]: x["text"] for x in opts.get(("incidents", "status"), [])}
        check("F", "D2 #18.3 a Status option reads what the table shows for that status (requests: 'Approved, waiting to "
              "run' for APPROVED; incidents: the incident labels)",
              bool(st_req) and all(st_req.get(k) == (WAITING if k == "APPROVED" else LABEL[k]) for k in statuses)
              and all(st_inc.get(k) == LABEL[k] for k in F.INCIDENT_STATUSES), requests=st_req, incidents=st_inc)
        note("F", "the Result dropdown's wording", runs=[(x["value"], x["text"]) for x in opts.get(("runs", "result"), [])],
             labels=[forms[k][1][c]["label"] for k in KINDS for c in KINDS[k] if forms[k][1] and forms[k][1][c]])
        for kind, c in (("runs", "result"), ("incidents", "result"), ("incidents", "status"), ("requests", "status")):
            if (kind, c) not in opts:
                check("F", f"D2 #18.3 History > {kind.capitalize()}: the {c.capitalize()} dropdown's values are the enum names "
                      "(no dropdown on this page)", False, control=forms[kind][1] and forms[kind][1][c])
    for who in ("requester", "nobc"):
        r = api(who, "/batch-control/history/?kind=runs")
        check("F", f"guard: {who} (no ViewHistory) gets no History page and no filter form", r.status_code >= 400
              and 'name="result"' not in r.text and 'name="status"' not in r.text, status=r.status_code)


def submit(s, control, value, how="button"):
    """Chooses `value` in the dropdown `control` and submits the filter form; returns what the navigation did."""
    seen = []
    if s.page.locator(f"{FORM} select[name={control}]").count() == 0:  # no dropdown (a build before D2)
        return None
    listener = lambda r: seen.append((r.method, r.url)) if r.is_navigation_request() or r.method != "GET" else None  # noqa: E731
    s.page.on("request", listener)
    s.page.locator(f"{FORM} select[name={control}]").select_option(value)
    with s.page.expect_navigation(timeout=20000):
        if how == "button":
            s.page.locator(f"{FORM} button[type=submit]").first.click()
        else:
            s.page.locator(f"{FORM} select[name={control}]").press("Enter")
    s.page.wait_for_load_state("load")
    s.page.remove_listener("request", listener)
    return seen


def query(url):
    return {k: v[0] for k, v in parse_qs(urlparse(url).query, keep_blank_values=True).items()}


def view(s):
    v = s.page.evaluate(ROWS_JS)
    m = re.search(r"\((\d+) matching", v.get("summary") or "")
    v["matching"] = int(m.group(1)) if m else None
    return v


def csv_of(who, s, v, name):
    """The rows of the view's own CSV export link (resolved against the page), read as `who`."""
    href = next((h for h in v["csv"] if h.startswith(name + ".csv")), None)
    if not href:
        return None, None
    base = s.page.url.split("?")[0]
    path = (base[: base.rindex("/") + 1] + href).replace(lib.BASE, "")
    return href, F.csv_rows(path, who)


def sec_G():
    who = "approver-1"
    s = Session(who)
    # ---- every option of every dropdown
    for kind, control, column, options in (("runs", "result", "result", RESULTS), ("incidents", "result", "result", RESULTS),
                                           ("incidents", "status", "status", F.INCIDENT_STATUSES),
                                           ("requests", "status", "status", F.REQUEST_STATUSES)):
        s.go(f"/batch-control/history/?kind={kind}&job={P}")
        base = view(s)
        all_values = [r.get(column) for r in F.csv_rows(f"/batch-control/history/{kind}.csv?job={P}", who)]
        bad, detail = [], {}
        for value in options:
            if s.page.locator(f"{FORM} select[name={control}]").count() == 0:
                bad.append((value, "no dropdown"))
                break
            if value not in [o.get_attribute("value") for o in s.page.locator(f"{FORM} select[name={control}] option").all()]:
                detail[value] = "not offered"
                continue
            seen = submit(s, control, value)
            v, q = view(s), query(s.page.url)
            got = [r[column] for r in v["rows"]]
            href, exported = csv_of(who, s, v, kind)
            n = all_values.count(value)
            matching = v["matching"] if v["matching"] is not None else len(got)
            detail[value] = {"rows": len(got), "matching": matching, "expected": n, "csv": len(exported or [])}
            selected = s.page.locator(f"{FORM} select[name={control}]").input_value()
            if not (q.get(control) == value and selected == value and all(x == value for x in got)
                    and matching == n and (len(got) == n or len(got) >= 50) and any(x != value for x in all_values)
                    and exported is not None and f"{control}={value}" in href and len(exported) == n
                    and all(r.get(column) == value for r in exported) and [m for m, _ in seen] == ["GET"]):
                bad.append((value, q, got[:5], href, seen[:3]))
        s.shot("#main-panel", f"R27-D2-G-{kind}-{control}-last-option")
        seen = submit(s, control, "")
        v, q = view(s), query(s.page.url)
        check("G", f"D2 #18.3 History > {kind.capitalize()}, {control.capitalize()} dropdown: each option, chosen and submitted "
              "with Filter, leads to a URL carrying the token and a table whose rows all carry it and no others (premise: "
              "unfiltered, other values are listed too), the same rows as the view's CSV link, by a single GET",
              not bad and len(detail) >= 3 and len(base["rows"]) > 0, rows_unfiltered=len(base["rows"]),
              values_unfiltered=sorted(set(x for x in all_values if x)), per_option=detail, wrong=bad[:2])
        check("G", f"D2 #18.3 History > {kind.capitalize()}, {control.capitalize()} dropdown: 'Any' lists everything again and "
              "the token leaves the filter", q.get(control, "") == "" and len(v["rows"]) == len(base["rows"]) > 0
              and s.page.locator(f"{FORM} select[name={control}]").input_value() == "",
              url=s.page.url.replace(lib.BASE, ""), rows=len(v["rows"]), before=len(base["rows"]))
        if kind == "incidents" and control == "result":
            note("G", "a Result option that matches no record of the view", per_option=detail, empty_text=v.get("empty"))

    # ---- combined with from/to dates
    today = lib.gv("return java.time.LocalDate.now().toString()")
    yesterday = lib.gv("return java.time.LocalDate.now().minusDays(1).toString()")
    s.go(f"/batch-control/history/?kind=requests&job={P}")
    s.page.fill(f"{FORM} input[name=from]", today)
    s.page.fill(f"{FORM} input[name=to]", today)
    submit(s, "status", "REJECTED")
    v, q = view(s), query(s.page.url)
    s.page.fill(f"{FORM} input[name=from]", yesterday)
    s.page.fill(f"{FORM} input[name=to]", yesterday)
    submit(s, "status", "REJECTED")
    v2, q2 = view(s), query(s.page.url)
    check("G", "D2 #18.3 a Status filter combined with dates: from = to = today with REJECTED lists only rejected requests "
          "(at least the fixture's), the URL carrying the three; the day before with the same status lists none of the "
          "r27-d2 requests", q.get("from") == today and q.get("to") == today and q.get("status") == "REJECTED"
          and len(v["rows"]) >= 1 and all(r["status"] == "REJECTED" for r in v["rows"]) and q2.get("status") == "REJECTED"
          and q2.get("from") == yesterday and len(v2["rows"]) == 0, today=q, rows=len(v["rows"]), day_before=q2,
          rows_day_before=len(v2["rows"]))

    # ---- paging under a filter
    extra = ensure_pending(52)
    s.go("/batch-control/history/?kind=requests")
    submit(s, "status", "PENDING")
    v = view(s)
    older = [h for t, h in v["pager"] if "Older" in t]
    page1 = [r["status"] for r in v["rows"]]
    q_older = query("http://x/" + older[0]) if older else {}
    v2, newer = {"rows": []}, []
    if older:
        with s.page.expect_navigation(timeout=20000):
            s.page.locator("#main-panel a", has_text="Older").first.click()
        s.page.wait_for_load_state("load")
        v2 = view(s)
        newer = [h for t, h in v2["pager"] if "Newer" in t]
        sel = s.page.locator(f"{FORM} select[name=status]").input_value() if s.page.locator(f"{FORM} select[name=status]").count() else None
    s.shot("#main-panel", "R27-D2-G-requests-pending-page-2")
    check("G", "D2 #18.3 paging under a filter: with more PENDING requests than a page holds, page 1 holds only PENDING "
          "rows, its 'Older' link keeps status=PENDING, page 2 holds only PENDING rows with PENDING still selected, and "
          "its 'Newer' link keeps the token", bool(older) and (v["matching"] or 0) > len(page1) and set(page1) == {"PENDING"}
          and q_older.get("status") == "PENDING" and q_older.get("page") == "2" and len(v2["rows"]) >= 1
          and {r["status"] for r in v2["rows"]} == {"PENDING"} and sel == "PENDING"
          and bool(newer) and query("http://x/" + newer[0]).get("status") == "PENDING",
          matching=v["matching"], page1=len(page1), older=older[:1], page2=len(v2["rows"]), newer=newer[:1], filed_extra=extra)
    s.done()

    # ---- keyboard, GET, no crumb
    s = Session(who)
    s.go(f"/batch-control/history/?kind=requests&job={P}")
    posts, navs = [], []
    s.page.on("request", lambda r: (posts if r.method != "GET" else navs if r.is_navigation_request() else []).append(r.url))
    s.page.locator(f"{FORM} input[name=user]").focus()
    s.page.keyboard.press("Tab")
    focused = s.page.evaluate("document.activeElement.tagName + ':' + document.activeElement.name")
    s.page.keyboard.type("Exec")
    typed = s.page.locator(f"{FORM} select[name=status]").input_value() if s.page.locator(f"{FORM} select[name=status]").count() else None
    before = s.page.url
    s.page.keyboard.press("Enter")
    how = lib.react(s.page, before, timeout=8000)
    v, q = view(s), query(s.page.url)
    crumb_field = s.page.locator(f"{FORM} input[name='Jenkins-Crumb']").count()
    s.done()
    check("G", "D2 #18.3 keyboard: Tab from the User field reaches the Status dropdown, typing 'Exec' selects EXECUTED and "
          "Enter submits: the URL carries status=EXECUTED and the rows are the executed requests",
          focused == "SELECT:status" and typed == "EXECUTED" and how == "navigated" and q.get("status") == "EXECUTED"
          and len(v["rows"]) >= 1 and all(r["status"] == "EXECUTED" for r in v["rows"]), focused=focused, typed=typed,
          reaction=how, query=q)
    plain = api(who, f"/batch-control/history/?kind=requests&job={P}&status=EXECUTED", crumb=False)
    check("G", "guard: the filter form submits with GET: no request other than GET is made, the URL carries no crumb, and "
          "the same URL answers 200 to a plain GET", not posts and len(navs) >= 1
          and not any("crumb" in u.lower() for u in navs) and "Jenkins-Crumb" not in q and plain.status_code == 200,
          posts=posts[:3], navigations=[u.replace(lib.BASE, "") for u in navs][-1:], crumb_field_in_form=crumb_field,
          plain_get=plain.status_code)


def ensure_pending(n):
    """Premise of the paging check: at least `n` PENDING run requests in History's default range (the setup's seed
    files more than that; a Jenkins without the seed gets them here, on r27-d2-ok). Returns how many were filed."""
    have = len(F.csv_rows("/batch-control/history/requests.csv?status=PENDING"))
    filed = 0
    if have < n:
        p = lib.Poster("requester")
        import json
        for i in range(n - have):
            body = {"reason": f"e2e-27 D2 paging {i}", "approvers": ["approver-1"], "parameter": []}
            filed += p.post(lib.jpath(J["ok"]) + "/batch-control/submit", data={"json": json.dumps(body)}).status_code in (200, 302)
    return filed


def sec_K():
    who = "approver-1"
    s = Session(who)
    s.go(f"/batch-control/history/?kind=runs&job={P}")
    base = view(s)
    cases = (("runs", "result", "WEIRD<b>x</b>"), ("requests", "status", 'bogus"q'), ("incidents", "status", "<img src=x onerror=window.__r27d2=1>"))
    for kind, control, typed in cases:
        s.go(f"/batch-control/history/?kind={kind}&job={P}")
        n0 = len(view(s)["rows"])
        s.go(f"/batch-control/history/?kind={kind}&job={P}&{control}={quote(typed)}")
        st, v = s.page.evaluate(FORM_JS), view(s)
        c = (st or {}).get(control) or {}
        o = c.get("options") or []
        s.shot(FORM, f"R27-D2-K-{kind}-kept-value")
        canary = s.page.evaluate("window.__r27d2 === 1")
        check("K", f"D2 #18.3 kept input: History > {kind.capitalize()} with a hand-edited {control}={typed!r} keeps it as one "
              "extra selected option whose value and text are exactly the typed text (no element inside the select, the "
              "known options still offered, nothing executed), says that it is not applied, and lists what the view lists "
              "without it", c.get("tag") == "select" and [x["value"] for x in o if x["selected"]] == [typed]
              and sum(x["value"] == typed for x in o) == 1 and [x["text"] for x in o if x["value"] == typed] == [typed]
              and c.get("elements") == 0 and len(o) >= 5 and not canary
              and [n_ for n_ in st["notes"] if n_[0] == control and "not applied" in n_[1]] and len(v["rows"]) == n0 > 0,
              options=[(x["value"], x["selected"]) for x in o][-3:], notes=st["notes"], rows=len(v["rows"]), unfiltered=n0)
    s.go(f"/batch-control/history/?kind=incidents&job={P}&result=FAILURE&status=ACKNOWLEDGED")
    st, v = s.page.evaluate(FORM_JS), view(s)
    sel = {c: [x["value"] for x in ((st or {}).get(c) or {}).get("options") or [] if x["selected"]] for c in ("result", "status")}
    check("K", "D2 #18.3 a bookmarked URL with both tokens (incidents, result=FAILURE, status=ACKNOWLEDGED) opens with FAILURE "
          "and ACKNOWLEDGED selected and lists only acknowledged incidents of failed runs",
          sel == {"result": ["FAILURE"], "status": ["ACKNOWLEDGED"]} and len(v["rows"]) >= 1
          and all(r["status"] == "ACKNOWLEDGED" and r["result"] == "FAILURE" for r in v["rows"]), selected=sel, rows=len(v["rows"]))
    s.go(f"/batch-control/history/?kind=requests&job={P}&status=NOSUCH")
    st, v = s.page.evaluate(FORM_JS), view(s)
    o = ((st or {}).get("status") or {}).get("options") or []
    check("K", "D2 #18.3 kept input: a token-shaped value that names no status (status=NOSUCH) is kept as one extra selected "
          "option and lists no request", [x["value"] for x in o if x["selected"]] == ["NOSUCH"] and len(v["rows"]) == 0,
          selected=[x["value"] for x in o if x["selected"]], rows=len(v["rows"]), notes=st["notes"])
    s.go(f"/batch-control/history/?kind=requests&job={P}&status=rejected")
    st, v = s.page.evaluate(FORM_JS), view(s)
    o = ((st or {}).get("status") or {}).get("options") or []
    check("K", "D2 #18.3 kept input: a known value in lower case (status=rejected) selects the REJECTED option, adds no "
          "option and lists only rejected requests", [x["value"] for x in o if x["selected"]] == ["REJECTED"]
          and len(o) == len(F.REQUEST_STATUSES) + 1 and len(v["rows"]) >= 1 and all(r["status"] == "REJECTED" for r in v["rows"]),
          selected=[x["value"] for x in o if x["selected"]], options=len(o), rows=len(v["rows"]))
    s.go(f"/batch-control/history/?kind=changes&status=OPEN&result=FAILURE")
    st = s.page.evaluate(FORM_JS)
    check("K", "D2 #18.3 History > Changes offers no dropdown; a result and a status from the URL are kept as hidden fields, "
          "as the tab links keep them", st is not None and st["result"] is None and st["status"] is None
          and st["hidden"] == {"result": ["FAILURE"], "status": ["OPEN"]}, hidden=(st or {}).get("hidden"))
    s.done()
    r = api(who, f"/batch-control/history/?kind=runs&job={P}&result=FAILURE")
    t = lib.text_of(r.text)
    has = lambda job: bool(re.search(rf"(?<![\w-]){re.escape(job)}(?![\w-])", t))  # noqa: E731
    rows = F.csv_rows(f"/batch-control/history/runs.csv?job={P}&result=FAILURE")
    check("K", "guard: the URL tokens of before still filter: result=FAILURE lists r27-d2-fail and not r27-d2-ok, and "
          "runs.csv with it holds only FAILURE rows", r.status_code == 200 and has(J["fail"]) and not has(J["ok"])
          and len(rows) >= 3 and all(x.get("result") == "FAILURE" for x in rows), status=r.status_code, csv_rows=len(rows),
          unfiltered_rows=len(base["rows"]))


def cleanup():
    # ci/shard.py runs r27/status_badges.py next on the same records (BC_D2_KEEP_FIXTURE=1); that driver sweeps.
    keep = os.environ.get("BC_D2_KEEP_FIXTURE") == "1"
    note("cleanup", "restore", kept_for_the_next_driver=keep, swept=None if keep else lib.sweep("requester", P))


if __name__ == "__main__":
    lib.run(sys.argv, {"A": sec_A, "B": sec_B, "R": sec_R, "D": sec_D, "F": sec_F, "G": sec_G, "K": sec_K}, cleanup)
