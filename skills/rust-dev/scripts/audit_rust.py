#!/usr/bin/env python3
"""Audit a Rust crate or workspace for the mechanical rule breaks this skill rules out.

Checks:
  manifests
    - edition 2024 on every package
    - banned direct dependencies (error crates, lazy_static/once_cell, GUI
      frameworks and non-wgpu renderers, async-std, atty)
    - direct dependencies that are neither on the allowlist nor justified
      with a `# why:` comment on (or just above) their line
    - tokio with the "full" feature
    - a lint table (own or inherited from the workspace) with the key
      panic and unsafe lints
    - release profile: lto, codegen-units = 1, panic = "abort",
      overflow-checks = true (when the project builds a binary)
    - a sizable single-crate project that should be a workspace
  project files
    - rust-toolchain.toml pinned to an exact stable version; clippy.toml; deny.toml
  source (non-test code: tests/, benches/, examples/, fuzz/, build.rs and
  #[cfg(test)] items are skipped)
    - unwrap(), expect(), panic!, todo!, unimplemented!, unreachable!,
      assert! (debug_assert! and compile-time const asserts are fine), dbg!
    - unsafe blocks and impls without a SAFETY comment, unsafe fn/trait
      without a "# Safety" doc section, static mut
    - #[allow(...)] (use #[expect(..., reason = "...")]); #[expect] without reason
    - Box<dyn Error>, process::exit, #[tokio::main], lazy_static!,
      use of error crates
    - print!/println!/eprint!/eprintln! in library crates
    - TODO / FIXME / XXX comments

Usage:
    python3 audit_rust.py path/to/project
    python3 audit_rust.py path/to/project --json
    python3 audit_rust.py path/to/project --strict     # warnings fail too
    python3 audit_rust.py path/to/project --cargo      # also run fmt, clippy, test

A finding means "look at this". Clippy enforces the same panic rules
precisely; this script also covers the policies Clippy can't (dependencies,
toolchain, profiles) and works without compiling.

Exit code: 1 if there are errors (or warnings with --strict), else 0.
Standard library only (Python 3.11+ for tomllib).
"""

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

SKIP_DIRS = {"target", ".git", "node_modules", "vendor", ".cargo"}
NON_SHIPPED_DIRS = {"tests", "benches", "examples", "fuzz"}

# Mirrors references/dependencies.md. Keep the two in sync.
ALLOWED = {
    # GUI and rendering
    "wgpu", "winit", "bytemuck", "pollster", "glam", "fontdue", "cosmic-text",
    "png", "zune-jpeg",
    # concurrency
    "rayon", "rtrb", "crossbeam-queue", "core_affinity",
    # async and networking
    "tokio", "tokio-util", "hyper", "hyper-util", "http", "http-body-util",
    "bytes", "axum", "rustls", "tokio-rustls", "webpki-roots",
    # security
    "ring", "sha2", "hmac", "blake3", "subtle",
    # data, observability, CLI
    "serde", "serde_json", "tracing", "tracing-subscriber", "lexopt",
    # embedded
    "cortex-m", "cortex-m-rt", "embedded-hal", "embedded-hal-async",
    "embedded-io", "critical-section", "heapless", "defmt", "defmt-rtt",
    "panic-probe", "rtic",
    # dev and test
    "criterion", "proptest", "libfuzzer-sys", "arbitrary", "naga",
    "embedded-test", "defmt-test",
}
ALLOWED_PATTERNS = [
    re.compile(p) for p in (
        r"^embassy-", r"^stm32", r"^nrf", r"^rp2040-", r"^rp235x-", r"^esp-",
    )
]

