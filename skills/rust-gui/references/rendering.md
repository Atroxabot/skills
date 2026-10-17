# Rendering, frame loop and testing

How the skeleton's renderer and frame loop work, the rules that keep frame time flat, and how GUI code is tested and profiled. File paths refer to the skeleton in `skeleton/`.

## Contents
- The frame loop
- Surface states
- GPU resource rules
- Color
- Errors, device loss and system libraries
- Testing
- Performance budget and profiling

## The frame loop

- **Redraw on demand.** `ControlFlow::Wait` and `window.request_redraw()` when input arrives, state changes or an animation is running. An idle UI uses no CPU or GPU, which matters for laptops and for every other app on the machine.
- **Animations** call `request_redraw()` at the end of each frame while they're running, and stop when they finish.
- **Games and simulations** run the simulation on a fixed timestep (accumulate real elapsed time, step the simulation in fixed increments, render with interpolation between the last two states). Simulation results then don't depend on frame rate, and the render loop can run at the display's rate.
- **Present mode:** `Fifo` (vsync) is the default: supported everywhere, no tearing, no wasted frames. Use `Mailbox` when the surface supports it and input latency matters more than power. `AutoNoVsync` only for benchmarking. Pick from `surface.get_capabilities(&adapter).present_modes`, never assume.
- **Frame latency:** `desired_maximum_frame_latency` of 2 is the default. Set it to 1 for lower input latency in apps that render fast, at some cost in throughput.
- **Heavy work goes off the event-loop thread** (file loading, decoding, search, layout of huge documents, dialogs) and comes back as a user event through an `EventLoopProxy`, as the skeleton's file dialog does. A frame never waits on I/O.
- **HiDPI:** winit reports physical pixels in `Resized` and a `scale_factor`. Lay out in logical units and multiply by the scale factor when building the draw list, so everything is crisp at any scale.

## Surface states

`Surface::get_current_texture` returns a `CurrentSurfaceTexture`, and every variant gets handled. the skeleton's `crates/app/src/gpu.rs` shows all of them:

| Variant | Meaning | Action |
|---|---|---|
| `Success(frame)` | Normal | Render and present (`queue.present(frame)`) |
| `Suboptimal(frame)` | Usable, but the surface changed | Render and present this frame, then reconfigure |
| `Timeout`, `Occluded` | No frame available now, or the window is hidden | Skip this frame. Don't spin: an occluded window waits for the next event |
| `Outdated` | Configuration no longer matches (resize, monitor change) | Reconfigure, request another redraw |
| `Lost` | The surface itself is gone | Recreate the surface from the instance and window (or the device too, if the device was lost) |
| `Validation` | A validation error was raised | Report it; it's a bug in our code |

A window minimized to 0×0 can't be configured. `resize` ignores zero sizes.

## GPU resource rules

These are what keep frame time flat:

- **Create once, at startup:** shader modules, pipelines, bind group layouts, pipeline layouts, samplers. Pipeline creation compiles shaders and takes milliseconds. Doing it during a frame shows up as a hitch. With many pipelines, use a `PipelineCache` (where the backend supports it) and create them on a loading screen or a background thread.
- **Persistent buffers that grow geometrically.** Vertex, instance and uniform buffers live across frames. When a frame needs more space, reallocate to the next power of two, as `Renderer::set_quads` does. In steady state, nothing is allocated.
- **Uploads through `queue.write_buffer`** for per-frame data. For many or large uploads per frame, use `wgpu::util::StagingBelt` so staging memory is reused.
- **Never read back from the GPU inside a frame.** `map_async` round trips stall the pipeline. Read back asynchronously, a frame or more later. (The offscreen test reads back synchronously, which is fine in a test.)
- **Few draw calls, few state changes.** Instancing for repeated shapes, one instance buffer for all quads, texture atlases so many images share one bind group, and draws sorted by pipeline and then by bind group. A UI should be a handful of draw calls per frame, not one per widget.
- **One uniform buffer with dynamic offsets** instead of one buffer and bind group per object, when per-object uniforms are needed.
- **Minimal render passes.** Each pass has a cost, especially on tile-based mobile and Apple GPUs. Use `LoadOp::Clear` rather than drawing a full-screen clear quad, and `StoreOp::Discard` on attachments not needed after the pass (depth buffers, usually).
- **`#[repr(C)]` + `bytemuck::Pod`** for every struct sent to the GPU, so uploads are a byte cast with no copying loop and no unsafe. Match WGSL's alignment rules: `vec3<f32>` is 16-byte aligned in uniforms, so pad or use `vec4`.
- **Labels on every resource.** They show up in validation errors and GPU debuggers, and cost nothing in release.

