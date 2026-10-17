---
name: rust-gui
description: Builds GUI apps, editors, games and visualizations in Rust on raw wgpu and winit with a hand-built UI, never a UI framework or engine (no egui, iced, Slint, GTK, Tauri, Bevy). Starts from a verified, runnable workspace skeleton (core, renderer and app crates) with redraw on demand, instanced batched drawing, every surface state handled, a non-panicking GPU error handler, grapheme-aware text input with IME support, the OS clipboard, non-blocking native file dialogs, and an offscreen render test. Covers layout, text rendering with a glyph atlas, accessibility with accesskit, color spaces, frame-time budgets and GPU profiling. Use with the rust-dev skill for general Rust standards. Use when the user asks to build, scaffold, extend, debug, review or speed up a Rust desktop app, GUI, editor, tool window, game, visualization or renderer, write wgpu, winit or WGSL code, render text, handle keyboard, IME, clipboard or file dialogs, add screen reader support, or fix frame drops or stutter.
---

# Rust GUI apps on raw wgpu

This skill covers building graphical Rust applications: desktop apps, editors, tools, games and visualizations. It assumes the **rust-dev** skill's general standards (no panics outside tests, hand-written error types, the dependency allowlist, strict lints, workspaces). Load rust-dev as well when writing the code. The skeleton here already follows those standards, and its lint configuration enforces them.

## The rule: raw wgpu and winit, no framework

Every GUI renders with **wgpu** directly, on a window and event loop from **winit**, with a UI we build ourselves. Never egui, eframe, iced, Slint, GTK, Tauri, Dioxus, druid, xilem, imgui, Bevy, macroquad, pixels, or another graphics API (OpenGL crates, SDL, raylib, ash, vulkano).

Why: what decides whether a UI feels instant is the frame loop, what gets allocated per frame, how many draw calls and state changes a frame takes, and when the app sleeps. A framework decides all of those for us, tuned for generality. Owning the renderer makes each one a decision we make and can measure. wgpu gives one safe API over Vulkan, Metal, DX12 and WebGPU, so owning the renderer doesn't mean writing it four times.

The price is that we also own what frameworks provide for free: widgets and layout, text rendering, text input with input methods, the clipboard, file dialogs and accessibility. [references/ui.md](references/ui.md) covers each of them, so they're decided at the start instead of discovered late.

## Start from the skeleton

`references/skeleton/` is a complete workspace to copy as the start of every GUI app. It passes the rust-dev lint set, its audit script and `cargo deny check`. Its tests pass on a software Vulkan driver. It was also run under a virtual X display, where it draws correctly. Keystrokes typed into it (including non-ASCII) edit the text field, select-all, copy, cut and paste go through the real clipboard, and opening the file dialog doesn't freeze the window.

| File | What it shows |
|---|---|
| `Cargo.toml`, `clippy.toml`, `rust-toolchain.toml`, `deny.toml`, `Cargo.lock` | Workspace policy (lints, profiles, pinned toolchain, dependency checks) and the exact versions it was verified with |
| `crates/app-core/src/draw.rs` | The draw list type (`Quad`) shared by the UI and the renderer |
| `crates/app-core/src/text_field.rs` | Text editing: caret, selection, IME composition, grapheme-aware movement and deletion, bounded input. Unit tests and a property test over random edit sequences |
| `crates/app-render/src/lib.rs`, `quad.wgsl` | `Renderer`: one pipeline, instanced quads, one draw call, persistent buffers that grow geometrically. Renders into any texture view. Tests: shader validation and an offscreen render with pixel readback |
| `crates/app/src/main.rs` | winit event loop with user events, redraw on demand, IME setup, input routing |
| `crates/app/src/gpu.rs` | `Gpu`: device, surface, every surface state, the error handler that replaces wgpu's panicking default |
| `crates/app/src/input.rs` | Keyboard and IME events into the text field; clipboard shortcuts |
| `crates/app/src/dialogs.rs` | A native file dialog that doesn't block the frame loop |
| `crates/app/src/error.rs` | The app's hand-written error type and the `Report` helper |

