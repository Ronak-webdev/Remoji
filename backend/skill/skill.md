---
name: ieee-code-report
description: >
  Use this skill whenever a user wants to analyze code (a file, project, repository, or codebase)
  and produce a formal IEEE-format research paper or technical report about it. Triggers include:
  "analyze my code and write a report", "generate an IEEE paper from my project", "write a research
  paper about this codebase", "IEEE format report for my code", "document my project as a paper",
  "research report on my algorithm/system/application", or any request combining code analysis +
  academic/formal writing. Also trigger when the user uploads code files and asks for deep technical
  documentation. The output is a complete, compilable LaTeX .tex file using the IEEEtran class,
  plus a ready-to-render PDF via LaTeX compilation. The report must be humanized, deep, and fully
  IEEE-compliant — covering architecture, algorithms, complexity analysis, data flow, performance
  metrics, equations, auto-generated figures/tables, and well-cited references.
---
 
# IEEE Code Research Report Generator
 
Produces a publication-ready IEEE conference paper in LaTeX by performing a deep, structured
analysis of a provided codebase. The output feels authored by a human researcher — not
auto-generated — and strictly follows IEEE IEEEtran formatting guidelines.
 
---
 
## Step 0 — Read the IEEE Reference Template First
 
Before writing a single line of LaTeX, read the reference template to internalize all formatting
rules:
 
→ **`references/ieee-formatting-rules.md`** — authoritative rules for structure, headings,
equations, figures, tables, citations, and common mistakes to avoid.
 
---
 
## Step 1 — Gather Inputs
 
Collect from the user (ask if not provided):
 
| Input | Required? | Notes |
|---|---|---|
| Code files / repo | ✅ Yes | Source to analyze — can be uploaded files, pasted code, or a GitHub URL |
| Paper title | ✅ Yes | Can be proposed by Claude based on code analysis |
| Author name(s), affiliation, email | ✅ Yes | Needed for IEEE author block |
| Target conference/journal | Optional | Affects intro framing |
| Keywords (3–5) | Optional | Claude can suggest from code analysis |
| Known related works to cite | Optional | Claude will also propose citations |
 
