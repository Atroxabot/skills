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
