# Code standards

The configuration below has been compiled against Rust 1.97 with a wgpu/winit app, a threaded pipeline and a CLI under it. Every lint name in it exists, and the code in this skill's references passes it. Copy it as is. When a newer Clippy renames or adds a lint, `cargo clippy` warns about unknown lints, so you'll see it.

## Contents
- Files to copy: toolchain, lints, clippy.toml, profiles
- The panic rule in practice
- The unsafe rule in practice
- Arithmetic and casts
- Types and API shape
- Functions, modules and control flow
- Naming, comments and docs
- Review checklist

## Files to copy

### `rust-toolchain.toml`

```toml
[toolchain]
channel = "1.97.0"          # exact stable version; bump on purpose, in its own commit
components = ["rustfmt", "clippy"]
profile = "minimal"
```

### Lints in the root `Cargo.toml`

In a workspace this is `[workspace.lints.rust]` / `[workspace.lints.clippy]` in the root manifest, and each member has `[lints] workspace = true`. In a single crate it's `[lints.rust]` / `[lints.clippy]`.

```toml
[workspace.lints.rust]
unsafe_code = "deny"                    # opt in per module with #[expect(unsafe_code, reason = "...")]
unsafe_op_in_unsafe_fn = "deny"         # unsafe fn bodies still need unsafe blocks, each with its own SAFETY comment
unused_must_use = "deny"
missing_debug_implementations = "warn"
unreachable_pub = "warn"                # pub(crate) unless it's really part of the crate's API
unused_qualifications = "warn"
# Libraries also add: missing_docs = "warn"

[workspace.lints.clippy]
all = { level = "deny", priority = -1 }
pedantic = { level = "deny", priority = -1 }
# No panics outside tests (clippy.toml allows them in tests)
unwrap_used = "deny"
expect_used = "deny"
panic = "deny"
todo = "deny"
unimplemented = "deny"
unreachable = "deny"
indexing_slicing = "deny"
string_slice = "deny"                   # &s[a..b] panics on a non-char boundary
exit = "deny"                           # process::exit skips destructors; return ExitCode from main
# Unsafe hygiene
undocumented_unsafe_blocks = "deny"
multiple_unsafe_ops_per_block = "deny"
mem_forget = "deny"
# Exceptions must be explained and must expire
allow_attributes = "deny"               # use #[expect], which errors once the lint stops firing
allow_attributes_without_reason = "deny"
# Correctness and clarity
let_underscore_must_use = "deny"
await_holding_lock = "deny"
clone_on_ref_ptr = "deny"               # Arc::clone(&x), so a cheap pointer copy never looks like a deep clone
rc_buffer = "deny"
float_cmp_const = "deny"
lossy_float_literal = "deny"
rest_pat_in_fully_bound_structs = "deny"
same_name_method = "deny"
unneeded_field_pattern = "deny"
verbose_file_reads = "deny"
infinite_loop = "deny"                  # a loop that never ends must say so with `-> !`
dbg_macro = "deny"
# Libraries also add: print_stdout = "deny", print_stderr = "deny"
```

Why deny and not warn: warnings get scrolled past, and a warning that's tolerated once is tolerated forever. CI also runs `cargo clippy -- -D warnings`, so a lint that's only `warn` above (like `unreachable_pub`) still blocks merging.

### `clippy.toml`

```toml
allow-unwrap-in-tests = true
allow-expect-in-tests = true
allow-panic-in-tests = true
allow-indexing-slicing-in-tests = true
allow-dbg-in-tests = true
too-many-lines-threshold = 60           # a function longer than a screen is doing more than one thing
```

Tests are where a panic is the right failure: it fails the test with a location. That's why the panic lints are relaxed there and nowhere else.

### Profiles in the root `Cargo.toml`

```toml
[profile.release]
lto = "fat"                  # cross-crate inlining; often 5-20% on real code
codegen-units = 1            # better optimization, slower build
panic = "abort"              # no unwinding tables; a panic is a bug, so fail fast
overflow-checks = true       # see "Arithmetic" below
debug = "line-tables-only"   # usable backtraces and profiles at little size cost

[profile.dev.package."*"]
opt-level = 2                # optimized dependencies keep debug builds of GUI apps and games usable

[profile.bench]
inherits = "release"
debug = true                 # full symbols for profiling benchmarks
```

`panic = "abort"` is right for binaries. A library doesn't choose this: the profile of the final binary decides.

## The panic rule in practice

