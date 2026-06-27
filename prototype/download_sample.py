"""
下載 YouTube 賣場影片作為 demo 素材
使用 yt-dlp 下載，選擇適合的解析度
"""
import subprocess
import sys
import os

# 推薦的免費賣場/超市影片（Pexels 免費素材或 YouTube CC 授權）
SAMPLE_VIDEOS = [
    {
        "name": "超市購物人流 (Pexels)",
        "url": "https://www.pexels.com/video/people-shopping-at-a-supermarket-9010438/",
        "note": "從 Pexels 手動下載，免費商用"
    },
    {
        "name": "超市走道 (Pexels)",
        "url": "https://www.pexels.com/video/a-shopping-cart-roaming-the-supermarket-5137848/",
        "note": "從 Pexels 手動下載，免費商用"
    }
]

# YouTube 搜尋建議關鍵字（找 CC 授權的）
YOUTUBE_SEARCH_TIPS = """
建議搜尋關鍵字：
1. "supermarket CCTV footage" - 超市監視器畫面
2. "grocery store security camera" - 雜貨店安全攝影機
3. "shopping mall people walking overhead" - 商場俯瞰人流
4. "retail store traffic counting" - 零售店人流計數

注意：請確認影片授權為 Creative Commons 或自行錄製
"""


def download_from_youtube(url: str, output: str = "sample.mp4"):
    """
    用 yt-dlp 下載 YouTube 影片

    Args:
        url: YouTube 影片 URL
        output: 輸出檔名
    """
    cmd = [
        "yt-dlp",
        "-f", "best[height<=720]",  # 720p 就夠用
        "-o", output,
        "--no-playlist",
        url
    ]
    print(f"下載中：{url}")
    print(f"輸出：{output}")
    subprocess.run(cmd, check=True)
    print(f"✅ 下載完成：{output} ({os.path.getsize(output)/1024/1024:.1f} MB)")


def download_from_pexels(video_id: str, output: str = "sample.mp4"):
    """
    從 Pexels 下載免費影片

    Pexels 影片可直接用 wget/curl 下載
    先到網站取得直接連結
    """
    # Pexels 需要先到網站手動取得下載連結
    print("Pexels 影片請手動下載：")
    print(f"1. 前往 https://www.pexels.com/video/{video_id}/")
    print("2. 點擊「Free Download」")
    print("3. 選擇 HD (1280x720)")
    print(f"4. 將下載的檔案重新命名為 {output}")


if __name__ == "__main__":
    print("=" * 50)
    print("AegisMart AI - 影片素材下載工具")
    print("=" * 50)

    if len(sys.argv) > 1:
        url = sys.argv[1]
        output = sys.argv[2] if len(sys.argv) > 2 else "sample.mp4"
        download_from_youtube(url, output)
    else:
        print("\n推薦素材來源：")
        for i, v in enumerate(SAMPLE_VIDEOS, 1):
            print(f"\n  {i}. {v['name']}")
            print(f"     URL: {v['url']}")
            print(f"     備註: {v['note']}")

        print(YOUTUBE_SEARCH_TIPS)
        print("\n使用方式：")
        print("  python download_sample.py <YouTube_URL> [output.mp4]")
        print("\n或直接從 Pexels 下載後放到此目錄命名為 sample.mp4")
