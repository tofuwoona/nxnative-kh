// Rotate an open stdio stream without invalidating its FILE* or file descriptor.
// Caller owns any synchronization with writers (flockfile for stderr).
#pragma once
#include <stdint.h>
#include <stdio.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>

static inline int dm_log_rotate_file(FILE *stream, const char *active, const char *previous, uint64_t limit) {
    if (!stream || !active || !previous || !limit) { errno = EINVAL; return -1; }
    if (fflush(stream)) return -1;
    int original = fileno(stream);
    struct stat st;
    if (original < 0 || fstat(original, &st)) return -1;
    if ((uint64_t)st.st_size < limit) return 0;
    if (rename(active, previous)) return -1; // atomically replaces the previous segment
    int next = open(active, O_WRONLY | O_CREAT | O_TRUNC, 0600);
    if (next < 0) { int e = errno; rename(previous, active); errno = e; return -1; }
    if (dup2(next, original) < 0) {
        int e = errno; close(next); unlink(active); rename(previous, active); errno = e; return -1;
    }
    close(next); clearerr(stream);
    return 1;
}
