#pragma once
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef struct { uint64_t t_ns, buttons; int source, axes[4]; } dm_replay_event;
// Parses the exact recorder format; rejects unrelated/truncated/invalid lines.
// Source -1 is iOS merged front-end input; 0..7 is the pad player index.
static inline int dm_input_replay_parse(const char *s, dm_replay_event *e) {
    if (!s || !e) return 0;
    unsigned long long t, b; int src, a[4], n = 0;
    if (sscanf(s, "[dm] [input-trace] t_ns=%llu source=%d buttons=%llx axes=%d,%d,%d,%d%n",
               &t, &src, &b, &a[0], &a[1], &a[2], &a[3], &n) != 7 || !n || t == 0 || src < -1 || src > 7) return 0;
    for (int i = 0; i < 4; i++) if (a[i] < -32768 || a[i] > 32767) return 0;
    if (s[n] != 0 && !(s[n] == '\n' && s[n+1] == 0)) return 0;
    *e = (dm_replay_event){.t_ns=t, .buttons=b, .source=src, .axes={a[0],a[1],a[2],a[3]}};
    return 1;
}
