# TrialLens 临镜

**Batch-download and keyword-screen Protocol / SAP PDFs from ClinicalTrials.gov**

批量下载并筛选临床试验 Protocol / SAP 文件

---

## Download / 下载

**[⬇ Download TrialLens.exe](https://github.com/BiosQiang/TrialLens/releases/latest)**

Double-click to run — no installation, no Python required.  
双击运行，无需安装任何软件。

---

## What it does / 功能简介

| Feature | Description |
|---|---|
| **Batch Download** | Downloads Protocol and/or SAP PDFs from ClinicalTrials.gov, named by NCT number |
| **Stop & Resume** | Interrupt at any time — already-downloaded files are skipped on re-run |
| **Keyword Search** | Scans PDFs for keywords and sorts them into subfolders automatically |
| **Bilingual UI** | English and Chinese interface |

---

## How to use / 使用步骤

### Step 1 — Export trial list from ClinicalTrials.gov

Go to [clinicaltrials.gov](https://clinicaltrials.gov) → search for trials → click **Download → CSV**.  
The CSV must contain `NCT Number` and `Study Documents` columns.

### Step 2 — Configure

1. **①** Upload the CSV file
2. **②** Set the PDF output folder (e.g. `F:\my_trials\output`)
3. **③** Choose document type: Protocol / SAP / Both

### Step 3 — Download

Click **▶ Start**. The dashboard updates in real time.  
Click **■ Stop** to interrupt safely — already-downloaded files are preserved.

### Step 4 — Keyword search

Enter keywords (comma-separated) and click **Search**.  
Matching is case-insensitive. PDFs are moved into subfolders automatically.

---

## Output structure / 输出目录结构

```
PDF Output Folder/
├── matched/
│   ├── RPSFT/
│   │   └── NCT01714739.pdf
│   └── rank preserving/
│       └── NCT02234567.pdf
└── not_matched/
    └── NCT09999999.pdf
```

If a PDF matches multiple keywords, it is filed under the **first** matching keyword.  
多个关键词命中时，放入排在最前面的关键词文件夹。

---

## Notes / 注意事项

- **Paths:** Both `F:\test\output` and `F:/test/output` are accepted
- **Encrypted PDFs:** Password-protected PDFs cannot be read and will be logged as errors
- **Local use only:** TrialLens runs on your own machine and accesses your local filesystem directly

---

## System requirements / 系统要求

| | |
|---|---|
| OS | Windows 10 / 11 |
| Installation | None — standalone `.exe` |
| Internet | Required for downloading PDFs |

---

## License / 许可

© 2025 Dr Zhang. All rights reserved.  
For academic and research use only. / 仅供学术研究使用。
