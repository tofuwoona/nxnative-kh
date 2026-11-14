// Actual Vulkan handlers with heap-backed fake Metal objects; no Metal device.
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
static unsigned checks,failures,created,freed;
#define C(x) do { checks++; if (!(x)) { failures++; fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); } } while(0)
@interface ReviewAlias : NSObject
@property(nonatomic,strong) id buffer;
@end
@implementation ReviewAlias
@end
@interface ReviewBuffer : NSObject { void *_storage; NSUInteger _length; }
- (instancetype)initWithLength:(NSUInteger)n;
- (void *)contents;
- (NSUInteger)length;
- (id)newTextureWithDescriptor:(MTLTextureDescriptor *)d offset:(NSUInteger)o bytesPerRow:(NSUInteger)r;
@property(nonatomic,copy) NSString *label;
@end
@implementation ReviewBuffer
- (instancetype)initWithLength:(NSUInteger)n { if ((self=[super init])) { _length=n; _storage=calloc(n,1); assert(_storage); created++; } return self; }
- (void *)contents { return _storage; }
- (NSUInteger)length { return _length; }
- (void)dealloc { memset(_storage,0xdd,_length); free(_storage); freed++; }
- (id)newTextureWithDescriptor:(MTLTextureDescriptor *)d offset:(NSUInteger)o bytesPerRow:(NSUInteger)r { (void)d; (void)o; (void)r; ReviewAlias *a=[ReviewAlias new]; a.buffer=self; return a; }
@end
@interface ReviewDevice : NSObject
@property(nonatomic) BOOL fail;
@end
@implementation ReviewDevice
- (id)newBufferWithLength:(NSUInteger)n options:(NSUInteger)o { (void)o; return self.fail ? nil : [[ReviewBuffer alloc] initWithLength:n]; }
@end
static __weak id observed;
static VkDeviceMemory alloc_mem(size_t n, unsigned type) {
    VkMemoryAllocateInfo a={.allocationSize=n,.memoryTypeIndex=type}; VkDeviceMemory m=NULL;
    C(h_vkAllocateMemory(&g_device,&a,NULL,&m)==VK_SUCCESS && m); return m;
}
static VkBuffer buffer(VkDeviceMemory m,size_t off) {
    VkBufferCreateInfo c={.size=m->size>off ? m->size-off : 1,.usage=VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT}; VkBuffer b=NULL;
    C(h_vkCreateBuffer(&g_device,&c,NULL,&b)==VK_SUCCESS);
    C(h_vkBindBufferMemory(&g_device,b,m,off)==VK_SUCCESS); return b;
}
__attribute__((noinline)) static void ordinary(size_t n,unsigned type,int mode) {
    VkDeviceMemory m=alloc_mem(n,type); VkBuffer b=NULL;
    if(mode==1 || mode==2) b=buffer(m,0);
    if(mode!=1) {
        void *p=NULL,*again=NULL; size_t off=n>8?7:0;
        C(h_vkMapMemory(&g_device,m,off,VK_WHOLE_SIZE,0,&p)==VK_SUCCESS && p);
        observed=m->buf; C(observed!=nil);
        // Own heap backing, not immortal static fake storage. Must survive map-pool pop.
        ((unsigned char *)p)[0]=0x5a;
        C(((unsigned char *)p)[0]==0x5a);
        uintptr_t raw=(uintptr_t)atomic_load(&m->raw); C(raw!=0);
        h_vkUnmapMemory(&g_device,m);
        C(h_vkMapMemory(&g_device,m,off,1,0,&again)==VK_SUCCESS && again==p);
        C((uintptr_t)atomic_load(&m->raw)==raw && ((unsigned char *)again)[0]==0x5a);
        if(mode==3) b=buffer(m,0); // map first, bind after pool pop
        C(m->buf!=nil);
    } else observed=m->buf;
    if(b) h_vkDestroyBuffer(&g_device,b,NULL);
    h_vkFreeMemory(&g_device,m,NULL);
}
__attribute__((noinline)) static void alias_buffers(void) {
    VkDeviceMemory m=alloc_mem(4096,1); void *p=NULL;
    C(h_vkMapMemory(&g_device,m,7,16,0,&p)==VK_SUCCESS);
    observed=m->buf; uintptr_t raw=(uintptr_t)atomic_load(&m->raw);
    VkBuffer a=buffer(m,256),b=buffer(m,512);
    C(a->mem==m && b->mem==m && a->off==256 && b->off==512);
    C((uintptr_t)atomic_load(&m->raw)==raw);
    h_vkDestroyBuffer(&g_device,a,NULL); ((unsigned char *)p)[0]=0xa5;
    C(m->buf && ((unsigned char *)p)[0]==0xa5);
    h_vkDestroyBuffer(&g_device,b,NULL); h_vkFreeMemory(&g_device,m,NULL);
}
__attribute__((noinline)) static void failure_retry(ReviewDevice *device) {
    VkDeviceMemory m=alloc_mem(4096,2); void *p=(void *)0x1234;
    device.fail=YES;
    C(h_vkMapMemory(&g_device,m,0,16,0,&p)==VK_ERROR_MEMORY_MAP_FAILED);
    C(p==(void *)0x1234 && !m->buf && !atomic_load(&m->raw));
    device.fail=NO;
    C(h_vkMapMemory(&g_device,m,0,16,0,&p)==VK_SUCCESS && p!=(void *)0x1234);
    ((unsigned char *)p)[0]=0x67; C(((unsigned char *)p)[0]==0x67);
    h_vkFreeMemory(&g_device,m,NULL);
}
static VkDescriptorSetLayout layout(void) {
    VkDescriptorSetLayoutBinding b={.binding=0,.descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,.descriptorCount=1,.stageFlags=VK_SHADER_STAGE_FRAGMENT_BIT};
    VkDescriptorSetLayoutCreateInfo c={.bindingCount=1,.pBindings=&b}; VkDescriptorSetLayout l;
    C(h_vkCreateDescriptorSetLayout(&g_device,&c,NULL,&l)==VK_SUCCESS); return l;
}
static void write_descriptor(VkDescriptorSet s,VkBuffer b) {
    VkDescriptorBufferInfo i={.buffer=b,.offset=64,.range=16};
    VkWriteDescriptorSet w={.dstSet=s,.dstBinding=0,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,.pBufferInfo=&i};
    h_vkUpdateDescriptorSets(&g_device,1,&w,0,NULL);
}
__attribute__((noinline)) static void descriptor_populate(VkDescriptorSet *s) {
    VkDeviceMemory m=alloc_mem(4096,1); void *p;
    C(h_vkMapMemory(&g_device,m,7,16,0,&p)==VK_SUCCESS); ((unsigned char *)p)[0]=0x89;
    VkBuffer b=buffer(m,256); observed=m->buf;
    write_descriptor(s[0],b); C(s[0]->d[0].buf==m->buf && s[0]->d[0].off==320);
    VkCopyDescriptorSet cp={.srcSet=s[0],.dstSet=s[1],.descriptorCount=1};
    h_vkUpdateDescriptorSets(&g_device,0,NULL,1,&cp);
    C(s[0]->d[0].buf==s[1]->d[0].buf);
    h_vkDestroyBuffer(&g_device,b,NULL); h_vkFreeMemory(&g_device,m,NULL);
}
static void descriptors(void) {
    VkDescriptorSetLayout l=layout(); VkDescriptorPool pool; VkDescriptorPoolCreateInfo pc={.maxSets=2};
    C(h_vkCreateDescriptorPool(&g_device,&pc,NULL,&pool)==VK_SUCCESS);
    VkDescriptorSetLayout ls[2]={l,l}; VkDescriptorSet s[2];
    VkDescriptorSetAllocateInfo ai={.descriptorPool=pool,.descriptorSetCount=2,.pSetLayouts=ls};
    C(h_vkAllocateDescriptorSets(&g_device,&ai,s)==VK_SUCCESS);
    @autoreleasepool { descriptor_populate(s); }
    C(observed!=nil && s[0]->d[0].buf!=nil && s[1]->d[0].buf!=nil);
    @autoreleasepool { write_descriptor(s[0],NULL); }
    C(observed!=nil && !s[0]->d[0].buf && s[1]->d[0].buf!=nil);
    @autoreleasepool { h_vkFreeDescriptorSets(&g_device,pool,1,&s[1]); }
    C(observed==nil);
    @autoreleasepool { descriptor_populate((VkDescriptorSet[]){s[0],s[0]}); }
    C(observed!=nil);
    @autoreleasepool { C(h_vkResetDescriptorPool(&g_device,pool,0)==VK_SUCCESS); }
    C(observed==nil && pool->sets==NULL);
    h_vkDestroyDescriptorPool(&g_device,pool,NULL);
    // Production intentionally keeps layouts alive; release fixture-owned l only after all sets are gone.
    free(l->imm); free(l);
}
__attribute__((noinline)) static VkBufferView texture_view(void) {
    VkDeviceMemory m=alloc_mem(4096,1); void *p;
    C(h_vkMapMemory(&g_device,m,0,16,0,&p)==VK_SUCCESS); ((unsigned char *)p)[0]=0x77;
    VkBuffer b=buffer(m,0); observed=m->buf;
    VkBufferViewCreateInfo vc={.buffer=b,.format=VK_FORMAT_R8G8B8A8_UNORM,.range=256}; VkBufferView v;
    C(h_vkCreateBufferView(&g_device,&vc,NULL,&v)==VK_SUCCESS && bview_tex(v)!=nil);
    // Returning a view here tests the host alias owner only; no guest use after free.
    h_vkDestroyBuffer(&g_device,b,NULL); h_vkFreeMemory(&g_device,m,NULL); return v;
}
static void textures(void) {
    VkBufferView v; @autoreleasepool { v=texture_view(); }
    C(observed!=nil && v->tex!=nil);
    @autoreleasepool { h_vkDestroyBufferView(&g_device,v,NULL); }
    C(observed==nil);
}
// Linear-image constructor metadata is supplied at this seam; binding and release
// are the production handlers. The fake texture owns fake heap backing, not GPU data.
static void linear_after_map(void) {
    VkImage im=zalloc(sizeof *im); im->f=fmt_of(VK_FORMAT_R8G8B8A8_UNORM);
    im->fmt=VK_FORMAT_R8G8B8A8_UNORM; im->w=im->h=4; im->pitch=256;
    VkDeviceMemory m=alloc_mem(4096,1); void *p=NULL;
    @autoreleasepool {
        C(h_vkMapMemory(&g_device,m,0,16,0,&p)==VK_SUCCESS); observed=m->buf;
        ((unsigned char *)p)[0]=0x4b;
        C(h_vkBindImageMemory(&g_device,im,m,0)==VK_SUCCESS && im->tex!=nil);
        C(((unsigned char *)p)[0]==0x4b); h_vkFreeMemory(&g_device,m,NULL);
    }
    C(observed!=nil); // The alias, not an outer map autorelease, owns the buffer.
    @autoreleasepool { h_vkDestroyImage(&g_device,im,NULL); }
    C(observed==nil);
}
static void texel_descriptor_after_map(void) {
    VkDescriptorSetLayoutBinding binding={.binding=0,.descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_TEXEL_BUFFER,.descriptorCount=1,.stageFlags=VK_SHADER_STAGE_FRAGMENT_BIT};
    VkDescriptorSetLayoutCreateInfo lc={.bindingCount=1,.pBindings=&binding}; VkDescriptorSetLayout l=NULL;
    C(h_vkCreateDescriptorSetLayout(&g_device,&lc,NULL,&l)==VK_SUCCESS);
    VkDescriptorPool pool=NULL; VkDescriptorPoolCreateInfo pc={.maxSets=1};
    C(h_vkCreateDescriptorPool(&g_device,&pc,NULL,&pool)==VK_SUCCESS);
    VkDescriptorSetAllocateInfo ai={.descriptorPool=pool,.descriptorSetCount=1,.pSetLayouts=&l}; VkDescriptorSet s=NULL;
    C(h_vkAllocateDescriptorSets(&g_device,&ai,&s)==VK_SUCCESS);
    @autoreleasepool {
        VkDeviceMemory m=alloc_mem(4096,1); void *p=NULL;
        C(h_vkMapMemory(&g_device,m,0,16,0,&p)==VK_SUCCESS); observed=m->buf;
        VkBuffer b=buffer(m,0); VkBufferView v=NULL;
        VkBufferViewCreateInfo vc={.buffer=b,.format=VK_FORMAT_R8G8B8A8_UNORM,.range=256};
        C(h_vkCreateBufferView(&g_device,&vc,NULL,&v)==VK_SUCCESS);
        VkWriteDescriptorSet w={.dstSet=s,.dstBinding=0,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_TEXEL_BUFFER,.pTexelBufferView=&v};
        h_vkUpdateDescriptorSets(&g_device,1,&w,0,NULL); C(s->d[0].tex!=nil);
        h_vkDestroyBufferView(&g_device,v,NULL);
        h_vkDestroyBuffer(&g_device,b,NULL); h_vkFreeMemory(&g_device,m,NULL);
    }
    C(observed!=nil && s->d[0].tex!=nil);
    @autoreleasepool { C(h_vkResetDescriptorPool(&g_device,pool,0)==VK_SUCCESS); }
    C(observed==nil); h_vkDestroyDescriptorPool(&g_device,pool,NULL); free(l->imm); free(l);
}
static void cache_control(void) {
    if(DM_GAME_PROGRAM_ID!=DM_KH2_PROGRAM_ID) return;
    VkDeviceMemory m=alloc_mem(921600,1); void *p; __weak id w;
    @autoreleasepool {
        C(h_vkMapMemory(&g_device,m,0,16,0,&p)==VK_SUCCESS); w=m->buf;
        h_vkFreeMemory(&g_device,m,NULL);
    }
    C(w!=nil);
    VkDeviceMemory next=alloc_mem(921600,1);
    @autoreleasepool {
        C(h_vkMapMemory(&g_device,next,0,16,0,&p)==VK_SUCCESS && next->buf==w);
        h_vkFreeMemory(&g_device,next,NULL);
    }
    C(w!=nil);
    // Deliberately drain fixture-owned static cache only after checking production retention/reuse.
    for(int i=0;i<MOVIE_CACHE_SLOTS;i++) { if(g_movie_cache_buffers[i]) g_mem_bytes-=g_movie_cache_slots[i].size; g_movie_cache_buffers[i]=nil; memset(&g_movie_cache_slots[i],0,sizeof(g_movie_cache_slots[i])); }
    C(w==nil);
}
int main(int argc,char **argv) {
    (void)argc; (void)argv; const int pool=1;
    @autoreleasepool {
        ReviewDevice *device=[ReviewDevice new]; g_dev=(id<MTLDevice>)(id)device;
        const size_t sizes[]={16,4096,4194304};
        for(unsigned type=1;type<=2;type++) for(unsigned n=0;n<3;n++) for(int mode=0;mode<4;mode++) {
            @autoreleasepool { ordinary(sizes[n],type,mode); C((observed!=nil)==(mode==1?0:!pool)); }
            C(observed==nil);
        }
        @autoreleasepool { alias_buffers(); C((observed!=nil)==!pool); }
        C(observed==nil);
        @autoreleasepool { failure_retry(device); }
        descriptors(); textures(); linear_after_map(); texel_descriptor_after_map(); cache_control();
        C(created==freed); C(g_mem_bytes==0); g_dev=nil;
    }
    printf("map-pool CPU: profile=%s pool=%d checks=%u failed=%u buffers=%u freed=%u\n",DM_GAME_ID,pool,checks,failures,created,freed);
    return failures?1:0;
}
