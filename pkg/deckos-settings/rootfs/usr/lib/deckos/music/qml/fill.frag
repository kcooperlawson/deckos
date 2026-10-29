// The sung part of a lyric line: the text's own shape, filled with the Vibe's two colours from left to right.
// Compile: qsb --qt6 -o fill.frag.qsb fill.frag
#version 440

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec4 a;
    vec4 b;
};
layout(binding = 1) uniform sampler2D source;

void main() {
    float alpha = texture(source, qt_TexCoord0).a;
    fragColor = vec4(mix(a.rgb, b.rgb, qt_TexCoord0.x) * alpha, alpha) * qt_Opacity;
}
