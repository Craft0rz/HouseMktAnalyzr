import pathlib, textwrap
# This script writes the validation script
target = pathlib.Path("C:/Users/mfont/projects/HouseMktAnalyzr/validate_livability.py")
# Read the template from base64
import base64, sys
b64data = pathlib.Path("/tmp/validator_b64.txt").read_text().strip()
script = base64.b64decode(b64data).decode("utf-8")
target.write_text(script, encoding="utf-8")
print(f"Written {len(script)} chars to {target}")
