// Exact KH1 Program 1 / KH2 Program 3 repair; original serializers and FS only.
// Historical kh2 symbols/kinds are ABI names, not permission to cross profiles.
#include "dm.h"
#include <errno.h>
#include <setjmp.h>

// Independent original-module VAs, not a constant delta from the other title.
#if DM_GAME_PROGRAM_ID == 0x010090C022978001ull
#define DM_KH1_ALT_WRAPPER 1
static const char k_main_build[]="badf2faf580b712464365c4d529d92c9";
enum { k_status=0x2458850, k_png_flag=0x3d86d0, k_min_size=0x30bee40,
       k_inverse=0x12c74, k_commit=0x2ef440, k_destroy=0x2e18d0,
       k_close=0x2f00a0, k_literal=0x30840d, k_wrap_count=10, k_last_gate=18 };
#else
static const char k_main_build[]="e1bced80ffd14436980f7490b1d3c3e7";
enum { k_status=0xa62d08, k_png_flag=0x54b000, k_min_size=0xa62d20,
       k_inverse=0x2dba4, k_commit=0x4001b0, k_destroy=0x351d40,
       k_close=0x3ff0c0, k_literal=0x417a83, k_wrap_count=9, k_last_gate=17 };
#endif

#define DM_KH2_GUARD 1
typedef uint64_t (*body_fn)(uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t);
static body_fn g_body[11];
static uint8_t *g_base;
int dm_thread_host_wait_begin(void);
void dm_thread_host_wait_end(int previous);

// One process-lifetime recursive exclusion domain: the original cache is global.
// Never destroy it while original guest worker/writer frames may still exist.
static pthread_once_t g_lock_once = PTHREAD_ONCE_INIT;
static pthread_mutex_t g_save_lock;
static __thread unsigned g_lock_depth;
static void lock_init(void) {
    pthread_mutexattr_t a;
    if (pthread_mutexattr_init(&a) || pthread_mutexattr_settype(&a, PTHREAD_MUTEX_RECURSIVE) ||
        pthread_mutex_init(&g_save_lock, &a)) die("KH2 save mutex init");
    pthread_mutexattr_destroy(&a);
}
static void save_lock(void) {
    pthread_once(&g_lock_once, lock_init);
    int old = dm_thread_host_wait_begin();
    int error = pthread_mutex_lock(&g_save_lock);
    dm_thread_host_wait_end(old);
    if (error) die("KH2 save mutex lock");
    g_lock_depth++;
}
static void save_unlock(void) {
    if (!g_lock_depth) die("KH2 unpaired save unlock");
    g_lock_depth--;
    if (pthread_mutex_unlock(&g_save_lock)) die("KH2 save mutex unlock");
}
typedef struct cache_state {
    void *object; int active, closing; pthread_t closer;
    struct cache_state *next;
} cache_state;
static cache_state *g_states;
static cache_state *state_for(void *o, int create) { // holds save lock
    for (cache_state *s=g_states; s; s=s->next) if (s->object==o) return s;
    if (!create || !o) return NULL;
    cache_state *s=calloc(1,sizeof *s); if (!s) die("KH2 cache state allocation");
    s->object=o; s->next=g_states; g_states=s; return s;
}
typedef struct record_ctx { unsigned char *object; int failed; struct record_ctx *previous; } record_ctx;
static __thread record_ctx *g_record;

typedef struct flush_ctx {
    unsigned char *object;
    int pending, committed, finished, success;
    struct flush_ctx *previous;
} flush_ctx;
static __thread flush_ctx *g_flush;
static uint32_t (*g_commit)(const char *);
uint32_t dm_fs_reject_save(const char *name, int error);

