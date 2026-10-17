# Dependencies

Every crate we depend on is code we ship without reviewing, a supply-chain entry point, compile time, and something to keep upgraded. So dependencies are added on purpose, not by reflex.

## The process

1. **Check `std` first.** It covers more than people remember: `LazyLock`/`OnceLock` (instead of `lazy_static`, `once_cell`), `std::io::IsTerminal` (instead of `atty`), `std::sync::mpsc` including bounded `sync_channel` (instead of `crossbeam-channel` off the hot path), `std::thread::scope`, `std::hash::DefaultHasher`, `std::num::NonZero*`, `std::time`, `std::path`, `std::process`, `std::net`, `std::fs`, `std::os::*`, `std::arch` with runtime feature detection.
2. **Check whether it's small enough to write.** A 50-line function you own beats a crate with 30 transitive dependencies: an argument splitter, a CRC, a ring of fixed size, a `CachePadded` wrapper (`#[repr(align(128))] struct CachePadded<T>(T);`), a hex encoder.
3. **Use the allowlist** below for the job it names.
4. **Anything else needs a `# why:` comment** on its line in `Cargo.toml`, written after doing the evaluation in the next section:

```toml
[dependencies]
wgpu = "30"
cosmic-text = "0.15"
jiff = "0.2"  # why: time zones and calendar arithmetic for user-facing schedules; std has neither
```

The audit script fails a direct dependency that's neither allowlisted nor justified, and fails a banned one whatever the comment says.

When adding any crate, including allowlisted ones: pin a caret version of the current release (`cargo search <name>`), turn off default features and enable only what's used (`default-features = false, features = [...]`), and in a workspace declare it once in `[workspace.dependencies]`.

## Evaluating a crate that isn't on the list

Answer each of these in the review, briefly:

- **Need:** what it does that we can't reasonably write and maintain ourselves. "Saves an afternoon" is not enough for a permanent dependency. "Implements a protocol or format correctly, which is hard" is.
- **Maintenance:** releases in the last year, open soundness issues, more than one maintainer or an organization behind it, and how it responded to past RustSec advisories.
- **Weight:** `cargo tree -e normal -i <crate>` before and after. New transitive crates, duplicated versions (`cargo tree -d`), build time (`cargo build --timings`), binary size (`cargo bloat` if it matters).
- **Unsafe:** how much unsafe it contains and whether it's justified. `cargo geiger` gives a count; for crates on a hot or security-sensitive path, read the unsafe parts.
- **License:** compatible with `deny.toml`'s allowed list.
- **Build scripts and proc macros:** they run code on the build machine. A crate with a `build.rs` that downloads or compiles native code needs a stronger reason.

## Allowlist

Pre-approved for the use named. Using one outside its use still needs a `# why:`.

| Crate | Use |
|---|---|
| **GUI and rendering** | |
| `wgpu` | All GPU rendering and compute. |
| `winit` | Windows, input, event loop. Latest stable release, not a beta. |
| `bytemuck` (with `derive`) | Casting `#[repr(C)]` vertex and uniform structs to bytes without unsafe. |
| `pollster` | Blocking on wgpu's async setup calls in apps without an async runtime. |
| `glam` | Vector and matrix math (SIMD-backed, `bytemuck`-compatible). |
| `fontdue` | Glyph rasterization for UIs with simple scripts (Latin, Cyrillic, Greek). |
| `cosmic-text` | Text shaping, bidirectional text and layout when the UI must handle any script or rich text. |
| `png`, `zune-jpeg` | Decoding those image formats. Not the umbrella `image` crate, which pulls in every format. |
| **Concurrency** | |
| `rayon` | Data-parallel CPU work. |
| `rtrb` | Lock-free SPSC ring buffers between hot and cold threads. |
| `crossbeam-queue` | Lock-free bounded MPMC queue (`ArrayQueue`) when several producers or consumers share a hot path. |
| `core_affinity` | Pinning hot threads to cores. |
| **Async and networking** (only when the concurrency choice is async) | |
| `tokio` | The async runtime, with only the features used. Never `"full"`. |
| `tokio-util` | `CancellationToken`, codecs. |
| `hyper`, `hyper-util`, `http`, `http-body-util`, `bytes` | HTTP. |
| `axum` | HTTP services with more than a handful of routes. |
| `rustls`, `tokio-rustls`, `webpki-roots` | TLS. Not OpenSSL, unless a platform requirement forces it (with a `# why:`). |
| **Security** | |
| `ring`, `sha2`, `hmac`, `blake3`, `subtle` | Cryptographic primitives. Never write your own cryptography. |
| **Data** | |
| `serde` (with `derive`), `serde_json` | Serialization, when JSON is the format we have to speak. For formats we control, a hand-written binary encoding is often faster and simpler. |
| **Observability** | |
| `tracing`, `tracing-subscriber` | Structured logs and spans in services. CLIs usually need neither. |
| **CLI** | |
| `lexopt` | Argument parsing. No dependencies, no macros, a few hundred lines. |
| **Embedded** | |
| `cortex-m`, `cortex-m-rt`, `embedded-hal`, `embedded-hal-async`, `embedded-io`, `critical-section`, `heapless`, `defmt`, `defmt-rtt`, `panic-probe`, `embassy-*`, `rtic`, and the chip's PAC/HAL (`stm32*`, `nrf*`, `rp2040-*`, `rp235x-*`, `esp-*`) | Firmware. |
| **Dev and test only** (`[dev-dependencies]`) | |
| `criterion` | Benchmarks. |
| `proptest` | Property tests. |
| `libfuzzer-sys`, `arbitrary` | Fuzz targets. |
| `embedded-test`, `defmt-test` | On-target firmware tests. |
| `naga` (with `wgsl-in`) | Validating WGSL shaders in unit tests. Same major version as `wgpu`. |

