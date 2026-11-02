// Execute the real host gate registry/dispatch, with synthetic module metadata.
#define main metadata_main
#include "game_profile.h"
#if DM_GAME_PROGRAM_ID == 0x010090C022978001ull
#include "t_kh1_gates.c"
#define TEST_LAST 18
#else
#include "t_kh2_gates.c"
#define TEST_LAST 17
#endif
#undef main
#include "kh_save_test_profile.h"
#include "../hle.c"
#ifndef DM_KH2_DISPATCH
static void gate_kh2_prepare(void) {}
#endif
struct dm_flags g_flag;
uint64_t unimpl_stubs[MAX_STUB];
void *hlecount_wrap(const char *a,const char *b,void *p){(void)a;(void)b;return p;}
uint64_t guest_ns(void){return 0;}void guest_clock_read_wait(void){}
uint64_t svc_dispatch(int n,uint64_t *r,uint64_t o){(void)n;(void)r;(void)o;assert(!"unexpected ordinary SVC");return 0;}
void thr_svc_enter(uint64_t *r,uint64_t o){(void)r;(void)o;assert(!"guest callback must not own outer SVC context");}
void thr_svc_leave(void){assert(!"unexpected outer SVC leave");}
void dm_spin_wait(uint64_t a,uint64_t b){(void)a;(void)b;}
module_t *module_of(const void *p){return p>= (void *)g_mod[0].base && p<(void *)(g_mod[0].base+g_mod[0].size)?g_mod:NULL;}
void dm_kh2_save_gate(uint64_t ret,uint64_t *r){dm_kh2_save_dispatch(ret,r);}
int main(void){
    synthetic();
    for(int i=1;i<=TEST_LAST;i++)gate_register((uintptr_t)g_mod[0].base+ret_for(i),iswrap(i)?"kh2wrap":"svc",gatearg(i),offsets[i]);
    pid_t child=fork();assert(child>=0);
    if(!child){gate_register((uintptr_t)g_mod[0].base+ret_for(TEST_LAST+1),"svc",0x7f08,0x41048);gate_kh2_prepare();_exit(0);}
    int status;waitpid(child,&status,0);assert(WIFSIGNALED(status)&&WTERMSIG(status)==SIGABRT);
    gate_kh2_prepare();
    unsigned char flag=1;*(uint64_t *)(g_base+TEST_PNG_FLAG)=(uintptr_t)&flag;
    flush_ctx f={0};g_flush=&f;
    uint64_t r[31]={(uint32_t)-1};r[23]=(uintptr_t)&flag;
    gate_dispatch((uintptr_t)g_mod[0].base+ret_for(11),r);
    assert(!flag && !r[0]);
    g_flush=NULL;flag=1;r[0]=(uint32_t)-1;
    gate_dispatch((uintptr_t)g_mod[0].base+ret_for(11),r);
    assert(flag==1 && r[0]==1); // outside flush: original ldrb, no repair side effect
    free(g_mod[0].base);puts("PASS real registry/private dispatch without outer SVC frame, outside-flush original PNG status");return 0;
}
