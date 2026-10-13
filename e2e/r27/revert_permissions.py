"""e2e-27 D1 (#18.7, T-UI-235/239 for the two optional core permissions): who is offered "Revert to the plain strategy"
when Overall/Manage and Overall/SystemRead are in use. Their holders open Manage Jenkins > System without
Overall/Administer, so they are the viewers the administrator-only rule of the revert entry has to hold for.

usage: python revert_permissions.py [AVWS]   rows: out/revert_permissions.jsonl, shots: screenshots/run-27/R27-D1-M-*.png
The two permissions: core 2.568.3 has Overall/Manage enabled as it is; Overall/SystemRead is off unless Jenkins is
started with -Djenkins.security.SystemReadPermission=true. e2e/compose.permissions.yml starts the stack with both system
properties (BC_COMPOSE_EXTRA, see e2e/README.md); on the regular stack the arrangement switches on what is off with the
same switch the properties set (Permission#setEnabled, script console) and switches it off again at the end. The
arrangement check says which of the two it was.

A  arrangement: the installed strategy is saved (XStream, as r22/rename_queue.py); four accounts are added to the matrix:
   r27-ovm (Overall/Read + Overall/Manage), r27-ovm-bc (+ BatchControl/Manage), r27-sysread (Overall/Read +
   Overall/SystemRead), r27-sysread-bc (+ BatchControl/Manage). None holds Overall/Administer.
V  each account opens Manage Jenkins > System (all four: 200) and the Batch Control configuration page (200 with
   BatchControl/Manage, else 403), nothing pressed. On every page: nothing of the revert is rendered (no control in the
   DOM, neither its URL nor its caption in the HTML). Wherever the Batch Control section is shown to them it has no
   Advanced button and no Advanced body, and the sentence "Only a Jenkins administrator can change the authorization
   strategy." is displayed in it as the page loads (T-UI-239). A NOTE lists who was shown what. The administrator, with
   the permissions in use, still gets the entry inside Advanced on both pages (T-UI-234).
W  the revert endpoint answers 403 to a crumbed POST by each of the four; the strategy and its entries stay.
S  r27-ovm and r27-ovm-bc press Save on Manage Jenkins > System: answered below 400; the strategy, its entries, the
   Batch Control settings, the system message and the executor count are unchanged. The SystemRead holders get no Save.
cleanup: the saved strategy put back (the accounts' entries go with it), the accounts deleted, a permission that the
arrangement switched on switched off again."""
import json
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import titles_revert as D  # noqa: E402
import lib  # noqa: E402
from lib import api, check, note, Session, gv  # noqa: E402

lib.LOGNAME[0] = "revert_permissions"
READ, MANAGE, SYSTEM_READ = "hudson.model.Hudson.Read", "hudson.model.Hudson.Manage", "hudson.model.Hudson.SystemRead"
ADMINISTER, BC_MANAGE = "hudson.model.Hudson.Administer", lib.BC + ".security.BatchControlPermissions.Manage"
ACCOUNTS = {"r27-ovm": [READ, MANAGE], "r27-ovm-bc": [READ, MANAGE, BC_MANAGE],
            "r27-sysread": [READ, SYSTEM_READ], "r27-sysread-bc": [READ, SYSTEM_READ, BC_MANAGE]}
SYSTEM, BC_PAGE = D.CONFIG_PAGES[0][0], D.CONFIG_PAGES[1][0]
SNAPSHOT = "r27-d1-perm-strategy.xml"
S = {}


def switches():
    """Server state: the two permissions' switches and whether the system properties set them."""
    return lib.facts("""import jenkins.model.Jenkins
return groovy.json.JsonOutput.toJson([manage: Jenkins.MANAGE.enabled, system_read: Jenkins.SYSTEM_READ.enabled,
  manage_property: Boolean.getBoolean('jenkins.security.ManagePermission'),
  system_read_property: Boolean.getBoolean('jenkins.security.SystemReadPermission')])""")


def host():
    """Server state besides the Batch Control settings that a save of Manage Jenkins > System could change."""
    return lib.facts("""def j = jenkins.model.Jenkins.get()
return groovy.json.JsonOutput.toJson([message: j.systemMessage, executors: j.numExecutors, labels: j.labelString,
  quiet: j.quietPeriod, url: jenkins.model.JenkinsLocationConfiguration.get().url])""")