Pre-vetted but conditional. These still need a `# why:` that names the measurement or requirement:
- `mimalloc`: replacing the global allocator, after a profile shows allocator contention in a multi-threaded binary.
- `foldhash` or `rustc-hash`: a faster hasher for `HashMap`s with keys that aren't attacker-controlled, after a profile shows hashing in a hot path. The std hasher (SipHash) is slower on purpose: it resists hash-flooding attacks, so keys from the network keep it.
- `clap`: only when a CLI needs generated shell completions or a large tree of subcommands that `lexopt` makes unwieldy.
- `jiff`: time zones and calendar arithmetic.

## Banned

Never added, with or without a `# why:`:

| Crate | Reason | Use instead |
|---|---|---|
| `thiserror`, `anyhow`, `eyre`, `color-eyre`, `snafu`, `quick-error`, `displaydoc`, `failure`, `error-chain` | Errors are written by hand ([errors.md](errors.md)). | Hand-written enums |
| `lazy_static`, `once_cell` | In std since 1.80. | `LazyLock`, `OnceLock` |
| `egui`, `eframe`, `egui-wgpu`, `egui-winit`, `iced`, `slint`, `gtk`, `gtk4`, `relm4`, `tauri`, `druid`, `xilem`, `masonry`, `floem`, `vizia`, `freya`, `dioxus`, `gpui`, `fltk`, `makepad-widgets`, `imgui`, `dear-imgui-*` | GUIs are built on raw wgpu ([gui-wgpu.md](gui-wgpu.md)). A framework decides the frame loop, the allocation pattern and the draw-call count for us. | Hand-built UI on wgpu |
| `bevy`, `macroquad`, `ggez`, `fyrox`, `pixels`, `softbuffer`, `minifb` | Engines and framebuffer layers on top of, or instead of, wgpu. | wgpu |
| `glium`, `glow`, `glutin`, `gl`, `sdl2`, `sdl3`, `raylib`, `vulkano`, `ash` | Other graphics APIs. wgpu covers Vulkan, Metal, DX12 and WebGPU behind one safe API. | wgpu |
| `async-std` | Discontinued. | `tokio`, or threads |
| `atty` | Unmaintained, with an advisory. | `std::io::IsTerminal` |

## `deny.toml`

Run `cargo deny check` in CI. A starting point:

```toml
[graph]
all-features = true

[advisories]
version = 2
yanked = "deny"
ignore = []                 # every entry needs a comment: advisory id, why it doesn't apply, review date

[licenses]
version = 2
allow = ["MIT", "Apache-2.0", "Apache-2.0 WITH LLVM-exception", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unicode-3.0", "Zlib"]
confidence-threshold = 0.9

[bans]
multiple-versions = "warn"  # wgpu's tree has some duplicates; review them, don't fail on them
wildcards = "deny"
deny = [
    { name = "async-std" },
    { name = "atty" },
]

[sources]
unknown-registry = "deny"
unknown-git = "deny"
```

Most of the banned list isn't in `bans.deny`, because cargo-deny checks the whole dependency tree, and popular crates pull some of them in transitively: wgpu brings `thiserror`, and winit brings `once_cell`. The rule is about what our code uses, so the audit script enforces it on direct dependencies instead. `cargo deny check advisories` covers the RustSec database, so `cargo audit` isn't needed separately.
