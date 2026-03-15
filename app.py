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
  .log-warn  { color:#f0ad4e; }
  .log-error { color:#e74c3c; }
  .log-head  { color:#5dade2; font-weight:bold; }
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
  <h1>&#128300; TrialLens <span class="ver">v 1.0</span><span class="cn">&#20020;&#38236;</span></h1>
  <p class="sub">Batch download &amp; keyword-screen Protocol / SAP from ClinicalTrials.gov
  &nbsp;|&nbsp; &#25209;&#37327;&#19979;&#36733;&#24182;&#31807;&#36873;&#20020;&#24202;&#35797;&#39564;&#25991;&#20214;</p>
</div>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for key, val in {
    "dl_log": [], "dl_total": 0, "dl_ok": 0, "dl_skip": 0, "dl_fail": 0,
    "sr_log": [], "sr_total": 0, "sr_matched": 0, "sr_no": 0, "sr_err": 0,
    "sr_done": False,
    "df_cache": None,
    "df_cache_name": "",
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
        targets.append({"url": urls["protocol"],
                        "path": os.path.join(pdf_dir, trial_id + ".pdf")})
    elif doc_type == "SAP" and urls["sap"]:
        targets.append({"url": urls["sap"],
                        "path": os.path.join(pdf_dir, trial_id + ".pdf")})
    elif doc_type == "Both":
        if urls["protocol"]:
            targets.append({"url": urls["protocol"],
                            "path": os.path.join(pdf_dir, trial_id + "_protocol.pdf")})
        if urls["sap"]:
            targets.append({"url": urls["sap"],
                            "path": os.path.join(pdf_dir, trial_id + "_sap.pdf")})
    return targets

HDRS = {"User-Agent": "Mozilla/5.0", "Accept": "application/pdf,*/*"}

def safe_folder_name(kw):
    return re.sub(r'[\\/:*?"<>|]', "_", kw)

def extract_pdf_text(path):
    try:
        return extract_text(path).lower()
    except Exception:
        return None

def stat_html(dl_total, dl_ok, dl_skip, dl_fail):
    return (
        '<div class="stat-row">'
        '<div class="stat-box stat-blue">'
        '<div class="stat-num">' + str(dl_total) + '</div>'
        '<div class="stat-lbl">Total / \u603b\u8ba1</div></div>'
        '<div class="stat-box stat-green">'
        '<div class="stat-num">' + str(dl_ok) + '</div>'
        '<div class="stat-lbl">Downloaded</div></div>'
        '<div class="stat-box stat-orange">'
        '<div class="stat-num">' + str(dl_skip) + '</div>'
        '<div class="stat-lbl">Skipped / \u8df3\u8fc7</div></div>'
        '<div class="stat-box stat-red">'
        '<div class="stat-num">' + str(dl_fail) + '</div>'
        '<div class="stat-lbl">Failed / \u5931\u8d25</div></div>'
        '</div>'
    )

def sr_stat_html(sr_total, sr_matched, sr_no, sr_err):
    return (
        '<div class="stat-row">'
        '<div class="stat-box stat-blue">'
        '<div class="stat-num">' + str(sr_total) + '</div>'
        '<div class="stat-lbl">PDFs / \u603b\u6570</div></div>'
        '<div class="stat-box stat-green">'
        '<div class="stat-num">' + str(sr_matched) + '</div>'
        '<div class="stat-lbl">Matched / \u547d\u4e2d</div></div>'
        '<div class="stat-box stat-orange">'
        '<div class="stat-num">' + str(sr_no) + '</div>'
        '<div class="stat-lbl">No Match</div></div>'
        '<div class="stat-box stat-red">'
        '<div class="stat-num">' + str(sr_err) + '</div>'
        '<div class="stat-lbl">Errors / \u5931\u8d25</div></div>'
        '</div>'
    )

def log_html(lines):
    return '<div class="log-box">' + "<br>".join(lines[-200:]) + '</div>'

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_tool, tab_guide_en, tab_guide_zh = st.tabs(
    ["Tool / \u5de5\u5177", "Guide (EN)", "\u4f7f\u7528\u6307\u5357"])

with tab_tool:
    col_left, col_right = st.columns([5, 7])

    # ── Left column ───────────────────────────────────────────────────────────
    with col_left:
        st.markdown('<div class="sec-lbl">&#9312; Trial List CSV / \u8bd5\u9a8c\u5217\u8868</div>',
                    unsafe_allow_html=True)
        csv_file = st.file_uploader("Upload CSV", type="csv",
                                    label_visibility="collapsed")
        if csv_file is not None:
            if csv_file.name != st.session_state.df_cache_name:
                try:
                    st.session_state.df_cache = read_csv_auto(csv_file)
                    st.session_state.df_cache_name = csv_file.name
                except Exception as e:
                    st.error("Failed to read CSV: {}".format(e))

        if st.session_state.df_cache is not None:
            n = len(st.session_state.df_cache)
            st.success("✓  {} trials loaded / \u5df2\u8bfb\u53d6 {} \u6761  ({})".format(
                n, n, st.session_state.df_cache_name))

        st.markdown('<div class="sec-lbl">&#9313; PDF Output Folder / \u8f93\u51fa\u76ee\u5f55</div>',
                    unsafe_allow_html=True)
        pdf_dir_input = st.text_input("Output folder",
                                      placeholder=r"e.g.  F:\test\output",
                                      label_visibility="collapsed")

        st.markdown('<div class="sec-lbl">&#9314; Document Type / \u6587\u6863\u7c7b\u578b</div>',
                    unsafe_allow_html=True)
        doc_type_raw = st.radio("Document type",
                                ["Protocol", "SAP", "Both / \u4e24\u8005"],
                                horizontal=True, label_visibility="collapsed")
        doc_type = doc_type_raw.split(" ")[0]

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown('<div class="sec-lbl">Download / \u4e0b\u8f7d</div>',
                    unsafe_allow_html=True)
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            start_clicked = st.button("▶  Start / \u5f00\u59cb\u4e0b\u8f7d",
                                      type="primary", use_container_width=True)
        with col_b2:
            stop_clicked = st.button("■  Stop / \u505c\u6b62",
                                     use_container_width=True)

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown('<div class="sec-lbl">&#9315; Keyword Search / \u5173\u952e\u8bcd\u7b5b\u9009</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="search-box">', unsafe_allow_html=True)
        st.caption("Scans PDFs in the output folder  /  \u626b\u63cf\u4e0a\u65b9\u76ee\u5f55\u4e2d\u5df2\u4e0b\u8f7d\u7684 PDF")
        kw_input = st.text_input("Keywords input",
                                 placeholder="RPSFT, rank preserving  (comma / \u9017\u53f7\u5206\u9694)",
                                 label_visibility="collapsed")
        if kw_input:
            kws_preview = [k.strip() for k in kw_input.split(",") if k.strip()]
            st.markdown(
                "".join('<span class="kw-tag">{}</span>'.format(k) for k in kws_preview),
                unsafe_allow_html=True)
        search_clicked = st.button("Search / \u5f00\u59cb\u7b5b\u9009",
                                   use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Right column — all placeholders for live update ───────────────────────
    with col_right:
        st.markdown('<div class="sec-lbl">Download Progress / \u4e0b\u8f7d\u8fdb\u5ea6</div>',
                    unsafe_allow_html=True)
        ph_dl_stats = st.empty()
        ph_dl_prog  = st.empty()
        ph_dl_cap   = st.empty()
        ph_dl_log   = st.empty()

        st.markdown("<hr>", unsafe_allow_html=True)

        st.markdown('<div class="sec-lbl">Search Results / \u7b5b\u9009\u7ed3\u679c</div>',
                    unsafe_allow_html=True)
        ph_sr_stats = st.empty()
        ph_sr_prog  = st.empty()
        ph_sr_cap   = st.empty()
        ph_sr_log   = st.empty()

    def render_dl(ph_stats=ph_dl_stats, ph_prog=ph_dl_prog,
                  ph_cap=ph_dl_cap, ph_log=ph_dl_log):
        ok    = st.session_state.dl_ok
        skip  = st.session_state.dl_skip
        fail  = st.session_state.dl_fail
        total = st.session_state.dl_total
        done  = ok + skip + fail
        pct   = done / total if total > 0 else 0
        ph_stats.markdown(stat_html(total, ok, skip, fail), unsafe_allow_html=True)
        ph_prog.progress(pct)
        if total > 0:
            ph_cap.caption("{} / {}  ({:.0f}%)".format(done, total, pct * 100))
        ph_log.markdown(log_html(st.session_state.dl_log), unsafe_allow_html=True)

    def render_sr(ph_stats=ph_sr_stats, ph_prog=ph_sr_prog,
                  ph_cap=ph_sr_cap, ph_log=ph_sr_log):
        matched = st.session_state.sr_matched
        no      = st.session_state.sr_no
        err     = st.session_state.sr_err
        total   = st.session_state.sr_total
        done    = matched + no + err
        pct     = done / total if total > 0 else 0
        ph_stats.markdown(sr_stat_html(total, matched, no, err), unsafe_allow_html=True)
        ph_prog.progress(pct)
        if total > 0:
            ph_cap.caption("{} / {}  ({:.0f}%)".format(done, total, pct * 100))
        ph_log.markdown(log_html(st.session_state.sr_log), unsafe_allow_html=True)

    # Initial render
    render_dl()
    render_sr()

    # ── Button handlers ───────────────────────────────────────────────────────
    if stop_clicked:
        st.session_state.dl_stop = True

    if start_clicked:
        if st.session_state.df_cache is None:
            st.error("Please upload a CSV file  /  \u8bf7\u4e0a\u4f20 CSV \u6587\u4ef6")
            st.stop()
        if not pdf_dir_input.strip():
            st.error("Please enter the output folder path  /  \u8bf7\u586b\u5199\u8f93\u51fa\u76ee\u5f55")
            st.stop()

        df      = st.session_state.df_cache
        pdf_dir = fix_path(pdf_dir_input)

        nct_col = next((c for c in df.columns if re.search(r"nct.number", c, re.I)), None)
        doc_col = next((c for c in df.columns if re.search(r"study.documents", c, re.I)), None)
        if not nct_col or not doc_col:
            st.error("CSV missing 'NCT Number' or 'Study Documents' column")
            st.stop()

        os.makedirs(pdf_dir, exist_ok=True)

        st.session_state.dl_log   = []
        st.session_state.dl_total = len(df)
        st.session_state.dl_ok    = 0
        st.session_state.dl_skip  = 0
        st.session_state.dl_fail  = 0
        st.session_state.dl_stop  = False

        def add_dl_log(msg):
            st.session_state.dl_log.append(msg)

        add_dl_log('<span class="log-head">▶ Download started | Type: {} | Total: {}</span>'.format(
            doc_type.upper(), len(df)))
        render_dl()

        for i, row in df.iterrows():
            if st.session_state.get("dl_stop"):
                add_dl_log('<span class="log-warn">■ Stopped by user</span>')
                render_dl()
                break

            trial_id = str(row[nct_col]).strip()
            targets  = get_targets(str(row[doc_col]), doc_type, trial_id, pdf_dir)

            if not targets:
                add_dl_log('<span class="log-warn">⚠ [{}] No {} document found</span>'.format(
                    trial_id, doc_type))
                st.session_state.dl_fail += 1
                render_dl()
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
                    add_dl_log("✓ [{}] {}".format(trial_id, os.path.basename(tgt["path"])))
                except Exception as e:
                    st.session_state.dl_fail += 1
                    add_dl_log('<span class="log-error">✗ [{}] {}</span>'.format(trial_id, e))

            render_dl()  # live update after each trial

        add_dl_log('<span class="log-head">✅ Done — Downloaded: {}  Skipped: {}  Failed: {}</span>'.format(
            st.session_state.dl_ok, st.session_state.dl_skip, st.session_state.dl_fail))
        render_dl()
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
        st.session_state.sr_matched = 0
        st.session_state.sr_no      = 0
        st.session_state.sr_err     = 0
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

        add_sr_log('<span class="log-head">🔍 Searching {} PDFs — Keywords: {}</span>'.format(
            len(pdf_files), ", ".join(kws)))
        render_sr()

        for pdf_path in pdf_files:
            fname   = pdf_path.name
            content = extract_pdf_text(str(pdf_path))
            if content is None:
                add_sr_log('<span class="log-error">✗ Cannot read: {}</span>'.format(fname))
                st.session_state.sr_err += 1
                render_sr()
                continue
            hit_idx = next((i for i, kw in enumerate(kw_lower) if kw in content), None)
            if hit_idx is None:
                shutil.move(str(pdf_path), str(not_matched_dir / fname))
                st.session_state.sr_no += 1
            else:
                shutil.move(str(pdf_path), str(kw_dirs[hit_idx] / fname))
                st.session_state.sr_matched += 1
                add_sr_log("✓ HIT → {}  [{}]".format(fname, kws[hit_idx]))
            render_sr()  # live update after each PDF

        add_sr_log('<span class="log-head">✅ Done — Matched: {}  No match: {}  Errors: {}</span>'.format(
            st.session_state.sr_matched, st.session_state.sr_no, st.session_state.sr_err))
        st.session_state.sr_done = True
        render_sr()
        st.rerun()

# ── Guide EN ──────────────────────────────────────────────────────────────────
with tab_guide_en:
    st.markdown("### What does TrialLens do?")
    st.markdown("""
**Download:** Batch-downloads Protocol and/or SAP PDFs from ClinicalTrials.gov, named by NCT number.
Stop and resume at any time — already-downloaded files are skipped.

**Search:** Scans PDFs for keywords and moves them into `matched/<keyword>/` subfolders.
Non-matched PDFs go to `not_matched/`.
""")
    st.markdown("### How to use")
    st.markdown("""
1. Go to [clinicaltrials.gov](https://clinicaltrials.gov) → search → **Download → CSV**.
2. Upload CSV **(①)**, set output folder **(②)**, choose document type **(③)**.
3. Click **▶ Start**. Click **■ Stop** to pause — progress is preserved.
4. Enter keywords **(④)** → **Search**. Case-insensitive. First matching keyword wins.
""")
    st.markdown("### Output structure")
    st.code(
        "PDF Output Folder/\n"
        "├── matched/\n"
        "│   ├── RPSFT/\n"
        "│   │   └── NCT01714739.pdf\n"
        "│   └── rank preserving/\n"
        "│       └── NCT02234567.pdf\n"
        "└── not_matched/\n"
        "    └── NCT09999999.pdf",
        language=None)
    st.info(
        "**Paths:** Both `F:\\\\test` and `F:/test` work — backslashes convert automatically.\n\n"
        "**Keyword priority:** First matching keyword wins — order matters.\n\n"
        "**Encrypted PDFs:** Reported as errors, other files unaffected.\n\n"
        "**Local use only:** Reads and writes your local filesystem.")

# ── Guide ZH ──────────────────────────────────────────────────────────────────
with tab_guide_zh:
    st.markdown("### 工具简介")
    st.markdown("""
**下载：** 批量下载 Protocol / SAP PDF，以 NCT 编号命名。可随时停止，重新运行时自动跳过已下载文件。

**筛选：** 扫描 PDF，命中关键词的移入 `matched/<关键词>/`，未命中的移入 `not_matched/`。
""")
    st.markdown("### 操作步骤")
    st.markdown("""
1. 打开 [clinicaltrials.gov](https://clinicaltrials.gov) → 检索 → **Download → CSV**。
2. 上传 CSV **(①)**，填写输出目录 **(②)**，选择文档类型 **(③)**。
3. 点击 **▶ 开始下载**，随时可点 **■ 停止**，进度完整保留。
4. 输入关键词 **(④)** → **筛选**，不区分大小写，优先放入第一个匹配关键词的文件夹。
""")
    st.markdown("### 输出文件夹结构")
    st.code(
        "PDF 输出目录/\n"
        "├── matched/\n"
        "│   ├── RPSFT/\n"
        "│   │   └── NCT01714739.pdf\n"
        "│   └── rank preserving/\n"
        "│       └── NCT02234567.pdf\n"
        "└── not_matched/\n"
        "    └── NCT09999999.pdf",
        language=None)
    st.info(
        "**路径格式：** 反斜杠自动转换。\n\n"
        "**关键词优先级：** 多个关键词命中时，放入排在最前面的关键词文件夹。\n\n"
        "**加密 PDF：** 记为错误，不影响其他文件。\n\n"
        "**本地运行：** 直接读写本地文件夹。")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="footer">
  <div><strong style="color:rgba(255,255,255,0.75);">TrialLens &#20020;&#38236; v1.0</strong>
  &nbsp;·&nbsp; (c) 2025 Dr Zhang. All rights reserved.</div>
  <div>For academic &amp; research use only &nbsp;|&nbsp; &#20165;&#20379;&#23398;&#26415;&#30740;&#31350;&#20351;&#29992;</div>
</div>
""", unsafe_allow_html=True)
