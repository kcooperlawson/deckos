// Vibe mode's sky: one world that spans every monitor. Each window draws only its own part of it (origin, view),
// so an aurora runs on from one screen to the next and a beat's shockwave leaves the cover and rolls across them
// all. Everything comes from world coordinates and the shared clock, never from the window, so the screens agree.
// Compiled to stage.frag.qsb (tests/test_music.py checks it's current): qsb --qt6 -o stage.frag.qsb stage.frag
#version 440

layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 world;    // the whole stage, in pixels
    vec2 origin;   // this window's top left in the world
    vec2 view;     // this window's size
    vec2 cover;    // where the cover sits, in the world
    float t;       // seconds, the same on every screen
    float travel;  // how far the stars have flown (faster when the song is intense)
    float bass;
    float mid;
    float high;
    float energy;
    float reveal;  // 0: the desktop, 1: the whole world is the stage
    vec4 beats;    // when the last four beats landed (t), oldest first
    vec4 base;
    vec4 accent;
    vec4 second;
};

float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}

// One layer of stars flying out of the cover: a grid in a zoomed space, born small at the middle, gone at the edge
float stars(vec2 d, float scale, float phase, float span) {
    float s = fract(travel * 0.08 + phase);
    vec2 q = d / (span * (0.08 + s * 1.6)) * scale;
    vec2 cell = floor(q), f = fract(q) - 0.5;
    float h = hash(cell + phase * 17.0);
    if (h < 0.82)
        return 0.0;
    vec2 at = vec2(hash(cell + 3.1), hash(cell + 7.7)) - 0.5;
    float size = 0.06 + 0.1 * hash(cell + 1.3);
    float star = smoothstep(size, 0.0, length(f - at * 0.6));
    float twinkle = 0.6 + 0.4 * sin(t * (2.0 + 5.0 * h) + h * 40.0) * (0.5 + high);
    return star * twinkle * smoothstep(0.0, 0.25, s) * smoothstep(1.0, 0.7, s);
}

void main() {
    vec2 p = origin + qt_TexCoord0 * view;   // where this pixel is in the world
    vec2 d = p - cover;
    float r = length(d);
    float span = max(world.x, world.y);
    // the farthest corner of the world from the cover: waves and the reveal reach it, wherever the cover sits
    float far = length(max(cover, world - cover));

    // The ground: the cover's dark base, lit around the cover and swelling with the bass
    vec3 col = base.rgb * (0.35 + 0.65 * exp(-r / (far * 0.55)));
    col += accent.rgb * 0.18 * (0.4 + bass) * exp(-r / (span * 0.18));

    // Aurora: three curtains across the whole world, drifting; brighter with the mids and the song's energy
    for (int i = 0; i < 3; i++) {
        float fi = float(i);
        float x = p.x / span;
        float y = world.y * (0.22 + 0.2 * fi)
                + world.y * 0.1 * sin(x * (5.0 + 2.0 * fi) + t * (0.11 + 0.05 * fi) + fi * 2.0)
                + world.y * 0.06 * (noise(vec2(x * 3.0 + t * 0.05, fi * 9.0)) - 0.5);
        float width = world.y * (0.05 + 0.04 * mid + 0.02 * fi);
        float band = exp(-pow((p.y - y) / width, 2.0));
        float curtain = 0.55 + 0.45 * noise(vec2(x * 60.0 + fi * 13.0, t * 0.6 + fi));
        vec3 tint = mix(accent.rgb, second.rgb, 0.5 + 0.5 * sin(x * 4.0 + t * 0.2 + fi * 2.1));
        col += tint * band * curtain * (0.12 + 0.42 * energy + 0.2 * mid);
    }

    // Light from the cover: slow rays turning, longer on the bass
    float a = atan(d.y, d.x);
    float rays = pow(0.5 + 0.5 * sin(a * 9.0 + t * 0.15 + 2.0 * sin(a * 2.0 - t * 0.09)), 6.0);
    col += mix(accent.rgb, second.rgb, 0.3) * rays * exp(-r / (far * (0.25 + 0.35 * bass))) * (0.08 + 0.35 * bass);

    // Stars flying out of the cover, across every screen
    float st = stars(d, 26.0, 0.0, span) + stars(d, 34.0, 0.33, span) + stars(d, 44.0, 0.66, span);
    col += vec3(0.9, 0.93, 1.0) * st * (0.5 + 0.5 * energy);

    // Each beat sends a ring out of the cover that rolls across the monitors and fades as it goes
    for (int i = 0; i < 4; i++) {
        float age = t - beats[i];
        if (age < 0.0 || age > 2.4)
            continue;
        float front = age * far / 1.7;
        float w = 18.0 + age * 70.0;
        float ring = exp(-pow((r - front) / w, 2.0)) * (1.0 - age / 2.4);
        col += mix(accent.rgb, second.rgb, age / 2.4) * ring * 0.55;
    }

    // Coming in and going out: the stage opens as a circle from the cover, its edge glowing
    float edge = reveal * far * 1.08;
    float shown = smoothstep(edge, edge - 160.0, r);
    float glow = reveal < 1.0 ? exp(-pow((r - edge) / 40.0, 2.0)) * 0.9 : 0.0;
    vec3 rim = mix(accent.rgb, vec3(1.0), 0.35) * glow;
    float alpha = clamp(shown + glow * 0.8, 0.0, 1.0);
    fragColor = vec4(col * shown + rim, alpha) * qt_Opacity;
}
