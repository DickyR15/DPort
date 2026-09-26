from pathlib import Path
import re

path = Path("src/templates/map.html")
if not path.exists():
    raise SystemExit(f"UI template not found: {path}")

html = path.read_text(encoding="utf-8")

# Critical pre-paint theme: the final UI stylesheet is appended later in this
# script, so establish the dark canvas/panels inside <head> first. This
# prevents a visible light/default-theme flash while Chromium parses the page
# and before the final layout polish is applied.
critical_prepaint = r'''<style id="dport-prepaint-critical">
html,body{
  margin:0!important;
  background:#161b24!important;
  color:#f5f7fb!important;
}
body{
  min-height:100vh!important;
  color-scheme:dark!important;
}
body > div, main, section, article, aside, header, .card, .panel{
  box-sizing:border-box;
}
#map,.leaflet-container,.map-container{
  background:#202733!important;
}
.dport-hero,.geoport-control-panel,.geoport-map-panel,.geoport-gpx-card,
.geoport-location-card,.geoport-status-card{
  background:#1d2430!important;
  color:#f5f7fb!important;
}
</style>'''

if 'id="dport-prepaint-critical"' not in html and '<head' in html:
    html = re.sub(r'(<head[^>]*>)', r'\1\n' + critical_prepaint, html, count=1, flags=re.I)
elif 'id="dport-prepaint-critical"' in html:
    pass
else:
    raise SystemExit('Unable to locate <head>; refusing to add pre-paint CSS blindly.')
# Rebuild the desktop header from one authoritative block. This removes all
# previous layered header CSS/JS revisions without touching the rest of UI.
for pattern in (
    r'\s*<style id="dport-header-final-v[0-9]+">.*?</style>\s*',
    r'\s*<style id="dport-top-header-final-v[0-9]+">.*?</style>\s*',
    r'\s*<script id="dport-top-header-final-v[0-9]+-script">.*?</script>\s*',
    r'\s*<style id="dport-top-header-layout-v[0-9]+">.*?</style>\s*',
    r'\s*<script id="dport-top-header-layout-script-v[0-9]+">.*?</script>\s*',
    r'\s*<style id="dport-ultra-header-layout-v[0-9]+">.*?</style>\s*',
    r'\s*<script id="dport-ultra-header-layout-v[0-9]+-script">.*?</script>\s*',
    r'\s*<style id="dport-ultra-header-notification-v[0-9]+">.*?</style>\s*',
    r'\s*<script id="dport-ultra-header-notification-v[0-9]+-script">.*?</script>\s*',
):
    html = re.sub(pattern, "\n", html, flags=re.S)

# Remove any persistent notification card from old header experiments.
html = re.sub(
    r'\s*<div[^>]*id=["\']dport-persistent-notification["\'][\s\S]*?</div>\s*',
    "\n", html, flags=re.I
)

# Update-check wording only. The updater still decides when the result is shown.
html = html.replace("（GitHub 最新正式版）", "（最新）")
html = html.replace("DPort：檢查 GitHub 最新正式版…", "DPort：檢查更新中…")
html = re.sub(r'DPort：v\d+\.\d+\.\d+（最新）', '', html)