BANNED = {
    "thiserror": "write error types by hand (references/errors.md)",
    "anyhow": "write error types by hand (references/errors.md)",
    "eyre": "write error types by hand (references/errors.md)",
    "color-eyre": "write error types by hand (references/errors.md)",
    "snafu": "write error types by hand (references/errors.md)",
    "quick-error": "write error types by hand (references/errors.md)",
    "displaydoc": "write error types by hand (references/errors.md)",
    "failure": "write error types by hand (references/errors.md)",
    "error-chain": "write error types by hand (references/errors.md)",
    "lazy_static": "use std::sync::LazyLock",
    "once_cell": "use std::sync::OnceLock / LazyLock",
    "async-std": "discontinued; use tokio, or threads",
    "atty": "use std::io::IsTerminal",
}
GUI_BANNED = {
    "egui", "eframe", "egui-wgpu", "egui-winit", "egui_extras", "iced", "slint",
    "gtk", "gtk4", "relm4", "tauri", "druid", "xilem", "masonry", "floem",
    "vizia", "freya", "dioxus", "gpui", "fltk", "makepad-widgets", "imgui",
    "bevy", "macroquad", "ggez", "fyrox", "pixels", "softbuffer", "minifb",
    "glium", "glow", "glutin", "gl", "sdl2", "sdl3", "raylib", "vulkano", "ash",
}
GUI_BANNED_PATTERNS = [re.compile(r"^dear-imgui"), re.compile(r"^imgui-"),
                       re.compile(r"^bevy_"), re.compile(r"^egui_")]

REQUIRED_CLIPPY = ["unwrap_used", "expect_used", "panic", "indexing_slicing",
                   "undocumented_unsafe_blocks", "allow_attributes_without_reason"]
DEP_SECTIONS = ("dependencies", "dev-dependencies", "build-dependencies")
WORKSPACE_LINE_THRESHOLD = 5000


class Report:
    def __init__(self, root):
        self.root = root
        self.findings = []

    def add(self, severity, check, message, path=None, line=None):
        if path is not None:
            try:
                path = Path(path).resolve().relative_to(self.root)
            except ValueError:
                pass
        self.findings.append({"severity": severity, "check": check, "message": message,
                              "path": str(path) if path else None, "line": line})

    def count(self, severity):
        return sum(1 for f in self.findings if f["severity"] == severity)


# ---------------------------------------------------------------- manifests

def load_toml(path, report):
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        report.add("error", "manifest", f"cannot parse: {exc}", path)
        return None


def find_manifests(root):
    found = []
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for e in entries:
            if e.is_dir():
                if e.name not in SKIP_DIRS and not e.name.startswith("."):
                    stack.append(e)
            elif e.name == "Cargo.toml":
                found.append(e)
    return sorted(found)


def is_allowed(name):
    return name in ALLOWED or any(p.search(name) for p in ALLOWED_PATTERNS)


def banned_reason(name):
    if name in BANNED:
        return BANNED[name]
    if name in GUI_BANNED or any(p.search(name) for p in GUI_BANNED_PATTERNS):
        return "GUIs are built on raw wgpu + winit (references/gui-wgpu.md)"
    return None


def dep_decl_line(lines, key):
    """Index of the line declaring dependency `key` inside a *dependencies table, or None."""
    section = ""
    key_re = re.compile(r"^\s*" + re.escape(key) + r"\s*(=|\.)")
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        header = re.match(r"^\[(.+)\]\s*(#.*)?$", stripped)
        if header:
            section = header.group(1).replace('"', "").replace("'", "")
            parts = section.split(".")
            if parts[-1] == key and len(parts) >= 2 and parts[-2].endswith("dependencies"):
                return i
            continue
        if section.split(".")[-1].endswith("dependencies") and key_re.match(raw):
            return i
    return None


def has_why(lines, idx):
    if idx is None:
        return False
    if re.search(r"#\s*why:", lines[idx], re.I):
        return True
    return idx > 0 and re.match(r"^\s*#.*why:", lines[idx - 1], re.I) is not None


