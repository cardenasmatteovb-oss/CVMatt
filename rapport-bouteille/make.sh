#!/bin/bash
# Construit le docx en deux passes : la 2e remplit les numéros de page de la table des matières.
set -e
cd "$(dirname "$0")"
SK=/root/.claude/skills/synced/4b2ad4bb-b2e6-4bc5-baea-ad17c29c111d_1eee618c-41b0-4c83-a49a-a55fe0c8c4f4/docx
pack() { (cd out && rm -f ../rapport.docx && zip -qXrDy ../rapport.docx .); }
render() { rm -f rapport.pdf; python3 $SK/scripts/office/soffice.py --headless --convert-to pdf rapport.docx >/dev/null 2>&1; }

python3 build.py unpacked out
pack; render
# numéro de page affiché = page du PDF - 1 (page couverture non numérotée)
python3 - <<'EOF'
import json, subprocess
heads = json.load(open("heads_full.json"))
n = int([l for l in subprocess.run(["pdfinfo", "rapport.pdf"], capture_output=True, text=True).stdout.splitlines() if l.startswith("Pages")][0].split()[1])
pages = {}
start = 3  # on cherche après la table des matières
for lvl, text, bm in heads:
    for pg in range(start, n + 1):
        t = subprocess.run(["pdftotext", "-f", str(pg), "-l", str(pg), "-layout", "rapport.pdf", "-"], capture_output=True, text=True).stdout
        if any(line.strip() == text for line in t.splitlines()):
            pages[bm] = pg - 1
            start = pg
            break
    else:
        raise SystemExit(f"titre introuvable : {text}")
json.dump(pages, open("pages.json", "w"))
print(pages)
EOF
python3 build.py unpacked out pages.json
pack
zip -qd rapport.docx '*/' >/dev/null 2>&1 || true
render
python3 $SK/scripts/office/validate.py rapport.docx --original src/orig.docx
rm -f page-*.jpg; pdftoppm -jpeg -r 60 rapport.pdf page
ls page-*.jpg | wc -l
