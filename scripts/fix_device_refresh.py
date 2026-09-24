from pathlib import Path
import re

path = Path("src/templates/map.html")
if not path.exists():
    raise SystemExit(f"UI template not found: {path}")

text = path.read_text(encoding="utf-8")
original = text

# ---------------------------------------------------------------------------
# 1. Device refresh button fix
# ---------------------------------------------------------------------------
legacy_pattern = re.compile(
    r'''\s*<script>\s*\(function\(\)\{\s*
        function\s+syncDeviceRefreshButton\(\)\s*\{.*?
        document\.addEventListener\(\s*['"]DOMContentLoaded['"]\s*,\s*function\(\)\{\s*
        syncDeviceRefreshButton\(\);\s*
        setInterval\(syncDeviceRefreshButton\s*,\s*500\);\s*
        \}\);\s*
        \}\)\(\);\s*</script>\s*''',
    re.S | re.X,
)
text, legacy_removed = legacy_pattern.subn("\n", text)

text = text.replace(
    "button.disabled = (typeof isDeviceConnected !== 'undefined' && isDeviceConnected);",
    "button.disabled = false;",
)

handler_pattern = re.compile(
    r'''(function\s+handleUsbCableRemoved\(\)\s*\{.*?
        if\s*\(spinnerElement\)\s*spinnerElement\.style\.display\s*=\s*'none';)''',
    re.S | re.X,
)
if "refreshButtonAfterUsbRemoval.disabled = false;" not in text:
    def handler_repl(match):
        return match.group(1) + """
    var refreshButtonAfterUsbRemoval = document.getElementById('refresh-device');
    if (refreshButtonAfterUsbRemoval) {
        refreshButtonAfterUsbRemoval.disabled = false;
        refreshButtonAfterUsbRemoval.removeAttribute('aria-disabled');
    }"""
    text, handler_hits = handler_pattern.subn(handler_repl, text, count=1)
else:
    handler_hits = 0

text = text.replace(
    'title="重新讀取 USB 裝置清單"',
    'title="重新讀取 USB / Wi-Fi 裝置清單"',
)

# ---------------------------------------------------------------------------
# 2. Normal map-click -> coordinate + reverse geocode
# ---------------------------------------------------------------------------
map_click_old = """    // DPort: ordinary map clicks are inert. Drawing mode is the only mode
    // where a map click is allowed to add a route point.
    map.on('click', function(event){
        if (typeof isDrawingMode !== 'undefined' && isDrawingMode) {
            handleMapClick(event);
        }
    });"""

map_click_new = """    // Normal map clicks select a coordinate and identify the place.
    // Drawing mode keeps the existing route-point behavior.
    map.on('click', function(event){
        if (typeof isDrawingMode !== 'undefined' && isDrawingMode) {
            handleMapClick(event);
            return;
        }

        const lat = Number(event.latlng.lat);
        const lng = Number(event.latlng.lng);
        if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

        if (typeof geoportSetMapOnlyCoordinates === 'function') {
            geoportSetMapOnlyCoordinates(lat, lng);
        }
        if (typeof geoportMoveActiveMarker === 'function') {
            geoportMoveActiveMarker(lat, lng, 15);
        }
        if (typeof geoportScheduleReverseGeocode === 'function') {
            geoportScheduleReverseGeocode(lat, lng);
        }
        if (typeof geoportStatus === 'function') {
            geoportStatus('正在辨識地點……', false);
        }
    });"""

if map_click_old in text:
    text = text.replace(map_click_old, map_click_new, 1)
elif "Normal map clicks select a coordinate and identify the place." not in text:
    raise SystemExit("Expected map click handler was not found.")

# ---------------------------------------------------------------------------
# 3. Favorite place-name resolver
# ---------------------------------------------------------------------------
reverse_marker = "function geoportScheduleReverseGeocode(lat,lng){"
resolver = """async function geoportResolvePlaceNameForCoordinates(lat,lng){
    const cached=geoportGetCurrentPlaceNameForCoordinates(lat,lng);
    if(cached) return cached;

    const a=Number(lat),b=Number(lng);
    if(!Number.isFinite(a)||!Number.isFinite(b)) return '';

    const layers=[
        'poi,manmade,building',
        'natural,waterway,place,highway,railway,landuse',
        'address'
    ];

    for(const layer of layers){
        const url='https://nominatim.openstreetmap.org/reverse?format=jsonv2'
            +'&lat='+encodeURIComponent(a)
            +'&lon='+encodeURIComponent(b)
            +'&zoom=18&addressdetails=1&namedetails=1'
            +'&layer='+encodeURIComponent(layer)
            +'&accept-language=zh-TW,zh;q=0.9,en;q=0.7';
        try{
            const data=await fetchJsonWithTimeout(url,6000);
            if(!data) continue;
            if(layer!=='address' && !geoportIsUsefulNearbyPlace(data,a,b)) continue;
            const name=geoportFormatReverseName(data);
            if(name) return name;
        }catch(e){
            console.debug('最愛位置名稱辨識略過一次:',e);
        }
    }
    return '';
}

"""
if "async function geoportResolvePlaceNameForCoordinates" not in text:
    if reverse_marker not in text:
        raise SystemExit("Reverse geocode function marker was not found.")
    text = text.replace(reverse_marker, resolver + reverse_marker, 1)

