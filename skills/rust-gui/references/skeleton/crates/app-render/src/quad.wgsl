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