def sec_A():
    S["before"] = switches()
    S["strategy"], S["entries"] = lib.strategy(), D.entries()
    gv("""import jenkins.model.Jenkins
def j = Jenkins.get(); def snap = new File(j.rootDir, '""" + SNAPSHOT + """')
// a pass that died before its restore left the snapshot of the original strategy: keep it
if (!snap.exists()) snap.setText(Jenkins.XSTREAM2.toXML(j.authorizationStrategy), 'UTF-8')
Jenkins.MANAGE.setEnabled(true); Jenkins.SYSTEM_READ.setEnabled(true); return 'ok'""")
    S["now"] = switches()
    perms = {u: lib.L25.ensure_account(u, ids).split(",") for u, ids in ACCOUNTS.items()}
    how = {k: "its system property" if S["before"][k + "_property"] else "enabled in this core as it is" if S["before"][k]
           else "switched on for this pass (Permission#setEnabled)" for k in ("manage", "system_read")}
    check("A", "arrangement: Overall/Manage and Overall/SystemRead are in use; the Batch Control strategy is installed; "
          "r27-ovm, r27-ovm-bc, r27-sysread and r27-sysread-bc hold exactly what their names say and none holds "
          "Overall/Administer", S["now"]["manage"] and S["now"]["system_read"] and S["strategy"].startswith("BatchControl")
          and all(set(ids) <= set(perms[u]) and ADMINISTER not in perms[u]
                  and (MANAGE in perms[u]) == (MANAGE in ids) and (SYSTEM_READ in perms[u]) == (SYSTEM_READ in ids)
                  and (BC_MANAGE in perms[u]) == (BC_MANAGE in ids) for u, ids in ACCOUNTS.items()),
          how=how, strategy=S["strategy"], held={u: [x.rsplit(".", 2)[-2][-6:] + "/" + x.rsplit(".", 1)[-1] for x in v]
                                                    for u, v in perms.items()})


def sec_V():
    shown = {}
    for i, who in enumerate(ACCOUNTS, 1):
        has_bc = BC_MANAGE in ACCOUNTS[who]
        for path, tag in ((SYSTEM, "system"), (BC_PAGE, "bc-config")):
            s = Session(who)
            r = s.go(path)
            status = r.status if r else None
            h = s.page.evaluate(D.HOLDER_JS, D.ASK_ADMIN)
            st = s.page.evaluate(D.STATE_JS, D.REVERT_SEL)
            html = s.page.content()
            D.end_shot(s, f"R27-D1-M-{i}{1 if tag == 'system' else 2}-{who}-{tag}")
            saves = s.page.locator("button[name=Submit], button[name=Apply]").count()
            s.done()
            want = 200 if (path == SYSTEM or has_bc) else 403
            one = h["sentence"][0] if len(h["sentence"]) == 1 else {}
            shown[f"{who} {path}"] = {"status": status, "section": h["section"], "fields": h["fields"],
                                      "sentence": bool(one.get("displayed")), "advanced": h["advancedButtons"], "save": saves}
            check("V", f"D1 #18.7 administrators only: {who} gets {path} with HTTP {want} and nothing of the revert is "
                  "rendered, not even hidden: no control in the DOM, neither its URL nor its caption in the HTML",
                  status == want and not st["controls"] and D.REVERT not in html and D.REVERT_TEXT not in html,
                  status=status, controls=st["controls"])
            if h["section"]:
                check("V", f"guard (T-UI-239): {who} is shown the Batch Control section on {path}: it has no Advanced "
                      f"button and no Advanced body, and '{D.ASK_ADMIN}' is displayed in it as the page loads",
                      h["advancedButtons"] == 0 and h["advancedBodies"] == 0 and one.get("text") == D.ASK_ADMIN
                      and one.get("displayed") is True and one.get("inSection") is True
                      and one.get("inAdvancedBody") is False, page=h)
    S["shown"] = shown
    note("V", "who is shown what (status, Batch Control section, its named fields, the sentence, Advanced buttons, "
         "Save/Apply buttons)", shown=shown)
    check("V", "premise of the checks above: the Batch Control section is shown to a viewer without Overall/Administer on "
          "Manage Jenkins > System (the SystemRead holder's read-only view) and on the Batch Control page (the "
          "BatchControl/Manage holders)", shown[f"r27-sysread {SYSTEM}"]["section"]
          and shown[f"r27-ovm-bc {BC_PAGE}"]["section"] and shown[f"r27-sysread-bc {BC_PAGE}"]["section"],
          sections={k: v["section"] for k, v in shown.items()})
    for path, tag, n in D.CONFIG_PAGES:
        s = D.revert_place("V", path, tag + "-permissions", n, lib.strategy())
        if s is not None:
            s.done()


