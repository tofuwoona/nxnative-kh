// Executable fixture: compile the production Vulkan-to-Metal implementation in
// this translation unit, so the recorded commands really pass through replay().
#define DM_GAME_PROGRAM_ID 0x010090C022978003ull
#include "../hle_vk.m"
#include <assert.h>

static void depth_stencil_case(id<MTLDevice> dev, id<MTLCommandQueue> queue);

int main(void) {
    @autoreleasepool {
        if (!getenv("DM_VK_COALESCE_PASSES")) setenv("DM_VK_COALESCE_PASSES", "1", 1);
        g_dev = MTLCreateSystemDefaultDevice();
        assert(g_dev);
        g_dss_off = [g_dev newDepthStencilStateWithDescriptor:[MTLDepthStencilDescriptor new]];
        assert(g_dss_off);
        id<MTLCommandQueue> queue = [g_dev newCommandQueue];
        assert(queue);
        struct VkImageView_T color_view = {0};
        MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:4 height:4 mipmapped:NO];
        td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        td.storageMode = MTLStorageModePrivate;
        color_view.tex = [g_dev newTextureWithDescriptor:td];
        assert(color_view.tex);
        struct VkFramebuffer_T fb = {.n=1,.w=4,.h=4,.layers=1,.v={&color_view}};
        struct VkRenderPass_T rp = {.natt=1,.ncol=1,.col={0},.res={-1},.depth=-1};
        rp.att[0] = (ratt){.fmt=VK_FORMAT_R8G8B8A8_UNORM,.load=VK_ATTACHMENT_LOAD_OP_LOAD,.store=VK_ATTACHMENT_STORE_OP_STORE};
        VkRenderPassBeginInfo bi = {.sType=VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO,.renderPass=&rp,.framebuffer=&fb,
            .renderArea={{0,0},{4,4}}};
        // Shader draws make the merged pass observable through GPU readback.
        NSError *error = nil;
        id<MTLLibrary> lib = [g_dev newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal;\nvertex float4 v(uint id [[vertex_id]]) { float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)}; return float4(p[id],0,1); }\nfragment float4 green() {return float4(0,1,0,1);}\nfragment float4 red() {return float4(1,0,0,1);}\n" options:nil error:&error];
        assert(lib && !error);
        struct VkPipeline_T pipelines[2] = {{0}};
        for (int i=0;i<2;i++) {
            MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
            pd.vertexFunction = [lib newFunctionWithName:@"v"];
            pd.fragmentFunction = [lib newFunctionWithName:i ? @"red" : @"green"];
            pd.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
            pipelines[i].pso = [g_dev newRenderPipelineStateWithDescriptor:pd error:&error];
            assert(pipelines[i].pso && !error);
            pipelines[i].prim = MTLPrimitiveTypeTriangle;
        }
        id<MTLTexture> standalone = color_view.tex;
        for (int mode=0;mode<4;mode++) {
            color_view.tex = standalone;
            id<MTLBuffer> backing = nil;
            id<MTLHeap> heap = nil;
            if (mode==2) {
                backing = [g_dev newBufferWithLength:1024 options:MTLResourceStorageModeShared];
                MTLTextureDescriptor *alias = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:4 height:4 mipmapped:NO];
                alias.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
                alias.storageMode = MTLStorageModeShared;
                color_view.tex = [backing newTextureWithDescriptor:alias offset:0 bytesPerRow:256];
                assert(color_view.tex && color_view.tex.buffer==backing);
            } else if (mode==3) {
                MTLHeapDescriptor *hd=[MTLHeapDescriptor new];
                MTLSizeAndAlign sa=[g_dev heapTextureSizeAndAlignWithDescriptor:td];
                hd.size=(sa.size+sa.align-1)&~(sa.align-1); hd.storageMode=MTLStorageModePrivate;
                heap=[g_dev newHeapWithDescriptor:hd]; assert(heap);
                color_view.tex=[heap newTextureWithDescriptor:td];
                assert(color_view.tex && color_view.tex.heap==heap);
            }
            struct VkCommandBuffer_T commands = {0};
            bool feedback_done = false;
            for (int i=0;i<2;i++) {
                h_vkCmdBeginRenderPass(&commands,&bi,VK_SUBPASS_CONTENTS_INLINE);
                if (mode==0) {
                    h_vkCmdBindPipeline(&commands,VK_PIPELINE_BIND_POINT_GRAPHICS,&pipelines[i]);
                    h_vkCmdDraw(&commands,3,1,0,0);
                }
                if (mode==1 && i==1) {
                    // First draw does not sample the attachment. A later draw
                    // switches pipeline/set to feedback; recheck must still cut.
                    h_vkCmdBindPipeline(&commands,VK_PIPELINE_BIND_POINT_GRAPHICS,&pipelines[0]);
                    h_vkCmdDraw(&commands,3,1,0,0);
                    struct VkDescriptorSetLayout_T layout = {.n=1,.total=1};
                    layout.idx[0]=0; layout.b[0]=(lbind){.binding=0,.count=1,.base=0};
                    desc_t descriptor = {.tex=color_view.tex};
                    struct VkDescriptorSet_T set = {.L=&layout,.d=&descriptor};
                    shinfo fs = {.nres=1,.res={{.kind='t',.set=0,.binding=0,.count=1}}};
                    struct VkPipeline_T pipe = {.pso=pipelines[1].pso,.prim=MTLPrimitiveTypeTriangle,.fs=&fs};
                    h_vkCmdBindPipeline(&commands,VK_PIPELINE_BIND_POINT_GRAPHICS,&pipe);
                    h_vkCmdBindDescriptorSets(&commands,VK_PIPELINE_BIND_POINT_GRAPHICS,NULL,0,1,(VkDescriptorSet[]){&set},0,NULL);
                    h_vkCmdDraw(&commands,3,1,0,0);
                    // replay synchronously while stack-backed shader/set exist.
                    rs_t s = {.cb=[queue commandBuffer]};
                    uint64_t before=g_n_encoder, passes=g_n_pass;
                    h_vkCmdEndRenderPass(&commands);
                    replay(&s,&commands);
                    assert(g_n_pass-passes==2);
                    assert(g_n_encoder-before==2 && "feedback draw must cut and resume merged encoder");
                    assert(s.feedback_resolved && !s.re && !s.rpd);
                    id<MTLBuffer> readback = [g_dev newBufferWithLength:1024 options:MTLResourceStorageModeShared];
                    id<MTLBlitCommandEncoder> copy = [s.cb blitCommandEncoder];
                    [copy copyFromTexture:color_view.tex sourceSlice:0 sourceLevel:0
                          sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(4,4,1)
                              toBuffer:readback destinationOffset:0 destinationBytesPerRow:256 destinationBytesPerImage:1024];
                    [copy endEncoding];
                    [s.cb commit]; [s.cb waitUntilCompleted];
                    assert(s.cb.status==MTLCommandBufferStatusCompleted);
                    const uint8_t *pixel = (const uint8_t *)readback.contents + 256 + 4;
                    assert(pixel[0]==255 && pixel[1]==0 && pixel[2]==0 && pixel[3]==255 && "feedback cut draw must store red pixel");
                    free(commands.buf);
                    puts("PASS: feedback descriptor cuts merged replay encoder and resumes with LOAD");
                    feedback_done = true;
                    break;
                }
                h_vkCmdEndRenderPass(&commands);
            }
            if (feedback_done) continue;
            rs_t s = {.cb=[queue commandBuffer]};
            uint64_t before=g_n_encoder, passes=g_n_pass;
            replay(&s,&commands);
            assert(g_n_pass-passes==2);
            assert(g_n_encoder-before==(mode>=2 ? 2 : 1) && "alias must fail closed; safe LOAD/STORE pair must merge");
            assert(!s.re && !s.rpd);
            id<MTLBuffer> readback = nil;
            if (mode==0) {
                readback = [g_dev newBufferWithLength:1024 options:MTLResourceStorageModeShared];
                id<MTLBlitCommandEncoder> copy = [s.cb blitCommandEncoder];
                [copy copyFromTexture:color_view.tex sourceSlice:0 sourceLevel:0
                      sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(4,4,1)
                          toBuffer:readback destinationOffset:0 destinationBytesPerRow:256 destinationBytesPerImage:1024];
                [copy endEncoding];
            }
            [s.cb commit]; [s.cb waitUntilCompleted];
            assert(s.cb.status==MTLCommandBufferStatusCompleted);
            if (mode==0) {
                const uint8_t *pixel = (const uint8_t *)readback.contents + 256 + 4;
                assert(pixel[0]==255 && pixel[1]==0 && pixel[2]==0 && pixel[3]==255 && "second replay draw must store red pixel");
            }
            free(commands.buf);
            puts(mode==3 ? "PASS: heap-backed attachment prevents replay merge" :
                 mode==2 ? "PASS: buffer-backed attachment prevents replay merge" :
                 "PASS: replay merges two drawn LOAD/STORE passes; red pixel readback");
        }
        depth_stencil_case(g_dev, queue);
    }
    return 0;
}

