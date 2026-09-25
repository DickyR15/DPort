from pathlib import Path
import re

p=Path("src/templates/map.html")
t=p.read_text(encoding="utf-8",errors="replace")
print("TEMPLATE",p,len(t))

for pat in [r'<[^>]+id=["\']device["\'][^>]*>',
            r'<[^>]+id=["\'][^"\']*(?:speed|gpx)[^"\']*["\'][^>]*>',
            r'<[^>]+class=["\'][^"\']*(?:speed|gpx)[^"\']*["\'][^>]*>',
            r'<[^>]*>[^<]*(?:GPX|速度|步行|跑步|騎車|開車)[^<]*</[^>]+>',
            r'map\.on\([\'"]click[\'"][\s\S]{0,3000}']:
    print("PATTERN",pat)
    for m in list(re.finditer(pat,t,re.I))[:20]:
        print("----",m.start())
        print(t[max(0,m.start()-500):m.end()+1500].replace("\n"," ")[:3000])