The window title stands in for text rendering (it shows the field's text with `|` at the caret). Replace it with real text rendering when building the actual app.

### Versions

Verified in October 2026 with **wgpu 30.0.1**, **winit 0.30.13**, **arboard 3.7**, **rfd 0.17**, **unicode-segmentation 1.13** and **naga 30**. `Cargo.lock` pins them. wgpu ships a major version every few months and changes its API each time (recent majors changed how frames are acquired and presented, how buffers are mapped, and what pipeline descriptors contain). Before starting:

```bash
cargo search wgpu --limit 1
cargo search winit --limit 1     # the latest *stable* winit, not a beta
```

If a newer major exists, read the changelog entries since the skeleton's version, update the dependency, and fix what the compiler reports, before building features on it.

## Architecture

```
crates/
  app-core/     # state, input handling, layout, the draw list. No wgpu, no winit.
  app-render/   # wgpu only: pipelines, atlases, buffers; turns a draw list into GPU commands
  app/          # winit event loop, surface, OS integration (clipboard, dialogs); wires the rest together
```

The boundary that matters is the **draw list**: plain data that `app-core` produces (quads, glyph runs, clip rectangles, image references) and `app-render` consumes. Because `app-core` never touches the GPU or the window system, layout, hit-testing and editing logic are tested and benchmarked without a window. Because `app-render` never touches the window system, it renders offscreen in tests. Keep it that way: when `app-core` seems to need a winit or wgpu type, define a plain type in `app-core` and convert in `app`.

## The rules that keep it fast

The details and reasons are in [references/rendering.md](references/rendering.md). In short:

- **Redraw on demand.** `ControlFlow::Wait` and `request_redraw()` when something changed. An idle app uses no CPU or GPU.
- **Create GPU resources once:** shaders, pipelines, layouts, samplers at startup. Pipeline creation mid-frame is a visible hitch.
- **Nothing allocates per frame in steady state.** Buffers persist and grow geometrically, and draw-list `Vec`s are cleared and reused.
- **A handful of draw calls per frame**, not one per widget: instancing, texture atlases, draws sorted by pipeline and bind group.
- **No GPU readback inside a frame**, and no I/O on the event-loop thread. Slow work runs on another thread and returns as a user event.
- **Handle every `CurrentSurfaceTexture` state**, and replace wgpu's panicking uncaptured-error handler.
- **Colors in shaders are linear.** Convert sRGB design colors once when building the draw list.
- **A frame-time budget** (16.6 ms at 60 Hz, 8.3 ms at 120 Hz), with a target of about half, measured on the CPU and GPU separately.

## Workflow

### Starting a new app
1. Check current wgpu and winit versions (above). Copy `references/skeleton/`, rename the crates and the window title.
2. Decide up front, and write down: target platforms, whether screen reader support is needed ([references/ui.md](references/ui.md), Accessibility), which text stack (`fontdue` for simple scripts, `cosmic-text` for any language or rich text), and the frame-time budget.
3. Build features in `app-core` first (state, layout, draw list), with tests, then extend `app-render` only when a new kind of primitive is needed (glyphs, images, rounded rectangles).
4. Keep the skeleton's checks passing, tiered as rust-dev describes: lints, tests and the audit script on every change (the offscreen render test takes about a quarter of a second), `cargo deny check` and the full suite in CI.

### Adding a widget or feature
1. State and behavior go in `app-core`, with unit tests. Input that comes from the OS (keys, IME, clipboard, files) is converted to plain values in `app` and handed to `app-core`.
2. Emit draw-list items. Reuse existing primitives. A new primitive means a new pipeline or a new instance attribute, so batch it with the others.
3. Give the widget a stable id, so hover, focus and (when used) accessibility state survive across frames.
4. Check the frame-time numbers before and after when the change touches rendering or layout.

### Reviewing GUI code
Look for: pipelines or buffers created per frame, allocation in the frame path, one draw call per item, readbacks or file I/O on the event-loop thread, continuous redraw while idle, unhandled surface states, a missing error handler, `char`-based (not grapheme-based) text editing, IME left on outside text fields, and UI logic that depends on winit or wgpu types in `app-core`. Then the general rust-dev review.

## References

- [references/rendering.md](references/rendering.md): frame loop, surface states, GPU resource rules, color, errors and device loss, runtime system libraries, testing (including the offscreen render test and readback alignment), performance budget and profiling.
- [references/ui.md](references/ui.md): building widgets and layout, text rendering with a glyph atlas, text input and IME, the clipboard, file dialogs, accessibility with accesskit (including the hidden-window ordering that avoids a panic).
- `references/skeleton/`: the verified workspace to copy.

Sources: wgpu, winit, arboard, rfd and accesskit documentation and source, the WGSL specification's layout rules, and Unicode's text segmentation standard (UAX #29) for grapheme clusters. All code here was written for this skill and tested against the versions above.
