// A sibling profile must reject replay even when all operator guards are set.
#define main unused_reject_suite_main
#include "t_input_replay_reject.c"
#undef main
int main(int argc,char **argv) {
    assert(argc==2);
    setenv("DM_SAVE",argv[1],1); setenv("DM_KH_REPLAY_CONFIRM_SAVE",argv[1],1); setenv("DM_KH_REPLAY_ALLOW","1",1);
    assert(dm_input_replay_mac_start("unused.log")==-1);
    assert(!atomic_load(&replay_running) && !atomic_load(&a_presses));
    puts("sibling profile: replay disabled PASS");
}
