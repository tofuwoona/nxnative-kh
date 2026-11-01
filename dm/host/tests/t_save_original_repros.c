// Independent CPU-only adversarial tests against the exact production hle_fs.c.
// No production fixes. Failing cases assert the desired no-loss property.
#include <sys/types.h>
#include <sys/wait.h>
#include <pthread.h>
#include <errno.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/clonefile.h>
#include "save_test_log_rotation.h"
static ssize_t review_pwrite(int, const void *, size_t, off_t);
static int review_ftruncate(int, off_t);
static int review_clonefile(const char *, const char *, int);
static int review_renamex(const char *, const char *, unsigned);
static int review_unlink(const char *);
#define pwrite review_pwrite
#define ftruncate review_ftruncate
#define clonefile review_clonefile
#define renamex_np review_renamex
#define unlink review_unlink
#ifndef HLE_FS_SOURCE
#define HLE_FS_SOURCE "../hle_fs.c"
#endif
#include HLE_FS_SOURCE
#if DM_GAME_PROGRAM_ID == 0x010090C022978001ull
#define KH_TEST_SAVE_FILE "KHFM.png"
#else
#define KH_TEST_SAVE_FILE "KHIIFM.png"
#endif
#undef pwrite
#undef ftruncate
#undef clonefile
#undef renamex_np
#undef unlink
ssize_t pwrite(int, const void *, size_t, off_t);
int ftruncate(int, off_t);
int clonefile(const char *, const char *, uint32_t);
int renamex_np(const char *, const char *, unsigned);
int unlink(const char *);

#ifdef REVIEW_BASELINE
#define REVIEW_POISON atomic_load(&g_save_poison)
#else
#define REVIEW_POISON atomic_load(&g_save_poison[0])
#endif

struct dm_flags g_flag; uint64_t g_t0_ns;
uint64_t now_ns(void) { return clock_gettime_nsec_np(CLOCK_MONOTONIC); }

