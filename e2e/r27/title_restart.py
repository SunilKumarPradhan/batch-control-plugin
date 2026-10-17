"""e2e-27 D1 (T-UI-236, note 360 (7) "not covered: a title after a restart"): the page of a permission window whose
item was renamed is titled with the item's current name after Jenkins restarted, too.

usage: python title_restart.py before|after     rows: out/title_restart.jsonl, shots: screenshots/run-27/R27-D1-Y-*.png
This driver does not restart Jenkins. ci/shard.py runs it as the first and the last step of the unit r16-durable, whose
own steps restart Jenkins twice (r16/durable.py with the grants directory read-only, r19/restart.py); a window that is
not touched in between stays open across both (r16/durable.py's own control).
before  re-creates r27-d1r/keep-a; the requester's CONFIGURE window on it (60 minutes; designated approvers approver-1
        and approver-disc, who holds no Item/Read) is approved by approver-1; the administrator renames it to
        r27-d1r/keep-b. Guards: the requester's page reads "Grant request: r27-d1r/keep-b", approver-disc's the approved
        name. The request id and Jenkins' start time are written to out/title_restart.json.
after   premises (server state): Jenkins has started again since `before`, the window is still open and names keep-b,
        the requester, approver-1 and admin may read it, approver-disc may not. Then the three readers each read
        "Grant request: r27-d1r/keep-b" in the title, the heading, the breadcrumb and its tooltip, keep-a in none of
        them, the same item in the Scope row, and the ID row; approver-disc, who may open the page but not read the
        item, reads exactly "Grant request: r27-d1r/keep-a", the Scope row with the "moved" note, and keep-b is
        nowhere in the page's HTML (T-UI-237 after a restart). The window is revoked at the end.
Item names end in -nightly-settlement (core cuts a long breadcrumb and only then gives it a tooltip)."""
import json
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import titles_revert as D  # noqa: E402
import lib  # noqa: E402
from lib import api, check  # noqa: E402

lib.LOGNAME[0] = "title_restart"
FOLDER = "r27-d1r"
OLD, NEW = f"{FOLDER}/keep-a{D.TAIL}", f"{FOLDER}/keep-b{D.TAIL}"
STATE = lib.OUT / "title_restart.json"
STARTED = "return String.valueOf(java.lang.management.ManagementFactory.getRuntimeMXBean().getStartTime())"


def read(sec, who, n, what):
    D.titled(sec, who, "grant", "grant_keep", f"Grant request: {NEW}", what, f"R27-D1-Y-0{n}-window-renamed-{sec}-{who}",
             absent=(OLD,), scope="Freestyle project " + NEW)


def read_unseen(sec, n, what):
    D.titled(sec, "approver-disc", "grant", "grant_keep", f"Grant request: {OLD}", what,
             f"R27-D1-Y-0{n}-window-renamed-{sec}-approver-disc", absent=(NEW,), scope="Freestyle project " + OLD + D.MOVED,
             raw_absent=("keep-b",))


def before():
    lib.ensure_folder(FOLDER)
    removed = D.remove(OLD, NEW)
    swept = lib.sweep("requester", FOLDER)
    lib.ensure_item(OLD, lib.job_xml("fs", shell="echo e2e-27 D1"))
    D.S["grant_keep"] = lib.submit_grant("requester", OLD, ["CONFIGURE"], minutes=60, reason="e2e-27 D1 title across a restart",
                                         approvers=("approver-1", "approver-disc"))
    gid = D.S["grant_keep"][1]
    approved = lib.decide("approver-1", "grants", gid, "approve", "e2e-27 D1") if gid else None
    renamed = D.rename(OLD, NEW.rsplit("/", 1)[1])
    check("B", "arrangement: the requester's CONFIGURE window on r27-d1r/keep-a is approved, the administrator renamed the "
          "job to keep-b, the window is open and names keep-b", D.window_of(gid) == {"scope": NEW, "open": True},
          approved=approved, renamed=renamed, window=D.window_of(gid) if gid else None, removed=removed, swept=swept)
    read("B", "requester", 1, "window whose item was renamed, before the restart")
    read_unseen("B", 5, "window whose item was renamed, before the restart (a viewer who may not read the item)")
    STATE.write_text(json.dumps({"grant_keep": gid, "jvm_started": lib.gv(STARTED)}))


def after():
    saved = json.loads(STATE.read_text()) if STATE.exists() else {}
    gid = saved.get("grant_keep")
    D.S["grant_keep"] = (302, gid)
    now = lib.gv(STARTED)
    window = D.window_of(gid) if gid else None
    readers = D.may_read(NEW, ("requester", "approver-1", "admin", "approver-disc"))
    check("Y", "arrangement: Jenkins has restarted since the window's item was renamed (another JVM start time); the "
          "window is still open and names keep-b; requester, approver-1 and admin may read the job, approver-disc may not",
          bool(gid) and now.isdigit() and now != saved.get("jvm_started") and window == {"scope": NEW, "open": True}
          and readers == {"requester": True, "approver-1": True, "admin": True, "approver-disc": False},
          jvm_started_before=saved.get("jvm_started"), jvm_started_now=now, window=window, readers=readers)
    if gid:
        for n, who in enumerate(("requester", "approver-1", "admin"), 2):
            read("Y", who, n, "window whose item was renamed, after a restart")
        read_unseen("Y", 6, "window whose item was renamed, after a restart (a viewer who may not read the item)")
        check("Y", "arrangement: the window revoked at the end",
              api("admin", f"/batch-control/grants/{gid}/revoke", "POST").status_code < 400 and not D.window_of(gid).get("open"))


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    if which not in ("before", "after"):
        sys.exit("usage: title_restart.py before|after")
    lib.run([sys.argv[0], "B" if which == "before" else "Y"], {"B": before} if which == "before" else {"Y": after})
