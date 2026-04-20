"""
靠北長官2026 - 每日自動下載與分析系統
功能：
1. 從 Apify 自動下載最新資料
2. 執行情緒分析
3. 產出 Excel 報告
4. 更新網頁儀錶板
"""

import os
import json
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path

# ══════════════════════════════════════════════════════════════
# ⚙️ 設定區
# ══════════════════════════════════════════════════════════════

# Apify 設定
# 優先從環境變數讀取（GitHub Actions 使用 Secrets 注入）
# 本機執行時，可將 Token 填入下方引號內作為備用
APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN", "")  # 本機測試請設定同名環境變數，或詳見設定指南.md
ACTOR_ID = "apify/facebook-groups-scraper"     # Actor ID
TASK_ID = ""  # 如果你用 Task，填這裡（選填）

# 儲存路徑
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"           # 每日原始資料
OUTPUT_DIR = BASE_DIR / "output"       # 分析報告
DASHBOARD_PATH = BASE_DIR / "sentinel_dashboard.html"  # 儀錶板路徑
HISTORY_PATH = BASE_DIR / "summary_history.json"       # 7日摘要歷史（已去識別化）

# 建立資料夾
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════════════
# 1. Apify 資料下載
# ══════════════════════════════════════════════════════════════

def get_latest_run():
    """取得最新的 Apify 執行紀錄"""
    print("\n[步驟1] 正在查詢最新執行紀錄...")
    
    # 方法1：如果你用 Task
    if TASK_ID:
        url = f"https://api.apify.com/v2/actor-tasks/{TASK_ID}/runs"
    # 方法2：直接查 Actor 的所有執行
    # 注意：Actor ID 中的 '/' 需轉換為 '~'
    else:
        actor_encoded = ACTOR_ID.replace("/", "~")
        url = f"https://api.apify.com/v2/acts/{actor_encoded}/runs"
    
    headers = {"Authorization": f"Bearer {APIFY_API_TOKEN}"}
    params = {
        "limit": 5,
        "desc": "true",  # 最新的排前面 (必須用字串 "true"，否則 requests 發送 "True" 會被 Apify 忽略導致抓到最舊的)
        "status": "SUCCEEDED"  # 只要成功的
    }
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        if not data.get("data", {}).get("items"):
            print("[X] 找不到任何成功的執行紀錄")
            return None
        
        latest = data["data"]["items"][0]
        run_id = latest["id"]
        finished_at = latest["finishedAt"]
        
        print(f"[OK] 找到最新執行：{run_id}")
        print(f"     完成時間：{finished_at}")
        return run_id
        
    except Exception as e:
        print(f"[X] 取得執行紀錄失敗：{e}")
        return None


def download_dataset(run_id):
    """下載指定執行的資料集"""
    print(f"\n[步驟2] 正在下載資料集...")
    
    url = f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items"
    headers = {"Authorization": f"Bearer {APIFY_API_TOKEN}"}
    params = {"format": "json"}
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        if not data:
            print("[!]  資料集是空的")
            return None
        
        # 儲存原始資料
        today = datetime.now().strftime("%Y%m%d")
        filename = DATA_DIR / f"dataset_{today}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[OK] 已下載 {len(data)} 則貼文")
        print(f"     儲存位置：{filename}")
        return filename
        
    except Exception as e:
        print(f"[X] 下載失敗：{e}")
        return None


# ══════════════════════════════════════════════════════════════
# 2. 情緒分析（整合之前的程式）
# ══════════════════════════════════════════════════════════════

def analyze_sentiment(text):
    """簡易情緒分析"""
    NEGATIVE = ['靠北','幹','爛','廢物','欺壓','剝削','不公','貪污','腐敗','霸凌',
                '騷擾','吸毒','外遇','偷吃','搞鬼','黑箱','不公平','壓榨','虐待',
                '亂搞','不滿','憤怒','違規','不爽','官僚','廢','爛透','恐怖',
                '可怕','詐騙','陰謀','打壓','排擠']
    POSITIVE = ['優秀','感謝','加油','讚','支持','改善','進步','榮譽','努力',
                '感恩','正向','公平','開心','期待','棒','佩服','尊重','認真',
                '幸運','友善','互助','團結']
    
    neg_score = sum(1 for w in NEGATIVE if w in text)
    pos_score = sum(1 for w in POSITIVE if w in text)
    
    if neg_score > pos_score:
        return 'negative'
    elif pos_score > neg_score:
        return 'positive'
    else:
        return 'neutral'


