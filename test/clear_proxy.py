
import winreg
    
 #关闭系统代理
def disable_windows_proxy():
    settings_key = r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'
    try:
        registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        settings = winreg.OpenKey(registry, settings_key, 0, winreg.KEY_WRITE)
        
        # 设置代理启用值为0（禁用）
        winreg.SetValueEx(settings, 'ProxyEnable', 0, winreg.REG_DWORD, 0)
        
        # 清空代理服务器和代理覆盖设置
        winreg.SetValueEx(settings, 'ProxyServer', 0, winreg.REG_SZ, '')
        winreg.SetValueEx(settings, 'ProxyOverride', 0, winreg.REG_SZ, '')
        
        winreg.CloseKey(settings)
        winreg.CloseKey(registry)
    except Exception as e:
        pass


if __name__ == '__main__':
  disable_windows_proxy()

    