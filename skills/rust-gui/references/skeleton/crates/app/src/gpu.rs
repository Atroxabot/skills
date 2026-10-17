use std::sync::{Arc, Mutex, PoisonError};

use wgpu::CurrentSurfaceTexture;
use winit::event_loop::OwnedDisplayHandle;
use winit::window::Window;

use app_core::draw::Quad;
use app_render::Renderer;

use crate::error::AppError;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum Frame {
    Presented,
    Skipped,
    Retry,
}

/// The window's GPU state: device, surface and the renderer that draws into it.
pub(crate) struct Gpu {
    surface: wgpu::Surface<'static>,
    device: wgpu::Device,
    queue: wgpu::Queue,
    config: wgpu::SurfaceConfiguration,
    renderer: Renderer,
    device_error: Arc<Mutex<Option<String>>>,
}

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
        let renderer = Renderer::new(&device, config.format);
        renderer.resize(&queue, config.width, config.height);
        Ok(Self {
            surface,
            device,
            queue,
            config,
            renderer,
            device_error,
        })
    }

    pub(crate) fn set_quads(&mut self, quads: &[Quad]) {
        self.renderer.set_quads(&self.device, &self.queue, quads);
    }

    pub(crate) fn resize(&mut self, width: u32, height: u32) {
        // A minimized window reports 0x0, which is not a valid surface size.
        if width == 0 || height == 0 {
            return;
        }
        self.config.width = width;
        self.config.height = height;
        self.surface.configure(&self.device, &self.config);
        self.renderer.resize(&self.queue, width, height);
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
        self.renderer.encode(&mut encoder, &view);
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
