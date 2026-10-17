//! Draws the UI's draw list with wgpu. No windowing types: it renders into any texture
//! view, so tests render offscreen and read the pixels back.

use app_core::draw::Quad;

const QUAD_SIZE: u64 = size_of::<Quad>() as u64;

/// Draws the UI into any texture view. It owns no surface, so the same code renders to
/// the window and, in tests, to an offscreen texture that can be read back.
#[derive(Debug)]
pub struct Renderer {
    pipeline: wgpu::RenderPipeline,
    screen: wgpu::Buffer,
    screen_bind: wgpu::BindGroup,
    quads: wgpu::Buffer,
    quad_capacity: u64,
    quad_count: u32,
}

impl Renderer {
    /// Creates everything once. Pipelines and layouts are expensive to build;
    /// creating them inside the frame loop causes hitches.
    #[must_use]
    pub fn new(device: &wgpu::Device, format: wgpu::TextureFormat) -> Self {
        let screen = device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("screen"),
            size: 16,
            usage: wgpu::BufferUsages::UNIFORM | wgpu::BufferUsages::COPY_DST,
            mapped_at_creation: false,
        });
        let (pipeline, bind_layout) = Self::quad_pipeline(device, format);
        let screen_bind = device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: Some("screen"),
            layout: &bind_layout,
            entries: &[wgpu::BindGroupEntry {
                binding: 0,
                resource: screen.as_entire_binding(),
            }],
        });
        let quad_capacity = 256;
        Self {
            pipeline,
            screen,
            screen_bind,
            quads: Self::quad_buffer(device, quad_capacity),
            quad_capacity,
            quad_count: 0,
        }
    }

    pub fn resize(&self, queue: &wgpu::Queue, width: u32, height: u32) {
        #[expect(
            clippy::cast_precision_loss,
            reason = "window sizes are far below 2^24"
        )]
        let size = [width as f32, height as f32, 0.0, 0.0];
        queue.write_buffer(&self.screen, 0, bytemuck::cast_slice(&size));
    }

    /// Uploads this frame's quads. The buffer is reused across frames and only reallocated,
    /// to the next power of two, when it is too small. Steady state allocates nothing.
    pub fn set_quads(&mut self, device: &wgpu::Device, queue: &wgpu::Queue, quads: &[Quad]) {
        let needed = quads.len() as u64;
        if needed > self.quad_capacity {
            self.quad_capacity = needed.next_power_of_two();
            self.quads = Self::quad_buffer(device, self.quad_capacity);
        }
        queue.write_buffer(&self.quads, 0, bytemuck::cast_slice(quads));
        self.quad_count = u32::try_from(quads.len()).unwrap_or(u32::MAX);
    }

    /// Records the UI pass into `encoder`, drawing onto `target`.
    pub fn encode(&self, encoder: &mut wgpu::CommandEncoder, target: &wgpu::TextureView) {
        let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
            label: Some("ui"),
            color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                view: target,
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
}

#[cfg(test)]
mod tests {
    use super::*;

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

    /// Any adapter works: the developer's GPU locally, a software rasterizer in CI
    /// (Mesa's lavapipe on Linux; Windows ships WARP). Solid, axis-aligned quads have no
    /// anti-aliasing, so exact pixel values are the same on every adapter.
    async fn headless_device() -> (wgpu::Device, wgpu::Queue) {
        let instance = wgpu::Instance::new(wgpu::InstanceDescriptor::new_without_display_handle());
        let adapter = instance
            .request_adapter(&wgpu::RequestAdapterOptions::default())
            .await
            .expect("no GPU adapter; on a headless Linux CI runner install mesa-vulkan-drivers");
        adapter
            .request_device(&wgpu::DeviceDescriptor::default())
            .await
            .unwrap()
    }

    /// Copies an RGBA8 texture back to the CPU. `width * 4` must be a multiple of
    /// `wgpu::COPY_BYTES_PER_ROW_ALIGNMENT` (256); pad rows otherwise.
    fn read_pixels(device: &wgpu::Device, queue: &wgpu::Queue, texture: &wgpu::Texture) -> Vec<u8> {
        let size = texture.size();
        let readback = device.create_buffer(&wgpu::BufferDescriptor {
            label: Some("readback"),
            size: u64::from(size.width * size.height * 4),
            usage: wgpu::BufferUsages::COPY_DST | wgpu::BufferUsages::MAP_READ,
            mapped_at_creation: false,
        });
        let mut encoder = device.create_command_encoder(&wgpu::CommandEncoderDescriptor::default());
        encoder.copy_texture_to_buffer(
            texture.as_image_copy(),
            wgpu::TexelCopyBufferInfo {
                buffer: &readback,
                layout: wgpu::TexelCopyBufferLayout {
                    offset: 0,
                    bytes_per_row: Some(size.width * 4),
                    rows_per_image: None,
                },
            },
            size,
        );
        queue.submit([encoder.finish()]);
        readback.map_async(wgpu::MapMode::Read, .., |result| result.unwrap());
        device.poll(wgpu::PollType::wait_indefinitely()).unwrap();
        readback.get_mapped_range(..).unwrap().to_vec()
    }

    #[test]
    fn draws_quad_offscreen() {
        const SIZE: u32 = 64; // 64 px * 4 bytes = 256 bytes per row, already aligned
        let (device, queue) = pollster::block_on(headless_device());
        let format = wgpu::TextureFormat::Rgba8UnormSrgb;
        let target = device.create_texture(&wgpu::TextureDescriptor {
            label: Some("target"),
            size: wgpu::Extent3d {
                width: SIZE,
                height: SIZE,
                depth_or_array_layers: 1,
            },
            mip_level_count: 1,
            sample_count: 1,
            dimension: wgpu::TextureDimension::D2,
            format,
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT | wgpu::TextureUsages::COPY_SRC,
            view_formats: &[],
        });
        let mut renderer = Renderer::new(&device, format);
        renderer.resize(&queue, SIZE, SIZE);
        let red = Quad {
            rect: [16.0, 16.0, 32.0, 32.0],
            color: [1.0, 0.0, 0.0, 1.0],
        };
        renderer.set_quads(&device, &queue, &[red]);
        let view = target.create_view(&wgpu::TextureViewDescriptor::default());
        let mut encoder = device.create_command_encoder(&wgpu::CommandEncoderDescriptor::default());
        renderer.encode(&mut encoder, &view);
        queue.submit([encoder.finish()]);

        let pixels = read_pixels(&device, &queue, &target);
        let px = |x: u32, y: u32| {
            let i = ((y * SIZE + x) * 4) as usize;
            [pixels[i], pixels[i + 1], pixels[i + 2], pixels[i + 3]]
        };
        assert_eq!(px(16, 16), [255, 0, 0, 255], "top-left corner of the quad");
        assert_eq!(
            px(47, 47),
            [255, 0, 0, 255],
            "bottom-right corner of the quad"
        );
        assert_eq!(
            px(15, 32),
            [0, 0, 0, 255],
            "left of the quad is the clear color"
        );
        assert_eq!(
            px(48, 32),
            [0, 0, 0, 255],
            "right of the quad is the clear color"
        );
    }
}
