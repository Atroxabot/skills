# Performance

Performance comes from design decisions made early (data layout, allocation strategy, threading model) and is confirmed by measurement. Micro-optimizations without a profile mostly make code harder to read and leave the real bottleneck alone.

## Contents
- How to work
- Data layout
- Allocation
- Dispatch, inlining and generics
- Bounds checks and vectorization
- Hashing, strings, I/O
- SIMD
- Build settings
- Profiling and benchmarking tools

## How to work

1. **Set a target** where it matters: frame time (8.3 ms at 120 Hz), p99 latency, throughput, startup time, memory ceiling. Without a target there's no way to know when to stop.
2. **Design for it.** Choose the data layout, the threading model ([concurrency.md](concurrency.md)) and the allocation strategy up front. These are the expensive things to change later.
3. **Write clear code**, following the rules below by default. They cost nothing in readability.
4. **Measure** with a benchmark or a profiler on realistic input, in release mode.
5. **Optimize what the profile shows**, re-measure, and keep the change only if it helps. Record the before and after numbers in the commit message.

## Data layout

- **Contiguous memory first.** `Vec<T>` of plain structs beats linked lists, trees of `Box`es and maps of `Rc` for almost every workload, because the CPU prefetches sequential memory and a cache miss costs around 100 cycles.
- **Struct of arrays for hot loops** that touch a few fields of many items: `positions: Vec<Vec3>, velocities: Vec<Vec3>` instead of `Vec<Particle>` when the update loop never reads the particle's name and color. This vectorizes and fits more useful data per cache line.
- **Split hot and cold fields.** Rarely used data (names, debug info, metadata) moves to a side table indexed by the same id, so the hot struct stays small.
- **Indices instead of pointers** for graphs and trees: `Vec<Node>` with `u32` indices. Smaller than pointers, no borrow-checker fights, cache-friendly, and serializable.
- **Smallest correct types.** `u32` indices instead of `usize` when four billion is enough, enums instead of strings, `Box<str>` instead of `String` for strings that never grow. Check sizes with `size_of` in a test when a type is hot.
- **Watch padding.** Rust reorders struct fields to minimize it unless `#[repr(C)]` is set. For `#[repr(C)]` GPU structs, order fields by alignment yourself.

## Allocation

- **No allocation in the steady state of a hot path.** Allocate at startup or on the first use, then reuse.
- `Vec::with_capacity` when the size is known or bounded. `clear()` and refill instead of creating a new `Vec`. Keep scratch buffers in the owning struct and pass `&mut` to helpers.
- `extend` and `collect` from iterators with an exact size hint allocate once.
- Return iterators (`impl Iterator`) instead of `Vec` when the caller may only need part of the output.
- Avoid `clone()` to satisfy the borrow checker. Restructure the borrows first. `Arc` clones are cheap but are atomic operations that contend across cores.
- Arenas (a `Vec<T>` you index into, cleared per frame or per request) for many short-lived objects with the same lifetime.
- Only replace the global allocator (`mimalloc`) after a profile shows allocator time or contention, and benchmark the change.

## Dispatch, inlining and generics

- **Static dispatch in hot code:** generics or an `enum` over the known variants, not `Box<dyn Trait>`. A `match` on an enum can be inlined and branch-predicted. A virtual call can't be inlined.
- `dyn Trait` is fine at boundaries that run rarely (plugin registration, configuration), and it shrinks compile time and binary size compared with heavy generics.
- `#[inline]` is only needed for small functions called across crates (LTO handles much of this anyway). `#[inline(always)]` only with a benchmark showing the gain. `#[cold]` on error-handling paths helps the compiler lay out the hot path.
- Watch for generic code bloat: a generic function instantiated for 20 types is 20 copies. Move the type-independent body into a non-generic inner function.

## Bounds checks and vectorization

