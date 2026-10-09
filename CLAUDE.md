# SENTINEL 輿情監控系統

監控 Facebook 公開社團「靠北長官2026」(groups/3643373249226437，約 8.3 萬成員) 的每日貼文，做情緒分析與關鍵字統計，輸出成給主管看的網頁儀錶板。

- 使用者以繁體中文溝通，請用繁體中文回覆、寫註解與文件。
- 使用者非專業工程師：解釋時少用術語，指令要能直接複製執行（Windows / PowerShell）。
- 時區一律用台灣時間 UTC+8（程式內用 `timezone(timedelta(hours=8))`，不要用裸的 `datetime.now()`）。

## 線上位置

| 項目 | 值 |
|---|---|
| GitHub Repo | https://github.com/cxr0801/sentinel-dashboard (Public) |
| 儀錶板 (GitHub Pages) | https://cxr0801.github.io/sentinel-dashboard/sentinel_dashboard.html |
| 本機路徑 | `C:\Users\User2\Desktop\vibe coding tool\reptile fb` |

## 資料流（全自動，已上線）

```
Apify 排程 (Cron 5 16 * * * UTC = 台灣 00:05；Number of posts=25；2026-10-09 起只統計台灣 17:00–24:00 發文)
  → Actor apify/facebook-groups-scraper 爬社團
  → Run succeeded 時 Apify Webhook POST
      https://api.github.com/repos/cxr0801/sentinel-dashboard/dispatches
      body: {"event_type": "apify-done"}
  → GitHub Actions (.github/workflows/update-dashboard.yml)
      pip install → python auto_daily_analysis.py → git commit & push
      （commit 回 repo 的檔案：sentinel_dashboard.html、summary_history.json、all_posts_db.json）
  → GitHub Pages 自動重新部署
```

- Workflow 也可在 GitHub Actions 頁面手動觸發（`workflow_dispatch`）。
- `APIFY_API_TOKEN` 只放在 GitHub Secrets 與本機環境變數。**絕對不要寫進程式碼或 commit**——這個 repo 是 Public，2026-04-20 曾經因 Token 外洩被 Apify 自動停用。

## 主要檔案

| 檔案 | 用途 |
|---|---|
| `auto_daily_analysis.py` | 主程式。步驟：1 查最新 Apify run → 2 下載資料集到 `data/` → 2.5 合併進 `all_posts_db.json` → 3 分析 → 4 Excel 到 `output/` → 5 改寫儀錶板 HTML → 6 產出待回覆清單 |
| `sentinel_dashboard.html` | 單一 HTML 檔的前端儀錶板，資料以 JS 常數內嵌（`const C=`、`const POSTS=`、`const KW=` 等），由 `update_dashboard()` 用 regex 替換 |
| `all_posts_db.json` | 累積貼文資料庫：以貼文 URL 去重、更新互動數，保留 30 天 |
| `summary_history.json` | 每日摘要歷史（已去識別化），供七日趨勢圖使用 |
| `.github/workflows/update-dashboard.yml` | 自動化流程 |
| `開發進度.md`、`每日開發紀錄/` | 使用者自己的開發日誌，改動功能後請一併更新 |
| `update_now.py`、`fix_188.py`、`check_html.py` | 過去一次性的修復／檢查腳本，非正式流程 |
| `reply_manager.py`、`log_reply.py`、`auto_reply.py`、`reply_config.json` | 貼文回覆系統（2026-05-10 加入，見下方說明） |

本機才有、不 commit：`data/`、`output/`、`*.xlsx`、`.env`、`reply_config.json`、`reply_history.json`、`reply_queue.json`、`chrome_profiles/`。

## 分析邏輯重點

- 情緒分析：關鍵字比對法（`analyze_sentiment()`，正面/負面詞庫），尚未用 NLP 模型。
- 關鍵字統計：使用自訂清單 `CUSTOM_KEYWORDS`（徐巧芯、陸勤部、服供站、點數、運動鞋、服裝供售站、迷彩服、迷彩鞋、魔鬼氈），不是自動斷詞。
- KPI 與圖表用最近 7 天資料計算；儀錶板貼文列表載入 7 天內互動熱度最高的 200 則。
- 互動熱度 = 按讚數 + 留言數 × 2。

## 儀錶板設計規範

- 配色固定使用薄荷綠色系：`#2C6975`（主色/深青）、`#68B2A0`（次色/薄荷）、`#CDE0C9`、`#E0ECDE`（淺底）、`#FFFFFF`。
- 必須能完全離線開啟：**不可依賴外部 JS 函式庫（如 Recharts/CDN）**，圖表一律手寫 SVG。過去用 CDN 會在 `file://` 開啟時整頁空白。
- 寫入 JS 字串前要先清掉換行並跳脫（`safe_text()`），否則換行會破壞 JS 導致整頁空白。
- 無資料時顯示「暫無資料」，不要放假資料。
- 名稱為「輿情監控系統」，介面上不出現「靠北長官2026」字樣。

## 本機執行

```powershell
pip install -r requirements.txt
$env:APIFY_API_TOKEN = "（向使用者索取，不要寫進檔案）"
python auto_daily_analysis.py
```

本機產生的 HTML 會被下一次 GitHub Actions 覆蓋；要讓線上版生效，改程式後需 push，再手動觸發 workflow。

## Git 注意事項（重要）

- GitHub Actions 機器人每天都會 commit 到 `main`，所以**本機通常落後遠端**。修改前先 `git fetch` 並確認狀態。
- 截至 2026-10-08：本機最後 commit 是 2026-04-21，而且有尚未 commit 的修改（`auto_daily_analysis.py`、`requirements.txt`、`.gitignore`、workflow、`開發進度.md`，以及新檔 `all_posts_db.json`、`auto_reply.py`、`log_reply.py` 等）。直接 `git pull` 很可能在 `sentinel_dashboard.html`、`summary_history.json`、`all_posts_db.json` 產生衝突。**處理同步前先跟使用者確認做法**，不要擅自 reset 或覆蓋；這三個資料檔一般以遠端（機器人產生的）版本為準。
- 不要 force push。

## 已知問題 / 待辦

- **儀錶板自 2026-09-26 後未更新，原因已查明**：Apify 免費額度 $5/月（週期每月 20 日～次月 19 日 UTC）用完，每月約 25 日後無法爬取。已於 2026-10-09 改為每天 25 則＋晚間 17:00–24:00 抽樣（見 `開發進度.md`），預計 10/21 恢復。新版程式需 push 並手動觸發 workflow 驗證。
- 資料一致性：確保統計數字與可搜尋貼文數完全吻合。
- 情緒分析升級為 NLP / LLM 判斷（尚未決定 API）。

## 回覆系統說明

`reply_manager.py` 會從貼文中篩出含關鍵字的貼文，產生待回覆清單；`log_reply.py` 用來記錄人工回覆。`auto_reply.py` 是用 Playwright 搭配多個匿名帳號、反偵測機制自動留言的引擎，違反 Facebook 使用條款（假帳號、規避自動化偵測），有封號風險。若使用者要擴充這部分，先說明風險，並建議改走半自動流程（人工確認後再送出）。
