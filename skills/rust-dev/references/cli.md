# CLI tools

A command-line tool is judged by how it behaves in a pipeline and a script: fast startup, clean output on stdout, errors on stderr, honest exit codes, no surprises with large input or closed pipes.

## Structure

- Small tools: one crate, `main.rs` that parses arguments and calls into `lib.rs`, where the logic lives and is tested.
- Tools with several subcommands or sizable logic: a workspace with `<name>-core` and a thin `<name>` binary ([workspace.md](workspace.md)).
- `main` returns `ExitCode` and prints the error chain once ([errors.md](errors.md)). No `process::exit` (denied by Clippy), since it skips destructors and leaves buffered output unflushed.

## Arguments

- **`lexopt`** for parsing (on the allowlist): no dependencies, no proc macros, and it handles `--flag=value`, `-abc`, `--` and non-UTF-8 arguments correctly. A tool with one or two positional arguments can use `std::env::args_os()` directly.
- `clap` only with a `# why:`, for tools that need generated shell completions or a large subcommand tree. Its derive macros add noticeable compile time and binary size.
- Parse into a typed `Args` struct (enums for modes, `PathBuf` for paths, `NonZeroUsize` for counts) at the start of `main`. Code past that point never touches raw strings.
- Paths are `OsString`/`PathBuf`, never `String`. File names aren't guaranteed to be UTF-8, and a tool that panics or refuses on one is broken.
- `--help` and `--version` work and exit 0. Help text goes to stdout (it's the requested output); usage errors go to stderr with exit code 2.

## Output

- **stdout is for data, stderr for everything else** (progress, warnings, errors). Then `tool | other` and `tool > file` get only the data.
- **Lock and buffer stdout once.** `println!` locks stdout on every call and writes line by line, which is slow for large output. Worse, **it panics on a closed pipe**: `tool | head -1` crashes the tool when `head` exits. Rust ignores `SIGPIPE`, so the write returns `BrokenPipe`, and `println!` turns that error into a panic.
- **A broken pipe is success.** The reader got what it wanted.

This module compiles under the lint set in [code-standards.md](code-standards.md):

```rust
use std::io::{self, BufWriter, ErrorKind, Write};

/// Writes results to stdout through one locked, buffered handle.
/// `println!` re-locks stdout on every call and panics when the reader closes the pipe
/// (`tool | head`), so a CLI that prints more than a line or two writes this way instead.
///
/// # Errors
///
/// Returns the I/O error from writing or flushing stdout.
pub fn write_lines<I: IntoIterator<Item = u64>>(values: I) -> io::Result<()> {
    let stdout = io::stdout();
    let mut out = BufWriter::new(stdout.lock());
    for v in values {
        writeln!(out, "{v}")?;
    }
    out.flush()
}

/// A closed pipe means the reader has everything it wanted. That's success, not an error.
///
/// # Errors
///
/// Passes through every error except [`ErrorKind::BrokenPipe`].
pub fn ignore_broken_pipe(result: io::Result<()>) -> io::Result<()> {
    match result {
        Err(e) if e.kind() == ErrorKind::BrokenPipe => Ok(()),
        other => other,
    }
}
```

- Machine-readable output (`--json`, or tab-separated) is a stable interface. Changing it is a breaking change.
- Colors only when stderr/stdout is a terminal (`std::io::IsTerminal`) and `NO_COLOR` isn't set. Never put escape codes into a pipe.
- Progress output goes to stderr, only on a terminal, and is throttled (at most about 10 updates per second). Printing progress per item can cost more than the work.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success (including a broken pipe on output) |
| 1 | The operation failed |
| 2 | Usage error: bad arguments, missing required input |
| Tool-specific (documented) | When scripts need to tell outcomes apart, as `grep` uses 1 for "no match" |

The top-level error enum maps each variant to its code, so the mapping lives in one place.

## Input

- **Stream, don't slurp.** Read with `BufReader` and process line by line or chunk by chunk, so a 50 GB input uses the same memory as a 50 KB one. Read whole files only when the format needs random access, and then consider memory-mapping (with its `# why:` and the unsafe rule).
- Accept `-` as stdin where a file path is expected.
- Lines: use `read_until(b'\n', &mut buf)` on a reused `Vec<u8>` when input may not be UTF-8 or when speed matters. `lines()` allocates a `String` per line and fails on invalid UTF-8.
- Bound everything from input: line length, nesting depth, counts. A malformed or hostile file must produce an error, not exhaust memory.

## Startup and speed

- Startup time is part of a CLI's performance. No work before it's needed: no config files read, no directories scanned, no thread pools started for `--help`.
- Release profile from [code-standards.md](code-standards.md). For tools distributed as binaries, consider `opt-level = 3` with `strip = "symbols"` to reduce size.
- For parallel work over many files, `rayon` or `std::thread::scope` over a work list, with output collected and written in a deterministic order. Output order must not depend on thread timing.

## Signals

- Ctrl-C (`SIGINT`) on a long operation: by default the process dies immediately, which is fine for read-only tools. Tools that write files must not leave partial output behind: write to a temporary file in the same directory and `rename` it into place when done, so an interruption leaves either the old file or the new one.

## Testing

- Logic in `lib.rs` gets unit tests.
- The binary gets a few end-to-end tests in `tests/` that run it with `std::process::Command` (via `env!("CARGO_BIN_EXE_<name>")`) and check stdout, stderr and the exit code for: a normal run, a usage error, a missing file, and output into a closed pipe.
