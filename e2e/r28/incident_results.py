"""e2e-28 #91: "Results that open an incident" accepts only FAILURE, UNSTABLE and ABORTED (TEST-MATRIX T-11-32..36,
note 364), on the real configuration pages in a browser.

usage: python incident_results.py [ALVG]   rows: r27/out/incident_results.jsonl, shots: screenshots/run-27/R28-91-*.png
A check named "#91" fails without the fix; one named "guard" holds with and without it. The stored values are read in
the script console; the settings change history from the store (CONFIG_CHANGE and CONFIGURE records). The cleaning of a
stored value on load needs a restart (T-11-34/35) and is not driven here.

A  arrangement: the settings as they are (put back at the end).
L  the live field check (admin, the Batch Control configuration page): typing "FAILURE, SUCCESS" and "UNSTABLE,
   NOT_BUILT" shows an error under the field (#91); "FAILURE, ABORTED" shows none (guard).
V  a refused save (#91): admin saves Manage Jenkins > System with "FAILURE, SUCCESS", manager the Batch Control page with
   "UNSTABLE, NOT_BUILT", each together with another retention period: the save is not answered as a success, neither
   value is stored (incidentResults and retentionMonths unchanged) and no CONFIG_CHANGE or CONFIGURE record is written.
G  guards: admin saves Manage Jenkins > System with "FAILURE, ABORTED", manager the Batch Control page with "UNSTABLE,
   ABORTED": each answers below 400, stores exactly that and writes its settings change record.
cleanup: the settings as they were."""
import json
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 2)[0] + "/r27")
import lib  # noqa: E402
from lib import check, note, Session, gv  # noqa: E402

lib.LOGNAME[0] = "incident_results"
SYSTEM, BC = "/manage/configure", "/manage/batch-control-configuration/"
FIELD = "input[name='_.incidentResults']"
S = {}


def now_ms():
    return int(gv("return System.currentTimeMillis()"))


def stored():
    return lib.facts(lib.L25.CFG + "return groovy.json.JsonOutput.toJson([results: cfg.incidentResults, retention: cfg.retentionMonths])")


def records(since):
    return lib.facts(f"""def res = []
(new File(jenkins.model.Jenkins.get().rootDir, 'batch-control/changes').listFiles() ?: []).findAll {{ it.name.endsWith('.jsonl') }}.each {{
  it.eachLine('UTF-8') {{ l -> def m = new groovy.json.JsonSlurper().parseText(l)
    if ((m.at as long) >= {since}L && ['CONFIG_CHANGE', 'CONFIGURE'].contains(m.type)) res << [type: m.type, user: m.user, target: m.target, detail: String.valueOf(m.detail)] }} }}
return groovy.json.JsonOutput.toJson(res)""")


def field_error(s):
    """The validation message core shows under the field (empty when there is none)."""
    return s.page.evaluate(f"""() => {{ const f = document.querySelector("{FIELD}"); if (!f) return null;
      const item = f.closest('.jenkins-form-item') || f.closest('tr') || f.parentElement;  // the error area sits beside .setting-main
      return [...item.querySelectorAll('.error, .validation-error-area .error')].map(e => e.textContent.replace(/\\s+/g, ' ').trim())
        .filter(Boolean).join(' | '); }}""")


def save(who, path, results, retention=None):
    s = Session(who)
    s.go(path)
    s.page.locator(FIELD).first.fill(results)
    if retention is not None:
        s.page.locator("input[name='_.retentionMonths']").first.fill(str(retention))
    with s.page.expect_response(lambda r: r.request.method == "POST" and "configSubmit" in r.url, timeout=60000) as ri:
        s.page.locator("button[name=Submit]").first.click()
    s.page.wait_for_load_state("load")
    status, text = ri.value.status, re.sub(r"\s+", " ", s.text())
    lib.page_shot(s, f"R28-91-{who}-{path.strip('/').replace('/', '-')}-{results.replace(', ', '-')}")
    s.done()
    return status, text


def sec_A():
    S["before"] = stored()
    S["default"] = gv(lib.L25.CFG + "cfg.setIncidentResultsText('FAILURE, UNSTABLE'); cfg.save(); return cfg.incidentResultsText")
    check("A", "arrangement: the settings read; incidentResults at the default FAILURE, UNSTABLE", S["default"] == "FAILURE, UNSTABLE",
          before=S["before"])


def sec_L():
    s = Session("admin")
    s.go(BC)
    seen = {}
    for value in ("FAILURE, SUCCESS", "UNSTABLE, NOT_BUILT", "FAILURE, ABORTED"):
        f = s.page.locator(FIELD).first
        f.fill(value)
        f.blur()
        lib.wait_until(lambda: field_error(s) or value == "FAILURE, ABORTED", 5, 0.3)
        s.page.wait_for_timeout(800)  # core's check answers asynchronously; a late error would show by now
        seen[value] = field_error(s)
        if value == "FAILURE, SUCCESS":
            s.shot(FIELD, "R28-91-L-field-error", pad=80)
    s.done()
    check("L", "#91 (T-11-32): typing FAILURE, SUCCESS or UNSTABLE, NOT_BUILT into 'Results that open an incident' shows an "
          "error under the field while typing (admin, Batch Control configuration page)",
          bool(seen["FAILURE, SUCCESS"]) and bool(seen["UNSTABLE, NOT_BUILT"]), errors=seen)
    check("L", "guard: FAILURE, ABORTED shows no error", seen["FAILURE, ABORTED"] == "", errors=seen)


def sec_V():
    for who, path, value in (("admin", SYSTEM, "FAILURE, SUCCESS"), ("manager", BC, "UNSTABLE, NOT_BUILT")):
        before, mark = stored(), now_ms()
        status, text = save(who, path, value, retention=before["retention"] + 1)
        after, recs = stored(), records(mark)
        check("V", f"#91 (T-11-33): {who}'s save of {path} with '{value}' (and another retention period) is not answered as "
              "a successful save, stores neither value and writes no CONFIG_CHANGE or CONFIGURE record",
              status >= 400 and after == before and not recs, status=status, before=before, after=after, records=recs,
              text=text[:300])


def sec_G():
    for who, path, value in (("admin", SYSTEM, "FAILURE, ABORTED"), ("manager", BC, "UNSTABLE, ABORTED")):
        mark = now_ms()
        status, _ = save(who, path, value)
        after, recs = stored(), records(mark)
        mine = [x for x in recs if x["type"] == "CONFIG_CHANGE" and "incidentResults" in x["detail"]]
        check("G", f"guard: {who}'s save of {path} with '{value}' answers below 400, stores exactly it and writes its settings "
              "change record", status < 400 and after["results"] == [v.strip() for v in value.split(",")] and len(mine) == 1
              and mine[0]["user"] == who, status=status, stored=after, records=recs)


def cleanup():
    b = S.get("before") or {"results": ["FAILURE", "UNSTABLE"], "retention": None}
    out = gv(lib.L25.CFG + f"cfg.setIncidentResults({json.dumps(b['results'])})"
             + (f"; cfg.setRetentionMonths({b['retention']})" if b.get("retention") else "") + "; cfg.save(); return cfg.incidentResultsText")
    note("cleanup", "restore", incident_results=out)


if __name__ == "__main__":
    lib.run(sys.argv, {"A": sec_A, "L": sec_L, "V": sec_V, "G": sec_G}, cleanup)
