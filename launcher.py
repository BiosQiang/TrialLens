"""
launcher.py - TrialLens launcher
Runs streamlit in-process via bootstrap (no subprocess needed)
"""

import sys
import os
import time
import webbrowser
import socket
import tempfile
import threading

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

    print("TrialLens starting...")
    print("base_dir : {}".format(base_dir))
    print("app.py   : {}".format(app_py))
    print("port     : {}".format(port))

    if not os.path.exists(app_py):
        print("[ERROR] app.py not found")
        input("Press Enter to exit...")
        return

    # Run streamlit in a background thread via bootstrap API
    # This avoids all subprocess/executable issues
    def run_streamlit():
        try:
            from streamlit.web import bootstrap
            bootstrap.run(
                app_py,
                "streamlit run",   # command string (informational only)
                [],                # script args
                {                  # flag options
                    "server.port": port,
                    "server.headless": True,
                    "browser.gatherUsageStats": False,
                    "server.fileWatcherType": "none",
                    "global.developmentMode": False,
                }
            )
        except Exception as e:
            print("\n[ERROR] Streamlit bootstrap failed: {}".format(e))
            import traceback
            traceback.print_exc()

    t = threading.Thread(target=run_streamlit, daemon=True)
    t.start()

    # Wait for port to open (max 90s)
    print("Waiting for startup", end="", flush=True)
    started = False
    for _ in range(90):
        time.sleep(1)
        sys.stdout.write(".")
        sys.stdout.flush()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) == 0:
                started = True
                break

    if not started:
        print("\n[ERROR] Startup timed out.")
        input("Press Enter to exit...")
        return

    print("\n[OK] Started! Opening browser...")
    webbrowser.open(url)
    print("If browser did not open, visit: {}".format(url))
    print("Close this window to quit TrialLens.")

    # Keep main thread alive
    try:
        t.join()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
