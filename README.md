# DPort

**DPort** — Windows 版 iPhone 定位、位置模擬與 GPX 工具。

目前版本：**DPort 6.9.3**。

DPort 是一個以 Windows 為主要使用環境的 iPhone 裝置工具，提供透過 USB 與 iPhone 連線、定位控制、位置模擬及 GPX 相關功能。正式發行版本以單一可執行檔為主要使用方式，一般使用者不需要另外安裝 Python、pip、PyInstaller 或 pymobiledevice3。

> **目前主版以 USB 功能為主，Wi-Fi 裝置連線功能不在此正式主版基底中。**

---

## ✨ 主要功能

- 📱 **iPhone 裝置連線**
  - 支援 Windows 與 iPhone 之間的裝置連線。
  - 目前正式主版以 USB 連線為主要方式。
- 📍 **iPhone 定位與位置模擬**
  - 可配合支援的裝置環境進行位置相關操作。
- 🗺️ **地圖與座標操作**
  - 選擇、輸入及管理位置座標。
- 🧭 **GPX 相關功能**
  - 支援 GPX 路徑資料的載入與相關定位模擬流程。
- 🔄 **自動更新**
  - 程式可檢查 GitHub Release。
  - 下載新版本後驗證 SHA-256，再進行程式替換與重新啟動。

---

## 🖥️ 一般使用者

一般使用者只需要下載 GitHub **Releases** 中提供的 DPort EXE。

不需要另外安裝：

- Python
- pip
- PyInstaller
- pymobiledevice3

所需的執行環境與 Python 相依元件會在正式建置時整合進發行版。

---

## 📦 GitHub Actions 自動建置

本專案使用 GitHub Actions 進行 Windows 自動建置。

主要流程包含：

1. 使用 Windows Runner 建置。
2. 安裝 `.github/python-version.txt` 指定的 Python 建置版本（目前為 3.14.8）。
3. 安裝固定版本的 Python 相依套件。
4. 建置 DPort 及其更新元件。
5. 產生 SHA-256 校驗值。
6. 建立或更新 GitHub Release。
7. 上傳正式版 EXE。

建置依賴會隨目前正式版本更新；完整建置依賴請參考：

[`requirements-build.txt`](requirements-build.txt)

第三方授權與 GPL / LGPL 注意事項：

