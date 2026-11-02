// CPU-only production capture -> parser -> scheduler -> setters/HID readout.
// Unrelated host/GPU symbols come from the existing HID test's stubs only.
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include "../dm.h"
static int replay_test_fprintf(FILE *, const char *, ...);
#define fprintf replay_test_fprintf
#define main unused_hid_suite_main
#define dm_input_replay_mac_start unused_hid_replay_stub
#include "t_hid.c"
#undef dm_input_replay_mac_start
#undef main
#include "../input_replay_mac.c"
#undef fprintf

static dm_replay_event expected[64];
static unsigned expected_count, seen, iteration;
static int observing;
static uint64_t first_dispatch;
static int replay_test_fprintf(FILE *stream, const char *fmt, ...) {
    char line[8192]; va_list ap; va_start(ap,fmt);
    int n=vsnprintf(line,sizeof line,fmt,ap); va_end(ap);
    assert(n>=0 && (size_t)n<sizeof line);
    fputs(line,stream);
    dm_replay_event e;
    if (observing && dm_input_replay_parse(line,&e)) {
        if (seen < expected_count) {
            dm_replay_event *want=&expected[seen];
            assert(e.source==want->source && e.buttons==want->buttons);
            assert(!memcmp(e.axes,want->axes,sizeof e.axes));
            if (!seen) first_dispatch=e.t_ns;
            // The scheduler must not collapse the recorded inter-event delays.
            assert(e.t_ns-first_dispatch+1000000 >= want->t_ns-expected[0].t_ns);
        } else {
            assert(e.buttons==0 && !e.axes[0] && !e.axes[1] && !e.axes[2] && !e.axes[3]);
        }
        uint64_t got_buttons=e.source<0 ? atomic_load(&g_btn) : atomic_load(&g_pad_btn[e.source]);
        uint64_t got_axes=e.source<0 ? atomic_load(&g_axes) : atomic_load(&g_pad_axes[e.source]);
        assert(got_buttons==e.buttons && got_axes==pack(e.axes[0],e.axes[1],e.axes[2],e.axes[3]));
        // Execute production HID state assembly, not just the setter's storage.
        int player=e.source<0 ? 0 : e.source;
        NpadState state; fill(&state,(uint32_t)player,STYLE_FULLKEY);
        uint64_t merged=atomic_load(&g_pad_btn[player]);
        if (!player) merged|=atomic_load(&g_btn);
        assert(state.attributes & ATTR_CONNECTED);
        assert((state.buttons & 0xffff)==(merged & 0xffff));
        // Independent fixed oracle for our seven-publication capture + EOF
        // release; do not derive this from production pack/pick helpers.
        static const int axes_oracle[8][4] = {
            {-32768,123,0,0}, {-32768,123,32767,-32768}, {3,4,5,6},
            {1,-2,32767,-32768}, {0}, {0}, {0}, {0}
        };
        static const uint64_t buttons_oracle[8] = {
            DM_BTN_A, DM_BTN_A|DM_BTN_B, DM_BTN_X, DM_BTN_B, 0, 0, DM_BTN_Y, 0
        };
        assert(seen<8);
        assert((state.buttons & 0xffff)==buttons_oracle[seen]);
        assert(state.lx==axes_oracle[seen][0] && state.ly==axes_oracle[seen][1]);
        assert(state.rx==axes_oracle[seen][2] && state.ry==axes_oracle[seen][3]);
        seen++;
    }
    return n;
}

static void capture(void) {
    dm_input_set(DM_BTN_A,-32768,123,0,0);
    uint64_t pressed=dm_input_last_event_ns();
    dm_input_set(DM_BTN_A,-32768,123,0,0);
    assert(dm_input_last_event_ns()==pressed); // unchanged polls are suppressed
    usleep(8000); dm_pad_set_player(0,DM_BTN_B,1,-2,32767,-32768);
    usleep(8000); dm_pad_set_player(7,DM_BTN_X,3,4,5,6);
    usleep(8000); dm_input_set(0,0,0,0,0);
    usleep(8000); dm_pad_set_player(0,0,0,0,0,0);
    usleep(8000); dm_pad_set_player(7,0,0,0,0,0);
    usleep(8000); dm_input_set(DM_BTN_Y,0,0,0,0); // EOF must release held Y
}

static void assert_released(void) {
    assert(!atomic_load(&g_btn) && !atomic_load(&g_axes));
    for (int p=0;p<DM_PLAYERS;p++) assert(!atomic_load(&g_pad_btn[p]) && !atomic_load(&g_pad_axes[p]));
}
int main(int argc,char **argv) {
    assert(argc>=2);
    setenv("DM_KH_INPUT_TRACE","1",1);
    dm_pad_players(0xff);
    if (!strcmp(argv[1],"capture")) { capture(); puts("production capture complete"); return 0; }
    assert(argc==5 && !strcmp(argv[1],"replay"));
    FILE *f=fopen(argv[2],"r"); assert(f); char line[4096];
    while (fgets(line,sizeof line,f)) { assert(expected_count<64); assert(dm_input_replay_parse(line,&expected[expected_count++])); }
    fclose(f); assert(expected_count==7);
    unsetenv("DM_SAVE"); unsetenv("DM_KH_REPLAY_ALLOW"); unsetenv("DM_KH_REPLAY_CONFIRM_SAVE");
    assert(dm_input_replay_mac_start(argv[2])==-1);
    setenv("DM_SAVE","relative",1); setenv("DM_KH_REPLAY_CONFIRM_SAVE","relative",1); setenv("DM_KH_REPLAY_ALLOW","1",1);
    assert(dm_input_replay_mac_start(argv[2])==-1);
    setenv("DM_SAVE",argv[3],1); assert(dm_input_replay_mac_start(argv[2])==-1);
    setenv("DM_KH_REPLAY_CONFIRM_SAVE",argv[3],1);
    setenv("DM_KH_REPLAY_ALLOW","0",1); assert(dm_input_replay_mac_start(argv[2])==-1);
    setenv("DM_KH_REPLAY_ALLOW","1",1);
    unsigned repeats=(unsigned)strtoul(argv[4],NULL,10); assert(repeats>1 && repeats<=100);
    for (iteration=1;iteration<=repeats;iteration++) {
        seen=0; observing=1;
        assert(dm_input_replay_mac_start(argv[2])==1);
        assert(dm_input_replay_mac_start(argv[2])==0);
        for (int i=0;i<10000 && atomic_load(&replay_running);i++) usleep(1000);
        assert(!atomic_load(&replay_running)); observing=0;
        assert(seen==expected_count+1); // final held-Y release is a real changed state
        assert_released();
    }
    printf("pipeline: %u repeats; production capture/parser/scheduler/setters/HID PASS (NO save writes; NOT KH2 menu/slot route)\n",repeats);
}