static void depth_stencil_case(id<MTLDevice> dev, id<MTLCommandQueue> queue) {
    MTLTextureDescriptor *ct=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:4 height:4 mipmapped:NO];
    ct.storageMode=MTLStorageModePrivate; ct.usage=MTLTextureUsageRenderTarget;
    MTLTextureDescriptor *dt=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float_Stencil8 width:4 height:4 mipmapped:NO];
    dt.storageMode=MTLStorageModePrivate; dt.usage=MTLTextureUsageRenderTarget;
    id<MTLTexture> color=[dev newTextureWithDescriptor:ct], depth=[dev newTextureWithDescriptor:dt];
    assert(color && depth);
    struct VkImageView_T cv={.tex=color}, dv={.tex=depth};
    struct VkFramebuffer_T fb={.n=2,.w=4,.h=4,.layers=1,.v={&cv,&dv}};
    struct VkRenderPass_T rp={.natt=2,.ncol=1,.col={0},.res={-1},.depth=1};
    rp.att[0]=(ratt){.fmt=VK_FORMAT_R8G8B8A8_UNORM,.load=VK_ATTACHMENT_LOAD_OP_LOAD,.store=VK_ATTACHMENT_STORE_OP_STORE};
    rp.att[1]=(ratt){.fmt=VK_FORMAT_D32_SFLOAT_S8_UINT,.load=VK_ATTACHMENT_LOAD_OP_LOAD,.store=VK_ATTACHMENT_STORE_OP_STORE,
                     .sload=VK_ATTACHMENT_LOAD_OP_LOAD,.sstore=VK_ATTACHMENT_STORE_OP_STORE};
    NSError *err=nil;
    id<MTLLibrary> lib=[dev newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal;\nvertex float4 far_v(uint id [[vertex_id]]) { float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)}; return float4(p[id],0.8,1); }\nvertex float4 near_v(uint id [[vertex_id]]) { float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)}; return float4(p[id],0.2,1); }\nfragment float4 green_fs() {return float4(0,1,0,1);}\nfragment float4 red_fs() {return float4(1,0,0,1);}\n" options:nil error:&err];
    assert(lib && !err);
    MTLDepthStencilDescriptor *ds=[MTLDepthStencilDescriptor new];
    ds.depthCompareFunction=MTLCompareFunctionLess; ds.depthWriteEnabled=YES;
    MTLStencilDescriptor *st=[MTLStencilDescriptor new];
    st.stencilCompareFunction=MTLCompareFunctionAlways; st.depthStencilPassOperation=MTLStencilOperationReplace;
    st.readMask=st.writeMask=0xff; ds.frontFaceStencil=ds.backFaceStencil=st;
    id<MTLDepthStencilState> depth_state=[dev newDepthStencilStateWithDescriptor:ds]; assert(depth_state);
    struct VkPipeline_T pipe[2]={{0}};
    for(int i=0;i<2;i++) {
        MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];
        pd.vertexFunction=[lib newFunctionWithName:i ? @"near_v" : @"far_v"];
        pd.fragmentFunction=[lib newFunctionWithName:i ? @"red_fs" : @"green_fs"];
        pd.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA8Unorm;
        pd.depthAttachmentPixelFormat=pd.stencilAttachmentPixelFormat=MTLPixelFormatDepth32Float_Stencil8;
        pipe[i].pso=[dev newRenderPipelineStateWithDescriptor:pd error:&err]; assert(pipe[i].pso && !err);
        pipe[i].dss=depth_state; pipe[i].prim=MTLPrimitiveTypeTriangle;
        pipe[i].sref_f=pipe[i].sref_b=i ? 7 : 3;
    }
    id<MTLCommandBuffer> cb=[queue commandBuffer];
    MTLRenderPassDescriptor *clear=[MTLRenderPassDescriptor renderPassDescriptor];
    clear.depthAttachment.texture=depth; clear.depthAttachment.loadAction=MTLLoadActionClear;
    clear.depthAttachment.storeAction=MTLStoreActionStore; clear.depthAttachment.clearDepth=1;
    clear.stencilAttachment.texture=depth; clear.stencilAttachment.loadAction=MTLLoadActionClear;
    clear.stencilAttachment.storeAction=MTLStoreActionStore; clear.stencilAttachment.clearStencil=0;
    id<MTLRenderCommandEncoder> ce=[cb renderCommandEncoderWithDescriptor:clear]; assert(ce); [ce endEncoding];
    struct VkCommandBuffer_T commands={0};
    VkRenderPassBeginInfo bi={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO,.renderPass=&rp,.framebuffer=&fb,.renderArea={{0,0},{4,4}}};
    for(int i=0;i<2;i++) {
        h_vkCmdBeginRenderPass(&commands,&bi,VK_SUBPASS_CONTENTS_INLINE);
        h_vkCmdBindPipeline(&commands,VK_PIPELINE_BIND_POINT_GRAPHICS,&pipe[i]);
        h_vkCmdDraw(&commands,3,1,0,0);
        h_vkCmdEndRenderPass(&commands);
    }
    rs_t s={.cb=cb};uint64_t enc_before=g_n_encoder,pass_before=g_n_pass;
    replay(&s,&commands);
    assert(g_n_pass-pass_before==2 && g_n_encoder-enc_before==1 && "depth/stencil LOAD/STORE passes must share one encoder");
    id<MTLBuffer> cr=[dev newBufferWithLength:1024 options:MTLResourceStorageModeShared];
    id<MTLBuffer> dr=[dev newBufferWithLength:1024 options:MTLResourceStorageModeShared];
    id<MTLBuffer> sr=[dev newBufferWithLength:1024 options:MTLResourceStorageModeShared];
    id<MTLBlitCommandEncoder> bl=[cb blitCommandEncoder];
    MTLOrigin origin=MTLOriginMake(0,0,0);MTLSize size=MTLSizeMake(4,4,1);
    [bl copyFromTexture:color sourceSlice:0 sourceLevel:0 sourceOrigin:origin sourceSize:size toBuffer:cr destinationOffset:0 destinationBytesPerRow:256 destinationBytesPerImage:1024];
    [bl copyFromTexture:depth sourceSlice:0 sourceLevel:0 sourceOrigin:origin sourceSize:size toBuffer:dr destinationOffset:0 destinationBytesPerRow:256 destinationBytesPerImage:1024 options:MTLBlitOptionDepthFromDepthStencil];
    [bl copyFromTexture:depth sourceSlice:0 sourceLevel:0 sourceOrigin:origin sourceSize:size toBuffer:sr destinationOffset:0 destinationBytesPerRow:256 destinationBytesPerImage:1024 options:MTLBlitOptionStencilFromDepthStencil];
    [bl endEncoding];[cb commit];[cb waitUntilCompleted];assert(cb.status==MTLCommandBufferStatusCompleted);
    const uint8_t *pixel=(const uint8_t *)cr.contents+256+4;
    float z=0;memcpy(&z,(const uint8_t *)dr.contents+256+4,4);
    uint8_t stencil=* ((const uint8_t *)sr.contents+256+1);
    assert(pixel[0]==255 && pixel[1]==0 && pixel[2]==0 && pixel[3]==255);
    assert(fabsf(z-0.2f)<0.01f && stencil==7 && "depth/stencil writes must survive merged passes");
    free(commands.buf);
    puts("PASS: merged replay preserves color, depth and stencil GPU readback");
}
