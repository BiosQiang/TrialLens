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
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def find_streamlit_script(base_dir):
    """在打包目录里找到 streamlit 的真实入口脚本"""
    candidates = [
        os.path.join(base_dir, "streamlit", "__main__.py"),
        os.path.join(base_dir, "streamlit", "web", "cli.py"),
        os.path.join(base_dir, "streamlit", "cli.py"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def main():
    base_dir  = get_base_dir()
    app_py    = os.path.join(base_dir, "app.py")
    port      = find_free_port()
    url       = f"http://localhost:{port}"
    log_path  = os.path.join(tempfile.gettempdir(), "triallens_startup.log")

    print(f"TrialLens 正在启动...")
    print(f"base_dir : {base_dir}")
    print(f"app.py   : {app_py}")
    print(f"端口     : {port}")
    print(f"日志     : {log_path}")

    if not os.path.exists(app_py):
        print(f"\n❌ 找不到 app.py，请重新下载")
        input("按回车键退出...")
        return

    # 找 streamlit 入口
    st_script = find_streamlit_script(base_dir)
    if st_script:
        print(f"streamlit: {st_script}")
        cmd = [sys.executable, st_script, "run", app_py,
               "--server.port", str(port),
               "--server.headless", "true",
               "--browser.gatherUsageStats", "false",
               "--server.fileWatcherType", "none"]
    else:
        # fallback：直接用 streamlit 模块内的 run
        print("streamlit: 使用内置模块方式启动")
        # 在同进程里用 streamlit 的 bootstrap 启动
        cmd = None

    log_file = open(log_path, "w", encoding="utf-8")

    if cmd:
        proc = subprocess.Popen(cmd, stdout=log_file, stderr=log_file)
    else:
        # 直接在当前进程里跑 streamlit（最后的备选方案）
        log_file.write("使用 bootstrap 模式启动\n")
        log_file.flush()

        def run_streamlit():
            from streamlit.web import bootstrap
            flag_options = {
                "server.port": port,
                "server.headless": True,
                "browser.gatherUsageStats": False,
                "server.fileWatcherType": "none",
            }
            bootstrap.run(app_py, "", [], flag_options)

        import threading
        t = threading.Thread(target=run_streamlit, daemon=True)
        t.start()

        # 模拟一个假的 proc 对象
        class FakeProc:
            def poll(self): return None
            def wait(self): t.join()
            def terminate(self): pass
        proc = FakeProc()

    # 等待启动，最多 90 秒
    print("等待启动", end="", flush=True)
    started = False
    for _ in range(90):
        time.sleep(1)
        print(".", end="", flush=True)

        if hasattr(proc, 'poll') and callable(proc.poll):
            ret = proc.poll()
            if ret is not None:
                print(f"\n❌ 进程意外退出（退出码: {ret}）")
                log_file.close()
                try:
                    with open(log_path, encoding="utf-8") as f:
                        content = f.read()
                        if content:
                            print("\n--- 错误日志 ---")
                            print(content[-3000:])
                        else:
                            print("\n（日志为空）")
                except Exception:
                    pass
                input("\n按回车键退出...")
                return

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) == 0:
                started = True
                break

    log_file.close()

    if not started:
        print(f"\n❌ 启动超时，请查看日志: {log_path}")
        try:
            with open(log_path, encoding="utf-8") as f:
                content = f.read()
                if content:
                    print("\n--- 错误日志 ---")
                    print(content[-3000:])
                else:
                    print("\n（日志为空，streamlit 可能未能正确找到）")
        except Exception:
            pass
        input("\n按回车键退出...")
        try:
            proc.terminate()
        except Exception:
            pass
        return

    print(f"\n✅ 启动成功！正在打开浏览器: {url}")
    webbrowser.open(url)
    print(f"如未自动打开，请手动访问: {url}")
    print("关闭此窗口即可退出。")

    try:
        proc.wait()
    except KeyboardInterrupt:
        try:
            proc.terminate()
        except Exception:
            pass

if __name__ == "__main__":
    main()
