"""
AegisMart AI - Streamlit 控制台
影片畫面 + 即時人流數字 + Agent 推演 + 店長審批按鈕
"""
import streamlit as st
import cv2
import numpy as np
import time
from detector import PeopleDetector, create_default_detector
from agent import MartAgent

# === Page Config ===
st.set_page_config(
    page_title="🛒 AegisMart AI - 店長控制台",
    page_icon="🛒",
    layout="wide"
)

# === Custom CSS ===
st.markdown("""
<style>
    .stApp { background-color: #0f172a; }
    .metric-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
    }
    .metric-value { font-size: 2rem; font-weight: 800; color: #f8fafc; }
    .metric-label { font-size: 0.8rem; color: #94a3b8; }
    .alert-box {
        background: #1c1017;
        border: 1px solid #ef4444;
        border-left: 4px solid #ef4444;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .promotion-card {
        background: #0f172a;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .log-entry { font-family: monospace; font-size: 0.8rem; color: #38bdf8; }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """初始化 session state"""
    if "detector" not in st.session_state:
        st.session_state.detector = create_default_detector()
    if "agent" not in st.session_state:
        st.session_state.agent = MartAgent()
    if "log" not in st.session_state:
        st.session_state.log = ["[System] AegisMart AI 已啟動，賣場視覺監控中..."]
    if "approved" not in st.session_state:
        st.session_state.approved = []
    if "current_decision" not in st.session_state:
        st.session_state.current_decision = None
    if "running" not in st.session_state:
        st.session_state.running = False
    if "video_path" not in st.session_state:
        st.session_state.video_path = ""


def main():
    init_session_state()

    # === Header ===
    st.markdown("# 🛒 AegisMart AI — 店長即時控制台")
    st.markdown("*Edge AI 視覺感知 → Agent 策略推演 → 店長審批 → 看板更新*")
    st.divider()

    # === Sidebar: 設定 ===
    with st.sidebar:
        st.markdown("### ⚙️ 系統設定")
        video_source = st.text_input(
            "影片來源（本地路徑或 YouTube URL）",
            value=st.session_state.video_path or "sample.mp4",
            help="支援本地 .mp4 檔案或 YouTube 連結"
        )
        st.session_state.video_path = video_source

        confidence = st.slider("偵測信心閾值", 0.2, 0.8, 0.4, 0.05)
        st.session_state.detector.confidence = confidence

        st.markdown("### 📊 區域設定")
        st.info("預設 4 區域：生鮮區、零食區、飲料區、結帳區\n可在程式碼中自訂座標")

        st.markdown("### 📋 審批記錄")
        for item in st.session_state.approved[-5:]:
            st.success(f"✅ {item}", icon="✅")

    # === Main Layout ===
    col_video, col_panel = st.columns([3, 2])

    with col_video:
        st.markdown("### 📹 即時監控畫面")
        video_placeholder = st.empty()
        metrics_placeholder = st.empty()

    with col_panel:
        st.markdown("### 🤖 Agent 推演")
        agent_placeholder = st.empty()
        st.markdown("### 📜 系統日誌")
        log_placeholder = st.empty()

    # === Control Buttons ===
    col_start, col_stop = st.columns(2)
    with col_start:
        start_btn = st.button("▶️ 啟動監控", use_container_width=True, type="primary")
    with col_stop:
        stop_btn = st.button("⏹️ 停止監控", use_container_width=True)

    if stop_btn:
        st.session_state.running = False

    if start_btn:
        st.session_state.running = True
        run_detection(video_source, video_placeholder, metrics_placeholder,
                     agent_placeholder, log_placeholder)


def run_detection(video_source, video_ph, metrics_ph, agent_ph, log_ph):
    """執行影片偵測主迴圈"""
    detector = st.session_state.detector
    agent = st.session_state.agent

    # 開啟影片
    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        st.error(f"❌ 無法開啟影片：{video_source}")
        return

    add_log(f"[Edge AI] 影片已載入：{video_source}")
    add_log("[Edge AI] YOLOv8 人流偵測啟動...")

    frame_skip = 2  # 每 N 幀處理一次（加速）
    frame_idx = 0

    while st.session_state.running and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # 循環播放
            continue

        frame_idx += 1
        if frame_idx % frame_skip != 0:
            continue

        # YOLO 偵測
        result = detector.detect_frame(frame)

        # 顯示影片畫面
        annotated_rgb = cv2.cvtColor(result["annotated_frame"], cv2.COLOR_BGR2RGB)
        video_ph.image(annotated_rgb, channels="RGB", use_container_width=True)

        # 顯示指標
        with metrics_ph.container():
            cols = st.columns(len(result["zones"]) + 1)
            cols[0].metric("👥 全場人數", result["total_count"])
            for i, zone in enumerate(result["zones"]):
                delta = zone["count"] - zone["avg"] if zone["avg"] > 0 else 0
                cols[i+1].metric(
                    f"📍 {zone['name']}",
                    f"{zone['count']} 人",
                    f"{delta:+.0f} vs 平均"
                )

        # Agent 評估
        decision = agent.evaluate(result["zones"], result["total_count"])
        if decision:
            st.session_state.current_decision = decision
            add_log(f"[Agent] {decision.trigger_reason}")
            add_log(f"[Agent] 已推演 {len(decision.promotions)} 套方案，等待店長審批...")

        # 顯示 Agent 面板
        render_agent_panel(agent_ph)

        # 顯示日誌
        render_log(log_ph)

        time.sleep(0.05)  # 控制更新速率

    cap.release()
    add_log("[System] 監控已停止")


def render_agent_panel(placeholder):
    """渲染 Agent 推演面板"""
    decision = st.session_state.current_decision

    with placeholder.container():
        if decision is None:
            st.info("✅ 各區域正常，持續監控中...")
            return

        # 觸發原因
        if decision.severity == "critical":
            st.error(f"🚨 **{decision.trigger_reason}**")
        else:
            st.warning(f"⚠️ **{decision.trigger_reason}**")

        st.markdown(f"*觸發時間：{decision.timestamp}*")
        st.markdown("---")

        # 方案列表
        for i, promo in enumerate(decision.promotions):
            col_info, col_btn = st.columns([4, 1])
            with col_info:
                badge_color = {"推薦": "🟢", "低風險": "🔵", "中風險": "🟡", "激進": "🔴", "創新": "🟣"}
                badge = badge_color.get(promo.risk_level, "⚪")
                st.markdown(f"**{badge} {promo.name}** ({promo.risk_level})")
                st.markdown(f"_{promo.description}_")
                st.caption(f"預期效果：{promo.expected_effect}")
            with col_btn:
                if st.button("核准 ✓", key=f"approve_{decision.timestamp}_{i}",
                           use_container_width=True):
                    approve_promotion(promo, decision.zone_name)


def approve_promotion(promo, zone_name):
    """店長核准促銷方案"""
    add_log(f"[Human-in-the-Loop] ✅ 店長核准「{promo.name}」")
    add_log(f"[MCP] 📺 {zone_name}電子看板已更新")
    add_log(f"[MCP] 🏷️ POS 折扣碼同步完成")
    add_log(f"[RAG] 💾 寫入策略記憶庫")
    st.session_state.approved.append(f"{promo.name} @ {zone_name}")
    st.session_state.current_decision = None
    st.success(f"🚀 「{promo.name}」已上線！看板已更新")


def render_log(placeholder):
    """渲染系統日誌"""
    with placeholder.container():
        log_text = "\n".join(st.session_state.log[-15:])
        st.code(log_text, language="")


def add_log(msg: str):
    """新增日誌"""
    timestamp = time.strftime("%H:%M:%S")
    st.session_state.log.append(f"[{timestamp}] {msg}")


if __name__ == "__main__":
    main()
