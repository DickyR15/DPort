from pathlib import Path
t=Path("src/templates/map.html").read_text(encoding="utf-8", errors="replace")

def out(label, s):
    print(label)
    print(s[:7000].encode("unicode_escape").decode("ascii"))

for term in [
    "dport-gpx-speed-select",
    "dport-gpx-speed-wrap",
    "dport-gpx-speed",
    "dport-gpx-card",
    "change",
]:
    print("\nTERM", term.encode("unicode_escape").decode("ascii"), "COUNT", t.count(term))
    pos=0
    n=0
    while n < 20:
        i=t.find(term,pos)
        if i < 0:
            break
        out(f"--- {i} ---", t[max(0,i-1600):i+5000])
        pos=i+len(term)
        n+=1

print("\nMAP CLICK HANDLERS")
start=0
while True:
    i=t.find("map.on('click'", start)
    if i<0:
        break
    out(f"--- {i} ---", t[i:i+7000])
    start=i+12
