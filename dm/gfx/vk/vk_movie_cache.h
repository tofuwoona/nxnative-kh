#ifndef DM_VK_MOVIE_CACHE_H
#define DM_VK_MOVIE_CACHE_H

#include <stdint.h>
#include <string.h>

#define DM_VK_MOVIE_CACHE_SLOTS 6u
#define DM_KH2_PROGRAM_ID UINT64_C(0x010090C022978003)

typedef struct {
    uint64_t size;
    int occupied;
} dm_vk_movie_cache_slot;

static inline int dm_vk_movie_cache_enabled(uint64_t program_id, const char *setting) {
    if (program_id != DM_KH2_PROGRAM_ID) return 0;
    return !setting || strcmp(setting, "0");
}

static inline int dm_vk_movie_cache_size(uint64_t size) {
    return size == UINT64_C(921600) || size == UINT64_C(460800);
}

static inline int dm_vk_movie_cache_take_slot(dm_vk_movie_cache_slot slots[DM_VK_MOVIE_CACHE_SLOTS], int enabled, uint64_t size) {
    if (!enabled || !dm_vk_movie_cache_size(size)) return -1;
    for (unsigned i = 0; i < DM_VK_MOVIE_CACHE_SLOTS; i++) if (slots[i].occupied && slots[i].size == size) {
        slots[i].occupied = 0;
        slots[i].size = 0;
        return (int)i;
    }
    return -1;
}

static inline int dm_vk_movie_cache_put_slot(dm_vk_movie_cache_slot slots[DM_VK_MOVIE_CACHE_SLOTS], int enabled, uint64_t size) {
    if (!enabled || !dm_vk_movie_cache_size(size)) return -1;
    for (unsigned i = 0; i < DM_VK_MOVIE_CACHE_SLOTS; i++) if (!slots[i].occupied) {
        slots[i].occupied = 1;
        slots[i].size = size;
        return (int)i;
    }
    return -1;
}

#endif