def iter_dep_tables(manifest):
    for sec in DEP_SECTIONS:
        table = manifest.get(sec)
        if isinstance(table, dict):
            yield sec, table
    for target in (manifest.get("target") or {}).values():
        if isinstance(target, dict):
            for sec in DEP_SECTIONS:
                table = target.get(sec)
                if isinstance(table, dict):
                    yield sec, table


def real_name(key, spec):
    if isinstance(spec, dict) and isinstance(spec.get("package"), str):
        return spec["package"]
    return key


def check_dependencies(path, manifest, lines, root_ws_deps, root_lines, root_path, report):
    for sec, table in iter_dep_tables(manifest):
        for key, spec in table.items():
            is_ws = isinstance(spec, dict) and spec.get("workspace") is True
            ws_spec = root_ws_deps.get(key) if is_ws else None
            effective = ws_spec if is_ws else spec
            if isinstance(effective, dict) and "path" in effective:
                continue  # an internal crate
            name = real_name(key, effective if effective is not None else spec)
            idx = dep_decl_line(lines, key)
            reason = banned_reason(name)
            if reason:
                report.add("error", "banned-dependency", f"`{name}` is banned: {reason}",
                           path, idx + 1 if idx is not None else None)
                continue
            features = []
            for s in (spec, effective):
                if isinstance(s, dict):
                    features += s.get("features", [])
            if name == "tokio" and "full" in features:
                report.add("warning", "tokio-full",
                           "tokio with the \"full\" feature; enable only the features used",
                           path, idx + 1 if idx is not None else None)
            if is_allowed(name):
                continue
            justified = has_why(lines, idx)
            if not justified and is_ws and root_lines is not None:
                justified = has_why(root_lines, dep_decl_line(root_lines, key))
            if not justified:
                report.add("error", "unjustified-dependency",
                           f"`{name}` ({sec}) is not on the allowlist and has no `# why:` comment",
                           path, idx + 1 if idx is not None else None)


def resolve(pkg, field, root_ws_pkg):
    value = pkg.get(field)
    if isinstance(value, dict) and value.get("workspace") is True:
        return root_ws_pkg.get(field)
    return value


def check_lints(path, manifest, root_manifest, report):
    lints = manifest.get("lints")
    if lints is None:
        report.add("error", "lints", "no [lints] table; copy the lint set from "
                   "references/code-standards.md (or `[lints] workspace = true`)", path)
        return
    if lints.get("workspace") is True:
        lints = ((root_manifest or {}).get("workspace") or {}).get("lints")
        if not lints:
            report.add("error", "lints", "`lints.workspace = true` but the root has no "
                       "[workspace.lints]", path)
            return
    rust = lints.get("rust") or {}
    clippy = lints.get("clippy") or {}

    def level(v):
        return v.get("level") if isinstance(v, dict) else v

    if level(rust.get("unsafe_code")) not in ("deny", "forbid"):
        report.add("warning", "lints", "rust lint `unsafe_code` should be deny", path)
    missing = [l for l in REQUIRED_CLIPPY if level(clippy.get(l)) not in ("deny", "forbid")]
    if missing:
        report.add("warning", "lints", "clippy lints not denied: " + ", ".join(missing), path)
    if level(clippy.get("pedantic")) not in ("deny", "warn"):
        report.add("warning", "lints", "clippy::pedantic is not enabled", path)


def package_has_binary(pkg_dir, manifest):
    return ((pkg_dir / "src" / "main.rs").exists() or (pkg_dir / "src" / "bin").is_dir()
            or bool(manifest.get("bin")))


def package_is_library_only(pkg_dir, manifest):
    return (pkg_dir / "src" / "lib.rs").exists() and not package_has_binary(pkg_dir, manifest)


def check_profile(root_path, root_manifest, report):
    release = ((root_manifest.get("profile") or {}).get("release")) or {}
    if release.get("lto") not in ("fat", True):
        report.add("warning", "profile", "[profile.release] lto should be \"fat\"", root_path)
    if release.get("codegen-units") != 1:
        report.add("warning", "profile", "[profile.release] codegen-units should be 1", root_path)
    if release.get("panic") != "abort":
        report.add("warning", "profile", "[profile.release] panic should be \"abort\"", root_path)
    if release.get("overflow-checks") is not True:
        report.add("warning", "profile", "[profile.release] overflow-checks should be true",
                   root_path)


