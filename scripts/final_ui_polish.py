from pathlib import Path
import re

path = Path("src/templates/map.html")
if not path.exists():
    raise SystemExit(f"UI template not found: {path}")

html = path.read_text(encoding="utf-8")

# Remove previously injected final-polish layers. Keep feature logic from
# fix_device_refresh.py untouched; this file is styling/placement only.
for pattern in (
    r'\s*<style id="dport-final-ui-polish-v[0-9]+">.*?</style>\s*',
    r'\s*<script id="dport-final-favorites-render-v[0-9]+">.*?</script>\s*',
    r'\s*<script id="dport-map-status-overlay-script">.*?</script>\s*',
):
    html = re.sub(pattern, "\n", html, flags=re.S)

block = r'''
<style id="dport-final-ui-polish-v5">
:root{
    --dport-panel:#2a3240;
    --dport-panel-hover:#313b4d;
    --dport-border:#5a6983;
    --dport-border-hover:#8193bb;
    --dport-text:#f5f7fb;
    --dport-muted:#aeb8ca;
    --dport-blue:#5669e7;
    --dport-blue-hover:#697bf4;
    --dport-danger-bg:rgba(151,70,70,.42);
    --dport-danger-bg-hover:rgba(171,80,80,.56);
    --dport-danger-border:rgba(225,158,158,.66);
    --dport-danger-text:#ffeaea;
}

/* One consistent DPort interaction language for application buttons.
   Leaflet's own map controls are intentionally excluded. */
body button:not(.leaflet-control-button):not(.leaflet-bar a):not(.leaflet-control-zoom a){
    box-sizing:border-box !important;
    font-family:inherit !important;
    font-weight:700 !important;
    border-radius:10px !important;
    transition:
        background .16s ease,
        border-color .16s ease,
        color .16s ease,
        box-shadow .16s ease,
        transform .16s ease,
        opacity .16s ease !important;
}
body button:not(.leaflet-control-button):not(.leaflet-bar a):not(.leaflet-control-zoom a):hover{
    transform:translateY(-1px);
}
body button:not(.leaflet-control-button):not(.leaflet-bar a):not(.leaflet-control-zoom a):active{
    transform:translateY(0);
}
body button:disabled{
    opacity:.48 !important;
    cursor:not-allowed !important;
    transform:none !important;
    box-shadow:none !important;
}

/* DPort primary workflow buttons. */
#search,#connect,#disconnect,#set-location,#stop-location,
#geoport-apply-coordinates,#geoport-recenter,#dport-current-position,
#dport-map-follow,#dport-locate,#dport-stop-location{
    background:var(--dport-blue) !important;
    border:1px solid #8f9cff !important;
    color:#fff !important;
    box-shadow:0 4px 12px rgba(36,51,132,.24) !important;
}
#search:hover,#connect:hover,#disconnect:hover,#set-location:hover,#stop-location:hover,
#geoport-apply-coordinates:hover,#geoport-recenter:hover,#dport-current-position:hover,
#dport-map-follow:hover,#dport-locate:hover,#dport-stop-location:hover{
    background:var(--dport-blue-hover) !important;
    border-color:#a9b4ff !important;
    box-shadow:0 8px 18px rgba(36,51,132,.30) !important;
}

/* DPort neutral utility buttons, including 複製座標. */
#geoport-copy-coordinates,#geoport-load-last{
    background:var(--dport-panel) !important;
    border:1px solid var(--dport-border) !important;
    color:var(--dport-text) !important;
    box-shadow:0 2px 8px rgba(0,0,0,.10) !important;
}
#geoport-copy-coordinates:hover,#geoport-load-last:hover{
    background:var(--dport-panel-hover) !important;
    border-color:var(--dport-border-hover) !important;
}

/* Destructive actions: consistent translucent red. */
#geoport-clear-coordinates,.geoport-recent-delete-selected,
.geoport-recent-clear,.geoport-fav-clear-all{
    background:var(--dport-danger-bg) !important;
    border:1px solid var(--dport-danger-border) !important;
    color:var(--dport-danger-text) !important;
    box-shadow:none !important;
}
#geoport-clear-coordinates:hover,.geoport-recent-delete-selected:hover,
.geoport-recent-clear:hover,.geoport-fav-clear-all:hover{
    background:var(--dport-danger-bg-hover) !important;
    border-color:#efb2b2 !important;
    color:#fff !important;
    box-shadow:0 6px 15px rgba(0,0,0,.18) !important;
}

/* ---------------- Favorites ---------------- */
.geoport-favorites-title{
    display:flex !important;
    align-items:center !important;
    justify-content:space-between !important;
    gap:10px !important;
    margin:14px 0 8px !important;
}
.geoport-favorites-actions{
    display:flex !important;
    align-items:center !important;
}
.geoport-fav-count{
    color:var(--dport-muted) !important;
    font-size:13px !important;
    font-weight:700 !important;
}

/* Six visible Favorite cards: 2 columns x 3 rows. */
.geoport-fav-list{
    display:grid !important;
    grid-template-columns:repeat(2,minmax(0,1fr)) !important;
    grid-template-rows:repeat(3,68px) !important;
    grid-auto-rows:68px !important;
    gap:8px !important;
    padding:9px !important;
    margin:0 !important;
    height:236px !important;
    max-height:236px !important;
    overflow-y:auto !important;
    overflow-x:hidden !important;
    border:1px solid #46536b !important;
    border-radius:14px !important;
    background:rgba(29,35,47,.74) !important;
    scrollbar-width:thin !important;
    scrollbar-color:#68758d transparent !important;
}
.geoport-fav-list::-webkit-scrollbar{width:7px}
.geoport-fav-list::-webkit-scrollbar-track{background:transparent}
.geoport-fav-list::-webkit-scrollbar-thumb{
    background:#68758d;
    border-radius:999px;
}

.geoport-fav-card{
    position:relative !important;
    width:100% !important;
    height:68px !important;
    min-width:0 !important;
    min-height:68px !important;
    overflow:hidden !important;
    border-radius:11px !important;
}
.geoport-fav-open{
    position:absolute !important;
    inset:0 !important;
    width:100% !important;
    height:100% !important;
    min-height:0 !important;
    box-sizing:border-box !important;
    display:flex !important;
    align-items:center !important;
    justify-content:flex-start !important;
    text-align:left !important;
    padding:8px 26px 8px 13px !important;
    border:1px solid #5d6c88 !important;
    border-radius:11px !important;
    background:var(--dport-panel) !important;
    color:var(--dport-text) !important;
    overflow:hidden !important;
    z-index:1 !important;
    box-shadow:0 2px 8px rgba(0,0,0,.10) !important;
}
.geoport-fav-open:hover{
    background:var(--dport-panel-hover) !important;
    border-color:var(--dport-border-hover) !important;
    box-shadow:0 7px 16px rgba(0,0,0,.20) !important;
}
.geoport-fav-name{
    display:-webkit-box !important;
    width:100% !important;
    margin:0 !important;
    padding:0 !important;
    color:#f7f9fc !important;
    font-size:15px !important;
    font-weight:700 !important;
    line-height:1.16 !important;
    white-space:normal !important;
    overflow:hidden !important;
    text-overflow:clip !important;
    -webkit-box-orient:vertical !important;
    -webkit-line-clamp:2 !important;
    overflow-wrap:anywhere !important;
}
.geoport-fav-name.long{font-size:14px !important}
.geoport-fav-name.xlong{font-size:12.5px !important;line-height:1.08 !important}
.geoport-fav-detail{display:none !important}

/* The button remains 32x32 for easy clicking, while its visual chip is only
   18x18. The hit area is positioned inside the card's top-right corner. */
.geoport-fav-delete{
    position:absolute !important;
    top:2px !important;
    right:2px !important;
    width:32px !important;
    min-width:32px !important;
    max-width:32px !important;
    height:32px !important;
    min-height:32px !important;
    max-height:32px !important;
    padding:0 !important;
    margin:0 !important;
    border:0 !important;
    border-radius:8px !important;
    background:transparent !important;
    color:transparent !important;
    font-size:0 !important;
    line-height:0 !important;
    box-shadow:none !important;
    overflow:visible !important;
    transform:none !important;
    z-index:20 !important;
}
.geoport-fav-delete::before{
    content:'' !important;
    position:absolute !important;
    top:7px !important;
    right:7px !important;
    width:18px !important;
    height:18px !important;
    box-sizing:border-box !important;
    border-radius:5px !important;
    background:rgba(151,70,70,.42) !important;
    border:1px solid rgba(225,158,158,.60) !important;
}
.geoport-fav-delete::after{
    content:'×' !important;
    position:absolute !important;
    top:7px !important;
    right:7px !important;
    width:18px !important;
    height:18px !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    color:#ffeaea !important;
    font-size:12px !important;
    line-height:18px !important;
    font-weight:800 !important;
}
.geoport-fav-delete:hover::before{
    background:rgba(171,80,80,.58) !important;
    border-color:rgba(239,177,177,.80) !important;
}
.geoport-fav-delete:hover::after{color:#fff !important}

.geoport-fav-clear-all{
    min-width:56px !important;
    min-height:38px !important;
    height:38px !important;
    padding:5px 13px !important;
    border-radius:9px !important;
}

/* ---------------- Map-center DPort notifications ---------------- */
#dport-map-status-overlay{
    position:absolute !important;
    left:50% !important;
    top:50% !important;
    transform:translate(-50%,-50%) !important;
    z-index:900 !important;
    width:min(430px,72%) !important;
    max-width:430px !important;
    margin:0 !important;
    padding:0 !important;
    box-sizing:border-box !important;
    pointer-events:none !important;
}
#dport-map-status-overlay > *{
    width:100% !important;
    box-sizing:border-box !important;
    background:rgba(31,38,50,.90) !important;
    border:1px solid rgba(112,130,168,.80) !important;
    border-radius:12px !important;
    color:#f5f7fb !important;
    box-shadow:0 10px 28px rgba(0,0,0,.28) !important;
    backdrop-filter:blur(7px) !important;
}
@media (max-width:900px){
    #dport-map-status-overlay{width:min(360px,78%) !important;}
    .geoport-fav-list{
        grid-template-rows:repeat(3,64px) !important;
        grid-auto-rows:64px !important;
        height:224px !important;
        max-height:224px !important;
    }
    .geoport-fav-card,.geoport-fav-open{
        height:64px !important;
        min-height:64px !important;
    }
    .geoport-fav-name{font-size:14px !important}
    .geoport-fav-name.long{font-size:13px !important}
    .geoport-fav-name.xlong{font-size:12px !important}
}
</style>

<script id="dport-map-status-overlay-script">
(function(){
    function findStatusCard(){
        var found=[];
        document.querySelectorAll('body *').forEach(function(el){
            if(!el || el.id==='dport-map-status-overlay') return;
            var t=(el.innerText||'').replace(/\s+/g,' ').trim();
            if(
                t.indexOf('準備就緒')>=0 &&
                (t.indexOf('USB')>=0 || t.indexOf('裝置')>=0)
            ){
                var r=el.getBoundingClientRect();
                if(r.width>=180 && r.height>=40 && r.width<=700 && r.height<=260){
                    found.push(el);
                }
            }
        });
        found.sort(function(a,b){
            var ra=a.getBoundingClientRect();
            var rb=b.getBoundingClientRect();
            return (ra.width*ra.height)-(rb.width*rb.height);
        });
        return found[0] || null;
    }

    function mount(){
        if(document.getElementById('dport-map-status-overlay')) return true;

        var map=document.querySelector('.leaflet-container, #map, .map-container');
        var source=findStatusCard();
        if(!map || !source) return false;

        var holder=document.createElement('div');
        holder.id='dport-map-status-overlay';
        map.appendChild(holder);
        holder.appendChild(source);
        return true;
    }

    function ensure(){
        if(mount()) return;
        [200,500,1000,1800,3000].forEach(function(ms){
            setTimeout(mount,ms);
        });
    }

    if(document.readyState==='loading'){
        document.addEventListener('DOMContentLoaded',ensure,{once:true});
    }else{
        ensure();
    }
    window.addEventListener('load',ensure);
})();
</script>
'''

if "</body>" in html:
    html = html.replace("</body>", block + "\n</body>", 1)
else:
    html += block

path.write_text(html, encoding="utf-8")
print("DPort final UI polish v5 applied successfully.")
print("Application buttons unified without altering button behavior.")
print("Favorite delete: 32px click target with 18px translucent-red visual chip.")
print("Favorites: 2 columns x 3 visible rows, names only.")
print("Status notification moved to map center when the existing card is available.")
