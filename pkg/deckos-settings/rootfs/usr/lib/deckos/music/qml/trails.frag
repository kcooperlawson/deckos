// Vibe mode's Trails: the 2000s feedback visualizer (Milkdrop, the WMP plug-ins), our way. Each frame starts from
// the last one, zoomed out from the cover a little (more on the bass), turned and rippled, and dimmed, then a ring
// of sound is drawn around the cover: so every ring leaves a trail that flows outward across the screens. The warp
// is in world coordinates, centred on the cover, so every monitor flows the same way. Trails.qml feeds the picture
// back in; trails_show.frag shows it. Compile: qsb --qt6 -o trails.frag.qsb trails.frag
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
    float mid;
    float kick;
    vec4 accent;
    vec4 second;
    vec4 b0; vec4 b1; vec4 b2; vec4 b3; vec4 b4; vec4 b5; vec4 b6; vec4 b7;
    vec4 b8; vec4 b9; vec4 b10; vec4 b11; vec4 b12; vec4 b13; vec4 b14; vec4 b15;
};
layout(binding = 1) uniform sampler2D last;  // the previous frame

void main() {
    vec4 B[16] = vec4[16](b0, b1, b2, b3, b4, b5, b6, b7, b8, b9, b10, b11, b12, b13, b14, b15);
    vec2 p = origin + qt_TexCoord0 * view;
    vec2 d = p - cover;

    // Where this pixel's colour was last frame: nearer the cover (so it flows out), turned, rippling
    float ang = 0.004 * sin(t * 0.21) + 0.006 * mid * sin(t * 0.13 + 1.0);
    float zoom = 1.0 - (0.007 + 0.03 * bass);
    vec2 src = cover + mat2(cos(ang), -sin(ang), sin(ang), cos(ang)) * d * zoom;
    src += 2.5 * vec2(sin(d.y * 0.012 + t * 0.7), cos(d.x * 0.012 + t * 0.6));
    vec2 uv = (src - origin) / view;
    vec3 col = vec3(0.0);
    if (uv.x > 0.0 && uv.x < 1.0 && uv.y > 0.0 && uv.y < 1.0)
        col = texture(last, uv).rgb * vec3(0.952, 0.948, 0.958);

    // The ring of sound: the spectrum wrapped around the cover, mirrored left and right
    float r = length(d);
    float a = atan(d.y, d.x);
    int k = int(clamp(abs(a) / 3.14159 * 63.0, 0.0, 63.0));
    float R = world.y * 0.2 + B[k >> 2][k & 3] * world.y * 0.14;
    float line = exp(-pow((r - R) / (2.0 + 4.0 * kick), 2.0));
    vec3 hue = mix(accent.rgb, second.rgb, 0.5 + 0.5 * sin(t * 0.4 + a * 2.0));
    col += hue * line * (0.55 + 0.6 * kick);

    // And a wave through the cover from one end of the world to the other (the spectrum again, louder near the
    // cover), so every screen has something to trail, not just the cover's
    float along = abs(p.x - cover.x) / max(cover.x, world.x - cover.x);
    int j = int(clamp(along * 63.0, 0.0, 63.0));
    float wave = cover.y + sin(p.x * 0.012 - t * 2.0) * B[j >> 2][j & 3] * world.y * 0.16 * (1.0 - 0.5 * along);
    float wline = exp(-pow((p.y - wave) / 2.5, 2.0)) * step(R + 30.0, r);
    col += mix(second.rgb, accent.rgb, along) * wline * (0.4 + 0.4 * kick);
    fragColor = vec4(min(col, vec3(1.4)), 1.0);
}
