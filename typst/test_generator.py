"""Run with: python3 -m unittest discover -s typst -p 'test_*.py'."""
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
        subprocess.run(["g++", "-std=c++17", "-O2", str(cls.source / "gettypst.cpp"),
                        "-o", str(cls.binary)], check=True)

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

    def generate(self, *args):
        return subprocess.run([str(self.binary), *args], cwd=self.work,
                              env={**os.environ, "CODE_DIR": str(self.code) + "/"},
                              text=True, capture_output=True, check=True).stdout

    def test_literal_code_titles_and_hashes(self):
        output = self.generate()
        self.assertIn('#heading(level: 2, "A # [titulo] $ 2^61 & \\"aspas\\"")', output)
        self.assertNotIn("Z oculto", output)
        blocks = [json.loads(value) for value in re.findall(
            r'#raw\(("(?:[^"\\]|\\.)*"), block: true', output)]
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