def extract_keywords(posts, top_n=10):
    """自定義關鍵字擷取頻率統計"""
    from collections import Counter
    
    # 📝 您可以在這裡自由新增、刪除、修改您想追蹤的「專屬關鍵字」
    CUSTOM_KEYWORDS = [
        '徐巧芯', '申訴', '督導', '陸勤部', '服供站', '長官', '點數',
        '運動鞋', '服裝供售站', '退伍', '懲處', '國防部', '演習',
        '中華民國陸軍', '志願役', '義務役', '裝備', '官兵', '福利'
    ]
    
    all_text = ' '.join(p.get('text','') or '' for p in posts)
    
    keyword_counts = Counter()
    for kw in CUSTOM_KEYWORDS:
        # 計算該關鍵字在所有貼文中出現的總次數
        count = all_text.count(kw)
        if count > 0:
            keyword_counts[kw] = count
    
    # 回傳出現次數最高的前 N 名
    return keyword_counts.most_common(top_n)

def analyze_data(json_file):
    """執行完整分析"""
    print(f"\n[步驟3] 正在分析資料...")
    
    with open(json_file, encoding='utf-8') as f:
        posts = json.load(f)
    
    # 資料清理與分析
    analyzed = []
    for p in posts:
        text = p.get('text', '') or ''
        if not text.strip():
            continue
            
        analyzed.append({
            'text': text,
            'likes': p.get('likesCount', 0) or 0,
            'comments': p.get('commentsCount', 0) or 0,
            'sentiment': analyze_sentiment(text),
            'author': p.get('user', {}).get('name', '匿名') if isinstance(p.get('user'), dict) else '匿名',
            'url': p.get('url', '') or '',  # Facebook 貼文原文連結
            'date': str(p.get('date') or p.get('createdAt') or '')[:10],
        })
    
    # 統計
    total = len(analyzed)
    neg = sum(1 for p in analyzed if p['sentiment'] == 'negative')
    pos = sum(1 for p in analyzed if p['sentiment'] == 'positive')
    neu = total - neg - pos
    
    avg_likes = sum(p['likes'] for p in analyzed) / total if total else 0
    max_likes = max((p['likes'] for p in analyzed), default=0)
    max_comments = max((p['comments'] for p in analyzed), default=0)
    avg_comments = sum(p['comments'] for p in analyzed) / total if total else 0
    
    high = sum(1 for p in analyzed if p['likes'] > 100)
    mid = sum(1 for p in analyzed if 20 < p['likes'] <= 100)
    low = sum(1 for p in analyzed if p['likes'] <= 20)
    
    # 熱門關鍵字
    keywords = extract_keywords(posts, top_n=10)
    
    # Top 100 貼文 (顯示在儀表板)
    top_posts = sorted(analyzed, key=lambda x: x['likes'] + x['comments']*2, reverse=True)[:100]
    
    stats = {
        'total': total,
        'negative': neg,
        'positive': pos,
        'neutral': neu,
        'avgLikes': round(avg_likes, 1),
        'maxLikes': max_likes,
        'maxComments': max_comments,
        'avgComments': round(avg_comments, 1),
        'high': high,
        'mid': mid,
        'low': low,
        'keywords': keywords,
        'topPosts': top_posts,
    }
    
    print(f"[OK] 分析完成")
    print(f"     總貼文：{total} 則")
    print(f"     負面：{neg} ({neg/total*100:.1f}%) | 正面：{pos} | 中性：{neu}")
    print(f"     平均按讚：{avg_likes:.1f}")
    
    return stats


# ══════════════════════════════════════════════════════════════
# 2.5 更新7日摘要歷史（已去識別化，可安全公開）
# ══════════════════════════════════════════════════════════════