#define DM_KH2_PNG_BOUNDARY 1
// Host jmp_buf is NEVER passed to guest libpng/SDK longjmp. The only nonlocal
// return is a direct normal-thread callback, after fwrite (and its locks/HLE)
// has returned. All metadata/resources that change after setjmp live on heap.
typedef struct png_ctx {
    jmp_buf jump;
    void *file, *png, *info;
    void *key18, *keytls, *keytlr;
    flush_ctx *flush;
    struct png_ctx *previous;
    int armed;
} png_ctx;
static __thread png_ctx *g_png;
static void (*g_png_destroy)(void **,void **);
static int (*g_png_close)(void *);
static uint64_t call_body(int id,const uint64_t *r);
static void png_restore_tls(const png_ctx *c) {
    if (pthread_setspecific(g_key18,c->key18) || pthread_setspecific(g_keytls,c->keytls) ||
        pthread_setspecific(g_keytlr,c->keytlr)) die("KH2 PNG TLS restore");
}
static void png_error_return(void *png,const char *message) {
    (void)message;
    png_ctx *c=g_png;
    if (!c || !c->armed || !g_flush || c->flush!=g_flush || !png ||
        (c->png && c->png!=png)) die("KH2 PNG callback outside owned writer");
    // Creation itself may report an error before its return capture.
    if (!c->png) c->png=png;
    c->armed=0;
    longjmp(c->jump,1);
}
static void kh2_png_capture(int num,uint64_t *r) {
    png_ctx *c=g_png;
    if (c && (!c->armed || c->flush!=g_flush)) die("KH2 PNG capture context mismatch");
    switch (num) {
    case 0x7f03: r[19]=r[0]; if (c) c->file=(void *)(uintptr_t)r[0]; break;
    case 0x7f04: r[2]=c?(uintptr_t)png_error_return:0; break; // original mov x2,xzr outside flush
    case 0x7f05: r[21]=r[0]; if (c) c->png=(void *)(uintptr_t)r[0]; break;
    case 0x7f06: r[22]=r[0]; if (c) c->info=(void *)(uintptr_t)r[0]; break;
    case 0x7f07:
        r[0]=r[29]+0x18; // original add x0,x29,#0x18, before original destroy
        // Transfer ownership back to the original normal destroy/fclose tail.
        // A pathological callback during that cleanup must fail closed rather
        // than nonlocally re-enter cleanup with already-freed resources.
        if (c) { c->armed=0; c->file=NULL; c->png=NULL; c->info=NULL; }
        break;
    default: die("KH2 unknown PNG capture");
    }
}
static uint64_t kh2_png_original(const uint64_t *r) {
    if (!g_flush) return call_body(9,r); // other original PNG users unchanged
    if (g_png) die("KH2 nested PNG writer refused");
    png_ctx *const c=calloc(1,sizeof *c);
    if (!c) die("KH2 PNG boundary allocation");
    c->previous=g_png; c->flush=g_flush;
    c->key18=pthread_getspecific(g_key18);
    c->keytls=pthread_getspecific(g_keytls);
    c->keytlr=pthread_getspecific(g_keytlr);
    g_png=c;
    uint64_t result;
    if (!setjmp(c->jump)) {
        c->armed=1;
        result=call_body(9,r); // mapped ORIGINAL PNG writer and encoder/container
        c->armed=0; // normal original destroy/fclose already ran: no double cleanup
    } else {
        // Darwin restores host SP/FP, callee-saved GPRs/d8-d15. Guest x18 is
        // virtualized into TSD and is NOT covered by Darwin's jmp_buf. Restore
        // all guest thread-register slots before calling original guest cleanup.
        png_restore_tls(c);
        if (c->png) g_png_destroy(&c->png,&c->info);
        if (c->file) { void *file=c->file; c->file=NULL; (void)g_png_close(file); }
        png_restore_tls(c); // cleanup callees may also use virtual guest registers
        **(unsigned char **)(g_base+k_png_flag)=0;
        result=0; // serializer still runs original inverse and rejection tail
    }
    g_png=c->previous; free(c);
    return result;
}

