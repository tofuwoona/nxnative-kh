// Original-instruction CPU mechanism fixture. PNG APIs are explicit seams, not
// an encoder; original writer, libpng fwrite/error and SDK fwrite slices run.
#include "../hle_kh2_save.c"
#include "kh_save_test_profile.h"
#include <assert.h>
module_t g_mod[MAX_MOD];int g_nmod=1;
pthread_key_t g_key18,g_keytls,g_keytlr,g_keygate;
unsigned char slice_flag=1;
const char slice_string[]="Write Error";
static unsigned char png[0x500],info[0x100],file[0x100],buffer[1024];
static int locked,locks,unlocks,destroys,closes,writes,inject=1,default_negative;
static int create_error;
int dm_thread_host_wait_begin(void){return 0;}void dm_thread_host_wait_end(int p){(void)p;}
uint32_t dm_fs_reject_save(const char *n,int e){(void)n;(void)e;return 1;}
int dm_guest_as_contains(uintptr_t p){(void)p;return 0;}
extern void dm_kh2_save_gate(uint64_t,uint64_t *);
extern uint64_t slice_wrapped(void *,const char *);
extern void slice_body(void),slice_ret__slice_wrapped(void);
extern void slice_ret_Lcapture_file(void),slice_ret_Lcapture_error(void),slice_ret_Lcapture_png(void),slice_ret_Lcapture_info(void);
extern void slice_ret_Lcapture_handoff(void);
extern void slice_default_write(void *,const void *,size_t);
extern void slice_png_error(void *,const char *);
uint64_t gate_dispatch(uint64_t ret,uint64_t *r){dm_kh2_save_gate(ret,r);return r[0];}
uint64_t unimpl_c(unsigned i,uint64_t *r){(void)i;(void)r;abort();}
void dm_thread_returned(void){abort();}
void slice_unexpected(void){assert(!"unexpected SDK stream mode");abort();}
void slice_default_error(void *p,const char *s){assert(p==png && s==slice_string);assert(!locked && locks==unlocks);abort();}
void slice_noop(void){}
int slice_lock(void *f){assert(f==file && !locked);locked=1;locks++;return 1;}
void slice_unlock(void *f){assert(f==file && locked);locked=0;unlocks++;}
static size_t stream_write(void *f,const void *data,size_t n){
    assert(f==file && data && n==2048 && locked);writes++;
    if(inject){pthread_setspecific(g_key18,(void *)0xdead);return 0;}
    return n;
}
void *slice_open(const char *path,const char *mode){
    assert(path && mode==slice_string);memset(file,0,sizeof file);
    *(void **)(file+0x20)=buffer+sizeof buffer;*(void **)(file+0x28)=buffer;
    *(void **)(file+0x48)=stream_write;return file;
}
void *slice_create(const char *ver,void *error_ptr,void *error_fn,void *warning_fn){
    assert(ver==slice_string && !error_ptr && !warning_fn);assert(error_fn);
    memset(png,0,sizeof png);*(void **)(png+0x140)=default_negative?NULL:error_fn;
    if(create_error)slice_png_error(png,slice_string);
    return png;
}
void *slice_info(void *p){assert(p==png);return info;}
void slice_init_io(void *p,void *f){assert(p==png && f==file);*(void **)(png+0x168)=f;}
void slice_write_end(void *p,void *i){
    assert(p==png && i==info);unsigned char bytes[2048]={0};
    slice_default_write(p,bytes,sizeof bytes);assert(!inject);
}
void slice_destroy(void **p,void **i){
    assert(!locked && *p==png && (!*i || *i==info));
    assert(pthread_getspecific(g_key18)==(void *)0x1818);
    destroys++;*p=NULL;*i=NULL;
}
int slice_close(void *f){assert(f==file && !locked);closes++;return 0;}
int slice_close_status(int r){if(r)slice_flag=0;return slice_flag;}
int main(int argc,char **argv){
    (void)argv;default_negative=argc>1;
    pthread_key_create(&g_key18,NULL);pthread_key_create(&g_keytls,NULL);pthread_key_create(&g_keytlr,NULL);
    pthread_setspecific(g_key18,(void *)0x1818);
    strcpy(g_mod[0].name,"main");strcpy(g_mod[0].build_id,TEST_MAIN_BUILD);
    g_save_module=g_mod;g_ready=1;g_returns[12]=(uintptr_t)slice_ret__slice_wrapped;g_body[9]=(body_fn)(uintptr_t)slice_body;
    g_returns[13]=(uintptr_t)slice_ret_Lcapture_file;g_returns[14]=(uintptr_t)slice_ret_Lcapture_error;
    g_returns[15]=(uintptr_t)slice_ret_Lcapture_png;g_returns[16]=(uintptr_t)slice_ret_Lcapture_info;
    g_returns[17]=(uintptr_t)slice_ret_Lcapture_handoff;
    g_png_destroy=slice_destroy;g_png_close=slice_close;
    g_base=calloc(1,(TEST_PNG_FLAG+8));*(void **)(g_base+TEST_PNG_FLAG)=&slice_flag;
    unsigned char image[0x200]={0};flush_ctx f={.object=image};g_flush=&f;
    assert(slice_wrapped(image,"save:mechanism")==0);
    assert(!locked && locks==1 && unlocks==1 && writes==1 && destroys==1 && closes==1 && !slice_flag && !g_png);
    inject=0;assert(slice_wrapped(image,"save:mechanism")==1);
    assert(!locked && writes==2 && destroys==2 && closes==2 && slice_flag && !g_png);
    create_error=1;assert(slice_wrapped(image,"save:mechanism")==0);
    assert(writes==2 && destroys==3 && closes==3 && !slice_flag && !g_png);
    free(g_base);
    puts("PASS mapped original PNG writer + libpng default write/error + locked SDK fwrite: failure/unlock/cleanup/TLS/full-original-retry and create-error unwind (CPU API seams, not encoder)");
}
