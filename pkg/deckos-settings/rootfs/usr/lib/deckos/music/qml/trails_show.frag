// Shows Trails' fed-back picture on its dark ground, opening from the cover like the other stages.
// Compile: qsb --qt6 -o trails_show.frag.qsb trails_show.frag
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
    float reveal;
    vec4 base;
    vec4 accent;
};
layout(binding = 1) uniform sampler2D picture;

void main() {
    vec2 p = origin + qt_TexCoord0 * view;
    float r = length(p - cover);
    float far = length(max(cover, world - cover));
    vec3 col = base.rgb * (0.4 + 0.6 * exp(-r / (far * 0.6))) + texture(picture, qt_TexCoord0).rgb;
    float edge = reveal * far * 1.08;
    float shown = smoothstep(edge, edge - 160.0, r);
    float glow = reveal < 1.0 ? exp(-pow((r - edge) / 40.0, 2.0)) * 0.9 : 0.0;
    vec3 rim = mix(accent.rgb, vec3(1.0), 0.35) * glow;
    fragColor = vec4(col * shown + rim, clamp(shown + glow * 0.8, 0.0, 1.0)) * qt_Opacity;
}