def check_project_files(root, report):
    tc = root / "rust-toolchain.toml"
    legacy = root / "rust-toolchain"
    if not tc.exists() and not legacy.exists():
        report.add("warning", "toolchain", "no rust-toolchain.toml pinning an exact stable "
                   "version", root)
    elif tc.exists():
        data = load_toml(tc, report) or {}
        channel = str((data.get("toolchain") or {}).get("channel", ""))
        if "nightly" in channel:
            report.add("error", "toolchain", f"toolchain channel is `{channel}`; ship on "
                       "stable (nightly only to run tools)", tc)
        elif not re.match(r"^\d+\.\d+\.\d+$", channel):
            report.add("warning", "toolchain", f"toolchain channel `{channel}` is not an exact "
                       "version like 1.97.0", tc)
    if not (root / "clippy.toml").exists() and not (root / ".clippy.toml").exists():
        report.add("warning", "clippy-config", "no clippy.toml (tests need allow-unwrap-in-tests "
                   "and friends, and the 60-line function limit)", root)
    if not (root / "deny.toml").exists():
        report.add("warning", "cargo-deny", "no deny.toml for `cargo deny check`", root)


# ---------------------------------------------------------------- source

def strip_rust(src):
    """Blank out comments and string/char literal contents, keeping offsets and newlines.

    Returns (code, comments) where comments is a list of (line_number, text).
    """
    out = list(src)
    comments = []
    i, n = 0, len(src)
    line = 1

    def blank(a, b):
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        c = src[i]
        if c == "\n":
            line += 1
            i += 1
            continue
        nxt = src[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = src.find("\n", i)
            j = n if j == -1 else j
            comments.append((line, src[i:j]))
            blank(i, j)
            i = j
            continue
        if c == "/" and nxt == "*":
            depth, j, start_line = 1, i + 2, line
            while j < n and depth:
                if src.startswith("/*", j):
                    depth += 1
                    j += 2
                elif src.startswith("*/", j):
                    depth -= 1
                    j += 2
                else:
                    j += 1
            text = src[i:j]
            comments.append((start_line, text))
            line += text.count("\n")
            blank(i, j)
            i = j
            continue
        prev = src[i - 1] if i > 0 else ""
        m = None
        if not (prev.isalnum() or prev == "_"):
            m = re.match(r'(?:b|c)?r(#*)"', src[i:i + 300])
        if m:
            hashes = m.group(1)
            start = i + m.end()
            end = src.find('"' + hashes, start)
            end = n if end == -1 else end
            line += src[start:end].count("\n")
            blank(start, end)
            i = end + 1 + len(hashes)
            continue
        if c == '"' or (c in "bc" and nxt == '"' and not (prev.isalnum() or prev == "_")):
            j = i + 1 if c == '"' else i + 2
            start = j
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            line += src[start:j].count("\n")
            blank(start, j)
            i = j + 1
            continue
        if c == "'":
            if nxt == "\\":
                j = src.find("'", i + 2)
                if j != -1 and j - i < 14:
                    blank(i + 1, j)
                    i = j + 1
                    continue
            elif i + 2 < n and src[i + 2] == "'" and nxt != "\n":
                blank(i + 1, i + 2)
                i += 3
                continue
        i += 1
    return "".join(out), comments


def matching_brace(code, open_idx):
    depth = 0
    for k in range(open_idx, len(code)):
        if code[k] == "{":
            depth += 1
        elif code[k] == "}":
            depth -= 1
            if depth == 0:
                return k
    return len(code) - 1


def test_regions(code):
    """Character ranges of items annotated #[cfg(test)] (modules, functions, impls)."""
    regions = []
    for m in re.finditer(r"#\[\s*cfg\s*\(\s*test\s*\)\s*\]", code):
        j = m.end()
        brace = code.find("{", j)
        semi = code.find(";", j)
        if brace == -1:
            continue
        if semi != -1 and semi < brace:
            regions.append((m.start(), semi))  # e.g. `mod tests;` or a use
            continue
        regions.append((m.start(), matching_brace(code, brace)))
    return regions


SOURCE_RULES = [
    (re.compile(r"\.unwrap\(\)"), "error", "panic", "`.unwrap()` in non-test code"),
    (re.compile(r"\.expect\("), "error", "panic", "`.expect(...)` in non-test code"),
    (re.compile(r"\b(panic|todo|unimplemented|unreachable)!"), "error", "panic",
     "`{0}!` in non-test code"),
    (re.compile(r"(?<![\w_])assert(_eq|_ne)?!"), "error", "panic",
     "`assert{0}!` in non-test code (use debug_assert!, a type, or a Result)"),
    (re.compile(r"\bdbg!"), "error", "debug", "`dbg!` left in"),
    (re.compile(r"\bstatic\s+mut\b"), "error", "unsafe", "`static mut`; use atomics, "
     "OnceLock, Mutex or critical_section::Mutex"),
    (re.compile(r"\blazy_static!"), "error", "dependency", "`lazy_static!`; use LazyLock"),
    (re.compile(r"\b(thiserror|anyhow|eyre|snafu)::|\banyhow!|\bbail!"), "error",
     "error-crate", "error crate used; write error types by hand"),
    (re.compile(r"#!?\[\s*allow\s*\("), "warning", "allow",
     "`#[allow]`; use `#[expect(lint, reason = \"...\")]`"),
    (re.compile(r"Box\s*<\s*dyn\s+(std::error::|core::error::)?Error\b"), "warning",
     "boxed-error", "`Box<dyn Error>`; use a hand-written error type"),
    (re.compile(r"\bprocess::exit\s*\("), "warning", "exit",
     "`process::exit` skips destructors; return ExitCode from main"),
    (re.compile(r"#\[\s*tokio::main"), "warning", "runtime",
     "`#[tokio::main]`; build the runtime explicitly with chosen workers and thread names"),
]
PRINT_RULE = re.compile(r"\b(e?print(ln)?)!")
EXPECT_ATTR = re.compile(r"#!?\[\s*expect\s*\(([^\]]*)\)\s*\]")
UNSAFE_BLOCK = re.compile(r"\bunsafe\s*\{")
UNSAFE_IMPL = re.compile(r"\bunsafe\s+impl\b")
UNSAFE_FN = re.compile(r"\bunsafe\s+(extern\s+\"[^\"]*\"\s+)?(fn|trait)\b")


def line_of(code, idx):
    return code.count("\n", 0, idx) + 1


def safety_comment_near(raw_lines, lineno, span=4):
    lo = max(0, lineno - 1 - span)
    for k in range(lineno - 1, lo - 1, -1):
        if "SAFETY:" in raw_lines[k]:
            return True
    return False


def safety_doc_above(raw_lines, lineno):
    k = lineno - 2
    while k >= 0:
        s = raw_lines[k].strip()
        if s.startswith("///") or s.startswith("#[") or s.startswith("//!"):
            if "# Safety" in s:
                return True
            k -= 1
            continue
        break
    return False


def scan_file(path, library_only, report):
    try:
        src = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        report.add("warning", "read", f"cannot read: {exc}", path)
        return
    code, comments = strip_rust(src)
    if re.search(r"#!\[\s*cfg\s*\(\s*test\s*\)\s*\]", code):
        return
    raw_lines = src.split("\n")
    regions = test_regions(code)

    def in_test(idx):
        return any(a <= idx <= b for a, b in regions)

    code_lines = code.split("\n")
    for rx, sev, check, msg in SOURCE_RULES:
        for m in rx.finditer(code):
            if in_test(m.start()):
                continue
            ln = line_of(code, m.start())
            if check == "panic" and "assert" in m.group(0):
                # Compile-time asserts in const items can't panic at run time.
                if re.search(r"\bconst\b", code_lines[ln - 1]):
                    continue
            groups = [g or "" for g in m.groups()] if m.groups() else []
            report.add(sev, check, msg.format(*groups) if groups else msg, path, ln)
    for m in EXPECT_ATTR.finditer(code):
        if not in_test(m.start()) and "reason" not in m.group(1):
            report.add("warning", "allow", "`#[expect]` without `reason = \"...\"`", path,
                       line_of(code, m.start()))
    for rx, need in ((UNSAFE_BLOCK, "comment"), (UNSAFE_IMPL, "comment"), (UNSAFE_FN, "doc")):
        for m in rx.finditer(code):
            if in_test(m.start()):
                continue
            ln = line_of(code, m.start())
            if need == "comment" and not safety_comment_near(raw_lines, ln):
                report.add("error", "unsafe", "unsafe without a `// SAFETY:` comment", path, ln)
            if need == "doc" and "unsafe extern" not in m.group(0) and \
                    not safety_doc_above(raw_lines, ln):
                report.add("error", "unsafe", "`unsafe fn`/`unsafe trait` without a "
                           "`# Safety` doc section", path, ln)
    if library_only:
        for m in PRINT_RULE.finditer(code):
            if not in_test(m.start()):
                report.add("warning", "print", f"`{m.group(1)}!` in a library crate; return "
                           "data or errors instead", path, line_of(code, m.start()))
    for ln, text in comments:
        if re.search(r"\b(TODO|FIXME|XXX)\b", text):
            report.add("warning", "todo", "TODO/FIXME/XXX comment; do it or reference an issue",
                       path, ln)


def rust_files(pkg_dir, nested_pkg_dirs):
    files = []
    stack = [pkg_dir]
    while stack:
        d = stack.pop()
        for e in sorted(d.iterdir()):
            if e.is_dir():
                if e.name in SKIP_DIRS or e.name in NON_SHIPPED_DIRS or e.name.startswith("."):
                    continue
                if e in nested_pkg_dirs:
                    continue
                stack.append(e)
            elif e.suffix == ".rs" and not (e.name == "build.rs" and e.parent == pkg_dir):
                files.append(e)
    return files


# ---------------------------------------------------------------- cargo

def run_cargo(root, report):
    steps = [
        (["cargo", "fmt", "--all", "--check"], "cargo-fmt"),
        (["cargo", "clippy", "--workspace", "--all-targets", "--", "-D", "warnings"],
         "cargo-clippy"),
        (["cargo", "test", "--workspace"], "cargo-test"),
    ]
    for cmd, check in steps:
        try:
            res = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=1800)
        except (OSError, subprocess.TimeoutExpired) as exc:
            report.add("error", check, f"`{' '.join(cmd)}` could not run: {exc}", root)
            continue
        if res.returncode != 0:
            tail = "\n".join((res.stdout + res.stderr).strip().splitlines()[-15:])
            report.add("error", check, f"`{' '.join(cmd)}` failed:\n{tail}", root)


