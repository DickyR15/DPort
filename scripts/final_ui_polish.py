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
    r'\s*<script id="dport-map-status-overlay-script">
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
                if(r.width>=150 && r.height>=28 && r.width<=700 && r.height<=260){
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

    function findMapFrame(){
        var map=document.querySelector('.leaflet-container, #map, .map-container');
        if(!map) return null;

        var rect=map.getBoundingClientRect();
        if(rect.width<250 || rect.height<180) return null;
        return map;
    }

    function mountTopRight(){
        if(document.getElementById('dport-map-status-overlay')) return true;

        var map=findMapFrame();
        var source=findStatusCard();
        if(!map || !source) return false;

        var holder=document.createElement('div');
        holder.id='dport-map-status-overlay';
        map.appendChild(holder);
        holder.appendChild(source);
        return true;
    }

    function ensure(){
        if(mountTopRight()) return;
        [200,500,1000,1800,3000].forEach(function(ms){
            setTimeout(mountTopRight,ms);
        });
    }

    if(document.readyState==='loading'){
        document.addEventListener('DOMContentLoaded',ensure,{once:true});
    }else{
        ensure();
    }
    window.addEventListener('load',ensure);
})();
</script>\s*',
):
    html = re.sub(pattern, "\n", html, flags=re.S)

block = r'''
<style id="dport-final-ui-polish-v7">
:root{
    --dport-panel:#2a3240;
    --dport-panel-hover:#313b4d;
    --dport-border:#5a6983;
    --dport-border-hover:#8193bb;
    --dport-text:#f5f7fb;
    --dport-muted:#aeb8ca;
    --dport-blue:#5669e7;
    --dport-blue-hover:#697bf4;
    --dport-danger-bg:rgba(67,78,98,.66);
    --dport-danger-bg-hover:rgba(87,101,126,.82);
    --dport-danger-border:rgba(127,143,171,.72);
    --dport-danger-text:#edf2fa;
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
    color:#ffffff !important;
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

/* Destructive actions: dark blue-gray translucent, matching DPort. */
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
    color:#ffffff !important;
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

/* Favorite delete: generous click target, compact visual chip, always inside card. */
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
    padding:8px 30px 10px 13px !important;
    z-index:1 !important;
}
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete{
    position:absolute !important;
    bottom:2px !important;
    right:2px !important;
    top:auto !important;
    left:auto !important;
    width:34px !important;
    min-width:34px !important;
    max-width:34px !important;
    height:34px !important;
    min-height:34px !important;
    max-height:34px !important;
    margin:0 !important;
    padding:0 !important;
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
    cursor:pointer !important;
}
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete::before{
    content:'' !important;
    position:absolute !important;
    bottom:7px !important;
    right:7px !important;
    top:auto !important;
    left:auto !important;
    width:18px !important;
    height:18px !important;
    box-sizing:border-box !important;
    border-radius:5px !important;
    background:rgba(67,78,98,.68) !important;
    border:1px solid rgba(127,143,171,.72) !important;
    box-shadow:0 2px 6px rgba(0,0,0,.15) !important;
}
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete::after{
    content:'×' !important;
    position:absolute !important;
    top:7px !important;
    right:7px !important;
    width:18px !important;
    height:18px !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    color:#edf2fa !important;
    font-size:12px !important;
    line-height:18px !important;
    font-weight:800 !important;
}
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete:hover::before{
    background:rgba(87,101,126,.84) !important;
    border-color:#8fa1c1 !important;
}
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete:hover::after{
    color:#ffffff !important;
}
.geoport-fav-clear-all{
    min-width:56px !important;
    min-height:38px !important;
    height:38px !important;
    padding:5px 13px !important;
    border-radius:9px !important;
}

/* ---------------- DPort status notification: top-right inside map ---------------- */
#dport-map-status-overlay{
    position:absolute !important;
    top:8px !important;
    right:8px !important;
    left:auto !important;
    bottom:auto !important;
    transform:none !important;
    z-index:900 !important;
    width:min(300px,32%) !important;
    max-width:calc(100% - 16px) !important;
    min-width:0 !important;
    margin:0 !important;
    padding:0 !important;
    box-sizing:border-box !important;
    pointer-events:none !important;
    overflow:hidden !important;
}
#dport-map-status-overlay > *{
    width:100% !important;
    max-width:100% !important;
    min-width:0 !important;
    box-sizing:border-box !important;
    padding:7px 10px !important;
    background:rgba(31,38,50,.92) !important;
    border:1px solid rgba(92,108,137,.84) !important;
    border-radius:9px !important;
    color:#f5f7fb !important;
    box-shadow:0 6px 18px rgba(0,0,0,.22) !important;
    backdrop-filter:blur(7px) !important;
    overflow:hidden !important;
    font-size:13px !important;
    line-height:1.3 !important;
}
#dport-map-status-overlay > * *{
    max-width:100% !important;
    font-size:13px !important;
    line-height:1.3 !important;
    overflow:hidden !important;
    text-overflow:ellipsis !important;
}
@media (max-width:1100px){
    #dport-map-status-overlay{width:min(270px,38%) !important;}
    #dport-map-status-overlay > *,
    #dport-map-status-overlay > * *{
        font-size:12px !important;
    }
}
@media (max-width:700px){
    #dport-map-status-overlay{
        top:6px !important;
        right:6px !important;
        width:min(240px,52%) !important;
        max-width:calc(100% - 12px) !important;
    }
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
