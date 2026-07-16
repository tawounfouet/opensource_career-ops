#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable


MIN_SECTIONS = 4
REQUIRED_COMMANDS = [r"\\resumeSubheading", r"\\resumeItem", r"\\resumeProjectHeading"]
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff\uff66-\uff9f\uac00-\ud7af\u1100-\u11ff]")
AUX_EXTS = [".aux", ".log", ".out", ".fls", ".fdb_latexmk", ".synctex.gz"]


Runner = Callable[[list[str], Path, int], subprocess.CompletedProcess[str]]


def validate_latex_content(content: str, compile_only: bool = False) -> dict[str, Any]:
    issues: list[str] = []
    if r"\begin{document}" not in content:
        issues.append(r"Missing \begin{document}")
    if r"\end{document}" not in content:
        issues.append(r"Missing \end{document}")
    if compile_only:
        return {"issues": issues, "counts": {"resumeItems": 0, "subheadings": 0, "projectHeadings": 0}}

    section_count = len(re.findall(r"\\section\{", content))
    if section_count < MIN_SECTIONS:
        issues.append(
            f"Expected at least {MIN_SECTIONS} \\section{{}} blocks "
            f"(Education, Work Experience, Projects, Skills — or localized equivalents), found {section_count}"
        )
    if CJK_RE.search(content):
        issues.append(
            "CJK characters detected. The LaTeX template does not support Japanese/Chinese/Korean yet "
            "(pdfLaTeX setup with no CJK font). Use `pdf` mode (HTML to PDF, which renders CJK) for these CVs."
        )
    for command in REQUIRED_COMMANDS:
        if not re.search(command, content):
            issues.append(f"Missing command: {command}")
    unresolved = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", content)))
    if unresolved:
        issues.append(f"Unresolved placeholders: {', '.join(unresolved)}")
    if r"\pdfgentounicode=1" not in content:
        issues.append(r"Missing \pdfgentounicode=1 (ATS compatibility)")

    counts = {
        "resumeItems": len([line for line in content.splitlines() if re.search(r"\\resumeItem\{", line)]),
        "subheadings": len([line for line in content.splitlines() if re.search(r"\\resumeSubheading(?!Continue)", line)]),
        "projectHeadings": len([line for line in content.splitlines() if re.search(r"\\resumeProjectHeading", line)]),
    }
    return {"issues": issues, "counts": counts}


def default_runner(args: list[str], cwd: Path, timeout_ms: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout_ms / 1000, check=True)


def find_engine(runner: Runner = default_runner) -> str | None:
    for candidate in ["tectonic", "pdflatex"]:
        try:
            runner([candidate, "--version"], Path.cwd(), 120_000)
            return candidate
        except Exception:
            continue
    return None


def extract_latex_error(log_path: Path, fallback: str) -> str:
    try:
        lines = [line for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines() if line.startswith("!")]
    except Exception:
        lines = []
    return "\n".join(lines) if lines else fallback


def cleanup_aux_files(directory: Path, base_name: str) -> None:
    for ext in AUX_EXTS:
        (directory / f"{base_name}{ext}").unlink(missing_ok=True)


def compile_latex_file(
    input_path: str | Path,
    content: str | None = None,
    output_path: str | Path | None = None,
    compile_only: bool = False,
    *,
    runner: Runner = default_runner,
    engine: str | None = None,
) -> dict[str, Any]:
    abs_path = Path(input_path).resolve(strict=False)
    text = content if content is not None else abs_path.read_text(encoding="utf-8")
    validation = validate_latex_content(text, compile_only)
    report: dict[str, Any] = {
        "file": abs_path.name,
        "path": str(abs_path),
        "sizeKB": round(abs_path.stat().st_size / 1024, 1) if abs_path.exists() else round(len(text.encode("utf-8")) / 1024, 1),
        "counts": validation["counts"],
        "issues": validation["issues"],
        "valid": not validation["issues"],
        "compileOnly": compile_only,
    }
    if validation["issues"]:
        return report

    tex_dir = abs_path.parent
    tex_base = abs_path.stem
    target_pdf = Path(output_path).resolve(strict=False) if output_path else tex_dir / f"{tex_base}.pdf"
    target_pdf.parent.mkdir(parents=True, exist_ok=True)
    selected_engine = engine or find_engine(runner)
    if not selected_engine:
        report["compiled"] = False
        report["compileError"] = "No LaTeX engine found. Install tectonic (brew install tectonic) or pdflatex."
        return report
    report["engine"] = selected_engine

    compile_path = abs_path
    if selected_engine == "tectonic":
        patched = re.sub(r"\\pdfgentounicode\s*=\s*\d+[^\n]*\n?", "", text)
        patched = re.sub(r"\\input\{glyphtounicode\}[^\n]*\n?", "", patched)
        compile_path = tex_dir / f"{tex_base}._tectonic.tex"
        compile_path.write_text(patched, encoding="utf-8")

    try:
        if selected_engine == "tectonic":
            runner(["tectonic", "--outdir", str(tex_dir), str(compile_path)], tex_dir, 120_000)
        else:
            args = [
                "pdflatex",
                "-no-shell-escape",
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-output-directory={tex_dir}",
                str(abs_path),
            ]
            runner(args, tex_dir, 120_000)
            runner(args, tex_dir, 120_000)
        report["compiled"] = True
    except Exception as error:
        report["compiled"] = False
        report["compileError"] = extract_latex_error(tex_dir / f"{tex_base}.log", str(error))

    if report.get("compiled"):
        compile_base = compile_path.stem
        compiled_pdf = tex_dir / f"{compile_base}.pdf"
        try:
            shutil.copyfile(compiled_pdf, target_pdf)
            if compiled_pdf.resolve(strict=False) != target_pdf.resolve(strict=False):
                compiled_pdf.unlink(missing_ok=True)
            report["pdf"] = {"path": str(target_pdf), "sizeKB": round(target_pdf.stat().st_size / 1024, 1)}
        except Exception as error:
            report["postCompileError"] = f"Failed to finalize PDF: {error}"
        cleanup_aux_files(tex_dir, compile_base)
        if selected_engine == "tectonic":
            compile_path.unlink(missing_ok=True)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and compile a generated .tex CV file to PDF.")
    parser.add_argument("input")
    parser.add_argument("output", nargs="?")
    parser.add_argument("--compile-only", action="store_true")
    args = parser.parse_args(argv)
    path = Path(args.input)
    if not path.exists():
        print(f"Error reading {path.resolve(strict=False)}: file not found")
        return 1
    report = compile_latex_file(path, output_path=args.output, compile_only=args.compile_only)
    print(json.dumps(report, indent=2))
    return 0 if report.get("compiled") else 1


if __name__ == "__main__":
    raise SystemExit(main())
