// Execute original instruction slices with production repair bytes and tail policy.
#define main retained_original_main
#include "t_kh2_failure_boundary.c"
#undef main
#include "../hle_kh2_save.c"
#include <assert.h>
module_t g_mod[MAX_MOD]; int g_nmod;
pthread_key_t g_key18,g_keytls,g_keytlr,g_keygate;
int dm_thread_host_wait_begin(void){return 0;}void dm_thread_host_wait_end(int n){(void)n;}
static int rejected, published;
uint32_t dm_fs_reject_save(const char *n,int e){assert(!strcmp(n,"save")&&e);rejected++;return 0x2a2;}
static uint32_t original_commit_seam(const char *n){assert(!strcmp(n,"save"));published++;return commit_result;}
uint32_t repair_commit(void *object,uint64_t png){uint64_t r[31]={(uintptr_t)"save"};r[19]=(uintptr_t)object;r[23]=png;kh2_tail(0x7f00,r);return r[0];}
uint32_t repair_finish(void *object,uint64_t result){uint64_t r[31]={result};r[19]=(uintptr_t)object;kh2_tail(0x7f01,r);return r[0];}
uint32_t repair_close(void *flag,uint64_t result){uint64_t r[31]={result};r[23]=(uintptr_t)flag;kh2_tail(0x7f02,r);return r[0];}
int main(void){
    g_commit=original_commit_seam;
    for(int mode=0;mode<3;mode++){
        unsigned char buffer[32]={0};struct cache c={.buffer=buffer,.dirty=1,.length=1024};
        flush_ctx f={.object=(void *)&c};g_flush=&f;
        int png=mode!=1;commit_result=mode==2?514:0;
        inverse_entries=0;inverse_body_reached=0;
        int32_t result=probe_serializer_tail(&c,png);
        assert(inverse_entries==1 && inverse_length==1024 && inverse_body_reached==1);
        assert(f.finished && f.success==(mode==0));
        assert(c.dirty==(mode!=0) && result==(mode==0?1024:-1));
        printf("PASS repaired original tail png=%d commit=%u inverse_length=%d dirty=%d result=%d\n",png,commit_result,inverse_length,c.dirty,result);
    }
    assert(rejected==1 && published==2);
    FILE *f=funopen(NULL,NULL,failing_write,NULL,close_ok);assert(f);
    assert(!setvbuf(f,NULL,_IOFBF,4096));assert(fputs("not a game PNG",f)>=0);
    unsigned char flag=1;int result=probe_writer_close(f,&flag);
    assert(close_result==EOF && io_failures && !result && !flag);
    puts("PASS real buffered fclose failure reaches repaired PNG status; original inverse guard reached on PNG failure");return 0;
}