css = "\n<style id=\"dport-final-ui-polish-v8\">\n:root{\n    --dport-panel:#2a3240;\n    --dport-panel-hover:#323c4e;\n    --dport-border:#5d6c88;\n    --dport-border-hover:#8295bd;\n    --dport-text:#f7f9fc;\n    --dport-muted:#aeb8ca;\n    --dport-blue:#5669e7;\n    --dport-blue-hover:#697bf4;\n    --dport-action-bg:rgba(67,78,98,.66);\n    --dport-action-hover:rgba(87,101,126,.84);\n    --dport-action-border:rgba(127,143,171,.72);\n    --dport-action-text:#edf2fa;\n}\n\n/* DPort application buttons. Map controls are intentionally excluded. */\nbody button:not(.leaflet-control-button):not(.leaflet-bar a):not(.leaflet-control-zoom a){\n    box-sizing:border-box !important;\n    font-family:inherit !important;\n    font-weight:700 !important;\n    border-radius:10px !important;\n    transition:\n        background .16s ease,\n        border-color .16s ease,\n        color .16s ease,\n        box-shadow .16s ease,\n        transform .16s ease !important;\n}\nbody button:not(.leaflet-control-button):not(.leaflet-bar a):not(.leaflet-control-zoom a):hover{\n    transform:translateY(-1px) !important;\n}\nbody button:not(.leaflet-control-button):not(.leaflet-bar a):not(.leaflet-control-zoom a):active{\n    transform:translateY(0) !important;\n}\nbody button:disabled{\n    opacity:.48 !important;\n    cursor:not-allowed !important;\n    transform:none !important;\n}\n\n/* Dark blue-gray utility / clear family. */\n#geoport-copy-coordinates,\n#geoport-load-last,\n#geoport-clear-coordinates,\n.geoport-recent-delete-selected,\n.geoport-recent-clear,\n.geoport-fav-clear-all{\n    background:var(--dport-action-bg) !important;\n    border:1px solid var(--dport-action-border) !important;\n    color:var(--dport-action-text) !important;\n    box-shadow:0 2px 8px rgba(0,0,0,.10) !important;\n}\n#geoport-copy-coordinates:hover,\n#geoport-load-last:hover,\n#geoport-clear-coordinates:hover,\n.geoport-recent-delete-selected:hover,\n.geoport-recent-clear:hover,\n.geoport-fav-clear-all:hover{\n    background:var(--dport-action-hover) !important;\n    border-color:var(--dport-border-hover) !important;\n    color:#fff !important;\n    box-shadow:0 6px 15px rgba(0,0,0,.18) !important;\n}\n\n/* Favorite section. */\n.geoport-favorites-title{\n    display:flex !important;\n    align-items:center !important;\n    justify-content:space-between !important;\n    gap:10px !important;\n    margin:14px 0 8px !important;\n}\n.geoport-favorites-actions{\n    display:flex !important;\n    align-items:center !important;\n}\n.geoport-fav-count{\n    color:var(--dport-muted) !important;\n    font-size:13px !important;\n    font-weight:700 !important;\n}\n.geoport-fav-list{\n    display:grid !important;\n    grid-template-columns:repeat(2,minmax(0,1fr)) !important;\n    grid-template-rows:repeat(3,68px) !important;\n    grid-auto-rows:68px !important;\n    gap:8px !important;\n    padding:9px !important;\n    margin:0 !important;\n    height:236px !important;\n    max-height:236px !important;\n    overflow-y:auto !important;\n    overflow-x:hidden !important;\n    border:1px solid #46536b !important;\n    border-radius:14px !important;\n    background:rgba(29,35,47,.74) !important;\n    scrollbar-width:thin !important;\n    scrollbar-color:#68758d transparent !important;\n}\n.geoport-fav-list::-webkit-scrollbar{width:7px}\n.geoport-fav-list::-webkit-scrollbar-track{background:transparent}\n.geoport-fav-list::-webkit-scrollbar-thumb{background:#68758d;border-radius:999px}\n\n.geoport-fav-card{\n    position:relative !important;\n    width:100% !important;\n    height:68px !important;\n    min-width:0 !important;\n    min-height:68px !important;\n    overflow:hidden !important;\n    border-radius:11px !important;\n}\n.geoport-fav-open{\n    position:absolute !important;\n    inset:0 !important;\n    width:100% !important;\n    height:100% !important;\n    min-height:0 !important;\n    box-sizing:border-box !important;\n    display:flex !important;\n    align-items:center !important;\n    justify-content:flex-start !important;\n    text-align:left !important;\n    padding:8px 28px 8px 13px !important;\n    border:1px solid #5d6c88 !important;\n    border-radius:11px !important;\n    background:var(--dport-panel) !important;\n    color:var(--dport-text) !important;\n    box-shadow:0 2px 8px rgba(0,0,0,.10) !important;\n    overflow:hidden !important;\n    z-index:1 !important;\n}\n.geoport-fav-open:hover{\n    background:var(--dport-panel-hover) !important;\n    border-color:var(--dport-border-hover) !important;\n    box-shadow:0 7px 16px rgba(0,0,0,.20) !important;\n}\n.geoport-fav-name{\n    display:-webkit-box !important;\n    width:100% !important;\n    max-width:100% !important;\n    margin:0 !important;\n    padding:0 !important;\n    color:var(--dport-text) !important;\n    font-size:15px !important;\n    font-weight:700 !important;\n    line-height:1.17 !important;\n    white-space:normal !important;\n    overflow:hidden !important;\n    text-overflow:clip !important;\n    -webkit-box-orient:vertical !important;\n    -webkit-line-clamp:2 !important;\n    overflow-wrap:anywhere !important;\n}\n.geoport-fav-name.long{font-size:14px !important}\n.geoport-fav-name.xlong{font-size:12.5px !important;line-height:1.08 !important}\n.geoport-fav-detail{display:none !important}\n\n/* Keep a comfortable click target, but show the X as a small chip in the\n   bottom-right INSIDE the card. */\nhtml body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete{\n    position:absolute !important;\n    top:auto !important;\n    left:auto !important;\n    right:2px !important;\n    bottom:2px !important;\n    width:30px !important;\n    min-width:30px !important;\n    max-width:30px !important;\n    height:30px !important;\n    min-height:30px !important;\n    max-height:30px !important;\n    margin:0 !important;\n    padding:0 !important;\n    border:0 !important;\n    border-radius:8px !important;\n    background:transparent !important;\n    color:transparent !important;\n    font-size:0 !important;\n    line-height:0 !important;\n    box-shadow:none !important;\n    overflow:visible !important;\n    transform:none !important;\n    z-index:20 !important;\n    cursor:pointer !important;\n}\nhtml body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete::before{\n    content:'' !important;\n    position:absolute !important;\n    right:6px !important;\n    bottom:6px !important;\n    width:18px !important;\n    height:18px !important;\n    border-radius:5px !important;\n    background:rgba(67,78,98,.70) !important;\n    border:1px solid rgba(127,143,171,.72) !important;\n    box-sizing:border-box !important;\n    box-shadow:0 2px 6px rgba(0,0,0,.15) !important;\n}\nhtml body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete::after{\n    content:'×' !important;\n    position:absolute !important;\n    right:6px !important;\n    bottom:6px !important;\n    width:18px !important;\n    height:18px !important;\n    display:flex !important;\n    align-items:center !important;\n    justify-content:center !important;\n    color:#edf2fa !important;\n    font-size:12px !important;\n    line-height:18px !important;\n    font-weight:800 !important;\n}\nhtml body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete:hover::before{\n    background:rgba(87,101,126,.88) !important;\n    border-color:#8fa1c1 !important;\n}\nhtml body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete:hover::after{\n    color:#ffffff !important;\n}\n\n/* Favorite clear-all button stays compact and in the same blue-gray family. */\n.geoport-fav-clear-all{\n    min-width:56px !important;\n    min-height:38px !important;\n    height:38px !important;\n    padding:5px 13px !important;\n    border-radius:9px !important;\n}\n\n/* Top-right status notification, always clipped inside the map frame. */\n#dport-map-status-overlay{\n    position:absolute !important;\n    top:8px !important;\n    right:8px !important;\n    left:auto !important;\n    bottom:auto !important;\n    z-index:900 !important;\n    width:min(320px,34%) !important;\n    max-width:calc(100% - 16px) !important;\n    min-width:0 !important;\n    margin:0 !important;\n    padding:0 !important;\n    box-sizing:border-box !important;\n    pointer-events:none !important;\n    overflow:hidden !important;\n}\n#dport-map-status-overlay > *{\n    width:100% !important;\n    max-width:100% !important;\n    min-width:0 !important;\n    box-sizing:border-box !important;\n    padding:7px 10px !important;\n    margin:0 !important;\n    background:rgba(31,38,50,.93) !important;\n    border:1px solid rgba(92,108,137,.84) !important;\n    border-radius:9px !important;\n    color:#f5f7fb !important;\n    box-shadow:0 7px 18px rgba(0,0,0,.22) !important;\n    backdrop-filter:blur(7px) !important;\n    overflow:hidden !important;\n    font-size:13px !important;\n    line-height:1.3 !important;\n}\n#dport-map-status-overlay > * *{\n    max-width:100% !important;\n    font-size:13px !important;\n    line-height:1.3 !important;\n    overflow:hidden !important;\n    text-overflow:ellipsis !important;\n}\n@media (max-width:1100px){\n    #dport-map-status-overlay{\n        width:min(280px,42%) !important;\n    }\n    #dport-map-status-overlay > *,\n    #dport-map-status-overlay > * *{\n        font-size:12px !important;\n    }\n}\n@media (max-width:700px){\n    #dport-map-status-overlay{\n        top:6px !important;\n        right:6px !important;\n        width:min(245px,56%) !important;\n        max-width:calc(100% - 12px) !important;\n    }\n}\n</style>\n"
favorites_js = "\n<script id=\"dport-final-favorites-render-v8\">\n(function(){\n    function renderFavorites(){\n        var box=document.getElementById('geoport-favorites');\n        if(!box || typeof geoportGetFavorites!=='function') return;\n        var items=geoportGetFavorites() || [];\n        box.innerHTML='';\n\n        var count=document.getElementById('geoport-fav-count');\n        if(count) count.textContent=items.length + '/20';\n\n        if(!items.length){\n            box.innerHTML='<div class=\"geoport-fav-empty\">還沒有儲存的位置</div>';\n            return;\n        }\n\n        items.forEach(function(item,index){\n            var card=document.createElement('div');\n            card.className='geoport-fav-card';\n\n            var open=document.createElement('button');\n            open.type='button';\n            open.className='geoport-fav-open';\n            open.title='前往 ' + String(item.name || '未命名位置');\n\n            var name=document.createElement('span');\n            name.className='geoport-fav-name';\n            var text=String(item.name || '未命名位置');\n            if(text.length > 16) name.classList.add('long');\n            if(text.length > 28) name.classList.add('xlong');\n            name.textContent=text;\n\n            open.appendChild(name);\n            open.onclick=function(){\n                geoportSetMapOnlyCoordinates(item.lat,item.lng);\n                geoportMoveActiveMarker(item.lat,item.lng,15);\n                if(typeof geoportStatus==='function'){\n                    geoportStatus('已載入最愛位置',false);\n                }\n            };\n\n            var del=document.createElement('button');\n            del.type='button';\n            del.className='geoport-fav-delete';\n            del.textContent='×';\n            del.title='刪除 ' + text;\n            del.setAttribute('aria-label','刪除 ' + text);\n            del.onclick=function(event){\n                event.preventDefault();\n                event.stopPropagation();\n                var next=geoportGetFavorites() || [];\n                next.splice(index,1);\n                geoportSetFavorites(next);\n                renderFavorites();\n            };\n\n            card.appendChild(open);\n            card.appendChild(del);\n            box.appendChild(card);\n        });\n    }\n\n    window.geoportRenderFavorites=renderFavorites;\n\n    function init(){\n        renderFavorites();\n    }\n\n    if(document.readyState==='loading'){\n        document.addEventListener('DOMContentLoaded',init,{once:true});\n    }else{\n        init();\n    }\n})();\n</script>\n"
status_js = "\n<script id=\"dport-map-status-overlay-script\">\n(function(){\n    function findStatusCard(){\n        var found=[];\n        document.querySelectorAll('body *').forEach(function(el){\n            if(!el || el.id==='dport-map-status-overlay') return;\n            var t=(el.innerText||'').replace(/\\\\s+/g,' ').trim();\n            if(\n                (t.indexOf('準備就緒')>=0 || t.indexOf('定位套用失敗')>=0 ||\n                 t.indexOf('定位成功')>=0 || t.indexOf('目前尚未偵測')>=0) &&\n                (t.indexOf('USB')>=0 || t.indexOf('裝置')>=0 || t.indexOf('座標')>=0)\n            ){\n                var r=el.getBoundingClientRect();\n                if(r.width>=140 && r.height>=28 && r.width<=700 && r.height<=280){\n                    found.push(el);\n                }\n            }\n        });\n        found.sort(function(a,b){\n            var ra=a.getBoundingClientRect(), rb=b.getBoundingClientRect();\n            return (ra.width*ra.height)-(rb.width*rb.height);\n        });\n        return found[0] || null;\n    }\n\n    function getMapFrame(){\n        var selectors=['.leaflet-container','#map','.map-container'];\n        for(var i=0;i<selectors.length;i++){\n            var map=document.querySelector(selectors[i]);\n            if(!map) continue;\n            var r=map.getBoundingClientRect();\n            if(r.width>=250 && r.height>=180) return map;\n        }\n        return null;\n    }\n\n    function mount(){\n        if(document.getElementById('dport-map-status-overlay')) return true;\n        var map=getMapFrame();\n        var source=findStatusCard();\n        if(!map || !source) return false;\n\n        var holder=document.createElement('div');\n        holder.id='dport-map-status-overlay';\n        map.appendChild(holder);\n        holder.appendChild(source);\n        return true;\n    }\n\n    function ensure(){\n        if(mount()) return;\n        [200,500,1000,1800,3000].forEach(function(ms){\n            setTimeout(mount,ms);\n        });\n    }\n\n    if(document.readyState==='loading'){\n        document.addEventListener('DOMContentLoaded',ensure,{once:true});\n    }else{\n        ensure();\n    }\n    window.addEventListener('load',ensure);\n})();\n</script>\n"
header_css = r"""
<style id="dport-header-final-v2">
/*
  DPort Header final visual reference:
  Brand -> GPX -> Device -> Refresh -> Connect -> Exit.
  No notification column.
*/
@media (min-width:1600px){
  .dport-hero{
    display:grid!important;
    grid-template-columns:clamp(300px,19vw,340px) minmax(600px,1fr) clamp(560px,31vw,680px) 82px!important;
    column-gap:14px!important;
    row-gap:0!important;
    align-items:center!important;
    justify-content:start!important;
    width:100%!important;
    min-width:0!important;
    max-width:100%!important;
    height:100px!important;
    min-height:100px!important;
    max-height:100px!important;
    padding:8px 14px!important;
    box-sizing:border-box!important;
    overflow:hidden!important;
  }

  /* No header notifications. All reminders remain in the left green status area. */
  .dport-hero-notifications{
    display:none!important;
    width:0!important;height:0!important;min-width:0!important;min-height:0!important;
    max-width:0!important;max-height:0!important;margin:0!important;padding:0!important;overflow:hidden!important;
  }

  .dport-brand{
    grid-column:1!important;grid-row:1!important;
    display:flex!important;align-items:center!important;
    width:100%!important;min-width:0!important;max-width:none!important;
    height:86px!important;min-height:86px!important;max-height:86px!important;
    margin:0!important;padding:0!important;overflow:hidden!important;box-sizing:border-box!important;
  }
  .dport-brand-icon{
    flex:0 0 84px!important;
    width:84px!important;height:84px!important;
    min-width:84px!important;min-height:84px!important;
    max-width:84px!important;max-height:84px!important;
    border-radius:16px!important;
  }
  .dport-brand-text{
    min-width:0!important;
    max-width:calc(100% - 100px)!important;
    margin-left:14px!important;
    overflow:hidden!important;
  }
  .dport-title{
    font-size:30px!important;line-height:1.05!important;font-weight:850!important;
    white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-subtitle{
    margin-top:5px!important;font-size:12px!important;line-height:1.2!important;
    white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-caption,
  #dport-pm3-status{
    margin-top:3px!important;font-size:10.5px!important;line-height:1.15!important;
    white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }

  .dport-header-center{display:contents!important;min-width:0!important}
  .dport-standard-device-slot{display:none!important}

  /* GPX: visual priority second only to brand. */
  .dport-ultra-gpx-slot{
    grid-column:2!important;grid-row:1!important;
    width:100%!important;min-width:0!important;max-width:none!important;
    height:86px!important;min-height:86px!important;max-height:86px!important;
    margin:0!important;padding:0!important;overflow:hidden!important;box-sizing:border-box!important;
    justify-self:stretch!important;align-self:center!important;
  }
  .dport-ultra-gpx-slot > *{
    width:100%!important;min-width:0!important;max-width:none!important;box-sizing:border-box!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-card{
    display:block!important;width:100%!important;height:86px!important;min-height:86px!important;max-height:86px!important;
    min-width:0!important;max-width:none!important;margin:0!important;padding:6px 9px!important;
    box-sizing:border-box!important;overflow:hidden!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-head{
    display:grid!important;grid-template-columns:minmax(0,1fr) auto auto!important;
    align-items:center!important;gap:9px!important;width:100%!important;min-width:0!important;max-width:none!important;
    height:28px!important;min-height:28px!important;max-height:28px!important;margin:0!important;padding:0!important;overflow:hidden!important;
    box-sizing:border-box!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-head > *{
    min-width:0!important;max-width:100%!important;box-sizing:border-box!important;
  }
  .dport-ultra-gpx-slot .dport-section-kicker{
    font-size:9px!important;line-height:1!important;
  }
  .dport-ultra-gpx-slot .dport-section-title{
    font-size:18px!important;line-height:19px!important;font-weight:850!important;
    min-width:0!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-status-pill{
    max-width:135px!important;min-width:0!important;padding:3px 8px!important;
    font-size:9px!important;line-height:14px!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-speed-wrap{
    display:flex!important;align-items:center!important;justify-content:flex-end!important;gap:5px!important;min-width:0!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-speed-label{
    font-size:9px!important;white-space:nowrap!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-speed-select{
    width:118px!important;min-width:118px!important;max-width:118px!important;height:30px!important;min-height:30px!important;
    padding:3px 22px 3px 8px!important;font-size:10.5px!important;box-sizing:border-box!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-grid{
    display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:7px!important;
    width:100%!important;min-width:0!important;max-width:none!important;
    height:45px!important;min-height:45px!important;max-height:45px!important;
    margin:5px 0 0!important;padding:0!important;overflow:hidden!important;box-sizing:border-box!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-item{
    width:100%!important;min-width:0!important;height:45px!important;min-height:45px!important;max-height:45px!important;
    margin:0!important;padding:6px 8px!important;border-radius:9px!important;box-sizing:border-box!important;overflow:hidden!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-item span{
    display:block!important;max-width:100%!important;font-size:9px!important;line-height:10px!important;
    white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-item strong{
    display:block!important;max-width:100%!important;margin-top:2px!important;font-size:13px!important;line-height:16px!important;
    font-weight:800!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }

  /* Device block: complete phone selector first, then Refresh + Connect. */
  .dport-ultra-device-slot{
    grid-column:3!important;grid-row:1!important;
    width:100%!important;min-width:0!important;max-width:none!important;
    height:86px!important;min-height:86px!important;max-height:86px!important;
    display:block!important;margin:0!important;padding:0!important;overflow:hidden!important;box-sizing:border-box!important;
  }
  .dport-ultra-device-slot .dport-connection-panel{
    width:100%!important;height:86px!important;min-height:86px!important;max-height:86px!important;min-width:0!important;max-width:none!important;
    margin:0!important;padding:8px 9px!important;box-sizing:border-box!important;overflow:hidden!important;
  }
  .dport-ultra-device-slot .dport-connection-title{margin:0 0 5px!important}
  .dport-ultra-device-slot .dport-section-kicker{font-size:9px!important;line-height:1!important}
  .dport-ultra-device-slot .dport-mini-title{font-size:15px!important;line-height:1.05!important;font-weight:850!important}
  .dport-ultra-device-slot .dport-connection-body{
    display:flex!important;flex-direction:row!important;align-items:center!important;flex-wrap:nowrap!important;gap:8px!important;
    width:100%!important;min-width:0!important;max-width:100%!important;margin:0!important;padding:0!important;overflow:hidden!important;
  }
  .dport-ultra-device-slot .dport-connection-body>form{
    flex:1 1 auto!important;width:auto!important;min-width:0!important;max-width:none!important;margin:0!important;padding:0!important;overflow:hidden!important;
  }
  .dport-ultra-device-slot .dport-connection-body form>.mb-3,
  .dport-ultra-device-slot .dport-connection-body form>.mb-3>.row{
    width:100%!important;min-width:0!important;margin:0!important;padding:0!important;
  }
  .dport-ultra-device-slot .dport-connection-body form>.mb-3>.row{
    display:flex!important;align-items:center!important;flex-wrap:nowrap!important;gap:8px!important;
  }
  .dport-ultra-device-slot .dport-connection-body form>.mb-3>.row>.col{
    flex:1 1 auto!important;width:auto!important;min-width:0!important;max-width:none!important;margin:0!important;padding:0!important;
  }
  .dport-ultra-device-slot #device{
    display:block!important;width:100%!important;min-width:0!important;max-width:100%!important;height:46px!important;min-height:46px!important;
    margin:0!important;padding:6px 30px 6px 12px!important;box-sizing:border-box!important;font-size:14px!important;font-weight:800!important;
    line-height:1.15!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-ultra-device-slot #refresh-device{
    flex:0 0 90px!important;width:90px!important;min-width:90px!important;max-width:90px!important;height:46px!important;min-height:46px!important;
    margin:0!important;padding:5px 4px!important;font-size:12.5px!important;line-height:1!important;white-space:nowrap!important;box-sizing:border-box!important;
  }
  .dport-ultra-device-slot #connect,
  .dport-ultra-device-slot #disconnect{
    flex:0 0 100px!important;width:100px!important;min-width:100px!important;max-width:100px!important;height:46px!important;min-height:46px!important;
    margin:0!important;padding:5px 6px!important;font-size:12.5px!important;line-height:1!important;white-space:nowrap!important;box-sizing:border-box!important;
  }

  /* Exit is aligned to the exact same 46px control height as Connect. */
  .dport-hero-actions{
    grid-column:4!important;grid-row:1!important;
    display:flex!important;align-items:center!important;justify-content:flex-end!important;align-self:center!important;
    width:82px!important;min-width:82px!important;max-width:82px!important;height:86px!important;
    margin:0!important;padding:0!important;box-sizing:border-box!important;
  }
  .dport-hero-actions #exit-btn{
    align-self:center!important;
    width:82px!important;min-width:82px!important;max-width:82px!important;height:46px!important;min-height:46px!important;
    margin:0!important;padding:5px 8px!important;font-size:12.5px!important;line-height:1!important;white-space:nowrap!important;box-sizing:border-box!important;
  }
}

@media (min-width:1400px) and (max-width:1599px){
  .dport-hero{
    grid-template-columns:240px minmax(430px,1fr) 510px 70px!important;
    column-gap:10px!important;height:88px!important;min-height:88px!important;max-height:88px!important;padding:7px 10px!important;
  }
  .dport-brand{height:72px!important;min-height:72px!important;max-height:72px!important}
  .dport-brand-icon{
    flex-basis:72px!important;width:72px!important;height:72px!important;min-width:72px!important;min-height:72px!important;
    max-width:72px!important;max-height:72px!important;
  }
  .dport-title{font-size:22px!important}
  .dport-ultra-device-slot{height:74px!important;min-height:74px!important;max-height:74px!important}
  .dport-ultra-device-slot .dport-connection-panel{height:74px!important;min-height:74px!important;max-height:74px!important}
  .dport-ultra-gpx-slot{height:74px!important;min-height:74px!important;max-height:74px!important}
  .dport-ultra-gpx-slot .dport-gpx-card{height:74px!important;min-height:74px!important;max-height:74px!important}
  .dport-ultra-gpx-slot .dport-gpx-grid{height:40px!important;min-height:40px!important;max-height:40px!important;margin-top:4px!important}
  .dport-ultra-gpx-slot .dport-gpx-item{height:40px!important;min-height:40px!important;max-height:40px!important}
  .dport-hero-actions{height:74px!important;min-height:74px!important;max-height:74px!important;width:70px!important;min-width:70px!important;max-width:70px!important}
  .dport-hero-actions #exit-btn{width:70px!important;min-width:70px!important;max-width:70px!important;height:42px!important;min-height:42px!important}
}

@media (min-width:2200px){
  .dport-hero{
    grid-template-columns:330px minmax(760px,1fr) 640px 84px!important;
    column-gap:16px!important;height:104px!important;min-height:104px!important;max-height:104px!important;padding:8px 16px!important;
  }
  .dport-brand{height:90px!important;min-height:90px!important;max-height:90px!important}
  .dport-brand-icon{
    flex-basis:88px!important;width:88px!important;height:88px!important;min-width:88px!important;min-height:88px!important;
    max-width:88px!important;max-height:88px!important;
  }
  .dport-title{font-size:29px!important}
  .dport-ultra-gpx-slot,
  .dport-ultra-gpx-slot .dport-gpx-card{height:92px!important;min-height:92px!important;max-height:92px!important}
  .dport-ultra-gpx-slot .dport-gpx-grid{height:53px!important;min-height:53px!important;max-height:53px!important}
  .dport-ultra-gpx-slot .dport-gpx-item{height:53px!important;min-height:53px!important;max-height:53px!important}
  .dport-ultra-device-slot{height:92px!important;min-height:92px!important;max-height:92px!important}
  .dport-ultra-device-slot .dport-connection-panel{height:92px!important;min-height:92px!important;max-height:92px!important}
  .dport-hero-actions{height:92px!important;min-height:92px!important;max-height:92px!important;width:84px!important;min-width:84px!important;max-width:84px!important}
  .dport-hero-actions #exit-btn{width:84px!important;min-width:84px!important;max-width:84px!important;height:48px!important;min-height:48px!important}
}

@media (max-width:1399px){
  .dport-hero{
    display:flex!important;align-items:center!important;flex-wrap:wrap!important;gap:10px!important;
    min-height:0!important;height:auto!important;max-height:none!important;overflow:visible!important;
  }
  .dport-brand{flex:1 1 100%!important;width:auto!important;min-width:0!important;max-width:100%!important}
  .dport-ultra-gpx-slot,
  .dport-ultra-device-slot{flex:1 1 100%!important;width:100%!important;min-width:0!important;max-width:100%!important}
}

/* 1100-1599px desktop: keep the approved single-row composition and readable text. */
@media (min-width:1100px) and (max-width:1599px){
  .dport-hero{
    display:grid!important;
    grid-template-columns:270px minmax(460px,1fr) 500px 74px!important;
    column-gap:10px!important;
    row-gap:0!important;
    align-items:center!important;
    justify-content:start!important;
    width:100%!important;
    min-width:0!important;
    max-width:100%!important;
    height:96px!important;
    min-height:96px!important;
    max-height:96px!important;
    padding:7px 10px!important;
    box-sizing:border-box!important;
    overflow:hidden!important;
    position:relative!important;
    z-index:3000!important;
  }
  .dport-hero-notifications{display:none!important;width:0!important;height:0!important}
  .dport-brand{
    grid-column:1!important;grid-row:1!important;
    width:100%!important;min-width:0!important;max-width:none!important;
    height:82px!important;min-height:82px!important;max-height:82px!important;
    display:flex!important;align-items:center!important;
  }
  .dport-brand-icon{
    flex:0 0 82px!important;width:82px!important;height:82px!important;
    min-width:82px!important;min-height:82px!important;max-width:82px!important;max-height:82px!important;
    border-radius:15px!important;
  }
  .dport-brand-text{
    min-width:0!important;max-width:calc(100% - 90px)!important;
    margin-left:14px!important;overflow:hidden!important;
  }
  .dport-title{
    font-size:28px!important;line-height:1.05!important;font-weight:850!important;
    white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-subtitle{
    margin-top:5px!important;font-size:12.5px!important;line-height:1.2!important;
    white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-caption,
  #dport-pm3-status{
    margin-top:3px!important;font-size:11px!important;line-height:1.15!important;
    white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important;
  }
  .dport-header-center{display:contents!important}
  .dport-standard-device-slot{display:none!important}

  .dport-ultra-gpx-slot{
    grid-column:2!important;grid-row:1!important;display:block!important;width:100%!important;min-width:0!important;max-width:none!important;
    height:76px!important;min-height:76px!important;max-height:76px!important;
    justify-self:stretch!important;align-self:center!important;
  }
  .dport-ultra-gpx-slot > *,
  .dport-ultra-gpx-slot .dport-gpx-card,
  .dport-ultra-gpx-slot .dport-gpx-head,
  .dport-ultra-gpx-slot .dport-gpx-grid{
    width:100%!important;min-width:0!important;max-width:none!important;box-sizing:border-box!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-card{
    height:76px!important;min-height:76px!important;max-height:76px!important;padding:5px 8px!important;
  }
  .dport-ultra-gpx-slot .dport-section-kicker{font-size:9.5px!important}
  .dport-ultra-gpx-slot .dport-section-title{
    font-size:18px!important;line-height:19px!important;font-weight:850!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-speed-label{font-size:8.5px!important}
  .dport-ultra-gpx-slot .dport-gpx-speed-select{
    width:108px!important;min-width:108px!important;max-width:108px!important;height:27px!important;min-height:27px!important;font-size:11.5px!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-grid{
    display:grid!important;grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:6px!important;
    height:44px!important;min-height:44px!important;max-height:44px!important;margin:4px 0 0!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-item{
    height:44px!important;min-height:44px!important;max-height:44px!important;padding:5px 7px!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-item span{font-size:10px!important;line-height:11px!important}
  .dport-ultra-gpx-slot .dport-gpx-item strong{font-size:14px!important;line-height:16px!important}

  .dport-ultra-device-slot{
    grid-column:3!important;grid-row:1!important;width:100%!important;min-width:0!important;max-width:none!important;
    height:82px!important;min-height:82px!important;max-height:82px!important;
  }
  .dport-ultra-device-slot .dport-connection-panel{
    width:100%!important;height:82px!important;min-height:82px!important;max-height:82px!important;padding:7px 8px!important;
  }
  .dport-ultra-device-slot .dport-section-kicker{font-size:8.5px!important}
  .dport-ultra-device-slot .dport-mini-title{font-size:14px!important}
  .dport-ultra-device-slot #device{height:42px!important;min-height:42px!important;font-size:13px!important}
  .dport-ultra-device-slot #refresh-device{
    width:88px!important;min-width:88px!important;max-width:88px!important;height:46px!important;min-height:46px!important;font-size:14px!important;
  }
  .dport-ultra-device-slot #connect,
  .dport-ultra-device-slot #disconnect{
    width:96px!important;min-width:96px!important;max-width:96px!important;height:46px!important;min-height:46px!important;font-size:14px!important;
  }
  .dport-hero-actions{
    grid-column:4!important;grid-row:1!important;display:flex!important;align-items:center!important;justify-content:flex-end!important;
    width:72px!important;min-width:72px!important;max-width:72px!important;height:82px!important;min-height:82px!important;max-height:82px!important;
  }
  .dport-hero-actions #exit-btn{
    width:74px!important;min-width:74px!important;max-width:74px!important;height:46px!important;min-height:46px!important;
    margin:0!important;align-self:center!important;font-size:12px!important;
  }
}

  /* Brand metadata: caption + live update result share one line. */
  .dport-brand-meta-row{
    display:flex!important;
    align-items:center!important;
    flex-wrap:nowrap!important;
    gap:8px!important;
    width:100%!important;
    min-width:0!important;
    max-width:100%!important;
    margin:0!important;
    padding:0!important;
    overflow:hidden!important;
  }
  .dport-brand-meta-row .dport-caption{
    flex:0 1 auto!important;
    min-width:0!important;
    max-width:100%!important;
    margin:0!important;
    font-size:11px!important;
    line-height:1.15!important;
    white-space:nowrap!important;
    overflow:hidden!important;
    text-overflow:ellipsis!important;
  }
  .dport-brand-meta-row #dport-pm3-status{
    flex:0 0 auto!important;
    min-width:0!important;
    max-width:46%!important;
    display:inline-block!important;
    margin:0!important;
    padding:0!important;
    font-size:11px!important;
    line-height:1.15!important;
    white-space:nowrap!important;
    overflow:hidden!important;
    text-overflow:ellipsis!important;
    vertical-align:baseline!important;
  }

  /* GPX speed control: never collapse the label or the km/h value. */
  .dport-ultra-gpx-slot .dport-gpx-speed-wrap{
    display:flex!important;
    align-items:center!important;
    justify-content:flex-end!important;
    flex:0 0 auto!important;
    min-width:max-content!important;
    gap:6px!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-speed-label{
    display:inline-block!important;
    flex:0 0 auto!important;
    width:auto!important;
    min-width:max-content!important;
    font-size:10px!important;
    line-height:1!important;
    white-space:nowrap!important;
    overflow:visible!important;
  }
  .dport-ultra-gpx-slot .dport-gpx-speed-select{
    flex:0 0 auto!important;
    width:132px!important;
    min-width:132px!important;
    max-width:132px!important;
    height:30px!important;
    min-height:30px!important;
    padding:3px 24px 3px 8px!important;
    font-size:11px!important;
    line-height:1.1!important;
    white-space:nowrap!important;
    overflow:hidden!important;
  }

</style>

<script id="dport-header-brand-version-final">
(function(){
  function findExactText(root,text){
    var nodes=root.querySelectorAll('*');
    var best=null;
    for(var i=0;i<nodes.length;i++){
      var el=nodes[i];
      if((el.textContent||'').trim()===text){
        if(!best || el.children.length<best.children.length) best=el;
      }
    }
    return best;
  }

  function arrangeBrandMeta(){
    var brand=document.querySelector('.dport-brand');
    var caption=document.querySelector('.dport-brand .dport-caption') ||
                 findExactText(brand||document,'iPhone 定位與 GPX 模擬工具');
    var status=document.querySelector('.dport-brand #dport-pm3-status') ||
                document.getElementById('dport-pm3-status');
    if(!brand || !caption || !status) return false;

    var parent=caption.parentElement;
    if(!parent) return false;

    var row=brand.querySelector('.dport-brand-meta-row');
    if(!row){
      row=document.createElement('div');
      row.className='dport-brand-meta-row';
      row.setAttribute('data-dport-final','brand-meta');

      var captionIndex=Array.prototype.indexOf.call(parent.children,caption);
      if(captionIndex<0) captionIndex=parent.children.length-1;

      parent.insertBefore(row,caption);
      row.appendChild(caption);
      row.appendChild(status);
    }else{
      if(caption.parentElement!==row) row.appendChild(caption);
      if(status.parentElement!==row) row.appendChild(status);
    }
    return true;
  }

  function fixSpeed(){
    var wrap=document.querySelector('.dport-ultra-gpx-slot .dport-gpx-speed-wrap');
    if(!wrap) return false;
    var label=wrap.querySelector('.dport-gpx-speed-label');
    var select=wrap.querySelector('.dport-gpx-speed-select');
    if(label){
      label.style.setProperty('display','inline-block','important');
      label.style.setProperty('flex','0 0 auto','important');
      label.style.setProperty('min-width','max-content','important');
      label.style.setProperty('white-space','nowrap','important');
    }
    if(select){
      select.style.setProperty('display','block','important');
      select.style.setProperty('flex','0 0 132px','important');
      select.style.setProperty('width','132px','important');
      select.style.setProperty('min-width','132px','important');
      select.style.setProperty('max-width','132px','important');
      select.style.setProperty('font-size','11px','important');
      return true;
    }
    return false;
  }

  function apply(){
    arrangeBrandMeta();
    fixSpeed();
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',apply,{once:true});
  }else{
    apply();
  }
  window.addEventListener('load',apply);
  window.addEventListener('resize',apply);
  [100,300,700,1200].forEach(function(ms){setTimeout(apply,ms);});
})();
</script>
"""

