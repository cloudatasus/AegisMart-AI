"""
AegisMart AI - Streamlit 控制台（Demo 模式）
呼叫 agent.py 的 MartAgent 進行判斷
"""
import streamlit as st
import numpy as np
import time
import random
import cv2
from agent import MartAgent

st.set_page_config(page_title="🛒 AegisMart AI - 店長控制台", page_icon="🛒", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0f172a; color: #f8fafc; }
    div[data-testid="stMetric"] { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 0.8rem; }
    div[data-testid="stMetric"] label { color: #94a3b8 !important; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #f8fafc !important; }
    .stButton>button { background-color: #10b981 !important; color: white !important; font-weight: 700 !important; border: none !important; }
    .stButton>button:hover { background-color: #059669 !important; }
</style>
""", unsafe_allow_html=True)

# === Session State ===
if "agent" not in st.session_state:
    st.session_state.agent = MartAgent()
if "log" not in st.session_state:
    st.session_state.log = ["[System] AegisMart AI 已啟動，Agent 就緒"]
if "approved" not in st.session_state:
    st.session_state.approved = []
if "decision" not in st.session_state:
    st.session_state.decision = None
if "zones" not in st.session_state:
    st.session_state.zones = {"生鮮區": 10, "零食區": 7, "飲料區": 6, "結帳區": 5}
if "history" not in st.session_state:
    st.session_state.history = {"生鮮區": [10]*5, "零食區": [7]*5, "飲料區": [6]*5, "結帳區": [5]*5}


def refresh_zones():
    """更新人流數字（隨機波動 ±3）"""
    for zone in st.session_state.zones:
        current = st.session_state.zones[zone]
        change = random.randint(-3, 3)
        st.session_state.zones[zone] = max(0, current + change)
        st.session_state.history[zone].append(st.session_state.zones[zone])
        if len(st.session_state.history[zone]) > 10:
            st.session_state.history[zone].pop(0)


def call_agent():
    """呼叫 Agent 評估當前人流"""
    zone_stats = []
    for name in st.session_state.zones:
        count = st.session_state.zones[name]
        hist = st.session_state.history[name]
        avg = sum(hist) / len(hist) if hist else count
        zone_stats.append({"name": name, "count": count, "avg": round(avg, 1)})
    total = sum(z["count"] for z in zone_stats)
    return st.session_state.agent.evaluate(zone_stats, total)


# === Header ===
st.markdown("# 🛒 AegisMart AI — 店長即時控制台")
st.caption("Edge AI 視覺感知 → Agent 策略推演 → 店長審批 → 看板更新")

# === 即時人流（最上面）===
zones = st.session_state.zones
total = sum(zones.values())

col_r1, col_r2 = st.columns([6, 1])
with col_r2:
    if st.button("🔄 刷新", help="模擬時間流動，更新人流"):
        refresh_zones()
        # 每次刷新都重新評估
        result = call_agent()
        if result:
            st.session_state.decision = result
            ts = time.strftime("%H:%M:%S")
            st.session_state.log.append(f"[{ts}] 🚨 Agent：{result.trigger_reason}")
        else:
            st.session_state.decision = None
        st.rerun()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("👥 全場", f"{total} 人", "FPS: 24.1")
zone_names = list(zones.keys())
for i, name in enumerate(zone_names):
    count = zones[name]
    hist = st.session_state.history[name]
    avg = sum(hist) / len(hist) if hist else count
    delta = count - avg
    [m2, m3, m4, m5][i].metric(f"📍 {name}", f"{count} 人", f"{delta:+.0f} vs avg")

st.divider()

# === 主區域 ===
col_video, col_panel = st.columns([3, 2])

with col_video:
    st.markdown("### 📹 即時監控畫面")
    img = np.zeros((380, 680, 3), dtype=np.uint8)
    img[:] = (26, 23, 15)
    rects = [
        ("生鮮區", (10, 10, 335, 185)),
        ("零食區", (345, 10, 670, 185)),
        ("飲料區", (10, 195, 335, 370)),
        ("結帳區", (345, 195, 670, 370)),
    ]
    for name, (x1, y1, x2, y2) in rects:
        count = zones[name]
        color = (0, 80, 255) if count <= 2 else (0, 200, 100) if count < 12 else (0, 255, 255)
        cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
        cv2.putText(img, f"{name}: {count}", (x1+5, y1+22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        rng = random.Random(hash(name))
        for j in range(min(count, 10)):
            px = rng.randint(x1+15, x2-15)
            py = rng.randint(y1+30, y2-15)
            cv2.circle(img, (px, py), 6, (0, 200, 255), -1)
    cv2.putText(img, f"YOLOv8n | GPU | {time.strftime('%H:%M:%S')}", (10, 378),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
    st.image(img, channels="BGR", use_container_width=True)

with col_panel:
    st.markdown("### 🤖 Agent 推演")

    decision = st.session_state.decision

    if decision is not None:
        # 有觸發
        severity_style = "background:#2d0a0a;border:2px solid #ef4444;" if decision.severity == "critical" else "background:#2d2400;border:2px solid #f59e0b;"
        severity_color = "#fca5a5" if decision.severity == "critical" else "#fbbf24"
        icon = "🚨" if decision.severity == "critical" else "⚠️"

        st.markdown(
            f'<div style="{severity_style}border-radius:10px;padding:1rem;">'
            f'<span style="color:{severity_color};font-size:1.05rem;font-weight:700;">'
            f'{icon} {decision.trigger_reason}</span></div>',
            unsafe_allow_html=True
        )
        st.markdown("")

        badge_map = {"推薦": "推薦 🟢", "低風險": "低風險 🔵", "中風險": "中風險 🟡", "激進": "激進 🔴", "創新": "創新 🟣"}

        for i, promo in enumerate(decision.promotions):
            badge = badge_map.get(promo.risk_level, promo.risk_level)
            st.markdown(
                f'<div style="background:#1e293b;border:1px solid #475569;border-radius:10px;padding:1rem;margin:0.4rem 0;">'
                f'<span style="color:#f8fafc;font-weight:700;">{badge} {promo.name}</span><br>'
                f'<span style="color:#cbd5e1;font-size:0.85rem;">{promo.description}</span><br>'
                f'<span style="color:#10b981;font-size:0.8rem;">📈 {promo.expected_effect}</span></div>',
                unsafe_allow_html=True
            )
            if st.button(f"核准「{promo.name}」✓", key=f"approve_{i}"):
                ts = time.strftime("%H:%M:%S")
                st.session_state.log.append(f"[{ts}] ✅ 核准「{promo.name}」@ {decision.zone_name}")
                st.session_state.log.append(f"[{ts}] 📺 {decision.zone_name}看板已更新")
                st.session_state.log.append(f"[{ts}] 💾 RAG 記憶寫入")
                st.session_state.approved.append(f"{promo.name} @ {decision.zone_name}")
                st.session_state.decision = None
                st.rerun()
    else:
        # 正常
        st.markdown(
            '<div style="background:#1e293b;border:1px solid #334155;border-radius:12px;padding:1.5rem;text-align:center;">'
            '<div style="font-size:2rem;">✅</div>'
            '<div style="color:#10b981;font-size:1.1rem;font-weight:700;">各區域正常</div>'
            '<div style="color:#94a3b8;font-size:0.85rem;margin-top:0.3rem;">持續監控中，人流異常時 Agent 自動啟動</div>'
            '</div>',
            unsafe_allow_html=True
        )

    # 歷史核准
    if st.session_state.approved:
        st.markdown("##### 📋 歷史核准")
        for item in st.session_state.approved[-5:]:
            st.markdown(
                f'<div style="background:#0f2920;border:1px solid #065f46;border-radius:6px;'
                f'padding:0.4rem 0.8rem;margin:0.2rem 0;color:#6ee7b7;font-size:0.82rem;">✓ {item}</div>',
                unsafe_allow_html=True
            )

# === 系統日誌（折疊） ===
with st.expander("📜 系統日誌", expanded=False):
    st.code("\n".join(st.session_state.log[-12:]), language="")
