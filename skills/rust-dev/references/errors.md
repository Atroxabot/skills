# Error handling

No error crates: not `thiserror`, `anyhow`, `eyre`, `color-eyre`, `snafu`, `quick-error`, `displaydoc`, `failure` or `error-chain`. No `Box<dyn Error>` outside tests, examples and build scripts. Every error is a type written by hand.

Why: an error type is part of a function's contract. Writing `Display` and `Error` by hand takes a few minutes, keeps every variant a deliberate decision, and costs no compile time or dependency. Derive macros make it cheap to add vague variants and blanket `#[from]` conversions that drop context, and `anyhow`-style catch-all errors turn "what can go wrong here?" into a question nobody can answer from the signature.

(Crates we depend on may use `thiserror` internally. wgpu does, for example. The rule is about our code, which is why the audit script checks direct dependencies only.)

## Contents
- The shape of an error type (verified example)
- Adding context as errors cross layers
- Reporting at the top: `main`, exit codes, the source chain
- Error types in libraries
- Rules of thumb

## The shape of an error type

This module compiles under the lint set in [code-standards.md](code-standards.md), and its test passes.

```rust
use std::error::Error;
use std::fmt;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};

/// Settings read from a `key = value` file.
#[derive(Debug)]
pub struct Config {
    pub workers: u16,
}

/// Why [`load`] failed. Each variant carries what a caller or a person needs to act on it.
#[derive(Debug)]
#[non_exhaustive]
pub enum LoadConfigError {
    Read {
        path: PathBuf,
        source: io::Error,
    },
    Parse {
        path: PathBuf,
        line: usize,
        kind: ParseErrorKind,
    },
    MissingKey {
        path: PathBuf,
        key: &'static str,
    },
}

/// Leaf detail for [`LoadConfigError::Parse`]. Not an error type itself: it has no
/// cause, so it is printed inline instead of becoming a link in the `source()` chain.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum ParseErrorKind {
    MissingEquals,
    InvalidNumber,
}

impl fmt::Display for ParseErrorKind {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Self::MissingEquals => "expected `key = value`",
            Self::InvalidNumber => "value is not a number in range",
        })
    }
}

impl fmt::Display for LoadConfigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            // The io::Error is the source, so it is not repeated here.
            Self::Read { path, .. } => write!(f, "cannot read config file {}", path.display()),
            Self::Parse { path, line, kind } => write!(f, "{}:{line}: {kind}", path.display()),
            Self::MissingKey { path, key } => {
                write!(f, "{}: missing required key `{key}`", path.display())
            }
        }
    }
}

impl Error for LoadConfigError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::Read { source, .. } => Some(source),
            Self::Parse { .. } | Self::MissingKey { .. } => None,
        }
    }
}

/// Loads the config file at `path`.
///
/// # Errors
///
/// Returns [`LoadConfigError`] if the file can't be read, a line is malformed,
/// or a required key is missing.
pub fn load(path: &Path) -> Result<Config, LoadConfigError> {
    let text = fs::read_to_string(path).map_err(|source| LoadConfigError::Read {
        path: path.to_owned(),
        source,
    })?;
    let parse_err = |line: usize, kind| LoadConfigError::Parse {
        path: path.to_owned(),
        line,
        kind,
    };
    let mut workers = None;
    for (index, raw) in text.lines().enumerate() {
        let line = index + 1;
        let raw = raw.trim();
        if raw.is_empty() || raw.starts_with('#') {
            continue;
        }
        let (key, value) = raw
            .split_once('=')
            .ok_or_else(|| parse_err(line, ParseErrorKind::MissingEquals))?;
        if key.trim() == "workers" {
            let n = value
                .trim()
                .parse::<u16>()
                .map_err(|_| parse_err(line, ParseErrorKind::InvalidNumber))?;
            workers = Some(n);
        }
    }
    let workers = workers.ok_or_else(|| LoadConfigError::MissingKey {
        path: path.to_owned(),
        key: "workers",
    })?;
    Ok(Config { workers })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reports_line_of_bad_number() {
        let dir = std::env::temp_dir().join("cfgtest-bad-number");
        fs::create_dir_all(&dir).unwrap();
        let path = dir.join("app.conf");
        fs::write(&path, "# comment\nworkers = many\n").unwrap();
        let err = load(&path).unwrap_err();
        assert!(matches!(
            err,
            LoadConfigError::Parse {
                line: 2,
                kind: ParseErrorKind::InvalidNumber,
                ..
            }
        ));
    }
}
```