if "</body>" in html:
    html = html.replace("</body>", css + favorites_js + status_js + header_css + "\n</body>", 1)
else:
    html += css + favorites_js + status_js + header_css



# ==================== DPort USB reconnect: manual refresh only ====================
# IMPORTANT: Refresh must remain a user action. Do NOT click or schedule the
# Refresh button automatically. When the cable is reinserted, show only a
# green status hint telling the user to press Refresh.
html += r'''
<style id="dport-usb-manual-refresh-status">
/* Lower-left toast/notification panels are removed. */
.toast-container,
.toast-container.show,
body > .toast-container,
body > div.toast-container{
    display:none!important;
    visibility:hidden!important;
    pointer-events:none!important;
}

/* The single allowed notification surface is the existing green status text. */
.dport-status,
#dport-status,
.geoport-status,
#geoport-status{
    position:relative!important;
    z-index:3200!important;
}
</style>

<script id="dport-usb-manual-refresh-only">
(function(){
    function greenStatus(message){
        try{
            if(typeof geoportStatus==='function'){
                geoportStatus(String(message||''),false);
                return true;
            }
        }catch(e){}
        return false;
    }


    function deviceListHasPhone(){
        var select=document.getElementById('device');
        if(!select) return false;

        var options=Array.prototype.slice.call(select.options||[]);
        return options.some(function(option){
            var value=String(option.value||'').trim();
            var label=String(option.textContent||'').trim();

            if(!value) return false;
            if(/請選擇|選擇裝置|找不到裝置|沒有裝置|無裝置/i.test(label)) return false;

            // A real iPhone/USB device option normally contains USB / iPhone / iOS.
            // Keep this permissive so it also works with custom device labels.
            return true;
        });
    }

    function clearStaleDisconnectStatus(){
        if(!deviceListHasPhone()) return;

        var stalePhrases=[
            '裝置已中斷連接，重新插入 USB 後會自動出現在裝置清單。',
            '裝置已中斷連接'
        ];

        var nodes=document.querySelectorAll('body *');
        for(var i=0;i<nodes.length;i++){
            var el=nodes[i];
            if(!el || el.children.length>0) continue;

            var text=String(el.textContent||'').trim();
            if(!text) continue;

            var stale=false;
            for(var j=0;j<stalePhrases.length;j++){
                if(text===stalePhrases[j] || text.indexOf(stalePhrases[j])>=0){
                    stale=true;
                    break;
                }
            }

            if(!stale) continue;

            try{
                el.textContent='';
                el.setAttribute('aria-hidden','true');
                el.style.setProperty('display','none','important');
            }catch(e){}
        }
    }

    function watchDeviceEnumeration(){
        var select=document.getElementById('device');

        if(select && !select.dataset.dportStatusReconnectWatch){
            select.dataset.dportStatusReconnectWatch='1';

            var observer=new MutationObserver(function(){
                if(deviceListHasPhone()){
                    clearStaleDisconnectStatus();
                }
            });

            observer.observe(select,{childList:true,subtree:true});
        }

        if(!window.__dportReconnectStatusObserver && document.body && window.MutationObserver){
            var bodyObserver=new MutationObserver(function(){
                clearStaleDisconnectStatus();
            });

            bodyObserver.observe(document.body,{childList:true,subtree:true,characterData:true});
            window.__dportReconnectStatusObserver=bodyObserver;
        }

        clearStaleDisconnectStatus();
    }

    function enableManualRefresh(){
        var btn=document.getElementById('refresh-device');
        if(!btn) return;
        // The user controls Refresh. Never leave it disabled merely because
        // a previous USB device was disconnected.
        btn.disabled=false;
        btn.removeAttribute('aria-disabled');
    }

    function wrapUsbEvent(name,message){
        try{
            if(typeof window[name]!=='function') return;
            if(window[name].__dportManualRefreshOnly) return;

            var original=window[name];
            var wrapped=function(){
                var result=original.apply(this,arguments);

                // Give Windows/usbmux a moment to settle, but never trigger
                // Refresh automatically.
                if(name==='handleUsbCableConnected'){
                    setTimeout(function(){
                        enableManualRefresh();
                        clearStaleDisconnectReminder();
                        if(!isActuallyConnected()){
                            greenStatus(message);
                        }
                    },250);
                }else{
                    setTimeout(function(){
                        enableManualRefresh();
                    },100);
                }
                return result;
            };

            wrapped.__dportManualRefreshOnly=true;
            wrapped.__dportManualRefreshOriginal=original;
            window[name]=wrapped;
        }catch(e){}
    }


    function isActuallyConnected(){
        try{
            if(typeof isDeviceConnected!=='undefined' && isDeviceConnected===true) return true;
        }catch(e){}

        var disconnect=document.getElementById('disconnect');
        if(disconnect && disconnect.disabled===false) return true;

        var connect=document.getElementById('connect');
        if(connect && connect.dataset && connect.dataset.connected==='true') return true;

        return false;
    }

    function clearStaleDisconnectReminder(){
        if(!isActuallyConnected()) return;

        var exact='裝置已中斷連接，重新插入 USB 後會自動出現在裝置清單。';
        var nodes=document.querySelectorAll('body *');

        for(var i=0;i<nodes.length;i++){
            var el=nodes[i];
            var txt=String(el.textContent||'').trim();
            if(txt!==exact) continue;

            try{
                el.textContent='';
                el.setAttribute('aria-hidden','true');
                el.style.setProperty('display','none','important');
            }catch(e){}
        }
    }

    function watchConnectionState(){
        clearStaleDisconnectReminder();

        if(window.__dportUsbStatusObserver) return;
        if(!window.MutationObserver) return;

        var observer=new MutationObserver(function(){
            clearStaleDisconnectReminder();
        });

        observer.observe(document.body,{childList:true,subtree:true,characterData:true});
        window.__dportUsbStatusObserver=observer;
    }

    function redirectLegacyToast(){
        if(typeof window.displayToast!=='function') return;
        if(window.displayToast.__dportStatusOnlyFinal) return;

        window.displayToast=function(message){
            var msg=String(message==null?'':message).trim();
            if(!msg) return;
            greenStatus(msg);
        };
        window.displayToast.__dportStatusOnlyFinal=true;
    }

    function boot(){
        enableManualRefresh();
        redirectLegacyToast();
        watchConnectionState();
        clearStaleDisconnectReminder();

        // Only observe native USB callbacks. No polling and no automatic
        // refresh are performed here.
        wrapUsbEvent(
            'handleUsbCableConnected',
            'USB 已重新插入，請按「重新整理」偵測 iPhone'
        );
        wrapUsbEvent('handleUsbCableRemoved','USB 已拔除');

        // Keep Refresh available after startup too.
        [500,1000,2000,3000,5000].forEach(function(ms){
            setTimeout(function(){
                enableManualRefresh();
                redirectLegacyToast();
                clearStaleDisconnectReminder();
            },ms);
        });
    }

    if(document.readyState==='loading'){
        document.addEventListener('DOMContentLoaded',boot,{once:true});
    }else{
        boot();
    }

    window.addEventListener('load',function(){
        boot();
        watchConnectionState();
        clearStaleDisconnectReminder();
        [500,1200,2500].forEach(function(ms){
            setTimeout(clearStaleDisconnectReminder,ms);
        });
    });
})();
</script>
'''


