"""
launcher.py - TrialLens launcher
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
    candidates = [
        os.path.join(base_dir, "streamlit", "__main__.py"),
        os.path.join(base_dir, "streamlit", "web", "cli.py"),
        os.path.join(base_dir, "streamlit", "cli.py"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

def log(msg):
    try:
        print(msg)
    except Exception:
        pass  # silently ignore encode errors

def main():
    base_dir = get_base_dir()
    app_py   = os.path.join(base_dir, "app.py")
    port     = find_free_port()
    url      = "http://localhost:{}".format(port)
    log_path = os.path.join(tempfile.gettempdir(), "triallens_startup.log")

    log("TrialLens starting...")
    log("base_dir : {}".format(base_dir))
    log("app.py   : {}".format(app_py))
    log("port     : {}".format(port))
    log("log file : {}".format(log_path))

    if not os.path.exists(app_py):
        log("[ERROR] app.py not found, please re-download")
        input("Press Enter to exit...")
        return

    st_script = find_streamlit_script(base_dir)
    if st_script:
        log("streamlit: {}".format(st_script))
        cmd = [
            sys.executable, st_script, "run", app_py,
            "--server.port", str(port),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
            "--server.fileWatcherType", "none",
        ]
    else:
        log("[ERROR] streamlit script not found in: {}".format(base_dir))
        input("Press Enter to exit...")
        return

    log_file = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, stdout=log_file, stderr=log_file)

    log("Waiting for startup", )
    started = False
    for _ in range(90):
        time.sleep(1)
        sys.stdout.write(".")
        sys.stdout.flush()

        ret = proc.poll()
        if ret is not None:
            log("\n[ERROR] Process exited unexpectedly (code: {})".format(ret))
            log_file.close()
            try:
                with open(log_path, encoding="utf-8") as f:
                    content = f.read()
                    if content:
                        log("\n--- error log ---")
                        log(content[-3000:])
                    else:
                        log("(log is empty)")
            except Exception:
                pass
            input("\nPress Enter to exit...")
            return

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) == 0:
                started = True
                break

    log_file.close()

    if not started:
        log("\n[ERROR] Startup timed out. Log: {}".format(log_path))
        try:
            with open(log_path, encoding="utf-8") as f:
                content = f.read()
                if content:
                    log("--- error log ---")
                    log(content[-3000:])
                else:
                    log("(log is empty)")
        except Exception:
            pass
        input("\nPress Enter to exit...")
        proc.terminate()
        return

    log("\n[OK] Started! Opening browser: {}".format(url))
    webbrowser.open(url)
    log("If browser did not open, visit: {}".format(url))
    log("Close this window to quit TrialLens.")

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()

if __name__ == "__main__":
    main()