# ---------------------------------------------------------------------------
# 4. Favorites UI: 2 columns normally, 3 on wide screens, 6 visible slots
# ---------------------------------------------------------------------------
fav_render_old = """function geoportRenderFavorites(){
    const box=document.getElementById('geoport-favorites'); if(!box) return;
    const items=geoportGetFavorites(); box.innerHTML='';
    if(!items.length){ box.innerHTML='<small>沒有已儲存的位置。</small>'; return; }
    items.forEach((item,i)=>{
        const b=document.createElement('button'); b.type='button'; b.className='btn btn-sm btn-outline-secondary'; b.textContent=item.name;
        b.onclick=()=>{geoportSetMapOnlyCoordinates(item.lat,item.lng); geoportMoveActiveMarker(item.lat,item.lng,15)};
        box.appendChild(b);
        const d=document.createElement('button'); d.type='button'; d.className='btn btn-sm btn-outline-danger'; d.textContent='×'; d.title='刪除 '+item.name;
        d.onclick=()=>{const a=geoportGetFavorites();a.splice(i,1);geoportSetFavorites(a);geoportRenderFavorites()}; box.appendChild(d);
    });
}"""

fav_render_new = """function geoportRenderFavorites(){
    const box=document.getElementById('geoport-favorites'); if(!box) return;
    const items=geoportGetFavorites(); box.innerHTML='';

    const count=document.getElementById('geoport-fav-count');
    if(count) count.textContent=items.length + '/20';

    if(!items.length){
        box.innerHTML='<div class="geoport-fav-empty">還沒有儲存的位置</div>';
        return;
    }

    items.forEach((item,i)=>{
        const card=document.createElement('div');
        card.className='geoport-fav-card';

        const open=document.createElement('button');
        open.type='button';
        open.className='geoport-fav-open';
        open.title='前往 ' + String(item.name || '未命名位置');

        const name=document.createElement('span');
        name.className='geoport-fav-name';
        name.textContent=String(item.name || '未命名位置');

        const detail=document.createElement('span');
        detail.className='geoport-fav-detail';
        detail.textContent=Number(item.lat).toFixed(6) + ', ' + Number(item.lng).toFixed(6);

        open.appendChild(name);
        open.appendChild(detail);
        open.onclick=()=>{
            geoportSetMapOnlyCoordinates(item.lat,item.lng);
            geoportMoveActiveMarker(item.lat,item.lng,15);
            geoportStatus('已載入最愛位置', false);
        };

        const del=document.createElement('button');
        del.type='button';
        del.className='geoport-fav-delete';
        del.textContent='×';
        del.title='刪除 ' + String(item.name || '未命名位置');
        del.setAttribute('aria-label','刪除 ' + String(item.name || '未命名位置'));
        del.onclick=(event)=>{
            event.preventDefault();
            event.stopPropagation();
            const next=geoportGetFavorites();
            next.splice(i,1);
            geoportSetFavorites(next);
            geoportRenderFavorites();
        };

        card.appendChild(open);
        card.appendChild(del);
        box.appendChild(card);
    });
}"""

if fav_render_old in text:
    text = text.replace(fav_render_old, fav_render_new, 1)
elif "geoport-fav-card" not in text:
    raise SystemExit("Favorite renderer was not found.")

fav_save_old = """async function geoportSaveFavorite(){
    const c=geoportParseCoordinates(document.getElementById('coordinates').value);
    if(!c){dportUiAlert('請輸入緯度與經度。');return;}
    const suggestedName =
        geoportGetCurrentPlaceNameForCoordinates(c.lat,c.lng) ||
        '自訂位置';
    const name=await dportUiPrompt('請輸入此地點名稱', suggestedName);
    if(name===null) return;
    const cleanName=String(name).trim();
    if(!cleanName){dportUiAlert('地點名稱不可空白。');return;}
    const a=geoportGetFavorites().filter(x=>!(x.lat===c.lat&&x.lng===c.lng)); a.unshift({name:cleanName,lat:c.lat,lng:c.lng}); geoportSetFavorites(a); geoportRenderFavorites();
}"""