# ==================== DPort unified status / device UX ====================
# One green status message only. No stacked toast panels. Dialogs/prompts are
# intentionally left alone because they require direct user interaction.
html += r'''
<style id="dport-unified-status-final">
.toast-container,
.toast-container.show,
body > .toast-container,
body > div.toast-container{
    display:none!important;
    visibility:hidden!important;
    pointer-events:none!important;
}

#geoport-status,
.geoport-status,
#dport-status,
.dport-status{
    position:relative!important;
    z-index:3200!important;
    min-height:1.2em!important;
    overflow:hidden!important;
    transition:opacity .18s ease!important;
}
</style>

<script id="dport-unified-status-final-script">
(function(){
    var hideTimer=null;
    var originalStatus=null;
    var installing=false;

    function statusElement(){
        return document.getElementById('geoport-status') ||
               document.getElementById('dport-status') ||
               document.querySelector('.geoport-status,.dport-status');
    }

    function clearStatusVisual(){
        var el=statusElement();
        if(!el) return;
        try{
            el.textContent='';
            el.style.removeProperty('display');
            el.style.removeProperty('opacity');
        }catch(e){}
    }

    function armHide(message){
        if(hideTimer) clearTimeout(hideTimer);
        var msg=String(message||'').trim();
        var delay=4500;
        if(/請按「重新整理」|USB/.test(msg)) delay=8000;
        if(/定位成功|已辨識地點/.test(msg)) delay=4000;

        hideTimer=setTimeout(function(){
            var el=statusElement();
            if(!el) return;
            try{
                el.style.setProperty('opacity','0','important');
                setTimeout(function(){
                    var current=statusElement();
                    if(current && String(current.textContent||'').trim()===msg){
                        current.textContent='';
                        current.style.removeProperty('opacity');
                    }
                },200);
            }catch(e){}
        },delay);
    }

    function install(){
        if(installing) return;
        installing=true;

        try{
            if(typeof window.geoportStatus==='function' &&
               !window.geoportStatus.__dportUnifiedStatusFinal){

                originalStatus=window.geoportStatus;

                var wrapped=function(message){
                    var args=Array.prototype.slice.call(arguments);
                    var msg=String(message==null?'':message).trim();

                    if(hideTimer) clearTimeout(hideTimer);

                    if(!msg){
                        clearStatusVisual();
                        return;
                    }

                    var result;
                    try{
                        result=originalStatus.apply(this,args);
                    }catch(e){}

                    // Always collapse the status area to one text message.
                    var el=statusElement();
                    if(el){
                        try{
                            el.textContent=msg;
                            el.style.setProperty('opacity','1','important');
                            el.style.removeProperty('display');
                        }catch(e){}
                    }

                    armHide(msg);
                    return result;
                };

                wrapped.__dportUnifiedStatusFinal=true;
                wrapped.__dportUnifiedStatusOriginal=originalStatus;
                window.geoportStatus=wrapped;
            }
        }catch(e){
            // Leave the original implementation untouched if the page is
            // still initializing.
        }

        try{
            if(typeof window.displayToast==='function' &&
               !window.displayToast.__dportStatusOnlyFinal){

                window.displayToast=function(message){
                    var msg=String(message==null?'':message).trim();
                    if(!msg) return;
                    if(typeof window.geoportStatus==='function'){
                        window.geoportStatus(msg,false);
                    }
                };

                window.displayToast.__dportStatusOnlyFinal=true;
            }
        }catch(e){}

        installing=false;
    }

    function updateDeviceTooltip(){
        var select=document.getElementById('device');
        if(!select) return false;

        var option=select.options && select.selectedIndex>=0 ?
            select.options[select.selectedIndex] : null;

        var label=option ? String(option.textContent||'').trim() : '';
        if(label && !/請選擇|選擇裝置|沒有裝置|找不到裝置|無裝置/i.test(label)){
            select.title=label;
        }else{
            select.removeAttribute('title');
        }
        return true;
    }

    function watchDeviceList(){
        var select=document.getElementById('device');
        if(!select || select.dataset.dportTooltipWatch==='1') return;

        select.dataset.dportTooltipWatch='1';
        updateDeviceTooltip();

        select.addEventListener('change',updateDeviceTooltip);

        if(window.MutationObserver){
            var observer=new MutationObserver(updateDeviceTooltip);
            observer.observe(select,{childList:true,subtree:true});
        }
    }

    function boot(){
        install();
        watchDeviceList();
        var el=statusElement();
        if(el){
            el.style.setProperty('z-index','3200','important');
        }
    }

    if(document.readyState==='loading'){
        document.addEventListener('DOMContentLoaded',boot,{once:true});
    }else{
        boot();
    }

    window.addEventListener('load',boot);
    [100,500,1200,2500,5000].forEach(function(ms){
        setTimeout(boot,ms);
    });
})();
</script>
'''


