// R1 seam tests: real transactions + narrow one-shot host failures. No fake commit.
#include <dirent.h>
#include <unistd.h>
#include <stdio.h>
#include <sys/stat.h>
#include <sys/xattr.h>
#include <errno.h>
#include <string.h>
static DIR *seam_opendir(const char *);
static struct dirent *seam_readdir(DIR *);
static int seam_closedir(DIR *);
static ssize_t seam_getxattr(const char *, const char *, void *, size_t, unsigned, int);
static int seam_lstat(const char *, struct stat *);
static int seam_access(const char *, int);
static int seam_rename(const char *, const char *);
static int seam_rmdir(const char *);
static int seam_fstat(int, struct stat *);
static ssize_t seam_pread(int, void *, size_t, off_t);
#define opendir seam_opendir
#define readdir seam_readdir
#define closedir seam_closedir
#define getxattr seam_getxattr
#define lstat seam_lstat
#define access seam_access
#define rename seam_rename
#define rmdir seam_rmdir
#define fstat seam_fstat
#define pread seam_pread
#define main supplied_harness_main
#include "t_fs_save_adversarial.c"
#undef main
#undef opendir
#undef readdir
#undef closedir
#undef getxattr
#undef lstat
#undef access
#undef rename
#undef rmdir
#undef fstat
#undef pread