If the user hasn't specified a paper title, propose one based on the code's primary purpose
(e.g., *"A Lightweight REST API Framework for Real-Time Audio Processing Using FastAPI and
WebSockets"*). Let the user confirm.
 
---
 
## Step 2 — Deep Code Analysis
 
Perform a **comprehensive, systematic analysis** of the provided code. This is the foundation of
the entire paper — do not rush or summarize superficially. Extract:
 
### 2a. Architecture & System Design
- Overall system architecture (layers, modules, services)
- Design patterns identified (MVC, pipeline, factory, observer, etc.)
- Dependency graph between major components
- Entry points, data flow, and control flow
### 2b. Algorithms & Logic
- Every non-trivial algorithm present — name it, describe it, explain its role
- Data structures used and why they were chosen
- Recursion, dynamic programming, graph traversal, or other algorithmic strategies
- State machines or finite automata if present
### 2c. Complexity Analysis
- Time complexity of key functions (Big-O, Big-Θ where applicable)
- Space complexity
- Any identified bottlenecks or inefficiency notes
### 2d. Performance & Metrics
- Lines of code per module
- Function/method count
- Cyclomatic complexity (estimate if not measurable)
- Memory or I/O patterns
- Any benchmarks or test results embedded in the code
### 2e. Technologies & Dependencies
- Languages, frameworks, libraries — versions if mentioned
- External APIs or services
- Build systems or configuration files
### 2f. Novelty & Contribution Claims
- What does this code do that standard approaches don't?
- What problems does it solve?
- Any optimizations, novel combinations, or unique design choices
---
 
## Step 3 — Paper Structure
 
Generate ALL of the following sections. Do not omit any. Depth matters — each section must be
substantive, not placeholder text.
 
### Mandatory IEEE Sections (in this order):
 
1. **Title** — descriptive, specific, no abbreviations unless unavoidable
2. **Author Block** — IEEE multi-author format with dept, org, city, country, email
3. **Abstract** (150–250 words) — problem, methodology, key results, conclusion. No symbols,
   footnotes, or math. Written as a single flowing paragraph.
4. **Index Terms / Keywords** — 4–6 terms, lowercase except proper nouns
5. **I. Introduction** — motivation, problem statement, paper scope, contributions enumerated,
   paper organization overview. Must end with a paragraph like *"The rest of this paper is
   organized as follows..."*
6. **II. Related Work** — cite ≥5 relevant works; discuss what they do and how this work differs
7. **III. System Architecture / Methodology** — the main technical section; use subsections
   freely; must include at least one figure (architecture diagram described as TikZ or referenced
   as `fig1`) and one table
8. **IV. Implementation Details** — language/framework details, key code decisions, non-obvious
   implementation choices, data pipeline if applicable
9. **V. Complexity Analysis & Performance Evaluation** — all Big-O analysis, benchmark numbers
   (real or estimated from code), at least one equation block, at least one results table
10. **VI. Results & Discussion** — what the system achieves, limitations, comparisons to baselines
11. **VII. Conclusion & Future Work** — summary of contributions, 3–5 bullet-level future directions
    written as prose
12. **Acknowledgment** (unnumbered) — placeholder or real
13. **References** — minimum 8, IEEE bibliography format (see formatting rules)
---
 
## Step 4 — Humanization Rules
 
The paper must read like it was written by a knowledgeable human researcher, not generated by AI.
Apply these rules throughout:
 
- **Vary sentence structure**: mix short punchy sentences with longer compound ones
- **Use first-person plural sparingly but naturally**: *"We propose..."*, *"Our system..."*,
  *"As we observed in Section III..."*
- **Avoid hollow filler phrases**: never write *"In this paper, we present..."* as your FIRST
  sentence — start with the problem context instead
- **Use concrete specifics**: instead of *"the algorithm is efficient"*, write *"the sort
  operation runs in O(n log n) with an observed 40ms latency on 10,000 items"*
- **Transitional phrases between sections**: every section should end with a forward reference
  or closing thought that connects to the next
- **Active voice preferred**: *"the module processes..."* not *"processing is done by..."*
- **Technical hedging where appropriate**: *"preliminary results suggest..."*, *"while our
  evaluation is limited to..."*
- **Equations embedded naturally**: introduce each equation in prose before displaying it
- **Figures referenced in text**: every figure/table must be cited in the body with `Fig.~\ref{}`
  or `Table~\ref{}`
---
 
## Step 5 — Equations & Math
 
- Number ALL equations with `\begin{equation}...\end{equation}`
- Define every symbol before or immediately after the equation
- Use `\eqref{label}` for cross-references, never `(1)` hardcoded
- Complexity expressions: use `$O(n \log n)$` inline or full equation block for derivations
- If the code has loss functions, distance metrics, probability distributions, or any numeric
  formula — turn them into proper LaTeX equations
Minimum required: **3 equations** (complexity, a key formula from the code, and one performance
metric or evaluation formula like accuracy/F1/throughput).
 
---
 
## Step 6 — Figures & Tables
 
Since actual image files may not be available, use one of:
 
**Option A — ASCII/TikZ architecture diagram** (preferred):
```latex
\usepackage{tikz}
\usetikzlibrary{shapes,arrows,positioning}
% ... draw system architecture as boxes and arrows
```
 
**Option B — Placeholder figure with caption** (fallback):
```latex
\begin{figure}[htbp]
\centerline{\includegraphics[width=0.45\textwidth]{architecture.png}}
\caption{System architecture of [ProjectName] showing the three-layer pipeline.}
\label{fig:arch}
\end{figure}
```
 
**Required tables** (include ALL that apply):
- Module/component breakdown table (name, responsibility, LOC, complexity)
- Performance comparison table (this system vs. baselines or naive approaches)
- Technology stack table (component, library, version, purpose)
Tables must use `\begin{table}[htbp]`, have `\caption{}` ABOVE, and use `\hline` formatting.
Column headers in `\textbf{\textit{...}}`.
 
---
 
## Step 7 — Citations & References
 
Format ALL references strictly in IEEE style:
 
```latex
\bibitem{bN} A. Author and B. Author, "Title of paper," \textit{Journal Name},
vol. X, no. Y, pp. ZZ--ZZ, Month Year.
```
 
Reference types to include:
- Journal articles: `\textit{IEEE Trans. ...}` or `\textit{ACM ...}`
- Conference papers: *Proc. Int. Conf. ...*
- Books: italic title, publisher, year
- ArXiv: include arXiv ID and URL
- GitHub repos: author, repo name, year, [Online] Available: URL
- Datasets: institution, title, DOI or URL
Cite works naturally in text: `\cite{b1}` after the claim, not before. Multiple citations:
`\cite{b1,b3,b5}`. Cite at least once per section.
 
Auto-propose references based on the technologies used in the code. For example:
- FastAPI → cite the FastAPI documentation or related REST API paper
- PyTorch → cite the original PyTorch paper (Paszke et al., 2019)
- Transformers → cite Vaswani et al., 2017
- React → cite relevant web framework paper or Meta technical report
---
 
## Step 8 — LaTeX Output Rules
 
Generate a **single complete .tex file**. It must:
 
- Begin with `\documentclass[conference]{IEEEtran}` — no other document class
- Include all necessary `\usepackage{}` declarations at the top
- Have NO placeholder/template guidance text (remove all `TODO`, `[Your text here]`, etc.)
- Compile without errors in a standard LaTeX environment with IEEEtran.cls present
- Use `\IEEEoverridecommandlockouts` only if funding footnote is used
- Have proper `\label{}` and `\ref{}`/`\eqref{}` for all cross-references
- End with `\end{document}`
**Required packages** (include all):
```latex
\usepackage{cite}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{algorithmic}
\usepackage{graphicx}
\usepackage{textcomp}
\usepackage{xcolor}
\usepackage{booktabs}       % for professional tables
\usepackage{tikz}           % for architecture diagrams
\usepackage{listings}       % for inline code snippets
\usepackage{hyperref}       % for URL links in references
```
 
---
 
## Step 9 — Output Delivery
 
1. Write the `.tex` file to `/mnt/user-data/outputs/ieee_report.tex`
2. Attempt LaTeX compilation:
```bash
cd /tmp && cp /mnt/user-data/outputs/ieee_report.tex . && \
pdflatex -interaction=nonstopmode ieee_report.tex 2>&1 | tail -20
```
3. If compilation succeeds, copy PDF: `cp /tmp/ieee_report.pdf /mnt/user-data/outputs/`
4. Present BOTH files to the user with `present_files`
5. If compilation fails, diagnose the error, fix the .tex file, retry once.
If pdflatex is not available or IEEEtran.cls is missing:
- Still deliver the `.tex` file
- Tell the user they can compile it with: `pdflatex ieee_report.tex` (requires IEEEtran.cls
  in the same folder, available at https://www.ieee.org/conferences/publishing/templates.html)
---
 
## Quality Checklist (verify before output)
 
Before delivering, mentally check:
 
- [ ] Abstract: no math symbols, no footnotes, 150–250 words, single paragraph
- [ ] All sections present: I through VII + Acknowledgment + References
- [ ] ≥3 numbered equations with symbols defined
- [ ] ≥1 figure with caption below
- [ ] ≥2 tables with caption above
- [ ] ≥8 references in IEEE bibliography format
- [ ] Every figure/table cited in body text
- [ ] No hardcoded equation numbers (using `\eqref{}`)
- [ ] Complexity analysis present for all major algorithms
- [ ] Humanized writing — no AI filler phrases
- [ ] Paper reads as a coherent research contribution, not a code walkthrough