# ==================== DPort location / GPX interaction polish ====================
# 1) A reverse-geocoded place name must never change the width of the left panel.
#    Truncate visually with an ellipsis and expose the full value on hover.
# 2) GPX speed controls are UI controls, not map controls. Stop their pointer
#    events from bubbling into Leaflet so selecting a speed can never pan/zoom
#    the map to the click position.
html += r'''
<style id="dport-location-gpx-interaction-final">
/* Long place-name row: never push the sidebar wider than its grid column. */
.dport-location-name,
.geoport-location-name,
.geoport-place-name,
#geoport-place-name{
    display:block!important;
    width:100%!important;
    max-width:100%!important;
    min-width:0!important;
    box-sizing:border-box!important;
    overflow:hidden!important;
    white-space:nowrap!important;
    text-overflow:ellipsis!important;
}

.dport-location-name *,
.geoport-location-name *,
.geoport-place-name *,
#geoport-place-name *{
    max-width:100%!important;
    min-width:0!important;
    box-sizing:border-box!important;
}

.dport-location-name,
.geoport-location-name,
.geoport-place-name,
#geoport-place-name{
    flex:1 1 auto!important;
}

/* GPX speed selector gets its own interaction boundary. */
.dport-gpx-speed-wrap,
.dport-gpx-speed-select,
.dport-gpx-speed-wrap select{
    touch-action:manipulation!important;
    user-select:none!important;
}

.dport-gpx-speed-wrap{
    position:relative!important;
    z-index:4000!important;
}
</style>

<script id="dport-location-gpx-interaction-final-script">
(function(){
    function findPlaceNameElements(){
        var all=document.querySelectorAll('body *');
        var found=[];

        for(var i=0;i<all.length;i++){
            var el=all[i];
            if(!el || el.children.length>3) continue;

            var text=String(el.textContent||'').replace(/\s+/g,' ').trim();
            if(text.length<8 || text.length>220) continue;

            if(/^地點\s*[:：]/.test(text)){
                found.push(el);
            }
        }
        return found;
    }

    function constrainPlaceName(){
        var found=findPlaceNameElements();

        found.forEach(function(el){
            try{
                el.classList.add('dport-location-name');
                el.title=String(el.textContent||'').replace(/\s+/g,' ').trim();

                var parent=el.parentElement;
                for(var level=0; parent && level<4; level++,parent=parent.parentElement){
                    parent.style.setProperty('min-width','0','important');
                    parent.style.setProperty('max-width','100%','important');
                    parent.style.setProperty('box-sizing','border-box','important');
                    parent.style.setProperty('overflow','hidden','important');
                }
            }catch(e){}
        });
    }

    function protectGpxControls(){
        var wraps=document.querySelectorAll(
            '.dport-gpx-speed-wrap, .dport-gpx-speed-select, .dport-gpx-speed-wrap select'
        );

        wraps.forEach(function(el){
            if(el.dataset.dportLeafletShield==='1') return;
            el.dataset.dportLeafletShield='1';

            [
                'mousedown','mouseup','click','dblclick',
                'pointerdown','pointerup',
                'touchstart','touchend',
                'wheel','contextmenu'
            ].forEach(function(type){
                el.addEventListener(type,function(event){
                    event.stopPropagation();
                },false);
            });
        });
    }

    function apply(){
        constrainPlaceName();
        protectGpxControls();
    }

    if(document.readyState==='loading'){
        document.addEventListener('DOMContentLoaded',apply,{once:true});
    }else{
        apply();
    }

    window.addEventListener('load',apply);
    window.addEventListener('resize',apply);

    if(window.MutationObserver){
        var observer=new MutationObserver(function(){
            apply();
        });
        observer.observe(document.body,{childList:true,subtree:true});
    }

    [200,700,1500,3000].forEach(function(ms){
        setTimeout(apply,ms);
    });
})();
</script>
'''


