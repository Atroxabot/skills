# Workspaces

Any sizable project is a Cargo workspace from the first commit (the thresholds are in SKILL.md). Starting as one crate and splitting later means moving files, rewriting paths and untangling dependencies in the middle of other work.

What a workspace buys:
- **Enforced boundaries.** A crate can only use what another crate makes `pub`, and dependencies can't go in a circle. Layering stops being a convention people forget.
- **Faster builds.** Crates compile in parallel and are cached separately, so editing the app shell doesn't recompile the core.
- **Isolated testing.** `core` tests run without a GPU, network or target board.
- **One place for policy.** Versions, lints and profiles are declared once.

## Layout

```
Cargo.toml              # virtual manifest: workspace, shared package fields, dependencies, lints, profiles
Cargo.lock              # committed, for applications and libraries alike
rust-toolchain.toml
clippy.toml
deny.toml
crates/
  <name>-core/          # domain logic: no I/O, no platform crates, no async runtime
  <name>-render/        # (GUI) wgpu code: pipelines, buffers, the UI renderer
  <name>-net/           # (services) protocol and transport
  <name>/               # the binary: argument parsing, config, wiring, main
fuzz/                   # cargo-fuzz targets; excluded from the workspace (needs nightly)
```

The binary crate takes the project's plain name, so `cargo install` and the output file read naturally. For firmware, `<name>-core` holds the logic and is tested on the host, and `<name>-fw` is the `no_std` target crate (see [embedded.md](embedded.md)).

## Root `Cargo.toml`

```toml
[workspace]
resolver = "3"                  # required in a virtual manifest; 3 is the edition-2024 resolver
members = ["crates/*"]
exclude = ["fuzz"]

[workspace.package]
edition = "2024"
rust-version = "1.97"
version = "0.1.0"
license = "MIT"
publish = false

[workspace.dependencies]
# Internal crates
app-core = { path = "crates/app-core" }
app-render = { path = "crates/app-render" }
# External crates: each declared once, with versions and default features decided here
wgpu = "30"
winit = "0.30"
bytemuck = { version = "1.25", features = ["derive"] }
pollster = "1.0"

[workspace.lints.rust]
# the full block from code-standards.md

[workspace.lints.clippy]
# the full block from code-standards.md

[profile.release]
# the profiles from code-standards.md
```

## Member `Cargo.toml`

```toml
[package]
name = "app-render"
version.workspace = true
edition.workspace = true
rust-version.workspace = true
license.workspace = true
publish.workspace = true

[dependencies]
app-core.workspace = true
wgpu.workspace = true
bytemuck.workspace = true

[lints]
workspace = true
```

A member can add features to a workspace dependency (`tokio = { workspace = true, features = ["net"] }`) but never sets its own version. Two versions of one crate in the tree means two copies compiled and linked, and types from one that don't match the other.

Profiles in member manifests are ignored by Cargo, so they only go in the root.

## Crate boundaries

Add a crate when a part of the code has a different reason to change, a different set of heavy dependencies, or needs to be tested without the rest. Don't split by file count. Each crate adds link time, and anything another crate uses has to be `pub`, which widens what counts as API.

Rules:
- **Dependencies point toward the core.** `core` depends on nothing in the workspace. Platform crates depend on `core`. The binary depends on everything. If `core` needs something from a platform crate, define a trait in `core` and implement it in the platform crate.
- **`core` is pure.** No file system, network, clock or randomness called directly. Pass them in (a `&mut impl Read`, a `now: Instant` argument, a seeded RNG). That's what makes core logic deterministic to test, fuzz and benchmark.
- **The binary crate is thin.** It parses arguments and config, builds the pieces, connects them, and maps errors to exit codes. Logic in `main.rs` can't be tested or reused.
- **Internal APIs stay `pub(crate)`** inside each crate. Only what other crates use is `pub`.

## Fast builds

Build time is development time: every second in the edit-compile-test loop is paid hundreds of times a day. Measure before changing anything (`cargo build --timings` writes an HTML report of what compiled when, and what blocked what), then apply what helps:

- **Split crates along the edit path.** Editing a leaf crate recompiles only it and what depends on it. A large crate that everything depends on and that changes often is the most common cause of slow incremental builds.
- **Line tables instead of full debug info in dev builds:** `[profile.dev] debug = "line-tables-only"` (in the profile block in [code-standards.md](code-standards.md)). Backtraces keep file and line numbers, and debuggers still step by line, but there's less debug info to generate and link. Measured on the rust-gui skill's skeleton (wgpu, winit, about 300 crates): an incremental rebuild went from 1.54 s to 1.08 s. When you need to inspect variables in a debugger, build with `CARGO_PROFILE_DEV_DEBUG=true` for that session.
- **Optimized dependencies, unoptimized own code:** `[profile.dev.package."*"] opt-level = 2` makes the first build slower but keeps debug builds of heavy apps usable, and dependencies rarely recompile.
- **The linker:** on x86_64 Linux, Rust 1.90 and later already link with the bundled LLD, which is fast. `mold` can be faster still on very large binaries. Try it only when `--timings` shows linking as the bottleneck, through `.cargo/config.toml`:

  ```toml
  [target.x86_64-unknown-linux-gnu]
  linker = "clang"
  rustflags = ["-C", "link-arg=-fuse-ld=mold"]
  ```
- **Few proc macros and build scripts.** Each proc-macro crate (`serde_derive` and friends) compiles before anything that uses it and can't be parallelized away. Each build script runs on every clean build. The dependency rules already keep these down.
- **Check, don't build, while editing.** `cargo check` (what rust-analyzer runs) skips code generation entirely. Run `cargo test -p <crate>` for the crate being changed, and the whole workspace before pushing.
- **CI:** cache `~/.cargo/registry`, `~/.cargo/git` and `target/`, keyed on `Cargo.lock`, the toolchain version and the OS. For large projects with many CI machines, `sccache` (`RUSTC_WRAPPER=sccache`) shares compiled dependencies between them. It doesn't help local incremental builds, so it's a CI tool.

## Commands

```bash
cargo build --workspace
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
cargo test -p app-core              # one crate
cargo tree -d                       # duplicated dependency versions
cargo build --timings               # where build time goes; split crates that block the graph
```

## Converting an existing crate

1. Move the existing crate into `crates/<name>/` and create the virtual root manifest.
2. Move `[profile.*]` and the lint table to the root, and switch the member to `lints.workspace = true`.
3. Move every external dependency into `[workspace.dependencies]` and use `dep.workspace = true`.
4. Extract `<name>-core` by moving the modules that have no I/O or platform dependencies. Let the compiler's errors show what has to become `pub` or be passed in.
5. Run the full checks. Commit the move separately from any behavior change, so the diff of the move is reviewable.
