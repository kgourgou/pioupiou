#!/usr/bin/env python

# Python Standard Library
import codeop
import doctest
import os
import shutil
import sys
import tempfile

# Third-Party Libraries
import strictyaml

# Test Files
# ------------------------------------------------------------------------------
# Read mkdocs config file.
mkdocs_content = strictyaml.load(open("mkdocs.yml").read())["nav"].data
mkdocs_files = []
for value in [list(item.values())[0] for item in mkdocs_content]:
    if isinstance(value, str):  # page
        mkdocs_files.append(value)
    else:  # section
        mkdocs_files.extend([list(item.values())[0] for item in value])
mkdocs_files = ["mkdocs/" + file for file in mkdocs_files]
extra_testfiles = []
test_files = mkdocs_files + extra_testfiles

# Sandbox the Test Files
# ------------------------------------------------------------------------------
# This is required:
#   - to tweak the files before the tests,
#   - to avoid the generation of artifacts (generated by the test code)
#     in the current directory.
tmp_dir = tempfile.mkdtemp()  # TODO: clean-up this directory
for filename in test_files:
    target_file = os.path.join(tmp_dir, filename)
    target_dir = os.path.dirname(target_file)
    os.makedirs(target_dir, exist_ok=True)
    shutil.copy(filename, target_file)

# Tweak the Test Files
# ------------------------------------------------------------------------------
# For each file, find the python fences, see if they are in interpreter mode
# or "code" mode. If they are in code mode, add the prompts (use and heuristic,
# see <https://github.com/boisgera/pioupiou/issues/8>), then remove the fences
# and indent the code lines.
def promptize(src):
    "Add >>> or ... prompts to Python code"
    cc = codeop.compile_command  # symbol="single" (the default here)
    # is required to deal with if / else constructs properly
    # (without going back to the ">>> " prompt after the if clause).
    lines = src.splitlines()
    output = []
    chunk = []
    for line in lines:
        if chunk == []:  # new start
            output.append(">>> " + line)
        else:
            output.append("... " + line)
        chunk.append(line)
        try:
            code = cc("\n".join(chunk))
            if code is not None:  # full statement
                chunk = []  # start over
        except: # pragma: no cover
            raise
    assert len(lines) == len(output)
    return "\n".join(output)


def tweak(src):
    # Find code blocks with python fences,
    # add prompts when necessary,
    # then transform them into indented code blocks.
    lines = src.splitlines()
    chunks = {}
    start, end, code = None, None, []
    for i, line in enumerate(lines):
        if line.startswith("```python"):
            start = i
            code.append("")
        elif line.startswith("```"):
            end = i + 1
            code.append("")
            assert end - start == len(code)
            chunks[(start, end)] = code
            code = []
        elif code != []:
            code.append(line)

    for loc, code in chunks.items():
        chunk = "\n".join(code[1:-1])  # dont promptize initial and final newline
        if not chunk.strip().startswith(">>> "):  # prompts are missing
            code[1:-1] = promptize(chunk).splitlines()
        code = [4 * " " + line for line in code]
        chunks[loc] = code

    for (i, j), code in chunks.items():
        lines[i:j] = code
    new_src = "\n".join(lines)
    return new_src


cwd = os.getcwd()
os.chdir(tmp_dir)

for filename in test_files:
    with open(filename, encoding="utf-8") as file:
        src = file.read()
    src = tweak(src)
    with open(filename, "w", encoding="utf-8") as file:
        file.write(src)

# Run the Tests
# ------------------------------------------------------------------------------
verbose = "-v" in sys.argv or "--verbose" in sys.argv

fails = 0
tests = 0
for filename in test_files:
    options = {"module_relative": False, "verbose": verbose}
    _fails, _tests = doctest.testfile(filename, **options)
    fails += _fails
    tests += _tests

os.chdir(cwd)

if fails > 0 or verbose:  # pragma: no cover
    print()
    print(60 * "-")
    print("Test Suite Report:", end=" ")
    print("{0} failures / {1} tests".format(fails, tests))
    print(60 * "-")
if fails:  # pragma: no cover
    sys.exit(1)