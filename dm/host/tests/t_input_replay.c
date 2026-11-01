#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "../input_replay.h"
int main(void) {
    dm_replay_event e;
    assert(dm_input_replay_parse("[dm] [input-trace] t_ns=18455551000 source=-1 buttons=0x4 axes=-32767,123,0,0\n", &e));
    assert(e.t_ns == UINT64_C(18455551000) && e.source == -1 && e.buttons == 4 && e.axes[0] == -32767 && e.axes[1] == 123);
    assert(!dm_input_replay_parse("[dm] [vk-diag] pass frame=1", &e));
    assert(!dm_input_replay_parse("[dm] [input-trace] t_ns=5 source=999 buttons=0x1 axes=0,0,0,0", &e));
    assert(!dm_input_replay_parse("[dm] [input-trace] t_ns=5 source=0 buttons=0x1 axes=90000,0,0,0", &e));
    assert(!dm_input_replay_parse("[dm] [input-trace] t_ns=5 source=0 buttons=0x1 axes=0,0,0,0 GARBAGE", &e));
    puts("input replay parser: 5 checks passed");
}
