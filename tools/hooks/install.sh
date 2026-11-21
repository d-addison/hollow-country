#!/bin/sh
# Opt-in installer. Honor core.hooksPath and worktree-aware git paths.
set -eu
replace=false
case "${1-}" in
    '') ;;
    --replace) replace=true ;;
    *) echo 'usage: tools/hooks/install.sh [--replace]' >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then
    echo 'usage: tools/hooks/install.sh [--replace]' >&2
    exit 2
fi
root=$(git rev-parse --show-toplevel)
cd "$root"
hooks=$(git rev-parse --git-path hooks)
mkdir -p "$hooks"
target=$hooks/pre-push
source=$root/tools/hooks/pre-push
if [ -L "$target" ] && [ "$(readlink "$target")" = "$source" ]; then
    echo 'pre-push hook already installed'
    exit 0
fi
if [ -e "$target" ] || [ -L "$target" ]; then
    if [ "$replace" != true ]; then
        echo 'Existing pre-push hook preserved; explicit --replace is required to replace it.' >&2
        exit 1
    fi
    if [ -d "$target" ] && [ ! -L "$target" ]; then
        echo 'Cannot replace a pre-push directory.' >&2
        exit 1
    fi
    rm "$target"
fi
ln -s "$source" "$target"
echo 'pre-push hook installed'
