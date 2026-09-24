from pathlib import Path
import re

path = Path("src/templates/map.html")
if not path.exists():
    raise SystemExit(f"UI template not found: {path}")

html = path.read_text(encoding="utf-8")

# Remove any previous version of this final polish so the build is idempotent.
html = re.sub(
    r'\s*<style id="dport-final-ui-polish-v2">.*?</style>\s*',
    '\n',
    html,
    flags=re.S,
)
html = re.sub(
    r'\s*<script id="dport-final-favorites-render-v2">.*?
    
    // Move the actual existing DPort status/notification card into the map
    // center. We move the original element (not a clone) so its existing
    // update logic continues to work.
    function mountStatusOverlay(){
        if(document.getElementById('dport-map-status-overlay')) return true;
        var map=document.querySelector('.leaflet-container, #map, .map-container');
        if(!map) return false;

        var candidates=Array.from(document.querySelectorAll('body *')).filter(function(el){
            if(!el || el.id==='dport-map-status-overlay') return false;
            var t=(el.innerText||'').replace(/\s+/g,' ').trim();
            return t.indexOf('準備就緒')>=0 && t.indexOf('DPort')>=0;
        });

        // Prefer the smallest element that contains the status text.
        candidates.sort(function(a,b){
            return (a.getBoundingClientRect().width*a.getBoundingClientRect().height)
                 - (b.getBoundingClientRect().width*b.getBoundingClientRect().height);
        });

        var source=candidates[0];
        if(!source) return false;

        var overlay=document.createElement('div');
        overlay.id='dport-map-status-overlay';
        source.parentNode.insertBefore(overlay,source);
        overlay.appendChild(source);
        return true;
    }

    function ensureStatusOverlay(){
        if(mountStatusOverlay()) return;
        setTimeout(mountStatusOverlay,250);
        setTimeout(mountStatusOverlay,800);
        setTimeout(mountStatusOverlay,1600);
    }
    document.addEventListener('DOMContentLoaded',ensureStatusOverlay,{once:true});
    window.addEventListener('load',ensureStatusOverlay);
    setTimeout(ensureStatusOverlay,1200);
</script>\s*',
    '\n',
    html,
    flags=re.S,
)

