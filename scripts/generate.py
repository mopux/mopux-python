"""Generates src/mopux/models/_generated.py from spec/openapi.yaml (component schemas only)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "src/mopux/models/_generated.py"

subprocess.run(
    [
        sys.executable,
        "-m",
        "datamodel_code_generator",
        "--input",
        str(ROOT / "spec/openapi.yaml"),
        "--input-file-type",
        "openapi",
        "--openapi-scopes",
        "schemas",
        "--output-model-type",
        "pydantic_v2.BaseModel",
        "--target-python-version",
        "3.11",
        "--extra-fields",
        "allow",
        "--use-standard-collections",
        "--use-union-operator",
        "--use-schema-description",
        "--enum-field-as-literal",
        "all",
        "--disable-timestamp",
        "--use-type-alias",
        "--field-constraints",
        "--force-optional",
        "--use-annotated",
        "--formatters",
        "ruff-format",
        "--output",
        str(OUTPUT),
    ],
    check=True,
    cwd=ROOT,
)
# Emails are plain strings: EmailStr would need the optional email-validator package at runtime.
source = OUTPUT.read_text()
source = source.replace("EmailStr, ", "").replace("EmailStr", "str")
OUTPUT.write_text(source)
subprocess.run([sys.executable, "-m", "ruff", "format", str(OUTPUT)], check=True, cwd=ROOT, capture_output=True)
print(f"Generated {OUTPUT.relative_to(ROOT)}")
