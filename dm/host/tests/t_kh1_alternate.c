// KH1 alternate original cached-write+explicit-flush state, not a new serializer.
#define main shared_guard_main
#include "t_kh2_guard.c"
#undef main
static int alternate_calls;
static uint64_t alternate_body(ARGS){
    UNUSED;alternate_calls++;
    uint64_t r[31]={(uintptr_t)object};kh2_wrap(4,r); // original 12dec
    *(int32_t *)(g_base+0x2458858)=r[0]; // original 12df0
    r[0]=(uintptr_t)object;kh2_wrap(8,r); // original 12df8
    *(int32_t *)(g_base+0x2458858)=73; // original 12dfc overwrites flush failure
    return 3; // original state-machine result, not serialized length
}
static uint64_t invoke(void){
#ifdef DM_KH1_ALT_WRAPPER
    uint64_t r[31]={0};kh2_wrap(10,r);return r[0];
#else
    return alternate_body(0,0,0,0,0,0,0,0); // pre-port original entrant semantics
#endif
}
int main(void){
    alarm(10);g_base=calloc(1,0x2458860);assert(g_base);g_commit=commit_fn;
    g_body[1]=init_body;g_body[4]=update_body;g_body[8]=serializer_body;
#ifdef DM_KH1_ALT_WRAPPER
    g_body[10]=alternate_body;
#endif
    uint64_t r[31]={(uintptr_t)object};kh2_wrap(1,r);release_flush=1;
    assert(invoke()==3 && alternate_calls==1 && commits==1 && !object[0x68]);
    fail_commit=514;
    assert(invoke()==3 && alternate_calls==2 && commits==2 && object[0x68]);
    assert(*(int32_t *)(g_base+0x2458858)==-1 && "alternate final store must not hide original flush failure");
    fail_commit=0;assert(invoke()==3 && commits==3 && !object[0x68]);
    assert(*(int32_t *)(g_base+0x2458858)==73);
    png=0;assert(invoke()==3 && commits==3 && rejects==1 && object[0x68]);
    assert(*(int32_t *)(g_base+0x2458858)==-1);
    free(g_base);puts("PASS Program1 alternate state: one original flush, late failure status, unchanged state return and full retry");
}
