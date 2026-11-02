// CPU mechanism probe only: generated original instruction slices + C call seams.
// This does NOT run KH2, encode a PNG, publish a save, or test a save-menu route.
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct cache {
    unsigned char before_buffer[0x40];
    void *buffer;
    unsigned char before_dirty[0x20];
    unsigned char dirty;
    unsigned char padding[3];
    int32_t length;
};
_Static_assert(offsetof(struct cache, buffer) == 0x40, "guest buffer offset");
_Static_assert(offsetof(struct cache, dirty) == 0x68, "guest dirty offset");
_Static_assert(offsetof(struct cache, length) == 0x6c, "guest length offset");
extern int32_t probe_serializer_tail(struct cache *, int png_result);
extern int probe_writer_close(FILE *, unsigned char *png_flag);
static uint32_t commit_result;
static int inverse_entries, inverse_body_reached, close_result, io_failures;
static int32_t inverse_length;

// Deliberately bounded seams: these do not implement a serializer or filesystem.
void probe_note_inverse(int32_t n) { inverse_entries++; inverse_length = n; }
void probe_note_inverse_body_reached(void) { inverse_body_reached++; }
uint32_t probe_commit(void) { return commit_result; }
int probe_fclose(FILE *f) { close_result = fclose(f); return close_result; }
static int failing_write(void *cookie, const char *data, int n) {
    (void)cookie; (void)data; (void)n;
    io_failures++; errno = ENOSPC; return -1;
}
static int close_ok(void *cookie) { (void)cookie; return 0; }
static int tail_case(int png, uint32_t result, int require_restore) {
    unsigned char buffer[32] = {0};
    struct cache c = {.buffer = buffer, .dirty = 1, .length = 1024};
    commit_result = result;
    int32_t ret = probe_serializer_tail(&c, png);
    printf("TAIL png=%d commit=%u inverse_entries=%d inverse_length=%d "
           "inverse_body_reached=%d dirty=%u return=%d\n", png, result, inverse_entries,
           inverse_length, inverse_body_reached, c.dirty, ret);
    if (inverse_entries != 1 || inverse_length != (png ? 1024 : -1) ||
        inverse_body_reached != (png ? 1 : 0) || c.dirty != 0 || ret != (png ? 1024 : -1)) {
        fputs("ERROR: native slice did not match the original control flow\n", stderr);
        return 2;
    }
    if (require_restore && !inverse_body_reached) {
        fputs("EXPECTED RED: PNG failure must restore the transformed cache before any read/retry\n", stderr);
        return 1;
    }
    return 0;
}
static int close_case(int require_error) {
    FILE *f = funopen(NULL, NULL, failing_write, NULL, close_ok);
    if (!f || setvbuf(f, NULL, _IOFBF, 4096) || fputs("CPU probe: not a PNG/save", f) < 0) {
        fputs("ERROR: stdio fixture setup failed\n", stderr); return 2;
    }
    unsigned char png_flag = 1;
    int ret = probe_writer_close(f, &png_flag);
    printf("CLOSE real_fclose=%d failing_writes=%d original_writer_return=%d flag=%u\n",
           close_result, io_failures, ret, png_flag);
    if (close_result != EOF || !io_failures || ret != 1 || png_flag != 1) {
        fputs("ERROR: buffered-close failure was not reproduced\n", stderr); return 2;
    }
    if (require_error && ret != 0) {
        fputs("EXPECTED RED: writer success must not ignore fclose failure\n", stderr);
        return 1;
    }
    return 0;
}
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    if (!strcmp(argv[1], "png-success")) return tail_case(1, 0, 0);
    if (!strcmp(argv[1], "commit-failure")) return tail_case(1, 0x202, 0);
    if (!strcmp(argv[1], "png-failure-observed")) return tail_case(0, 0, 0);
    if (!strcmp(argv[1], "require-png-recovery")) return tail_case(0, 0, 1);
    if (!strcmp(argv[1], "close-failure-observed")) return close_case(0);
    if (!strcmp(argv[1], "require-close-error")) return close_case(1);
    return 2;
}
