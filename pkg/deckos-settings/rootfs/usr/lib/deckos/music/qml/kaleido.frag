// Vibe mode's Kaleido: a kaleidoscope turning around the cover. The world folded into eight mirrored slices that
// turn slowly (and jump a little on the beat); rings, flowing bands and petals that open with the bass, in the
// colours, brighter with the sound.
// Compile: qsb --qt6 -o kaleido.frag.qsb kaleido.frag
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

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

void main() {
    vec2 p = origin + qt_TexCoord0 * view;
    vec2 d = p - cover;
    float r = length(d);
    float far = length(max(cover, world - cover));
    float slices = 8.0;
    float turn = t * 0.12 + kick * 0.08;
    float a = atan(d.y, d.x) + turn;
    float seg = 6.2831853 / slices;
    a = abs(mod(a, seg) - seg * 0.5);  // fold into one mirrored slice
    vec2 q = vec2(cos(a), sin(a)) * r / world.y;  // the slice, in screen heights

    int k = int(clamp(r / far, 0.0, 1.0) * 63.0);
    float level = bar(k);
    // rings running outward, pushed by the music at their distance
    float rings = pow(0.5 + 0.5 * sin(r / world.y * 26.0 - t * 2.4 + level * 4.0), 3.0);
    // flowing bands across the slice
    float bands = 0.5 + 0.5 * sin(q.x * 10.0 + sin(q.y * 16.0 + t * 0.9) * 1.6 - t * 0.7);
    // petals: the slice's edge curving, opening with the bass
    float petal = smoothstep(0.08 + 0.12 * bass, 0.0, abs(q.y - 0.18 * sin(q.x * 6.0 - t * 0.8)));
    float spark = step(0.995, hash(floor(q * 110.0) + floor(t * 6.0)));
    vec3 col = mix(accent.rgb, second.rgb, bands) * (rings * (0.5 + 1.1 * level) + 0.25 * bands);
    col += mix(second.rgb, accent.rgb, rings) * petal * (0.35 + 0.8 * bass);
    col += vec3(1.0) * spark * (0.4 + level);
    col *= smoothstep(far * 1.1, far * 0.15, r);
    col += base.rgb * 0.3;
    fragColor = opened(col, p);
}