def update_history(stats):
    """更新7日摩要歷史（已去識別化，公開安全）
    summary_history.json 內容：純統統計數字，無個人資料
    """
    from datetime import timezone, timedelta
    tz_tw = timezone(timedelta(hours=8))
    today = datetime.now(tz_tw).strftime("%Y-%m-%d")
    total = stats['total']
    
    # 讀取現有歷史
    if HISTORY_PATH.exists():
        try:
            with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception as e:
            print(f"[!] 讀取歷史記錄失敗：{e}，將建立新紀錄")
            history = []
    else:
        history = []
    
    # 移除今天已有的紀錄（避免重複）
    history = [h for h in history if h['date'] != today]
    
    # 新增今日摘要（僅統計數字，無言論內容、無ID、無名字）
    today_summary = {
        'date': today,
        'total': total,
        'negative': stats['negative'],
        'positive': stats['positive'],
        'neutral': stats['neutral'],
        'negRate': round(stats['negative'] / total * 100, 1) if total else 0,
        'posRate': round(stats['positive'] / total * 100, 1) if total else 0,
        'avgLikes': stats['avgLikes'],
        'maxLikes': stats['maxLikes'],
        'topKeywords': [kw for kw, _ in stats['keywords'][:5]],
    }
    history.append(today_summary)
    
    # 只保留最近7天
    history = sorted(history, key=lambda x: x['date'])[-7:]
    
    # 儲存
    with open(HISTORY_PATH, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] 7日摖要已更新（共 {len(history)} 天紀錄）")
    return history


# ══════════════════════════════════════════════════════════════
# 3. 產出 Excel 報告
# ══════════════════════════════════════════════════════════════

def generate_excel_report(stats, json_file):
    """產出 Excel 報告（需要 pandas, openpyxl）"""
    print(f"\n[步驟4] 正在產出 Excel 報告...")
    
    try:
        import pandas as pd
    except ImportError:
        print("[!] 未安裝 pandas，略過 Excel 報告")
        return None
    
    with open(json_file, encoding='utf-8') as f:
        posts = json.load(f)
    
    # 整理資料
    df_posts = []
    for p in posts:
        text = p.get('text', '') or ''
        if not text.strip():
            continue
        df_posts.append({
            '貼文內容': text[:200],
            '按讚數': p.get('likesCount', 0) or 0,
            '留言數': p.get('commentsCount', 0) or 0,
            '情緒': analyze_sentiment(text),
            '作者': p.get('user', {}).get('name', '匿名') if isinstance(p.get('user'), dict) else '匿名',
        })
    
    df = pd.DataFrame(df_posts)
    
    # 儲存
    from datetime import timezone, timedelta
    tz_tw = timezone(timedelta(hours=8))
    today = datetime.now(tz_tw).strftime("%Y%m%d")
    excel_path = OUTPUT_DIR / f"輿情報告_{today}.xlsx"
    
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        if df.empty:
            pd.DataFrame(columns=['貼文內容', '按讚數', '留言數', '情緒', '作者']).to_excel(writer, sheet_name='所有貼文', index=False)
            pd.DataFrame(columns=['貼文內容', '按讚數', '留言數', '情緒', '作者']).to_excel(writer, sheet_name='負面貼文TOP50', index=False)
        else:
            df.to_excel(writer, sheet_name='所有貼文', index=False)
            # 負面貼文
            df_neg = df[df['情緒'] == 'negative'].nlargest(50, '按讚數')
            df_neg.to_excel(writer, sheet_name='負面貼文TOP50', index=False)
        
        # 關鍵字
        kw_df = pd.DataFrame(stats['keywords'], columns=['關鍵字', '出現次數'])
        if kw_df.empty:
            kw_df = pd.DataFrame(columns=['關鍵字', '出現次數'])
        kw_df.to_excel(writer, sheet_name='熱門關鍵字', index=False)
    
    print(f"[OK] Excel 報告已儲存：{excel_path}")
    return excel_path


# ══════════════════════════════════════════════════════════════
# 4. 更新網頁儀錶板
# ══════════════════════════════════════════════════════════════

