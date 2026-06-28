"""
AegisMart AI - Streamlit 控制台
左側監控畫面每 3 秒自動刷新（fragment），右側 Agent 面板只在異常時更新
"""
import streamlit as st
import cv2
import numpy as np
import time
import random
import math
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
    .log-entry { font-family: monospace; font-size: 0.8rem; color: #38bdf8; }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    if "detector" not in st.session_state:
        st.session_state.detector = create_default_detector()
    if "agent" not in st.session_state:
        st.session_state.agent = MartAgent()
    if "log" not in st.session_state:
        st.session_state.log = ["[System] AegisMart AI 已啟動，等待開始監控..."]
    if "approved" not in st.session_state:
        st.session_state.approved = []
    if "current_decisions" not in st.session_state:
        st.session_state.current_decisions = []
    if "running" not in st.session_state:
        st.session_state.running = False
    if "video_path" not in st.session_state:
        st.session_state.video_path = ""
    if "sim_tick" not in st.session_state:
        st.session_state.sim_tick = 0
    if "sim_mode" not in st.session_state:
        st.session_state.sim_mode = True
    if "sim_zone_counts" not in st.session_state:
        st.session_state.sim_zone_counts = [8, 5, 4, 6]
    if "sim_zone_smooth" not in st.session_state:
        st.session_state.sim_zone_smooth = [8.0, 5.0, 4.0, 6.0]
    if "sim_hour" not in st.session_state:
        st.session_state.sim_hour = 8.0
    if "sim_hour_start" not in st.session_state:
        st.session_state.sim_hour_start = 8.0
    if "sim_hour_end" not in st.session_state:
        st.session_state.sim_hour_end = 22.0
    if "sim_peak" not in st.session_state:
        st.session_state.sim_peak = 50
    if "sim_base" not in st.session_state:
        st.session_state.sim_base = 8
    if "sim_weights" not in st.session_state:
        st.session_state.sim_weights = [3, 2, 2, 3]


# ── 左側監控 fragment（每 3 秒自動刷新，不影響右側）──────────────────────────

@st.fragment(run_every=5)
def sim_monitor_fragment():
    """模擬監控 — 每 3 秒刷新一次，僅更新左側畫面與指標"""
    if not st.session_state.running:
        st.info("⏸️ 監控已暫停")
        return

    tick = st.session_state.sim_tick
    zones_data, total = simulate_zone_counts(tick)

    # 人流指標（監控畫面上方）
    cols = st.columns(len(zones_data) + 1)
    cols[0].metric("👥 全場人數", total)
    for i, zone in enumerate(zones_data):
        delta = zone["count"] - zone["avg"]
        cols[i + 1].metric(
            f"📍 {zone['name']}",
            f"{zone['count']} 人",
            f"{delta:+.0f} vs 平均"
        )

    # 賣場平面圖
    frame = draw_store_map(zones_data, total, tick)
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    st.image(frame_rgb, channels="RGB", use_container_width=True)

    # 推進 tick
    st.session_state.sim_tick += 1

    # 記錄初始日誌
    if tick == 0:
        add_log("[Simulation] 模擬模式啟動，各區域人流隨機漫步中...")
        add_log("[Simulation] 異常由機率自然觸發，Agent 即時偵測中")

    # 狀況解除檢查：各區域獨立判斷，回升後移出待審清單
    min_pending = st.session_state.get("min_pending_seconds", 30)
    now_t = time.time()
    still_pending, resolved_any = [], False
    for pending in st.session_state.current_decisions:
        zone_data = next((z for z in zones_data if z["name"] == pending.zone_name), None)
        if zone_data:
            count, avg = zone_data["count"], zone_data["avg"]
            recovered = avg > 0 and count > avg * 0.5
            elapsed = now_t - pending.created_at
            if recovered and elapsed >= min_pending:
                add_log(f"[Agent] ✅ {pending.zone_name} 狀況已解除，撤銷方案")
                st.session_state.agent.clear_cooldown(pending.zone_name)
                resolved_any = True
            else:
                if recovered:
                    add_log(f"[Agent] {pending.zone_name} 已回升，方案再保留 {int(min_pending - elapsed)}s")
                still_pending.append(pending)
    if resolved_any:
        st.session_state.current_decisions = still_pending

    # 異常偵測：持續評估，新發現加入清單
    new_decisions, debug_msgs = st.session_state.agent.evaluate(zones_data, total)
    for msg in debug_msgs:
        add_log(msg)
    if new_decisions:
        st.session_state.current_decisions.extend(new_decisions)
        for d in new_decisions:
            add_log(f"[Agent] ⚠️ {d.trigger_reason}")
            add_log(f"[Agent] 已推演 {len(d.promotions)} 套方案，等待店長審批...")

    if resolved_any or new_decisions:
        st.rerun()


# ── 模擬資料產生 ─────────────────────────────────────────────────────────────

def _store_wave(hour: float, peak: int, base: int) -> int:
    """全場人流波形：早上小高峰(10)、午餐(12.5)、傍晚大高峰(18.5)"""
    def bump(h, center, width, height):
        if abs(h - center) >= width:
            return 0.0
        return height * max(0.0, math.cos(math.pi * (h - center) / width))

    level = (bump(hour, 10.0, 2.5, 0.55) +
             bump(hour, 12.5, 1.5, 0.75) +
             bump(hour, 18.5, 2.5, 1.00))
    level = max(0.0, min(1.0, level))
    return max(base, int(base + (peak - base) * level))


def simulate_zone_counts(tick: int) -> tuple[list[dict], int]:
    """波形驅動 + 人流守恆分配模型"""
    names   = ["生鮮區", "烘焙區", "乳品區", "熟食區"]
    hour    = st.session_state.sim_hour
    peak    = st.session_state.sim_peak
    base    = st.session_state.sim_base
    weights = st.session_state.sim_weights

    # 全場離峰門檻：低於 base × 1.5 時 Agent 不觸發區域方案
    st.session_state.agent.min_store_total = int(base * 1.5)

    # Layer 1：全場總人數（波形 + 微小雜訊）
    store_total = _store_wave(hour, peak, base)
    store_total = max(base, store_total + random.randint(-2, 2))

    # Layer 2：依吸引力權重分配到各區域
    total_w = sum(weights)
    targets = [store_total * w / total_w for w in weights]

    # 指數平滑（alpha=0.35）讓人數緩慢趨近目標，不瞬間跳變
    prev_smooth = st.session_state.sim_zone_smooth
    alpha = 0.35
    new_smooth = [
        alpha * t + (1 - alpha) * p + random.gauss(0, max(1.5, p * 0.08))
        for t, p in zip(targets, prev_smooth)
    ]
    new_counts = [max(0, round(s)) for s in new_smooth]

    st.session_state.sim_zone_smooth = new_smooth
    st.session_state.sim_zone_counts = new_counts

    # 時間推進：每 tick（5 秒）= 模擬 2 分鐘，到結束時段後回繞
    hour_start = st.session_state.get("sim_hour_start", 8.0)
    hour_end = st.session_state.get("sim_hour_end", 22.0)
    next_hour = hour + 2 / 60
    st.session_state.sim_hour = hour_start if next_hour >= hour_end else next_hour

    # 各區域的「歷史平均」= 以中段時間（尖峰 60%）為基準
    mid_total = base + (peak - base) * 0.6
    avgs = [mid_total * w / total_w for w in weights]

    zones_data = [
        {"name": names[i], "count": new_counts[i], "avg": round(avgs[i], 1)}
        for i in range(4)
    ]
    return zones_data, sum(new_counts)


ZONE_LABELS_EN = {
    "生鮮區": "Fresh",
    "烘焙區": "Bakery",
    "乳品區": "Dairy",
    "熟食區": "Deli",
}


def draw_store_map(zones_data: list[dict], total: int, tick: int) -> np.ndarray:
    """繪製賣場平面示意圖"""
    W, H = 720, 480
    canvas = np.zeros((H, W, 3), dtype=np.uint8)
    canvas[:] = (15, 23, 42)

    layout = [
        (0,   0,   360, 240),
        (360, 0,   720, 240),
        (0,   240, 360, 480),
        (360, 240, 720, 480),
    ]
    colors_normal = [(34, 197, 94), (59, 130, 246), (234, 179, 8), (168, 85, 247)]

    for i, zone in enumerate(zones_data):
        x1, y1, x2, y2 = layout[i]
        count, avg = zone["count"], zone["avg"]
        is_alert = count < avg * 0.5 and avg > 0

        base_c = (239, 68, 68) if is_alert else colors_normal[i]
        alpha = max(0.15, min(0.7, count / 12.0))
        fill = tuple(int(c * alpha) for c in base_c)

        cv2.rectangle(canvas, (x1+2, y1+2), (x2-2, y2-2), fill, -1)
        border = (239, 68, 68) if is_alert else (51, 65, 85)
        cv2.rectangle(canvas, (x1+2, y1+2), (x2-2, y2-2), border, 3 if is_alert else 1)

        cx, cy = (x1+x2)//2, (y1+y2)//2
        label = ZONE_LABELS_EN.get(zone["name"], zone["name"])
        (tw, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
        cv2.putText(canvas, label, (cx-tw//2, cy-20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (248, 250, 252), 2)

        count_str = f"{count} ppl"
        (cw, _), _ = cv2.getTextSize(count_str, cv2.FONT_HERSHEY_SIMPLEX, 1.2, 3)
        cv2.putText(canvas, count_str, (cx-cw//2, cy+20),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (239, 68, 68) if is_alert else (248, 250, 252), 3)

        if is_alert:
            cv2.putText(canvas, "! LOW TRAFFIC", (cx-70, cy+58),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (239, 68, 68), 2)

    hour = st.session_state.get("sim_hour", 10.0)
    hh, mm = int(hour), int((hour % 1) * 60)
    info = f"  T+{tick:03d}s  |  模擬時段 {hh:02d}:{mm:02d}  |  Total: {total} ppl"
    cv2.rectangle(canvas, (0, H-30), (W, H), (30, 41, 59), -1)
    cv2.putText(canvas, info, (10, H-10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (148, 163, 184), 1)
    return canvas


# ── 右側 Agent 面板（主流程渲染，只在整頁 rerun 時更新）────────────────────

def render_agent_panel():
    decisions = st.session_state.current_decisions

    if not decisions:
        st.info("✅ 各區域正常，持續監控中...")
        return

    for decision in decisions:
        if decision.severity == "critical":
            st.error(f"🚨 **{decision.trigger_reason}**")
        else:
            st.warning(f"⚠️ **{decision.trigger_reason}**")

        col_ts, col_skip = st.columns([3, 1])
        col_ts.markdown(f"*觸發時間：{decision.timestamp}*")
        if col_skip.button("略過 ✕", key=f"skip_{decision.zone_name}_{decision.timestamp}",
                           use_container_width=True):
            skip_decision(decision)
            st.rerun()

        for i, promo in enumerate(decision.promotions):
            col_info, col_btn = st.columns([4, 1])
            with col_info:
                badge = {"推薦": "🟢", "低風險": "🔵", "中風險": "🟡", "激進": "🔴", "創新": "🟣"}.get(promo.risk_level, "⚪")
                st.markdown(f"**{badge} {promo.name}** ({promo.risk_level})")
                st.markdown(f"_{promo.description}_")
                st.caption(f"預期效果：{promo.expected_effect}")
            with col_btn:
                if st.button("核准 ✓", key=f"approve_{decision.zone_name}_{decision.timestamp}_{i}",
                             use_container_width=True):
                    approve_promotion(promo, decision)
                    st.rerun()

        st.markdown("---")


def skip_decision(decision):
    add_log(f"[Human-in-the-Loop] ⏭️ 店長略過 {decision.zone_name} 方案，本次不採取行動")
    st.session_state.current_decisions = [
        d for d in st.session_state.current_decisions
        if not (d.zone_name == decision.zone_name and d.timestamp == decision.timestamp)
    ]


def approve_promotion(promo, decision):
    zone_name = decision.zone_name
    add_log(f"[Human-in-the-Loop] ✅ 店長核准「{promo.name}」@ {zone_name}")
    add_log(f"[MCP] 📺 {zone_name} 電子看板已更新")
    add_log(f"[MCP] 🏷️ POS 折扣碼同步完成")
    add_log(f"[RAG] 💾 寫入策略記憶庫")
    st.session_state.approved.append(f"{promo.name} @ {zone_name}")
    st.session_state.current_decisions = [
        d for d in st.session_state.current_decisions
        if not (d.zone_name == zone_name and d.timestamp == decision.timestamp)
    ]


def render_log():
    log_text = "\n".join(st.session_state.log[-15:])
    st.code(log_text, language="")


def add_log(msg: str):
    if st.session_state.get("sim_mode") and st.session_state.get("running"):
        h = st.session_state.get("sim_hour", 0.0)
        timestamp = f"{int(h):02d}:{int((h % 1) * 60):02d}"
    else:
        timestamp = time.strftime("%H:%M:%S")
    st.session_state.log.append(f"[{timestamp}] {msg}")


# ── 主程式 ───────────────────────────────────────────────────────────────────

def main():
    init_session_state()

    st.markdown("""
<div style="
    position: fixed;
    top: 0; left: 0; right: 0;
    height: 3.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 999999;
    pointer-events: none;
">
    <span style="
        color: #f8fafc;
        font-size: 1.05rem;
        font-weight: 700;
        letter-spacing: 0.01em;
        text-shadow: 0 1px 3px rgba(0,0,0,0.5);
    ">🛒 AegisMart AI — 店長控制台</span>
</div>
""", unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown("### ⚙️ 系統設定")
        sim_mode = st.toggle("🎭 模擬模式（無需影片）", value=st.session_state.sim_mode)
        st.session_state.sim_mode = sim_mode

        if not sim_mode:
            video_source = st.text_input(
                "影片來源",
                value=st.session_state.video_path or "sample.mp4",
            )
            st.session_state.video_path = video_source
            confidence = st.slider("偵測信心閾值", 0.2, 0.8, 0.4, 0.05)
            st.session_state.detector.confidence = confidence
        else:
            st.markdown("#### 🕐 時段設定")
            tc1, tc2 = st.columns(2)
            sim_hour_start = tc1.slider(
                "起始", 6.0, 21.0,
                value=st.session_state.sim_hour_start, step=0.5,
                format="%.1f h"
            )
            sim_hour_end = tc2.slider(
                "結束", 7.0, 24.0,
                value=st.session_state.sim_hour_end, step=0.5,
                format="%.1f h"
            )
            if sim_hour_end <= sim_hour_start:
                sim_hour_end = sim_hour_start + 1.0
            st.session_state.sim_hour_start = sim_hour_start
            st.session_state.sim_hour_end = sim_hour_end

            def _fmt_h(h):
                return f"{int(h):02d}:{int((h % 1) * 60):02d}"
            st.caption(f"營業時段 {_fmt_h(sim_hour_start)} – {_fmt_h(sim_hour_end)}")
            c1, c2 = st.columns(2)
            sim_peak = c1.number_input("尖峰人數", 20, 120, st.session_state.sim_peak, 5)
            sim_base = c2.number_input("離峰人數", 3, 30, st.session_state.sim_base, 1)

            st.markdown("#### 🏪 區域吸引力")
            st.caption("數值越高，該區域分配到的人數越多")
            names = ["生鮮區", "烘焙區", "乳品區", "熟食區"]
            weights = []
            for i, n in enumerate(names):
                w = st.slider(n, 1, 10, st.session_state.sim_weights[i], key=f"w_{i}")
                weights.append(w)

            st.session_state.sim_peak = sim_peak
            st.session_state.sim_base = sim_base
            st.session_state.sim_weights = weights

            if st.button("🔄 套用並重設模擬", use_container_width=True):
                st.session_state.sim_hour = sim_hour_start
                total_w = sum(weights)
                init_total = _store_wave(sim_hour_start, sim_peak, sim_base)
                st.session_state.sim_zone_smooth = [init_total * w / total_w for w in weights]
                st.session_state.sim_zone_counts = [max(0, round(s)) for s in st.session_state.sim_zone_smooth]

        st.divider()
        st.markdown("### 🎛️ 監控控制")
        if st.button("▶️ 啟動監控", use_container_width=True, type="primary",
                     disabled=st.session_state.running):
            st.session_state.running = True
            st.session_state.sim_tick = 0
            st.session_state.sim_hour = st.session_state.sim_hour_start
            st.session_state.log = ["[System] AegisMart AI 已啟動，賣場視覺監控中..."]
            st.session_state.current_decisions = []
            st.session_state.agent.reset_cooldowns()
            # 波形模型初始化：依起始時段的實際波形值設定，避免從 mid 起跳
            weights = st.session_state.sim_weights
            total_w = sum(weights)
            init_total = _store_wave(st.session_state.sim_hour_start,
                                     st.session_state.sim_peak,
                                     st.session_state.sim_base)
            init_smooth = [init_total * w / total_w for w in weights]
            st.session_state.sim_zone_smooth = init_smooth
            st.session_state.sim_zone_counts = [max(0, round(s)) for s in init_smooth]
        if st.button("⏹️ 停止監控", use_container_width=True,
                     disabled=not st.session_state.running):
            st.session_state.running = False

        st.divider()
        st.markdown("### 📊 靈敏度調控")
        min_pending = st.slider(
            "方案最短停留（秒）", 10, 120,
            value=st.session_state.get("min_pending_seconds", 30), step=5,
            help="異常方案出現後，至少保留幾秒才允許自動解除"
        )
        st.session_state.min_pending_seconds = min_pending

        cooldown = st.slider(
            "核准後冷卻（秒）", 10, 180,
            value=st.session_state.agent.cooldown_seconds, step=5,
            help="核准方案後，同區域幾秒內不再重複觸發"
        )
        st.session_state.agent.cooldown_seconds = cooldown

        drop_pct = st.slider(
            "人流驟降門檻（%）", 10, 60,
            value=int(st.session_state.agent.thresholds["drop_rate"] * 100), step=5,
            help="人流跌至均值的幾 % 以下才觸發驟降方案"
        )
        st.session_state.agent.thresholds["drop_rate"] = drop_pct / 100

        high_mult = st.slider(
            "人流爆滿門檻（倍）", 1.2, 3.0,
            value=float(st.session_state.agent.thresholds["high_multiplier"]), step=0.1,
            help="人流超過均值幾倍才觸發爆滿方案（預設 1.8×）"
        )
        st.session_state.agent.thresholds["high_multiplier"] = high_mult

        st.divider()
        st.markdown("### 📋 審批記錄")
        for item in st.session_state.approved[-5:]:
            st.success(f"✅ {item}")

    # 主要版面
    col_video, col_panel = st.columns([3, 2])

    with col_video:
        st.markdown("### 📹 即時監控畫面")
        if st.session_state.sim_mode:
            sim_monitor_fragment()
        else:
            st.warning("影片模式請提供 sample.mp4")

    with col_panel:
        st.markdown("### 🤖 Agent 推演")
        render_agent_panel()
        st.markdown("### 📜 系統日誌")
        render_log()


if __name__ == "__main__":
    main()
