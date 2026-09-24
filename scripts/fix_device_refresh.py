from pathlib import Path
import re

path = Path("src/templates/map.html")
if not path.exists():
    raise SystemExit(f"UI template not found: {path}")

text = path.read_text(encoding="utf-8")
original = text

# The refresh button must only be disabled while the application is actively
# connected. Remove the historical background timer that re-disabled it from
# stale isDeviceConnected state after the USB cable was removed.
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

# Manual refresh is intentionally blocked while an active connection exists.
# After refresh finishes, the button must not be left disabled based on stale
# state.
text = text.replace(
    "button.disabled = (typeof isDeviceConnected !== 'undefined' && isDeviceConnected);",
    "button.disabled = false;",
)

# Make the physical USB removal handler the authoritative place that restores
# Refresh.
handler_pattern = re.compile(
    r'''(function\s+handleUsbCableRemoved\(\)\s*\{.*?
        if\s*\(spinnerElement\)\s*spinnerElement\.style\.display\s*=\s*'none';)''',
    re.S | re.X,
)
if "refreshButtonAfterUsbRemoval.disabled = false;" not in text:
    def handler_repl(m):
        return m.group(1) + """
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

path.write_text(text, encoding="utf-8")

print(f"legacy refresh timer removed: {legacy_removed}")
print(f"USB removal handler patched: {handler_hits}")
print(f"changed: {text != original}")

if legacy_removed == 0 and handler_hits == 0 and "button.disabled = false;" not in text:
    raise SystemExit("Refresh state patch did not find expected source patterns.")


# ==================== DPort 6.9.1 location/favorites improvements ====================

# 1) Normal map click should select a point and reverse-geocode it.
map_click_old = """    // DPort: ordinary map clicks are inert. Drawing mode is the only mode
    // where a map click is allowed to add a route point.
    map.on('click', function(event){
        if (typeof isDrawingMode !== 'undefined' && isDrawingMode) {
            handleMapClick(event);
        }
    });"""
map_click_new = """    // Normal map clicks select a location and trigger place-name lookup.
    // Drawing mode retains its existing route-point behavior.
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
map_click_hits = text.count(map_click_old)
if map_click_hits:
    text = text.replace(map_click_old, map_click_new, 1)

# 2) Resolve the place name again at the time a favorite is saved. This avoids
# the race where the user clicks the map and immediately saves before the
# asynchronous reverse-geocode request has finished.
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
        raise SystemExit("Reverse geocode function marker not found.")
    text = text.replace(reverse_marker, resolver + reverse_marker, 1)

# 3) Replace the favorite renderer with a compact card grid.
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
fav_render_hits = text.count(fav_render_old)
if fav_render_hits == 0:
    raise SystemExit("Favorite renderer not found.")
text=text.replace(fav_render_old,fav_render_new,1)

# 4) Use the resolved place name as the default Favorite name.
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
if fav_save_old not in text:
    raise SystemExit("Favorite save routine not found.")
text=text.replace(fav_save_old,fav_save_new,1)

# 5) Never show the misleading "已定位" button state after a successful
# simulation; the same coordinate can be sent again at any time.
text=text.replace(
    "geoportStatus('已定位', true);",
    "geoportStatus('定位成功，可再次定位', true);"
)
text=text.replace(
    "const isLocated = /即時定位已啟用|已定位/.test(text);",
    "const isLocated = false; // 定位成功後按鈕維持「定位」，允許重複定位"
)

# 6) Show favorite count in the section header.
title_old = '<div class="geoport-favorites-title">我的最愛位置</div>'
title_new = '<div class="geoport-favorites-title">我的最愛位置 <span id="geoport-fav-count" class="geoport-fav-count">0/20</span></div>'
if title_old in text:
    text=text.replace(title_old,title_new,1)

# 7) Replace the old plain list styling with a compact click-friendly grid:
# 2 columns by default, 3 columns on wider screens, exactly 6 visible cards.
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
        raise SystemExit("Favorite CSS block not found.")
    text=text.replace(css_old,css_new,1)

path.write_text(text, encoding="utf-8")
print(f"Map click restored: {map_click_hits}")
print(f"Favorite renderer replaced: {fav_render_hits}")
print("Favorite name resolver added.")
print("Repeat positioning state fixed.")
print("Favorite UI changed to 6-slot grid with scrollbar after overflow.")