def sec_W():
    codes = {who: api(who, "/manage/" + D.REVERT, "POST").status_code for who in ACCOUNTS}
    check("W", "guard: the revert endpoint answers 403 to a crumbed POST by r27-ovm, r27-ovm-bc, r27-sysread and "
          "r27-sysread-bc; the Batch Control strategy and its entries stay", all(v == 403 for v in codes.values())
          and lib.strategy() == S["strategy"], codes=codes, strategy=lib.strategy())


def sec_S():
    for i, who in enumerate(("r27-ovm", "r27-ovm-bc"), 1):
        before = {"strategy": lib.strategy(), "entries": D.entries(), "settings": D.settings(), "host": host()}
        s = Session(who)
        s.go(SYSTEM)
        save = s.page.locator("button[name=Submit]")
        status = None
        if save.count():
            with s.page.expect_navigation() as nav:
                save.first.click()
            s.page.wait_for_load_state("load")
            status = nav.value.status if nav.value else None
        lib.page_shot(s, f"R27-D1-M-5{i}-{who}-system-saved")
        landed = s.page.url.replace(lib.BASE, "")
        s.done()
        after = {"strategy": lib.strategy(), "entries": D.entries(), "settings": D.settings(), "host": host()}
        check("S", f"guard: {who} (Overall/Manage, no Administer) presses Save on Manage Jenkins > System: answered below "
              "400, and the authorization strategy, its entries, the Batch Control settings, the system message, the "
              "executors, the labels and the Jenkins URL are unchanged", status is not None and status < 400
              and after == before, status=status, landed=landed,
              changed=[k for k in before if before[k] != after[k]], before=before["settings"], after=after["settings"])
    saves = {who: (S.get("shown") or {}).get(f"{who} {SYSTEM}", {}).get("save") for who in ("r27-sysread", "r27-sysread-bc")}
    check("S", "guard: the SystemRead holders' Manage Jenkins > System has no Save and no Apply button (read-only view)",
          bool(S.get("shown")) and all(v == 0 for v in saves.values()), buttons=saves)


def cleanup():
    back = gv("""import jenkins.model.Jenkins
def j = Jenkins.get(); def snap = new File(j.rootDir, '""" + SNAPSHOT + """'); def out = []
if (snap.exists()) { j.setAuthorizationStrategy(Jenkins.XSTREAM2.fromXML(snap.getText('UTF-8'))); j.save(); snap.delete(); out << 'strategy' }
""" + json.dumps(list(ACCOUNTS)) + """.each { def u = hudson.model.User.getById(it, false); if (u != null) { u.delete(); out << it } }
return out.join(',')""")
    b = S.get("before") or {}
    if b and not b["manage"]:
        gv("jenkins.model.Jenkins.MANAGE.setEnabled(false); return 0")
    if b and not b["system_read"]:
        gv("jenkins.model.Jenkins.SYSTEM_READ.setEnabled(false); return 0")
    now = switches()
    check("cleanup", "the saved authorization strategy is installed again with its entries, the four accounts are deleted "
          "and the two permissions are switched as they were", lib.strategy() == S.get("strategy")
          and D.entries() == S.get("entries") and all(now[k] == b.get(k) for k in ("manage", "system_read")),
          restored=back, strategy=lib.strategy(), switches=now, before=b)


if __name__ == "__main__":
    lib.run(sys.argv, {"A": sec_A, "V": sec_V, "W": sec_W, "S": sec_S}, cleanup)
