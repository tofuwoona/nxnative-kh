// Rotate an open stdio stream without invalidating its FILE* or file descriptor.
// Caller owns any synchronization with writers (flockfile for stderr).
//
// Invariant this relies on: nothing else in the process holds a dup() of
// `stream`'s fd (stderr/fd 2) pointing at the same open file description.
// If something did, rename() wouldn't move that fd's target -- it would keep
// writing into whatever file just got renamed to `previous`, silently
// diverging from the active log. As of this writing no other code in dm/
// dup()s fd 2 or STDERR_FILENO directly; dm_log_rotate_assert_sole_owner()
// below checks for that at process start (best-effort, not airtight).
#pragma once
#include <stdint.h>
#include <stdio.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>

// Call once at startup, right after the stream to be rotated is opened, to
// assert the fd-sharing invariant above: no other fd in this process may
// already reference the same file description as `original`.
static inline void dm_log_rotate_assert_sole_owner(int original) {
    struct stat mine; if (fstat(original, &mine)) return;
    for (int fd = 0; fd < 64; fd++) {
        if (fd == original) continue;
        struct stat other;
        if (fstat(fd, &other)) continue;   // not an open fd, or inaccessible: not a collision
        if (other.st_dev == mine.st_dev && other.st_ino == mine.st_ino)
            fprintf(stderr, "[dm] [RED] fd %d already shares the diagnostic log's file with fd %d; "
                "rotation will silently diverge for whatever writes through fd %d\n", fd, original, fd);
    }
}

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
