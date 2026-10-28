// Vibe mode's Spectrum: the 2000s analyzer (Winamp, WMP), stretched across every monitor as one. 64 chunky bars
// of lit segments, the unlit ones still faintly there like a real display, a cap on each that falls slowly from the
// bar's last top, and the bars mirrored in a glossy floor. Like stage.frag, all of it comes from world coordinates,
// so the analyzer runs on from one screen to the next. Compile: qsb --qt6 -o spectrum.frag.qsb spectrum.frag
#version 440

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 world;
    vec2 origin;
    vec2 view;
    vec2 cover;
    float t;
    float bass;
    float kick;    // 1 on a beat, fading fast
    float reveal;
    vec4 base;
    vec4 accent;
    vec4 second;
    vec4 b0; vec4 b1; vec4 b2; vec4 b3; vec4 b4; vec4 b5; vec4 b6; vec4 b7;  // the 64 bars, four to a vec4
    vec4 b8; vec4 b9; vec4 b10; vec4 b11; vec4 b12; vec4 b13; vec4 b14; vec4 b15;
    vec4 p0; vec4 p1; vec4 p2; vec4 p3; vec4 p4; vec4 p5; vec4 p6; vec4 p7;  // and their falling caps
    vec4 p8; vec4 p9; vec4 p10; vec4 p11; vec4 p12; vec4 p13; vec4 p14; vec4 p15;
};

// The lit part of one column at height y (0 at the floor): segments, the faint unlit ones, and the cap
vec3 column(float y, float h, float cap, float maxH, float seg) {
    float slot = floor(y / seg);
    float inSeg = step(mod(y, seg), seg * 0.7);
    float top = slot * seg / maxH;   // how high this segment sits, 0..1
    vec3 lit = mix(second.rgb, accent.rgb, smoothstep(0.05, 0.65, top));
    lit = mix(lit, vec3(1.0, 0.96, 0.92), smoothstep(0.78, 1.0, top) * 0.75);  // hot at the very top
    vec3 col = (slot * seg < h ? lit * 1.15 : accent.rgb * 0.07) * inSeg;
    float capSlot = floor(cap * maxH / seg);
    if (slot == capSlot && capSlot >= 2.0 && capSlot * seg >= h)  // a cap only above a bar that's fallen
        col = mix(col, mix(accent.rgb, vec3(1.0), 0.6), inSeg);
    return col;
}

void main() {
    vec4 B[16] = vec4[16](b0, b1, b2, b3, b4, b5, b6, b7, b8, b9, b10, b11, b12, b13, b14, b15);
    vec4 P[16] = vec4[16](p0, p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12, p13, p14, p15);
    vec2 p = origin + qt_TexCoord0 * view;
    float r = length(p - cover);
    float far = length(max(cover, world - cover));

    // The ground: dark, a little lighter toward the floor, with fine scanlines
    vec3 col = base.rgb * (0.55 + 0.6 * smoothstep(0.0, 0.8, p.y / world.y));
    col *= 0.9 + 0.1 * step(1.0, mod(p.y, 3.0));

    float margin = world.x * 0.035;
    float cell = (world.x - 2.0 * margin) / 64.0;
    float floorY = world.y * 0.8;
    float maxH = world.y * 0.58;
    float seg = max(9.0, maxH / 26.0);
    float cx = (p.x - margin) / cell;
    int i = int(clamp(floor(cx), 0.0, 63.0));
    float inBar = step(0.0, cx) * step(cx, 64.0) * step(0.12, fract(cx)) * step(fract(cx), 0.88);
    float h = B[i >> 2][i & 3] * maxH;
    float cap = P[i >> 2][i & 3];

    float up = floorY - p.y;
    if (up >= 0.0 && up < maxH) {
        col += column(up, h, cap, maxH, seg) * inBar;
        // the glow above each bar's top, like light on a CRT
        float soft = exp(-pow((fract(cx) - 0.5) / 0.6, 2.0));
        col += accent.rgb * 0.16 * soft * exp(-max(0.0, up - h) / (seg * 3.0)) * step(0.0, cx) * step(cx, 64.0);
    } else if (up < 0.0) {
        // the floor: the bars mirrored, fading, rippling a little
        float down = -up;
        float wob = sin(down * 0.08 - t * 3.0) * 2.0 * (down / world.y);
        float cx2 = (p.x + wob - margin) / cell;
        float inBar2 = step(0.0, cx2) * step(cx2, 64.0) * step(0.12, fract(cx2)) * step(fract(cx2), 0.88);
        col += column(down, h, cap, maxH, seg) * inBar2 * 0.3 * exp(-down / (world.y * 0.08));
    }
    // the floor line flashes on the beat
    col += mix(accent.rgb, vec3(1.0), 0.3) * exp(-pow((p.y - floorY) / 2.5, 2.0)) * (0.25 + 0.75 * kick);

    float edge = reveal * far * 1.08;
    float shown = smoothstep(edge, edge - 160.0, r);
    float glow = reveal < 1.0 ? exp(-pow((r - edge) / 40.0, 2.0)) * 0.9 : 0.0;
    vec3 rim = mix(accent.rgb, vec3(1.0), 0.35) * glow;
    fragColor = vec4(col * shown + rim, clamp(shown + glow * 0.8, 0.0, 1.0)) * qt_Opacity;
}