# ==================== DPort definitive location / GPX event fix ====================
# Use the actual DOM IDs from src/templates/map.html instead of inferred
# selectors. Long place names must never change the sidebar width, and the GPX
# speed <select> must be a hard Leaflet interaction boundary.
html += r'''
<style id="dport-definitive-location-gpx-fix">
/* Actual location-name element in the current template. */
.geoport-current-place-row{
    display:flex!important;
    align-items:center!important;
    gap:6px!important;
    width:100%!important;
    min-width:0!important;
    max-width:100%!important;
    box-sizing:border-box!important;
    overflow:hidden!important;
}
.geoport-current-place-label{
    flex:0 0 auto!important;
    white-space:nowrap!important;
}
#geoport-current-place{
    display:block!important;
    flex:1 1 auto!important;
    width:auto!important;
    min-width:0!important;
    max-width:100%!important;
    overflow:hidden!important;
    white-space:nowrap!important;
    text-overflow:ellipsis!important;
    box-sizing:border-box!important;
}
.geoport-status-card{
    width:100%!important;
    min-width:0!important;
    max-width:100%!important;
    box-sizing:border-box!important;
    overflow:hidden!important;
}

/* Actual GPX speed control in the current template. */
#dport-gpx-speed-select,
.dport-gpx-speed-wrap,
.dport-gpx-speed-wrap select{
    position:relative!important;
    z-index:5000!important;
    pointer-events:auto!important;
    touch-action:manipulation!important;
    user-select:none!important;
}
#dport-gpx-speed-select{
    display:block!important;
    width:132px!important;
    min-width:132px!important;
    max-width:132px!important;
    overflow:hidden!important;
    white-space:nowrap!important;
}
</style>

<script id="dport-definitive-location-gpx-fix-script">
(function(){
    function protectSpeedSelect(){
        var select=document.getElementById('dport-gpx-speed-select');
        var wrap=document.querySelector('.dport-gpx-speed-wrap');
        var els=[];
        if(wrap) els.push(wrap);
        if(select) els.push(select);

        els.forEach(function(el){
            if(!el || el.dataset.dportLeafletHardStop==='1') return;
            el.dataset.dportLeafletHardStop='1';

            [
                'click','dblclick','mousedown','mouseup',
                'pointerdown','pointerup','touchstart','touchend',
                'contextmenu','wheel'
            ].forEach(function(type){
                el.addEventListener(type,function(ev){
                    ev.stopPropagation();
                },true);
            });

            /* Leaflet's own DOM helpers are more robust than only native
               bubbling control, especially when the map has handlers on the
               container. */
            try{
                if(window.L && L.DomEvent){
                    if(L.DomEvent.disableClickPropagation){
                        L.DomEvent.disableClickPropagation(el);
                    }
                    if(L.DomEvent.disableScrollPropagation){
                        L.DomEvent.disableScrollPropagation(el);
                    }
                }
            }catch(e){}
        });
    }

    function constrainPlace(){
        var row=document.querySelector('.geoport-current-place-row');
        var name=document.getElementById('geoport-current-place');

        if(row){
            row.style.setProperty('width','100%','important');
            row.style.setProperty('min-width','0','important');
            row.style.setProperty('max-width','100%','important');
            row.style.setProperty('overflow','hidden','important');
            row.style.setProperty('box-sizing','border-box','important');
        }

        if(name){
            name.style.setProperty('min-width','0','important');
            name.style.setProperty('max-width','100%','important');
            name.style.setProperty('overflow','hidden','important');
            name.style.setProperty('white-space','nowrap','important');
            name.style.setProperty('text-overflow','ellipsis','important');

            var parent=name.parentElement;
            if(parent){
                parent.style.setProperty('min-width','0','important');
                parent.style.setProperty('max-width','100%','important');
                parent.style.setProperty('overflow','hidden','important');
            }

            name.title=String(name.textContent||'').trim();
        }
    }

    function apply(){
        protectSpeedSelect();
        constrainPlace();
    }

    if(document.readyState==='loading'){
        document.addEventListener('DOMContentLoaded',apply,{once:true});
    }else{
        apply();
    }
    window.addEventListener('load',apply);
    window.addEventListener('resize',apply);

    if(window.MutationObserver && document.body){
        var observer=new MutationObserver(function(){
            protectSpeedSelect();
            constrainPlace();
        });
        observer.observe(document.body,{childList:true,subtree:true,characterData:true});
    }

    [50,150,400,1000,2500].forEach(function(ms){
        setTimeout(apply,ms);
    });
})();
</script>
'''


