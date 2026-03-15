"""
launcher.py — TrialLens 启动器
"""

import subprocess
import sys
import os
import time
import webbrowser
import socket
import tempfile

def find_free_port(start=8501):
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) != 0:
                return port
    return start

def get_base_dir():
    """打包后返回 _MEIPASS，开发时返回脚本所在目录"""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def main():
    base_dir = get_base_dir()
    app_py   = os.path.join(base_dir, "app.py")
    port     = find_free_port()
    url      = f"http://localhost:{port}"

    # 把输出写到临时日志文件，方便排查
    log_path = os.path.join(tempfile.gettempdir(), "triallens_startup.log")
    log_file = open(log_path, "w", encoding="utf-8")

    print(f"TrialLens 正在启动...")
    print(f"app.py 路径: {app_py}")
    print(f"端口: {port}")
    print(f"启动日志: {log_path}")

    if not os.path.exists(app_py):
        print(f"\n❌ 找不到 app.py，请重新下载完整版本")
        input("按回车键退出...")
        return

    cmd = [
        sys.executable, "-m", "streamlit", "run", app_py,
        "--server.port", str(port),
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
        "--server.fileWatcherType", "none",
    ]

    proc = subprocess.Popen(cmd, stdout=log_file, stderr=log_file)

    # 最多等 60 秒
    print("等待启动", end="", flush=True)
    started = False
    for i in range(60):
        time.sleep(1)
        print(".", end="", flush=True)

        # 进程意外退出
        if proc.poll() is not None:
            print(f"\n❌ 启动失败（退出码: {proc.returncode}）")
            log_file.close()
            try:
                with open(log_path, encoding="utf-8") as f:
                    print("\n--- 错误日志 ---")
                    print(f.read()[-3000:])
            except Exception:
                pass
            input("\n按回车键退出...")
            return

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) == 0:
                started = True
                break

    if not started:
        print(f"\n❌ 启动超时")
        log_file.close()
        try:
            with open(log_path, encoding="utf-8") as f:
                print("\n--- 错误日志 ---")
                print(f.read()[-3000:])
        except Exception:
            pass
        input("\n按回车键退出...")
        proc.terminate()
        return

    print(f"\n✅ 启动成功！正在打开浏览器...")
    webbrowser.open(url)
    print(f"如未自动打开，请手动访问: {url}")
    print("关闭此窗口即可退出。")

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
    finally:
        log_file.close()

if __name__ == "__main__":
    main()
