# DPort

DPort 6.9.0 — iPhone 定位與 GPX 模擬工具。

## GitHub 自動建置

版本標籤採用：

- `v6.9.0`
- `v6.9.1`
- `v6.9.2`

推送版本 Tag 後，GitHub Actions 會在 Windows Runner 自動：

1. 安裝 Python 3.14
2. 安裝固定版本的 pymobiledevice3
3. 建置內嵌更新器
4. 建置完整 DPort EXE
5. 產生 SHA-256
6. 建立 GitHub Release 並上傳 EXE

一般使用者只需要 DPort EXE，不需要 Python、pip 或 PyInstaller。

Wi-Fi 功能目前不在這個主版基底中。
