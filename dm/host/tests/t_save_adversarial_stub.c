// Same CPU-only loader/guest stubs as the normal tests; notification re-enters
// the FS to prove production callbacks run outside both transaction locks.
#define front_save_failed normal_test_save_failed
#include "t_fs_stub.c"
#undef front_save_failed
extern void review_save_failed(int);
void front_save_failed(int err) { normal_test_save_failed(err); review_save_failed(err); }
