#include <assert.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include "../input_replay_mac.c"
static _Atomic int n_front, n_press;
void dm_input_set(uint64_t b, int32_t lx, int32_t ly, int32_t rx, int32_t ry) {
    (void)lx;(void)ly;(void)rx;(void)ry;atomic_fetch_add(&n_front,1);if(b==DM_BTN_A) atomic_fetch_add(&n_press,1);
}
void dm_pad_set_player(int p,uint64_t b,int32_t lx,int32_t ly,int32_t rx,int32_t ry) {
    (void)p;(void)b;(void)lx;(void)ly;(void)rx;(void)ry;
}
int main(void) {
    char dir[]="/Users/tofu/.hermes/cache/scratch/kh-input-replay.XXXXXX";
    assert(mkdtemp(dir));
    char path[512];snprintf(path,sizeof path,"%s/trace.log",dir);
    FILE *f=fopen(path,"w");assert(f);
    fputs("[dm] [input-trace] t_ns=1000000000 source=-1 buttons=0x1 axes=0,0,0,0\n",f);
    fputs("[dm] [input-trace] t_ns=1030000000 source=-1 buttons=0 axes=0,0,0,0\n",f);
    fclose(f);
    assert(dm_input_replay_mac_start(path)==-1); // no explicit consent or save
    setenv("DM_SAVE",dir,1);setenv("DM_KH_REPLAY_ALLOW","1",1);
    assert(dm_input_replay_mac_start(path)==-1); // missing matching save-path confirmation
    setenv("DM_KH_REPLAY_CONFIRM_SAVE",dir,1);
    assert(dm_input_replay_mac_start(path)==1);
    assert(dm_input_replay_mac_start(path)==0); // cannot start a second replay
    for(int i=0;i<1000 && atomic_load(&replay_running);i++) usleep(1000);
    assert(!atomic_load(&replay_running));
    assert(atomic_load(&n_press)==1 && atomic_load(&n_front)==3); // press, release, final clear
    unlink(path);rmdir(dir);puts("Mac input replay: exact press/release order and guard verified");
}
