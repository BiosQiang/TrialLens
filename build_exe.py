"""
build_exe.py — 打包 TrialLens 为 Windows 单文件 exe

用法（在 Windows 上运行）：
    pip install pyinstaller streamlit pdfminer.six requests
    python build_exe.py
"""

import subprocess
import sys
import os

# 找到 streamlit 包的路径（需要把它完整打包进去）
try:
    import streamlit
    st_path = os.path.dirname(streamlit.__file__)
except ImportError:
    print("请先安装 streamlit: pip install streamlit")
    sys.exit(1)

# PyInstaller 命令
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",                        # 打包成单个 exe
    "--noconfirm",                      # 覆盖已有输出
    "--name", "TrialLens",             # exe 名称
    "--icon", "NONE",                  # 可替换为 .ico 文件路径
    "--hidden-import", "streamlit",
    "--hidden-import", "pdfminer",
    "--hidden-import", "pdfminer.high_level",
    "--hidden-import", "pdfminer.layout",
    "--hidden-import", "pdfminer.converter",
    "--hidden-import", "requests",
    "--hidden-import", "pandas",
    "--collect-all", "streamlit",       # 把 streamlit 的静态资源全部打包
    "--collect-all", "pdfminer",
    "launcher.py",                      # 入口文件（见下方）
]

print("Running PyInstaller...")
print(" ".join(cmd))
subprocess.run(cmd, check=True)
print("\nDone! Find TrialLens.exe in the dist/ folder.")
