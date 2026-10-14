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
git checkout --quiet -B "$BRANCH" "refs/remotes/bundle/$BRANCH"
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
