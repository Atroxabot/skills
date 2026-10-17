# Verification

Verification has to catch real bugs without slowing development down. A tool that adds minutes to every change gets skipped or resented, and then it protects nothing. So checks are tiered by cost: the cheap ones run on every change, the full suite runs in CI where nobody waits on it, and the expensive ones run only when a change actually needs them.

## Contents
- When each check runs
- What each tool is for
- Tests
- Property tests (verified example)
- Fuzzing
- Miri and sanitizers
- Benchmarks (verified example)
- The CI pipeline

## When each check runs

| Tier | When | What | Time budget |
|---|---|---|---|
| **1. While working** | Every change, locally, before committing | `cargo fmt`, `cargo clippy --workspace --all-targets -- -D warnings`, `cargo test -p <crates you changed>` (property tests included), the audit script | Seconds on an incremental build. If it takes over a minute, fix the build or the tests (see below), not the habit |
| **2. Every pull request** | In CI, automatically | Tier 1 for the whole workspace, `cargo deny check`, `cargo doc` | Minutes, but nobody waits on it. Developers keep working |
| **3. Only when it applies** | Triggered by what changed, not routine | The rows below | Run once for the change, not on every edit |

Tier 3, with the trigger for each:

| Check | Run it when | Skip it when |
|---|---|---|
| Miri | Unsafe code, or a contract that unsafe code relies on, changed | No unsafe code changed. Most changes |
| AddressSanitizer / ThreadSanitizer (or valgrind) | Unsafe, FFI or lock-free code changed | Same |
| Fuzzing | A parser of untrusted input was added or changed: add or update its target and run it for a few minutes locally. Long runs happen on a nightly or weekly CI schedule | The change doesn't touch input parsing |
| Benchmarks | A hot path changed, or someone claims a speedup | The code isn't on a measured hot path |
| `cargo semver-checks` | Releasing a library | Applications; unreleased changes |

**The toolset is closed.** These are all the verification tools a project uses by default. Adding another (mutation testing, model checkers, coverage gates, more linters, a second test runner) needs a reason, the same way a dependency does: a specific kind of bug the current set misses, and evidence that the tool would have caught it. More tools mean slower builds, more configuration and more CI time, and past a point they find little the existing set doesn't.

### Keeping tier 1 fast

- **Unit tests run in milliseconds.** Tests that need a GPU, network, large data or real time are few, live in their own integration test file, and are the only slow part of the suite.
- **A crate's `cargo test` stays under about 10 seconds.** When it doesn't, find the slow tests and shrink their inputs, or move them into an integration test file in `tests/` and iterate with `cargo test -p <crate> --lib`, which runs only the unit tests. CI still runs everything.
- **Property tests use proptest's default case count (256) locally.** The scheduled CI job can raise it (`PROPTEST_CASES=10000`) where more cases are worth the time.
- **Test only the crates you changed** while working. The workspace layout makes that possible ([workspace.md](workspace.md)), and CI runs everything.
- **Build speed is test speed.** The settings in [workspace.md](workspace.md) ("Fast builds") apply to every tier.

## What each tool is for

| Risk | Tool |
|---|---|
| Wrong behavior on cases someone thought of | Unit and integration tests |
| Wrong behavior on cases nobody thought of | Property tests (`proptest`) |
| Crashes, hangs and blowups on hostile input | Fuzzing (`cargo-fuzz`) |
| Undefined behavior in unsafe code | Miri, AddressSanitizer |
| Data races in unsafe or lock-free code | ThreadSanitizer, `loom` |
| Performance regressions | Benchmarks (`criterion`) |
| Vulnerable, unlicensed or banned dependencies | `cargo deny` |
| Accidental breaking changes (libraries) | `cargo semver-checks` |

## Tests

- Unit tests in a `#[cfg(test)] mod tests` at the bottom of the file they test, so they can reach private items. Integration tests in `tests/` use only the public API, the way users do.
- Test behavior, not implementation: inputs and outputs, error variants, state after an operation. A test that breaks on every refactor without catching bugs is a cost.
- Every error path a caller can hit has a test that asserts the variant (`matches!(err, LoadConfigError::Parse { line: 2, .. })`), not the message text.
- Every bug fix comes with a test that fails before the fix.
- Tests are deterministic: no wall-clock time (inject `Instant`s), no real randomness (fixed seeds), no shared temp paths between tests, no network except to servers the test starts on port 0.
- Tests may `unwrap`, `expect`, index and panic. `clippy.toml` allows it there, because a panic is the right way for a test to fail.

## Property tests

A property test states something that must hold for *every* input, and `proptest` generates hundreds of inputs and shrinks any failure to a minimal case. Good properties:
- **Round-trip:** `decode(encode(x)) == x`.
- **Invariants:** a sorted output is sorted and is a permutation of the input; an average is within the min and max.
- **Agreement with a reference:** the optimized version gives the same result as a slow, obviously correct version (the right way to test SIMD paths and clever data structures).
- **Idempotence and commutativity** where the domain has them: `normalize(normalize(x)) == normalize(x)`.

Verified example (from the firmware core in [embedded.md](embedded.md)):

