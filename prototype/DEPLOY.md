# 🛒 AegisMart AI - 部署手冊

## 系統需求

| 項目 | 最低需求 | 建議 |
|------|---------|------|
| Python | 3.9+ | 3.11 |
| GPU | 無（CPU 可跑） | NVIDIA GPU + CUDA 12.x |
| RAM | 4 GB | 8 GB+ |
| 磁碟 | 5 GB | 10 GB |
| OS | Windows/Linux/Mac | Ubuntu 22.04 / Windows 11 |

---

## 快速部署（5 分鐘）

### Step 1：建立虛擬環境

```bash
# 進入專案目錄
cd prototype

# 建立虛擬環境
python -m venv venv

# 啟動虛擬環境
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

### Step 2：安裝依賴

**有 NVIDIA GPU 的機器（推薦）：**
```bash
# 先裝 PyTorch GPU 版
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# 再裝其他依賴
pip install ultralytics streamlit opencv-python-headless numpy Pillow yt-dlp
```

**只有 CPU 的機器：**
```bash
# 裝 PyTorch CPU 版（較小）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 再裝其他依賴
pip install ultralytics streamlit opencv-python-headless numpy Pillow yt-dlp
```

### Step 3：準備影片素材

**方法 A：從 Pexels 下載免費影片（推薦）**
1. 前往 https://www.pexels.com/video/people-shopping-at-a-supermarket-9010438/
2. 點擊「Free Download」→ 選 HD (1280x720)
3. 將檔案放到 `prototype/` 目錄，命名為 `sample.mp4`

**方法 B：從 YouTube 下載**
```bash
python download_sample.py "https://www.youtube.com/watch?v=YOUR_VIDEO_ID"
```

**方法 C：使用自己的攝影機影片**
- 任何 .mp4 檔案都可以，放到 `prototype/` 目錄即可
- 建議解析度 720p-1080p，有人走動的場景

### Step 4：啟動系統

```bash
streamlit run app.py
```

瀏覽器會自動開啟 `http://localhost:8501`

---

## 操作說明

### 控制台介面

```
┌─────────────────────────────────────────────────┐
│ 🛒 AegisMart AI — 店長即時控制台                │
├────────────────────────┬────────────────────────┤
│                        │ 🤖 Agent 推演          │
│  📹 即時監控畫面       │  ⚠️ 觸發原因           │
│  (YOLO 偵測標註)       │  方案 A [核准 ✓]      │
│                        │  方案 B [核准 ✓]      │
│  👥全場 📍生鮮 📍零食  │  方案 C [核准 ✓]      │
│                        │                        │
│                        │ 📜 系統日誌            │
├────────────────────────┴────────────────────────┤
│  [▶️ 啟動監控]          [⏹️ 停止監控]           │
└─────────────────────────────────────────────────┘
```

### 操作流程

1. **設定影片來源**：左側面板輸入影片路徑或 YouTube URL
2. **啟動監控**：點擊「▶️ 啟動監控」
3. **觀察偵測**：畫面會顯示人物框 + 區域人數
4. **等待觸發**：當人流異常時，右側 Agent 面板會推演方案
5. **審批方案**：點擊「核准 ✓」按鈕
6. **查看結果**：日誌顯示看板更新 + POS 同步 + RAG 寫入

---

## 自訂區域

編輯 `detector.py` 中的 `create_default_detector()` 函數：

```python
# 座標為比例值 (0~1)：(x1, y1, x2, y2)
# (0,0) = 左上角, (1,1) = 右下角
detector.add_zone("生鮮區", (0.0, 0.0, 0.5, 0.5))   # 左上
detector.add_zone("零食區", (0.5, 0.0, 1.0, 0.5))   # 右上
detector.add_zone("飲料區", (0.0, 0.5, 0.5, 1.0))   # 左下
detector.add_zone("結帳區", (0.5, 0.5, 1.0, 1.0))   # 右下
```

根據你的影片內容調整區域名稱和座標。

---

## 調整 Agent 觸發閾值

編輯 `agent.py` 中的 `thresholds`：

```python
self.thresholds = {
    "low_traffic": 3,       # 人數低於此值觸發
    "high_traffic": 15,     # 人數高於此值觸發
    "drop_rate": 0.5,       # 人流下降 50% 觸發
}
```

---

## Demo 錄影建議

1. 先讓影片跑 10-20 秒，展示正常監控狀態
2. 當 Agent 觸發時，暫停講解觸發原因
3. 點擊「核准」按鈕，展示完整 Human-in-the-Loop 流程
4. 切到日誌區展示「看板更新 → POS 同步 → RAG 寫入」

---

## 檔案結構

```
prototype/
├── app.py              # Streamlit 主程式（控制台 UI）
├── detector.py         # YOLOv8 人流偵測模組
├── agent.py            # 模擬 Agent 邏輯
├── download_sample.py  # 影片下載工具
├── requirements.txt    # Python 依賴
├── DEPLOY.md           # 本文件
└── sample.mp4          # 影片素材（需自行下載）
```

---

## 常見問題

**Q: YOLO 跑太慢？**
- 確認有使用 GPU（`nvidia-smi` 檢查）
- 降低影片解析度：在 app.py 中 resize frame
- 增加 `frame_skip` 值（預設為 2）

**Q: 偵測不到人？**
- 降低 confidence 閾值（左側面板可調）
- 確認影片中有人走動
- 嘗試用 yolov8s.pt（較大但更準）

**Q: Agent 沒有觸發？**
- 預設需要有「人流下降」或「區域無人」才會觸發
- 調低 `agent.py` 中的 thresholds
- 或使用人少的影片段落

**Q: YouTube 影片無法下載？**
- 確認已安裝 yt-dlp：`pip install yt-dlp`
- 部分影片有地區限制，換一部試試
- 建議直接從 Pexels 下載免費素材
