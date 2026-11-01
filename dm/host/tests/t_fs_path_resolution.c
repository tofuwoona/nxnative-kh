// Review-only extension: inject one real host name-resolution failure,
// before repaired Create/OpenFile reach their syscall/poison branches.
#include <dirent.h>
static DIR *review_opendir(const char *);
#define opendir review_opendir
#define main supplied_harness_main
#include "t_fs_save_adversarial.c"
#undef main
#undef opendir
static int resolution_fail;
static DIR *review_opendir(const char *p) {
    if (resolution_fail && strstr(p, ".work")) {
        resolution_fail = 0; errno = EIO; return NULL;
    }
    return opendir(p);
}
int main(int argc, char **argv) {
    // A fresh exec must use the exact production mount/read path.
    if (argc == 5 && !strcmp(argv[1], "cold-check")) return supplied_harness_main(argc, argv);
    alarm(20); setup();
    MUST(h_fs_DeleteFile(guest) == RES_OK);
    int opening = argc == 2 && !strcmp(argv[1], "open");
    if (opening) MUST(h_fs_CreateFile(guest, 6) == RES_OK);
    resolution_fail = 1;
    uint64_t h = 0;
    Result r = opening ? h_fs_OpenFile(&h, guest, MODE_WRITE) : h_fs_CreateFile(guest, 6);
    int poison = REVIEW_POISON;
    Result c = h_fs_Commit("save");
    printf("OBS path-%s=%#x poison=%d commit=%#x alerts=%d committed=%s\n", opening ? "open" : "create", r, poison, c, g_nfail, content(canonical));
    struct stat committed_stat;
    if (!stat(canonical, &committed_stat)) {
        unsigned char bytes[6]; FILE *raw = fopen(canonical, "rb"); MUST(raw);
        size_t count = fread(bytes, 1, sizeof bytes, raw); fclose(raw);
        printf("RAW committed_size=%lld hex=", (long long)committed_stat.st_size);
        for (size_t i = 0; i < count; i++) printf("%02x", bytes[i]);
        printf("\n");
    }
    EXPECT(r != RES_OK && !resolution_fail, "injected path opendir EIO was exercised");
    EXPECT(c != RES_OK, "path-resolution I/O failure must refuse replacement transaction");
    EXPECT(!strcmp(content(canonical), "OLDold"), "old committed bytes survive failed replacement path resolution");
    fflush(NULL); pid_t child = fork(); MUST(child >= 0);
    if (!child) { execl(argv[0], argv[0], "cold-check", save, "OLDold", "path-failure", NULL); _exit(2); }
    int status; MUST(waitpid(child, &status, 0) == child);
    EXPECT(WIFEXITED(status) && !WEXITSTATUS(status), "fresh process preserves complete old save");
    printf("RESULT path-resolution-%s: %d checks, %d failed\n", opening ? "open" : "create", checks, failures);
    MUST(!rm_tree(root)); return failures ? 1 : 0;
}