```rust
use fwcore::MovingAverage;
use proptest::prelude::*;

proptest! {
    // The average must stay within the smallest and largest sample of the current window,
    // for any input sequence. One property covers what dozens of hand-picked cases would.
    #[test]
    fn average_stays_within_window_bounds(samples in prop::collection::vec(any::<u16>(), 1..200)) {
        let mut avg = MovingAverage::<8>::new();
        for (i, &s) in samples.iter().enumerate() {
            let out = avg.push(s);
            let window = &samples[i.saturating_sub(7)..=i];
            let lo = *window.iter().min().unwrap();
            let hi = *window.iter().max().unwrap();
            prop_assert!((lo..=hi).contains(&out), "{out} outside {lo}..={hi}");
        }
    }
}
```

Commit the `proptest-regressions/` files that proptest writes when it finds a failure, so the failing case is retried on every run.

## Fuzzing

Every function that parses input from outside the process (files, network, IPC, user-provided config) gets a fuzz target. Fuzzers find the panics, infinite loops and memory blowups that example-based tests don't think of.

```bash
cargo install cargo-fuzz
cargo fuzz init                        # creates fuzz/, excluded from the workspace
cargo fuzz add parse_frame
cargo +nightly fuzz run parse_frame -- -max_total_time=300
```

```rust
// fuzz/fuzz_targets/parse_frame.rs
#![no_main]
use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    // Any input must produce Ok or Err, never a panic, hang or huge allocation.
    let _ignored = app_core::protocol::parse_frame(data);
});
```

- Make the target check more than "doesn't crash" where possible: if parsing succeeds, re-encode and check the round trip.
- Use `arbitrary` to fuzz structured inputs (a sequence of API calls, for example) instead of raw bytes.
- Run each target for a fixed time in CI (5 to 10 minutes per target, on a schedule if it's too slow for every push), keep the corpus in the repository or a cache, and add every crash input as a regular unit test once fixed.
- The fuzzer builds with debug assertions on, so `debug_assert!` invariants get checked on millions of inputs.

## Miri and sanitizers

For every crate containing unsafe code:

```bash
rustup +nightly component add miri
cargo +nightly miri test -p app-simd
```

Miri interprets the program and reports undefined behavior: out-of-bounds access, use after free, invalid values, aliasing violations, data races. It can't execute FFI or most platform intrinsics, so test the scalar fallback under Miri and the real path under sanitizers.

```bash
# AddressSanitizer: memory errors in unsafe code, FFI and intrinsics
RUSTFLAGS="-Zsanitizer=address" cargo +nightly test -Zbuild-std --target x86_64-unknown-linux-gnu -p app-simd

# ThreadSanitizer: data races in lock-free and concurrent code
RUSTFLAGS="-Zsanitizer=thread" cargo +nightly test -Zbuild-std --target x86_64-unknown-linux-gnu -p app-pipeline
```

For hand-written lock-free structures, `loom` (with a `# why:`, as a dev-dependency) explores every thread interleaving the memory model allows. It's the only practical way to test memory orderings.

Nightly is only for running these tools. The product is built and shipped with the pinned stable toolchain.

## Benchmarks

Hot paths have criterion benchmarks in the crate's `benches/`. Verified example:

```rust
use std::hint::black_box;

use criterion::{Criterion, criterion_group, criterion_main};
use fwcore::MovingAverage;

fn push_1k(c: &mut Criterion) {
    let input: Vec<u16> = (0..1024_u16).map(|i| i.wrapping_mul(7919)).collect();
    c.bench_function("moving_average_push_1k", |b| {
        b.iter(|| {
            let mut avg = MovingAverage::<16>::new();
            let mut last = 0;
            for &s in black_box(&input) {
                last = avg.push(s);
            }
            last
        });
    });
}

criterion_group!(benches, push_1k);
criterion_main!(benches);
```

```toml
# Cargo.toml of the crate
[[bench]]
name = "moving_average"
harness = false
```

- `black_box` the inputs, and return the result from the closure, so the compiler can't optimize the work away.
- Realistic sizes and data. Benchmarking 10 elements says nothing about 10 million.
- Compare against a baseline: `cargo bench -- --save-baseline main` on the base branch, then `cargo bench -- --baseline main` on the change. Put the numbers, hardware and input in the commit or PR description.
- CI machines are noisy. Run benchmarks in CI to catch large regressions only (or on dedicated hardware), and confirm small differences locally.

## The CI pipeline

Every pull request (tier 2), failing fast on the cheap checks:

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features --locked -- -D warnings
cargo test --workspace --all-features --locked          # includes doctests
cargo deny check
python3 <path-to-skill>/scripts/audit_rust.py . --strict
RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps --locked
```

Only when the pull request touches the relevant code (tier 3). CI can decide this from the changed paths, or the author runs it and says so in the PR:

```bash
cargo +nightly miri test -p <crate-with-changed-unsafe>
cargo +nightly fuzz run <changed-parser-target> -- -max_total_time=300
cargo bench -p <crate> -- --baseline main
```

On a schedule (nightly or weekly), never per push:

```bash
cargo +nightly fuzz run <target> -- -max_total_time=600       # each target
PROPTEST_CASES=10000 cargo test --workspace --release
```

At release (libraries): `cargo semver-checks`.

`--locked` makes CI fail when `Cargo.lock` doesn't match `Cargo.toml`, instead of silently updating it. Cache `~/.cargo/registry`, `~/.cargo/git` and `target/` between runs, keyed on `Cargo.lock`, the toolchain version and the OS.