// Invoked only after title/build/site validation by the private gate dispatcher.
// w23 holds PNG status, not length. The original inverse has already completed.
static void kh2_tail(int num, uint64_t *r) {
    if (num == 0x7f02) {
        unsigned char *flag = (void *)(uintptr_t)r[23];
        if ((uint32_t)r[0]) *flag = 0;
        r[0] = *flag;   // displaced ldrb w0,[x23]
        return;
    }
    unsigned char *o = (void *)(uintptr_t)r[19];
    if (!g_flush || g_flush->object != o) die("KH2 save tail outside original flush");
    if (num == 0x7f00) {
        if (g_flush->committed) die("KH2 duplicate publication in one flush");
        g_flush->committed = 1;
        // Reject logical encoder errors even when no host syscall poisoned the
        // transaction. This is the existing poison/rollback engine, not a writer.
        r[0] = r[23] == 1 && !g_flush->pending ? g_commit((const char *)(uintptr_t)r[0]) : dm_fs_reject_save("save", EIO);
    } else if (num == 0x7f01) {
        if (!g_flush->committed || g_flush->finished) die("KH2 unpaired flush result");
        g_flush->finished = 1;
        g_flush->success = !(uint32_t)r[0] && !g_flush->pending;
        o[0x68] = !g_flush->success;  // replace unconditional dirty clear
        if (!g_flush->success) *(int32_t *)(o+0x6c) = -1; // AFTER inverse
    } else die("unknown KH2 private save gate");
}

