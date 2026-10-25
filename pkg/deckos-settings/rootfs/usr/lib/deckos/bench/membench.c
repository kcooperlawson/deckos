// DecKoOS Bench memory test: bandwidth (STREAM-style copy and triad over every core) and latency (a
// random pointer chase, one load at a time, so prefetching can't hide it). Arrays are 8x the
// biggest L3 seen in AMD and Intel desktop CPUs (X3D included), so it measures RAM, not cache.
// Bench compiles it once: gcc -O3 -march=native -fopenmp membench.c -o membench
// Prints key=value lines: copy_gbs, triad_gbs, latency_ns.
#include <omp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define N (64UL * 1024 * 1024)           // doubles per array: 512 MiB each
#define CHASE (256UL * 1024 * 1024 / 8)  // pointer-chase slots: 256 MiB
#define REPS 6

static double now(void)
{
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec * 1e-9;
}

int main(void)
{
    double *a = aligned_alloc(64, N * sizeof(double));
    double *b = aligned_alloc(64, N * sizeof(double));
    double *c = aligned_alloc(64, N * sizeof(double));
    if (!a || !b || !c) {
        fprintf(stderr, "not enough memory\n");
        return 1;
    }
#pragma omp parallel for
    for (size_t i = 0; i < N; i++) {  // first touch on the thread that uses it (NUMA-friendly)
        a[i] = 1.0;
        b[i] = 2.0;
        c[i] = 0.0;
    }

    double best_copy = 1e9, best_triad = 1e9;
    for (int r = 0; r < REPS; r++) {
        double t = now();
#pragma omp parallel for
        for (size_t i = 0; i < N; i++)
            c[i] = a[i];
        t = now() - t;
        if (t < best_copy)
            best_copy = t;

        t = now();
#pragma omp parallel for
        for (size_t i = 0; i < N; i++)
            a[i] = b[i] + 3.0 * c[i];
        t = now() - t;
        if (t < best_triad)
            best_triad = t;
    }
    // STREAM's byte counts: copy moves 2 arrays, triad 3
    printf("copy_gbs=%.2f\n", 2.0 * N * sizeof(double) / best_copy / 1e9);
    printf("triad_gbs=%.2f\n", 3.0 * N * sizeof(double) / best_triad / 1e9);
    free(a);
    free(b);
    free(c);

    // Latency: a single random cycle through every slot (Sattolo's shuffle), one cache line per slot
    // stride so neighbours don't share lines.
    size_t *next = aligned_alloc(64, CHASE * sizeof(size_t));
    size_t lines = CHASE / 8, *order = malloc(lines * sizeof(size_t));
    if (!next || !order)
        return 1;
    for (size_t i = 0; i < lines; i++)
        order[i] = i * 8;
    uint64_t seed = 0x9E3779B97F4A7C15ULL;
    for (size_t i = lines - 1; i > 0; i--) {
        seed ^= seed << 13;
        seed ^= seed >> 7;
        seed ^= seed << 17;
        size_t j = seed % i;
        size_t tmp = order[i];
        order[i] = order[j];
        order[j] = tmp;
    }
    for (size_t i = 0; i < lines; i++)
        next[order[i]] = order[(i + 1) % lines];
    free(order);

    size_t p = 0, steps = 20UL * 1000 * 1000;
    for (size_t i = 0; i < 1000000; i++)  // warm the TLB and the path
        p = next[p];
    double t = now();
    for (size_t i = 0; i < steps; i++)
        p = next[p];
    t = now() - t;
    printf("latency_ns=%.2f\n", t / steps * 1e9);
    printf("check=%zu\n", p);  // keeps the chase from being optimised away
    free(next);
    return 0;
}
