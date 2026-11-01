// Continuous diagnostic log rotation: keep an active file and one previous file.
#include <assert.h>
#include <pthread.h>
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

// Every line a writer emits must survive intact: either in the previous
// segment, the active segment, or split exactly at a line boundary across
// both -- never with a line missing its own trailing newline or merged with
// another line's text. This is the failure mode a single flockfile-guarded
// fprintf per line (dm.h's LOG macro) must rule out: the rotation thread's
// flockfile(stream) can only ever land between two callers' fprintf calls,
// not inside one, so every line is either fully before or fully after a
// rollover.
static int check_no_split_lines(const char *path, int *next_expected) {
    FILE *f = fopen(path, "r"); if (!f) return 1;
    char line[256]; int ok = 1, saw_any = 0;
    while (fgets(line, sizeof line, f)) {
        size_t n = strlen(line);
        if (n == 0 || line[n - 1] != '\n') { ok = 0; break; }   // truncated / split line: corruption
        int v; if (sscanf(line, "line %d\n", &v) != 1) { ok = 0; break; }
        if (saw_any && v != *next_expected) { ok = 0; break; }   // out of order or a line vanished mid-stream
        *next_expected = v + 1; saw_any = 1;
    }
    fclose(f);
    return ok;
}

static volatile int g_stop;
static FILE *g_f;
static void *writer(void *arg) {
    (void)arg;
    for (int i = 0; !g_stop; i++) { fprintf(g_f, "line %d\n", i); fflush(g_f); }
    return NULL;
}

static void concurrent_rotation_preserves_whole_lines(void) {
    char root[512];
    snprintf(root, sizeof root, "%s/kh-logtest-mt.XXXXXX", getenv("TMPDIR") ?: ".");
    assert(mkdtemp(root));
    char active[640], prev[640];
    snprintf(active, sizeof active, "%s/log.txt", root);
    snprintf(prev, sizeof prev, "%s/log.prev.txt", root);
    g_f = fopen(active, "w+"); assert(g_f);
    pthread_t t; assert(!pthread_create(&t, NULL, writer, NULL));
    for (int i = 0; i < 2000; i++) {
        flockfile(g_f);
        dm_log_rotate_file(g_f, active, prev, 256);   // small limit: forces frequent rollovers under load
        funlockfile(g_f);
        usleep(200);
    }
    g_stop = 1; pthread_join(t, NULL); fclose(g_f);
    int next = 0;
    assert(check_no_split_lines(prev, &next) && "previous segment has a split or malformed line");
    assert(check_no_split_lines(active, &next) && "active segment has a split or malformed line, or a gap after the previous segment");
    unlink(active); unlink(prev); rmdir(root);
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
    concurrent_rotation_preserves_whole_lines();
    puts("log rotation: 2 rollover checks + concurrent-writer stress, no split lines, current stream survived");
    return 0;
}
