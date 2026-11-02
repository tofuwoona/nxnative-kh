// Test-only link support: hle_fs.c's optional HID reference has no provider
// in t_fs_case / t_fs_commit_list on this source revision.
#include <stdint.h>
uint64_t dm_input_last_event_ns(void) { return 0; }