# ==================== DPort definitive map/UI interaction guard ====================
# The GPX speed selector lives in the page header, but its interaction can still
# bubble into Leaflet's map click handler in some Chromium/Bootstrap combinations.
# Guard the actual map click handler itself so UI controls can never create/move a
# map coordinate. This is intentionally source-level, not another event-bubble hack.
needle = "map.on('click', function(event){"
if needle in html:
    html = html.replace(
        needle,
        """map.on('click', function(event){
        // Header / UI controls are not map-coordinate input.
        const originalEvent = event && event.originalEvent;
        const target = originalEvent && originalEvent.target;
        if (target && target.closest && target.closest(
            '.dport-ultra-gpx-slot, .dport-gpx-speed-wrap, select, button, input, textarea, label'
        )) {
            return;
        }
""",
        1,
    )
else:
    raise SystemExit("Expected Leaflet map click handler was not found; refusing to guess.")

# Long place names must be constrained by the actual left location row.
html += r'''
<style id="dport-definitive-location-row-final">
/* Actual "地點：" row in src/templates/map.html. */
.geoport-status-card,
.geoport-current-place-row,
.geoport-current-place-label,
#geoport-current-place{
    min-width:0!important;
    max-width:100%!important;
    box-sizing:border-box!important;
}

.geoport-status-card{
    width:100%!important;
    overflow:hidden!important;
}

.geoport-current-place-row{
    width:100%!important;
    display:flex!important;
    flex:1 1 100%!important;
    align-items:center!important;
    gap:6px!important;
    overflow:hidden!important;
}

.geoport-current-place-label{
    flex:0 0 auto!important;
    white-space:nowrap!important;
}

#geoport-current-place{
    flex:1 1 0%!important;
    width:0!important;
    max-width:none!important;
    overflow:hidden!important;
    white-space:nowrap!important;
    text-overflow:ellipsis!important;
    display:block!important;
    cursor:help!important;
}

#geoport-current-place[title]:hover{
    text-decoration:underline dotted!important;
    text-underline-offset:2px!important;
}
</style>

<script id="dport-long-place-title-final">
(function(){
    function syncPlaceTitle(){
        var el=document.getElementById('geoport-current-place');
        if(!el) return;
        var text=String(el.textContent||'').replace(/\s+/g,' ').trim();
        if(text && text!=='尚未辨識地點'){
            el.title=text;
        }else{
            el.removeAttribute('title');
        }
    }
    if(document.readyState==='loading'){
        document.addEventListener('DOMContentLoaded',syncPlaceTitle,{once:true});
    }else{
        syncPlaceTitle();
    }
    window.addEventListener('load',syncPlaceTitle);
    if(window.MutationObserver){
        var obs=new MutationObserver(syncPlaceTitle);
        obs.observe(document.body,{subtree:true,childList:true,characterData:true});
    }
})();
</script>
'''
path.write_text(html, encoding="utf-8")

print("DPort final header rebuilt from one authoritative layout.")
print("Order: Brand -> GPX -> Device -> Refresh -> Connect -> Exit.")
print("Header notification removed; left green status area remains the reminder location.")
print("Typography and spacing tuned for clarity against the visual reference.")
