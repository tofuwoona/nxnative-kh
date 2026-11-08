// Exact offline adapter contract; not an original-NSO identity claim.
// Must run on the normal startup thread after load/join, before guest entry.
#pragma once
#include "dm.h"
#include <sys/mman.h>
#include "kh2_mask_payload.h"

static int dm_kh2_mask_apply(int on) {
    if (DM_GAME_PROGRAM_ID != 0x010090C022978003ull) return 0;
    module_t *m = NULL;
    for (int i = 0; i < g_nmod; ++i) if (!strcmp(g_mod[i].name, "main")) {
        if (m) return 0;
        m = &g_mod[i];
    }
    if (!m || !m->base || !m->loaded || m->nro ||
        strcmp(m->build_id, "e1bced80ffd14436980f7490b1d3c3e7") ||
        m->size != 0x2d60000 || ((uintptr_t)m->base & 0x3fff) ||
        m->text_end != 0x400d50 || m->ro_off != 0x401000 || m->data_off != 0x52f000 ||
        m->key_page_off != 0x2d30000 || m->key_page_size != 0x4000 ||
        m->patch_off != 0x2d40000 || m->fps_state_off ||
        m->image_size || m->file_image_len || m->patch_len) return 0;
    // Loader contract: precisely four TSD words; reserve +0x100 independently.
    for (unsigned i = 0; i < 4; ++i) if (m->key_idx[i] != i) return 0;
    int cpu = !memcmp(m->base + 0x2d5c000, kh2_mask_tail[1], sizeof kh2_mask_tail[1]);
    if (!cpu && memcmp(m->base + 0x2d5c000, kh2_mask_tail[0], sizeof kh2_mask_tail[0])) return 0;
    unsigned capability = cpu ? 3 : 1;
    int unsupported = ((unsigned)on & ~capability) != 0;
    if (unsupported) on = 0; // clear a previously valid activation only after all layout checks
    for (size_t i = 0x2d5c000 + sizeof kh2_mask_tail[0]; i < 0x2d60000; ++i) if (m->base[i]) return 0;
    uint32_t cpu_entry = cpu ? 0x14b4e9f2 : 0x340000c8;
    if (memcmp(m->base + 0x21938, &cpu_entry, 4)) return 0;
    // Both stateful producer prologues must remain original, never early-return hooks.
    static const uint32_t entries[2] = { 0xd10283ff, 0xd10283ff };
    static const size_t sites[2] = { 0x37760, 0x4422c };
    static const unsigned char next[12] = { 0xed,0x33,0x02,0x6d,0xeb,0x2b,0x03,0x6d,0xe9,0x23,0x04,0x6d };
    for (unsigned i = 0; i < 2; ++i)
        if (memcmp(m->base + sites[i], &entries[i], 4) || memcmp(m->base + sites[i] + 4, next, sizeof next)) return 0;
    for (unsigned i = 0; i < sizeof kh2_mask_quad_calls / sizeof kh2_mask_quad_calls[0]; ++i)
        if (memcmp(m->base + kh2_mask_quad_calls[i][0], &kh2_mask_quad_calls[i][1], 4)) return 0;
    uint8_t *page = m->base + 0x2d30000;
    uint32_t *flag = (uint32_t *)(page + 0x100);
    if (*flag & ~capability) return 0;
    for (size_t i = 32; i < 0x4000; ++i)
        if ((i < 0x100 || i >= 0x104) && page[i]) return 0;
    if (*flag == (unsigned)on) return !unsupported;
    // No executable mapping is ever writable. Only the loader's COW data page.
    if (mprotect(page, 0x4000, PROT_READ | PROT_WRITE)) {
        if (*flag) die("KH2 mask: cannot reset previously active key-page flag");
        return 0;
    }
    *flag = (unsigned)on;
    if (mprotect(page, 0x4000, PROT_READ)) die("KH2 mask: cannot restore read-only key page");
    return !unsupported;
}
