// Real dm_gate + big-stack + PNG nonlocal unwind on a disposable CPU guest stack.
#include "../hle_kh2_save.c"
#include "kh_save_test_profile.h"
#include <assert.h>
#include <stdatomic.h>
#include <sys/mman.h>
#if __has_feature(address_sanitizer)
#include <sanitizer/common_interface_defs.h>
static void *asan_main_fake,*asan_host_fake;
static const void *asan_main_bottom;
static size_t asan_main_size;
#endif
static uintptr_t guest_lo,guest_hi;
static pthread_key_t marker_key;
static void *marker=(void *)0x12345;
module_t g_mod[MAX_MOD];int g_nmod=1;
pthread_key_t g_key18,g_keytls,g_keytlr,g_keygate;
int dm_thread_host_wait_begin(void){return 0;}void dm_thread_host_wait_end(int p){(void)p;}
uint32_t dm_fs_reject_save(const char *n,int e){(void)n;(void)e;return 1;}
int dm_guest_as_contains(uintptr_t p){return p>=guest_lo && p<guest_hi;}
uintptr_t dm_bigstack_top(uintptr_t);
extern void dm_kh2_save_gate(uint64_t,uint64_t *);
extern const unsigned char abi_ret[],abi_body[];
extern int abi_exercise(void *object);
extern int abi_on_stack(void *,uintptr_t top);
extern int abi_nested_big(int x);
extern int abi_png_wrapped(void);
extern _Noreturn void abi_png_error_jump(void *callback,void *png);
extern void *abi_png_captures(void *file,void *png,void *info);
extern const unsigned char abi_png_ret[],abi_png_body[];
extern const unsigned char abi_cap_file_ret[],abi_cap_error_ret[],abi_cap_png_ret[],abi_cap_info_ret[];
static unsigned char png_object[0x180],info_object,file_object,png_flag=1;
static int png_fail=1,png_destroyed,png_closed;
static void destroy_png(void **p,void **i){assert(*p==png_object && *i==&info_object);assert(pthread_getspecific(g_key18)==(void *)0x1818);png_destroyed++;*p=NULL;*i=NULL;}
static int close_png(void *f){assert(f==&file_object);png_closed++;return 0;}
static uintptr_t outer_frame;
int abi_nested_impl(int x){
    uintptr_t frame=(uintptr_t)__builtin_frame_address(0);
    assert(!dm_guest_as_contains(frame) && !dm_bigstack_top(frame));
    assert(frame<outer_frame && outer_frame-frame<65536);
    assert(pthread_getspecific(marker_key)==marker);return x+1;
}
void abi_png_payload(void){
    void *cb=abi_png_captures(&file_object,png_object,&info_object);
    assert(cb && g_png && g_png->armed);
    assert(abi_nested_big(41)==42); // HLE frame must finish BEFORE callback
    if(png_fail){
        pthread_setspecific(g_key18,(void *)0xdead);
        pthread_setspecific(g_keytls,(void *)0xbeef);
        pthread_setspecific(g_keytlr,(void *)0xf00d);
        abi_png_error_jump(cb,png_object); // guest-shaped callee clobbers saved GPR/SIMD/control state
    }
    void *p=png_object,*i=&info_object;destroy_png(&p,&i);close_png(&file_object);
}
static uint32_t commit(const char *n){assert(!strcmp(n,"save"));return 0;}
void abi_guest_payload(unsigned char *o){
#if __has_feature(address_sanitizer)
    __sanitizer_finish_switch_fiber(NULL,&asan_main_bottom,&asan_main_size);
#endif
    outer_frame=(uintptr_t)__builtin_frame_address(0);
    assert(!dm_guest_as_contains(outer_frame));assert(pthread_getspecific(marker_key)==marker);
    assert(abi_nested_big(41)==42);
    assert(abi_png_wrapped()==0); // nested real dm_gate -> callback -> Darwin longjmp
    assert(!png_flag && png_destroyed==1 && png_closed==1 && !g_png);
    assert(pthread_getspecific(g_key18)==(void *)0x1818);
    assert(pthread_getspecific(g_keytls)==(void *)0xeeee);
    assert(pthread_getspecific(g_keytlr)==(void *)0xffff);
    png_fail=0;png_flag=1;
    assert(abi_png_wrapped()==1 && png_destroyed==2 && png_closed==2 && !g_png);
    *(int32_t *)(o+0x6c)=1024;
    uint64_t r[31]={(uintptr_t)"save"};r[19]=(uintptr_t)o;r[23]=1;
    kh2_tail(0x7f00,r);kh2_tail(0x7f01,r);
#if __has_feature(address_sanitizer)
    __sanitizer_start_switch_fiber(&asan_host_fake,asan_main_bottom,asan_main_size);
#endif
}
uint64_t gate_dispatch(uint64_t ret,uint64_t *r){dm_kh2_save_gate(ret,r);return r[0];}
uint64_t unimpl_c(unsigned idx,uint64_t *r){(void)idx;(void)r;abort();}
void dm_thread_returned(void){abort();}
int main(void){
    assert(!pthread_key_create(&marker_key,NULL));pthread_setspecific(marker_key,marker);
    pthread_key_create(&g_key18,NULL);pthread_key_create(&g_keytls,NULL);pthread_key_create(&g_keytlr,NULL);
    pthread_setspecific(g_key18,(void *)0x1818);pthread_setspecific(g_keytls,(void *)0xeeee);pthread_setspecific(g_keytlr,(void *)0xffff);
    strcpy(g_mod[0].name,"main");strcpy(g_mod[0].build_id,TEST_MAIN_BUILD);
    g_save_module=g_mod;g_ready=1;g_returns[8]=(uintptr_t)abi_ret;g_body[8]=(body_fn)(uintptr_t)abi_body;g_commit=commit;
    g_returns[12]=(uintptr_t)abi_png_ret;g_body[9]=(body_fn)(uintptr_t)abi_png_body;
    g_returns[13]=(uintptr_t)abi_cap_file_ret;g_returns[14]=(uintptr_t)abi_cap_error_ret;
    g_returns[15]=(uintptr_t)abi_cap_png_ret;g_returns[16]=(uintptr_t)abi_cap_info_ret;
    g_png_destroy=destroy_png;g_png_close=close_png;
    g_base=calloc(1,(TEST_PNG_FLAG+8));*(void **)(g_base+TEST_PNG_FLAG)=&png_flag;
    unsigned char object[0x1b0]={0};cache_state *s=state_for(object,1);s->active=1;
    void *stack=mmap(NULL,65536,PROT_READ|PROT_WRITE,MAP_ANON|MAP_PRIVATE,-1,0);assert(stack!=MAP_FAILED);
    guest_lo=(uintptr_t)stack;guest_hi=guest_lo+65536;
#if __has_feature(address_sanitizer)
    // Describe the real big-stack destination to ASan; guest stack transit is
    // assembly only. Otherwise longjmp's ASan interceptor mistakes it for the
    // default pthread stack and emits sanitizer issue #189's warning.
    uintptr_t host_top=dm_bigstack_top(guest_lo);
    __sanitizer_start_switch_fiber(&asan_main_fake,(void *)(host_top-(512u<<10)),512u<<10);
#endif
    assert(abi_on_stack(object,guest_hi)==1);
#if __has_feature(address_sanitizer)
    __sanitizer_finish_switch_fiber(asan_main_fake,NULL,NULL);
#endif
    assert(!object[0x68] && *(int32_t *)(object+0x6c)==1024);
    free(g_base);munmap(stack,65536);pthread_key_delete(marker_key);
    puts("PASS real gate GPR/SIMD preservation, nested big-stack PNG error unwind/cleanup/retry, virtual x18/TLS/TLR restoration");return 0;
}
