#!/usr/bin/env bash
# e2e-27 (Wave D: D1 titles and revert placement, D2 filter dropdowns and status labels, D3 decision area and run tables,
# D4 administrator checks) local wrapper: the r27 units on their own compose project and ports, so they can run next to
# other stacks on the same machine. CI does not use this file (it runs ci/run.sh with the group's index).
#
#   e2e/r27/wrap.sh unit <unit> [label]       ci/run.sh on a fresh stack with BC_UNITS=<unit> (the SETUP steps first,
#                                              as in CI); artefacts in ci/out/w2d-<unit>-<label>/
#   e2e/r27/wrap.sh up                        a development stack (same compose files as ci/run.sh), waits until ready
#   e2e/r27/wrap.sh setup                     the SETUP steps of ci/shard.py against the development stack
#   e2e/r27/wrap.sh drv <driver.py> [args]    one driver against the development stack
#   e2e/r27/wrap.sh down                      removes the development stack and its volume
#
# Environment (defaults): BC_PROJECT=bc-w2d, BC_PORT=8100, BC_MAIL_PORT=18100, PY=python3 with ci/requirements.txt,
# BC_COMPOSE_EXTRA (extra -f files). The plugin is target/batch-control.hpi (BC_BUILD=never: build it first).
set -euo pipefail
E2E="$(cd "$(dirname "$0")/.." && pwd)"
export BC_PROJECT="${BC_PROJECT:-bc-w2d}" BC_PORT="${BC_PORT:-8100}" BC_MAIL_PORT="${BC_MAIL_PORT:-18100}"
export BC_CONTAINER="$BC_PROJECT" BC_BASE="http://localhost:${BC_PORT}/jenkins" BC_BUILD="${BC_BUILD:-never}"
export BC_BROWSER_CHANNEL="${BC_BROWSER_CHANNEL:-chromium}" TZ="${TZ:-Asia/Seoul}" PY="${PY:-python3}"

group_of() { # "<k>/<N>": k is the index of the group that holds unit $1 (ci/shard.py GROUPS)
  "$PY" -c 'import sys; sys.path.insert(0, sys.argv[1]); import shard
hit = [f"{i}/{len(shard.GROUPS)}" for i, (label, names) in enumerate(shard.GROUPS, 1) if sys.argv[2] in names]
print(hit[0]) if hit else sys.exit("unit " + sys.argv[2] + " is in no group")' "$E2E/ci" "$1"
}
files=(-f "$E2E/docker-compose.yml" -f "$E2E/compose.prefix.yml" -f "$E2E/compose.coverage.yml")
for f in ${BC_COMPOSE_EXTRA:-}; do files+=(-f "$f"); done

case "${1:-}" in
  unit)
    unit="${2:?unit}"
    shard="$(group_of "$unit")"
    export BC_SHARD="${shard%%/*}"
    BC_UNITS="$unit" BC_OUT="${BC_OUT:-$E2E/ci/out/w2d-$unit-${3:-run}}" exec "$E2E/ci/run.sh" "$shard"
    ;;
  up)
    if [ ! -f "$E2E/.env" ]; then # as ci/run.sh step 2: random passwords, never committed
      (umask 077; for k in ADMIN APPROVER REQUESTER OTHER; do
         echo "BC_${k}_PASSWORD=$("$PY" -c 'import secrets; print(secrets.token_urlsafe(18))')"; done > "$E2E/.env")
    fi
    "$E2E/ci/fetch-jacoco.sh" >/dev/null
    export BC_SHARD="${BC_SHARD:-dev}"
    docker compose -p "$BC_PROJECT" --project-directory "$E2E" "${files[@]}" up -d --build --quiet-pull
    pw="$(sed -n 's/^BC_ADMIN_PASSWORD=//p' "$E2E/.env")"
    for _ in $(seq 1 120); do
      if curl -sf -u "admin:$pw" "$BC_BASE/pluginManager/api/json?tree=plugins%5BshortName,active%5D" | grep -q '"batch-control"'; then
        echo "ready: $BC_BASE"; exit 0
      fi
      sleep 3
    done
    echo "not ready" >&2; exit 2
    ;;
  setup)
    cd "$E2E" && "$PY" -c 'import sys, subprocess; sys.path.insert(0, "ci"); import shard
for name, step in shard.SETUP:
    rc = subprocess.call([sys.executable] + step["argv"])
    print(f"== {name}: exit {rc}", flush=True)'
    ;;
  drv)
    shift
    cd "$E2E" && exec "$PY" "$@"
    ;;
  down)
    BC_SHARD=dev docker compose -p "$BC_PROJECT" --project-directory "$E2E" "${files[@]}" down -v --remove-orphans
    ;;
  *)
    sed -n '2,15p' "$0" >&2; exit 64 ;;
esac
