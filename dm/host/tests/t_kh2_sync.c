// CPU mechanism tests: production tail policy; NOT guest PNG/gameplay validation.
#include "../dm.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#if __has_include("../hle_kh2_save.c")
#include "../hle_kh2_save.c"
#else
static void kh2_tail(int num, uint64_t *r) { (void)num; (void)r; }
#endif
static int commits, rejects;
uint32_t dm_fs_reject_save(const char *name, int error) { assert(!strcmp(name,"save")); assert(error); rejects++; return 0x2a2; }
int dm_thread_host_wait_begin(void) { return 0; }
void dm_thread_host_wait_end(int old) { (void)old; }
module_t g_mod[MAX_MOD]; int g_nmod;
pthread_key_t g_key18,g_keytls,g_keytlr,g_keygate;
static uint32_t commit_result;
static uint32_t original_commit(const char *name) { assert(!strcmp(name,"save")); commits++; return commit_result; }
int main(void) {
    unsigned char object[0x1b0] = {0};
    uint64_t r[31] = {0};
    r[19] = (uintptr_t)object; r[23] = 0;
    object[0x68] = 1; *(int32_t *)(object+0x6c) = 1024;
#if __has_include("../hle_kh2_save.c")
    g_commit = original_commit;
    flush_ctx ctx = {.object=object}; g_flush=&ctx;
#endif
    r[0] = (uintptr_t)"save";
    kh2_tail(0x7f00, r);
    assert(rejects == 1 && commits == 0 && r[0]);
    kh2_tail(0x7f01, r);
    assert(object[0x68] == 1 && *(int32_t *)(object+0x6c) == -1);
#if __has_include("../hle_kh2_save.c")
    assert(ctx.finished && !ctx.success);
    memset(&ctx,0,sizeof ctx); ctx.object=object;
#endif
    r[23]=1; r[0]=(uintptr_t)"save"; commit_result=514;
    *(int32_t *)(object+0x6c)=1024;
    kh2_tail(0x7f00,r); kh2_tail(0x7f01,r);
    assert(commits==1 && object[0x68]==1 && *(int32_t *)(object+0x6c)==-1);
#if __has_include("../hle_kh2_save.c")
    memset(&ctx,0,sizeof ctx); ctx.object=object;
#endif
    r[0]=(uintptr_t)"save"; commit_result=0;
    *(int32_t *)(object+0x6c)=1024;
    kh2_tail(0x7f00,r); kh2_tail(0x7f01,r);
    assert(commits==2 && !object[0x68] && *(int32_t *)(object+0x6c)==1024);
    unsigned char flag=1; r[23]=(uintptr_t)&flag; r[0]=(uint32_t)-1;
    kh2_tail(0x7f02,r); assert(!flag && !r[0]);
    flag=1; r[0]=0; kh2_tail(0x7f02,r); assert(flag && r[0]==1);
    puts("PASS production PNG/Commit/fclose policy (CPU seams only)");
    return 0;
}
