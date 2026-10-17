---
name: rust-dev
description: Standards for writing, structuring and reviewing idiomatic, high-assurance, high-performance Rust. No unwrap, expect or panics outside tests, audited unsafe, strict Clippy lints, edition 2024 on stable, Cargo workspaces for larger projects, hand-written error types (never thiserror or anyhow), and a dependency allowlist where any other crate needs a written reason. GUI apps render with raw wgpu and winit and a hand-built UI, never a GUI framework. Async only when the workload needs it; latency-critical paths use pinned hot threads and ring buffers. Covers CLI tools, services, libraries and no_std firmware, plus benchmarks, proptest, fuzzing, Miri, sanitizers and cargo-deny, with an audit script. Use when the user asks to start, write, refactor, review, optimize or debug Rust code, a Cargo project, crate or workspace, a CLI, server, daemon, library, firmware, game, renderer or desktop app in Rust, add a dependency, handle errors, use wgpu, winit or WGSL, write unsafe or concurrent code, or make Rust faster.
---

# Rust development

This skill sets how Rust code is written in our projects: the toolchain, the project layout, the code-quality bar, error handling, dependencies, concurrency, performance and verification, plus specific guidance for each kind of application. It applies to new code, changes to existing code, and reviews.

The bar has three parts, and none of them is traded away for another:

