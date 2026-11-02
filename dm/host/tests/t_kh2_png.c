// CPU production-boundary seam. No replacement encoder, game or module rewrite.
#include "../hle_kh2_save.c"
#include "kh_save_test_profile.h"
#include <assert.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>
module_t g_mod[MAX_MOD]; int g_nmod;
pthread_key_t g_key18,g_keytls,g_keytlr,g_keygate;
int dm_thread_host_wait_begin(void){return 0;}
void dm_thread_host_wait_end(int p){(void)p;}
uint32_t dm_fs_reject_save(const char *n,int e){(void)n;(void)e;return 1;}
static int destroyed,closed,fail=1;
static unsigned char flag=1;
static void *callback;
static unsigned char png_token,info_token,file_token;
static void destroy(void **png,void **info){assert(*png==&png_token);assert(*info==&info_token);destroyed++;*png=NULL;*info=NULL;}
static int close_file(void *f){
    assert(f==&file_token);closed++;
    if(fail){pthread_setspecific(g_key18,(void *)0xcccc);pthread_setspecific(g_keytls,(void *)0xdddd);pthread_setspecific(g_keytlr,(void *)0xeeee);}
    return 0;
}
static uint64_t writer(uint64_t a,uint64_t b,uint64_t c,uint64_t d,uint64_t e,uint64_t f,uint64_t g,uint64_t h){
    (void)a;(void)b;(void)c;(void)d;(void)e;(void)f;(void)g;(void)h;
#ifdef DM_KH2_PNG_BOUNDARY
    uint64_t r[31]={(uintptr_t)&file_token};kh2_png_capture(0x7f03,r);assert(r[19]==r[0]);
    kh2_png_capture(0x7f04,r);callback=(void *)(uintptr_t)r[2];assert(callback);
    r[0]=(uintptr_t)&png_token;kh2_png_capture(0x7f05,r);assert(r[21]==r[0]);
    r[0]=(uintptr_t)&info_token;kh2_png_capture(0x7f06,r);assert(r[22]==r[0]);
#endif
    if(fail){
        pthread_setspecific(g_key18,(void *)0xdead); // guest callee changed virtual x18
        if(callback)((void (*)(void *,const char *))callback)(&png_token,"Write Error");
        abort(); // original default PNG handler: must NOT be reached
    }
#ifdef DM_KH2_PNG_BOUNDARY
    r[29]=0x12340;kh2_png_capture(0x7f07,r);
    assert(r[0]==0x12358 && !g_png->armed && !g_png->png && !g_png->info && !g_png->file);
#endif
    void *p=&png_token,*i=&info_token;destroy(&p,&i);close_file(&file_token);return 1;
}
static void trial(void){
    pthread_key_create(&g_key18,NULL);pthread_key_create(&g_keytls,NULL);pthread_key_create(&g_keytlr,NULL);pthread_key_create(&g_keygate,NULL);
    pthread_setspecific(g_key18,(void *)0x1234);
    unsigned char *base=calloc(1,(TEST_PNG_FLAG+8));g_base=base;*(void **)(base+TEST_PNG_FLAG)=&flag;
    flush_ctx flush={0};g_flush=&flush;
    uint64_t r[31]={0};
#ifdef DM_KH2_PNG_BOUNDARY
    g_body[9]=writer;g_png_destroy=destroy;g_png_close=close_file;
    r[0]=kh2_png_original(r);
#else
    r[0]=writer(0,0,0,0,0,0,0,0); // baseline original writer has no error boundary
#endif
    assert(r[0]==0 && !flag && destroyed==1 && closed==1);
    assert(pthread_getspecific(g_key18)==(void *)0x1234);
    assert(!pthread_getspecific(g_keytls) && !pthread_getspecific(g_keytlr));
    fail=0;flag=1;
#ifdef DM_KH2_PNG_BOUNDARY
    assert(kh2_png_original(r)==1);
#endif
    assert(destroyed==2 && closed==2 && flag==1);
    free(base);
}
int main(void){
    pid_t p=fork();assert(p>=0);if(!p){trial();_exit(0);}int status;waitpid(p,&status,0);
    assert(WIFEXITED(status)&&WEXITSTATUS(status)==0 && "immediate PNG failure must return 0, clean up and allow full retry");
#ifdef DM_KH2_PNG_BOUNDARY
    // New sites must execute the exact original MOV/ADD behavior outside an
    // owned flush; they must not install a host callback into another caller.
    uint64_t r[31]={0x5678};r[29]=0x12340;
    kh2_png_capture(0x7f03,r);assert(r[19]==0x5678);
    kh2_png_capture(0x7f04,r);assert(!r[2]);
    kh2_png_capture(0x7f05,r);assert(r[21]==0x5678);
    kh2_png_capture(0x7f06,r);assert(r[22]==0x5678);
    kh2_png_capture(0x7f07,r);assert(r[0]==0x12358);
    for(int mode=0;mode<6;mode++){
        p=fork();assert(p>=0);
        if(!p){
            flush_ctx f={0},other={0};png_ctx c={.armed=1,.flush=&f,.png=&png_token};
            g_flush=&f;g_png=mode==0?NULL:&c;
            if(mode==1)c.armed=0; // cleanup/repeated error may never jump twice
            if(mode==2)c.png=&info_token;
            if(mode==3)c.flush=&other;
            if(mode==4){kh2_png_original(r);_exit(99);} // no nested original writer
            if(mode==5){c.armed=0;kh2_png_capture(0x7f03,r);_exit(99);}
            png_error_return(&png_token,"Write Error");_exit(99);
        }
        waitpid(p,&status,0);assert(WIFSIGNALED(status)&&WTERMSIG(status)==SIGABRT);
    }
#endif
    puts("PASS PNG immediate-error original-writer boundary, cleanup, virtual x18 and retry (CPU seams)");
}
