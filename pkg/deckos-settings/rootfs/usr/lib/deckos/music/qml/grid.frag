// Vibe mode's Grid: 80s neon. A sky glowing at the horizon, a striped sun behind the cover that swells with the
// bass, mountains along the horizon drawn by the spectrum, and a grid floor racing toward you (faster when the song
// is intense), flaring on the beat. In world coordinates, so the horizon and the grid run across every screen.
// Compile: qsb --qt6 -o grid.frag.qsb grid.frag
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
    float travel;
    float bass;
    float mid;
    float energy;
    float kick;
    float reveal;
    vec4 base;
    vec4 accent;
    vec4 second;
    vec4 b0; vec4 b1; vec4 b2; vec4 b3; vec4 b4; vec4 b5; vec4 b6; vec4 b7;
    vec4 b8; vec4 b9; vec4 b10; vec4 b11; vec4 b12; vec4 b13; vec4 b14; vec4 b15;
};

float bar(int i) {
    vec4 B[16] = vec4[16](b0, b1, b2, b3, b4, b5, b6, b7, b8, b9, b10, b11, b12, b13, b14, b15);
    i = clamp(i, 0, 63);
    return B[i >> 2][i & 3];
}

// Coming in and going out: the stage opens as a circle from the cover, its edge glowing (as in stage.frag)
vec4 opened(vec3 col, vec2 p) {
    float r = length(p - cover);
    float far = length(max(cover, world - cover));
    float edge = reveal * far * 1.08;
    float shown = smoothstep(edge, edge - 160.0, r);
    float glow = reveal < 1.0 ? exp(-pow((r - edge) / 40.0, 2.0)) * 0.9 : 0.0;
    vec3 rim = mix(accent.rgb, vec3(1.0), 0.35) * glow;
    return vec4(col * shown + rim, clamp(shown + glow * 0.8, 0.0, 1.0)) * qt_Opacity;
}

void main() {
    vec2 p = origin + qt_TexCoord0 * view;
    float sunR = world.y * 0.27 * (1.0 + 0.05 * bass);
    float horizon = cover.y + sunR * 0.55;
    float halfW = max(cover.x, world.x - cover.x);

    // the sky: dark above, the colours glowing up from the horizon
    float up = clamp((horizon - p.y) / horizon, 0.0, 1.0);
    vec3 col = mix(mix(second.rgb, accent.rgb, 0.4) * 0.55, base.rgb * 0.5, smoothstep(0.0, 0.8, up));

    // the sun, striped in its lower half
    float d = length(p - cover);
    if (p.y < horizon && d < sunR) {
        float v = (p.y - (cover.y - sunR)) / (2.0 * sunR);  // 0 at its top
        vec3 sun = mix(mix(accent.rgb, vec3(1.0), 0.35), second.rgb, smoothstep(0.1, 1.0, v));
        float gap = step(0.45, v) * step(fract((p.y - cover.y) / (sunR * 0.11) - t * 0.25), 0.18 + 0.5 * (v - 0.45));
        col = mix(col, sun, 1.0 - gap);
    }
    col += mix(accent.rgb, second.rgb, 0.5) * 0.25 * exp(-max(0.0, d - sunR) / (sunR * 0.5)) * step(p.y, horizon);

    // mountains from the spectrum, mirrored out from the sun
    int k = int(abs(p.x - cover.x) / halfW * 63.0);
    float peak = horizon - (0.15 + bar(k) * 0.85) * world.y * 0.13;
    if (p.y > peak && p.y < horizon) {
        col = mix(base.rgb * 0.35, col, 0.15);
        col += accent.rgb * 0.9 * exp(-abs(p.y - peak) / 2.0);
    }

    // the floor: a perspective grid moving toward you
    if (p.y >= horizon) {
        float below = p.y - horizon + 1.0;
        float z = world.y * 0.35 / below;               // distance into the floor
        float lx = (p.x - cover.x) * z / world.y * 6.0;  // across
        float lz = z * 2.0 + travel * 1.6;               // along, moving
        // distance to the nearest line, in line spacings, against how much one pixel covers there
        float dx = min(fract(lx), 1.0 - fract(lx)), dz = min(fract(lz), 1.0 - fract(lz));
        float line = max(1.0 - smoothstep(0.0, fwidth(lx) * 1.4, dx), 1.0 - smoothstep(0.0, fwidth(lz) * 1.4, dz));
        float fade = exp(-z * 0.6);
        col = base.rgb * 0.2 + mix(accent.rgb, second.rgb, clamp(z * 0.4, 0.0, 1.0)) * line * fade * (1.1 + 0.9 * kick);
        col += mix(accent.rgb, second.rgb, 0.5) * 0.35 * exp(-below / (world.y * 0.04));  // the glow at the horizon
    }
    fragColor = opened(col, p);
}