# ---------------------------------------------------------------- main

def audit(root, with_cargo):
    report = Report(root)
    manifests = find_manifests(root)
    root_path = root / "Cargo.toml"
    if not root_path.exists():
        report.add("error", "manifest", "no Cargo.toml at the given path", root)
        return report
    root_manifest = load_toml(root_path, report) or {}
    root_lines = root_path.read_text(encoding="utf-8").split("\n")
    ws = root_manifest.get("workspace") or {}
    root_ws_pkg = ws.get("package") or {}
    root_ws_deps = ws.get("dependencies") or {}
    excluded = {(root / e).resolve() for e in ws.get("exclude", [])}

    if ws:
        for key, spec in root_ws_deps.items():
            if isinstance(spec, dict) and "path" in spec:
                continue
            name = real_name(key, spec)
            idx = dep_decl_line(root_lines, key)
            reason = banned_reason(name)
            if reason:
                report.add("error", "banned-dependency", f"`{name}` is banned: {reason}",
                           root_path, idx + 1 if idx is not None else None)

    packages = []
    for mpath in manifests:
        if any(ex == mpath.parent or ex in mpath.parents for ex in excluded):
            continue
        if mpath.parent.name == "fuzz" or "fuzz" in mpath.parent.parts[len(root.parts):]:
            continue
        manifest = root_manifest if mpath == root_path else load_toml(mpath, report)
        if not manifest or "package" not in manifest:
            continue
        packages.append((mpath, manifest))

    pkg_dirs = {m.parent for m, _ in packages}
    any_binary = False
    total_lines = 0
    for mpath, manifest in packages:
        pkg = manifest["package"]
        pkg_dir = mpath.parent
        lines = mpath.read_text(encoding="utf-8").split("\n")
        edition = str(resolve(pkg, "edition", root_ws_pkg) or "2015")
        if edition != "2024":
            report.add("error", "edition", f"edition {edition}; use 2024", mpath)
        check_lints(mpath, manifest, root_manifest, report)
        check_dependencies(mpath, manifest, lines, root_ws_deps,
                           root_lines if mpath != root_path else None, root_path, report)
        any_binary = any_binary or package_has_binary(pkg_dir, manifest)
        nested = {d for d in pkg_dirs if d != pkg_dir and pkg_dir in d.parents}
        library_only = package_is_library_only(pkg_dir, manifest)
        for f in rust_files(pkg_dir, nested):
            scan_file(f, library_only, report)
            try:
                total_lines += f.read_text(encoding="utf-8").count("\n")
            except (OSError, UnicodeDecodeError):
                pass

    if any_binary:
        check_profile(root_path, root_manifest, report)
    if not ws and packages:
        _, manifest = packages[0]
        bins = len(manifest.get("bin") or []) + int((root / "src" / "main.rs").exists())
        deps = {real_name(k, v) for _, t in iter_dep_tables(manifest) for k, v in t.items()}
        reasons = []
        if total_lines > WORKSPACE_LINE_THRESHOLD:
            reasons.append(f"{total_lines} lines of Rust")
        if bins > 1 or (root / "src" / "bin").is_dir():
            reasons.append("several binaries")
        if "wgpu" in deps:
            reasons.append("a GUI/renderer")
        if "cortex-m-rt" in deps or any(d.startswith("embassy-") for d in deps):
            reasons.append("firmware")
        if reasons:
            report.add("warning", "workspace", "single crate with " + ", ".join(reasons) +
                       "; this should be a workspace (references/workspace.md)", root_path)
    check_project_files(root, report)
    if with_cargo:
        run_cargo(root, report)
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("path", help="crate or workspace root (the directory with Cargo.toml)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--strict", action="store_true", help="exit 1 on warnings too")
    ap.add_argument("--cargo", action="store_true", help="also run cargo fmt, clippy and test")
    args = ap.parse_args()
    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2
    report = audit(root, args.cargo)
    order = {"error": 0, "warning": 1}
    report.findings.sort(key=lambda f: (order[f["severity"]], f["path"] or "", f["line"] or 0))
    if args.json:
        print(json.dumps({"root": str(root), "errors": report.count("error"),
                          "warnings": report.count("warning"),
                          "findings": report.findings}, indent=2))
    else:
        for f in report.findings:
            loc = f["path"] or "."
            if f["line"]:
                loc += f":{f['line']}"
            print(f"{f['severity'].upper():7} {f['check']:24} {loc}  {f['message']}")
        print(f"\n{report.count('error')} error(s), {report.count('warning')} warning(s)")
    failed = report.count("error") or (args.strict and report.count("warning"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
