#!/usr/bin/env bash
# Compila somente o guia teórico. Para a biblioteca: ../typst/gettypst.sh.
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd -- "$script_dir"

: "${TEAMNAME:=Xerebêlerebébis}"
: "${MEMBERS:=Emanuel Silva, Bruno Monteiro \\& Rafael Grandsire}"
: "${UNIVERSITY:=UFMG}"

trap 'rm -f -- "$script_dir/env.tex"' EXIT
printf '\\def\\teamname{%s}\n\\def\\teammembers{%s}\n\\def\\teamuni{%s}\n' \
    "$TEAMNAME" "$MEMBERS" "$UNIVERSITY" > env.tex

mkdir -p ../pdf
cd ../theoretical
latexmk -pdf theoretical -outdir=../pdf
latexmk -pdf theoretical -outdir=../pdf -c
