"""
launcher.py - TrialLens launcher
"""

import sys
import os
import time
import webbrowser
import socket
import tempfile
import threading
import traceback

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

def main():
    base_dir = get_base_dir()
    app_py   = os.path.join(base_dir, "app.py")
    port     = find_free_port()
    url      = "http://localhost:{}".format(port)
    log_path = os.path.join(tempfile.gettempdir(), "triallens_error.log")

    print("TrialLens starting...")
    print("base_dir : {}".format(base_dir))
    print("app.py   : {}".format(app_py))
    print("port     : {}".format(port))
    print("error log: {}".format(log_path))

    if not os.path.exists(app_py):
        print("[ERROR] app.py not found")
        input("Press Enter to exit...")
        return

    error_holder = []

    def run_streamlit():
        try:
            # 重定向 stdout/stderr 到日志文件，捕获 streamlit 的所有输出
            log_f = open(log_path, "w", encoding="utf-8")
            old_stdout = sys.stdout
            old_stderr = sys.stderr

            class Tee:
                def __init__(self, *targets): self.targets = targets
                def write(self, s):
                    for t in self.targets:
                        try: t.write(s)
                        except: pass
                def flush(self):
                    for t in self.targets:
                        try: t.flush()
                        except: pass

            sys.stdout = Tee(old_stdout, log_f)
            sys.stderr = Tee(old_stderr, log_f)

            from streamlit.web import bootstrap
            bootstrap.run(
                app_py,
                "streamlit run",
                [],
                {
                    "server.port": port,
                    "server.headless": True,
                    "browser.gatherUsageStats": False,
                    "server.fileWatcherType": "none",
                    "global.developmentMode": False,
                }
            )
        except Exception as e:
            err = traceback.format_exc()
            error_holder.append(err)
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write("\n[EXCEPTION]\n" + err)
            except: pass
        finally:
            try:
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                log_f.close()
            except: pass

    t = threading.Thread(target=run_streamlit, daemon=True)
    t.start()

    print("Waiting for startup", end="", flush=True)
    started = False
    for _ in range(90):
        time.sleep(1)
        sys.stdout.write(".")
        sys.stdout.flush()

        # 如果线程里有错误，提前退出
        if error_holder:
            print("\n[ERROR] Streamlit failed to start.")
            print("--- error log ({}) ---".format(log_path))
            try:
                with open(log_path, encoding="utf-8") as f:
                    print(f.read()[-4000:])
            except: pass
            input("\nPress Enter to exit...")
            return

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) == 0:
                started = True
                break

    if not started:
        print("\n[ERROR] Startup timed out.")
        print("--- error log ({}) ---".format(log_path))
        try:
            with open(log_path, encoding="utf-8") as f:
                content = f.read()
                print(content[-4000:] if content else "(empty)")
        except: pass
        input("\nPress Enter to exit...")
        return

    print("\n[OK] Started! Opening browser: {}".format(url))
    webbrowser.open(url)
    print("If browser did not open, visit: {}".format(url))
    print("Close this window to quit TrialLens.")

    try:
        t.join()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