static const char *fault;
static int remaining, hit, fault_errno = EIO, clobber;
static int lookup_count, first_lookup;
static int inject(const char *which) {
    if (lookup_count >= first_lookup && fault && !strcmp(fault, which) && --remaining == 0) {
        hit++; errno = fault_errno; return 1;
    }
    return 0;
}
static int independent_repeat_opendir;
static DIR *seam_opendir(const char *p) {
    if (independent_repeat_opendir) { hit++; errno=EIO; return NULL; }
    lookup_count++;
    if (inject("opendir")) return NULL;
    return opendir(p);
}
static struct dirent *seam_readdir(DIR *d) {
    if (inject("readdir")) return NULL;
    return readdir(d);
}
static int seam_closedir(DIR *d) {
    int r = closedir(d);
    if (inject("closedir")) return -1;
    if (clobber) errno = ENOENT; // cleanup must not replace the real lookup error
    return r;
}
static ssize_t seam_getxattr(const char *p, const char *n, void *v, size_t s, unsigned pos, int opts) {
    if (inject("getxattr")) return -1;
    return getxattr(p, n, v, s, pos, opts);
}
static int seam_lstat(const char *p, struct stat *s) {
    if (inject("lstat")) return -1;
    return lstat(p, s);
}
static int seam_access(const char *p, int mode) {
    if (inject("access")) return -1;
    return access(p, mode);
}
static int seam_rename(const char *a, const char *b) {
    if (inject("rename")) return -1;
    return rename(a, b);
}
static int seam_rmdir(const char *p) {
    if (inject("rmdir")) return -1;
    return rmdir(p);
}
static int seam_fstat(int fd, struct stat *s) {
    if (inject("fstat")) return -1;
    return fstat(fd, s);
}
static ssize_t seam_pread(int fd, void *buf, size_t n, off_t off) {
    if (inject("pread")) return -1;
    return pread(fd, buf, n, off);
}
static void arm(const char *f, int nth, int error) {
    fault = f; remaining = 1; fault_errno = error; hit = 0;
    lookup_count = 0; first_lookup = nth;
}
static void disarm(void) { fault = NULL; clobber = 0; }
static int cold(const char *exe, const char *expected) {
    fflush(NULL); pid_t p = fork(); MUST(p >= 0);
    if (!p) { execl(exe, exe, "cold-check", save, expected, "path-seam", NULL); _exit(2); }
    int s; MUST(waitpid(p, &s, 0) == p);
    return WIFEXITED(s) && !WEXITSTATUS(s);
}
static const char *node = "save:/KINGDOM HEARTS HD 1.5+2.5 ReMIX/node";
static const char *dest = "save:/KINGDOM HEARTS HD 1.5+2.5 ReMIX/new";
static Result operation(const char *op) {
    uint64_t h = 0; Result r;
    if (!strcmp(op, "create")) return h_fs_CreateFile(dest, 6);
    if (!strcmp(op, "mkdir")) return h_fs_CreateDirectory(dest);
    if (!strcmp(op, "delete")) return h_fs_DeleteFile(guest);
    if (!strcmp(op, "rmdir")) return h_fs_DeleteDir(node);
    if (!strcmp(op, "clean")) return h_fs_CleanDirRec(node);
    if (!strcmp(op, "recursive")) return h_fs_DeleteDirRec(node);
    if (!strncmp(op, "rename-file", 11)) return h_fs_RenameFile(guest, dest);
    if (!strncmp(op, "rename-dir", 10)) return h_fs_RenameDir(node, dest);
    if (!strcmp(op, "stat")) { int32_t type; return h_fs_GetEntryType(&type, guest); }
    if (!strcmp(op, "read-dir")) {
        r = h_fs_OpenDirectory(&h, node, DIRMODE_FILE); if (!r) h_fs_CloseDirectory(h); return r;
    }
    int mode = !strcmp(op, "read") ? MODE_READ : !strcmp(op, "append") ? MODE_APPEND : !strcmp(op, "readwrite") ? MODE_READ | MODE_WRITE : MODE_WRITE;
    r = h_fs_OpenFile(&h, guest, mode); if (!r) h_fs_CloseFile(h); return r;
}
static void seams(const char *exe, const char *op, const char *f) {
    // Physical alias forces metadata lookup even before the first path component
    // completes, without needing a complete physical target for attribution.
    char old[1400], alias[1400];
    snprintf(old, sizeof old, "%s/KINGDOM HEARTS HD 1.5+2.5 ReMIX", g_mnt[0].dir);
    snprintf(alias, sizeof alias, "%s/.dm-case-1", g_mnt[0].dir);
    MUST(!rename(old, alias));
    snprintf(canonical, sizeof canonical, "%s/.dm-case-1/" KH_TEST_SAVE_FILE "", save);
    const char *label = "KINGDOM HEARTS HD 1.5+2.5 ReMIX";
    MUST(!setxattr(alias, FS_GUEST_NAME, label, strlen(label), 0, XATTR_NOFOLLOW));
    MUST(h_fs_CreateDirectory(node) == RES_OK);
    MUST(h_fs_Commit("save") == RES_OK);
    MUST(write_save("BADbad") == RES_OK);
    int nth = 1;
    if (strstr(op, "-dst")) nth = 3; // two source components, then first destination component
    const char *actual_fault = f;
    if (!strcmp(f, "opendir2")) { actual_fault = "opendir"; nth++; }
    arm(actual_fault, nth, !strcmp(f, "opendir2") ? EMFILE : EIO);
    if (!strcmp(f, "getxattr") || !strcmp(f, "readdir")) clobber = 1;
    Result r = operation(op);
    int exercised = hit, error = fault_errno;
    disarm();
    int readonly = !strcmp(op, "read") || !strcmp(op, "stat") || !strcmp(op, "read-dir");
    EXPECT(exercised == 1, "exact intended host seam was faulted once");
    EXPECT(r != RES_OK, "host lookup/resource failure reaches guest (not missing-as-success)");
    EXPECT(REVIEW_POISON == (readonly ? 0 : error), "only mutating lookup poisons attributable transaction with original errno");
    Result c = h_fs_Commit("save");
    EXPECT(readonly ? c == RES_OK : c != RES_OK, "commit accepts read-only error but refuses failed mutation");
    const char *expected = readonly ? "BADbad" : "OLDold";
    EXPECT(!strcmp(content(canonical), expected), "committed bytes match complete expected generation");
    EXPECT(g_nfail == (readonly ? 0 : 1) && (!g_nfail || g_lasterr == error), "failure notification preserves original errno without false read-only alert");
    EXPECT(callback_locked == 0, "native notification runs outside both FS locks");
    EXPECT(cold(exe, expected), "fresh exec reads exact committed bytes via normalized guest path");
}
static void probes(const char *exe) {
    MUST(write_save("NEWnew") == RES_OK);
    uint64_t h = 0;
    EXPECT(h_fs_OpenFile(&h, "save:/absent/child", MODE_WRITE) == RES_PATH_NOT_FOUND, "missing intermediate component is benign");
    EXPECT(h_fs_CreateFile("save:/absent/child", 0) == RES_PATH_NOT_FOUND, "create with missing parent is benign");
    EXPECT(h_fs_CreateDirectory("save:/absent/child") == RES_PATH_NOT_FOUND, "mkdir with missing parent is benign");
    EXPECT(h_fs_RenameFile(guest, "save:/absent/child") == RES_PATH_NOT_FOUND, "rename with missing destination parent is benign");
    EXPECT(h_fs_RenameFile(guest, guest) == RES_PATH_EXISTS, "existing destination probe is benign");
    EXPECT(h_fs_CreateFile(guest, 6) == RES_PATH_EXISTS, "existing create probe is benign");
    EXPECT(h_fs_DeleteDir("save:/absent") == RES_PATH_NOT_FOUND, "missing directory delete is benign");
    EXPECT(h_fs_CleanDirRec("save:/absent") == RES_PATH_NOT_FOUND, "missing recursive-clean path is benign");
    EXPECT(h_fs_DeleteDirRec("save:/absent") == RES_PATH_NOT_FOUND, "missing recursive-delete path is benign");
    EXPECT(h_fs_OpenFile(&h, "save:/KINGDOM HEARTS HD 1.5+2.5 ReMIX", MODE_WRITE) != RES_OK, "opening directory as file is benign");
    EXPECT(h_fs_CreateFile("save:/../outside", 0) == RES_PATH_NOT_FOUND, "lexically invalid above-root path is benign");
    char overlong[1200]; memset(overlong, 'x', sizeof overlong); memcpy(overlong, "save:/", 6); overlong[sizeof overlong - 1] = 0;
    EXPECT(h_fs_CreateFile(overlong, 0) != RES_OK, "oversized guest name fails without poisoning another valid rewrite");
    arm("opendir", 1, EIO);
    EXPECT(h_fs_CreateFile("unknown:/x", 0) != RES_OK && hit == 0, "unmounted identity does not touch another mount"); disarm();
    EXPECT(!REVIEW_POISON && h_fs_Commit("save") == RES_OK && !g_nfail, "benign probes never poison or notify");
    EXPECT(cold(exe, "NEWnew"), "benign probes permit exact successful fresh-process rewrite");
}
static void readonly_read(const char *exe) {
    MUST(write_save("NEWnew") == RES_OK);
    uint64_t h = 0; MUST(h_fs_OpenFile(&h, guest, MODE_READ) == RES_OK);
    arm("pread", 0, EIO); char b[8]; size_t got = 0;
    Result r = h_fs_ReadFile(&got, h, 0, b, 6); disarm(); h_fs_CloseFile(h);
    EXPECT(r != RES_OK && hit == 1, "read-only data I/O error reaches guest");
    EXPECT(!REVIEW_POISON && h_fs_Commit("save") == RES_OK && !g_nfail, "read-only data I/O does not poison successful independent rewrite");
    EXPECT(cold(exe, "NEWnew"), "read-only data error leaves acknowledged rewrite intact after exec");
}
static void isolation(const char *exe, int use_alias) {
    char other[1200], otherfile[1300];
    snprintf(other, sizeof other, "%s/independent", root); MUST(!mkdir(other, 0700));
    snprintf(otherfile, sizeof otherfile, "%s/value", other); put(otherfile, "OTHER0");
    MUST(mount_ex("save2", other, 0, 1) == RES_OK);
    MUST(mount_ex("alias", save, 0, 1) == RES_OK);
    MUST(write_save("BADbad") == RES_OK);
    uint64_t h = 0; MUST(h_fs_OpenFile(&h, "save2:/value", MODE_WRITE) == RES_OK);
    MUST(h_fs_WriteFile(h, 0, "OTHER1", 6, NULL) == RES_OK); h_fs_CloseFile(h);
    arm("opendir", 1, ENOMEM);
    Result r = h_fs_CreateFile(use_alias ? "alias:/new" : backslash, 6);
    disarm();
    EXPECT(r != RES_OK && hit == 1, "failed lookup is attributable by exact mount identity including alias/backslash");
    EXPECT(h_fs_Commit("save2") == RES_OK && !strcmp(content(otherfile), "OTHER1"), "independent prefix-sharing mount commits its own bytes");
    EXPECT(REVIEW_POISON == ENOMEM, "independent commit cannot consume other transaction's lookup error");
    EXPECT(h_fs_Commit(use_alias ? "save" : "alias") != RES_OK && !strcmp(content(canonical), "OLDold"), "both mount aliases share rollback poison");
    EXPECT(g_nfail == 1 && g_lasterr == ENOMEM && !callback_locked, "resource failure notifies once outside locks");
    EXPECT(cold(exe, "OLDold"), "isolated rollback preserves exact old bytes after fresh exec");
}
static int r1_supplied_main(int argc, char **argv) {
    if (argc == 5 && !strcmp(argv[1], "cold-check")) return supplied_harness_main(argc, argv);
    alarm(20); setup();
    if (argc == 4 && !strcmp(argv[1], "seam")) seams(argv[0], argv[2], argv[3]);
    else if (argc == 2 && !strcmp(argv[1], "probes")) probes(argv[0]);
    else if (argc == 2 && !strcmp(argv[1], "isolation")) isolation(argv[0], 0);
    else if (argc == 2 && !strcmp(argv[1], "alias")) isolation(argv[0], 1);
    else if (argc == 2 && !strcmp(argv[1], "readonly-read")) readonly_read(argv[0]);
    else return 2;
    printf("RESULT path-seam-%s%s%s: %d checks, %d failed\n", argv[1], argc == 4 ? ":" : "", argc == 4 ? argv[2] : "", checks, failures);
    MUST(!rm_tree(root)); return failures ? 1 : 0;
}