#define DM_KH2_GATE_POLICY 1
static void kh2_wrap(int id, uint64_t *r);
#if DM_GAME_PROGRAM_ID == 0x010090C022978001ull
static const struct { uint32_t off, word; } k_wrap[11] = {
    {0,0},{0x11110,0xa9ba7bfd},{0x10f50,0xa9be7bfd},{0x12430,0xd10103ff},
    {0x12530,0xa9ba7bfd},{0x126a0,0xa9ba7bfd},{0x12320,0xa9bb7bfd},
    {0x11df0,0xd10283ff},{0x12af4,0xd10543ff},{0x3dff0,0xd10243ff},
    {0x12cd0,0xa9bd7bfd}
};
static const uint32_t k_tail[8]={0x12c9c,0x12ca0,0x3e144,0x3e030,0x3e040,0x3e04c,0x3e058,0x3e130};
#else
static const struct { uint32_t off, word; } k_wrap[10] = {
    {0,0},{0x2c040,0xa9ba7bfd},{0x2be80,0xa9be7bfd},{0x2d360,0xd10103ff},
    {0x2d460,0xa9ba7bfd},{0x2d5d0,0xa9ba7bfd},{0x2d250,0xa9bb7bfd},
    {0x2cd20,0xd10283ff},{0x2da24,0xd10543ff},{0x40ef0,0xd10243ff}
};
static const uint32_t k_tail[8]={0x2dbcc,0x2dbd0,0x41044,0x40f30,0x40f40,0x40f4c,0x40f58,0x41030};
#endif
static uint64_t g_returns[19];
static module_t *g_save_module;
static int g_ready;
static uint32_t word_at(const void *p) { uint32_t w; memcpy(&w,p,4); return w; }
static uint32_t branch_word(uint64_t src,uint64_t dst) {
    int64_t d=(int64_t)(dst-src);
    if ((d&3) || d < -(1ll<<27) || d >= (1ll<<27)) die("KH2 branch out of range");
    return 0x14000000 | ((d/4)&0x3ffffff);
}
static int is_target(const module_t *m) {
    return (DM_GAME_PROGRAM_ID==0x010090C022978003ull || DM_GAME_PROGRAM_ID==0x010090C022978001ull) &&
           m && !strcmp(m->name,"main") && !strcmp(m->build_id,k_main_build);
}
// The SDK ProgramId override must agree with the compiled exact-address map.
// Parse strictly: strtoull alone accepts suffixes, signs and whitespace.
static void validate_program_id(void) {
    const char *s=getenv("DM_PROGRAM_ID");
    if (!s) return;
    if (strlen(s)!=16 || strspn(s,"0123456789abcdefABCDEF")!=16 ||
        strtoull(s,NULL,16)!=DM_GAME_PROGRAM_ID) die("KH save runtime ProgramId mismatch");
}
// Called once for each private gate after all modules have loaded/relocated.
// Metadata is tied to the containing module, original site AND emitted bytes.
void dm_kh2_save_register(module_t *m,uint64_t ret,const char *kind,int arg,uint64_t orig) {
    if (!is_target(m)) die("KH2 private gate has wrong title/module/build");
    validate_program_id();
    int wrap=!strcmp(kind,"kh2wrap");
    if ((wrap && (arg<1 || arg>k_wrap_count)) || (!wrap && (strcmp(kind,"svc") || arg<0x7f00 || arg>0x7f07))) die("KH2 unknown gate ID");
    int id=wrap ? (arg==10?18:arg==9?12:arg) : (arg<=0x7f02?arg-0x7f00+9:arg-0x7f03+13);
    if (g_ready || g_returns[id] || (g_save_module && g_save_module!=m)) die("KH2 duplicate/late gate registration");
    uint32_t off=wrap?k_wrap[arg].off:k_tail[arg-0x7f00];
    int64_t rel=(int64_t)(ret-(uintptr_t)m->base);
    uint64_t plen=m->patch_off<0?m->patch_len:m->size-(uint64_t)m->patch_off;
    if (orig!=off || off+4>m->text_end || m->size<k_min_size ||
        rel<m->patch_off+32 || rel+16>m->patch_off+(int64_t)plen) die("KH2 invalid gate site/range");
    const uint8_t *p=(const void *)(uintptr_t)ret;
    if (word_at(p-32)!=0xa9bf7bfd || word_at(p-4)!=0xd63f03c0 || word_at(p)!=0xa8c17bfd ||
        word_at(m->base+off)!=branch_word((uintptr_t)m->base+off,ret-32)) die("KH2 invalid gate entry/return bytes");
    if (wrap) {
        if (word_at(p+4)!=0xd65f03c0 || word_at(p+8)!=k_wrap[arg].word ||
            word_at(p+12)!=branch_word(ret+12,(uintptr_t)m->base+off+4)) die("KH2 invalid original-body trampoline");
        g_body[arg]=(body_fn)(uintptr_t)(ret+8);
    } else if (word_at(p+4)!=branch_word(ret+4,(uintptr_t)m->base+off+4)) die("KH2 invalid tail continuation");
    g_returns[id]=ret; g_save_module=m;
}
void dm_kh2_save_ready(void) {
    module_t *m=NULL;
    for (int i=0;i<g_nmod;i++) if (is_target(&g_mod[i])) m=&g_mod[i];
    if (!m) { if (g_save_module) die("KH2 private gates without exact main"); return; }
    validate_program_id();
    // The callback/unwind assumptions are audited against this complete title
    // build set, not arbitrary SDK stdio implementations with the same main.
    static const char *const names[]={"main","sdk","subsdk1"};
    const char *const builds[]={k_main_build,
        "bc204aae7319bab274894f1cc3f5da92","99e21f98a397434b534c1459fc38a2b8"};
    for (unsigned n=0;n<3;n++) {
        int count=0;
        for (int i=0;i<g_nmod;i++) if (!strcmp(g_mod[i].name,names[n])) {
            if (strcmp(g_mod[i].build_id,builds[n])) die("KH2 mismatched %s build",names[n]);
            count++;
        }
        if (count!=1) die("KH2 missing/duplicate %s module",names[n]);
    }
    for (int i=1;i<=k_last_gate;i++) if (!g_returns[i]) die("KH2 incomplete save repair gates (%d missing)",i);
    if (g_save_module!=m || word_at(m->base+k_inverse)!=0x2a0003f7 ||
        word_at(m->base+k_inverse+4)!=0xb9406e62 || word_at(m->base+k_inverse+8)!=0x14000003)
        die("KH2 missing positive-length unwind repair");
    g_base=m->base;
    g_commit=(uint32_t (*)(const char *))(m->base+k_commit); // ORIGINAL relocated PLT
    g_png_destroy=(void (*)(void **,void **))(m->base+k_destroy);
    g_png_close=(int (*)(void *))(m->base+k_close);
    g_ready=1;
}
// entry.S routes this call through dm_bigstack_enter. Calls of the guest body
// keep the same pthread/SDK TLS; nested HLE_FORCE_BIG sees the current host SP
// and does NOT reset/overwrite the outer host stack frame. No SVC frame is
// published around guest execution (its own nested real SVCs own those frames).
void dm_kh2_save_dispatch(uint64_t ret,uint64_t *r) {
    if (!g_ready || !is_target(g_save_module)) die("KH2 save gate before validation");
    validate_program_id();
    int id=1;while(id<=k_last_gate && g_returns[id]!=ret)id++;
    if (id>k_last_gate) die("KH2 unregistered private save gate");
    if (id<=8 || id==18) kh2_wrap(id==18?10:id,r);
    else if (id==12) r[0]=kh2_png_original(r);
    else if (id>=13) kh2_png_capture(0x7f03+id-13,r);
    else {
        if (!g_flush && id!=11) die("KH2 tail outside guarded serializer");
        if (id==11 && r[23]!=*(uint64_t *)(g_base+k_png_flag)) die("KH2 PNG flag mismatch");
        if (id==9 && r[0]!=(uintptr_t)(g_base+k_literal)) die("KH2 Commit literal mismatch");
        if (id==11 && !g_flush) r[0]=*(unsigned char *)(uintptr_t)r[23];
        else kh2_tail(0x7f00+id-9,r);
    }
}

