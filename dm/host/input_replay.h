#pragma once
#include <stdint.h>
#include <string.h>

typedef struct { uint64_t t_ns, buttons; int source, axes[4]; } dm_replay_event;
// Accumulate before narrowing: scanf's integer conversions accept negative
// unsigned values and can wrap overflowing axes/source indices into range.
static inline int dm_replay_number(const char **s, unsigned base, uint64_t max, uint64_t *out) {
    const char *p = *s; uint64_t v = 0; int seen = 0;
    for (;;) {
        unsigned char c = (unsigned char)*p;
        unsigned d = c >= '0' && c <= '9' ? c-'0' : c >= 'a' && c <= 'f' ? c-'a'+10 : c >= 'A' && c <= 'F' ? c-'A'+10 : 255;
        if (d >= base) break;
        if (v > max/base || (v == max/base && d > max%base)) return 0;
        v = v*base+d; p++; seen = 1;
    }
    if (!seen) return 0;
    *s = p; *out = v; return 1;
}
static inline int dm_replay_literal(const char **s, const char *lit) {
    size_t n = strlen(lit);
    if (strncmp(*s,lit,n)) return 0;
    *s += n; return 1;
}
// Parses the recorder format; rejects unrelated/truncated/invalid lines.
// Source -1 is iOS merged front-end input; 0..7 is the pad player index.
static inline int dm_input_replay_parse(const char *s, dm_replay_event *e) {
    if (!s || !e) return 0;
    dm_replay_event v = {0}; uint64_t n;
    if (!dm_replay_literal(&s,"[dm] [input-trace] t_ns=") ||
        !dm_replay_number(&s,10,UINT64_MAX,&v.t_ns) || !v.t_ns ||
        !dm_replay_literal(&s," source=")) return 0;
    if (*s == '-') { s++; if (!dm_replay_number(&s,10,1,&n) || n != 1) return 0; v.source = -1; }
    else { if (!dm_replay_number(&s,10,7,&n)) return 0; v.source = (int)n; }
    if (!dm_replay_literal(&s," buttons=")) return 0;
    if (s[0]=='0' && (s[1]=='x' || s[1]=='X')) s+=2;
    if (!dm_replay_number(&s,16,UINT64_MAX,&v.buttons) || !dm_replay_literal(&s," axes=")) return 0;
    for (int i=0; i<4; i++) {
        int neg = *s=='-'; if (neg) s++;
        if (!dm_replay_number(&s,10,neg ? 32768 : 32767,&n)) return 0;
        v.axes[i] = neg ? -(int)n : (int)n;
        if (i<3 && !dm_replay_literal(&s,",")) return 0;
    }
    if (*s=='\n') s++;
    if (*s) return 0;
    *e = v; return 1;
}
