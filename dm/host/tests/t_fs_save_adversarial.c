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
#include <fcntl.h>
#include <stdarg.h>
#include <sys/xattr.h>
#include "../../ios/Sources/log_rotation.h"
static ssize_t review_pwrite(int, const void *, size_t, off_t);
static int review_ftruncate(int, off_t);
static int review_clonefile(const char *, const char *, int);
static int review_renamex(const char *, const char *, unsigned);
static int review_unlink(const char *);
static int review_open(const char *, int, ...);
static int review_removexattr(const char *, const char *, int);
static int review_mkdir(const char *, mode_t);
#define pwrite review_pwrite
#define ftruncate review_ftruncate
#define clonefile review_clonefile
#define renamex_np review_renamex
#define unlink review_unlink
#define open review_open
#define removexattr review_removexattr
#define mkdir review_mkdir
#ifndef HLE_FS_SOURCE
#define HLE_FS_SOURCE "../hle_fs.c"
#endif
#include HLE_FS_SOURCE
#undef pwrite
#undef ftruncate
#undef clonefile
#undef renamex_np
#undef unlink
#undef open
#undef removexattr
#undef mkdir
ssize_t pwrite(int, const void *, size_t, off_t);
int ftruncate(int, off_t);
int clonefile(const char *, const char *, uint32_t);
int renamex_np(const char *, const char *, unsigned);
int unlink(const char *);
int mkdir(const char *, mode_t);
#ifdef REVIEW_BASELINE
#define REVIEW_POISON atomic_load(&g_save_poison)
#else
#define REVIEW_POISON atomic_load(&g_save_poison[0])
#endif

