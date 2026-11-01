// Mac-only replay of captured KH2 input transitions. DM_CTL 'replay <log>'
// starts it after the operator has opened the same save/scene in an isolated
// host run. Absolute CLOCK_MONOTONIC timestamps in the log are converted to
// delays from the first transition. This cannot reproduce loading speed,
// random state, touch-screen gestures or six-axis motion automatically.
#include "dm.h"
#include "dm_input.h"
#include "input_replay.h"
#include <stdatomic.h>
#include <pthread.h>
#include <time.h>
#include <unistd.h>
#include <errno.h>

static _Atomic int replay_running;
static void *replay_main(void *arg) {
    char *path = arg;
    FILE *f = fopen(path, "r");
    if (!f) { LOG("[RED] input replay open failed: %s errno=%d", path, errno); goto done; }
    char line[4096]; dm_replay_event e; uint64_t first=0, start=0, prev=0; unsigned long long count=0;
    while (fgets(line, sizeof line, f)) {
        if (!strchr(line, '\n') && !feof(f)) { LOG("[RED] input replay line too long; stopping"); break; }
        if (!dm_input_replay_parse(line, &e)) continue;
        if (!first) { first=e.t_ns; start=clock_gettime_nsec_np(CLOCK_MONOTONIC); }
        if (e.t_ns < prev || e.t_ns - first > UINT64_C(7200)*1000000000ull) { LOG("[RED] input replay invalid time ordering / exceeds 2h; stopping"); break; }
        prev=e.t_ns;
        uint64_t target=start+(e.t_ns-first);
        while (clock_gettime_nsec_np(CLOCK_MONOTONIC)<target) {
            uint64_t left=target-clock_gettime_nsec_np(CLOCK_MONOTONIC);
            usleep((useconds_t)(left>10000000 ? 10000 : left/1000 ? left/1000 : 1));
        }
        if (e.source == -1) dm_input_set(e.buttons,e.axes[0],e.axes[1],e.axes[2],e.axes[3]);
        else dm_pad_set_player(e.source,e.buttons,e.axes[0],e.axes[1],e.axes[2],e.axes[3]);
        count++;
    }
    if (f) fclose(f);
    // Never leave a recorded key held after the replay file ends.
    if (count) {
        dm_input_set(0,0,0,0,0);
        for (int i=0;i<DM_PLAYERS;i++) dm_pad_set_player(i,0,0,0,0,0);
    }
    LOG("[input-replay] completed %llu transitions from %s",count,path);
done:
    free(path); atomic_store(&replay_running,0); return NULL;
}
int dm_input_replay_mac_start(const char *path) {
#if DM_GAME_PROGRAM_ID == 0x010090C022978003ull
    const char *save=getenv("DM_SAVE"), *confirm=getenv("DM_KH_REPLAY_CONFIRM_SAVE");
    if (!path || !*path || !save || save[0]!='/' || !confirm || strcmp(save,confirm) || !getenv("DM_KH_REPLAY_ALLOW") || strcmp(getenv("DM_KH_REPLAY_ALLOW"),"1")) return -1;
    FILE *f=fopen(path,"r"); if (!f) return -1; fclose(f);
    int z=0; if (!atomic_compare_exchange_strong(&replay_running,&z,1)) return 0;
    char *copy=strdup(path); pthread_t t;
    if (!copy || pthread_create(&t,NULL,replay_main,copy)) { free(copy); atomic_store(&replay_running,0); return -1; }
    pthread_detach(t); LOG("[input-replay] started %s (Mac only; isolated DM_SAVE=%s)",path,getenv("DM_SAVE")); return 1;
#else
    (void)path; return -1;
#endif
}