def update_dashboard(stats, history=None):
    """更新 HTML 儀錶板資料"""
    print(f"\n[步驟5] 正在更新儀錶板...")
    
    if history is None:
        if HISTORY_PATH.exists():
            try:
                with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except Exception as e:
                print(f"[!] 讀取歷史記錄失敗：{e}，將建立空紀錄")
                history = []
        else:
            history = []

    if not DASHBOARD_PATH.exists():
        print(f"[!] 找不到儀錶板檔案：{DASHBOARD_PATH}")
        return
    
    # 讀取儀錶板
    with open(DASHBOARD_PATH, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 準備新資料 (強制轉換為台灣時間 UTC+8)
    from datetime import timezone, timedelta
    tz_tw = timezone(timedelta(hours=8))
    now = datetime.now(tz_tw).strftime("%Y-%m-%d %H:%M")
    
    # 建立 JS 資料（文字中的換行符需清除，避免破壞 JS 字串語法）
    def safe_text(t, maxlen=120):
        t = t[:maxlen].replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ')
        return json.dumps(t, ensure_ascii=False)
    
    posts_js = ',\n  '.join([
        f'{{likes:{p["likes"]},comments:{p["comments"]},text:{safe_text(p["text"])},s:"{p["sentiment"]}",url:{json.dumps(p.get("url",""))},date:{json.dumps(p.get("date",""))}}}'
        for p in stats['topPosts']
    ])
    
    keywords_js = ',\n  '.join([
        f'{{w:"{kw}",n:{cnt}}}'
        for kw, cnt in stats['keywords']
    ])
    
    history_js = json.dumps(history, ensure_ascii=False, separators=(',', ':')) if history else '[]'

    new_config = f"""const C={{
  snapshot:"{now}",
  total:{stats['total']}, negative:{stats['negative']}, positive:{stats['positive']}, neutral:{stats['neutral']},
  avgLikes:{stats['avgLikes']}, maxLikes:{stats['maxLikes']}, maxComments:{stats['maxComments']}, avgComments:{stats['avgComments']},
  high:{stats['high']}, mid:{stats['mid']}, low:{stats['low']},
  alert:"⚠ 高負面聲量警報｜「加薪15000」「退伍」話題持續延燒，近期最高互動貼文均與薪資福利相關，建議重點關注。",
  tags:["#加薪15000","#職場霸凌","#裝備問題","#退伍潮","#長官行為","#海軍航指","#爆料"],
  radar:[
    {{l:"薪資待遇",v:85}},{{l:"長官行為",v:72}},{{l:"退伍意願",v:65}},
    {{l:"裝備問題",v:58}},{{l:"職場霸凌",v:42}},{{l:"爆料揭發",v:38}},
  ],
}};
const POSTS=[
  {posts_js}
];
const KW=[
  {keywords_js}
];
const HISTORY={history_js};"""
    
    # 替換資料區塊
    import re
    pattern = r'const C=\{.*?\};.*?const POSTS=\[.*?\];.*?const KW=\[.*?\];(?:\s*const HISTORY=.*?;)?'
    html_new = re.sub(pattern, new_config, html, flags=re.DOTALL)
    
    # 儲存
    with open(DASHBOARD_PATH, 'w', encoding='utf-8') as f:
        f.write(html_new)
    
    print(f"[OK] 儀錶板已更新：{DASHBOARD_PATH}")


# ══════════════════════════════════════════════════════════════
# 5. 主程式
# ══════════════════════════════════════════════════════════════

def main():
    """主程式流程"""
    print("=" * 60)
    print("  靠北長官2026 - 每日自動分析系統")
    print("=" * 60)
    from datetime import timezone, timedelta
    tz_tw = timezone(timedelta(hours=8))
    print(f"執行時間：{datetime.now(tz_tw).strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 檢查設定
        if not APIFY_API_TOKEN:
            print("\n[X] 錯誤：找不到 Apify API Token")
            print("    本機執行：請在腳本第 22 行填入 Token")
            print("    GitHub Actions：請在 Repo Settings > Secrets 新增 APIFY_API_TOKEN")
            return
        
        # 1. 下載資料
        run_id = get_latest_run()
        if not run_id:
            print("\n[X] 無法取得最新執行，程式結束")
            return
        
        json_file = download_dataset(run_id)
        if not json_file:
            print("\n[X] 無法下載資料集，程式結束")
            return
        
        # 2. 分析
        stats = analyze_data(json_file)
        
        # 3. 更新7日摖要歷史
        history = update_history(stats)
        
        # 4. 產出 Excel
        generate_excel_report(stats, json_file)
        
        # 5. 更新儀錶板（传入 7日歷史）
        update_dashboard(stats, history)
        
        print("\n" + "=" * 60)
        print("[OK] 所有任務完成！")
        print("=" * 60)
        print(f"\n資料位置：")
        print(f"   原始資料：{json_file}")
        print(f"   7日歷史：  {HISTORY_PATH}")
        print(f"   分析報告：{OUTPUT_DIR}")
        print(f"   儀錶板：  {DASHBOARD_PATH}")
    except Exception as e:
        import traceback
        print("\n[X] 執行過程中發生未預期的錯誤：")
        traceback.print_exc()
        import sys
        sys.exit(1)


if __name__ == '__main__':
    main()
