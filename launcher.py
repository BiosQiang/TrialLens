"""
launcher.py — TrialLens 启动器
打包后用户双击 TrialLens.exe 时执行此文件：
  1. 启动 Streamlit 服务（后台）
  2. 自动打开浏览器
  3. 等待用户关闭窗口
"""

import subprocess
import sys
import os
import time
import webbrowser
import threading
import socket

def find_free_port(start=8501):
    """找一个空闲端口，避免冲突"""
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) != 0:
                return port
    return start

def get_app_path():
    """获取 app.py 的路径（打包后在临时目录里）"""
    if getattr(sys, "frozen", False):
        # 打包后：PyInstaller 把文件解压到 sys._MEIPASS
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "app.py")

def main():
    port    = find_free_port()
    app_py  = get_app_path()
    url     = f"http://localhost:{port}"

    # 启动 streamlit（后台进程）
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", app_py,
            "--server.port", str(port),
            "--server.headless", "true",       # 不让 streamlit 自己开浏览器
            "--browser.gatherUsageStats", "false",
            "--server.fileWatcherType", "none", # 关闭文件监听，减少资源
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # 等 streamlit 启动（最多 10 秒）
    for _ in range(20):
        time.sleep(0.5)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) == 0:
                break

    # 打开浏览器
    webbrowser.open(url)
    print(f"TrialLens 已启动：{url}")
    print("关闭此窗口即可退出。")

    # 保持进程存活直到 Streamlit 退出
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()

if __name__ == "__main__":
    main()
