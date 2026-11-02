// Read-only validator against the production parser; NEVER dispatches input.
#include <stdio.h>
#include <stdint.h>
#include "../input_replay.h"
int main(int argc,char **argv) {
    if (argc!=2) return 2;
    FILE *f=fopen(argv[1],"r"); if (!f) return 2;
    char line[4096]; uint64_t prev=0,first=0; unsigned long long n=0;
    while (fgets(line,sizeof line,f)) {
        dm_replay_event e;
        if (!dm_input_replay_parse(line,&e) || e.t_ns<prev) { fclose(f); return 1; }
        if (!first) first=e.t_ns;
        if (e.t_ns-first>UINT64_C(7200000000000)) { fclose(f); return 1; }
        prev=e.t_ns; n++;
    }
    int bad=ferror(f) || !n; fclose(f);
    printf("production parser read-only: %llu records; %d failed\n",n,bad);
    return bad;
}
