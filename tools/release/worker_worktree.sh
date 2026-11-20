#!/usr/bin/env bash
# Create a detached dispatch checkout with the ignored worker context installed.
set -euo pipefail

usage() {
    echo 'Usage: tools/release/worker_worktree.sh <name> [ref]' >&2
    echo '       tools/release/worker_worktree.sh --remove <name>' >&2
    exit 2
}
fail() { echo "worker_worktree: $*" >&2; exit 1; }

remove=false
if [[ ${1:-} == --remove ]]; then
    [[ $# == 2 ]] || usage
    remove=true
    name=$2
else
    [[ $# == 1 || $# == 2 ]] || usage
    name=$1
fi
[[ $name =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]] || fail 'name must contain only letters, digits, underscores or hyphens and start with a letter or digit'
worker_path=/code/hc-worktrees/$name
script_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
# In linked checkouts the common Git directory still identifies the main checkout.
common_dir=$(git -C "$script_root" rev-parse --path-format=absolute --git-common-dir)
main_checkout=$(dirname -- "$common_dir")
required=(AGENTS.md .banso/config.yaml README.md docs/RUNTIME_IMPLEMENTATION_CONTRACT.md)

if $remove; then
    registered=false
    while IFS= read -r -d '' field; do
        [[ $field != "worktree $worker_path" ]] || registered=true
    done < <(git -C "$script_root" worktree list --porcelain -z)
    $registered || fail 'requested path is not a worktree of this repository'
    status=$(git -C "$worker_path" status --porcelain --untracked-files=all) || fail 'could not inspect worktree status'
    [[ -z $status ]] || fail 'worktree is dirty; removal refused'
    git -C "$script_root" worktree remove "$worker_path"
    printf '%s\n' "$worker_path"
    exit 0
fi

[[ ! -e $worker_path && ! -L $worker_path ]] || fail 'destination already exists'
for file in "${required[@]}"; do
    [[ -f $main_checkout/$file ]] || fail "main checkout is missing $file"
done
ref=${2:-HEAD}
# Resolve before creating anything; HEAD refers to this invoking checkout.
commit=$(git -C "$script_root" rev-parse --verify --end-of-options "${ref}^{commit}" 2>/dev/null) || fail 'ref does not resolve to a commit'
# Git diagnostics may include private checkout paths; keep those local.
if ! git -C "$script_root" worktree add --quiet --detach "$worker_path" "$commit" 2>/dev/null; then
    fail 'git worktree add failed'
fi
mkdir -p -- "$worker_path/.banso"
cp -- "$main_checkout/AGENTS.md" "$worker_path/AGENTS.md" 2>/dev/null || fail 'could not copy AGENTS.md'
cp -- "$main_checkout/.banso/config.yaml" "$worker_path/.banso/config.yaml" 2>/dev/null || fail 'could not copy .banso/config.yaml'
for file in "${required[@]}"; do
    [[ -f $worker_path/$file ]] || fail "created worktree is missing $file"
done
printf '%s\n' "$worker_path"
