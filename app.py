"""
TrialLens 临镜 v1.0
Batch-download and keyword-screen Protocol/SAP PDFs from ClinicalTrials.gov
(c) 2025 Dr Zhang. All rights reserved.
"""

import streamlit as st
import pandas as pd
import requests
import shutil
import re
import io
import os
from pathlib import Path
from pdfminer.high_level import extract_text

st.set_page_config(page_title="TrialLens 临镜", page_icon="🔬", layout="wide")

st.markdown("""
<style>
  .app-header { background: linear-gradient(135deg,#1a3a5c 0%,#2980b9 100%);
    padding:18px 28px 14px; border-radius:10px; margin-bottom:20px; }
  .app-header h1 { color:white; font-size:24px; font-weight:800; margin:0 0 2px; }
  .app-header .sub { color:rgba(255,255,255,0.65); font-size:13px; margin:0; }
  .ver { background:rgba(255,255,255,0.18); color:rgba(255,255,255,0.9);
    font-size:11px; font-weight:700; padding:2px 9px; border-radius:10px; margin-left:10px; }
  .cn  { color:rgba(255,255,255,0.45); font-size:15px; margin-left:8px; }
  .stat-row { display:flex; gap:10px; margin:12px 0; }
  .stat-box { flex:1; border-radius:8px; padding:12px 14px; text-align:center; border-left:4px solid; }
  .stat-blue   { background:#f0f7ff; border-color:#2980b9; }
  .stat-green  { background:#f0fff4; border-color:#27ae60; }
  .stat-orange { background:#fff8f0; border-color:#e67e22; }
  .stat-red    { background:#fff5f5; border-color:#e74c3c; }
  .stat-num { font-size:28px; font-weight:800; color:#2c3e50; line-height:1; }
  .stat-lbl { font-size:11px; color:#7f8c8d; margin-top:4px; text-transform:uppercase; }
  .log-box { background:#1a2332; color:#7ecf88; font-family:'Courier New',monospace;
    font-size:12px; padding:14px 16px; border-radius:8px; height:240px;
    overflow-y:auto; white-space:pre-wrap; line-height:1.65; border:1px solid #243447; }
  .log-warn  { color:#f0ad4e; } .log-error { color:#e74c3c; } .log-head { color:#5dade2; font-weight:bold; }
  .sec-lbl { font-size:11px; font-weight:700; color:#34495e; text-transform:uppercase;
    letter-spacing:0.8px; margin-bottom:6px; margin-top:18px; }
  .kw-tag { display:inline-block; background:#ebf5fb; color:#2980b9; border-radius:12px;
    padding:3px 11px; font-size:12px; margin:2px; font-weight:500; }
  .search-box { background:#f8fafc; border:1px solid #e2e8f0; border-radius:8px; padding:16px 18px; }
  .footer { background:linear-gradient(135deg,#1a3a5c,#154060); color:rgba(255,255,255,0.45);
    font-size:11.5px; padding:10px 24px; border-radius:8px; margin-top:28px;
    display:flex; justify-content:space-between; }
  hr { border:none; border-top:1px solid #eaecef; margin:20px 0; }
  #MainMenu {visibility:hidden;} footer {visibility:hidden;} header {visibility:hidden;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="app-header">
  <h1>🔬 TrialLens <span class="ver">v 1.0</span><span class="cn">临镜</span></h1>
  <p class="sub">Batch download &amp; keyword-screen Protocol / SAP from ClinicalTrials.gov
  &nbsp;|&nbsp; 批量下载并筛选临床试验文件</p>
</div>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for key, val in {
    "dl_log": [], "dl_total": 0, "dl_ok": 0, "dl_skip": 0, "dl_fail": 0,
    "sr_log": [], "sr_total": 0, "sr_matched": 0, "sr_no": 0, "sr_err": 0,
    "sr_done": False,
    "df_cache": None,      # ← CSV cached here so rerun doesn't lose it
    "df_cache_name": "",   # ← track filename to detect new upload
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ── Helpers ───────────────────────────────────────────────────────────────────
def fix_path(p):
    return p.strip().replace("\\", "/")

def read_csv_auto(uploaded):
    raw = uploaded.read()
    uploaded.seek(0)
    sample = raw[:2000].decode("utf-8", errors="replace")
    sep = "\t" if sample.count("\t") >= 2 else ","
    return pd.read_csv(io.BytesIO(raw), sep=sep, dtype=str).fillna("")

def parse_urls(cell):
    prot = sap = None
    for entry in cell.split("|"):
        entry = entry.strip()
        m = re.search(r"https?://\S+\.pdf", entry)
        if not m:
            continue
        url = m.group()
        if re.search(r"Prot_SAP|Protocol|Prot_", entry, re.I) and prot is None:
            prot = url
        elif re.search(r"Statistical Analysis Plan|SAP_", entry, re.I) and sap is None:
            sap = url
    return {"protocol": prot, "sap": sap}

def get_targets(cell, doc_type, trial_id, pdf_dir):
    urls = parse_urls(cell)
    targets = []
    if doc_type == "Protocol" and urls["protocol"]:
        targets.append({"url": urls["protocol"], "path": os.path.join(pdf_dir, f"{trial_id}.pdf")})
    elif doc_type == "SAP" and urls["sap"]:
        targets.append({"url": urls["sap"], "path": os.path.join(pdf_dir, f"{trial_id}.pdf")})
    elif doc_type == "Both":
        if urls["protocol"]:
            targets.append({"url": urls["protocol"], "path": os.path.join(pdf_dir, f"{trial_id}_protocol.pdf")})
        if urls["sap"]:
            targets.append({"url": urls["sap"], "path": os.path.join(pdf_dir, f"{trial_id}_sap.pdf")})
    return targets

HDRS = {"User-Agent": "Mozilla/5.0", "Accept": "application/pdf,*/*"}

def safe_folder_name(kw):
    return re.sub(r'[\\/:*?"<>|]', "_", kw)

def extract_pdf_text(path):
    try:
        return extract_text(path).lower()
    except Exception:
        return None

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_tool, tab_guide_en, tab_guide_zh = st.tabs(["🛠 Tool / 工具", "📖 Guide (EN)", "📖 使用指南"])

with tab_tool:
    col_left, col_right = st.columns([5, 7])

    with col_left:
        st.markdown('<div class="sec-lbl">① Trial List CSV / 试验列表</div>', unsafe_allow_html=True)
        csv_file = st.file_uploader("", type="csv", label_visibility="collapsed")

        # Cache CSV as soon as it's uploaded — survives rerun
        if csv_file is not None:
            if csv_file.name != st.session_state.df_cache_name:
                try:
                    st.session_state.df_cache = read_csv_auto(csv_file)
                    st.session_state.df_cache_name = csv_file.name
                except Exception as e:
                    st.error(f"Failed to read CSV: {e}")

        if st.session_state.df_cache is not None:
            n = len(st.session_state.df_cache)
            st.success(f"✓  {n} trials loaded / 已读取 {n} 条  ({st.session_state.df_cache_name})")

        st.markdown('<div class="sec-lbl">② PDF Output Folder / 输出目录</div>', unsafe_allow_html=True)
        pdf_dir_input = st.text_input("", placeholder=r"e.g.  F:\test\output", label_visibility="collapsed")

        st.markdown('<div class="sec-lbl">③ Document Type / 文档类型</div>', unsafe_allow_html=True)
        doc_type = st.radio("", ["Protocol", "SAP", "Both / 两者"], horizontal=True, label_visibility="collapsed")
        doc_type = doc_type.split(" ")[0]

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown('<div class="sec-lbl">Download / 下载</div>', unsafe_allow_html=True)
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            start_clicked = st.button("▶  Start Download / 开始下载", type="primary", use_container_width=True)
        with col_btn2:
            stop_clicked = st.button("■  Stop / 停止", use_container_width=True)

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown('<div class="sec-lbl">④ Keyword Search / 关键词筛选</div>', unsafe_allow_html=True)
        st.markdown('<div class="search-box">', unsafe_allow_html=True)
        st.caption("Scans PDFs already in the output folder above  /  扫描上方目录中已下载的 PDF")
        kw_input = st.text_input("Keywords", placeholder="RPSFT, rank preserving  (comma / 逗号分隔)", label_visibility="collapsed")
        if kw_input:
            kws = [k.strip() for k in kw_input.split(",") if k.strip()]
            st.markdown("".join(f'<span class="kw-tag">{k}</span>' for k in kws), unsafe_allow_html=True)
        search_clicked = st.button("🔍  Search / 开始筛选", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        dl_done = st.session_state.dl_ok + st.session_state.dl_skip + st.session_state.dl_fail
        dl_pct  = dl_done / st.session_state.dl_total if st.session_state.dl_total > 0 else 0

        st.markdown('<div class="sec-lbl">Download Progress / 下载进度</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="stat-row">
          <div class="stat-box stat-blue"><div class="stat-num">{st.session_state.dl_total}</div><div class="stat-lbl">Total / 总计</div></div>
          <div class="stat-box stat-green"><div class="stat-num">{st.session_state.dl_ok}</div><div class="stat-lbl">Downloaded</div></div>
          <div class="stat-box stat-orange"><div class="stat-num">{st.session_state.dl_skip}</div><div class="stat-lbl">Skipped / 跳过</div></div>
          <div class="stat-box stat-red"><div class="stat-num">{st.session_state.dl_fail}</div><div class="stat-lbl">Failed / 失败</div></div>
        </div>""", unsafe_allow_html=True)
        st.progress(dl_pct)
        if st.session_state.dl_total > 0:
            st.caption(f"{dl_done} / {st.session_state.dl_total}  ({dl_pct*100:.0f}%)")
        st.markdown(f'<div class="log-box">{"<br>".join(st.session_state.dl_log[-200:])}</div>', unsafe_allow_html=True)

        st.markdown("<hr>", unsafe_allow_html=True)

        sr_done_n = st.session_state.sr_matched + st.session_state.sr_no + st.session_state.sr_err
        sr_pct    = sr_done_n / st.session_state.sr_total if st.session_state.sr_total > 0 else 0

        st.markdown('<div class="sec-lbl">Search Results / 筛选结果</div>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="stat-row">
          <div class="stat-box stat-blue"><div class="stat-num">{st.session_state.sr_total}</div><div class="stat-lbl">PDFs / 总数</div></div>
          <div class="stat-box stat-green"><div class="stat-num">{st.session_state.sr_matched}</div><div class="stat-lbl">Matched / 命中</div></div>
          <div class="stat-box stat-orange"><div class="stat-num">{st.session_state.sr_no}</div><div class="stat-lbl">No Match</div></div>
          <div class="stat-box stat-red"><div class="stat-num">{st.session_state.sr_err}</div><div class="stat-lbl">Errors / 失败</div></div>
        </div>""", unsafe_allow_html=True)
        st.progress(sr_pct)
        if st.session_state.sr_total > 0:
            st.caption(f"{sr_done_n} / {st.session_state.sr_total}  ({sr_pct*100:.0f}%)")
        st.markdown(f'<div class="log-box">{"<br>".join(st.session_state.sr_log[-200:])}</div>', unsafe_allow_html=True)

    # ── Button handlers ───────────────────────────────────────────────────────
    if stop_clicked:
        st.session_state.dl_stop = True
        st.rerun()

    if start_clicked:
        if st.session_state.df_cache is None:
            st.error("Please upload a CSV file  /  请上传 CSV 文件")
            st.stop()
        if not pdf_dir_input.strip():
            st.error("Please enter the output folder path  /  请填写输出目录")
            st.stop()

        df      = st.session_state.df_cache   # use cached df — no re-read
        pdf_dir = fix_path(pdf_dir_input)

        nct_col = next((c for c in df.columns if re.search(r"nct.number", c, re.I)), None)
        doc_col = next((c for c in df.columns if re.search(r"study.documents", c, re.I)), None)
        if not nct_col or not doc_col:
            st.error("CSV missing 'NCT Number' or 'Study Documents' column")
            st.stop()

        os.makedirs(pdf_dir, exist_ok=True)

        st.session_state.dl_log   = []
        st.session_state.dl_total = len(df)
        st.session_state.dl_ok = st.session_state.dl_skip = st.session_state.dl_fail = 0
        st.session_state.dl_stop  = False

        def add_dl_log(msg):
            st.session_state.dl_log.append(msg)

        add_dl_log(f'<span class="log-head">▶ Download started | Type: {doc_type.upper()} | Total: {len(df)}</span>')

        # Download — no st.rerun() inside the loop
        for i, row in df.iterrows():
            if st.session_state.get("dl_stop"):
                add_dl_log('<span class="log-warn">■ Stopped by user</span>')
                break

            trial_id = str(row[nct_col]).strip()
            targets  = get_targets(str(row[doc_col]), doc_type, trial_id, pdf_dir)

            if not targets:
                add_dl_log(f'<span class="log-warn">⚠ [{trial_id}] No {doc_type} document found</span>')
                st.session_state.dl_fail += 1
                continue

            for tgt in targets:
                if os.path.exists(tgt["path"]):
                    st.session_state.dl_skip += 1
                    continue
                try:
                    r = requests.get(tgt["url"], headers=HDRS, timeout=30)
                    r.raise_for_status()
                    with open(tgt["path"], "wb") as f:
                        f.write(r.content)
                    st.session_state.dl_ok += 1
                    add_dl_log(f'✓ [{trial_id}] {os.path.basename(tgt["path"])}')
                except Exception as e:
                    st.session_state.dl_fail += 1
                    add_dl_log(f'<span class="log-error">✗ [{trial_id}] {e}</span>')

        add_dl_log(f'<span class="log-head">✅ Done — Downloaded: {st.session_state.dl_ok}  '
                   f'Skipped: {st.session_state.dl_skip}  Failed: {st.session_state.dl_fail}</span>')
        st.rerun()

    if search_clicked:
        pdf_dir = fix_path(pdf_dir_input)
        kws = [k.strip() for k in kw_input.split(",") if k.strip()] if kw_input else []

        if not pdf_dir:
            st.error("Please enter the output folder path"); st.stop()
        if not kws:
            st.error("Please enter at least one keyword"); st.stop()

        pdf_files = list(Path(pdf_dir).glob("*.pdf"))
        if not pdf_files:
            st.error("No PDF files found in the output folder"); st.stop()

        st.session_state.sr_log     = []
        st.session_state.sr_total   = len(pdf_files)
        st.session_state.sr_matched = st.session_state.sr_no = st.session_state.sr_err = 0
        st.session_state.sr_done    = False

        not_matched_dir = Path(pdf_dir) / "not_matched"
        not_matched_dir.mkdir(exist_ok=True)
        kw_lower   = [k.lower() for k in kws]
        safe_names = [safe_folder_name(k) for k in kws]
        kw_dirs    = [Path(pdf_dir) / "matched" / s for s in safe_names]
        for d in kw_dirs:
            d.mkdir(parents=True, exist_ok=True)

        def add_sr_log(msg):
            st.session_state.sr_log.append(msg)

        add_sr_log(f'<span class="log-head">🔍 Searching {len(pdf_files)} PDFs — Keywords: {", ".join(kws)}</span>')

        for pdf_path in pdf_files:
            fname   = pdf_path.name
            content = extract_pdf_text(str(pdf_path))
            if content is None:
                add_sr_log(f'<span class="log-error">✗ Cannot read: {fname}</span>')
                st.session_state.sr_err += 1
                continue
            hit_idx = next((i for i, kw in enumerate(kw_lower) if kw in content), None)
            if hit_idx is None:
                shutil.move(str(pdf_path), str(not_matched_dir / fname))
                st.session_state.sr_no += 1
            else:
                shutil.move(str(pdf_path), str(kw_dirs[hit_idx] / fname))
                st.session_state.sr_matched += 1
                add_sr_log(f'✓ HIT → {fname}  [{kws[hit_idx]}]')

        add_sr_log(f'<span class="log-head">✅ Done — Matched: {st.session_state.sr_matched}  '
                   f'No match: {st.session_state.sr_no}  Errors: {st.session_state.sr_err}</span>')
        st.session_state.sr_done = True
        st.rerun()

# ── Guide tabs ────────────────────────────────────────────────────────────────
with tab_guide_en:
    st.markdown("### 🔬 What does TrialLens do?")
    st.markdown("""
**Download:** Batch-downloads Protocol and/or SAP PDFs from ClinicalTrials.gov, named by NCT number.
Stop and resume at any time — already-downloaded files are skipped.

**Search:** Scans PDFs for keywords and moves them into `matched/<keyword>/` subfolders.
Non-matched PDFs go to `not_matched/`.
""")
    st.markdown("### 📋 How to use")
    st.markdown("""
1. Go to [clinicaltrials.gov](https://clinicaltrials.gov) → search → **Download → CSV**.
2. Upload CSV **(①)**, set output folder **(②)**, choose document type **(③)**.
3. Click **▶ Start Download**. Click **■ Stop** to pause — progress is preserved.
4. Enter keywords **(④)** → **🔍 Search**. Case-insensitive. First matching keyword wins.
""")
    st.markdown("### 📁 Output structure")
    st.code("PDF Output Folder/\n├── matched/\n│   ├── RPSFT/\n│   │   └── NCT01714739.pdf\n│   └── rank preserving/\n│       └── NCT02234567.pdf\n└── not_matched/\n    └── NCT09999999.pdf", language=None)
    st.info("**Paths:** Both `F:\\\\test` and `F:/test` work.\n\n**Keyword priority:** First matching keyword wins — order matters.\n\n**Encrypted PDFs:** Reported as errors, other files unaffected.")

with tab_guide_zh:
    st.markdown("### 🔬 工具简介")
    st.markdown("""
**下载：** 批量下载 Protocol / SAP PDF，以 NCT 编号命名。可随时停止，重新运行时自动跳过已下载文件。

**筛选：** 扫描 PDF，命中关键词的移入 `matched/<关键词>/`，未命中的移入 `not_matched/`。
""")
    st.markdown("### 📋 操作步骤")
    st.markdown("""
1. 打开 [clinicaltrials.gov](https://clinicaltrials.gov) → 检索 → **Download → CSV**。
2. 上传 CSV **(①)**，填写输出目录 **(②)**，选择文档类型 **(③)**。
3. 点击 **▶ 开始下载**，随时可点 **■ 停止**，进度完整保留。
4. 输入关键词 **(④)** → **🔍 开始筛选**，不区分大小写，优先放入第一个匹配关键词的文件夹。
""")
    st.markdown("### 📁 输出文件夹结构")
    st.code("PDF 输出目录/\n├── matched/\n│   ├── RPSFT/\n│   │   └── NCT01714739.pdf\n│   └── rank preserving/\n│       └── NCT02234567.pdf\n└── not_matched/\n    └── NCT09999999.pdf", language=None)
    st.info("**路径格式：** 反斜杠自动转换。\n\n**关键词优先级：** 多个关键词命中时，放入排在最前面的关键词文件夹。\n\n**加密 PDF：** 记为错误，不影响其他文件。")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
  <div><strong style="color:rgba(255,255,255,0.75);">TrialLens 临镜 v1.0</strong>
  &nbsp;·&nbsp; (c) 2025 Dr Zhang. All rights reserved.</div>
  <div>For academic &amp; research use only &nbsp;|&nbsp; 仅供学术研究使用</div>
</div>
""", unsafe_allow_html=True)