void dm_guest_write_prepare(void *p, size_t n) { (void)p; (void)n; }
extern int g_nfail, g_lasterr;
static int io_mode, io_calls, truncate_fail, clone_fail, swap_fail, kill_point, unlink_fail;
static pthread_mutex_t gate_mu = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t gate_cv = PTHREAD_COND_INITIALIZER;
static int partial_ready, release_write;
static ssize_t review_pwrite(int fd, const void *p, size_t n, off_t off) {
    io_calls++;
    if (io_mode == 1) { errno = ENOSPC; return -1; }
    if (io_mode == 2 && io_calls == 1) { errno = EINTR; return -1; }
    if (io_mode == 2 && io_calls == 2 && n > 3) return pwrite(fd, p, 3, off);
    if (io_mode == 3) {
        if (io_calls == 1) return pwrite(fd, p, 3, off);
        errno = ENOSPC; return -1;
    }
    if (io_mode == 4) {
        if (io_calls == 1) {
            ssize_t r = pwrite(fd, p, 3, off);
            pthread_mutex_lock(&gate_mu); partial_ready = 1;
            pthread_cond_broadcast(&gate_cv);
            while (!release_write) pthread_cond_wait(&gate_cv, &gate_mu);
            pthread_mutex_unlock(&gate_mu); return r;
        }
        errno = ENOSPC; return -1;
    }
    return pwrite(fd, p, n, off);
}
static int review_ftruncate(int fd, off_t n) {
    if (truncate_fail) { truncate_fail = 0; errno = ENOSPC; return -1; }
    return ftruncate(fd, n);
}
static int review_clonefile(const char *a, const char *b, int f) {
    size_t n = strlen(b); int snapshot = n >= 4 && !strcmp(b + n - 4, ".new");
    if (snapshot && clone_fail) { clone_fail = 0; errno = ENOSPC; return -1; }
    int r = clonefile(a, b, f);
    if (!r && snapshot && kill_point == 1) _exit(19);
    return r;
}
static int review_renamex(const char *a, const char *b, unsigned f) {
    if (swap_fail) { swap_fail = 0; errno = EIO; return -1; }
    int r = renamex_np(a, b, f);
    if (!r && kill_point == 2) _exit(19);
    return r;
}
static int review_unlink(const char *p) {
    if (unlink_fail && strstr(p, "/keep")) { errno = EIO; return -1; }
    return unlink(p);
}
static char root[1024], save[1100], canonical[1300];
static int failures, checks;
#define EXPECT(c, text) do { int ok_ = !!(c); checks++; if (!ok_) failures++; printf("%s: %s\n", ok_ ? "PASS" : "FAIL", text); } while (0)
#define MUST(c) do { if (!(c)) { fprintf(stderr, "fixture setup failed line %d errno=%d\n", __LINE__, errno); exit(2); } } while (0)
static void put(const char *p, const char *s) { FILE *f = fopen(p, "w"); MUST(f); MUST(fputs(s, f) >= 0); MUST(!fclose(f)); }
static const char *content(const char *p) { static char b[256]; FILE *f = fopen(p, "r"); if (!f) return "<missing>"; size_t n = fread(b, 1, sizeof b - 1, f); b[n] = 0; fclose(f); return b; }
static const char *guest = "save:/KINGDOM HEARTS HD 1.5+2.5 ReMIX/" KH_TEST_SAVE_FILE "";
static const char *backslash = "save:\\KINGDOM HEARTS HD 1.5+2.5 ReMIX\\" KH_TEST_SAVE_FILE "";
static void setup(void) {
    unsetenv("DM_TEST_FS_FAIL"); unsetenv("DM_TEST_KILL_AT"); unsetenv("DM_TEST_FS_FAILAT");
    unsetenv("DM_KH2_SAVE_FIX_MIGRATE");
    snprintf(root, sizeof root, "%s/kh-save-adversarial.XXXXXX", getenv("TMPDIR") ?: "."); MUST(mkdtemp(root));
    snprintf(save, sizeof save, "%s/save", root); MUST(!mkdir(save, 0700));
    char dir[1200]; snprintf(dir, sizeof dir, "%s/KINGDOM HEARTS HD 1.5+2.5 ReMIX", save); MUST(!mkdir(dir, 0700));
    snprintf(canonical, sizeof canonical, "%s/" KH_TEST_SAVE_FILE "", dir); put(canonical, "OLDold");
    setenv("DM_SAVE", save, 1); MUST(h_fs_MountSave("save", NULL) == RES_OK);
}
static uint64_t open_write(void) { uint64_t h = 0; MUST(h_fs_OpenFile(&h, guest, MODE_WRITE) == RES_OK); return h; }
static Result write_save(const char *s) { uint64_t h = open_write(); Result r = h_fs_SetFileSize(h, strlen(s)); if (!r) r = h_fs_WriteFile(h, 0, s, strlen(s), NULL); h_fs_CloseFile(h); return r; }
static const char *read_guest(const char *path) {
    static char b[256]; size_t n = 0; uint64_t h = 0;
    if (h_fs_OpenFile(&h, path, MODE_READ)) return "<open failed>";
    Result r = h_fs_ReadFile(&n, h, 0, b, sizeof b - 1); h_fs_CloseFile(h); b[n] = 0; return r ? "<read failed>" : b;
}
static void remount(void) { g_nmnt = 0; MUST(h_fs_MountSave("save", NULL) == RES_OK); }
static void failed_create(void) {
    MUST(h_fs_DeleteFile(guest) == RES_OK);
    truncate_fail = 1;
    Result create = h_fs_CreateFile(guest, 6); uint64_t h = 0;
    Result opened = h_fs_OpenFile(&h, guest, MODE_WRITE);
    Result write = h_fs_WriteFile(h, 0, "NEWnew", 6, NULL);
    Result committed = h_fs_Commit("save"); remount();
    printf("OBS create=%#x open=%#x write=%#x commit=%#x alerts=%d cold=%s\n", create, opened, write, committed, g_nfail, content(canonical));
    EXPECT(create != RES_OK && write != RES_OK, "fixture triggers failed create/write");
    EXPECT(committed != RES_OK, "failed replacement creation refuses commit");
    EXPECT(!strcmp(content(canonical), "OLDold"), "failed overwrite preserves previous committed save");
    EXPECT(g_nfail == 1, "failed save notifies front end");
}
static void readonly_path(void) {
    char p[1400]; snprintf(p, sizeof p, "%s/\\KINGDOM HEARTS HD 1.5+2.5 ReMIX\\" KH_TEST_SAVE_FILE "", save); put(p, "STALEflat");
    setenv("DM_TEST_FS_FAILAT", "mountclone:1", 1); remount();
    printf("OBS slash=%s\n", read_guest(guest));
    printf("OBS backslash=%s alerts=%d\n", read_guest(backslash), g_nfail);
    EXPECT(!strcmp(read_guest(guest), "OLDold"), "read-only fallback reads canonical save by slash spelling");
    EXPECT(!strcmp(read_guest(backslash), "OLDold"), "read-only fallback preserves canonical backslash mapping instead of stale flat save");
}
static void held_handle(void) {
    uint64_t h = open_write(); io_mode = 1;
    MUST(h_fs_WriteFile(h, 0, "BADbad", 6, NULL) != RES_OK); io_mode = 0;
    MUST(h_fs_Commit("save") != RES_OK);
    Result w = h_fs_WriteFile(h, 0, "NEWnew", 6, NULL);
    Result flush = h_fs_FlushFile(h); h_fs_CloseFile(h);
    Result commit = h_fs_Commit("save"); remount();
    printf("OBS reused-handle write=%#x flush=%#x commit=%#x alerts=%d cold=%s\n", w, flush, commit, g_nfail, content(canonical));
    EXPECT(w != RES_OK || commit != RES_OK || !strcmp(content(canonical), "NEWnew"), "post-rollback stale handle must fail or persist acknowledged bytes");
}
static void commit_error(int swap) {
    MUST(write_save("NEWnew") == RES_OK); if (swap) swap_fail = 1; else clone_fail = 1;
    Result r = h_fs_Commit("save");
    printf("OBS commit=%#x alerts=%d errno=%d committed=%s\n", r, g_nfail, errno, content(canonical));
    EXPECT(r != RES_OK && !strcmp(content(canonical), "OLDold"), "snapshot/swap failure leaves committed bytes intact");
    EXPECT(g_nfail == 1, "snapshot/swap failure notifies front end that progress was not saved");
    EXPECT(h_fs_Commit("save") == RES_OK && !strcmp(content(canonical), "NEWnew"), "retry publishes staged bytes after commit I/O failure");
}
static Result writer_result;
static void *racing_writer(void *arg) { writer_result = h_fs_WriteFile(*(uint64_t *)arg, 0, "NEWnew", 6, NULL); return NULL; }
static Result racing_commit_result;
static int commit_done;
static void *racing_commit(void *arg) {
    (void)arg; racing_commit_result = h_fs_Commit("save");
    pthread_mutex_lock(&gate_mu); commit_done = 1; pthread_cond_broadcast(&gate_cv); pthread_mutex_unlock(&gate_mu);
    return NULL;
}
static void concurrent_commit(void) {
    uint64_t h = open_write(); io_mode = 4; pthread_t t, cthread; MUST(!pthread_create(&t, NULL, racing_writer, &h));
    pthread_mutex_lock(&gate_mu); while (!partial_ready) pthread_cond_wait(&gate_cv, &gate_mu); pthread_mutex_unlock(&gate_mu);
    MUST(!pthread_create(&cthread, NULL, racing_commit, NULL));
    // The baseline can finish Commit while the failed write is gated; a fixed
    // Commit waits for the complete write/poison decision. Release either way.
    pthread_mutex_lock(&gate_mu);
    struct timespec deadline; clock_gettime(CLOCK_REALTIME, &deadline); deadline.tv_sec++;
    while (!commit_done && pthread_cond_timedwait(&gate_cv, &gate_mu, &deadline) != ETIMEDOUT) {}
    release_write = 1; pthread_cond_broadcast(&gate_cv); pthread_mutex_unlock(&gate_mu);
    MUST(!pthread_join(t, NULL)); MUST(!pthread_join(cthread, NULL)); h_fs_CloseFile(h); io_mode = 0;
    Result c = racing_commit_result;
    char saved[256]; strlcpy(saved, content(canonical), sizeof saved);
    printf("OBS in-flight commit=%#x writer=%#x snapshot=%s poison=%d\n", c, writer_result, saved, REVIEW_POISON);
    EXPECT(c != RES_OK || !strcmp(saved, "OLDold"), "commit cannot publish prefix of concurrent subsequently-failed write");
    remount(); EXPECT(!strcmp(content(canonical), "OLDold"), "cold remount keeps complete old save when concurrent write fails");
}
static void short_io(void) {
    io_mode = 2; io_calls = 0; EXPECT(write_save("NEWnew") == RES_OK, "EINTR + short positive write retries to completion");
    EXPECT(io_calls == 3, "one EINTR, one short write, one remaining write");
    EXPECT(h_fs_Commit("save") == RES_OK && !strcmp(content(canonical), "NEWnew"), "short-I/O transaction persists exact bytes");
    io_mode = 3; io_calls = 0; EXPECT(write_save("BADbad") != RES_OK, "partial pwrite then ENOSPC reports failure");
    EXPECT(h_fs_Commit("save") != RES_OK && !strcmp(content(canonical), "NEWnew"), "partial failed write cannot publish partial bytes");
    io_mode = 0; remount(); EXPECT(!strcmp(read_guest(backslash), "NEWnew"), "cold normalized read preserves last successful transaction");
}
static void resize_failure(void) {
    uint64_t h = open_write(); truncate_fail = 1;
    EXPECT(h_fs_SetFileSize(h, 0) != RES_OK, "resize failure reaches guest");
    MUST(h_fs_WriteFile(h, 0, "NEWnew", 6, NULL) == RES_OK); h_fs_CloseFile(h);
    EXPECT(h_fs_Commit("save") != RES_OK && !strcmp(content(canonical), "OLDold"), "failed resize poisons transaction despite subsequent successful write");
}
static void crash_test(int point) {
    fflush(NULL); pid_t p = fork(); MUST(p >= 0);
    if (!p) { MUST(write_save("NEWnew") == RES_OK); kill_point = point; if (!point) _exit(19); h_fs_Commit("save"); _exit(2); }
    int status; MUST(waitpid(p, &status, 0) == p); MUST(WIFEXITED(status) && WEXITSTATUS(status) == 19);
    remount(); const char *expected = point == 2 ? "NEWnew" : "OLDold";
    printf("OBS crash-point=%d cold=%s expected=%s\n", point, read_guest(backslash), expected);
    EXPECT(!strcmp(read_guest(backslash), expected), "process death before snapshot / before swap / after swap exposes complete expected generation");
    char n[1200]; snprintf(n, sizeof n, "%s.new", save); EXPECT(access(n, F_OK) != 0, "cold mount clears leftover .new");
}
static void aliases(void) {
    char flat[1400]; snprintf(flat, sizeof flat, "%s/\\KINGDOM HEARTS HD 1.5+2.5 ReMIX\\" KH_TEST_SAVE_FILE "", save); put(flat, "STALEflat");
    remount(); EXPECT(!strcmp(read_guest(backslash), "OLDold"), "normal mount chooses canonical over distinct stale flat save");
    MUST(write_save("NEWnew") == RES_OK); MUST(h_fs_Commit("save") == RES_OK); remount();
    EXPECT(!strcmp(read_guest(backslash), "NEWnew"), "normal remount loads new canonical via backslash");
    EXPECT(!strcmp(content(flat), "STALEflat"), "normalization does not migrate or overwrite distinct flat file");
}
static void recursive_failure(void) {
    char dir[1200], path[1300]; snprintf(dir, sizeof dir, "%s/cleanup", g_mnt[0].dir); MUST(!mkdir(dir, 0700));
    snprintf(path, sizeof path, "%s/remove", dir); put(path, "old-remove"); snprintf(path, sizeof path, "%s/keep", dir); put(path, "old-keep");
    MUST(h_fs_Commit("save") == RES_OK); unlink_fail = 1;
    Result clean = h_fs_CleanDirRec("save:/cleanup"); unlink_fail = 0;
    Result commit = h_fs_Commit("save");
    printf("OBS clean=%#x commit=%#x poison=%d\n", clean, commit, REVIEW_POISON);
    EXPECT(clean != RES_OK, "cleanup fixture returns I/O failure after partial deletion");
    EXPECT(commit != RES_OK, "partial recursive cleanup failure refuses entire transaction");
    snprintf(path, sizeof path, "%s/cleanup/remove", save); EXPECT(!strcmp(content(path), "old-remove"), "old tree preserved after partial failed cleanup");
}
static void overloads(void) {
    MUST(write_save("FIRST1") == RES_OK); EXPECT(h_fs_CommitOpt("save", NULL) == RES_OK && !strcmp(content(canonical), "FIRST1"), "CommitOption overload publishes exact bytes");
    MUST(write_save("NEXT22") == RES_OK); EXPECT(h_fs_CommitSaveData("save") == RES_OK && !strcmp(content(canonical), "NEXT22"), "legacy CommitSaveData overload publishes exact bytes");
    const char *names[] = {"save"}; MUST(write_save("LAST33") == RES_OK); EXPECT(h_fs_CommitList(names, 1) == RES_OK && !strcmp(content(canonical), "LAST33"), "mount-list overload publishes exact bytes");
    uint64_t h = 0; MUST(h_fs_OpenFile(&h, backslash, MODE_READ) == RES_OK); char b[16] = {0}; size_t n = 0;
    EXPECT(h_fs_ReadFileExact(h, 0, b, 6) == RES_OK && !memcmp(b, "LAST33", 6), "no-count exact-read overload returns entire save bytes");
    EXPECT(h_fs_ReadFileExact(h, 0, b, 7) != RES_OK, "no-count exact-read overload rejects EOF short read");
    EXPECT(h_fs_ReadFileOpt(&n, h, 0, b, 16, NULL) == RES_OK && n == 6, "read-option/count overload permits EOF and reports exact count"); h_fs_CloseFile(h);
    io_mode = 1; MUST(write_save("BAD444") != RES_OK); io_mode = 0;
    EXPECT(h_fs_CommitOpt("save", NULL) != RES_OK && !strcmp(content(canonical), "LAST33"), "CommitOption overload does not bypass transaction poison");
}
static _Atomic int log_stop, log_rotations;
static char active_log[1400], previous_log[1400];
static void *rotate_save_logs(void *arg) {
    (void)arg;
    while (!atomic_load(&log_stop)) {
        flockfile(stderr);
        int r = dm_log_rotate_file(stderr, active_log, previous_log, 256);
        if (r > 0) atomic_fetch_add(&log_rotations, 1);
        funlockfile(stderr); usleep(200);
    }
    return NULL;
}
static void log_rotation_save(void) {
    snprintf(active_log, sizeof active_log, "%s/log.txt", root);
    snprintf(previous_log, sizeof previous_log, "%s/log.prev.txt", root);
    MUST(freopen(active_log, "w", stderr)); setvbuf(stderr, NULL, _IOLBF, 0);
    pthread_t t; MUST(!pthread_create(&t, NULL, rotate_save_logs, NULL));
    int errors = 0;
    for (int i = 0; i < 100; i++) {
        char s[32]; snprintf(s, sizeof s, "generation-%d", i);
        if (write_save(s) != RES_OK || h_fs_Commit("save") != RES_OK || strcmp(content(canonical), s)) errors++;
        usleep(300);
    }
    atomic_store(&log_stop, 1); MUST(!pthread_join(t, NULL));
    remount();
    EXPECT(errors == 0, "100 transactions preserve exact acknowledged bytes during concurrent stderr rotation");
    EXPECT(atomic_load(&log_rotations) > 0, "fixture actually rotated logs while saving");
    EXPECT(!strcmp(read_guest(backslash), "generation-99"), "final generation survives cold remount after concurrent rotation");
    printf("OBS successful-log-rotations=%d\n", atomic_load(&log_rotations));
}
static void legacy_only(void) {
    char p[1400]; MUST(!unlink(canonical));
    snprintf(p, sizeof p, "%s/\\KINGDOM HEARTS HD 1.5+2.5 ReMIX\\" KH_TEST_SAVE_FILE "", save); put(p, "FLATonly");
    remount();
    EXPECT(!strcmp(read_guest(backslash), "<open failed>"), "legacy-only save is not silently migrated or selected");
    EXPECT(!strcmp(content(p), "FLATonly"), "legacy-only original is preserved");
}
static int real_copy(const char *mode, const char *dir, const char *expected) {
    // Caller must supply its disposable copy; never run this mode on original saves.
    unsetenv("DM_KH2_SAVE_FIX_MIGRATE"); setenv("DM_SAVE", dir, 1);
    MUST(h_fs_MountSave("save", NULL) == RES_OK);
    FILE *f = fopen(expected, "rb"); MUST(f); MUST(!fseek(f, 0, SEEK_END)); long n = ftell(f); MUST(n > 0); rewind(f);
    char *bytes = malloc((size_t)n), *got = malloc((size_t)n); MUST(bytes && got); MUST(fread(bytes, 1, n, f) == (size_t)n); fclose(f);
    uint64_t h = 0; MUST(h_fs_OpenFile(&h, backslash, MODE_READ) == RES_OK);
    size_t count = 0; MUST(h_fs_ReadFile(&count, h, 0, got, n) == RES_OK); h_fs_CloseFile(h);
    EXPECT(count == (size_t)n && !memcmp(bytes, got, n), "real copied canonical save reads byte-identically through normalized backslash spelling");
    if (!strcmp(mode, "real-roundtrip")) {
        MUST(h_fs_OpenFile(&h, guest, MODE_WRITE) == RES_OK); MUST(h_fs_SetFileSize(h, 0) == RES_OK); MUST(h_fs_SetFileSize(h, n) == RES_OK);
        int opt = 1;
        for (long off = 0; off < n;) {
            size_t chunk = (size_t)(n - off) > 300000 ? 300000 : (size_t)(n - off);
            MUST(h_fs_WriteFile(h, off, bytes + off, chunk, &opt) == RES_OK); off += chunk;
        }
        MUST(h_fs_FlushFile(h) == RES_OK); h_fs_CloseFile(h); EXPECT(h_fs_Commit("save") == RES_OK, "real copied container byte-rewrite commits successfully");
    }
    printf("RESULT %s: %d checks, %d failed; bytes=%ld\n", mode, checks, failures, n); free(bytes); free(got); return failures ? 1 : 0;
}
int main(int argc, char **argv) {
    if (argc == 4 && (!strcmp(argv[1], "real-roundtrip") || !strcmp(argv[1], "real-read"))) return real_copy(argv[1], argv[2], argv[3]);
    if (argc != 2) return 2; setup();
    if (!strcmp(argv[1], "create-failure")) failed_create();
    else if (!strcmp(argv[1], "readonly-path")) readonly_path();
    else if (!strcmp(argv[1], "held-handle")) held_handle();
    else if (!strcmp(argv[1], "clone-failure")) commit_error(0);
    else if (!strcmp(argv[1], "swap-failure")) commit_error(1);
    else if (!strcmp(argv[1], "concurrent-commit")) concurrent_commit();
    else if (!strcmp(argv[1], "short-io")) short_io();
    else if (!strcmp(argv[1], "resize-failure")) resize_failure();
    else if (!strcmp(argv[1], "crash-before-commit")) crash_test(0);
    else if (!strcmp(argv[1], "crash-before-swap")) crash_test(1);
    else if (!strcmp(argv[1], "crash-after-swap")) crash_test(2);
    else if (!strcmp(argv[1], "normal-aliases")) aliases();
    else if (!strcmp(argv[1], "recursive-failure")) recursive_failure();
    else if (!strcmp(argv[1], "log-rotation-save")) log_rotation_save();
    else if (!strcmp(argv[1], "legacy-only")) legacy_only();
    else if (!strcmp(argv[1], "overloads")) overloads();
    else return 2;
    printf("RESULT %s: %d checks, %d failed\n", argv[1], checks, failures);
    MUST(rm_tree(root) == 0); return failures ? 1 : 0;
}
