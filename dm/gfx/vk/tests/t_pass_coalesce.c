// KH2 encoder-coalescing eligibility: only adjacent identical full STORE/LOAD
// passes, whose attachment allocation identities are known safe, may merge.
#include <assert.h>
#include <stdio.h>
#include "../pass_coalesce.h"
static vk_pass_key fixture(void) {
    vk_pass_key k={0};k.rp=(void*)1;k.fb=(void*)2;
    k.area.width=1920;k.area.height=1080;k.color_count=1;k.depth=1;
    k.color[0]=(vk_pass_color){.attachment=0,.resolve=-1,.load=VK_ATTACHMENT_LOAD_OP_LOAD,.store=VK_ATTACHMENT_STORE_OP_STORE};
    k.depth_load=k.stencil_load=VK_ATTACHMENT_LOAD_OP_LOAD;
    k.depth_store=k.stencil_store=VK_ATTACHMENT_STORE_OP_STORE;
    return k;
}
int main(void) {
    vk_pass_key a=fixture(),b=fixture();
    assert(vk_pass_can_coalesce(&a,&b,1));
    assert(!vk_pass_can_coalesce(&a,&b,0)); // unknown/aliased attachment storage fails closed
    b.fb=(void*)3;assert(!vk_pass_can_coalesce(&a,&b,1));b=a;
    b.color[0].load=VK_ATTACHMENT_LOAD_OP_CLEAR;assert(!vk_pass_can_coalesce(&a,&b,1));b=a;
    b.depth_store=VK_ATTACHMENT_STORE_OP_DONT_CARE;assert(!vk_pass_can_coalesce(&a,&b,1));b=a;
    b.color[0].resolve=1;assert(!vk_pass_can_coalesce(&a,&b,1));b=a;
    b.area.width=1280;assert(!vk_pass_can_coalesce(&a,&b,1));
    assert(vk_pass_attachment_safe(1,0,0));
    assert(!vk_pass_attachment_safe(1,1,0)); // buffer-backed texture could alias UBO/SSBO or vertex/index data
    assert(!vk_pass_attachment_safe(1,0,1)); // independently placed resources can overlap a Metal heap
    assert(!vk_pass_attachment_safe(0,0,0)); // missing resource identity fails closed
    puts("coalescing eligibility: 11 checks passed");
}