fav_save_new = """async function geoportSaveFavorite(){
    const c=geoportParseCoordinates(document.getElementById('coordinates').value);
    if(!c){dportUiAlert('請輸入緯度與經度。');return;}

    let suggestedName=geoportGetCurrentPlaceNameForCoordinates(c.lat,c.lng);
    if(!suggestedName && typeof geoportResolvePlaceNameForCoordinates==='function'){
        suggestedName=await geoportResolvePlaceNameForCoordinates(c.lat,c.lng);
    }
    suggestedName=suggestedName || '自訂位置';

    const name=await dportUiPrompt(
        '請輸入此地點名稱（可直接使用自動辨識名稱）',
        suggestedName
    );
    if(name===null) return;

    const cleanName=String(name).trim();
    if(!cleanName){dportUiAlert('地點名稱不可空白。');return;}

    const a=geoportGetFavorites().filter(x=>!(x.lat===c.lat&&x.lng===c.lng));
    a.unshift({name:cleanName,lat:c.lat,lng:c.lng});
    geoportSetFavorites(a);
    geoportRenderFavorites();
}"""

if fav_save_old in text:
    text = text.replace(fav_save_old, fav_save_new, 1)
elif "geoportResolvePlaceNameForCoordinates(c.lat,c.lng)" not in text:
    raise SystemExit("Favorite save routine was not found.")

# ---------------------------------------------------------------------------
# 5. Repeatable positioning: never present success as "已定位"
# ---------------------------------------------------------------------------
text = text.replace(
    "geoportStatus('已定位', true);",
    "geoportStatus('定位成功，可再次定位', true);",
)

text = text.replace(
    "const isLocated = /即時定位已啟用|已定位/.test(text);",
    "const isLocated = false; // 定位成功後仍可再次定位",
)

# ---------------------------------------------------------------------------
# 6. Favorites count
# ---------------------------------------------------------------------------
title_old = '<div class="geoport-favorites-title">我的最愛位置</div>'
title_new = '<div class="geoport-favorites-title">我的最愛位置 <span id="geoport-fav-count" class="geoport-fav-count">0/20</span></div>'
if title_old in text:
    text = text.replace(title_old, title_new, 1)

# ---------------------------------------------------------------------------
# 7. Favorites CSS
# ---------------------------------------------------------------------------
css_old = '.geoport-fav-list{padding:9px 11px !important;border:1.5px solid #aaa}'
css_new = """.geoport-fav-list{
    display:grid !important;
    grid-template-columns:repeat(2,minmax(0,1fr));
    gap:8px;
    padding:10px !important;
    border:1px solid rgba(170,170,170,.65);
    border-radius:12px;
    max-height:236px;
    overflow-y:auto;
    overflow-x:hidden;
    scrollbar-width:thin;
}
.geoport-fav-card{position:relative;min-width:0}
.geoport-fav-open{
    width:100%;
    min-height:64px;
    border:1px solid rgba(180,190,215,.55) !important;
    border-radius:10px !important;
    display:flex;
    flex-direction:column;
    align-items:flex-start;
    justify-content:center;
    text-align:left;
    padding:9px 36px 9px 12px !important;
    overflow:hidden;
}
.geoport-fav-open:hover{filter:brightness(1.08)}
.geoport-fav-name{
    width:100%;
    font-size:16px !important;
    font-weight:700 !important;
    line-height:1.25;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
}
.geoport-fav-detail{
    width:100%;
    margin-top:3px;
    font-size:11px;
    opacity:.72;
    white-space:nowrap;
    overflow:hidden;
    text-overflow:ellipsis;
}
.geoport-fav-delete{
    position:absolute;
    top:6px;
    right:6px;
    width:26px;
    height:26px;
    padding:0 !important;
    border:1px solid rgba(220,150,150,.75) !important;
    border-radius:8px !important;
    background:transparent !important;
    color:inherit !important;
    font-size:18px !important;
    line-height:24px;
    font-weight:700;
    cursor:pointer;
}
.geoport-fav-empty{
    grid-column:1 / -1;
    padding:14px 10px;
    text-align:center;
    opacity:.72;
    font-size:14px;
}
.geoport-fav-count{
    font-size:13px !important;
    font-weight:600 !important;
    opacity:.68;
    margin-left:6px;
}
@media (min-width:1180px){
    .geoport-fav-list{grid-template-columns:repeat(3,minmax(0,1fr))}
}
@media (max-width:700px){
    .geoport-fav-list{grid-template-columns:repeat(2,minmax(0,1fr));max-height:220px}
    .geoport-fav-open{min-height:60px;padding-left:10px !important}
    .geoport-fav-name{font-size:15px !important}
}"""

if '.geoport-fav-card{' not in text:
    if css_old not in text:
        raise SystemExit("Favorite CSS block was not found.")
    text = text.replace(css_old, css_new, 1)

path.write_text(text, encoding="utf-8")

print(f"legacy refresh timer removed: {legacy_removed}")
print(f"USB removal handler patched: {handler_hits}")
print("6.9.1 location/favorites UI improvements applied.")
print("- Map click restores coordinate picking + reverse geocoding")
print("- Favorite name resolves automatically before save")
print("- Favorite list shows 6 slots in a compact grid and scrolls after overflow")
print("- Successful simulation keeps the button label as 定位 for repeat use")