static uint64_t call_body(int id, const uint64_t *r) {
    return g_body[id](r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7]);
}
static uint64_t flush_original(unsigned char *o) { // holds recursive save lock
    for (flush_ctx *p=g_flush; p; p=p->previous) if (p->object==o) {
        p->pending=1; return (uint32_t)-1; // never recursively transform
    }
    flush_ctx f={.object=o, .previous=g_flush}; g_flush=&f;
    uint64_t args[8]={(uintptr_t)o};
    uint64_t result=call_body(8,args); // original serializer entry trampoline
    g_flush=f.previous;
    if (!f.finished || !f.success || f.pending) {
        o[0x68]=1; *(int32_t *)(o+0x6c)=-1; return (uint32_t)-1;
    }
    return result;
}
static void kh2_wrap(int id, uint64_t *r) {
    save_lock();
    void *o=(void *)(uintptr_t)r[0];
    cache_state *s=(id==3 || id==10) ? NULL : state_for(o,id==1);
    if (id==1) {
        if (!s || s->closing || s->active) die("KH2 overlapping cache initialization");
        s->active=1;
        r[0]=call_body(id,r);
    } else if (id==10) {
#ifdef DM_KH1_ALT_WRAPPER
        // Original Program1 helper already writes+flushes at 12dec/12df8, but
        // its final 12dfc store hides failure. Keep the whole state step locked;
        // never add a second flush or change its returned state-machine value.
        if (g_flush) { g_flush->pending=1; *(int32_t *)(g_base+0x2458858)=-1; r[0]=3; }
        else {
            record_ctx c={.previous=g_record}; g_record=&c;
            r[0]=call_body(id,r);
            g_record=c.previous;
            if (c.failed) *(int32_t *)(g_base+0x2458858)=-1;
        }
#else
        die("KH1 helper on wrong profile");
#endif
    } else if (id==3) { // high-level write: original return ABI remains zero
        if (g_flush) { g_flush->pending=1; *(int32_t *)(g_base+k_status)=-1; r[0]=0; }
        else {
            record_ctx c={.previous=g_record}; g_record=&c;
            uint64_t result=call_body(id,r); // includes original final operation-status store
            g_record=c.previous;
            if (c.object && (int32_t)flush_original(c.object)<0) *(int32_t *)(g_base+k_status)=-1;
            r[0]=result; // do not trigger the original pre-return delete branch
        }
    } else if (!s || !s->active || (s->closing && !(id==8 && pthread_equal(s->closer,pthread_self())))) {
        r[0]=(uint32_t)-1;
    } else if (id==2) {
        if (g_flush || g_lock_depth!=1) die("KH2 reentrant teardown refused before worker join");
        {
            s->closing=1; s->closer=pthread_self();
            // Drain active cache calls before stop/join. New calls are refused.
            // The worker must be able to enter/reject serialization and exit.
            save_unlock();
            r[0]=call_body(id,r);
            save_lock(); s->active=0; s->closing=0;
        }
    } else if (id==8) r[0]=flush_original(o); // all original callers, including worker
    else if (g_flush) { g_flush->pending=1; r[0]=(uint32_t)-1; }
    else {
        r[0]=call_body(id,r);
        if (id==4 && g_record && (int32_t)r[0]>=0) g_record->object=o;
    }
    if (id==8 && g_record && (int32_t)r[0]<0) g_record->failed=1;
    save_unlock();
}
