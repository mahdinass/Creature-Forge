#!/bin/bash
# Runs ON the VM as user forge. Args: <bundle-path> <branch> <registered-protocol-commit>
set -euo pipefail
BUNDLE=$1; BRANCH=$2; REG=$3
REPO=$HOME/creature-forge; VENV=$HOME/venvs/creature-forge; LOGS=$HOME/logs
mkdir -p "$LOGS" "$HOME/venvs"
until [ -f /var/lib/forge/cloud-init-done ]; do sleep 5; done
if [ ! -d "$REPO/.git" ]; then git clone --quiet "$BUNDLE" "$REPO"; fi
cd "$REPO"
git fetch --quiet "$BUNDLE" "refs/heads/$BRANCH:refs/remotes/bundle/$BRANCH"
NEW=refs/remotes/bundle/$BRANCH
# Frozen files (training_set.json, selection.json, ...) are produced on the VM untracked and later committed locally; accept
# the incoming commit only if each such untracked file is byte-identical (as git sees it) to the committed blob.
for f in $(git diff --name-only --diff-filter=A HEAD "$NEW" 2>/dev/null || true); do
  if [ -f "$f" ] && ! git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    if [ "$(git hash-object "$f")" = "$(git rev-parse "$NEW:$f")" ]; then rm "$f"; else echo "untracked $f differs from the committed blob; refusing"; exit 6; fi
  fi
done
# Tracked results files that the VM appended to (e.g. the append-only ledger) are accepted only when they already equal the incoming blob.
for f in $(git diff --name-only); do
  if [ "$(git hash-object "$f")" = "$(git rev-parse "$NEW:$f" 2>/dev/null)" ]; then git checkout -- "$f"; else echo "modified $f differs from the incoming commit; refusing"; exit 7; fi
done
git checkout --quiet -B "$BRANCH" "$NEW"
git merge-base --is-ancestor "$REG" HEAD || { echo "registered commit $REG is not an ancestor of HEAD"; exit 2; }
git diff --quiet "$REG" HEAD -- experiments/phase2a_r1/protocol.json || { echo "protocol.json differs from registered commit"; exit 3; }
# R1 pre-registration hashes the Windows worktree bytes (CRLF via core.autocrlf), git stores LF. Reproduce the registered
# byte layout with the same git setting instead of touching the immutable protocol. Only when the tree is clean.
if [ "$(git config --get core.autocrlf || true)" != "true" ]; then
  git diff --quiet && git diff --cached --quiet || { echo "dirty tree; refusing to re-checkout"; exit 5; }
  git config core.autocrlf true
  git ls-files -z | xargs -0 rm -f
  git checkout -- .
fi
echo "HEAD=$(git rev-parse HEAD) registered=$REG protocol.json identical"
# Linux-only environment, outside the checkout; the Windows .venv is never involved.
[ -d "$VENV" ] || python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -e .
"$VENV/bin/pip" freeze > "$LOGS/pip-freeze.txt"
"$VENV/bin/python" - <<'PY'
import sys, numpy, mujoco, platform
print(platform.platform(), sys.version.split()[0], "numpy", numpy.__version__, "mujoco", mujoco.__version__)
PY
