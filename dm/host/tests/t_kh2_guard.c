// CPU-only production exclusion/synchronous boundary tests with guest call seams.
#include "../hle_kh2_save.c"
#include "kh_save_test_profile.h"
#include <assert.h>
#include <stdatomic.h>
#include <unistd.h>
#include <sys/wait.h>
#include <signal.h>
#ifndef DM_KH2_GUARD
static uint8_t *g_base;
typedef uint64_t (*body_fn)(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t);
static body_fn g_body[9];
static void kh2_wrap(int id, uint64_t *r) { r[0]=g_body[id](r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7]); }
#endif
module_t g_mod[MAX_MOD]; int g_nmod;
pthread_key_t g_key18,g_keytls,g_keytlr,g_keygate;
int dm_thread_host_wait_begin(void) { return 0; }
void dm_thread_host_wait_end(int old) { (void)old; }
static int commits, rejects, png=1, recursive, fail_commit;
static _Atomic int inside, reader_done, release_flush;
static unsigned char object[0x1b0];
uint32_t dm_fs_reject_save(const char *n, int e) { (void)n; assert(e); rejects++; return 0x2a2; }
static uint32_t commit_fn(const char *n) { assert(!strcmp(n,"save")); commits++; return fail_commit; }
#define ARGS uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f,uint64_t g,uint64_t h
#define UNUSED (void)a;(void)b;(void)c;(void)d;(void)e;(void)f;(void)g;(void)h
static uint64_t init_body(ARGS) { UNUSED; return 1; }
static uint64_t update_body(ARGS) { UNUSED; assert(!atomic_load(&inside)); object[0x68]=1; return 73; }
static uint64_t write_body(ARGS) { UNUSED; uint64_t r[31]={(uintptr_t)object}; kh2_wrap(4,r); *(int32_t *)(g_base+TEST_STATUS)=73; return 0; }
static uint64_t serializer_body(ARGS) {
    UNUSED;
    assert(!atomic_exchange(&inside,1));
    *(int32_t *)(object+0x6c)=1024;
    if (recursive) { uint64_t nested[31]={(uintptr_t)object}; kh2_wrap(8,nested); assert((int32_t)nested[0]<0); }
    while (!atomic_load(&release_flush)) usleep(100);
    uint64_t r[31]={(uintptr_t)"save"}; r[19]=(uintptr_t)object;r[23]=png;
    kh2_tail(0x7f00,r);kh2_tail(0x7f01,r);
    atomic_store(&inside,0);
    return *(int32_t *)(object+0x6c);
}
static uint64_t read_body(ARGS) { UNUSED; assert(!atomic_load(&inside)); atomic_store(&reader_done,1);return 9; }
static void *flush_thread(void *p) { (void)p;uint64_t r[31]={(uintptr_t)object}; kh2_wrap(8,r);return NULL; }
static void *read_thread(void *p) { uint64_t r[31]={(uintptr_t)object};kh2_wrap((int)(uintptr_t)p,r);return NULL; }
static uint64_t cleanup_body(ARGS) { UNUSED; pthread_t w;assert(!pthread_create(&w,NULL,flush_thread,NULL));pthread_join(w,NULL);return 0; }
static uint64_t nested_cleanup_body(ARGS) { UNUSED; uint64_t r[31]={(uintptr_t)object};kh2_wrap(2,r);return 0; }
int main(void) {
    alarm(10); g_base=calloc(1,(TEST_STATUS+8));assert(g_base);g_commit=commit_fn;
    g_body[1]=init_body;g_body[2]=cleanup_body;g_body[3]=write_body;g_body[4]=update_body;
    g_body[5]=read_body;g_body[6]=read_body;g_body[7]=read_body;g_body[8]=serializer_body;
    uint64_t r[31]={(uintptr_t)object};kh2_wrap(1,r);
    release_flush=1;memset(r,0,sizeof r);kh2_wrap(3,r);
    assert(commits==1 && !object[0x68] && r[0]==0 && *(int32_t *)(g_base+TEST_STATUS)==73);
    fail_commit=514;kh2_wrap(3,r);
    assert(commits==2 && object[0x68] && *(int32_t *)(g_base+TEST_STATUS)==-1 && r[0]==0);
    fail_commit=0;kh2_wrap(3,r);assert(commits==3 && !object[0x68]);
    png=0;kh2_wrap(3,r);assert(commits==3 && rejects==1 && object[0x68]);
    png=1;recursive=1;r[0]=(uintptr_t)object;kh2_wrap(8,r);
    assert(rejects==2 && object[0x68] && (int32_t)r[0]<0);recursive=0;
    // Both mutators, readers and list must wait until serialization releases.
    for(int id=4;id<=7;id++) {
        reader_done=0;release_flush=0;pthread_t w,q;
        assert(!pthread_create(&w,NULL,flush_thread,NULL));while(!atomic_load(&inside))usleep(100);
        assert(!pthread_create(&q,NULL,read_thread,(void *)(uintptr_t)id));usleep(10000);assert(!reader_done);
        release_flush=1;pthread_join(w,NULL);pthread_join(q,NULL);
    }
    pid_t child=fork();assert(child>=0);
    if(!child){alarm(1);g_body[3]=nested_cleanup_body;uint64_t nested[31]={0};kh2_wrap(3,nested);_exit(0);}
    int status;waitpid(child,&status,0);
    assert(WIFSIGNALED(status)&&WTERMSIG(status)==SIGABRT); // explicit rejection, never lock-across-join deadlock
    r[0]=(uintptr_t)object;kh2_wrap(2,r); // worker join must not hold mutex
    reader_done=0;r[0]=(uintptr_t)object;kh2_wrap(6,r);assert((int32_t)r[0]<0 && !reader_done);
    r[0]=(uintptr_t)object;kh2_wrap(1,r);r[0]=(uintptr_t)object;kh2_wrap(6,r);assert(reader_done);
    free(g_base);puts("PASS per-record sync/error/retry, recursion, common exclusion and cleanup/reinit CPU seams");return 0;
}
