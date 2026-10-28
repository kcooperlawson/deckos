// Vibe mode's Glow, the calm one: four soft lights in the Vibe's (or cover's) colours drift slowly across the
// world and swell a little with the bass, over a dark ground with a touch of grain. No rings, no stars.
// Compile: qsb --qt6 -o glow.frag.qsb glow.frag
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
    float energy;
    float reveal;
    vec4 base;
    vec4 accent;
    vec4 second;
};

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

void main() {
    vec2 p = origin + qt_TexCoord0 * view;
    float r = length(p - cover);
    float far = length(max(cover, world - cover));

    vec3 col = base.rgb * 0.7;
    for (int i = 0; i < 4; i++) {
        float fi = float(i);
        vec2 at = world * vec2(0.5 + 0.42 * sin(t * (0.031 + 0.011 * fi) + fi * 1.7),
                               0.5 + 0.35 * sin(t * (0.043 + 0.009 * fi) + fi * 2.9));
        float size = world.y * (0.42 + 0.08 * fi) * (1.0 + 0.12 * bass);
        vec3 tint = i == 0 ? accent.rgb : i == 1 ? second.rgb : i == 2 ? mix(accent.rgb, second.rgb, 0.5)
                                                                       : mix(accent.rgb, base.rgb, 0.4);
        col += tint * exp(-pow(length(p - at) / size, 2.0)) * (0.17 + 0.1 * energy);
    }
    col *= 0.85 + 0.15 * exp(-r / (far * 0.5));
    col += (hash(p + fract(t) * 91.0) - 0.5) * 0.025;

    float edge = reveal * far * 1.08;
    float shown = smoothstep(edge, edge - 160.0, r);
    float glow = reveal < 1.0 ? exp(-pow((r - edge) / 40.0, 2.0)) * 0.9 : 0.0;
    vec3 rim = mix(accent.rgb, vec3(1.0), 0.35) * glow;
    fragColor = vec4(col * shown + rim, clamp(shown + glow * 0.8, 0.0, 1.0)) * qt_Opacity;
}
