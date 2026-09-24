# DPort GitHub 全自動建置

Repository：DickyR15/DPort

主版基底：
- DPort 6.9.0
- USB 功能保留
- pymobiledevice3 固定 11.19.1
- Wi-Fi 不在主版開啟
- 一般使用者只需要完整 DPort EXE，不需要 Python

## 一次性設定

在 GitHub：
Settings → Secrets and variables → Actions → New repository secret

建立：
MOENV_API_KEY

真正的 API Key 不要提交到公開 Repository。

## 自動建置

目前正式版本固定為：
v6.9.0

建置流程會把其他 Tag / 手動輸入也正規化為 DPort 6.9.0，並更新同一個 v6.9.0 Release 的 EXE

GitHub Actions 會在 Windows Runner：
1. 安裝 Python 3.14
2. 安裝固定版本依賴
3. 建置內嵌 DPortUpdater.exe
4. 建置完整 DPort EXE
5. 產生 SHA-256
6. 建立 GitHub Release
7. 上傳 EXE

## 使用者自動更新

DPort 會檢查同一個 Repository 的最新正式 Release，下載新的完整 DPort EXE，驗證 SHA-256，關閉舊程序，替換 EXE，再自動重新啟動。相同版本 6.9.0 若 Release EXE 的 SHA-256 發生變化，也會視為有新的修正版並執行更新。

因此使用者不需要 Python、pip、PyInstaller 或另外安裝 pymobiledevice3。