struct dm_flags g_flag; uint64_t g_t0_ns;
uint64_t now_ns(void) { return clock_gettime_nsec_np(CLOCK_MONOTONIC); }
uint64_t dm_input_last_event_ns(void) { return 0; }
void dm_guest_write_prepare(void *p, size_t n) { (void)p; (void)n; }
extern int g_nfail, g_lasterr;
static int callback_locked;
void review_save_failed(int error) {
    (void)error;
    int p = pthread_mutex_trylock(&g_path_lock), m = pthread_mutex_trylock(&g_lock);
    if (p || m) callback_locked++;
    if (!m) pthread_mutex_unlock(&g_lock);
    if (!p) pthread_mutex_unlock(&g_path_lock);
    if (!p && !m) h_fs_IsMounted("save"); // An actual re-entrant path lookup.
}
static int io_mode, io_calls, truncate_fail, clone_fail, swap_fail, kill_point, unlink_fail;
static int open_fail, name_fail, mkdir_fail, write_open_fail;
static int review_open(const char *p, int flags, ...) {
    mode_t mode = 0;
    if (flags & O_CREAT) { va_list ap; va_start(ap, flags); mode = va_arg(ap, int); va_end(ap); }
    if ((flags & O_CREAT) && open_fail) { open_fail = 0; errno = ENOSPC; return -1; }
    if (!(flags & O_CREAT) && (flags & O_WRONLY) && write_open_fail) { write_open_fail = 0; errno = EMFILE; return -1; }
    return open(p, flags, mode);
}
static int review_removexattr(const char *p, const char *name, int flags) {
    if (name_fail) { name_fail = 0; errno = EIO; return -1; }
    return removexattr(p, name, flags);
}
static int review_mkdir(const char *p, mode_t mode) {
    if (mkdir_fail) { mkdir_fail = 0; errno = ENOSPC; return -1; }
    return mkdir(p, mode);
}
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
static const char *guest = "save:/KINGDOM HEARTS HD 1.5+2.5 ReMIX/KHIIFM.png";
static const char *backslash = "save:\\KINGDOM HEARTS HD 1.5+2.5 ReMIX\\KHIIFM.png";
static void setup(void) {
    unsetenv("DM_TEST_FS_FAIL"); unsetenv("DM_TEST_KILL_AT"); unsetenv("DM_TEST_FS_FAILAT");
    unsetenv("DM_KH2_SAVE_FIX_MIGRATE");
    snprintf(root, sizeof root, "%s/kh-save-adversarial.XXXXXX", getenv("TMPDIR") ?: "."); MUST(mkdtemp(root));
    snprintf(save, sizeof save, "%s/save", root); MUST(!mkdir(save, 0700));
    char dir[1200]; snprintf(dir, sizeof dir, "%s/KINGDOM HEARTS HD 1.5+2.5 ReMIX", save); MUST(!mkdir(dir, 0700));
    snprintf(canonical, sizeof canonical, "%s/KHIIFM.png", dir); put(canonical, "OLDold");
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
static void failed_create(int stage) {
    MUST(h_fs_DeleteFile(guest) == RES_OK);
    if (stage == 1) open_fail = 1;
    else if (stage == 2) name_fail = 1;
    else truncate_fail = 1;
    Result create = h_fs_CreateFile(guest, 6); uint64_t h = 0;
    Result opened = h_fs_OpenFile(&h, guest, MODE_WRITE);
    Result write = h_fs_WriteFile(h, 0, "NEWnew", 6, NULL);
    Result committed = h_fs_Commit("save"); remount();
    printf("OBS create=%#x open=%#x write=%#x commit=%#x alerts=%d cold=%s\n", create, opened, write, committed, g_nfail, content(canonical));
    EXPECT(create != RES_OK && write != RES_OK, "fixture triggers failed create/write");
    EXPECT(committed != RES_OK, "failed replacement creation refuses commit");
    EXPECT(!strcmp(content(canonical), "OLDold"), "failed overwrite preserves previous committed save");
    EXPECT(g_nfail == 1, "failed save notifies front end");
    Result retry_create = h_fs_CreateFile(guest, 6);
    MUST(retry_create == RES_OK || retry_create == RES_PATH_EXISTS);
    EXPECT(write_save("NEWnew") == RES_OK && h_fs_Commit("save") == RES_OK && !strcmp(content(canonical), "NEWnew"), "full rewrite retries successfully after failed creation rollback");
}
static void readonly_path(void) {
    char p[1400]; snprintf(p, sizeof p, "%s/\\KINGDOM HEARTS HD 1.5+2.5 ReMIX\\KHIIFM.png", save); put(p, "STALEflat");
    setenv("DM_TEST_FS_FAILAT", "mountclone:1", 1); remount();
    printf("OBS slash=%s\n", read_guest(guest));
    printf("OBS backslash=%s alerts=%d\n", read_guest(backslash), g_nfail);
    EXPECT(!strcmp(read_guest(guest), "OLDold"), "read-only fallback reads canonical save by slash spelling");
    EXPECT(!strcmp(read_guest(backslash), "OLDold"), "read-only fallback preserves canonical backslash mapping instead of stale flat save");
    MUST(!unlink(p));
    EXPECT(!strcmp(read_guest(backslash), "OLDold"), "read-only canonical lookup does not need a flat alias");
}
static void failed_write_open(void) {
    MUST(h_fs_DeleteFile(guest) == RES_OK); MUST(h_fs_CreateFile(guest, 6) == RES_OK);
    uint64_t h = 0; write_open_fail = 1;
    EXPECT(h_fs_OpenFile(&h, guest, MODE_WRITE) != RES_OK && !h, "replacement write-open I/O failure leaves null output handle");
    EXPECT(h_fs_WriteFile(h, 0, "NEWnew", 6, NULL) != RES_OK, "null write is rejected");
    EXPECT(h_fs_Commit("save") != RES_OK && !strcmp(content(canonical), "OLDold"), "failed writable open cannot publish empty replacement");
    EXPECT(g_nfail == 1, "failed writable open transaction notifies front end");
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
static void rollback_retry_handle(void) {
    uint64_t h = open_write(); io_mode = 1;
    MUST(h_fs_WriteFile(h, 0, "BADbad", 6, NULL) != RES_OK); io_mode = 0;
    setenv("DM_TEST_FS_FAILAT", "reclone:1", 1);
    EXPECT(h_fs_Commit("save") != RES_OK, "failed rollback clone refuses commit");
    EXPECT(h_fs_WriteFile(h, 0, "NEXT22", 6, NULL) == RES_OK, "failed rollback does not invalidate still-linked work handle");
    EXPECT(h_fs_Commit("save") != RES_OK && !strcmp(content(canonical), "OLDold"), "retry still refuses poisoned work and restores old generation");
    EXPECT(h_fs_WriteFile(h, 0, "BADbad", 6, NULL) != RES_OK && h_fs_FlushFile(h) != RES_OK, "successful retry rollback invalidates old handle");
    h_fs_CloseFile(h); unsetenv("DM_TEST_FS_FAILAT");
    EXPECT(write_save("NEWnew") == RES_OK && h_fs_Commit("save") == RES_OK, "new full transaction commits after failed/successful rollback sequence");
}
static void stale_edges(void) {
    uint64_t h = open_write(), reader = 0;
    MUST(h_fs_OpenFile(&reader, guest, MODE_READ) == RES_OK);
    io_mode = 1; MUST(h_fs_WriteFile(h, 0, "BADbad", 6, NULL) != RES_OK); io_mode = 0;
    MUST(h_fs_Commit("save") != RES_OK);
    int64_t size = -1; size_t n = 0; char b[8];
    EXPECT(h_fs_ReadFile(&n, reader, 0, b, 6) != RES_OK, "rollback invalidates old read handle");
    EXPECT(h_fs_GetFileSize(&size, h) != RES_OK, "rollback invalidates old get-size handle");
    EXPECT(h_fs_SetFileSize(h, 1) != RES_OK && h_fs_WriteFile(h, 0, "x", 1, NULL) != RES_OK && h_fs_FlushFile(h) != RES_OK, "stale resize/write/flush are rejected");
    int unrelated = open("/dev/null", O_RDONLY); MUST(unrelated >= 0);
    EXPECT(unrelated != (int)h, "rollback leaves stale descriptor owned until explicit close (no FD reuse window)");
    h_fs_CloseFile(reader); h_fs_CloseFile(h);
    EXPECT(fcntl(unrelated, F_GETFD) >= 0, "stale close does not close another host descriptor"); close(unrelated);
    uint64_t fresh = open_write();
    EXPECT((int)fresh == (int)h, "fixture reuses closed numeric FD for a fresh file handle");
    EXPECT(h_fs_WriteFile(h, 0, "BADbad", 6, NULL) != RES_OK, "old token cannot write reused FD");
    h_fs_CloseFile(h);
    EXPECT(h_fs_WriteFile(fresh, 0, "NEWnew", 6, NULL) == RES_OK, "old close cannot close fresh reused FD");
    h_fs_CloseFile(fresh);
    EXPECT(h_fs_Commit("save") == RES_OK && !strcmp(content(canonical), "NEWnew"), "fresh retry works after stale handle rejection");
}
static void benign_exists(void) {
    EXPECT(h_fs_CreateFile(guest, 6) == RES_PATH_EXISTS, "existing file probe returns PathExists");
    EXPECT(h_fs_CreateDirectory("save:/KINGDOM HEARTS HD 1.5+2.5 ReMIX") == RES_PATH_EXISTS, "existing directory probe returns PathExists");
    uint64_t h = 0;
    EXPECT(h_fs_OpenFile(&h, "save:/missing", MODE_WRITE) == RES_PATH_NOT_FOUND, "non-mutating missing-file open remains a valid probe");
    EXPECT(h_fs_DeleteFile("save:/missing") == RES_PATH_NOT_FOUND, "missing-file delete remains a valid probe");
    EXPECT(h_fs_WriteFile(0, 0, "x", 1, NULL) != RES_OK && h_fs_SetFileSize(0, 1) != RES_OK, "unattributable null mutations fail without poisoning unrelated save");
    EXPECT(write_save("NEWnew") == RES_OK && h_fs_Commit("save") == RES_OK, "benign probes do not poison a successful rewrite");
    EXPECT(!strcmp(content(canonical), "NEWnew") && !g_nfail, "benign probes preserve bytes and send no error notice");
}
static void healthy_handle(void) {
    uint64_t h = open_write();
    MUST(h_fs_WriteFile(h, 0, "FIRST1", 6, NULL) == RES_OK);
    EXPECT(h_fs_Commit("save") == RES_OK, "healthy commit with live handle remains supported");
    EXPECT(h_fs_WriteFile(h, 0, "NEXT22", 6, NULL) == RES_OK && h_fs_FlushFile(h) == RES_OK, "healthy commit does not invalidate unchanged work generation");
    h_fs_CloseFile(h); EXPECT(h_fs_Commit("save") == RES_OK && !strcmp(content(canonical), "NEXT22"), "continued handle writes persist next transaction");
}
static void directory_failure(int name) {
    MUST(h_fs_DeleteFile(guest) == RES_OK);
    if (name) name_fail = 1; else mkdir_fail = 1;
    EXPECT(h_fs_CreateDirectory("save:/replacement") != RES_OK, "replacement directory I/O/metadata creation fails");
    EXPECT(h_fs_Commit("save") != RES_OK && !strcmp(content(canonical), "OLDold"), "failed directory creation refuses transaction with earlier deletion");
    EXPECT(g_nfail == 1, "failed directory transaction notifies front end");
}
static void poison_isolation(void) {
    char other[1200]; snprintf(other, sizeof other, "%s/other", root); MUST(!mkdir(other, 0700));
    MUST(h_fs_DeleteFile(guest) == RES_OK); truncate_fail = 1;
    MUST(h_fs_CreateFile(guest, 6) != RES_OK);
    MUST(mount_ex("other", other, 0, 1) == RES_OK);
    EXPECT(h_fs_Commit("other") == RES_OK, "independent healthy transaction does not consume another save's failure");
    EXPECT(h_fs_Commit("save") != RES_OK && !strcmp(content(canonical), "OLDold"), "mounting/committing another save cannot clear replacement failure poison");
    // Reset the independent alias subcase even on the known-red baseline.
    if (access(canonical, F_OK)) put(canonical, "OLDold");
    remount();
    MUST(mount_ex("alias", save, 0, 1) == RES_OK);
    uint64_t h = 0; MUST(h_fs_OpenFile(&h, guest, MODE_WRITE) == RES_OK);
    io_mode = 1; MUST(h_fs_WriteFile(h, 0, "BADbad", 6, NULL) != RES_OK); io_mode = 0;
    EXPECT(h_fs_Commit("alias") != RES_OK, "alias shares backing transaction's failure");
    EXPECT(h_fs_FlushFile(h) != RES_OK, "rollback through alias invalidates original mount handle");
    h_fs_CloseFile(h);
}
static void commit_error(int swap) {
    MUST(write_save("NEWnew") == RES_OK); if (swap == 1) swap_fail = 1; else clone_fail = 1;
    const char *names[] = {"save"};
    Result r = swap == 2 ? h_fs_CommitList(names, 1) : h_fs_Commit("save");
    printf("OBS commit=%#x alerts=%d errno=%d committed=%s\n", r, g_nfail, errno, content(canonical));
    EXPECT(r != RES_OK && !strcmp(content(canonical), "OLDold"), "snapshot/swap failure leaves committed bytes intact");
    EXPECT(g_nfail == 1, "snapshot/swap failure notifies front end that progress was not saved");
    EXPECT(g_lasterr == (swap == 1 ? EIO : ENOSPC), "callback preserves original publication errno despite cleanup");
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
    char flat[1400]; snprintf(flat, sizeof flat, "%s/\\KINGDOM HEARTS HD 1.5+2.5 ReMIX\\KHIIFM.png", save); put(flat, "STALEflat");
    remount(); EXPECT(!strcmp(read_guest(backslash), "OLDold"), "normal mount chooses canonical over distinct stale flat save");
    MUST(write_save("NEWnew") == RES_OK); MUST(h_fs_Commit("save") == RES_OK); remount();
    EXPECT(!strcmp(read_guest(backslash), "NEWnew"), "normal remount loads new canonical via backslash");
    EXPECT(!strcmp(content(flat), "STALEflat"), "normalization does not migrate or overwrite distinct flat file");
}
static void recursive_failure(int remove_dir) {
    char dir[1200], path[1300]; snprintf(dir, sizeof dir, "%s/cleanup", g_mnt[0].dir); MUST(!mkdir(dir, 0700));
    snprintf(path, sizeof path, "%s/remove", dir); put(path, "old-remove"); snprintf(path, sizeof path, "%s/keep", dir); put(path, "old-keep");
    MUST(h_fs_Commit("save") == RES_OK); unlink_fail = 1;
    Result clean = remove_dir ? h_fs_DeleteDirRec("save:/cleanup") : h_fs_CleanDirRec("save:/cleanup"); unlink_fail = 0;
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
    snprintf(p, sizeof p, "%s/\\KINGDOM HEARTS HD 1.5+2.5 ReMIX\\KHIIFM.png", save); put(p, "FLATonly");
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
    if (argc == 5 && !strcmp(argv[1], "cold-check")) {
        unsetenv("DM_TEST_FS_FAILAT"); unsetenv("DM_KH2_SAVE_FIX_MIGRATE");
        setenv("DM_SAVE", argv[2], 1); MUST(h_fs_MountSave("save", NULL) == RES_OK);
        const char *actual = read_guest(backslash);
        printf("COLD expected=%s actual=%s\n", argv[3], actual);
        int mismatch = strcmp(actual, argv[3]) != 0;
        if (!strncmp(argv[4], "recursive", 9)) {
            actual = read_guest("save:/cleanup/remove");
            printf("COLD recursive/remove expected=old-remove actual=%s\n", actual);
            mismatch |= strcmp(actual, "old-remove") != 0;
        }
        return mismatch;
    }
    if (argc == 4 && (!strcmp(argv[1], "real-roundtrip") || !strcmp(argv[1], "real-read"))) return real_copy(argv[1], argv[2], argv[3]);
    alarm(20); // Any lock-order regression fails instead of hanging the runner.
    if (argc != 2) return 2; setup();
    if (!strcmp(argv[1], "create-failure")) failed_create(0);
    else if (!strcmp(argv[1], "create-open-failure")) failed_create(1);
    else if (!strcmp(argv[1], "create-name-failure")) failed_create(2);
    else if (!strcmp(argv[1], "write-open-failure")) failed_write_open();
    else if (!strcmp(argv[1], "readonly-path")) readonly_path();
    else if (!strcmp(argv[1], "held-handle")) held_handle();
    else if (!strcmp(argv[1], "rollback-retry-handle")) rollback_retry_handle();
    else if (!strcmp(argv[1], "stale-edges")) stale_edges();
    else if (!strcmp(argv[1], "benign-exists")) benign_exists();
    else if (!strcmp(argv[1], "healthy-handle")) healthy_handle();
    else if (!strcmp(argv[1], "directory-failure")) directory_failure(0);
    else if (!strcmp(argv[1], "directory-name-failure")) directory_failure(1);
    else if (!strcmp(argv[1], "poison-isolation")) poison_isolation();
    else if (!strcmp(argv[1], "clone-failure")) commit_error(0);
    else if (!strcmp(argv[1], "list-clone-failure")) commit_error(2);
    else if (!strcmp(argv[1], "swap-failure")) commit_error(1);
    else if (!strcmp(argv[1], "concurrent-commit")) concurrent_commit();
    else if (!strcmp(argv[1], "short-io")) short_io();
    else if (!strcmp(argv[1], "resize-failure")) resize_failure();
    else if (!strcmp(argv[1], "crash-before-commit")) crash_test(0);
    else if (!strcmp(argv[1], "crash-before-swap")) crash_test(1);
    else if (!strcmp(argv[1], "crash-after-swap")) crash_test(2);
    else if (!strcmp(argv[1], "normal-aliases")) aliases();
    else if (!strcmp(argv[1], "recursive-failure")) recursive_failure(0);
    else if (!strcmp(argv[1], "recursive-delete-failure")) recursive_failure(1);
    else if (!strcmp(argv[1], "log-rotation-save")) log_rotation_save();
    else if (!strcmp(argv[1], "legacy-only")) legacy_only();
    else if (!strcmp(argv[1], "overloads")) overloads();
    else return 2;
    EXPECT(callback_locked == 0, "native failure callbacks run outside FS locks and permit re-entry");
    const char *expected = "OLDold";
    const char *c = argv[1];
    if (!strncmp(c, "create-", 7) || !strcmp(c, "clone-failure") || !strcmp(c, "swap-failure") ||
        !strcmp(c, "short-io") || !strcmp(c, "normal-aliases") || !strcmp(c, "stale-edges") ||
        !strcmp(c, "benign-exists") || !strcmp(c, "crash-after-swap")) expected = "NEWnew";
    if (!strcmp(c, "rollback-retry-handle") || !strcmp(c, "list-clone-failure")) expected = "NEWnew";
    if (!strcmp(c, "healthy-handle")) expected = "NEXT22";
    if (!strcmp(c, "overloads")) expected = "LAST33";
    if (!strcmp(c, "log-rotation-save")) expected = "generation-99";
    if (!strcmp(c, "legacy-only")) expected = "<open failed>";
    fflush(NULL); pid_t cold = fork(); MUST(cold >= 0);
    if (!cold) { execl(argv[0], argv[0], "cold-check", save, expected, c, NULL); _exit(2); }
    int status; MUST(waitpid(cold, &status, 0) == cold);
    EXPECT(WIFEXITED(status) && WEXITSTATUS(status) == 0, "fresh exec/process normalized reopen returns expected committed bytes");
    printf("RESULT %s: %d checks, %d failed\n", argv[1], checks, failures);
    MUST(rm_tree(root) == 0); return failures ? 1 : 0;
}