// Independent supplemental checks: do not replace any supplied expectations.
int main(int argc, char **argv) {
    if (argc == 5 && !strcmp(argv[1], "cold-check")) return supplied_harness_main(argc, argv);
    alarm(20); setup(); MUST(argc == 2);
    const char *case_name = argv[1];
    if (!strcmp(case_name, "cross-dst-lookup") || !strcmp(case_name, "cross-access") || !strcmp(case_name, "cross-rename") || !strcmp(case_name, "cross-src-lookup")) {
        char other[1200], otherfile[1300];
        snprintf(other,sizeof other,"%s/independent",root); MUST(!mkdir(other,0700));
        snprintf(otherfile,sizeof otherfile,"%s/value",other); put(otherfile,"OTHER0");
        MUST(mount_ex("save2",other,0,1)==RES_OK);
        MUST(write_save("BADbad")==RES_OK);
        uint64_t h=0; MUST(h_fs_OpenFile(&h,"save2:/value",MODE_WRITE)==RES_OK);
        MUST(h_fs_WriteFile(h,0,"OTHER1",6,NULL)==RES_OK); h_fs_CloseFile(h);
        int src = !strcmp(case_name,"cross-src-lookup");
        arm(src || !strcmp(case_name,"cross-dst-lookup") ? "opendir" : !strcmp(case_name,"cross-access") ? "access" : "rename", src ? 1 : !strcmp(case_name,"cross-dst-lookup") ? 3 : 0,EIO);
        Result r=h_fs_RenameFile(guest,"save2:/new"); disarm();
        EXPECT(hit==1 && r!=RES_OK,"cross-mount exact rename failure exercised");
        EXPECT(REVIEW_POISON==EIO,"failed mutation attributed to exact source");
        EXPECT(atomic_load(&g_save_poison[save_owner(1)])==(src?0:EIO),"destination poisoned only once rename reaches its lookup/probe/syscall");
        EXPECT(h_fs_Commit("save2")== (src?RES_OK:RES_FAIL),"destination commit obeys relevant endpoint poison");
        EXPECT(!strcmp(content(otherfile),src?"OTHER1":"OTHER0"),"destination preserves expected complete generation");
        EXPECT(h_fs_Commit("save")!=RES_OK,"source refuses failed mutation");
        EXPECT(!strcmp(content(canonical),"OLDold"),"source preserves old bytes");
        EXPECT(g_nfail==(src?1:2) && g_lasterr==EIO && !callback_locked,"notifications preserve errno and run unlocked");
        EXPECT(cold(argv[0],"OLDold"),"source readback in fresh exec");
    } else if (!strcmp(case_name,"nontransactional") || !strcmp(case_name,"readonly")) {
        char other[1200], otherfile[1300];
        snprintf(other,sizeof other,"%s/other",root); MUST(!mkdir(other,0700));
        snprintf(otherfile,sizeof otherfile,"%s/value",other); put(otherfile,"OTHER0");
        int ro=!strcmp(case_name,"readonly");
        MUST(mount("save2",other,ro)==RES_OK); MUST(write_save("NEWnew")==RES_OK);
        // Fail both indexed and fallback lookups for RO; ordinary nontransactional
        // lookup uses one. Always return actual syscall-shaped error, never fake success.
        arm("opendir",1,EIO); independent_repeat_opendir=ro;
        uint64_t h=0; Result r=ro ? h_fs_OpenFile(&h,"save2:/value",MODE_WRITE) : h_fs_CreateFile("save2:/new",6); independent_repeat_opendir=0; disarm();
        EXPECT(hit==(ro?2:1) && r!=RES_OK,"other-mount lookup failure exercised");
        EXPECT(!REVIEW_POISON,"prefix-sharing unrelated mount does not poison save");
        EXPECT(h_fs_Commit("save")==RES_OK && !g_nfail,"healthy save publishes despite unrelated mount error");
        EXPECT(cold(argv[0],"NEWnew"),"healthy save exact cold bytes");
    } else if (!strncmp(case_name,"benign-",7)) {
        int errors[]={ENOENT,ENOTDIR,EEXIST,EISDIR,ENOTEMPTY,ENAMETOOLONG,EINVAL};
        int which=atoi(case_name+7); MUST(which>=0 && which<7);
        MUST(write_save("NEWnew")==RES_OK); arm("opendir",1,errors[which]);
        Result r=h_fs_CreateFile("save:/new",6); disarm();
        EXPECT(hit==1 && r!=RES_OK,"benign errno exercised at early mutation lookup");
        EXPECT(!REVIEW_POISON,"documented benign errno is not transaction poison");
        EXPECT(h_fs_Commit("save")==RES_OK && !g_nfail,"benign failure permits healthy pending rewrite");
        EXPECT(cold(argv[0],"NEWnew"),"benign failure preserves acknowledged full rewrite");
    } else return 2;
    printf("RESULT independent-%s: %d checks, %d failed\n",case_name,checks,failures);
    MUST(!rm_tree(root)); return failures?1:0;
}
