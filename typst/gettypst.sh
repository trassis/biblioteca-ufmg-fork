#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Uso: $0 [--printall] [--no-cache | --rebuild-cache] [--cache-dir DIR] [--jobs N] [--stats]" >&2
}

stats=false
args=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --printall|--no-cache|--rebuild-cache) args+=("$1"); shift ;;
        --stats) stats=true; args+=("$1"); shift ;;
        --jobs)
            if [[ $# -lt 2 || ! "$2" =~ ^[0-9]+$ || ${#2} -gt 2 ]]; then usage; exit 1; fi
            if (( 10#$2 < 1 || 10#$2 > 64 )); then usage; exit 1; fi
            args+=("$1" "$2"); shift 2 ;;
        --cache-dir)
            if [[ $# -lt 2 || -z "$2" ]]; then usage; exit 1; fi
            cache_dir="$2"
            [[ "$cache_dir" = /* ]] || cache_dir="$PWD/$cache_dir"
            args+=("$1" "$cache_dir"); shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) usage; exit 1 ;;
    esac
done

for dependency in g++ "${HASH_CPP:-cpp}" typst; do
    if ! command -v "$dependency" >/dev/null 2>&1; then
        echo "Dependência não encontrada: $dependency" >&2
        exit 1
    fi
done

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(dirname -- "$script_dir")"
build_dir="$(mktemp -d)"
trap 'rm -rf -- "$build_dir"' EXIT

: "${TEAMNAME:=Xerebêlerebébis}"
: "${MEMBERS:=Emanuel Silva, Bruno Monteiro & Rafael Grandsire}"
: "${UNIVERSITY:=UFMG}"

timed() {
    local label="$1"
    shift
    if "$stats"; then
        TIMEFORMAT="$label: %3R s"
        time "$@"
    else
        "$@"
    fi
}

timed "Compilação C++" g++ -std=c++17 -O2 -pthread "$script_dir/gettypst.cpp" -o "$build_dir/gettypst"
(
    cd -- "$repo_dir"
    timed "Geração dos hashes/documento" env CODE_DIR="$repo_dir/Codigo/" \
        "$build_dir/gettypst" --cache-dir "$script_dir/.cache/hashes" "${args[@]}" > "$build_dir/biblioteca.typ"
)
# Preserve the previous generated source if generation fails.
mv -- "$build_dir/biblioteca.typ" "$script_dir/biblioteca.typ"
mkdir -p -- "$repo_dir/pdf"
timed "Compilação Typst" typst compile --root "$repo_dir" \
    --input "teamname=$TEAMNAME" \
    --input "members=$MEMBERS" \
    --input "university=$UNIVERSITY" \
    "$script_dir/biblioteca.typ" "$repo_dir/pdf/biblioteca.pdf"
