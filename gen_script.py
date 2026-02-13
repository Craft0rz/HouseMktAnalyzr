import base64, pathlib, sys
b64 = sys.stdin.read().strip()
script = base64.b64decode(b64).decode("utf-8")
pathlib.Path("C:/Users/mfont/projects/HouseMktAnalyzr/validate_livability.py").write_text(script, encoding="utf-8")
print("Script written.")
