"""Broader retrieval for clips with weak or missing first-pass evidence."""
import json
from pathlib import Path
from match import search,OUT

if __name__=='__main__':
    inventory={r['path']:r for r in json.loads((OUT/'inventory.json').read_text())}
    rows=[]
    for p in sorted((OUT/'coarse').glob('*.json')):
        r=json.loads(p.read_text());c=r['candidates']
        if not c or c[0]['support']<5:rows.append(inventory[r['clip']])
    search(rows,'recovery',recovery=True)
