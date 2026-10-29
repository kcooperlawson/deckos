// Vibe mode's Scope: an oscilloscope. The music drawn as one glowing line through every screen (the spectrum as a sum
// of waves: bass makes the big slow swells, highs the fine wobble), with fading echoes of where it just was, over a
// faint graticule. Compile: qsb --qt6 -o scope.frag.qsb scope.frag
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

float wave(float x, float when) {
    float y = 0.0;
    for (int i = 0; i < 16; i++) {
        float fi = float(i);
        float level = (bar(i * 4) + bar(i * 4 + 2)) * 0.5;
        y += level * sin(x * (0.004 + fi * 0.0035) + when * (1.2 + fi * 0.45) + fi * 1.7) / (1.0 + fi * 0.25);
    }
    return y;
}

void main() {
    vec2 p = origin + qt_TexCoord0 * view;
    vec3 col = base.rgb * 0.45;
    // the graticule: faint lines every so often, brighter on the centre line
    vec2 g = abs(fract(p / (world.y * 0.1)) - 0.5);
    col += vec3(0.6, 0.7, 1.0) * 0.035 * (1.0 - smoothstep(0.0, 0.02, min(g.x, g.y)));
    col += accent.rgb * 0.06 * exp(-abs(p.y - cover.y) / 1.5);

    float amp = world.y * (0.22 + 0.12 * energy);
    for (int e = 4; e >= 0; e--) {  // the echoes first, the line itself last
        float fe = float(e);
        float y = cover.y + amp * wave(p.x, t - fe * 0.06);
        float dist = abs(p.y - y);
        float w = 2.2 + fe * 1.5 + 3.0 * kick * step(fe, 0.5);
        float strength = (e == 0 ? 1.0 : 0.35 / fe);
        vec3 hue = mix(accent.rgb, second.rgb, 0.5 + 0.5 * sin(p.x * 0.002 + t * 0.3 - fe * 0.4));
        col += hue * strength * (exp(-dist * dist / (w * w)) + 0.25 * exp(-dist / (w * 8.0)));
    }
    fragColor = opened(col, p);
}
