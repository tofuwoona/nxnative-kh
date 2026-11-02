// Numeric tokens must not wrap through scanf into valid controller states.
#include <stdio.h>
#include <string.h>
#include "../input_replay.h"
int main(void) {
    const char *bad[] = {
        "t_ns=-1 source=-1 buttons=0 axes=0,0,0,0",
        "t_ns=18446744073709551616 source=-1 buttons=0 axes=0,0,0,0",
        "t_ns=1 source=4294967295 buttons=0 axes=0,0,0,0",
        "t_ns=1 source=-1 buttons=-1 axes=0,0,0,0",
        "t_ns=1 source=-1 buttons=10000000000000000 axes=0,0,0,0",
        "t_ns=1 source=-1 buttons=0 axes=4294967296,0,0,0",
        "t_ns=1 source=-1 buttons=0 axes=-4294967296,0,0,0",
        "t_ns=1 source=-1 buttons=0 axes=32768,0,0,0",
        "t_ns=1 source=-1 buttons=0 axes=0,0,0,0 trailingdata",
    };
    int failed = 0;
    for (unsigned i=0; i<sizeof bad/sizeof *bad; i++) {
        char line[512]; snprintf(line,sizeof line,"[dm] [input-trace] %s\n",bad[i]);
        dm_replay_event e = {.t_ns=42}, before=e;
        if (dm_input_replay_parse(line,&e) || memcmp(&e,&before,sizeof e)) {
            fprintf(stderr,"FAIL invalid numeric/trailing record %u accepted or changed output: %s\n",i,bad[i]); failed++;
        }
    }
    dm_replay_event e;
    if (!dm_input_replay_parse("[dm] [input-trace] t_ns=18446744073709551615 source=7 buttons=0xffffffffffffffff axes=-32768,32767,0,-1\n",&e) || e.t_ns!=UINT64_MAX || e.buttons!=UINT64_MAX) failed++;
    printf("parser invalid records: %d failed\n",failed);
    return !!failed;
}
