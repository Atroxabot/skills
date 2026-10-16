#!/usr/bin/env python3
"""Audit a React Router web app for the mechanical problems this skill rules out.

Checks:
  - react-router is on the latest npm version, every @react-router/* package
    matches it, and nothing still depends on react-router-dom or @remix-run/*
  - react-router.config: SSR not switched off for the whole app
  - tsconfig: strict mode and noUncheckedIndexedAccess
  - global CSS stays under a line budget; components don't import global CSS
  - no data fetching inside useEffect
  - type escapes: any, @ts-ignore, @ts-nocheck
  - unstable_ React Router APIs used without a comment
  - filler tests: snapshots, "renders without crashing", no assertions,
    .skip/.only left in

Usage:
    python3 audit_webapp.py path/to/app
    python3 audit_webapp.py path/to/app --json
    python3 audit_webapp.py path/to/app --strict         # warnings fail too
    python3 audit_webapp.py path/to/app --offline        # skip the npm lookup
    python3 audit_webapp.py path/to/app --global-css-budget 250

A finding means "look at this", not "this is wrong". Some have good reasons
(a :global override for a third-party widget, an any in a generated file);
leave those with a comment explaining why.

Exit code: 1 if there are errors (or warnings with --strict), else 0.
Standard library only.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {
    "node_modules", ".git", "build", "dist", ".react-router", "coverage",
    "playwright-report", "test-results", ".cache", ".vercel", ".netlify",
}
TOP_LEVEL_SKIP = {"public"}  # static assets; a route folder named "public" is still scanned
CODE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mts", ".mjs"}
TEST_RE = re.compile(r"\.(test|spec)\.(t|j)sx?$")


class Report:
    def __init__(self):
        self.findings = []

    def add(self, severity, check, message, path=None, line=None):
        self.findings.append(
            {"severity": severity, "check": check, "message": message,
             "path": str(path) if path else None, "line": line}
        )

    def count(self, severity):
        return sum(1 for f in self.findings if f["severity"] == severity)


def walk(root):
    for path in root.rglob("*"):
        parts = path.relative_to(root).parts
        if any(part in SKIP_DIRS for part in parts) or parts[0] in TOP_LEVEL_SKIP:
            continue
        if path.is_file():
            yield path


def read(path):
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def strip_jsonc(text):
    """Remove // and /* */ comments and trailing commas so tsconfig parses."""
    out, i, in_str = [], 0, False
    while i < len(text):
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\":
                out.append(text[i + 1 : i + 2])
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif text.startswith("//", i):
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = len(text) if end == -1 else end + 2
            continue
        else:
            out.append(c)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def parse_version(spec):
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", spec or "")
    return tuple(int(x) for x in m.groups()) if m else None


