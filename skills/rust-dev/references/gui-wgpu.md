# GUI apps on raw wgpu

Every GUI app, game, editor or visualization renders with **wgpu** directly, on a window and event loop from **winit**, with a UI we build ourselves. No UI frameworks or engines: not egui, iced, Slint, GTK, Tauri, Dioxus, Bevy, imgui, or any of the others in [dependencies.md](dependencies.md).

Why: the things that decide whether a UI feels instant are the frame loop, what gets allocated per frame, how many draw calls and state changes a frame takes, and when the app sleeps. A framework decides all of those for us, in ways tuned for generality. Owning the renderer means every one of them is a decision we make and can measure. wgpu gives one safe API over Vulkan, Metal, DX12 and WebGPU, so owning the renderer doesn't mean writing it four times.

## Contents
- Versions
- Architecture
- Verified skeleton (wgpu 30, winit 0.30)
- The frame loop
- Surface states
- GPU resource rules
- Building the UI
- Text
- Color
- Errors, device loss and system libraries
- Testing
- Performance budget and profiling

## Versions

The skeleton below was compiled against **wgpu 30.0.1** and **winit 0.30.13** (October 2026), passes the full lint set, and was run on a software Vulkan driver, where it rendered as expected. wgpu ships a major version every few months and the API changes each time (recent majors changed how frames are acquired and presented, and what the pipeline descriptors contain). Before writing wgpu code:

```bash
cargo search wgpu --limit 1
cargo search winit --limit 1     # use the latest *stable* winit, not a beta
```

If the current major is newer than 30, read the wgpu changelog entries since v30 and adjust the skeleton. The compiler errors point at what changed.

## Architecture

A GUI app is always a workspace ([workspace.md](workspace.md)):

```
crates/
  app-core/     # state, input handling, layout, and the draw list. No wgpu, no winit.
  app-render/   # wgpu: device, pipelines, atlases, buffers; turns a draw list into GPU commands
  app/          # winit event loop; feeds input to core, hands core's draw list to render
```

The key boundary is the **draw list**: plain data that `core` produces each frame (`Vec<Quad>`, glyph runs, clip rectangles, image references) and `render` consumes. Because `core` never touches the GPU, layout, hit-testing and interaction logic can be unit-tested, property-tested and benchmarked without a window. And `render` can be benchmarked with synthetic draw lists.

## Verified skeleton

One pipeline, instanced quads in pixel coordinates, one draw call for the whole UI, and a redraw only when something changed. `error.rs` follows [errors.md](errors.md).

`main.rs`:

```rust
//! Raw wgpu + winit: one pipeline, instanced quads, redraw only when needed.

mod error;
mod gpu;

use std::process::ExitCode;
use std::sync::Arc;

use winit::application::ApplicationHandler;
use winit::event::WindowEvent;
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop, OwnedDisplayHandle};
use winit::window::{Window, WindowId};

use crate::error::{AppError, Report};
use crate::gpu::{Frame, Gpu, Quad};

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(err) => {
            eprintln!("error: {}", Report(&err));
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<(), AppError> {
    let event_loop = EventLoop::new().map_err(AppError::EventLoop)?;
    // Sleep until an event arrives. Idle UI costs zero CPU and GPU.
    event_loop.set_control_flow(ControlFlow::Wait);
    let mut app = App {
        display: event_loop.owned_display_handle(),
        state: None,
        failure: None,
    };
    event_loop.run_app(&mut app).map_err(AppError::EventLoop)?;
    app.failure.map_or(Ok(()), Err)
}

struct App {
    display: OwnedDisplayHandle,
    state: Option<(Arc<Window>, Gpu)>,
    // winit callbacks can't return errors, so the first one is stored and the loop exits.
    failure: Option<AppError>,
}

impl App {
    fn fail(&mut self, event_loop: &ActiveEventLoop, err: AppError) {
        self.failure.get_or_insert(err);
        event_loop.exit();
    }
}

impl ApplicationHandler for App {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        if self.state.is_some() {
            return;
        }
        let attrs = Window::default_attributes().with_title("gpucheck");
        let window = match event_loop.create_window(attrs) {
            Ok(window) => Arc::new(window),
            Err(err) => return self.fail(event_loop, AppError::Window(err)),
        };
        match pollster::block_on(Gpu::new(self.display.clone(), Arc::clone(&window))) {
            Ok(mut gpu) => {
                gpu.set_quads(&[Quad {
                    rect: [40.0, 40.0, 200.0, 120.0],
                    color: [0.2, 0.5, 0.9, 1.0],
                }]);
                window.request_redraw();
                self.state = Some((window, gpu));
            }
            Err(err) => self.fail(event_loop, err),
        }
    }

    fn window_event(&mut self, event_loop: &ActiveEventLoop, _id: WindowId, event: WindowEvent) {
        let Some((window, gpu)) = self.state.as_mut() else {
            return;
        };
        let result = match event {
            WindowEvent::CloseRequested => {
                event_loop.exit();
                Ok(())
            }
            WindowEvent::Resized(size) => {
                gpu.resize(size.width, size.height);
                window.request_redraw();
                Ok(())
            }
            WindowEvent::RedrawRequested => {
                window.pre_present_notify();
                gpu.render().map(|frame| {
                    if frame == Frame::Retry {
                        window.request_redraw();
                    }
                })
            }
            _ => Ok(()),
        };
        if let Err(err) = result {
            self.fail(event_loop, err);
        }
    }
}
```

