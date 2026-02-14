# LaTeX source (v1)

This directory contains a LaTeX version of the current manuscript for PDF generation.

Build (writes artifacts under `tmp/`, ignored):

```bash
mkdir -p tmp/paper_build
pdflatex -interaction=nonstopmode -halt-on-error -output-directory tmp/paper_build docs/paper/tex_v1/main.tex
pdflatex -interaction=nonstopmode -halt-on-error -output-directory tmp/paper_build docs/paper/tex_v1/main.tex
```

Output:
- `tmp/paper_build/main.pdf`

