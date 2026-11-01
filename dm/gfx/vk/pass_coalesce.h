// Adjacent Vulkan pass eligibility for reuse of an open Metal encoder.
#pragma once
#include <vulkan/vulkan_core.h>
#include <stdint.h>

typedef struct {
    int attachment, resolve;
    VkAttachmentLoadOp load;
    VkAttachmentStoreOp store;
} vk_pass_color;
typedef struct {
    const void *rp, *fb;
    struct { int32_t x, y; uint32_t width, height; } area;
    unsigned color_count;
    vk_pass_color color[8];
    int depth;
    VkAttachmentLoadOp depth_load, stencil_load;
    VkAttachmentStoreOp depth_store, stencil_store;
} vk_pass_key;

// attachment_storage_safe must be false unless all attachment objects are
// known to have non-aliased backing storage (no buffer-backed/heap texture).
// Reject storage identities whose physical backing could overlap a descriptor
// buffer, attachment view, or independently placed texture. The host creates
// ordinary optimal images as standalone textures, so this is conservative.
static inline int vk_pass_attachment_safe(int has_texture, int buffer_backed, int heap_placed) {
    return has_texture && !buffer_backed && !heap_placed;
}

static inline int vk_pass_can_coalesce(const vk_pass_key *prev, const vk_pass_key *next, int attachment_storage_safe) {
    if (!attachment_storage_safe || !prev || !next || !prev->color_count ||
        prev->rp != next->rp || prev->fb != next->fb ||
        prev->area.x != next->area.x || prev->area.y != next->area.y ||
        prev->area.width != next->area.width || prev->area.height != next->area.height ||
        prev->color_count != next->color_count || prev->depth != next->depth || prev->color_count > 8) return 0;
    for (unsigned i = 0; i < prev->color_count; i++) {
        const vk_pass_color *a=&prev->color[i], *b=&next->color[i];
        if (a->attachment < 0 || a->attachment != b->attachment || a->resolve != -1 || b->resolve != -1 ||
            a->load != VK_ATTACHMENT_LOAD_OP_LOAD || b->load != VK_ATTACHMENT_LOAD_OP_LOAD ||
            a->store != VK_ATTACHMENT_STORE_OP_STORE || b->store != VK_ATTACHMENT_STORE_OP_STORE) return 0;
    }
    if (prev->depth >= 0 && (prev->depth_load != VK_ATTACHMENT_LOAD_OP_LOAD ||
        next->depth_load != VK_ATTACHMENT_LOAD_OP_LOAD || prev->depth_store != VK_ATTACHMENT_STORE_OP_STORE ||
        next->depth_store != VK_ATTACHMENT_STORE_OP_STORE ||
        prev->stencil_load != VK_ATTACHMENT_LOAD_OP_LOAD || next->stencil_load != VK_ATTACHMENT_LOAD_OP_LOAD ||
        prev->stencil_store != VK_ATTACHMENT_STORE_OP_STORE || next->stencil_store != VK_ATTACHMENT_STORE_OP_STORE)) return 0;
    return 1;
}
