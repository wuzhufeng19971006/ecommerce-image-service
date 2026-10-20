"""手动验证真实中转站接口。

该脚本会调用一次真实生图接口，可能产生费用。
先在项目根目录 .env 中填写 IMAGE_API_KEY，并设置 IMAGE_MOCK=false。

用法（在项目根目录）：
    backend\.venv\Scripts\python.exe scripts\real_api_smoke.py --yes
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings  # noqa: E402
from app.services.relay import RelayClient, RelayError  # noqa: E402


PROMPT = (
    "为服装电商生成一张简洁的米白色风衣商品主图。"
    "纯浅灰背景，正面，完整展示，柔和棚拍光，真实面料质感，"
    "电商主图构图，不要文字、水印和多余道具。"
)


async def main() -> int:
    parser = argparse.ArgumentParser(description="真实接口冒烟测试（会产生费用）")
    parser.add_argument("--yes", action="store_true", help="跳过费用确认")
    args = parser.parse_args()

    settings = Settings()
    if not settings.image_api_key.strip():
        print("未配置 IMAGE_API_KEY，请先编辑项目根目录 .env。")
        return 2
    if settings.image_mock:
        print("当前 IMAGE_MOCK=true。请先改为 false 再运行真实接口测试。")
        return 2

    print(f"接口：{settings.image_api_base}")
    print(f"模型：{settings.image_model}")
    print("即将调用 /images/generations，可能产生一次真实费用。")
    if not args.yes:
        answer = input("输入 YES 继续：").strip()
        if answer != "YES":
            print("已取消。")
            return 1

    output_dir = settings.data_dir / "smoke"
    output_dir.mkdir(parents=True, exist_ok=True)
    client = RelayClient(settings)
    try:
        result = await client.generate(PROMPT, "1024x1024", "low")
    except RelayError as exc:
        print(f"失败 [{exc.code}] {exc.message}")
        return 3

    for index, image in enumerate(result.images):
        path = output_dir / f"smoke-{index + 1}.{image.extension}"
        path.write_bytes(image.data)
        print(f"已保存：{path} ({image.width}x{image.height})")
    if result.usage:
        print(f"usage: {result.usage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
