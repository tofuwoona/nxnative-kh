// Bounded opt-in host-Metal lifetime test of the actual map/free handlers.
#include HLE_VK_SOURCE
#include <assert.h>
int dm_guest_as_contains(uintptr_t p) { (void)p; return 0; }
void *front_metal_layer(void) { return NULL; }
module_t *module_of(const void *p) { (void)p; return NULL; }
module_t g_mod[MAX_MOD]; int g_nmod;
void svc_thread_dump(void) {}
uint64_t now_ns(void) { return clock_gettime_nsec_np(CLOCK_UPTIME_RAW); }
void dm_vi_layer_crop(int c[4]) { memset(c,0,4*sizeof(int)); }
int dm_opmode(void) { return 1; }
void dm_gfx_enter(void) {}
void dm_gfx_leave(void) {}
static unsigned checks,failed;
#define C(x) do { checks++; if (!(x)) { failed++; fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); } } while(0)
static __weak id<MTLBuffer> weak_buffer;
__attribute__((noinline)) static VkDeviceMemory allocate(size_t n,unsigned type) {
    VkMemoryAllocateInfo a={.allocationSize=n,.memoryTypeIndex=type}; VkDeviceMemory m=NULL;
    C(h_vkAllocateMemory(&g_device,&a,NULL,&m)==VK_SUCCESS); return m;
}
__attribute__((noinline)) static void map_use(VkDeviceMemory m) {
    void *base=NULL,*offset=NULL;
    C(h_vkMapMemory(&g_device,m,0,VK_WHOLE_SIZE,0,&base)==VK_SUCCESS && base);
    C(h_vkMapMemory(&g_device,m,7,16,0,&offset)==VK_SUCCESS && offset==(unsigned char *)base+7);
    // Both contents' temporary pools have popped; valid m->buf must keep these real bytes alive.
    ((unsigned char *)offset)[0]=0x5a; ((unsigned char *)base)[m->size-1]=0x6b;
    C(((unsigned char *)offset)[0]==0x5a && ((unsigned char *)base)[m->size-1]==0x6b);
    h_vkUnmapMemory(&g_device,m); void *again=NULL;
    C(h_vkMapMemory(&g_device,m,7,16,0,&again)==VK_SUCCESS && again==offset);
    C(((unsigned char *)again)[0]==0x5a);
}
__attribute__((noinline)) static void lifetime(size_t n,unsigned type,int mode) {
    VkDeviceMemory m=allocate(n,type); VkBuffer b=NULL;
    VkBufferCreateInfo bc={.size=n,.usage=VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT};
    if(mode==1 || mode==2) { C(h_vkCreateBuffer(&g_device,&bc,NULL,&b)==VK_SUCCESS); C(h_vkBindBufferMemory(&g_device,b,m,0)==VK_SUCCESS); }
    if(mode!=1) map_use(m);
    if(mode==3) { C(h_vkCreateBuffer(&g_device,&bc,NULL,&b)==VK_SUCCESS); C(h_vkBindBufferMemory(&g_device,b,m,0)==VK_SUCCESS); }
    weak_buffer=m->buf; C(weak_buffer!=nil);
    if(b) h_vkDestroyBuffer(&g_device,b,NULL);
    h_vkFreeMemory(&g_device,m,NULL);
}
int main(int argc,char **argv) {
    (void)argc; (void)argv; const int pool=1;
    @autoreleasepool {
        g_dev=MTLCreateSystemDefaultDevice(); C(g_dev!=nil);
        const size_t sizes[]={4096,4194304};
        for(unsigned type=1;type<=2;type++) for(unsigned n=0;n<2;n++) for(int mode=0;mode<4;mode++) {
            @autoreleasepool { lifetime(sizes[n],type,mode); C((weak_buffer!=nil)==(mode==1?0:!pool)); }
            C(weak_buffer==nil);
        }
        VkDeviceMemory retained=allocate(4096,1);
        @autoreleasepool { map_use(retained); weak_buffer=retained->buf; }
        C(weak_buffer!=nil); // Negative control: a pool must not release an unfreed wrapper's storage.
        @autoreleasepool { h_vkFreeMemory(&g_device,retained,NULL); }
        C(weak_buffer==nil); C(g_mem_bytes==0); g_dev=nil;
    }
    printf("real-Metal map lifetime: pool=%d checks=%u failed=%u\n",pool,checks,failed);
    return failed?1:0;
}
