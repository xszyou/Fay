#!/usr/bin/env python3
"""
Fay Logo 版本号更新脚本
用于更新 Logo 图片中的版本号文字

使用方法:
    python scripts/update_logo_version.py 3.12.4
    python scripts/update_logo_version.py --version 3.12.4
"""

import os
import sys
import argparse

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("请先安装 Pillow: pip install Pillow")
    sys.exit(1)


# Logo 文件路径（相对于项目根目录）
LOGO_PATHS = [
    "gui/static/images/Logo.png",
    "faymcp/static/images/Logo.png",
]

# 版本号区域配置（基于 330x178 的图片尺寸）
VERSION_CONFIG = {
    "area": {
        "x1": 220,   # 版本号区域左边界
        "y1": 155,   # 版本号区域上边界
        "x2": 350,   # 版本号区域右边界
        "y2": 178,   # 版本号区域下边界
    },
    "text": {
        "x": 265,    # 版本号文字 X 坐标（居中位置）
        "y": 158,    # 版本号文字 Y 坐标
        "color": (255, 255, 255, 255),  # 白色文字 RGBA
        "font_size": 14,
    },
    "background_color": (0, 0, 0, 0),  # 透明背景 RGBA
}


def get_font(size: int):
    """获取字体，优先使用系统字体"""
    font_paths = [
        # Windows
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
        # macOS
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        # Linux
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]

    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except:
                continue

    # 使用默认字体
    return ImageFont.load_default()


def update_logo_version(logo_path: str, version: str, dry_run: bool = False) -> bool:
    """
    更新单个 Logo 图片的版本号

    Args:
        logo_path: Logo 图片路径
        version: 新版本号
        dry_run: 是否只预览不保存

    Returns:
        是否成功
    """
    if not os.path.exists(logo_path):
        print(f"  [跳过] 文件不存在: {logo_path}")
        return False

    try:
        # 打开图片
        img = Image.open(logo_path)

        # 确保是 RGBA 模式
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        # 创建绘图对象
        draw = ImageDraw.Draw(img)

        # 获取配置
        area = VERSION_CONFIG["area"]
        text_cfg = VERSION_CONFIG["text"]
        bg_color = VERSION_CONFIG["background_color"]

        # 清除版本号区域（填充白色背景）
        draw.rectangle(
            [area["x1"], area["y1"], area["x2"], area["y2"]],
            fill=bg_color
        )

        # 获取字体
        font = get_font(text_cfg["font_size"])

        # 计算文字位置（居中）
        version_text = f"v{version}"
        bbox = draw.textbbox((0, 0), version_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 在区域内居中
        area_width = area["x2"] - area["x1"]
        area_height = area["y2"] - area["y1"]
        text_x = area["x1"] + (area_width - text_width) // 2
        text_y = area["y1"] + (area_height - text_height) // 2 - 2

        # 绘制新版本号
        draw.text(
            (text_x, text_y),
            version_text,
            fill=text_cfg["color"],
            font=font
        )

        if dry_run:
            print(f"  [预览] {logo_path}")
            # 可选：显示预览图片
            # img.show()
        else:
            # 保存图片
            img.save(logo_path, 'PNG')
            print(f"  [完成] {logo_path}")

        return True

    except Exception as e:
        print(f"  [错误] {logo_path}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="更新 Fay Logo 中的版本号",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/update_logo_version.py 3.12.4
    python scripts/update_logo_version.py --version 3.12.4 --dry-run
        """
    )
    parser.add_argument(
        "version",
        nargs="?",
        help="新版本号（如 3.12.4）"
    )
    parser.add_argument(
        "--version", "-v",
        dest="version_opt",
        help="新版本号（如 3.12.4）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只预览，不实际修改文件"
    )

    args = parser.parse_args()

    # 获取版本号
    version = args.version or args.version_opt
    if not version:
        parser.print_help()
        print("\n错误: 请提供版本号")
        sys.exit(1)

    print(f"更新 Logo 版本号为: v{version}")
    print("-" * 40)

    success_count = 0
    for rel_path in LOGO_PATHS:
        logo_path = os.path.join(project_root, rel_path)
        if update_logo_version(logo_path, version, args.dry_run):
            success_count += 1

    print("-" * 40)
    print(f"完成: {success_count}/{len(LOGO_PATHS)} 个文件已更新")

    if args.dry_run:
        print("\n(这是预览模式，文件未实际修改)")


if __name__ == "__main__":
    main()