- **High-assurance quality.** Code that a strict reviewer on a safety-critical project would accept: no hidden panics, every failure handled or propagated with context, unsafe code isolated and justified, every rule enforced by a tool where a tool can enforce it. Bugs caught by the compiler and Clippy cost seconds. Bugs caught in production cost incidents.
- **Idiomatic Rust.** Code that experienced Rust developers read without stopping: ownership and borrowing instead of clones, iterators instead of index loops, `?` and pattern matching instead of nested checks, enums instead of flags and sentinel values, std traits (`From`, `TryFrom`, `Default`, `Display`, `FromStr`, `IntoIterator`) instead of ad-hoc methods, and the Rust API Guidelines for naming. Code that fights the language is harder to review and usually slower too, because iterators drop bounds checks and borrows avoid copies. The idioms, with the non-idiomatic forms they replace, are in [references/code-standards.md](references/code-standards.md#idiomatic-rust).
- **Very high performance.** Performance is designed in (data layout, allocation, threading model) and then measured. It's not something sprinkled on at the end with `#[inline]`. A claim that code is fast needs a benchmark behind it.

When a rule here conflicts with an existing project's established convention, point out the conflict and ask before changing it. Don't silently pick one.

## Toolchain

- **Latest stable Rust, edition 2024**, pinned in `rust-toolchain.toml` with an exact version (`channel = "1.97.0"`, not `"stable"`). Then every developer and CI run builds with the same compiler, and upgrades happen on purpose in their own commit. Check the current stable with `rustup check` or the Rust blog, not from memory.
- **No nightly features in shipped code.** Nightly is used only to run tools that need it (Miri, sanitizers, cargo-fuzz), never to build the product. A nightly feature can change or disappear, which makes the build depend on luck.
- `rustfmt` with default settings. A formatter only helps if nobody argues about it, and the defaults are what every Rust developer already reads.
- Clippy with `all` and `pedantic` denied, plus a set of restriction lints that enforce the panic and unsafe rules below. The full `[workspace.lints]` block, `clippy.toml` and release profile are in [references/code-standards.md](references/code-standards.md). Copy them; don't retype them from memory.
- Before trusting what you remember about a crate's API, check the version that's actually current (`cargo search <crate>`, `cargo info <crate>`) and read that version's docs. wgpu, winit and tokio change their APIs between major versions.

## Project layout: workspaces for anything sizable

A project that is or will become sizable is a **Cargo workspace** from the start. Converting later means moving every file and fixing every path in the middle of other work. A project counts as sizable if any of these is true:

- more than one binary, or a binary plus logic worth reusing or testing alone
- a GUI app or a game (there's always at least a core, a renderer and an app shell)
- firmware (the logic has to be a host-testable crate separate from the hardware crate)
- over roughly 5,000 lines planned, or incremental builds over about 20 seconds

Below that, one crate is fine. Split crates by reason to change and by dependency weight, not one crate per module: `<name>-core` (pure logic, no I/O, no platform dependencies, fast to build and test), `<name>-render` or `<name>-net` (the heavy platform layer), and a thin binary crate that wires them together. Dependencies point one way: `core` never depends on the platform crates. Versions, lints and profiles live once in the root manifest. Layout, manifests and the rules for when to add a crate are in [references/workspace.md](references/workspace.md).

## Non-negotiables

These hold in every project. Each one has a reason, and knowing the reason is how you handle a case the rule didn't anticipate.

1. **No panics in non-test code.** No `unwrap`, `expect`, `panic!`, `todo!`, `unimplemented!`, `unreachable!` or `assert!`, and no indexing or slicing that can go out of bounds. Use `get`, iterators, `split_at_checked`, pattern matching, and `Result`. A panic in production is a crash (we build with `panic = "abort"`), and "this can't fail" is the assumption that most often turns out wrong. Invariants you want checked go in `debug_assert!`, which runs under tests, fuzzing and debug builds, and compile-time `const` assertions are fine because they fail the build, not the program. If something truly can't fail, encode that in the types so there's nothing to unwrap. Tests may unwrap freely; `clippy.toml` allows it there.
2. **Errors are hand-written types.** Never `thiserror`, `anyhow`, `eyre`, `snafu` or any other error crate, and no `Box<dyn Error>` outside tests and examples. Each module or operation has an error enum with `Display` and `std::error::Error` written by hand, carrying the context needed to act on it. Error crates hide what the type contains behind a macro and tempt you into one giant catch-all error. Writing the impl takes a few minutes and keeps every variant deliberate. Patterns are in [references/errors.md](references/errors.md).
3. **Dependencies only when necessary.** Crates on the allowlist in [references/dependencies.md](references/dependencies.md) may be added for their stated use. Any other crate needs a `# why:` comment on its line in `Cargo.toml` that says what it does that we can't reasonably write, and it must pass the checks in that file (maintenance, size, transitive tree, unsafe use, license). Each dependency is code we ship and don't review, a supply-chain risk, and compile time. Before adding one, check whether `std` already does the job: `LazyLock` and `OnceLock` replace `lazy_static` and `once_cell`, `std::io::IsTerminal` replaces `atty`, and `std::sync::mpsc` is a fine channel off the hot path.
4. **`unsafe` is isolated, justified and tested.** `unsafe_code` is denied workspace-wide. Unsafe is allowed only for FFI, hardware access, or a measured speedup that safe code can't reach. It lives in a dedicated module that opts in with `#[expect(unsafe_code, reason = "...")]`. Every block holds one unsafe operation with a `// SAFETY:` comment saying why it's sound, every `unsafe fn` has a `# Safety` doc section, a safe API wraps it, and its tests run under Miri and AddressSanitizer. Unsafe code is where Rust's guarantees stop, so the proof has to be written down where a reviewer can check it.
5. **Explain exceptions where they happen.** No `#[allow]`. Use `#[expect(lint, reason = "...")]`, which errors when the lint stops firing, so stale exceptions don't pile up. A reason like "false positive" isn't enough; say why the code is right.
6. **Integer overflow is a bug, never silent.** Release builds keep `overflow-checks = true`. Arithmetic on values from outside the process uses `checked_*` or `saturating_*`. Hot loops that are proven in bounds use `wrapping_*`, which the flag doesn't affect, so speed doesn't cost correctness. Silent wraparound corrupts data without a trace, and a crash at least points at the bug.
7. **The checks pass before the work is done:** `cargo fmt --check`, `cargo clippy --workspace --all-targets -- -D warnings`, `cargo test --workspace`, `cargo deny check`, and the audit script. When unsafe code changed, Miri as well, and criterion benchmarks when a hot path changed.

More rules, with their reasons (types, naming, function size, documentation, recursion, global state), are in [references/code-standards.md](references/code-standards.md).

## Performance

Design for performance first, then measure:

- **Pick the data layout before writing the algorithm.** Contiguous `Vec`s of plain structs, struct-of-arrays for hot loops that touch only a few fields, indices instead of pointer graphs. Cache misses cost more than almost any instruction count.
- **Nothing allocates in the steady state of a hot path.** Allocate up front, reuse buffers (`clear()`, not a new `Vec`), and pass `&mut` scratch space.
- **Iterate rather than index.** Iterators, `chunks_exact` and `zip` remove bounds checks and help the compiler vectorize, and they're the same code style the no-panic rule asks for.
- **Static dispatch on hot paths.** Generics or enums, not `Box<dyn Trait>`, inside the inner loops.
- **Release profile:** `lto = "fat"`, `codegen-units = 1`, `panic = "abort"`. Use `target-cpu=native` only for binaries that run on the machine that built them.
- **Measure with real tools.** criterion for benchmarks, `perf`, `samply` or `cargo flamegraph` for where time goes, `cargo-show-asm` to check whether a loop vectorized. Report numbers with the hardware and the input that produced them.

The full list (allocation, hashing, I/O, SIMD, profile-guided optimization, reading assembly) is in [references/performance.md](references/performance.md).

## Concurrency: threads, ring buffers, or async

Async is not faster by definition. An async task is cheaper than a thread *while it waits*, and that's its only advantage. It adds a runtime, scheduling you don't control, cancellation hazards, and latency jitter. So the threading model is a decision made per project, from the workload:

| Workload | Model |
|---|---|
| Fast enough on one thread | Sequential code. No threads. |
| CPU-bound and data-parallel (image processing, simulation steps, batch transforms) | `rayon`, or `std::thread::scope` for a few fixed chunks |
| Latency-critical pipeline (trading, audio, real-time control, packet processing, game simulation) | Dedicated threads with a **hot/cold split**: the hot thread is pinned to a core, busy-polls a lock-free SPSC ring buffer, and never allocates, locks, logs or makes a syscall. Anything slow goes to cold threads over ring buffers the hot thread can drop into without waiting. |
| Many concurrent I/O waits (thousands of mostly idle connections, an HTTP API, a proxy) | async on `tokio`, with only the features used |
| Network edge feeding a latency-critical core | async (or blocking I/O threads) at the edge, a ring buffer into synchronous hot threads. The hot path never runs on runtime worker threads. |

For a few hundred connections, a thread per connection or a small pool with blocking I/O is usually simpler and as fast. Before reaching for async, say which row the project is in and why. Patterns, memory ordering, false sharing and backpressure are in [references/concurrency.md](references/concurrency.md).

## Application types

Read the reference for the kind of application before writing it:

| Building | Read | The short version |
|---|---|---|
| GUI app, game, visualization, editor | [references/gui-wgpu.md](references/gui-wgpu.md) | **Always raw wgpu + winit with a hand-built UI.** Never egui, iced, Slint, GTK, Tauri, Bevy or any other UI framework or renderer. Redraw on demand, batch everything into a few draw calls, create pipelines once, no per-frame allocation. A frame-time budget is a requirement, not a hope. |
| CLI tool | [references/cli.md](references/cli.md) | `lexopt` or `std::env::args_os`, a locked and buffered stdout, broken pipes treated as success, data on stdout and diagnostics on stderr, meaningful exit codes, streaming instead of loading whole inputs. |
| Server, daemon, network service | [references/services.md](references/services.md) | Pick the concurrency model first. When it's tokio: explicit runtime, bounded everything (queues, connections, body sizes, timeouts), graceful shutdown, `tracing` for observability. |
| Library crate | [references/libraries.md](references/libraries.md) | Small public API, `#[non_exhaustive]` on what may grow, no dependency types in the public API, additive features, docs with runnable examples, `cargo-semver-checks` before release. |
| Embedded / `no_std` firmware | [references/embedded.md](references/embedded.md) | No heap, static buffers (`heapless`), no recursion, bounded loops, interrupt-safe sharing through `critical-section`, a logic crate tested on the host, `defmt` for logging. |

## Verification

Unit tests alone aren't enough at this bar. What each project needs:

- **Unit and integration tests** for behavior, including every error path a caller can hit. Every bug fix comes with a test that fails before the fix.
- **Property tests** (`proptest`) for invariants: round-trips, ordering, idempotence, agreement with a slow reference implementation.
- **Fuzzing** (`cargo-fuzz`) for every function that parses untrusted input. Run each target for a set time in CI and keep the corpus.
- **Miri** for every crate with unsafe code, and **AddressSanitizer / ThreadSanitizer** for unsafe and lock-free code.
- **Benchmarks** (`criterion`) for hot paths, compared against a saved baseline when those paths change.
- **`cargo deny check`** in CI for advisories, licenses, banned crates and duplicate versions.

Commands, CI layout and what a good property or fuzz target looks like are in [references/verification.md](references/verification.md).

## Workflow

### Starting a new project
1. Decide the application type, the threading model (from the table above), and whether it's a workspace. Say these choices and their reasons up front.
2. Check current versions of the toolchain and of the crates you'll use.
3. Create `rust-toolchain.toml`, the root `Cargo.toml` with the lints and profiles from [references/code-standards.md](references/code-standards.md), `clippy.toml`, and `deny.toml`.
4. Read the application-type reference and build from its skeleton.
5. Add tests, property tests, fuzz targets and benchmarks where [references/verification.md](references/verification.md) calls for them.
6. Run `python3 scripts/audit_rust.py <project-dir>` and the checks in non-negotiable 7. Fix everything they report.

### Changing existing code
1. Read the surrounding crate first and follow its structure. If it falls short of this skill (no lint config, `thiserror`, `unwrap`s), say so and propose fixing that as its own change, separate from the feature.
2. Before adding a dependency, check the allowlist and `std`. For anything else, write the `# why:` line.
3. Write the change with its error type, tests and (on a hot path) a benchmark.
4. Run the checks and the audit script.

### Reviewing Rust code
1. Run `python3 scripts/audit_rust.py <dir>` for the mechanical problems: banned and unjustified crates, panicking calls, unsafe without SAFETY comments, `#[allow]`, an old edition, missing lint config.
2. Then read for what a script can't see: logic errors, non-idiomatic code (clones to satisfy the borrow checker, index loops, flags and sentinels instead of enums, ad-hoc conversion methods instead of std traits), unhandled edge cases, error types that lose context, allocation or locking in hot paths, async where threads would do (or the reverse), unsound unsafe, API that will be hard to change.
3. Report findings ranked by severity: soundness and correctness first, then failure handling, then performance, then structure and style. Give each one a concrete fix.

## References

- [references/code-standards.md](references/code-standards.md): the lint configuration, `clippy.toml`, release profile and toolchain file to copy; idiomatic Rust; the panic, unsafe and arithmetic rules in detail; types, naming, size limits, docs; review checklist.
- [references/workspace.md](references/workspace.md): workspace manifests, crate boundaries, shared dependencies and lints.
- [references/errors.md](references/errors.md): hand-written error enums, `source()` chains, adding context, reporting at `main`, error types in libraries.
- [references/dependencies.md](references/dependencies.md): the allowlist, the banned list, how to evaluate any other crate, `deny.toml`.
- [references/performance.md](references/performance.md): data layout, allocation, dispatch, hashing, I/O, SIMD, release settings, profiling and benchmarking.
- [references/concurrency.md](references/concurrency.md): choosing threads or async, the hot/cold split with ring buffers (verified example), memory ordering, false sharing, backpressure.
- [references/gui-wgpu.md](references/gui-wgpu.md): raw wgpu + winit architecture, a compiling skeleton, frame loop, resource rules, building the UI, text, testing.
- [references/cli.md](references/cli.md), [references/services.md](references/services.md), [references/libraries.md](references/libraries.md), [references/embedded.md](references/embedded.md): per application type.
- [references/verification.md](references/verification.md): tests, proptest, cargo-fuzz, Miri, sanitizers, criterion, cargo-deny, the CI pipeline.
- `scripts/audit_rust.py`: scans a crate or workspace for the mechanical rule breaks above. `--json` for machine output, `--strict` to fail on warnings, `--cargo` to also run fmt, clippy and tests.

Sources: the code-quality rules adapt ideas from NASA/JPL's "Power of Ten" rules for safety-critical code (Holzmann, 2006), the Rust API Guidelines, the Rust Design Patterns book's idioms and anti-patterns, and the Clippy lint documentation. The GUI, service and firmware material draws on the wgpu, winit and tokio documentation and changelogs and the Rust Embedded Book. All code here was written for this skill and compiled against the versions named in each reference.
