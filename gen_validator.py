#!/usr/bin/env python3
"""Generator: writes validate_livability.py"""
import pathlib

SCRIPT = (
    'import asyncio, asyncpg, json, os
'
    'from dotenv import load_dotenv
'
    '
'
    'load_dotenv("C:/Users/mfont/projects/HouseMktAnalyzr/backend/.env")
'
    'DATABASE_URL = os.environ.get("DATABASE_URL")
'
    '
'
    'print("gen_validator loaded OK")
'
)

pathlib.Path('C:/Users/mfont/projects/HouseMktAnalyzr/validate_livability.py').write_text(SCRIPT)
print('done')