`gpu.rs`:

```rust
use std::sync::{Arc, Mutex, PoisonError};

use wgpu::CurrentSurfaceTexture;
use winit::event_loop::OwnedDisplayHandle;
use winit::window::Window;

use crate::error::AppError;

/// One UI rectangle. `#[repr(C)]` + `Pod` lets the slice go to the GPU as bytes with no copy loop.
#[repr(C)]
#[derive(Clone, Copy, Debug, bytemuck::Pod, bytemuck::Zeroable)]
pub(crate) struct Quad {
    pub(crate) rect: [f32; 4],
    pub(crate) color: [f32; 4],
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Frame {
    Presented,
    Skipped,
    Retry,
}

pub(crate) struct Gpu {
    surface: wgpu::Surface<'static>,
    device: wgpu::Device,
    queue: wgpu::Queue,
    config: wgpu::SurfaceConfiguration,
    pipeline: wgpu::RenderPipeline,
    screen: wgpu::Buffer,
    screen_bind: wgpu::BindGroup,
    quads: wgpu::Buffer,
    quad_capacity: u64,
    quad_count: u32,
    device_error: Arc<Mutex<Option<String>>>,
}

const QUAD_SIZE: u64 = size_of::<Quad>() as u64;

impl Gpu {
    pub(crate) async fn new(
        display: OwnedDisplayHandle,
        window: Arc<Window>,
    ) -> Result<Self, AppError> {
        let size = window.inner_size();
        let instance = wgpu::Instance::new(wgpu::InstanceDescriptor::new_with_display_handle(
            Box::new(display),
        ));
        let surface = instance.create_surface(window).map_err(AppError::Surface)?;
        let adapter = instance
            .request_adapter(&wgpu::RequestAdapterOptions {
                power_preference: wgpu::PowerPreference::HighPerformance,
                force_fallback_adapter: false,
                compatible_surface: Some(&surface),
                ..Default::default()
            })
            .await
            .map_err(AppError::Adapter)?;
        let (device, queue) = adapter
            .request_device(&wgpu::DeviceDescriptor {
                label: Some("main"),
                ..Default::default()
            })
            .await
            .map_err(AppError::Device)?;
        let device_error = watch_errors(&device);
        let config = surface
            .get_default_config(&adapter, size.width.max(1), size.height.max(1))
            .ok_or(AppError::SurfaceUnsupported)?;
        surface.configure(&device, &config);

        // Everything below is created once. Pipelines and layouts are expensive to build;
        // creating them inside the frame loop causes hitches.
        let screen = device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("screen"),
            size: 16,
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });
        let (pipeline, bind_layout) = Self::quad_pipeline(&device, config.format);
        let screen_bind = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("screen"),
            layout: &bind_layout,
            entries: &[wgpu::BindGroupEntry {
                binding: 0,
                resource: screen.as_entire_binding(),
            }],
        });
        let quad_capacity = 256;
        let quads = Self::quad_buffer(&device, quad_capacity);

        let gpu = Self {
            surface,
            device,
            queue,
            config,
            pipeline,
            screen,
            screen_bind,
            quads,
            quad_capacity,
            quad_count: 0,
            device_error,
        };
        gpu.write_screen_size();
        Ok(gpu)
    }

    fn quad_pipeline(
        device: &wgpu::Device,
        format: wgpu::TextureFormat,
    ) -> (wgpu::RenderPipeline, wgpu::BindGroupLayout) {
        let bind_layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("screen"),
            entries: &[wgpu::BindGroupLayoutEntry {
                binding: 0,
                visibility: wgpu::ShaderStages::VERTEX,
                ty: wgpu::BindingType::Buffer {
                    ty: wgpu::BufferBindingType::Uniform,
                    has_dynamic_offset: false,
                    min_binding_size: None,
                },
                count: None,
            }],
        });
        let shader = device.create_shader_module(wgpu::include_wgsl!("quad.wgsl"));
        let layout = device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor {
            label: Some("quad"),
            bind_group_layouts: &[Some(&bind_layout)],
            immediate_size: 0,
        });
        let pipeline = device.create_render_pipeline(&wgpu::RenderPipelineDescriptor {
            label: Some("quad"),
            layout: Some(&layout),
            vertex: wgpu::VertexState {
                module: &shader,
                entry_point: Some("vs_main"),
                compilation_options: wgpu::PipelineCompilationOptions::default(),
                buffers: &[Some(wgpu::VertexBufferLayout {
                    array_stride: QUAD_SIZE,
                    step_mode: wgpu::VertexStepMode::Instance,
                    attributes: &wgpu::vertex_attr_array![0 => Float32x4, 1 => Float32x4],
                })],
            },
            primitive: wgpu::PrimitiveState {
                topology: wgpu::PrimitiveTopology::TriangleStrip,
                ..Default::default()
            },
            depth_stencil: None,
            multisample: wgpu::MultisampleState::default(),
            fragment: Some(wgpu::FragmentState {
                module: &shader,
                entry_point: Some("fs_main"),
                compilation_options: wgpu::PipelineCompilationOptions::default(),
                targets: &[Some(wgpu::ColorTargetState {
                    format,
                    blend: Some(wgpu::BlendState::ALPHA_BLENDING),
                    write_mask: wgpu::ColorWrites::ALL,
                })],
            }),
            multiview_mask: None,
            cache: None,
        });
        (pipeline, bind_layout)
    }

    fn quad_buffer(device: &wgpu::Device, capacity: u64) -> wgpu::Buffer {
        device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("quads"),
            size: capacity * QUAD_SIZE,
            usage: wgpu::BufferUsages::VERTEX | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        })
    }

    fn write_screen_size(&self) {
        #[expect(
            clippy::cast_precision_loss,
            reason = "window sizes are far below 2^24"
        )]
        let size = [
            self.config.width as f32,
            self.config.height as f32,
            0.0,
            0.0,
        ];
        self.queue
            .write_buffer(&self.screen, 0, bytemuck::cast_slice(&size));
    }

    /// Uploads this frame's quads. The buffer is reused across frames and only reallocated,
    /// to the next power of two, when it is too small. Steady state allocates nothing.
    pub(crate) fn set_quads(&mut self, quads: &[Quad]) {
        let needed = quads.len() as u64;
        if needed > self.quad_capacity {
            self.quad_capacity = needed.next_power_of_two();
            self.quads = Self::quad_buffer(&self.device, self.quad_capacity);
        }
        self.queue
            .write_buffer(&self.quads, 0, bytemuck::cast_slice(quads));
        self.quad_count = u32::try_from(quads.len()).unwrap_or(u32::MAX);
    }

    pub(crate) fn resize(&mut self, width: u32, height: u32) {
        // A minimized window reports 0x0, which is not a valid surface size.
        if width == 0 || height == 0 {
            return;
        }
        self.config.width = width;
        self.config.height = height;
        self.surface.configure(&self.device, &self.config);
        self.write_screen_size();
    }

    pub(crate) fn render(&mut self) -> Result<Frame, AppError> {
        let recorded = self
            .device_error
            .lock()
            .unwrap_or_else(PoisonError::into_inner)
            .take();
        if let Some(message) = recorded {
            return Err(AppError::Gpu(message));
        }
        let (frame, suboptimal) = match self.surface.get_current_texture() {
            CurrentSurfaceTexture::Success(frame) => (frame, false),
            CurrentSurfaceTexture::Suboptimal(frame) => (frame, true),
            CurrentSurfaceTexture::Timeout | CurrentSurfaceTexture::Occluded => {
                return Ok(Frame::Skipped);
            }
            CurrentSurfaceTexture::Outdated => {
                self.surface.configure(&self.device, &self.config);
                return Ok(Frame::Retry);
            }
            CurrentSurfaceTexture::Lost => return Err(AppError::SurfaceLost),
            CurrentSurfaceTexture::Validation => return Err(AppError::SurfaceValidation),
        };
        let view = frame
            .texture
            .create_view(&wgpu::TextureViewDescriptor::default());
        let mut encoder = self
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                label: Some("frame"),
            });
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("ui"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &view,
                    depth_slice: None,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(wgpu::Color::BLACK),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: None,
                timestamp_writes: None,
                occlusion_query_set: None,
                multiview_mask: None,
            });
            // One pipeline, one bind group, one draw call for every quad on screen.
            pass.set_pipeline(&self.pipeline);
            pass.set_bind_group(0, &self.screen_bind, &[]);
            pass.set_vertex_buffer(0, self.quads.slice(..));
            pass.draw(0..4, 0..self.quad_count);
        }
        self.queue.submit([encoder.finish()]);
        self.queue.present(frame);
        if suboptimal {
            self.surface.configure(&self.device, &self.config);
        }
        Ok(Frame::Presented)
    }
}

