// Legacy standalone renderer tests have no loaded title or host OE state.
// Keep the experimental policy explicitly OFF; a targeted fixture may override.
#include "../../host/kh2_aspect.h"
__attribute__((weak)) int dm_kh2_aspect_on(void) { return 0; }
__attribute__((weak)) dm_kh2_extent dm_kh2_aspect_size(void) {
    return (dm_kh2_extent){0, 0};
}
