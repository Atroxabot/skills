# Verification

The compiler and Clippy catch a lot, and tests catch behavior. At this bar each kind of risk gets the tool that's good at finding it:

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

## Contents
- Tests
- Property tests (verified example)
- Fuzzing
- Miri and sanitizers
- Benchmarks (verified example)
- The CI pipeline

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

In order, failing fast on the cheap checks:

```bash
cargo fmt --all --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace --all-features
cargo test --workspace --doc
cargo deny check
python3 <path-to-skill>/scripts/audit_rust.py . --strict
RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps
# when unsafe code exists:
cargo +nightly miri test -p <crates-with-unsafe>
# libraries, before release:
cargo semver-checks
# scheduled (nightly CI job):
cargo +nightly fuzz run <target> -- -max_total_time=600    # per target
cargo bench                                                 # against the stored baseline
```

Build with `--locked` in CI so a `Cargo.lock` that doesn't match `Cargo.toml` fails instead of being silently updated. Cache `~/.cargo/registry` and `target/` between runs, keyed on `Cargo.lock` and the toolchain version.
