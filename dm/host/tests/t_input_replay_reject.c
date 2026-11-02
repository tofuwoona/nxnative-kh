// Focused scheduler failure regression; the pipeline test uses real setters.
#include <assert.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include "../input_replay_mac.c"
static _Atomic int a_presses, last_front;
void dm_input_set(uint64_t b,int32_t lx,int32_t ly,int32_t rx,int32_t ry) {
    (void)lx;(void)ly;(void)rx;(void)ry;
    atomic_store(&last_front,(int)b); if (b==DM_BTN_A) atomic_fetch_add(&a_presses,1);
}
void dm_pad_set_player(int p,uint64_t b,int32_t lx,int32_t ly,int32_t rx,int32_t ry) {
    (void)p;(void)b;(void)lx;(void)ly;(void)rx;(void)ry;
}
int main(int argc,char **argv) {
    assert(argc==2); char path[4096]; snprintf(path,sizeof path,"%s/reject.log",argv[1]);
    setenv("DM_SAVE",argv[1],1); setenv("DM_KH_REPLAY_CONFIRM_SAVE",argv[1],1); setenv("DM_KH_REPLAY_ALLOW","1",1);
    const char *invalid[] = {
        "[dm] [input-trace] t_ns=1000000001 source=-1 buttons=0 axes=90000,0,0,0\n",
        "[dm] [input-trace] t_ns=1000000001 source=-1 buttons=0 axes=0,0,0,0 trailingdata\n",
        "[dm] [input-trace] t_ns=999999999 source=-1 buttons=0 axes=0,0,0,0\n",
        "[dm] [input-trace] t_ns=7201000000001 source=-1 buttons=0 axes=0,0,0,0\n",
    };
    int fails=0;
    for (unsigned i=0;i<sizeof invalid/sizeof *invalid;i++) {
        FILE *f=fopen(path,"w"); assert(f);
        fputs("ordinary log\n[dm] [input-trace] t_ns=1000000000 source=-1 buttons=0x2 axes=0,0,0,0\n",f);
        fputs(invalid[i],f);
        fputs("[dm] [input-trace] t_ns=1000000002 source=-1 buttons=0x1 axes=0,0,0,0\n",f); fclose(f);
        atomic_store(&a_presses,0);
        assert(dm_input_replay_mac_start(path)==1);
        for (int j=0;j<5000 && atomic_load(&replay_running);j++) usleep(1000);
        assert(!atomic_load(&replay_running));
        if (atomic_load(&a_presses) || atomic_load(&last_front)) { fprintf(stderr,"FAIL scheduler dispatched beyond invalid capture %u\n",i); fails++; }
    }
    unlink(path); printf("scheduler reject: %d failed\n",fails); return !!fails;
}
