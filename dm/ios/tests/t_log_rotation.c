// Continuous diagnostic log rotation: keep an active file and one previous file.
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/stat.h>
#include "../Sources/log_rotation.h"

static void content(const char *path, const char *expected) {
    FILE *f = fopen(path, "r"); assert(f);
    char got[128] = {0}; size_t n = fread(got, 1, sizeof got - 1, f); fclose(f);
    assert(n == strlen(expected) && !memcmp(got, expected, n));
}
int main(void) {
    char root[512];
    snprintf(root, sizeof root, "%s/kh-logtest.XXXXXX", getenv("TMPDIR") ?: ".");
    assert(mkdtemp(root));
    char active[640], prev[640];
    snprintf(active, sizeof active, "%s/log.txt", root);
    snprintf(prev, sizeof prev, "%s/log.prev.txt", root);
    FILE *f = fopen(active, "w+"); assert(f);
    assert(fputs("first-1234", f) >= 0 && !fflush(f));
    assert(dm_log_rotate_file(f, active, prev, 10) == 1);
    content(prev, "first-1234");
    assert(fputs("second-1234", f) >= 0 && !fflush(f));
    content(active, "second-1234");
    assert(dm_log_rotate_file(f, active, prev, 10) == 1);
    content(prev, "second-1234");
    assert(fputs("next", f) >= 0 && !fflush(f));
    assert(dm_log_rotate_file(f, active, prev, 10) == 0);
    content(active, "next");
    fclose(f); unlink(active); unlink(prev); rmdir(root);
    puts("log rotation: 2 rollover checks, current stream survived");
    return 0;
}