What to copy from it:
- **One error type per operation or module**, named for what failed (`LoadConfigError`), not one `Error` for the whole crate. A caller matching on it only sees failures that can actually happen.
- **Variants carry the context needed to act**: the path, the line, the key. "Invalid number" without a location makes someone go hunting.
- **`Display` describes this layer's failure only.** When a variant wraps a cause, that cause is returned from `source()` and *not* repeated in the message. Otherwise a report prints it twice. Messages are lowercase with no trailing period, so they chain cleanly: `cannot start: cannot read config file /etc/app.conf: permission denied`.
- **Leaf details that aren't errors** (like `ParseErrorKind`) are printed inline and not exposed as a `source`.
- **`#[non_exhaustive]`** on public error enums, so adding a variant isn't a breaking change.
- **Tests match on variants**, not on message strings. Messages are for people and may change.

## Adding context as errors cross layers

Each layer that has something to add wraps the lower error in its own variant, with `map_err`:

```rust
let config = config::load(&path).map_err(StartError::Config)?;
let listener = TcpListener::bind(addr).map_err(|source| StartError::Bind { addr, source })?;
```

`impl From<LowerError> for HigherError` (so `?` converts automatically) is fine only when there's exactly one way the lower error can arise in the higher operation and no context is lost. If two calls in the same function can return `io::Error`, a `From<io::Error>` makes them impossible to tell apart. Use `map_err` with distinct variants instead.

Keep error values small. Clippy's `result_large_err` fires above 128 bytes, because every `Result` carrying a large error is copied around on the success path too. Box the large payload (`Parse(Box<ParseDetail>)`), not the whole error.

Errors are `Send + Sync + 'static` (no `Rc`, no borrowed data), so they can cross threads and be stored.

## Reporting at the top

`main` returns `ExitCode` and prints the whole chain once:

```rust
fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(err) => {
            eprintln!("error: {}", Report(&err));
            ExitCode::FAILURE
        }
    }
}

/// Formats an error and its whole `source()` chain on one line: `a: b: c`.
pub(crate) struct Report<'a>(pub(crate) &'a dyn Error);

impl fmt::Display for Report<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)?;
        let mut cause = self.0.source();
        while let Some(err) = cause {
            write!(f, ": {err}")?;
            cause = err.source();
        }
        Ok(())
    }
}
```

`run()` returns the application's top-level error enum, written by hand like any other. Not `Box<dyn Error>`: the top-level enum is also where exit codes come from (`impl AppError { fn exit_code(&self) -> ExitCode }`, for example usage errors exiting with 2).

Log or print an error **once**, where it's handled. Logging at every layer and then propagating produces the same failure five times in the log.

In services, the per-request handler is the top: it maps the error to a response status and logs it with the request's span. The process only exits on startup errors.

## Error types in libraries

- Enum errors with public variants work when the variants are stable and their fields are types you're happy to make part of the API (std types, your own types).
- When an error wraps a **third-party** error type, don't put that type in a public field: upgrading the dependency would then be a breaking change for your users. Use an opaque struct with a `kind()` accessor instead, like `std::io::Error`:

```rust
#[derive(Debug)]
pub struct Error {
    kind: ErrorKind,
    repr: Repr, // private enum holding the third-party causes
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum ErrorKind { NotFound, InvalidData, Network }

impl Error {
    #[must_use]
    pub fn kind(&self) -> ErrorKind { self.kind }
}
```

`source()` can still return the third-party error as `&dyn Error`, which doesn't put its type in your API.

## Rules of thumb

- `Option` for "absent is normal" (a lookup that may miss). `Result` for "something went wrong".
- Don't stringify errors on the way up (`map_err(|e| e.to_string())`). That throws away the type and the chain.
- Don't make every function return the same big error. If a function can fail in only one way, its error type has one variant, or it's a plain struct.
- Recoverable versus fatal is the caller's decision. Return the error and let the caller decide; don't exit or abort from library code.
- Error messages name the thing (path, address, key, id) and say what was expected. They never contain secrets: no tokens, passwords or full request bodies.