def latest_npm_version(package):
    try:
        out = subprocess.run(
            ["npm", "view", package, "version"],
            capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def installed_version(root, package):
    pkg = root / "node_modules" / package / "package.json"
    if pkg.exists():
        try:
            return json.loads(read(pkg)).get("version")
        except json.JSONDecodeError:
            return None
    return None


# --- checks -----------------------------------------------------------------


def check_dependencies(root, report, offline):
    pkg_path = root / "package.json"
    if not pkg_path.exists():
        report.add("error", "deps", "no package.json found; is this the app root?")
        return
    try:
        pkg = json.loads(read(pkg_path))
    except json.JSONDecodeError as e:
        report.add("error", "deps", f"package.json does not parse: {e}", pkg_path)
        return

    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

    if "react-router-dom" in deps:
        report.add("error", "deps",
                   "react-router-dom is a dependency; since v8 everything comes from "
                   "react-router and react-router/dom", pkg_path)
    remix = sorted(d for d in deps if d.startswith("@remix-run/"))
    if remix:
        report.add("error", "deps",
                   f"Remix packages still installed ({', '.join(remix)}); migrate to "
                   "react-router and @react-router/*", pkg_path)

    if "react-router" not in deps:
        report.add("error", "deps", "react-router is not a dependency", pkg_path)
        return

    current = installed_version(root, "react-router") or deps["react-router"]
    current_v = parse_version(current)

    for name in sorted(d for d in deps if d.startswith("@react-router/")):
        other = installed_version(root, name) or deps[name]
        if parse_version(other) != current_v:
            report.add("error", "deps",
                       f"{name} is {other} but react-router is {current}; keep them "
                       "on the same version", pkg_path)

    if offline:
        return
    latest = latest_npm_version("react-router")
    if latest is None:
        report.add("note", "deps",
                   "could not reach npm to check the latest react-router version "
                   "(rerun online, or pass --offline to silence this)")
        return
    latest_v = parse_version(latest)
    if current_v and latest_v and current_v < latest_v:
        severity = "error" if current_v[0] < latest_v[0] else "warning"
        report.add(severity, "deps",
                   f"react-router {current} is behind the latest {latest}", pkg_path)


def check_config(root, report):
    for name in ("react-router.config.ts", "react-router.config.js", "react-router.config.mjs"):
        path = root / name
        if path.exists():
            text = read(path)
            m = re.search(r"\bssr\s*:\s*false\b", text)
            if m:
                report.add("warning", "ssr",
                           "ssr is false for the whole app; server-render by default and "
                           "use clientLoader or React.lazy for browser-only parts",
                           path, line_of(text, m.start()))
            return
    report.add("note", "ssr",
               "no react-router.config found; framework mode expects one")


def check_tsconfig(root, report):
    path = root / "tsconfig.json"
    if not path.exists():
        report.add("warning", "types", "no tsconfig.json found")
        return
    try:
        cfg = json.loads(strip_jsonc(read(path)))
    except json.JSONDecodeError:
        report.add("note", "types", "tsconfig.json could not be parsed; check it by hand", path)
        return
    opts = cfg.get("compilerOptions", {})
    if opts.get("strict") is not True:
        report.add("error", "types", "compilerOptions.strict is not true", path)
    if opts.get("noUncheckedIndexedAccess") is not True:
        report.add("warning", "types", "compilerOptions.noUncheckedIndexedAccess is not true", path)


def check_css(root, files, report, budget):
    global_css = [f for f in files if f.suffix == ".css" and not f.name.endswith(".module.css")]
    total = 0
    for f in global_css:
        lines = sum(1 for ln in read(f).splitlines() if ln.strip())
        total += lines
    if total > budget:
        names = ", ".join(str(f.relative_to(root)) for f in global_css)
        report.add("warning", "css",
                   f"global CSS is {total} non-empty lines (budget {budget}) across: "
                   f"{names}; move component styles into .module.css files")

    import_re = re.compile(r"""import\s+(?:[\w*{}\s,]+from\s+)?["']([^"']+\.css)(\?[^"']*)?["']""")
    for f in files:
        if f.suffix not in CODE_EXT or TEST_RE.search(f.name):
            continue
        if f.stem in ("root", "entry.client", "entry.server"):
            continue
        text = read(f)
        for m in import_re.finditer(text):
            spec = m.group(1)
            if not spec.endswith(".module.css"):
                report.add("warning", "css",
                           f"imports global stylesheet '{spec}'; only root.tsx imports "
                           "global CSS, components use .module.css",
                           f.relative_to(root), line_of(text, m.start()))

    for f in files:
        if f.name.endswith(".module.css"):
            text = read(f)
            for m in re.finditer(r":global\b", text):
                start = max(0, text.rfind("\n", 0, m.start()) - 200)
                if "/*" not in text[start : m.start()]:
                    report.add("note", "css",
                               ":global without a nearby comment saying which library it targets",
                               f.relative_to(root), line_of(text, m.start()))


EFFECT_RE = re.compile(r"useEffect\s*\(")
FETCH_IN_EFFECT_RE = re.compile(r"\b(fetch|axios(\.\w+)?|ky(\.\w+)?)\s*\(")
ANY_RE = re.compile(r"(?::\s*any\b(?!\w)|\bas\s+any\b|<any>|\bany\[\])")
TS_IGNORE_RE = re.compile(r"@ts-(ignore|nocheck)\b")
UNSTABLE_RE = re.compile(r"\bunstable_\w+")


def effect_body(text, start):
    """Return the text of the useEffect call starting at `start` (balanced parens)."""
    depth, i = 0, text.index("(", start)
    begin = i
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[begin : i + 1]
        i += 1
    return text[begin:]


def check_code(root, files, report):
    for f in files:
        if f.suffix not in CODE_EXT or f.name.endswith(".d.ts"):
            continue
        rel = f.relative_to(root)
        text = read(f)
        is_test = bool(TEST_RE.search(f.name))

        if not is_test:
            for m in EFFECT_RE.finditer(text):
                body = effect_body(text, m.start())
                if FETCH_IN_EFFECT_RE.search(body):
                    report.add("warning", "data",
                               "data fetching inside useEffect; load it in a loader or "
                               "clientLoader instead", rel, line_of(text, m.start()))

            for m in re.finditer(r"""from\s+["']react-router-dom["']""", text):
                report.add("error", "deps", "imports from react-router-dom",
                           rel, line_of(text, m.start()))

            for m in UNSTABLE_RE.finditer(text):
                ln = line_of(text, m.start())
                lines = text.splitlines()
                context = " ".join(lines[max(0, ln - 3) : ln])
                if "//" not in context and "/*" not in context:
                    report.add("note", "api",
                               f"{m.group(0)} is an unstable API; keep it only with a comment "
                               "recording the decision", rel, ln)

        for m in ANY_RE.finditer(text):
            report.add("warning", "types", "explicit any", rel, line_of(text, m.start()))
        for m in TS_IGNORE_RE.finditer(text):
            report.add("warning", "types",
                       f"@ts-{m.group(1)}; use @ts-expect-error with a reason, or fix the type",
                       rel, line_of(text, m.start()))

        if is_test:
            check_test_file(rel, text, report)


TEST_CALL_RE = re.compile(r"\b(it|test)(\.only|\.skip|\.todo)?\s*\(\s*([\"'`])(.*?)\3", re.S)
FILLER_NAME_RE = re.compile(
    r"renders?( correctly| properly| successfully)?$|renders? without (crashing|errors?)|"
    r"should render$|is defined$|exists$|matches snapshot", re.I)


def check_test_file(rel, text, report):
    for m in re.finditer(r"\.toMatch(Inline)?Snapshot\s*\(", text):
        report.add("warning", "tests",
                   "snapshot assertion; assert the specific output that matters",
                   rel, line_of(text, m.start()))

    calls = list(TEST_CALL_RE.finditer(text))
    for idx, m in enumerate(calls):
        modifier, name = m.group(2), m.group(4)
        ln = line_of(text, m.start())
        if modifier == ".only":
            report.add("error", "tests", f"it.only left in: '{name}'", rel, ln)
        elif modifier == ".skip":
            report.add("warning", "tests", f"skipped test: '{name}'; fix or delete it", rel, ln)
        if FILLER_NAME_RE.search(name.strip()):
            report.add("warning", "tests",
                       f"'{name}' looks like a filler test; test behavior a user relies on",
                       rel, ln)
        end = calls[idx + 1].start() if idx + 1 < len(calls) else len(text)
        body = text[m.end() : end]
        if modifier != ".todo" and not re.search(r"\bexpect\b|\bassert\b|toBeVisible|toHave", body):
            report.add("warning", "tests", f"'{name}' has no assertion", rel, ln)


# --- main -------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("app", nargs="?", default=".", help="app root (where package.json is)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--strict", action="store_true", help="warnings fail the run too")
    ap.add_argument("--offline", action="store_true", help="skip the npm latest-version check")
    ap.add_argument("--global-css-budget", type=int, default=300,
                    help="max non-empty lines across global CSS files (default 300)")
    args = ap.parse_args()

    root = Path(args.app).resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2

    report = Report()
    files = list(walk(root))
    check_dependencies(root, report, args.offline)
    check_config(root, report)
    check_tsconfig(root, report)
    check_css(root, files, report, args.global_css_budget)
    check_code(root, files, report)

    for f in report.findings:
        if f["path"] and Path(f["path"]).is_absolute():
            f["path"] = str(Path(f["path"]).relative_to(root))

    order = {"error": 0, "warning": 1, "note": 2}
    report.findings.sort(key=lambda f: (order[f["severity"]], f["check"], f["path"] or "", f["line"] or 0))

    if args.json:
        print(json.dumps({"root": str(root), "findings": report.findings}, indent=2))
    else:
        for f in report.findings:
            where = f["path"] or ""
            if f["line"]:
                where += f":{f['line']}"
            prefix = f"{f['severity'].upper():7} [{f['check']}]"
            print(f"{prefix} {where + ' ' if where else ''}{f['message']}")
        print(f"\n{report.count('error')} errors, {report.count('warning')} warnings, "
              f"{report.count('note')} notes")

    failed = report.count("error") > 0 or (args.strict and report.count("warning") > 0)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
