#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--printall" ) ]]; then
    echo "Uso: $0 [--printall]" >&2
    exit 1
fi

for dependency in g++ cpp md5sum typst; do
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

g++ -std=c++17 -O2 "$script_dir/gettypst.cpp" -o "$build_dir/gettypst"
# O gerador usa tmp.cpp para calcular os hashes; mantenha-o isolado.
(
    cd -- "$build_dir"
    CODE_DIR="$repo_dir/Codigo/" ./gettypst "$@" > biblioteca.typ
)
mv -- "$build_dir/biblioteca.typ" "$script_dir/biblioteca.typ"
mkdir -p -- "$repo_dir/pdf"
typst compile --root "$repo_dir" \
    --input "teamname=$TEAMNAME" \
    --input "members=$MEMBERS" \
    --input "university=$UNIVERSITY" \
    "$script_dir/biblioteca.typ" "$repo_dir/pdf/biblioteca.pdf"
