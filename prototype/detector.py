"""
AegisMart AI - YOLOv8 人流偵測模組
讀取影片（本地或 YouTube），偵測人數，輸出區域人流統計
"""
import cv2
import numpy as np
from ultralytics import YOLO
from dataclasses import dataclass, field
from collections import deque
from pathlib import Path
import time


@dataclass
class ZoneStats:
    """單一區域的人流統計"""
    name: str
    bbox: tuple  # (x1, y1, x2, y2) 比例座標 0~1
    count: int = 0
    history: deque = field(default_factory=lambda: deque(maxlen=60))
    avg_count: float = 0.0

    def update(self, count: int):
        self.count = count
        self.history.append(count)
        self.avg_count = sum(self.history) / len(self.history)


class PeopleDetector:
    """YOLOv8 人流偵測器"""

    def __init__(self, model_size: str = "yolov8n.pt", confidence: float = 0.4):
        """
        Args:
            model_size: YOLO 模型大小 (yolov8n/s/m/l/x)
            confidence: 偵測信心閾值
        """
        self.model = YOLO(model_size)
        self.confidence = confidence
        self.zones = []
        self.frame_count = 0
        self.fps = 0
        self._last_time = time.time()

    def add_zone(self, name: str, bbox: tuple):
        """新增監控區域 (比例座標 0~1)"""
        self.zones.append(ZoneStats(name=name, bbox=bbox))

    def detect_frame(self, frame: np.ndarray) -> dict:
        """
        偵測單一幀的人流

        Returns:
            {
                "total_count": int,
                "zones": [{"name": str, "count": int, "avg": float}],
                "annotated_frame": np.ndarray,
                "detections": [(x1,y1,x2,y2,conf)]
            }
        """
        h, w = frame.shape[:2]

        # YOLO 偵測 (class 0 = person)
        results = self.model(frame, conf=self.confidence, classes=[0], verbose=False)
        detections = []

        if results and results[0].boxes:
            for box in results[0].boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0])
                detections.append((int(x1), int(y1), int(x2), int(y2), conf))

        total_count = len(detections)

        # 計算各區域人數
        zone_results = []
        for zone in self.zones:
            zx1 = int(zone.bbox[0] * w)
            zy1 = int(zone.bbox[1] * h)
            zx2 = int(zone.bbox[2] * w)
            zy2 = int(zone.bbox[3] * h)

            count = 0
            for (dx1, dy1, dx2, dy2, _) in detections:
                # 人的中心點是否在區域內
                cx = (dx1 + dx2) // 2
                cy = (dy1 + dy2) // 2
                if zx1 <= cx <= zx2 and zy1 <= cy <= zy2:
                    count += 1

            zone.update(count)
            zone_results.append({
                "name": zone.name,
                "count": zone.count,
                "avg": round(zone.avg_count, 1)
            })

        # 繪製標註
        annotated = self._draw_annotations(frame, detections, h, w)

        # 計算 FPS
        self.frame_count += 1
        if self.frame_count % 10 == 0:
            now = time.time()
            self.fps = 10 / (now - self._last_time)
            self._last_time = now

        return {
            "total_count": total_count,
            "zones": zone_results,
            "annotated_frame": annotated,
            "detections": detections,
            "fps": round(self.fps, 1)
        }

    def _draw_annotations(self, frame: np.ndarray, detections: list, h: int, w: int) -> np.ndarray:
        """在畫面上繪製偵測結果"""
        annotated = frame.copy()

        # 畫區域框
        for zone in self.zones:
            zx1 = int(zone.bbox[0] * w)
            zy1 = int(zone.bbox[1] * h)
            zx2 = int(zone.bbox[2] * w)
            zy2 = int(zone.bbox[3] * h)
            color = (0, 255, 0) if zone.count > 0 else (100, 100, 100)
            cv2.rectangle(annotated, (zx1, zy1), (zx2, zy2), color, 2)
            label = f"{zone.name}: {zone.count}"
            cv2.putText(annotated, label, (zx1, zy1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        # 畫人物框
        for (x1, y1, x2, y2, conf) in detections:
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 200, 255), 2)
            cv2.putText(annotated, f"{conf:.0%}", (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 1)

        # FPS
        cv2.putText(annotated, f"FPS: {self.fps:.1f} | Total: {len(detections)}",
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        return annotated


def create_default_detector() -> PeopleDetector:
    """建立預設偵測器，含賣場常見區域劃分"""
    model_path = str(Path(__file__).parent / "yolov8n.pt")
    detector = PeopleDetector(model_size=model_path, confidence=0.4)

    # 預設區域（可依實際影片調整）
    detector.add_zone("生鮮區", (0.0, 0.0, 0.5, 0.5))
    detector.add_zone("烘焙區", (0.5, 0.0, 1.0, 0.5))
    detector.add_zone("乳品區", (0.0, 0.5, 0.5, 1.0))
    detector.add_zone("熟食區", (0.5, 0.5, 1.0, 1.0))

    return detector
