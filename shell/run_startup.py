import subprocess
import os
import signal

# 存储所有启动的进程
running_processes = []

def run_startup_apps():
    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    startup_file = os.path.join(script_dir, 'startup.txt')
    if not os.path.exists(startup_file):
        return
    
    # Read and process each line in the startup file
    with open(startup_file, 'r', encoding='utf-8') as f:
        for line in f:
            # Skip empty lines
            line = line.strip()
            if not line:
                continue
                
            try:
                # Split the command into program path and arguments
                parts = line.split()
                program = parts[0]
                args = parts[1:] if len(parts) > 1 else []
                
                # Create the process with no window
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                
                # Start the process
                process = subprocess.Popen(
                    [program] + args,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
                running_processes.append(process)
                print(f"Started: {line}")
                
            except Exception as e:
                print(f"Error starting {line}: {str(e)}")

def stop_all_processes():
    """停止所有启动的进程"""
    for process in running_processes:
        try:
            if process.poll() is None:  # 检查进程是否还在运行
                process.terminate()  # 尝试正常终止
                try:
                    process.wait(timeout=3)  # 等待进程终止，最多等待3秒
                except subprocess.TimeoutExpired:
                    process.kill()  # 如果进程没有及时终止，强制结束
            print(f"Stopped process with PID: {process.pid}")
        except Exception as e:
            print(f"Error stopping process: {str(e)}")
    running_processes.clear()

if __name__ == "__main__":
    run_startup_apps()
