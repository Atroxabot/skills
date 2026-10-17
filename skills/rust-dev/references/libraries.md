# Library crates

A library's public API is a promise. Everything `pub` is something users can depend on, and changing it means a major version. So the API is kept small, deliberate and hard to misuse, and the rules in [code-standards.md](code-standards.md) apply with these additions.

## Lints

Add to the library's lint table:

```toml
[lints.rust]
missing_docs = "warn"

[lints.clippy]
print_stdout = "deny"     # a library never writes to the user's terminal
print_stderr = "deny"
```

A library never panics, prints, exits, reads environment variables or installs global state (a logger, a panic hook, a global allocator). Those decisions belong to the application.

## API design

Follow the Rust API Guidelines. The ones that matter most:

- **Small surface.** Start with what the known users need and keep everything else `pub(crate)`. Adding API later is a minor version. Removing it is a major one.
- **`#[non_exhaustive]`** on public enums and on structs with public fields that may grow, including error enums. Then adding a variant or field isn't breaking.
- **No dependency types in the public API** unless the dependency is effectively part of the interface (`bytes::Bytes` in a networking crate, for example). Otherwise, upgrading the dependency's major version becomes a major version for us. Wrap them, or convert at the boundary.
- **Constructors that can't produce invalid values.** A builder when there are more than about three optional settings, with validation in `build()` returning a `Result`.
- **Accept general, return specific:** take `impl AsRef<[u8]>`, `impl Into<String>`, `&[T]` or `impl IntoIterator`, and return concrete types or `impl Iterator`.
- **Common traits implemented** where they make sense: `Debug` always, plus `Clone`, `PartialEq`, `Eq`, `Hash`, `Default`, `Display`, `From`, and `Send`/`Sync` (check auto-trait impls with a compile-time test, because losing `Send` is a breaking change that's easy to cause by accident).
- **Sealed traits** for traits users may call but shouldn't implement: a public trait with a private supertrait.
- **Errors** follow [errors.md](errors.md): hand-written, `#[non_exhaustive]`, with an opaque struct and a `kind()` when the error wraps third-party types.

## `no_std` support

If the library's logic doesn't need the OS, make it `#![no_std]` with an optional `std` feature (and `alloc` if it needs `Vec`/`String`). It costs little to do from the start and opens up embedded and wasm users. Retrofitting it later means touching every import.

```toml
[features]
default = ["std"]
std = ["alloc"]
alloc = []
```

## Features

- **Additive only.** Enabling a feature adds API or capability, it never removes or changes behavior, because Cargo unifies features across the dependency graph and another crate can turn a feature on for you.
- **Minimal default features.** Users can add features, but turning off a default is easy to forget.
- Test every feature combination that matters in CI (`cargo hack --feature-powerset check` for small feature sets).
- Optional dependencies behind features use `dep:` syntax so they don't create implicit features.

## Documentation

- Crate-level docs (`//!` in `lib.rs`): what it does, when to use it, a short example.
- Every public item documented, with `# Errors`, `# Safety` and `# Examples` sections where they apply. Pedantic Clippy enforces `# Errors` on fallible functions.
- Examples are doctests, so they're compiled and run by `cargo test`. In a doctest, `?` works with a hidden `fn main() -> Result<(), Box<dyn std::error::Error>>`. That's allowed there: examples are not shipped code.
- `cargo doc --no-deps` builds without warnings, with `RUSTDOCFLAGS="-D warnings"` in CI to catch broken intra-doc links.

## Versioning and release

- Semantic versioning, checked with `cargo semver-checks` before every release. It catches most accidental breaking changes (removed items, changed signatures, lost auto-traits).
- `rust-version` in `Cargo.toml` is the minimum supported Rust version, tested in CI with that exact toolchain. Raising it is at least a minor version, and is noted in the changelog.
- A `CHANGELOG.md` with every user-visible change.
- `Cargo.lock` is committed for reproducible CI, even though users' builds ignore it.

## Performance in libraries

- No allocation that the caller can't control: offer APIs that write into a caller-provided buffer (`fn encode_into(&self, out: &mut Vec<u8>)`) alongside convenient allocating ones.
- Generic APIs in hot paths so callers get static dispatch. Keep the generic part thin and delegate to a non-generic inner function, to limit the code generated per type.
- `#[inline]` on small public functions that are called across the crate boundary in hot paths, because without LTO they can't be inlined otherwise.
- Benchmarks for the public hot paths live in the crate's `benches/` and run in CI against the previous release.
