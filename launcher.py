"""
launcher.py - TrialLens launcher
"""

import sys
import os
import time
import webbrowser
import socket
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

def open_browser_when_ready(port, url):
    for _ in range(90):
        time.sleep(1)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) == 0:
                webbrowser.open(url)
                print("\n[OK] Browser opened: {}".format(url))
                print("Close this window to quit TrialLens.")
                return
    print("\n[ERROR] Timed out. Visit manually: {}".format(url))

def main():
    base_dir = get_base_dir()
    app_py   = os.path.join(base_dir, "app.py")
    port     = find_free_port()
    url      = "http://localhost:{}".format(port)

    print("TrialLens starting...")
    print("port: {}".format(port))

    if not os.path.exists(app_py):
        print("[ERROR] app.py not found")
        input("Press Enter to exit...")
        return

    # Set config before importing streamlit
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"]   = "none"

    from streamlit import config as st_config
    st_config.set_option("global.developmentMode", False)
    st_config.set_option("server.port", port)
    st_config.set_option("server.headless", True)
    st_config.set_option("browser.gatherUsageStats", False)
    st_config.set_option("server.fileWatcherType", "none")

    static_dir = os.path.join(base_dir, "streamlit", "static")
    print("static exists: {}".format(os.path.isdir(static_dir)))

    # Open browser in background thread (streamlit must own main thread)
    t = threading.Thread(target=open_browser_when_ready, args=(port, url), daemon=True)
    t.start()

    # Run streamlit on main thread
    # Second arg is is_hello (bool), NOT a string
    from streamlit.web import bootstrap
    bootstrap.run(
        app_py,
        False,      # is_hello — must be bool, not string
        [],         # args
        {           # flag_options
            "server.port": port,
            "server.headless": True,
            "browser.gatherUsageStats": False,
            "server.fileWatcherType": "none",
            "global.developmentMode": False,
        }
    )

if __name__ == "__main__":
    main()
