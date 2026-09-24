# DPort

**DPort 6.9.0** — Windows 版 iPhone 定位、位置模擬與 GPX 工具。

DPort 是一個以 Windows 為主要使用環境的 iPhone 裝置工具，提供透過 USB 與 iPhone 連線、定位控制、位置模擬及 GPX 相關功能。正式發行版本以單一可執行檔為主要使用方式，一般使用者不需要另外安裝 Python、pip、PyInstaller 或 pymobiledevice3。

> **目前主版基底：DPort 6.9.0**  
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
  - 同版本但檔案雜湊不同的修正版，也可視為新的更新。
- 🌐 **環境資料功能**
  - 部分功能可使用環境資料 API；API Key 應透過 GitHub Actions Secret 或本機設定提供，不應公開提交真正的金鑰。

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
2. 安裝指定版本 Python。
3. 安裝固定版本的 Python 相依套件。
4. 建置 DPort 及其更新元件。
5. 產生 SHA-256 校驗值。
6. 建立或更新 GitHub Release。
7. 上傳正式版 EXE。

目前建置依賴包含固定版本：

`pymobiledevice3==11.19.1`

完整建置依賴請參考：

[`requirements-build.txt`](requirements-build.txt)

第三方授權與 GPL / LGPL 注意事項：

[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

自動建置說明：

[`GITHUB_AUTO_BUILD.md`](GITHUB_AUTO_BUILD.md)

---

## 🔐 MOENV API Key

若功能需要使用環境資料 API，請使用 GitHub Actions Secret 提供 API Key。

### GitHub 設定方式

進入：

**Repository → Settings → Secrets and variables → Actions**

建立 Repository Secret：

`MOENV_API_KEY`

真正的 API Key **不要直接提交到公開 Repository**。

本專案提供：

[`moenv_api_key.txt.example`](moenv_api_key.txt.example)

供設定格式參考。

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

即使版本號相同，只要 Release 中的 EXE SHA-256 發生變化，也可以作為修正版更新。

---

## 🏷️ 版本與 Release

目前主版固定為：

**DPort 6.9.0**

正式版本建議透過 Git Tag 與 GitHub Release 發布。

例如：

`v6.9.0`

Release 中的正式執行檔應以實際建置產物為準。

---

## 📁 專案結構

主要目錄與檔案：

```
DPort/
├─ .github/
├─ scripts/
├─ source/
├─ src/
├─ requirements-build.txt
├─ moenv_api_key.txt.example
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

## 🧩 第三方元件與授權

DPort 使用多項第三方開源軟體與 Python 套件。

其中包含：

- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3)
- Flask
- Requests
- pyuac
- psutil
- pycountry
- PyInstaller
- inquirer3
- readchar
- pyimg4
- pytun-pmd3

這些第三方元件均依其各自的原始專案授權條款使用。

**DPort 不主張擁有上述第三方專案的著作權或其他智慧財產權。**

使用、重新散布或修改第三方元件時，請同時遵守各第三方專案所附的授權條款及 NOTICE / LICENSE 文件。

第三方專案：

- pymobiledevice3：<https://github.com/doronz88/pymobiledevice3>
- Flask：<https://github.com/pallets/flask>
- Requests：<https://github.com/psf/requests>
- pyuac：<https://github.com/NickBruning/pyuac>
- psutil：<https://github.com/giampaolo/psutil>
- pycountry：<https://github.com/flyingcircusio/pycountry>
- PyInstaller：<https://github.com/pyinstaller/pyinstaller>
- inquirer3：<https://github.com/kazeburo/inquirer3>
- readchar：<https://github.com/magmax/python-readchar>
- pyimg4：<https://github.com/doronz88/pyimg4>
- pytun-pmd3：<https://github.com/doronz88/pytun-pmd3>

> 第三方套件的精確授權版本與條款，應以各專案當下發布內容及隨套件提供的 LICENSE 為準。

---

## 📜 DPort 授權

### DPort License

Copyright (c) 2026 DickyR15

本專案中由 **DickyR15 / DPort** 所創作、撰寫或維護的原始碼、文件、圖示、介面設計及其他原創內容，除另有明確標示外，均為著作權人所有。

除非另有明確書面授權，您不得：

- 將 DPort 的原創內容重新發布為另一個獨立專案。
- 移除或修改原始作者、著作權及授權聲明。
- 將 DPort 原創內容宣稱為自己所創作。
- 將 DPort 商業化、重新包裝或散布為其他產品，而未取得著作權人授權。

允許個人使用、研究、測試及在符合本授權與第三方授權條款的前提下查看原始碼。

**DPort 的授權只適用於 DPort 自有原創內容，不延伸或取代第三方元件原本的授權。**

如需取得額外授權、商業使用權、重新發布權或其他未列於本授權中的權利，請先取得著作權人 **DickyR15** 的明確書面許可。

---

## ⚖️ 免責聲明

DPort 依「現況」提供，不提供任何明示或默示的保證。

在法律允許的最大範圍內，DickyR15 不對因使用、無法使用、誤用、更新失敗、裝置相容性問題、第三方服務變更或其他相關因素所造成的任何直接、間接、附帶、特殊或衍生損害負責。

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
| DPort 原創程式碼 | DPort License |
| DPort 文件 | DPort License |
| DPort 原創介面／圖示 | DPort License |
| pymobiledevice3 | 依其原始授權 |
| 其他第三方套件 | 依各自原始授權 |
| GitHub Actions / 建置工具 | 依各工具自身授權 |
| API / 外部服務 | 依各服務提供者條款 |

**完整合法權利請以本 README、Repository 內的 LICENSE，以及各第三方專案所提供的授權文件為準。**

---

© 2026 DickyR15. All rights reserved.
