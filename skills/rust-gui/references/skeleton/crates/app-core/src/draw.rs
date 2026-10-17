//! What the UI asks the renderer to draw each frame.

/// One UI rectangle, in physical pixels. `#[repr(C)]` + `Pod` lets a slice of them go to
/// the GPU as bytes with no copy loop.
#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, bytemuck::Pod, bytemuck::Zeroable)]
pub struct Quad {
    /// x, y, width, height.
    pub rect: [f32; 4],
    /// Linear RGBA (see "Color" in the GUI reference).
    pub color: [f32; 4],
}
