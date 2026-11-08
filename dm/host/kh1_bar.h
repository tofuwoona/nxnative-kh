// Exact offline KH1 persistent-bar adapter contract; not an original-NSO claim.
// Run after load/join and before guest entry. Only the loader's COW key page is
// writable; executable mappings remain read/execute.
#pragma once
#include "dm.h"
#include <sys/mman.h>
#include "kh1_bar_payload.h"

static int dm_kh1_bar_apply(int on) {
    if (DM_GAME_PROGRAM_ID != 0x010090C022978001ull) return 0;
    module_t *m = NULL;
    for (int i = 0; i < g_nmod; ++i) if (!strcmp(g_mod[i].name, "main")) {
        if (m) return 0;
        m = &g_mod[i];
    }
    if (!m || !m->base || !m->loaded || m->nro ||
        strcmp(m->build_id, "badf2faf580b712464365c4d529d92c9") ||
        m->size != 0x31ec000 || ((uintptr_t)m->base & 0x3fff) ||
        m->text_end != 0x2f0c00 || m->ro_off != 0x2f1000 || m->data_off != 0x3cb000 ||
        m->key_page_off != 0x31c8000 || m->key_page_size != 0x4000 ||
        m->patch_off != 0x31d0000 || m->fps_state_off ||
        m->image_size || m->file_image_len || m->patch_len) return 0;
    for (unsigned i = 0; i < 4; ++i) if (m->key_idx[i] != i) return 0;
    static const unsigned char producer[16] = {
        0xff,0x83,0x02,0xd1,0xed,0x33,0x02,0x6d,
        0xeb,0x2b,0x03,0x6d,0xe9,0x23,0x04,0x6d,
    };
    static const unsigned char producer2[16] = {
        0xff,0x03,0x03,0xd1,0xef,0x3b,0x02,0x6d,
        0xfb,0x3b,0x00,0xf9,0xed,0x33,0x03,0x6d,
    };
    if (memcmp(m->base + 0x3edcc, producer, sizeof producer) ||
        memcmp(m->base + 0x5e940, producer2, sizeof producer2)) return 0;
    for (unsigned i = 0; i < sizeof kh1_bar_calls / sizeof kh1_bar_calls[0]; ++i)
        if (memcmp(m->base + kh1_bar_calls[i][0], &kh1_bar_calls[i][1], 4)) return 0;
    if (memcmp(m->base + 0x31e8000, kh1_bar_tail, sizeof kh1_bar_tail)) return 0;
    for (size_t i = 0x31e8000 + sizeof kh1_bar_tail; i < 0x31ec000; ++i)
        if (m->base[i]) return 0;
    uint8_t *page = m->base + 0x31c8000;
    uint32_t *flag = (uint32_t *)(page + 0x100);
    if (*flag & ~1u) return 0;
    for (size_t i = 32; i < 0x4000; ++i)
        if ((i < 0x100 || i >= 0x104) && page[i]) return 0;
    if (*flag == (unsigned)!!on) return 1;
    if (mprotect(page, 0x4000, PROT_READ | PROT_WRITE)) {
        if (*flag) die("KH1 bars: cannot reset previously active key-page flag");
        return 0;
    }
    *flag = !!on;
    if (mprotect(page, 0x4000, PROT_READ)) die("KH1 bars: cannot restore read-only key page");
    return 1;
}
