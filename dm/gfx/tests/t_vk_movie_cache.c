#include "../vk/vk_movie_cache.h"
#include <stdio.h>

#define CHECK(c) do { if (!(c)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); return 1; } } while (0)

int main(void) {
    CHECK(DM_VK_MOVIE_CACHE_SLOTS == 6);
    CHECK(dm_vk_movie_cache_enabled(DM_KH2_PROGRAM_ID, NULL));
    CHECK(dm_vk_movie_cache_enabled(DM_KH2_PROGRAM_ID, ""));
    CHECK(dm_vk_movie_cache_enabled(DM_KH2_PROGRAM_ID, "1"));
    CHECK(!dm_vk_movie_cache_enabled(DM_KH2_PROGRAM_ID, "0"));

    uint64_t kh1 = UINT64_C(0x010090C022978001);
    CHECK(!dm_vk_movie_cache_enabled(kh1, NULL));
    CHECK(!dm_vk_movie_cache_enabled(kh1, ""));
    CHECK(!dm_vk_movie_cache_enabled(kh1, "1"));
    CHECK(!dm_vk_movie_cache_enabled(kh1, "0"));
    CHECK(!dm_vk_movie_cache_enabled(UINT64_C(0x1234), "1"));

    uint64_t y = UINT64_C(1280) * 720;
    uint64_t uv = UINT64_C(640) * 360 * 2;
    CHECK(dm_vk_movie_cache_size(y));
    CHECK(dm_vk_movie_cache_size(uv));
    CHECK(!dm_vk_movie_cache_size(y - 1));
    CHECK(!dm_vk_movie_cache_size(y + 1));
    CHECK(!dm_vk_movie_cache_size(UINT64_C(1920) * 1080));

    dm_vk_movie_cache_slot slots[DM_VK_MOVIE_CACHE_SLOTS] = {0};
    CHECK(dm_vk_movie_cache_put_slot(slots, 0, y) == -1);
    CHECK(dm_vk_movie_cache_take_slot(slots, 0, y) == -1);
    for (unsigned i = 0; i < DM_VK_MOVIE_CACHE_SLOTS; i++) CHECK(!slots[i].occupied);

    for (unsigned i = 0; i < DM_VK_MOVIE_CACHE_SLOTS; i++)
        CHECK(dm_vk_movie_cache_put_slot(slots, 1, i & 1 ? uv : y) == (int)i);
    CHECK(dm_vk_movie_cache_put_slot(slots, 1, y) == -1);
    CHECK(dm_vk_movie_cache_put_slot(slots, 1, y + 1) == -1);

    CHECK(dm_vk_movie_cache_take_slot(slots, 1, y) == 0);
    CHECK(!slots[0].occupied && slots[0].size == 0);
    CHECK(dm_vk_movie_cache_take_slot(slots, 0, uv) == -1);
    CHECK(slots[1].occupied && slots[1].size == uv);
    CHECK(dm_vk_movie_cache_put_slot(slots, 1, y) == 0);

    for (unsigned i = 0; i < DM_VK_MOVIE_CACHE_SLOTS / 2; i++) CHECK(dm_vk_movie_cache_take_slot(slots, 1, y) >= 0);
    for (unsigned i = 0; i < DM_VK_MOVIE_CACHE_SLOTS / 2; i++) CHECK(dm_vk_movie_cache_take_slot(slots, 1, uv) >= 0);
    CHECK(dm_vk_movie_cache_take_slot(slots, 1, y) == -1);
    CHECK(dm_vk_movie_cache_take_slot(slots, 1, uv) == -1);

    puts("PASS: exact-KH2 movie staging-cache policy and slots");
    return 0;
}
