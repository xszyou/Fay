#!/usr/bin/env python3
"""
声音和形象模型管理工具
交互式命令行界面，用于管理智创宝数字人的声音和形象
"""

import os
import sys

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from ai_module.voice_manager import VoiceManager
from ai_module.avatar_manager import AvatarManager
from utils import config_util as cfg

# 尝试加载配置
try:
    cfg.load_config()
except:
    pass


def clear_screen():
    """清屏"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header(title):
    """打印标题"""
    print("\n" + "=" * 50)
    print(f"  {title}")
    print("=" * 50)


def print_menu(options):
    """打印菜单选项"""
    for key, desc in options.items():
        print(f"  [{key}] {desc}")
    print()


def input_with_default(prompt, default=None):
    """带默认值的输入"""
    if default:
        user_input = input(f"{prompt} [{default}]: ").strip()
        return user_input if user_input else default
    return input(f"{prompt}: ").strip()


def confirm(prompt):
    """确认操作"""
    response = input(f"{prompt} (y/n): ").strip().lower()
    return response in ['y', 'yes', '是']


class ModelManagerCLI:
    """模型管理命令行界面"""

    def __init__(self):
        self.voice_manager = VoiceManager()
        self.avatar_manager = AvatarManager()

    def run(self):
        """运行主程序"""
        while True:
            clear_screen()
            print_header("智创宝数字人模型管理工具")
            print_menu({
                '1': '声音管理',
                '2': '形象管理',
                '3': '查看当前配置',
                '0': '退出'
            })

            choice = input("请选择操作: ").strip()

            if choice == '1':
                self.voice_menu()
            elif choice == '2':
                self.avatar_menu()
            elif choice == '3':
                self.show_config()
            elif choice == '0':
                print("\n再见！")
                break
            else:
                print("无效选择，请重试")
                input("按回车继续...")

    # ==================== 声音管理 ====================

    def voice_menu(self):
        """声音管理菜单"""
        while True:
            clear_screen()
            print_header("声音管理")
            print_menu({
                '1': '添加新声音（输入已有模型ID）',
                '2': '试听声音',
                '3': '查看已保存的声音',
                '4': '删除声音',
                '5': '设为当前使用',
                '0': '返回上级'
            })

            choice = input("请选择操作: ").strip()

            if choice == '1':
                self.add_voice()
            elif choice == '2':
                self.preview_voice()
            elif choice == '3':
                self.list_voices()
            elif choice == '4':
                self.delete_voice()
            elif choice == '5':
                self.set_active_voice()
            elif choice == '0':
                break
            else:
                print("无效选择")
                input("按回车继续...")

    def add_voice(self):
        """添加声音"""
        clear_screen()
        print_header("添加新声音")

        print("\n请输入声音模型信息：")
        model_id = input_with_default("模型ID (modelId)")
        if not model_id:
            print("模型ID不能为空")
            input("按回车继续...")
            return

        name = input_with_default("声音名称", f"声音_{model_id[:8]}")

        # 可选：试听
        print("\n是否现在试听该声音？")
        if confirm("试听"):
            test_text = input_with_default("试听文本", "你好，欢迎使用智创宝数字人服务。")
            print("\n正在生成试听音频，请稍候...")

            preview_url = self.voice_manager.preview_voice(model_id, test_text)
            if preview_url:
                print(f"\n试听音频已生成：{preview_url}")
                print("请在浏览器中打开上述链接试听")

                if confirm("\n满意这个声音，保存"):
                    if self.voice_manager.save_voice(model_id, name, preview_url):
                        print(f"\n声音 [{name}] 保存成功！")
                    else:
                        print("\n保存失败")
                else:
                    print("\n已放弃保存")
            else:
                print("\n试听音频生成失败")
                if confirm("仍然保存这个声音"):
                    if self.voice_manager.save_voice(model_id, name):
                        print(f"\n声音 [{name}] 保存成功！")
        else:
            # 直接保存
            if self.voice_manager.save_voice(model_id, name):
                print(f"\n声音 [{name}] 保存成功！")
            else:
                print("\n保存失败")

        input("\n按回车继续...")

    def preview_voice(self):
        """试听声音"""
        clear_screen()
        print_header("试听声音")

        voices = self.voice_manager.list_voices()
        if not voices:
            print("\n暂无已保存的声音")
            input("按回车继续...")
            return

        print("\n已保存的声音：")
        for i, voice in enumerate(voices, 1):
            print(f"  [{i}] {voice['name']} (ID: {voice['model_id']})")

        print(f"  [0] 输入新的模型ID")

        choice = input("\n选择要试听的声音: ").strip()

        model_id = None
        if choice == '0':
            model_id = input("输入模型ID: ").strip()
        elif choice.isdigit() and 0 < int(choice) <= len(voices):
            model_id = voices[int(choice) - 1]['model_id']

        if not model_id:
            print("无效选择")
            input("按回车继续...")
            return

        test_text = input_with_default("试听文本", "你好，这是一段测试语音。")
        print("\n正在生成试听音频，请稍候...")

        preview_url = self.voice_manager.preview_voice(model_id, test_text)
        if preview_url:
            print(f"\n试听音频：{preview_url}")
        else:
            print("\n生成失败")

        input("\n按回车继续...")

    def list_voices(self):
        """列出声音"""
        clear_screen()
        print_header("已保存的声音")

        voices = self.voice_manager.list_voices()
        if not voices:
            print("\n暂无已保存的声音")
        else:
            print(f"\n共 {len(voices)} 个声音：\n")
            for i, voice in enumerate(voices, 1):
                print(f"  {i}. {voice['name']}")
                print(f"     模型ID: {voice['model_id']}")
                print(f"     状态: {voice.get('status', 'unknown')}")
                print(f"     创建时间: {voice.get('created_at', 'unknown')}")
                if voice.get('preview_url'):
                    print(f"     试听: {voice['preview_url']}")
                print()

        input("按回车继续...")

    def delete_voice(self):
        """删除声音"""
        clear_screen()
        print_header("删除声音")

        voices = self.voice_manager.list_voices()
        if not voices:
            print("\n暂无已保存的声音")
            input("按回车继续...")
            return

        print("\n已保存的声音：")
        for i, voice in enumerate(voices, 1):
            print(f"  [{i}] {voice['name']} (ID: {voice['model_id']})")

        choice = input("\n选择要删除的声音 (输入序号): ").strip()

        if choice.isdigit() and 0 < int(choice) <= len(voices):
            voice = voices[int(choice) - 1]
            if confirm(f"确定删除 [{voice['name']}]"):
                if self.voice_manager.delete_voice(voice['model_id']):
                    print("\n删除成功！")
                else:
                    print("\n删除失败")
        else:
            print("无效选择")

        input("\n按回车继续...")

    def set_active_voice(self):
        """设置当前使用的声音"""
        clear_screen()
        print_header("设置当前声音")

        voices = self.voice_manager.list_voices()
        if not voices:
            print("\n暂无已保存的声音")
            input("按回车继续...")
            return

        print("\n已保存的声音：")
        for i, voice in enumerate(voices, 1):
            print(f"  [{i}] {voice['name']} (ID: {voice['model_id']})")

        choice = input("\n选择要使用的声音: ").strip()

        if choice.isdigit() and 0 < int(choice) <= len(voices):
            voice = voices[int(choice) - 1]
            print(f"\n已选择: {voice['name']}")
            print(f"模型ID: {voice['model_id']}")
            print("\n请将以下配置更新到 system.conf：")
            print(f"zcb_model_id={voice['model_id']}")
        else:
            print("无效选择")

        input("\n按回车继续...")

    # ==================== 形象管理 ====================

    def avatar_menu(self):
        """形象管理菜单"""
        while True:
            clear_screen()
            print_header("形象管理")
            print_menu({
                '1': '添加新形象',
                '2': '预览形象（生成测试视频）',
                '3': '查看已保存的形象',
                '4': '删除形象',
                '5': '设为当前使用',
                '0': '返回上级'
            })

            choice = input("请选择操作: ").strip()

            if choice == '1':
                self.add_avatar()
            elif choice == '2':
                self.preview_avatar()
            elif choice == '3':
                self.list_avatars()
            elif choice == '4':
                self.delete_avatar()
            elif choice == '5':
                self.set_active_avatar()
            elif choice == '0':
                break
            else:
                print("无效选择")
                input("按回车继续...")

    def add_avatar(self):
        """添加形象"""
        clear_screen()
        print_header("添加新形象")

        print("\n请输入形象视频信息：")
        video_url = input_with_default("形象视频URL")
        if not video_url:
            print("视频URL不能为空")
            input("按回车继续...")
            return

        name = input_with_default("形象名称", "我的数字人")
        thumbnail = input_with_default("缩略图URL（可选，直接回车跳过）", "")

        # 可选：预览
        print("\n是否生成预览视频？（需要提供音频）")
        if confirm("生成预览"):
            audio_url = input_with_default("音频URL（用于生成预览视频）")
            if audio_url:
                print("\n正在生成预览视频，请稍候（可能需要几分钟）...")
                preview_url = self.avatar_manager.preview_avatar(video_url, audio_url)
                if preview_url:
                    print(f"\n预览视频已生成：{preview_url}")

                    if confirm("\n满意这个形象，保存"):
                        if self.avatar_manager.save_avatar(video_url, name, thumbnail, preview_url):
                            print(f"\n形象 [{name}] 保存成功！")
                        else:
                            print("\n保存失败")
                    else:
                        print("\n已放弃保存")
                else:
                    print("\n预览视频生成失败")
                    if confirm("仍然保存这个形象"):
                        if self.avatar_manager.save_avatar(video_url, name, thumbnail):
                            print(f"\n形象 [{name}] 保存成功！")
            else:
                print("未提供音频，跳过预览")
                if self.avatar_manager.save_avatar(video_url, name, thumbnail):
                    print(f"\n形象 [{name}] 保存成功！")
        else:
            # 直接保存
            if self.avatar_manager.save_avatar(video_url, name, thumbnail):
                print(f"\n形象 [{name}] 保存成功！")
            else:
                print("\n保存失败")

        input("\n按回车继续...")

    def preview_avatar(self):
        """预览形象"""
        clear_screen()
        print_header("预览形象")

        avatars = self.avatar_manager.list_avatars()
        if not avatars:
            print("\n暂无已保存的形象，请先添加")
            input("按回车继续...")
            return

        print("\n已保存的形象：")
        for i, avatar in enumerate(avatars, 1):
            print(f"  [{i}] {avatar['name']}")

        choice = input("\n选择要预览的形象: ").strip()

        if choice.isdigit() and 0 < int(choice) <= len(avatars):
            avatar = avatars[int(choice) - 1]
            audio_url = input_with_default("音频URL（用于生成预览视频）")

            if audio_url:
                print("\n正在生成预览视频，请稍候（可能需要几分钟）...")
                preview_url = self.avatar_manager.preview_avatar(avatar['video_url'], audio_url)
                if preview_url:
                    print(f"\n预览视频：{preview_url}")
                else:
                    print("\n生成失败")
            else:
                print("未提供音频")
        else:
            print("无效选择")

        input("\n按回车继续...")

    def list_avatars(self):
        """列出形象"""
        clear_screen()
        print_header("已保存的形象")

        avatars = self.avatar_manager.list_avatars()
        if not avatars:
            print("\n暂无已保存的形象")
        else:
            print(f"\n共 {len(avatars)} 个形象：\n")
            for i, avatar in enumerate(avatars, 1):
                print(f"  {i}. {avatar['name']}")
                print(f"     ID: {avatar.get('avatar_id', 'N/A')}")
                print(f"     视频: {avatar['video_url']}")
                print(f"     状态: {avatar.get('status', 'unknown')}")
                print(f"     创建时间: {avatar.get('created_at', 'unknown')}")
                if avatar.get('thumbnail_url'):
                    print(f"     缩略图: {avatar['thumbnail_url']}")
                if avatar.get('preview_url'):
                    print(f"     预览: {avatar['preview_url']}")
                print()

        input("按回车继续...")

    def delete_avatar(self):
        """删除形象"""
        clear_screen()
        print_header("删除形象")

        avatars = self.avatar_manager.list_avatars()
        if not avatars:
            print("\n暂无已保存的形象")
            input("按回车继续...")
            return

        print("\n已保存的形象：")
        for i, avatar in enumerate(avatars, 1):
            print(f"  [{i}] {avatar['name']}")

        choice = input("\n选择要删除的形象 (输入序号): ").strip()

        if choice.isdigit() and 0 < int(choice) <= len(avatars):
            avatar = avatars[int(choice) - 1]
            if confirm(f"确定删除 [{avatar['name']}]"):
                if self.avatar_manager.delete_avatar(avatar['video_url']):
                    print("\n删除成功！")
                else:
                    print("\n删除失败")
        else:
            print("无效选择")

        input("\n按回车继续...")

    def set_active_avatar(self):
        """设置当前使用的形象"""
        clear_screen()
        print_header("设置当前形象")

        avatars = self.avatar_manager.list_avatars()
        if not avatars:
            print("\n暂无已保存的形象")
            input("按回车继续...")
            return

        print("\n已保存的形象：")
        for i, avatar in enumerate(avatars, 1):
            print(f"  [{i}] {avatar['name']}")

        choice = input("\n选择要使用的形象: ").strip()

        if choice.isdigit() and 0 < int(choice) <= len(avatars):
            avatar = avatars[int(choice) - 1]
            print(f"\n已选择: {avatar['name']}")
            print(f"视频URL: {avatar['video_url']}")
            print("\n请将以下配置更新到 system.conf：")
            print(f"zcb_video_url={avatar['video_url']}")
        else:
            print("无效选择")

        input("\n按回车继续...")

    # ==================== 配置查看 ====================

    def show_config(self):
        """显示当前配置"""
        clear_screen()
        print_header("当前配置")

        print("\n智创宝数字人配置：")
        print(f"  API Token: {getattr(cfg, 'zcb_api_token', 'N/A')[:20]}..." if getattr(cfg, 'zcb_api_token', '') else "  API Token: 未配置")
        print(f"  声音模型ID: {getattr(cfg, 'zcb_model_id', '未配置') or '未配置'}")
        print(f"  形象视频URL: {getattr(cfg, 'zcb_video_url', '未配置') or '未配置'}")

        print("\n已保存的资源统计：")
        voices = self.voice_manager.list_voices()
        avatars = self.avatar_manager.list_avatars()
        print(f"  声音模型: {len(voices)} 个")
        print(f"  数字人形象: {len(avatars)} 个")

        input("\n按回车继续...")


def main():
    """主函数"""
    try:
        cli = ModelManagerCLI()
        cli.run()
    except KeyboardInterrupt:
        print("\n\n已退出")
    except Exception as e:
        print(f"\n发生错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