/// wgpu's default handler for uncaptured errors panics. This one records the first
/// validation error or device loss instead, and `render` returns it as an `AppError`.
fn watch_errors(device: &wgpu::Device) -> Arc<Mutex<Option<String>>> {
    let slot: Arc<Mutex<Option<String>>> = Arc::default();
    let on_error = Arc::clone(&slot);
    device.on_uncaptured_error(Arc::new(move |err: wgpu::Error| {
        let mut first = on_error.lock().unwrap_or_else(PoisonError::into_inner);
        first.get_or_insert_with(|| err.to_string());
    }));
    let on_lost = Arc::clone(&slot);
    device.set_device_lost_callback(move |reason, message| {
        let mut first = on_lost.lock().unwrap_or_else(PoisonError::into_inner);
        first.get_or_insert_with(|| format!("device lost ({reason:?}): {message}"));
    });
    slot
}
```

`quad.wgsl`:

```wgsl
struct Screen {
    size: vec2<f32>,
    _pad: vec2<f32>,
}

@group(0) @binding(0) var<uniform> screen: Screen;

struct Instance {
    @location(0) rect: vec4<f32>,  // x, y, width, height in physical pixels
    @location(1) color: vec4<f32>,
}

struct VsOut {
    @builtin(position) pos: vec4<f32>,
    @location(0) color: vec4<f32>,
}