block = r'''
<style id="dport-favorite-x-final-position">
/* Highest-specificity override: the delete chip is anchored INSIDE each
   favorite card, in its upper-right corner. */
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete{
    position:absolute !important;
    inset:auto 6px auto auto !important;
    top:6px !important;
    right:6px !important;
    bottom:auto !important;
    left:auto !important;
    width:10px !important;
    min-width:10px !important;
    max-width:10px !important;
    height:10px !important;
    min-height:10px !important;
    max-height:10px !important;
    padding:0 !important;
    margin:0 !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    box-sizing:border-box !important;
    border:1px solid rgba(226,157,157,.62) !important;
    border-radius:3px !important;
    background:rgba(154,68,68,.38) !important;
    color:#ffe9e9 !important;
    font-size:0 !important;
    line-height:0 !important;
    overflow:hidden !important;
    z-index:50 !important;
    transform:none !important;
    opacity:.9 !important;
    box-shadow:none !important;
}
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete::after{
    content:'×' !important;
    display:block !important;
    font-size:8px !important;
    line-height:8px !important;
    font-weight:800 !important;
    color:#ffe9e9 !important;
}
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete:hover{
    background:rgba(174,78,78,.56) !important;
    border-color:rgba(239,178,178,.82) !important;
    color:#ffffff !important;
    transform:scale(1.08) !important;
    opacity:1 !important;
}
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete:hover::after{
    color:#ffffff !important;
}

/* The favorite title/clear button remains compact and uses the same visual
   family as the other destructive controls. */
html body .geoport-fav-clear-all{
    background:rgba(154,68,68,.42) !important;
    border:1px solid rgba(226,157,157,.70) !important;
    color:#ffe9e9 !important;
}
html body .geoport-fav-clear-all:hover{
    background:rgba(174,78,78,.58) !important;
    border-color:rgba(239,178,178,.82) !important;
    color:#ffffff !important;
}
</style>

<style id="dport-final-ui-polish-v3">
:root{
    --dport-bg:#1f2632;
    --dport-panel:#252d3a;
    --dport-panel-2:#2b3443;
    --dport-border:#53617a;
    --dport-border-hover:#7185ad;
    --dport-text:#f5f7fb;
    --dport-muted:#aeb7c8;
    --dport-primary:#5568e6;
    --dport-primary-hover:#6578f1;
    --dport-primary-active:#495bd0;
    --dport-danger:rgba(154,68,68,.42);
    --dport-danger-hover:rgba(174,78,78,.58);
    --dport-danger-border:rgba(226,157,157,.70);
}

/* =========================================================
   DPort unified button system
   Only targets DPort application controls, not Leaflet map widgets.
   ========================================================= */

.dport-control-card button:not(.leaflet-control-button),
.dport-map-header-actions button,
.dport-page-shell .btn:not(.leaflet-control-button){
    appearance:none !important;
    -webkit-appearance:none !important;
    box-sizing:border-box !important;
    border-radius:10px !important;
    border:1px solid var(--dport-border) !important;
    background:var(--dport-panel) !important;
    color:var(--dport-text) !important;
    font-family:inherit !important;
    font-weight:700 !important;
    letter-spacing:.1px !important;
    box-shadow:0 2px 8px rgba(0,0,0,.10) !important;
    transition:
        background .15s ease,
        border-color .15s ease,
        color .15s ease,
        transform .15s ease,
        box-shadow .15s ease,
        filter .15s ease !important;
}

.dport-control-card button:not(.leaflet-control-button):hover,
.dport-map-header-actions button:hover,
.dport-page-shell .btn:not(.leaflet-control-button):hover{
    background:var(--dport-panel-2) !important;
    border-color:var(--dport-border-hover) !important;
    transform:translateY(-1px) !important;
    box-shadow:0 7px 16px rgba(0,0,0,.20) !important;
}

.dport-control-card button:not(.leaflet-control-button):active,
.dport-map-header-actions button:active,
.dport-page-shell .btn:not(.leaflet-control-button):active{
    transform:translateY(0) !important;
    box-shadow:0 3px 8px rgba(0,0,0,.14) !important;
}

.dport-control-card button:not(.leaflet-control-button):focus-visible,
.dport-map-header-actions button:focus-visible,
.dport-page-shell .btn:not(.leaflet-control-button):focus-visible{
    outline:2px solid rgba(113,131,255,.60) !important;
    outline-offset:2px !important;
}

/* Primary actions: the DPort blue used for the main workflow. */
#search,
#connect,
#disconnect,
#set-location,
#stop-location,
#geoport-apply-coordinates,
#geoport-recenter,
#dport-current-position,
#dport-map-follow{
    background:var(--dport-primary) !important;
    border-color:#8c9aff !important;
    color:#ffffff !important;
    box-shadow:0 4px 12px rgba(42,57,138,.28) !important;
}

#search:hover,
#connect:hover,
#disconnect:hover,
#set-location:hover,
#stop-location:hover,
#geoport-apply-coordinates:hover,
#geoport-recenter:hover,
#dport-current-position:hover,
#dport-map-follow:hover{
    background:var(--dport-primary-hover) !important;
    border-color:#a2adff !important;
    color:#ffffff !important;
    box-shadow:0 8px 18px rgba(42,57,138,.34) !important;
}

#search:active,
#connect:active,
#disconnect:active,
#set-location:active,
#stop-location:active,
#geoport-apply-coordinates:active,
#geoport-recenter:active,
#dport-current-position:active,
#dport-map-follow:active{
    background:var(--dport-primary-active) !important;
}

/* Secondary utility actions: dark blue-gray, not flat Bootstrap gray. */
#geoport-copy-coordinates,
#geoport-load-last,
#geoport-clear-coordinates,
.geoport-recent-delete-selected,
.geoport-recent-clear,
.geoport-fav-clear-all{
    min-height:42px !important;
    background:#2a3240 !important;
    border-color:#626f88 !important;
    color:#edf1f8 !important;
}

/* Destructive actions keep the same button geometry but use one subtle
   translucent red family so the visual language stays consistent. */
#geoport-clear-coordinates,
.geoport-recent-delete-selected,
.geoport-recent-clear,
.geoport-fav-clear-all{
    background:var(--dport-danger) !important;
    border-color:var(--dport-danger-border) !important;
    color:#ffe9e9 !important;
}
#geoport-clear-coordinates:hover,
.geoport-recent-delete-selected:hover,
.geoport-recent-clear:hover,
.geoport-fav-clear-all:hover{
    background:var(--dport-danger-hover) !important;
    border-color:#efb2b2 !important;
    color:#ffffff !important;
}

/* "複製座標" is the neutral reference button requested by the user. */
#geoport-copy-coordinates{
    background:#2a3240 !important;
    border-color:#6a7891 !important;
    color:#f4f7fb !important;
}

/* Favorite section */
.geoport-favorites-title{
    display:flex !important;
    align-items:center !important;
    justify-content:space-between !important;
    gap:10px !important;
    margin-top:14px !important;
    margin-bottom:8px !important;
}
.geoport-favorites-title > span:first-child{
    display:flex !important;
    align-items:baseline !important;
    gap:7px !important;
}
.geoport-fav-count{
    color:var(--dport-muted) !important;
    font-size:13px !important;
    font-weight:700 !important;
}
.geoport-favorites-actions{
    display:flex !important;
    align-items:center !important;
}

/* Six visible cards: 2 × 3. */
.geoport-fav-list{
    display:grid !important;
    grid-template-columns:repeat(2,minmax(0,1fr)) !important;
    grid-template-rows:repeat(3,70px) !important;
    grid-auto-rows:70px !important;
    gap:8px !important;
    padding:9px !important;
    margin:0 !important;
    max-height:242px !important;
    overflow-y:auto !important;
    overflow-x:hidden !important;
    border:1px solid #46536b !important;
    border-radius:14px !important;
    background:rgba(29,35,47,.78) !important;
    box-shadow:inset 0 1px 0 rgba(255,255,255,.025) !important;
    scrollbar-width:thin !important;
    scrollbar-color:#68758d transparent !important;
}
.geoport-fav-list::-webkit-scrollbar{width:7px}
.geoport-fav-list::-webkit-scrollbar-track{background:transparent}
.geoport-fav-list::-webkit-scrollbar-thumb{
    background:#69758d;
    border-radius:999px;
}
.geoport-fav-card{
    position:relative !important;
    min-width:0 !important;
    min-height:70px !important;
}
.geoport-fav-open{
    position:relative !important;
    width:100% !important;
    height:70px !important;
    min-height:70px !important;
    box-sizing:border-box !important;
    display:flex !important;
    align-items:center !important;
    justify-content:flex-start !important;
    text-align:left !important;
    padding:8px 24px 8px 13px !important;
    border:1px solid #5b6a86 !important;
    border-radius:11px !important;
    background:#2a3240 !important;
    color:#f7f9fc !important;
    overflow:hidden !important;
}
.geoport-fav-open:hover{
    background:#30394a !important;
    border-color:#8295bd !important;
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

/* Tiny red delete chip in the top-right corner. */
.geoport-fav-delete{
    position:absolute !important;
    top:5px !important;
    right:6px !important;
    width:16px !important;
    min-width:16px !important;
    max-width:16px !important;
    height:16px !important;
    min-height:16px !important;
    max-height:16px !important;
    padding:0 !important;
    margin:0 !important;
    display:grid !important;
    place-items:center !important;
    box-sizing:border-box !important;
    border-radius:4px !important;
    background:rgba(154,68,68,.38) !important;
    border:1px solid rgba(226,157,157,.58) !important;
    color:#ffe9e9 !important;
    font-size:8px !important;
    line-height:12px !important;
    font-weight:800 !important;
    box-shadow:none !important;
    opacity:.90 !important;
    z-index:10 !important;
    transition:background .14s ease,border-color .14s ease,transform .14s ease,opacity .14s ease !important;
}
.geoport-fav-delete:hover{
    background:rgba(174,78,78,.56) !important;
    border-color:rgba(239,178,178,.80) !important;
    color:#ffffff !important;
    transform:scale(1.08) !important;
    opacity:1 !important;
}

/* Favorite clear-all uses the same DPort destructive family. */
.geoport-fav-clear-all{
    min-width:56px !important;
    min-height:38px !important;
    height:38px !important;
    padding:5px 13px !important;
    border-radius:9px !important;
    font-size:14px !important;
}

/* Disabled buttons stay visually coherent rather than becoming pure gray. */
.dport-control-card button:disabled,
.dport-page-shell button:disabled{
    opacity:.48 !important;
    transform:none !important;
    box-shadow:none !important;
    cursor:not-allowed !important;
}

/* Keep compact controls compact on narrow layouts. */
@media (max-width:900px){
    .dport-control-card button:not(.leaflet-control-button),
    .dport-page-shell .btn:not(.leaflet-control-button){
        min-height:42px !important;
    }
    .geoport-fav-list{
        grid-template-rows:repeat(3,64px) !important;
        grid-auto-rows:64px !important;
        max-height:224px !important;
    }
    .geoport-fav-card,
    .geoport-fav-open{
        height:64px !important;
        min-height:64px !important;
    }
    .geoport-fav-name{font-size:14px !important}
    .geoport-fav-name.long{font-size:13px !important}
    .geoport-fav-name.xlong{font-size:12px !important}
}

/* =========================================================
   Map-center status notification
   Move the existing DPort status card to the center of the map so
   important messages remain visible on wide/short screens.
   ========================================================= */
#dport-map-status-overlay{
    position:absolute !important;
    left:50% !important;
    top:50% !important;
    transform:translate(-50%,-50%) !important;
    z-index:900 !important;
    width:min(420px,72%) !important;
    max-width:420px !important;
    pointer-events:none !important;
    margin:0 !important;
    padding:0 !important;
    box-sizing:border-box !important;
    display:block !important;
}
#dport-map-status-overlay > *{
    width:100% !important;
    box-sizing:border-box !important;
}
#dport-map-status-overlay .dport-status-card,
#dport-map-status-overlay .dport-status{
    background:rgba(31,38,50,.90) !important;
    border:1px solid rgba(111,130,170,.78) !important;
    border-radius:12px !important;
    color:var(--dport-text) !important;
    box-shadow:0 10px 26px rgba(0,0,0,.28) !important;
    backdrop-filter:blur(8px) !important;
}
#dport-map-status-overlay .dport-status-title,
#dport-map-status-overlay strong,
#dport-map-status-overlay b{
    color:#cbd4e4 !important;
}
#dport-map-status-overlay .dport-status-message,
#dport-map-status-overlay p,
#dport-map-status-overlay small{
    color:#f3f6fb !important;
}
@media (max-width:900px){
    #dport-map-status-overlay{
        width:min(360px,78%) !important;
    }
}

/* =========================================================
   Favorite delete: larger click target, smaller visual chip.
   The red chip is only ~18x18; the button itself is 32x32 for easy clicking.
   ========================================================= */
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete{
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
    background:transparent !important;
    color:transparent !important;
    font-size:0 !important;
    line-height:0 !important;
    border-radius:8px !important;
    box-shadow:none !important;
    opacity:1 !important;
    overflow:visible !important;
    z-index:20 !important;
    transform:none !important;
}
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete::before{
    content:'' !important;
    position:absolute !important;
    width:18px !important;
    height:18px !important;
    top:7px !important;
    right:7px !important;
    border-radius:5px !important;
    background:rgba(154,68,68,.50) !important;
    border:1px solid rgba(226,157,157,.62) !important;
    box-sizing:border-box !important;
    box-shadow:none !important;
}
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete::after{
    content:'×' !important;
    position:absolute !important;
    width:18px !important;
    height:18px !important;
    top:7px !important;
    right:7px !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
    color:#ffe9e9 !important;
    font-size:12px !important;
    line-height:18px !important;
    font-weight:800 !important;
}
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete:hover::before{
    background:rgba(174,78,78,.66) !important;
    border-color:rgba(239,178,178,.80) !important;
}
html body .geoport-fav-list .geoport-fav-card > button.geoport-fav-delete:hover::after{
    color:#ffffff !important;
}
html body .geoport-fav-list .geoport-fav-open{
    padding-right:16px !important;
}
</style>
'''

inject_at = '</body>'
if inject_at in html:
    html = html.replace(inject_at, block + '\n</body>', 1)
else:
    html += block

path.write_text(html, encoding="utf-8")
print("FINAL UI polish applied.")
print("Favorite grid: 2 columns × 3 visible rows.")
print("Favorite delete: 16x16, top-right, translucent red.")
print("Destructive buttons: unified translucent-red DPort style with hover.")