- Iterators (`iter`, `zip`, `chunks_exact`, `windows`) carry their bounds with them, so the compiler drops the checks and can vectorize. This also satisfies the no-indexing rule.
- When indexing is unavoidable, check once before the loop (`let s = s.get(..n)?;`), and the compiler can drop the per-iteration checks against the re-sliced bounds.
- `chunks_exact(N)` with a constant `N`, plus `remainder()`, gives the compiler fixed-width blocks that turn into SIMD instructions.
- Check whether a loop vectorized with `cargo asm` (from `cargo-show-asm`) instead of guessing.
- Branchless forms (`select`-style arithmetic, `min`/`max`) help in inner loops with unpredictable branches. Measure, since the compiler often does this already.

## Hashing, strings, I/O

- `HashMap` with the default hasher is DoS-resistant and slower. For keys that aren't attacker-controlled on a measured hot path, use a faster hasher (`foldhash`, `rustc-hash`, with a `# why:`). For small, dense integer keys, a `Vec` indexed by the key beats any map.
- Strings: build into a reused `String` with `write!`, not repeated `format!`. Work on `&str` slices and bytes. Avoid `to_string()` in loops. Compare and hash interned ids, not strings, in hot paths.
- I/O: wrap files and sockets in `BufReader`/`BufWriter`, lock `stdout` once per batch of writes, and read in large chunks. Stream input instead of loading whole files when inputs can be large. `memmap2` (with a `# why:`) for random access into large read-only files. Mapping is an unsafe call (another process can change the file underneath), so it goes through the unsafe rule.
- Parsing: parse from `&[u8]` without copying, and validate UTF-8 once at the boundary, not per field.

## SIMD

1. First, write the loop so the compiler auto-vectorizes it (`chunks_exact`, no early exits, no aliasing doubts), and check the assembly.
2. If that's not enough and the profile says this loop matters, use `std::arch` intrinsics behind runtime detection (`is_x86_feature_detected!`) with a scalar fallback. That's unsafe code under the unsafe rule: its own module, SAFETY comments, the scalar path tested under Miri, a property test that the SIMD and scalar paths agree on random input, and a benchmark in the module's `#[expect]` reason.
3. Portable SIMD (`std::simd`) is nightly-only, so it isn't used in shipped code.

## Build settings

The release profile in [code-standards.md](code-standards.md) (`lto = "fat"`, `codegen-units = 1`, `panic = "abort"`) is the baseline. Beyond it:

- **`target-cpu`**: `-C target-cpu=native` only for binaries built and run on the same machine type (servers we deploy to known hardware). Distributed binaries target a baseline (`x86-64-v2` or `x86-64-v3` if the user base allows it) and use runtime detection for anything newer.
- **Profile-guided optimization** with `cargo-pgo` for binaries where 10-20% matters and a representative workload exists. Record the workload in the repo so the profile can be regenerated.
- **Size-constrained targets** (firmware, wasm): `opt-level = "s"` or `"z"`, measured against `3`, since smaller code can also be faster when it fits in cache.

## Profiling and benchmarking tools

| Question | Tool |
|---|---|
| Where does the time go? | `perf record` + `perf report`, `samply`, or `cargo flamegraph`, on a release build with `debug = "line-tables-only"` |
| Did this change make it faster? | `criterion` benchmarks with `--save-baseline main` and `--baseline main`; see [verification.md](verification.md) |
| Where are the allocations? | `heaptrack`, or the `dhat` crate in a dev-only build |
| Did this loop vectorize, and did this call get inlined? | `cargo asm -p <crate> <path::to::fn>` |
| Cache misses and branch mispredictions | `perf stat -e cache-misses,branch-misses` |
| Frame timing on the GPU | wgpu timestamp queries; RenderDoc or the platform's GPU profiler |
| Build time | `cargo build --timings` |
| Binary size | `cargo bloat --release` |

Benchmark rules: release mode, realistic input sizes, warm caches unless cold is the case that matters, a quiet machine, and enough iterations for criterion to report a confidence interval. Report the hardware, the input, and both numbers for a change.