@vertex
fn vs_main(@builtin(vertex_index) vi: u32, inst: Instance) -> VsOut {
    // Four strip vertices from the index alone: no vertex buffer for the corners.
    let corner = vec2<f32>(f32(vi & 1u), f32(vi >> 1u));
    let px = inst.rect.xy + corner * inst.rect.zw;
    let ndc = vec2<f32>(px.x / screen.size.x * 2.0 - 1.0, 1.0 - px.y / screen.size.y * 2.0);
    var out: VsOut;
    out.pos = vec4<f32>(ndc, 0.0, 1.0);
    out.color = inst.color;
    return out;
}

@fragment
fn fs_main(in: VsOut) -> @location(0) vec4<f32> {
    return in.color;
}
```

`error.rs`:

```rust
use std::error::Error;
use std::fmt;

#[derive(Debug)]
pub(crate) enum AppError {
    EventLoop(winit::error::EventLoopError),
    Window(winit::error::OsError),
    Surface(wgpu::CreateSurfaceError),
    Adapter(wgpu::RequestAdapterError),
    Device(wgpu::RequestDeviceError),
    SurfaceUnsupported,
    SurfaceLost,
    SurfaceValidation,
    Gpu(String),
}

impl fmt::Display for AppError {
    // The message names this layer's failure only. The cause is reachable through
    // `source()`, so repeating it here would print it twice in a report.
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let message = match self {
            Self::EventLoop(_) => "event loop failed",
            Self::Window(_) => "could not create the window",
            Self::Surface(_) => "could not create a surface for the window",
            Self::Adapter(_) => "no suitable GPU adapter",
            Self::Device(_) => "could not open the GPU device",
            Self::SurfaceUnsupported => "the adapter cannot present to this window",
            Self::SurfaceLost => "the window surface was lost",
            Self::SurfaceValidation => "surface validation error",
            Self::Gpu(detail) => return write!(f, "GPU error: {detail}"),
        };
        f.write_str(message)
    }
}