## Color

When the surface format is sRGB (most are, and `get_default_config` picks one), the GPU converts the shader's output from linear to sRGB on write. So **colors in the shader are linear**: the skeleton's `[0.2, 0.5, 0.9]` shows on screen as a lighter blue. Design colors are almost always given in sRGB (hex codes), so convert them to linear once when building the draw list, not per pixel. Blending in linear space is what makes anti-aliased edges and transparency look right.

## Errors, device loss and system libraries

- wgpu's default handler for uncaptured errors **panics**. Always install one with `device.on_uncaptured_error` (the skeleton's `watch_errors`) that records the error and lets the app report it and shut down cleanly.
- `set_device_lost_callback` reports a lost device (driver crash or update, GPU reset, eGPU unplugged). A robust app recreates the device and every GPU resource from its own state. That's easier because `Renderer` is created in one place from data the app keeps.
- **Dependencies can still panic** on things outside our control. winit, for example, panics at startup on Linux X11 when `libxkbcommon-x11` isn't installed. Document the runtime system libraries in the README (Linux: a Vulkan driver or OpenGL/EGL, `libxkbcommon`, `libxkbcommon-x11` for X11, `libwayland-client` for Wayland, a desktop portal backend or `zenity` for dialogs), and list them in the package dependencies.

## Testing

- **Core logic** (layout, hit-testing, text editing, draw-list generation) is tested in `app-core` with ordinary unit and property tests. Most UI bugs live here, and these tests run in milliseconds.
- **Shaders** are validated with `naga` in a unit test (`quad_shader_is_valid` in `app-render`), so a shader typo fails `cargo test` instead of crashing at startup.
- **Rendering** is tested offscreen (`draws_quad_offscreen` in `app-render`): render into a texture, copy it to a buffer, map it, and check pixels. It uses whatever adapter exists: the developer's GPU locally, and on a headless Linux CI runner Mesa's software rasterizer (`mesa-vulkan-drivers`; Windows has WARP built in). Solid axis-aligned quads have no anti-aliasing, so exact pixel values are the same on every adapter. For anti-aliased content (text, rounded corners), compare against a stored reference image with a small per-channel tolerance instead. Keep render tests few and focused, one per pipeline or visual feature. The skeleton's takes about a quarter of a second on the software rasterizer.
- **Rows must be aligned for readback:** `bytes_per_row` has to be a multiple of `wgpu::COPY_BYTES_PER_ROW_ALIGNMENT` (256). The test uses a 64-pixel-wide texture (64 × 4 bytes = 256) to avoid padding. For other widths, pad each row and skip the padding when reading.
- **Frame-time benchmarks** run the build-layout-draw-list path with criterion on a representative screen, and the GPU side with timestamp queries in a dedicated benchmark mode.

## Performance budget and profiling

- Set the budget per frame: 16.6 ms at 60 Hz, 8.3 ms at 120 Hz, and target well under it (half) so hitches have headroom. Measure CPU frame time (input to submit) and GPU frame time (timestamp queries) separately.
- No allocation per frame in steady state: the draw list `Vec`s are cleared and reused, never recreated.
- Count draw calls and pipeline/bind group switches per frame in debug builds and display them in a debug overlay. A rising number is the earliest sign of a batching regression.
- Profile with RenderDoc (frame captures), the platform GPU tools (Xcode's Metal debugger, PIX, Radeon GPU Profiler, Nsight), and `samply` or `perf` for the CPU side.