| Instead of | Write |
|---|---|
| `v[i]` | `v.get(i)` with a handled `None`, or restructure as an iterator so there's no index |
| `&s[a..b]` | `s.get(a..b)`, or work in `char_indices` / bytes |
| `x.unwrap()` on an `Option` | `let Some(x) = x else { return Err(...) };`, `ok_or(...)?`, or a default that's actually correct |
| `.lock().unwrap()` | `.lock().unwrap_or_else(PoisonError::into_inner)` when the data is still valid after a panic elsewhere (with `panic = "abort"` it can't be poisoned), otherwise map to an error |
| `"…".parse().unwrap()` on a constant | a `const` of the parsed type, or parse once at startup and return the error |
| `assert!(cond)` for an invariant | `debug_assert!(cond)` plus a type that makes the bad state impossible, or a `Result` when the condition depends on input |
| `unreachable!()` in a `match` | make the match exhaustive over a narrower type, or return an error variant that says what was assumed |
| `Duration::from_secs_f64(x)` (panics on negative or NaN) | `Duration::try_from_secs_f64(x)` |
| `slice.split_at(n)` | `slice.split_at_checked(n)` |
| `u32::try_from(x).unwrap()` | `u32::try_from(x).map_err(...)?`, or `.unwrap_or(u32::MAX)` where clamping is the correct behavior and a comment says so |

Watch for panics that don't look like panics: integer division by zero, `RefCell::borrow_mut` while borrowed, `Vec::with_capacity` overflowing, `Instant` subtraction going backwards (use `saturating_duration_since`), `copy_from_slice` with mismatched lengths, and `println!` on a closed pipe. The audit script finds the obvious ones. Reading finds the rest.

Compile-time assertions (`const _: () = assert!(...)`, or an associated `const` that a constructor evaluates) are also allowed: they fail the build, never the running program.

`debug_assert!` is allowed in non-test code because it compiles out of release builds and documents an invariant that tests, property tests and fuzzing then check on every run.

## The unsafe rule in practice

Unsafe is allowed for three things: FFI, hardware or OS interfaces with no safe wrapper, and a speedup that a benchmark shows and safe code can't reach (for example `std::arch` intrinsics behind runtime feature detection). For anything else the answer is no.

```rust
// src/simd.rs
#![expect(unsafe_code, reason = "AVX2 kernel for sum_u32; 3.1x over the safe loop, see benches/sum.rs")]

/// Sums `values`, using AVX2 when the CPU has it.
pub fn sum_u32(values: &[u32]) -> u64 {
    if std::arch::is_x86_feature_detected!("avx2") {
        // SAFETY: the avx2 feature was detected at runtime on this CPU just above.
        unsafe { sum_u32_avx2(values) }
    } else {
        values.iter().map(|&v| u64::from(v)).sum()
    }
}

/// # Safety
///
/// The CPU must support AVX2.
#[target_feature(enable = "avx2")]
unsafe fn sum_u32_avx2(values: &[u32]) -> u64 { /* ... */ }
```

The rules, and why:
- **One module per unsafe concern**, opted in with `#[expect(unsafe_code, reason)]`. A reviewer can find all of it with one search and give it extra attention.
- **One unsafe operation per block, each with `// SAFETY:`** explaining why the preconditions hold *at this point*, not restating what the function does.
- **Every `unsafe fn` and `unsafe trait` has a `# Safety` section** listing what the caller must guarantee.
- **A safe function wraps it**, with the checks that make the unsafe call sound. Callers never see `unsafe`.
- **Tested under Miri** (`cargo +nightly miri test -p <crate>`) and AddressSanitizer. Miri can't run FFI or most intrinsics; for those, test the safe fallback under Miri and the real path under ASan.
- Edition 2024 syntax: `unsafe extern "C" { ... }`, `#[unsafe(no_mangle)]`, `#[unsafe(export_name = "...")]`. Never `static mut` (references to it are denied in 2024); use atomics, `OnceLock`, `Mutex`, or `critical_section::Mutex` on embedded.

## Arithmetic and casts

- Release keeps `overflow-checks = true`. Silent wraparound turns a bug into corrupt data that surfaces far from its cause. A crash with a location is the better failure. The cost is a predicted branch, usually under a few percent, and hot loops avoid even that with explicit operations.
- Values from outside the process (input, files, network, config) use `checked_*` and return an error, or `saturating_*` when clamping is the correct behavior.
- Inner loops whose bounds are proven use `wrapping_*` or are structured so overflow can't happen (`u64` accumulators for `u32` sums). Say in a comment why it's in bounds.
- No `as` for numeric conversions that can lose information. Use `From` for widening, `TryFrom` for narrowing, and `#[expect(clippy::cast_precision_loss, reason = "...")]` only where the loss is understood (window sizes into `f32`). The pedantic cast lints enforce this.
- Floating point: never compare with `==` except against an exact constant whose meaning is exact. Use `total_cmp` for sorting. NaN must be handled where it can arise, especially at input boundaries.
- Division and remainder: the divisor can't be zero by construction (`NonZeroU32`), or it's checked.

## Types and API shape

- **Make illegal states unrepresentable.** An enum with data per state instead of a struct with flags and `Option`s that are "only set when". Typestate (`Connection<Open>`) when the order of operations matters.
- **Newtypes for units and identifiers**: `struct UserId(u64)`, `struct Millis(u64)`. Mixing up two `u64`s is a bug the compiler can catch for free.
- **Parse at the boundary, then trust the types.** Input becomes a validated type once (`Port`, `NonEmptyStr`, `Config`). Code past the boundary never re-checks.
- `#[must_use]` on functions whose result means something (Clippy's `must_use_candidate` in pedantic flags many).
- Derive `Debug` on every type. Derive `Clone`, `Copy`, `PartialEq`, `Eq`, `Hash` and `Default` when they're meaningful, not by reflex: `Copy` on a large struct hides expensive copies.
- Borrow in parameters (`&str`, `&[T]`, `impl AsRef<Path>`), own in return values and struct fields. Use `Cow` only when measured allocation savings justify it.
- Avoid `Rc<RefCell<_>>` and `Arc<Mutex<_>>` webs. They move borrow checking to run time, where it panics. Prefer clear ownership: one owner, `&mut` passed down, indices into arenas for graphs.
- No global mutable state. Pass configuration and handles explicitly. `LazyLock` is fine for immutable tables computed once.

## Functions, modules and control flow

These come from the same thinking as NASA/JPL's "Power of Ten" rules for safety-critical code, adapted to what Rust already guarantees:

- **Functions at most 60 lines** (enforced through `too-many-lines-threshold`). Nesting at most about three levels; use early returns and `let ... else`.
- **No unbounded recursion.** Recursion needs a documented depth bound tied to input limits, and is banned outright in firmware and on hot paths. Deep input (nested JSON, trees) is processed with an explicit stack with a size limit.
- **Loops over external input have a bound.** A `loop` that reads from the network or a file stops at a maximum count, size or deadline, so malformed input can't spin it forever. Intentional infinite loops (event loops, firmware main loops) return `!`.
- **Check every result.** `let _ = fallible()` is denied for `#[must_use]` values. When ignoring is right, write `let _ignored = ...` with a comment, or match and handle.
- **Smallest scope.** Declare variables where they're first needed, keep items `pub(crate)` or private unless they're the crate's API, and keep `mut` local.
- Modules by domain, not by kind: `order/` holding its types, parsing and errors, not `types.rs`, `errors.rs`, `utils.rs` for the whole crate. A `utils` module collects unrelated code nobody owns.

## Naming, comments and docs

- Follow the Rust API Guidelines naming: `as_` (free, borrowed), `to_` (costly), `into_` (consuming); `iter`, `iter_mut`, `into_iter`; `try_` for fallible variants; no `get_` prefix on plain getters.
- Names say what something is in the domain: `pending_orders`, not `data`, `list` or `tmp`.
- Comments explain *why*: the constraint, the measured reason, the bug this avoids. Code already says what it does. A comment that restates the code goes stale and starts lying.
- Every `pub` item in a library has a doc comment. Public fallible functions have an `# Errors` section (pedantic enforces it), and anything with preconditions has `# Panics` (which should be empty) or `# Safety`.
- No `TODO`, `FIXME` or `XXX` in merged code. Either do it, or open an issue and reference its number.
- No commented-out code. Version control remembers it.

## Review checklist

1. **Soundness:** every unsafe block has a correct SAFETY argument; no data races; `Send`/`Sync` impls are justified.
2. **Panics:** no panicking calls, indexing, slicing, division or arithmetic that can fail on reachable input.
3. **Errors:** every failure is returned with enough context to act on; nothing is swallowed; error types don't lump unrelated failures together.
4. **Input:** everything from outside is parsed and bounded (sizes, counts, depth, time).
5. **Concurrency:** the threading model matches the workload; no locks held across `.await`; no blocking calls on async workers; atomics have the weakest *correct* ordering with a comment on why.
6. **Performance:** no allocation, locking or dynamic dispatch in hot loops; data layout fits the access pattern; claims have benchmarks.
7. **Dependencies:** each new crate is on the allowlist or has a `# why:`; no banned crates.
8. **Tests:** new behavior and every fixed bug are tested; parsers have fuzz targets; invariants have property tests.
9. **Structure:** functions small, names meaningful, visibility minimal, comments explain why.
