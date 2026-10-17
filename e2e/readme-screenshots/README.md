# README screenshots

`capture.py` seeds demo data (folder `batch`, run requests, grants, a configuration change) and writes the six
images in `docs/images/` that the README uses. They follow the README's three steps, and each one is taken as the
account that does the step:

| Step | Image | Account | Page | Highlighted |
|---|---|---|---|---|
| 1. Set it up | `global-config.png` | `admin` | Manage Jenkins → System, the Batch Control section down to its last setting | the two switches; the Approvers list |
| 2. Run a protected job | `request-run.png` | `requester` | Request Run of `batch/daily-settlement` | Reason and Approvers (one frame) |
| | `approval.png` | `approver-1` | that run request, pending | Approve; Reject |
| | `history.png` | `approver-1` | History, Requests view | the row of that request, now EXECUTED |
| 3. Change a job safely | `permission-window.png` | `requester` | Request Change Permission for `batch/nightly-load` | Actions with Duration; Reason |
| | `permission-window-approval.png` | `approver-1` | that permission window request, pending | Approve; Reject |

The request of step 2 and the window of step 3 are the same ones from form to decision: the script submits the form
it has photographed, photographs the approver's page of what was submitted, and approves the run request so that
History shows who asked, who decided and that it ran.

Every image is 1280 px wide. The highlight is a rounded frame in one accent colour (`ACCENT` in `capture.py`) that
the script draws on the page right before the capture: at most two frames per image, and the script stops if a
frame's line would cross text or a control. No image is edited by hand. `global-config.png` ends below the last
setting of the section; the "Batch Control strategy" entry under it (the red "Revert to the plain strategy" button)
is not in the picture.

Run it against a fresh e2e stack after UI changes (Python >= 3.10):

```bash
mvn -ntp clean package -DskipTests && cd e2e && cp -n .env.example .env    # then set the passwords in .env
scripts/reset.sh; TZ=UTC scripts/up.sh                                      # fresh JENKINS_HOME, UTC timestamps
python3 -m venv ~/.venvs/bc && ~/.venvs/bc/bin/pip install playwright requests pillow && ~/.venvs/bc/bin/playwright install chromium
~/.venvs/bc/bin/python readme-screenshots/capture.py && scripts/down.sh      # review the PNGs before committing
```

`scripts/reset.sh` deletes the JENKINS_HOME volume of the compose project. To leave the default project's volume
(`batch-control-e2e_jenkins_home`) alone, run the three stack scripts with `COMPOSE_PROJECT_NAME=<another name>`:
the stack then gets a volume of its own. The container names and ports stay the same, so stop one stack before
starting another.

On a stack that is not fresh the script still runs (the seed is skipped), but every run adds one executed run
request and one pending permission window request, so History and the tab badges show more than on a fresh one.