impl Error for AppError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::EventLoop(e) => Some(e),
            Self::Window(e) => Some(e),
            Self::Surface(e) => Some(e),
            Self::Adapter(e) => Some(e),
            Self::Device(e) => Some(e),
            Self::SurfaceUnsupported
            | Self::SurfaceLost
            | Self::SurfaceValidation
            | Self::Gpu(_) => None,
        }
    }
}

/// Formats an error and its whole `source()` chain on one line: `a: b: c`.
pub(crate) struct Report<'a>(pub(crate) &'a dyn Error);

impl fmt::Display for Report<'_> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.0)?;
        let mut cause = self.0.source();
        while let Some(err) = cause {
            write!(f, ": {err}")?;
            cause = err.source();
        }
        Ok(())
    }
}
```

## The frame loop

- **Redraw on demand.** `ControlFlow::Wait` and `window.request_redraw()` when input arrives, state changes or an animation is running. An idle UI uses no CPU or GPU, which matters for laptops and for every other app on the machine.
- **Animations** call `request_redraw()` at the end of each frame while they're running, and stop when they finish.
- **Games and simulations** run the simulation on a fixed timestep (accumulate real elapsed time, step the simulation in fixed increments, render with interpolation between the last two states). Simulation results then don't depend on frame rate, and the render loop can run at the display's rate.
- **Present mode:** `Fifo` (vsync) is the default: supported everywhere, no tearing, no wasted frames. Use `Mailbox` when the surface supports it and input latency matters more than power. `AutoNoVsync` only for benchmarking. Pick from `surface.get_capabilities(&adapter).present_modes`, never assume.
- **Frame latency:** `desired_maximum_frame_latency` of 2 is the default. Set it to 1 for lower input latency in apps that render fast, at some cost in throughput.
- **Heavy work goes off the event-loop thread** (file loading, decoding, search, layout of huge documents) and comes back through a channel with `EventLoopProxy::send_event` to wake the loop. A frame never waits on I/O.
- **HiDPI:** winit reports physical pixels in `Resized` and a `scale_factor`. Lay out in logical units and multiply by the scale factor when building the draw list, so everything is crisp at any scale.

## Surface states

`Surface::get_current_texture` returns a `CurrentSurfaceTexture`, and every variant gets handled. The skeleton shows all of them:

| Variant | Meaning | Action |
|---|---|---|
| `Success(frame)` | Normal | Render and present |
| `Suboptimal(frame)` | Usable, but the surface changed | Render and present this frame, then reconfigure |
| `Timeout`, `Occluded` | No frame available now, or the window is hidden | Skip this frame. Don't spin: an occluded window waits for the next event |
| `Outdated` | Configuration no longer matches (resize, monitor change) | Reconfigure, request another redraw |
| `Lost` | The surface itself is gone | Recreate the surface from the instance and window (or the device too, if the device was lost) |
| `Validation` | A validation error was raised | Report it; it's a bug in our code |

A window minimized to 0×0 can't be configured. `resize` ignores zero sizes.

## GPU resource rules

These are what keep frame time flat:

- **Create once, at startup:** shader modules, pipelines, bind group layouts, pipeline layouts, samplers. Pipeline creation compiles shaders and takes milliseconds. Doing it during a frame shows up as a hitch. With many pipelines, use a `PipelineCache` (where the backend supports it) and create them on a loading screen or a background thread.
- **Persistent buffers that grow geometrically.** Vertex, instance and uniform buffers live across frames. When a frame needs more space, reallocate to the next power of two, as `set_quads` does. In steady state, nothing is allocated.
- **Uploads through `queue.write_buffer`** for per-frame data. For many or large uploads per frame, use `wgpu::util::StagingBelt` so staging memory is reused.
- **Never read back from the GPU inside a frame.** `map_async` round trips stall the pipeline. Read back asynchronously, a frame or more later.
- **Few draw calls, few state changes.** Instancing for repeated shapes, one instance buffer for all quads, texture atlases so many images share one bind group, and draws sorted by pipeline and then by bind group. A UI should be a handful of draw calls per frame, not one per widget.
- **One uniform buffer with dynamic offsets** instead of one buffer and bind group per object, when per-object uniforms are needed.
- **Minimal render passes.** Each pass has a cost, especially on tile-based mobile and Apple GPUs. Use `LoadOp::Clear` rather than drawing a full-screen clear quad, and `StoreOp::Discard` on attachments not needed after the pass (depth buffers, usually).
- **`#[repr(C)]` + `bytemuck::Pod`** for every struct sent to the GPU, so uploads are a byte cast with no copying loop and no unsafe. Match WGSL's alignment rules: `vec3<f32>` is 16-byte aligned in uniforms, so pad or use `vec4`.
- **Labels on every resource.** They show up in validation errors and GPU debuggers, and cost nothing in release.
- **Validate shaders in tests.** `naga` (wgpu's shader compiler, as a dev-dependency with the `wgsl-in` feature) can parse and validate WGSL in a unit test, so a shader typo fails `cargo test` instead of crashing at startup.

## Building the UI

There's no framework, so the UI is ours, built in `app-core`. The structure that works:

1. **State** is plain Rust data owned by the app: the document, the selection, which panel is open.
2. **Each frame** (that needs one), a build pass walks the state and produces widgets with layout constraints. Keep it simple: rows, columns, fixed and flexible sizes, padding, alignment. That covers most UIs without a general constraint solver.
3. **Layout** resolves sizes and positions into rectangles, top-down, in logical units. Cache layout of subtrees whose input didn't change when profiling shows layout as a cost.
4. **Hit-testing** uses the same rectangles: the topmost rectangle under the pointer that accepts input gets the event. Keep a per-frame list of interactive rectangles with stable ids so hover, press and focus states persist across frames.
5. **The draw list** is emitted in paint order: background quads, borders, images, glyphs, overlays. The renderer batches consecutive items of the same kind into one draw.
6. **Rounded corners, borders and shadows** come from signed distance functions in the fragment shader (per-instance corner radius, border width, blur), which gives anti-aliased edges with no MSAA and no extra geometry.
7. **Clipping** (scroll areas) uses scissor rectangles per batch, or a clip rectangle per instance tested in the shader when scissor changes would break batches.
8. **Accessibility:** a hand-built UI has no accessibility tree by default. If the app needs screen reader support, plan for `accesskit` (with a `# why:`) from the start, fed from the same widget tree. Retrofitting it later is painful.

## Text

Text is the hardest part of a hand-built UI. Use a crate for shaping and rasterizing, and own the atlas and rendering:

- `fontdue` rasterizes glyphs and does simple layout. Enough for UIs in Latin, Cyrillic and Greek scripts with no ligatures or complex shaping.
- `cosmic-text` shapes (ligatures, Arabic, Indic, CJK fallback), handles bidirectional text and line breaking, and rasterizes through swash. Use it when the app shows user-provided text in any language, or rich text.

Either way: rasterize glyphs on demand into a GPU **glyph atlas** texture (a single-channel `R8Unorm` for coverage), cache by (font, glyph id, size, subpixel offset), and draw each glyph as an instanced quad sampling the atlas: the same pipeline shape as the skeleton, plus texture coordinates. Upload only newly rasterized glyphs each frame. Evict with a least-recently-used policy when the atlas fills, or grow it.

## Color

When the surface format is sRGB (most are, and `get_default_config` picks one), the GPU converts the shader's output from linear to sRGB on write. So **colors in the shader are linear**: the skeleton's `[0.2, 0.5, 0.9]` shows on screen as a lighter blue. Design colors are almost always given in sRGB (hex codes), so convert them to linear once when building the draw list, not per pixel. Blending in linear space is what makes anti-aliased edges and transparency look right.

## Errors, device loss and system libraries

- wgpu's default handler for uncaptured errors **panics**. Always install one with `device.on_uncaptured_error` (the skeleton's `watch_errors`) that records the error and lets the app report it and shut down cleanly.
- `set_device_lost_callback` reports a lost device (driver crash or update, GPU reset, eGPU unplugged). A robust app recreates the device and every GPU resource from its own state, which is easiest when resources are created in one place (the `Gpu` struct) from data the app keeps.
- **Dependencies can still panic** on things outside our control. winit, for example, panics at startup on Linux X11 when `libxkbcommon-x11` isn't installed. Document the runtime system libraries in the README (Linux: a Vulkan driver or OpenGL/EGL, `libxkbcommon`, `libxkbcommon-x11` for X11, `libwayland-client` for Wayland), and check them in the installer or package dependencies.