[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

自動建置說明：

[`GITHUB_AUTO_BUILD.md`](GITHUB_AUTO_BUILD.md)

---

## 🔄 使用者自動更新機制

DPort 內建更新流程會檢查本專案的正式 GitHub Release。

更新流程概念如下：

1. 檢查目前版本。
2. 查詢正式 Release。
3. 發現更新後下載完整 DPort EXE。
4. 驗證下載檔案的 SHA-256。
5. 關閉目前執行中的 DPort。
6. 替換舊版 EXE。
7. 自動重新啟動新版本。

僅當正式 Release 的版本號高於目前版本時，才會進行版本更新；同版本的重新建置不會觸發自動更新。

---

## 🏷️ 版本與 Release

正式版本建議透過 Git Tag 與 GitHub Release 發布。

例如：

`vX.Y.Z`

版本號以 GitHub Releases 的正式發行版本為準。

Release 中的正式執行檔應以實際建置產物為準。

---

## 📁 專案結構

主要目錄與檔案：

```
DPort/
├─ .github/
├─ scripts/
├─ src/
├─ requirements-build.txt
├─ GITHUB_AUTO_BUILD.md
├─ README.md
└─ .gitignore
```

---

## ⚠️ 使用注意事項

DPort 涉及 iPhone 裝置連線及位置相關功能，實際可用功能會依：

- Windows 環境
- iOS 版本
- iPhone 型號
- 配對及信任狀態
- Apple 裝置通訊介面
- 第三方相依套件版本

而有所不同。

請確認你使用的裝置、系統版本及相關服務符合 Apple 與所在地適用的規範。

本專案不保證所有 iOS 版本、所有裝置或所有第三方環境均可正常運作。

---

## 🧩 第三方元件、上游來源與授權

DPort Windows 是基於開源專案 **GeoPort** 進行修改與再開發。GeoPort 採用 **GNU GPL
v3.0**；DPort Windows 依 Repository 根目錄 LICENSE 採 GPL-3.0 發布，並保留上游及第三方
授權所要求的著作權與授權資訊。

### 上游專案

- **GeoPort** — https://github.com/davesc63/GeoPort — GPL-3.0
- **pymobiledevice3** — https://github.com/doronz88/pymobiledevice3 — GPL-3.0-or-later

DPort-specific modifications include DPort branding, Traditional Chinese (Taiwan) localization,
UI adjustments, GPX-related behavior, device-state handling, update/build tooling and other
project-specific changes.

### 第三方授權

DPort 使用的第三方元件，其著作權及授權仍歸各自權利人所有。DPort 不以自己的授權取代、
縮減或限制第三方授權所授予的權利。

完整清單及目前建置依賴版本請參考：

- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
- [requirements-build.txt](requirements-build.txt)

目前直接依賴包含 GPL、LGPL、MIT、BSD、Apache 等不同授權；實際再發布時應遵守各元件
隨附的 LICENSE / NOTICE 以及適用條款。

### 前端與地圖

DPort 的地圖介面引用 Leaflet、Bootstrap、jQuery、Popper、Leaflet 相關外掛、Font Awesome、
Lineicons 等第三方資源，並引用 OpenStreetMap、Stadia Maps、OpenMapTiles 等外部地圖
資料／圖磚服務。

這些程式庫、圖示、字型、地圖資料與服務均由各自權利人控制，適用各自的授權、attribution、
API 及服務條款。DPort 不主張擁有這些第三方內容。

### GPL 二進位發布與原始碼

DPort 發布包含 GPL 涵蓋內容的 EXE 時，應讓使用者能取得該版本所需的 Corresponding Source
以及適用的 GPL 授權資訊。

正式 Release 應使用明確的 Git Tag 與對應的 Source Snapshot 對應所發布的二進位版本。

例如：

`vX.Y.Z` → 該 Tag 所指向的 Commit → 該 Commit 建置出的 `DPort-X.Y.Z.exe`

GitHub Release 的 Source archive 應以該 Release Tag 為準。建置流程應確認 Tag 版本與 DPort 內部版本一致，避免二進位檔與 Source Snapshot 對應錯誤。

### 商標與品牌

**DPort、Dicky** 是 DPort 專案使用的名稱／品牌識別。

**Apple、iPhone、iPad、iOS、iPadOS** 等名稱及相關商標屬 Apple Inc. 或相關權利人所有。

DPort 並非 Apple 官方產品，也不表示 Apple 背書、贊助、認證或官方合作。

軟體 GPL-3.0 授權本身不等同於授予 DPort、Dicky、Apple 或其他第三方商標的使用權。

### 安全與機密資訊

公開 Repository 不應包含：

- 密碼
- Access Token
- 私鑰
- Apple Developer 憑證
- 程式碼簽署憑證
- 其他機密資訊

機密資訊應保存在本機設定或 GitHub Secrets，不應提交到公開 Repository。

---

## 📜 DPort Windows License

DPort Windows 使用 **GNU General Public License v3.0 (GPL-3.0)**。

完整 GPL 條款位於 Repository 根目錄的 [LICENSE](LICENSE)。

本授權適用於本專案中依 GPL-3.0 發布的內容；第三方元件仍受其原始授權控制。
不得使用本專案的說明文件或其他附加條款，限制 GPL 所授予的修改、複製、再發布等權利。

---

## ⚖️ 免責聲明

DPort 依「現況」提供，不提供任何明示或默示的保證。

在法律允許的最大範圍內，DickyR15 不對因使用、無法使用、誤用、更新失敗、裝置相容性問題、
第三方服務變更或其他相關因素所造成的任何直接、間接、附帶、特殊或衍生損害負責。

使用者應自行確認：

- 裝置資料及重要資料已適當備份。
- 使用方式符合所在地法律及相關服務條款。
- 第三方套件與服務的使用符合其各自授權條款。

---

## 👤 作者

**DickyR15**

GitHub：

https://github.com/DickyR15

DPort Repository：

https://github.com/DickyR15/DPort

---

## 📄 License / 授權摘要

| 項目 | 授權方式 |
|---|---|
| DPort Windows | GNU GPL-3.0 |
| GeoPort 上游內容 | GNU GPL-3.0 |
| pymobiledevice3 | GPL-3.0-or-later |
| pyimg4 | GPL-3.0 |
| pytun-pmd3 | GPL-3.0-or-later |
| 其他第三方套件 | 依各自原始授權 |
| 地圖資料／圖磚服務 | 依各服務提供者條款 |
| DPort / Dicky 品牌 | 與軟體授權分開處理 |

完整權利與義務請以 LICENSE、THIRD_PARTY_NOTICES.md、各第三方 LICENSE / NOTICE 及相關
服務條款為準。

---

© 2026 DickyR15 / DPort.

