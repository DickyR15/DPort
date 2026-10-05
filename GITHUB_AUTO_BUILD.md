# DPort GitHub 全自動建置

這個版本將 DPort 的 Windows 建置與 Release 發布交給 GitHub Actions。

## 發布方式

在 `main` 分支修改程式後，建立並推送版本標籤：

```text
vX.Y.Z
```

GitHub Actions 會自動：

1. Windows runner 建立 Python 3.14 建置環境
2. 安裝 requirements-build.txt
3. 建置內嵌 DPort-Updater.exe
4. 建置完整 DPort EXE
5. 產生 SHA-256
6. 建立 GitHub Release
7. 上傳 EXE 與 checksum

使用者端只需要 DPort EXE，不需要 Python、pip 或 PyInstaller。

## 手動觸發

GitHub → Actions → DPort Build & Release → Run workflow，輸入既有版本標籤，例如 `vX.Y.Z`。版本標籤必須符合 `vX.Y.Z`，且 Tag 內的 `src/dport_version.py` 必須使用相同版本。

## pymobiledevice3 自動更新

GitHub Actions 每 6 小時檢查一次上游 pymobiledevice3。發現新版時會建立更新 PR，先通過版本驗證、Python 編譯與 Windows PyInstaller Build Validation，再由維護者手動合併；合併不會自動建立 DPort Release。

## DPort 自動更新

DPort 會讀取 `DickyR15/DPort` 的最新正式 Release，尋找對應的 `DPort-x.y.z.exe` 與 `.sha256`，驗證 SHA-256 後交給內嵌 updater 等待舊程序退出、替換目前 EXE，再自動重新啟動。

## 注意

版本號由 Git tag / workflow input 決定；不需要手動修改 `version_info.txt`。Wi-Fi 功能沒有在這個主版流程中新增。