## Testing

- **Core logic** (layout, hit-testing, state transitions, draw-list generation) is tested in `app-core` with ordinary unit and property tests. Most UI bugs live here.
- **Shaders** are validated with `naga` in unit tests (verified with naga 30):

```rust
#[cfg(test)]
mod tests {
    #[test]
    fn quad_shader_is_valid() {
        let module = naga::front::wgsl::parse_str(include_str!("quad.wgsl"))
            .unwrap_or_else(|e| panic!("{}", e.emit_to_string(include_str!("quad.wgsl"))));
        naga::valid::Validator::new(
            naga::valid::ValidationFlags::all(),
            naga::valid::Capabilities::empty(),
        )
        .validate(&module)
        .unwrap();
    }
}
```

- **Rendering** is tested headlessly: create an adapter with `force_fallback_adapter: true` (a software rasterizer such as llvmpipe or WARP, which CI machines can install), render to a texture instead of a surface, copy it back, and compare against a stored reference image with a small tolerance. Keep these few and focused (one per pipeline), since they're slow.
- **Frame-time benchmarks** run the build-layout-draw-list path with criterion on a representative screen, and the GPU side with timestamp queries in a dedicated benchmark mode.

## Performance budget and profiling

- Set the budget per frame: 16.6 ms at 60 Hz, 8.3 ms at 120 Hz, and target well under it (half) so hitches have headroom. Measure CPU frame time (input to submit) and GPU frame time (timestamp queries) separately.
- No allocation per frame in steady state: the draw list `Vec`s are cleared and reused, never recreated.
- Count draw calls and pipeline/bind group switches per frame in debug builds and display them in a debug overlay. A rising number is the earliest sign of a batching regression.
- Profile with RenderDoc (frame captures), the platform GPU tools (Xcode's Metal debugger, PIX, Radeon GPU Profiler, Nsight), and `samply` or `perf` for the CPU side.
