"""
AegisMart AI - 模擬 Agent 邏輯
根據人流數據觸發促銷方案推薦（模擬版，不需 LLM API）
"""
import time
from dataclasses import dataclass


@dataclass
class Promotion:
    """促銷方案"""
    name: str
    description: str
    discount: str
    risk_level: str  # 推薦/低風險/中風險/激進/創新
    expected_effect: str


@dataclass
class AgentDecision:
    """Agent 推演結果"""
    trigger_reason: str
    zone_name: str
    severity: str  # normal / warning / critical
    promotions: list  # List[Promotion]
    timestamp: str


class MartAgent:
    """賣場動態定價 Agent（模擬版）"""

    def __init__(self):
        self.history = []
        self.thresholds = {
            "low_traffic": 2,       # 人數低於此值觸發（≤2 人）
            "high_traffic": 15,     # 人數高於此值觸發
            "drop_rate": 0.35,      # 人流下降 65% 才觸發
        }
        self.cooldown_seconds = 30  # 同區域核准後冷卻秒數（可由外部調整）
        self.cooldown = {}  # 各區域冷卻時間

    def clear_cooldown(self, zone_name: str):
        """手動清除特定區域的冷卻（用於狀況自動解除時）"""
        self.cooldown.pop(zone_name, None)

    def reset_cooldowns(self):
        """清除所有冷卻（用於模擬重新啟動時）"""
        self.cooldown.clear()

    def evaluate(self, zone_stats: list, total_count: int) -> tuple:
        """
        評估當前人流狀態，決定是否觸發促銷推薦

        Returns:
            (AgentDecision | None, list[str])  — 決策 + debug 訊息列表
        """
        now = time.time()
        debug_msgs = []

        for zone in zone_stats:
            name = zone["name"]
            count = zone["count"]
            avg = zone["avg"]

            # 冷卻中不重複觸發
            if name in self.cooldown and now - self.cooldown[name] < self.cooldown_seconds:
                remaining = int(self.cooldown_seconds - (now - self.cooldown[name]))
                debug_msgs.append(f"[Agent] {name} 冷卻中，剩餘 {remaining}s，跳過評估")
                continue

            # 情境 1：區域無人
            if count == 0 and avg >= 2:
                decision = self._generate_dead_zone_plan(name)
                self.cooldown[name] = now
                self.history.append(decision)
                return decision, debug_msgs

            # 情境 2：人流驟降（低於平均的門檻，且人數 <= 2）
            if avg > 3 and count <= self.thresholds["low_traffic"] and count <= avg * self.thresholds["drop_rate"]:
                decision = self._generate_low_traffic_plan(name, count, avg)
                self.cooldown[name] = now
                self.history.append(decision)
                return decision, debug_msgs

            # 情境 3：人流爆滿
            if count >= self.thresholds["high_traffic"]:
                decision = self._generate_peak_plan(name, count)
                self.cooldown[name] = now
                self.history.append(decision)
                return decision, debug_msgs

        return None, debug_msgs

    def _generate_low_traffic_plan(self, zone: str, count: int, avg: float) -> AgentDecision:
        """人流驟降 → 即期品促銷（依區域客製化文案）"""
        drop_pct = int((avg - count) / avg * 100)

        zone_copy = {
            "烘焙區": ("今日現烤出清", "麵包出爐快搶！今日現烤限時 65 折，過時不候", "麵包當日消化率 +90%，零報廢"),
            "乳品區": ("冷藏即期特價", "牛奶／優格今日效期特惠，買 2 送 1，新鮮帶回家", "乳品報廢率從 18% 降至 3%"),
        }
        promo1_name, promo1_desc, promo1_effect = zone_copy.get(
            zone, ("限時 6 折看板", f"{zone}看板「⏰ 限時 6 折！即期品新鮮出清」+ 鄰近走道導引", "預估消化率 85%，報廢率降至 6%")
        )

        return AgentDecision(
            trigger_reason=f"⚠️ {zone} 人流驟降：目前 {count} 人（平均 {avg:.0f} 人，下降 {drop_pct}%）",
            zone_name=zone,
            severity="critical",
            timestamp=time.strftime("%H:%M:%S"),
            promotions=[
                Promotion(
                    name=promo1_name,
                    description=promo1_desc,
                    discount="65折" if zone == "烘焙區" else ("買2送1" if zone == "乳品區" else "6折"),
                    risk_level="推薦",
                    expected_effect=promo1_effect
                ),
                Promotion(
                    name="買一送一",
                    description=f"{zone}看板「買一送一倒數中」，搭配聲音提示吸引注意",
                    discount="買一送一",
                    risk_level="激進",
                    expected_effect="消化率 92%，毛利較低但報廢歸零"
                ),
                Promotion(
                    name="$99 驚喜福袋",
                    description="看板推「$99 隨機 3 樣福袋」，製造趣味性與社群分享動機",
                    discount="組合價",
                    risk_level="創新",
                    expected_effect="社群分享率 +40%，吸引年輕客群"
                ),
            ]
        )

    def _generate_dead_zone_plan(self, zone: str) -> AgentDecision:
        """區域無人 → 導引策略"""
        return AgentDecision(
            trigger_reason=f"👻 {zone} 連續無人！需要人流導引",
            zone_name=zone,
            severity="warning",
            timestamp=time.strftime("%H:%M:%S"),
            promotions=[
                Promotion(
                    name="鄰近看板導引",
                    description=f"熱區看板跳出「→ {zone} 限時 5 折」箭頭導引",
                    discount="5折",
                    risk_level="推薦",
                    expected_effect="導引率 25%，走道人流 +300%"
                ),
                Promotion(
                    name="食譜影片看板",
                    description=f"{zone}看板播放食譜短影片「今晚做這道→ 食材就在旁邊」",
                    discount="無折扣",
                    risk_level="創新",
                    expected_effect="連帶購買率 35%，客單價 +$120"
                ),
                Promotion(
                    name="限時閃購",
                    description=f"{zone}看板「⚡ 15 分鐘內 5 折」製造急迫感",
                    discount="5折限時",
                    risk_level="中風險",
                    expected_effect="清掉 60% 滯銷品，衝動購買率高"
                ),
            ]
        )

    def _generate_peak_plan(self, zone: str, count: int) -> AgentDecision:
        """人流爆滿 → 分流策略"""
        return AgentDecision(
            trigger_reason=f"🔥 {zone} 人流爆滿：{count} 人！需要分流",
            zone_name=zone,
            severity="warning",
            timestamp=time.strftime("%H:%M:%S"),
            promotions=[
                Promotion(
                    name="冷門區導引分流",
                    description="看板推「沙拉吧免排隊 85 折」引導至隔壁冷清區域",
                    discount="85折",
                    risk_level="推薦",
                    expected_effect="分流 30%，整體滿意度提升"
                ),
                Promotion(
                    name="加價購推薦",
                    description=f"{zone}看板推「+$10 升級套餐」提升客單價",
                    discount="加價購",
                    risk_level="低風險",
                    expected_effect="客單價 +15%，毛利提升"
                ),
                Promotion(
                    name="預購快取",
                    description="看板推 QR code 預購，30 分鐘後取餐免排隊",
                    discount="無折扣",
                    risk_level="創新",
                    expected_effect="排隊 -50%，延伸下午時段營收"
                ),
            ]
        )

    def get_history(self) -> list:
        """取得歷史推演記錄"""
        return self.history[-10:]  # 最近 10 筆
