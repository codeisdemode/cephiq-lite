import json
from pathlib import Path
from typing import Tuple, List

from jsonschema import Draft202012Validator


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8-sig")
        return json.loads(text)


def validate_envelope(envelope: dict, schema_path: Path) -> Tuple[bool, List[str]]:
    schema = load_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(envelope), key=lambda e: e.path)
    if not errors:
        return True, []
    msgs: List[str] = []
    for e in errors:
        loc = "/".join(str(p) for p in e.path) or "<root>"
        msgs.append(f"ERROR at {loc}: {e.message}")
    return False, msgs


if __name__ == "__main__":
    # Quick self-test with a minimal valid message envelope
    here = Path(__file__).resolve().parent.parent
    schema_path = here / "envelope.schema.json"
    sample = {"type": "message", "message": "ok", "brief_rationale": "Notify user."}
    ok, errs = validate_envelope(sample, schema_path)
    print("VALID" if ok else "INVALID")
    if not ok:
        print("\n".join(errs))

