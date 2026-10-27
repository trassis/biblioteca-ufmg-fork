"""Run with: python3 -m unittest discover -s typst -p 'test_*.py'."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


class GeneratorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.source = Path(__file__).resolve().parent
        cls.binary = cls.root / "gettypst"
        subprocess.run(["g++", "-std=c++17", "-O2", "-pthread", str(cls.source / "gettypst.cpp"),
                        "-o", str(cls.binary)], check=True)
        # Exercise range hashing and process I/O without rendering 10,000 lines.
        probe_source = cls.root / "probe.cpp"
        probe_source.write_text(
            '#define main generator_main\n#include "' + str(cls.source / "gettypst.cpp") + '"\n'
            '#undef main\nint main(int argc, char** argv) {\n'
            'signal(SIGPIPE, SIG_IGN); try {\n'
            'std::string mode = argv[1];\n'
            'if (mode == "hash") { Source s(argv[2], false); Preprocessor p; '
            'std::cout << p.hash(s, std::stoi(argv[3]), std::stoi(argv[4])); }\n'
            'else { std::string input((std::istreambuf_iterator<char>(std::cin)), {});\n'
            'if (mode == "md5") std::cout << hashing::md5(input);\n'
            'else { auto r = hashing::run({argv[2]}, input); '
            'std::cout << r.output; std::cerr << r.error; return r.status; } }\n'
            '} catch (const std::exception& e) { std::cerr << e.what(); return 1; } }\n')
        cls.probe = cls.root / "probe"
        subprocess.run(["g++", "-std=c++17", "-O2", "-pthread", str(probe_source),
                        "-o", str(cls.probe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(dir=self.root))
        self.code = self.work / "Codigo"
        (self.code / "Teste" / "Nested").mkdir(parents=True)
        (self.code / "Extra").mkdir()
        (self.code / "Teste" / "Nested" / "a.cpp").write_text(
            '// A # [titulo] $ 2^61 & "aspas"\n//\n'
            '// Comentário com ``` e #raw("literal")\n'
            'int f() {\n\treturn 1;\n}\n', encoding="utf-8")
        (self.code / "Teste" / "z.cpp").write_text(
            '// Z oculto [noprint]\n//\nint z;\n', encoding="utf-8")
        (self.code / "Extra" / "hash.sh").write_text(
            '#!/bin/bash\nprintf "\\n" # ```\n', encoding="utf-8")

    def run_generator(self, *args, env=None, check=True):
        return subprocess.run([str(self.binary), *args], cwd=self.work,
                              env={**os.environ, "CODE_DIR": str(self.code) + "/", **(env or {})},
                              text=True, capture_output=True, check=check, timeout=30)

    def generate(self, *args):
        return self.run_generator(*args).stdout

    def stats(self, result):
        line = next(line for line in result.stderr.splitlines() if line.startswith("stats "))
        return dict(item.split("=", 1) for item in line.split()[1:])

    def test_literal_code_titles_and_hashes(self):
        output = self.generate()
        self.assertIn('#heading(level: 2, "A # [titulo] $ 2^61 & \\"aspas\\"")', output)
        self.assertNotIn("Z oculto", output)
        self.assertNotIn("#pagebreak", output)
        self.assertIn("hashed: true", output)
        self.assertIn("hashed: false", output)
        blocks = [json.loads(value) for value in re.findall(
            r'#listing\(("(?:[^"\\]|\\.)*"), hashed:', output)]
        self.assertEqual(len(blocks), 2)
        self.assertIn('// Comentário com ``` e #raw("literal")', blocks[0])
        self.assertRegex(blocks[0], r'(?m)^[0-9a-f]{3} int f\(\) \{$')
        self.assertRegex(blocks[0], r'(?m)^[0-9a-f]{3} \}$')
        self.assertEqual(blocks[1], '#!/bin/bash\nprintf "\\n" # ```\n')
        # Same preprocessing and hash semantics as the previous generator.
        expected = subprocess.run(
            "printf 'int f() {\\n\\treturn 1;\\n}\\n' | "
            "cpp -dD -P -fpreprocessed | tr -d '[:space:]' | md5sum | cut -c-3",
            shell=True, text=True, capture_output=True, check=True).stdout.strip()
        self.assertIn(expected + " }", blocks[0])

    def test_printall(self):
        output = self.generate("--printall")
        self.assertIn('"Z oculto"', output)
        self.assertNotIn("noprint", output)

    def test_md5_vectors(self):
        for data in [b"", b"a", b"abc", b"message digest", bytes(range(256)),
                     b"x" * 55, b"x" * 56, b"x" * 64, b"x" * 1000000]:
            with self.subTest(size=len(data)):
                result = subprocess.run([str(self.probe), "md5"], input=data,
                                        capture_output=True, check=True, timeout=10)
                self.assertEqual(result.stdout.decode(), hashlib.md5(data).hexdigest())

    def test_legacy_pipeline_edge_cases(self):
        snippets = [
            'int a; // comentário com acento\n',
            '#define A(x) ((x) + 1)\nint a = A(2);\n',
            '#warning ignorado\n#whatever ignorado também\nint a;\n',
            'const char* s = " a \\t b ";\nconst char* t = "/* literal */";\n',
            '/* bloco\n comentário */\nint\ta = 1;\n\n',
            '\v\fint a;\r\n',
            'int f() {\n\treturn 1;\n}\n',
            '#w ignored\n' + 'int a;\n' * 9999 + 'int ignored;\n',
        ]
        for index, snippet in enumerate(snippets):
            with self.subTest(index=index):
                file = self.work / "snippet.cpp"
                # A prefix verifies that the 10k cap applies after range selection.
                file.write_bytes(('// prefix\n' + snippet).encode())
                legacy = subprocess.run(
                    "sed -n '1,10000p' | sed '/^#w/d' | cpp -dD -P -fpreprocessed | "
                    "tr -d '[:space:]' | md5sum | cut -c-3", shell=True,
                    input=snippet.encode(), capture_output=True, check=True)
                result = subprocess.run([str(self.probe), "hash", str(file), "1",
                                         str(len(snippet.split('\n')) - 1)],
                                        capture_output=True, check=True, timeout=15)
                self.assertEqual(result.stdout.strip(), legacy.stdout.strip())

    def test_cache_hits_and_rebuild(self):
        cold = self.run_generator("--stats")
        self.assertGreater(int(self.stats(cold)["cpp_processes"]), 0)
        warm = self.run_generator("--stats")
        self.assertEqual(cold.stdout, warm.stdout)
        self.assertEqual(self.stats(warm)["cpp_processes"], "0")
        self.assertEqual(self.stats(warm)["cache_misses"], "0")
        rebuilt = self.run_generator("--rebuild-cache", "--stats")
        self.assertEqual(rebuilt.stdout, cold.stdout)
        self.assertGreater(int(self.stats(rebuilt)["cpp_processes"]), 0)

    def test_changed_deleted_and_hidden_files(self):
        self.generate()
        file = self.code / "Teste" / "Nested" / "a.cpp"
        file.write_text(file.read_text().replace("return 1;", "return 2;"))
        changed = self.run_generator("--stats")
        self.assertEqual(self.stats(changed)["cache_misses"], "1")
        self.assertIn("return 2;", changed.stdout)
        all_files = self.run_generator("--printall", "--stats")
        self.assertEqual(self.stats(all_files)["cache_misses"], "1")
        file.unlink()
        deleted = self.run_generator("--stats")
        self.assertEqual(self.stats(deleted)["cpp_processes"], "0")
        self.assertNotIn("return 2;", deleted.stdout)

    def test_corrupt_cache_is_a_miss(self):
        expected = self.generate()
        for file in (self.work / ".hash-cache").glob("*.cache"):
            file.write_bytes(b"truncated or corrupted cache")
        result = self.run_generator("--stats")
        self.assertEqual(result.stdout, expected)
        self.assertEqual(self.stats(result)["cache_hits"], "0")
        # A valid header with a modified payload must also be rejected.
        for file in (self.work / ".hash-cache").glob("*.cache"):
            file.write_bytes(file.read_bytes() + b"tampered")
        self.assertEqual(self.run_generator("--stats").stdout, expected)

    def test_no_cache_and_custom_directory(self):
        cold = self.run_generator("--no-cache", "--stats")
        self.assertFalse((self.work / ".hash-cache").exists())
        custom = self.work / "cache with spaces"
        cached = self.run_generator("--cache-dir", str(custom), "--stats")
        self.assertEqual(cold.stdout, cached.stdout)
        self.assertTrue(list(custom.glob("*.cache")))
        bypass = self.run_generator("--cache-dir", str(custom), "--no-cache", "--stats")
        self.assertEqual(self.stats(bypass)["cache_hits"], "0")
        blocked = self.work / "not-a-directory"
        blocked.write_text("regular file")
        unavailable = self.run_generator("--cache-dir", str(blocked))
        self.assertEqual(unavailable.stdout, cold.stdout)
        self.assertIn("continuando sem cache", unavailable.stderr)

    def test_configuration_invalidates_cache(self):
        self.generate()
        changed = self.run_generator("--stats", env={"LC_ALL": "C"})
        self.assertEqual(self.stats(changed)["cache_hits"], "0")
        warm = self.run_generator("--stats", env={"LC_ALL": "C"})
        self.assertEqual(self.stats(warm)["cpp_processes"], "0")

    def test_preprocessor_identity_invalidates_cache(self):
        wrapper = self.work / "cpp-wrapper"
        wrapper.write_text('#!/bin/sh\nexec cpp "$@"\n')
        wrapper.chmod(0o755)
        env = {"HASH_CPP": str(wrapper)}
        cold = self.run_generator("--stats", env=env)
        self.assertEqual(self.stats(self.run_generator("--stats", env=env))["cpp_processes"], "0")
        # Same path and --version, different executable content.
        wrapper.write_text('#!/bin/sh\n# updated wrapper\nexec cpp "$@"\n')
        changed = self.run_generator("--stats", env=env)
        self.assertEqual(changed.stdout, cold.stdout)
        self.assertEqual(self.stats(changed)["cache_hits"], "0")

    def test_parallel_order_and_shared_cache(self):
        expected = self.generate("--no-cache", "--printall")
        # Two generators can populate the same cache without partial entries.
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(self.generate, "--jobs", "4", "--printall") for _ in range(2)]
            for future in futures:
                self.assertEqual(future.result(), expected)
        self.assertEqual(self.stats(self.run_generator("--printall", "--stats"))["cpp_processes"], "0")
        self.assertFalse(list((self.work / ".hash-cache").glob("*.tmp.*")))

    def test_failed_preprocessor_does_not_cache_partial_output(self):
        wrapper = self.work / "broken cpp"
        wrapper.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo test-cpp; exit 0; fi\n'
                           'cat >/dev/null\nprintf "partial output"\necho "expected failure" >&2\nexit 7\n')
        wrapper.chmod(0o755)
        result = self.run_generator(env={"HASH_CPP": str(wrapper)}, check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("código 7", result.stderr)
        self.assertIn("expected failure", result.stderr)
        self.assertFalse(list((self.work / ".hash-cache").glob("*.cache")))
        missing = self.run_generator(env={"HASH_CPP": "/nonexistent/cpp"}, check=False)
        self.assertNotEqual(missing.returncode, 0)

    def test_process_drains_large_pipes_and_propagates_failure(self):
        wrapper = self.work / "large-process"
        wrapper.write_text('#!/usr/bin/env python3\nimport sys\n'
                           'sys.stdout.buffer.write(b"o" * 200000); sys.stdout.flush()\n'
                           'sys.stderr.buffer.write(b"e" * 200000); sys.stderr.flush()\n'
                           'data = sys.stdin.buffer.read()\n'
                           'sys.stdout.buffer.write(data)\nsys.exit(7)\n')
        wrapper.chmod(0o755)
        result = subprocess.run([str(self.probe), "run", str(wrapper)], input=b"i" * 500000,
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 7)
        self.assertEqual(result.stdout, b"o" * 200000 + b"i" * 500000)
        self.assertEqual(result.stderr, b"e" * 200000)
        wrapper.write_text('#!/bin/sh\necho "early exit" >&2\nexit 7\n')
        early = subprocess.run([str(self.probe), "run", str(wrapper)], input=b"i" * 500000,
                               capture_output=True, timeout=10)
        self.assertNotEqual(early.returncode, 0)
        self.assertIn(b"early exit", early.stderr)

    def test_invalid_options(self):
        for args in [("--jobs", "0"), ("--jobs", "65"), ("--jobs", "-1"),
                     ("--jobs", "abc"), ("--cache-dir",), ("--unknown",)]:
            with self.subTest(args=args):
                self.assertNotEqual(self.run_generator(*args, check=False).returncode, 0)

    @unittest.skipUnless(shutil.which("typst"), "Typst não está no PATH")
    def test_hashes_use_comment_color(self):
        import xml.etree.ElementTree as ET
        shutil.copy(self.source / "template.typ", self.work)
        source = self.work / "colors.typ"
        source.write_text('#import "template.typ": listing\n'
                          '#listing("12f int a;\\n// comment\\n", hashed: true)\n')
        svg = self.work / "colors.svg"
        subprocess.run(["typst", "compile", "--format", "svg", str(source), str(svg)], check=True)
        colors = [element.attrib["fill"] for element in ET.parse(svg).iter()
                  if element.tag.endswith("}use") and "fill" in element.attrib]
        self.assertEqual(colors[:3], ["#8a8a8a"] * 3)
        self.assertEqual(colors[-9:], ["#8a8a8a"] * 9)
        self.assertIn("#d73a49", colors[3:-9])  # Keywords retain syntax highlighting.

    @unittest.skipUnless(shutil.which("typst"), "Typst não está no PATH")
    def test_typst_compilation(self):
        (self.work / "biblioteca.typ").write_text(self.generate(), encoding="utf-8")
        shutil.copy(self.source / "template.typ", self.work)
        subprocess.run(["typst", "compile", "--input", 'teamname=Time # & "teste"',
                        str(self.work / "biblioteca.typ"), str(self.work / "test.pdf")],
                       check=True)
        self.assertTrue((self.work / "test.pdf").read_bytes().startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
