from pathlib import Path
import re

t=Path("src/templates/map.html").read_text(encoding="utf-8",errors="replace")
def out(label,s):
    print(label, s[:5000].encode("unicode_escape").decode("ascii"))

for term in ["dport-gpx-speed-select","dport-gpx-speed-wrap","dport-gpx-speed","addEventListener('change'","addEventListener("change"","change', function","change", function"]:
    print("\nTERM",term.encode("unicode_escape").decode("ascii"),"COUNT",t.count(term))
    pos=0
    n=0
    while True:
        i=t.find(term,pos)
        if i<0 or n>=12: break
        out(f"--- {i} ---",t[max(0,i-1800):i+3500])
        pos=i+len(term); n+=1

print("\nMAP CLICK CONTEXTS")
for m in re.finditer(r"map\\.on\\(['\"]click['\"][\\s\\S]{0,5000}",t):
    out(f"--- {m.start()} ---",t[m.start():m.end()])
