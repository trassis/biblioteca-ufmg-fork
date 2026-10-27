#!/usr/bin/env python3
"""Benchmark generation without modifying tracked sources/PDFs.

Optional --baseline points to a copy of the previous gettypst.cpp. Every full
output is compared byte-for-byte when a baseline is provided. Results and
references live in --output, never in Codigo/ or pdf/.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = {}

    def measure(name, command, cwd, code=None, before=None):
        times = []
        for index in range(args.repeat):
            if before:
                before(index)
            started = time.perf_counter()
            with (output / (name + ".typ")).open("wb") as out, (output / (name + ".log")).open("wb") as err:
                subprocess.run([str(arg) for arg in command], cwd=cwd,
                               env={**os.environ, "CODE_DIR": str(code or ROOT / "Codigo") + "/"},
                               stdout=out, stderr=err, check=True)
            times.append(time.perf_counter() - started)
        results[name] = {"seconds": times, "median_seconds": statistics.median(times)}
        log = (output / (name + ".log")).read_text(errors="replace")
        for line in log.splitlines():
            if line.startswith("stats "):
                results[name]["stats"] = dict(part.split("=", 1) for part in line.split()[1:])
        print(name, results[name]["median_seconds"], flush=True)
        return (output / (name + ".typ")).read_bytes()

    with tempfile.TemporaryDirectory() as temp:
        work = Path(temp)
        optimized = work / "optimized"
        measure("compile", ["g++", "-std=c++17", "-O2", "-pthread",
                            ROOT / "typst/gettypst.cpp", "-o", optimized], work)
        legacy = None
        if args.baseline:
            legacy = work / "legacy"
            measure("legacy-compile", ["g++", "-std=c++17", "-O2", args.baseline.resolve(), "-o", legacy], work)
        for mode, flags in [("default", []), ("all", ["--printall"])]:
            reference = measure(mode + "-legacy", [legacy, *flags], work) if legacy else None
            cache = work / (mode + "-cache")
            base = [optimized, "--stats", "--cache-dir", cache, *flags]
            serial = measure(mode + "-cold", [*base, "--rebuild-cache"], work)
            warm = measure(mode + "-warm", base, work)
            parallel = measure(mode + "-parallel", [*base, "--no-cache", "--jobs", "4"], work)
            if serial != warm or serial != parallel or (reference is not None and serial != reference):
                raise RuntimeError("Output mismatch: " + mode)
            results[mode + "-equivalent"] = True
        # Reuse the cache, but change one algorithm in a private copy.
        copy = work / "Codigo"
        shutil.copytree(ROOT / "Codigo", copy)
        file = copy / "Grafos/dijkstra.cpp"
        original = file.read_bytes()
        measure("one-file-changed", [optimized, "--stats", "--cache-dir", work / "default-cache"], work, copy,
                before=lambda index: file.write_bytes(original + f"\n// benchmark: change {index}\n".encode()))
        if results["one-file-changed"]["stats"]["cache_misses"] != "1":
            raise RuntimeError("Expected exactly one invalidated cache entry")
        # Typst-only measurements do not rerun hash generation.
        if shutil.which("typst"):
            shutil.copy(ROOT / "typst/template.typ", output)
            measure("typst", ["typst", "compile", output / "default-cold.typ", output / "biblioteca.pdf"], work)
    (output / "results.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
