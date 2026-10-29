#include <assert.h>
#include <stdint.h>
#include "face_swap.h"

int main(void) {
    const uint64_t extras = (UINT64_C(1) << 63) | (UINT64_C(1) << 12);
    for (uint64_t bits = 0; bits < 16; ++bits) {
        uint64_t input = bits | extras;
        uint64_t expected = extras | ((bits & 1) << 1) | ((bits & 2) >> 1)
                                   | ((bits & 4) << 1) | ((bits & 8) >> 1);
        assert(dm_face_swap(input, 0) == input);
        assert(dm_face_swap(input, 1) == expected);
        assert(dm_face_swap(dm_face_swap(input, 1), 1) == input);
    }
    // Touch labels remain X and Y at their original positions when enabled.
    assert(dm_face_swap(UINT64_C(1) << 2, 1) == (UINT64_C(1) << 3));
    assert(dm_face_swap(UINT64_C(1) << 3, 1) == (UINT64_C(1) << 2));
    // Apple physical buttonX is initially mapped by position to Switch Y.
    // With swap enabled it must still produce game Y, not X.
    assert(dm_face_swap(dm_pad_before_face_swap(UINT64_C(1) << 3, 1), 1) == (UINT64_C(1) << 3));
    assert(dm_face_swap(dm_pad_before_face_swap(UINT64_C(1) << 2, 1), 1) == (UINT64_C(1) << 2));
    for (uint64_t bits = 0; bits < 16; ++bits) {
        uint64_t input = bits | extras;
        assert(dm_pad_before_face_swap(input, 0) == input);
        uint64_t corrected = dm_face_swap(dm_pad_before_face_swap(input, 1), 1);
        uint64_t expected = extras | ((bits & 1) << 1) | ((bits & 2) >> 1) | (bits & 12);
        assert(corrected == expected);
    }
    return 0;
}
