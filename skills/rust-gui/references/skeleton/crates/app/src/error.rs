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
    Dialog(std::io::Error),
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
            Self::Dialog(_) => "could not start the file dialog",
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
            Self::Dialog(e) => Some(e),
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
