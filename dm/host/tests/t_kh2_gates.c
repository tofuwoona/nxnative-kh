// Exact metadata/build/site fail-closed CPU test. Synthetic bytes, never executable.
#include "../hle_kh2_save.c"
#include <assert.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>
module_t g_mod[MAX_MOD]; int g_nmod=3;
pthread_key_t g_key18,g_keytls,g_keytlr,g_keygate;
int dm_thread_host_wait_begin(void){return 0;}void dm_thread_host_wait_end(int p){(void)p;}
uint32_t dm_fs_reject_save(const char *n,int e){(void)n;(void)e;return 1;}
#ifndef DM_KH2_GATE_POLICY
static void dm_kh2_save_register(module_t *m,uint64_t ret,const char *kind,int arg,uint64_t orig){(void)m;(void)ret;(void)kind;(void)arg;(void)orig;}
static void dm_kh2_save_ready(void){}
#endif
static const uint32_t offsets[]={0,0x2c040,0x2be80,0x2d360,0x2d460,0x2d5d0,0x2d250,0x2cd20,0x2da24,0x2dbcc,0x2dbd0,0x41044,0x40ef0,0x40f30,0x40f40,0x40f4c,0x40f58,0x41030};
static const uint32_t words[]={0,0xa9ba7bfd,0xa9be7bfd,0xd10103ff,0xa9ba7bfd,0xa9ba7bfd,0xa9bb7bfd,0xd10283ff,0xd10543ff,0,0,0,0xd10243ff};
static int iswrap(int i){return i<=8 || i==12;}
static int gatearg(int i){return i==12?9:i<=8?i:i<=11?0x7f00+i-9:0x7f03+i-13;}
static uint32_t branch(uint64_t src,uint64_t dst){return 0x14000000|(((int64_t)(dst-src)/4)&0x3ffffff);}
static void put(uint64_t off,uint32_t w){memcpy(g_mod[0].base+off,&w,4);}
static uint64_t ret_for(int i){return 0xb00020+i*0x80;}
static void synthetic(void){
    module_t *m=g_mod;strcpy(m->name,"main");strcpy(m->build_id,"e1bced80ffd14436980f7490b1d3c3e7");
    strcpy(g_mod[1].name,"sdk");strcpy(g_mod[1].build_id,"bc204aae7319bab274894f1cc3f5da92");
    strcpy(g_mod[2].name,"subsdk1");strcpy(g_mod[2].build_id,"99e21f98a397434b534c1459fc38a2b8");
    m->size=0xc00000;m->base=calloc(1,m->size);m->text_end=0x401000;m->patch_off=0xb00000;m->patch_len=0x1000;
    put(0x2dba4,0x2a0003f7);put(0x2dba8,0xb9406e62);put(0x2dbac,0x14000003);
    for(int i=1;i<=17;i++){
        uint64_t ret=ret_for(i);put(offsets[i],branch(offsets[i],ret-32));put(ret-32,0xa9bf7bfd);put(ret-4,0xd63f03c0);put(ret,0xa8c17bfd);
        if(iswrap(i)){put(ret+4,0xd65f03c0);put(ret+8,words[i]);put(ret+12,branch(ret+12,offsets[i]+4));}
        else put(ret+4,branch(ret+4,offsets[i]+4));
    }
}
static void regall(int mode){
    for(int i=1;i<=17;i++){
        if(mode==1 && i==5)continue;
        if(mode==19 && i==17)continue;
        if((mode==8 && i>=12) || (mode>=9 && mode<=13 && i==mode+3))continue;
        uint64_t orig=offsets[i]+(mode==2 && i==8 ? 4:0);
        dm_kh2_save_register(g_mod,(uintptr_t)g_mod[0].base+ret_for(i),iswrap(i)?"kh2wrap":"svc",gatearg(i),orig);
    }
}
static void child(int mode){
    if(mode==3 || mode==6)g_mod[0].build_id[0]='f';
    if(mode==4)put(ret_for(8)+8,0xd503201f);
    if(mode==14)g_mod[1].build_id[0]='f';
    if(mode==15)g_mod[2].build_id[0]='f';
    if(mode==16)g_nmod=1;
    if(mode==17){g_mod[3]=g_mod[1];g_nmod=4;}
    if(mode==18)put(ret_for(12)+8,0xd503201f);
    if(mode!=5 && mode!=6)regall(mode);
    if(mode==7){dm_kh2_save_register(g_mod,(uintptr_t)g_mod[0].base+ret_for(9),"svc",INT32_MIN,offsets[9]);}
    dm_kh2_save_ready();_exit(0);
}
int main(void){
    synthetic();
    for(int mode=1;mode<=19;mode++){
        pid_t p=fork();assert(p>=0);if(!p)child(mode);int st;waitpid(p,&st,0);
        int refuses=mode<=4 || mode>=7 || (mode==5 && DM_GAME_PROGRAM_ID==0x010090C022978003ull);
        if(refuses)assert(WIFSIGNALED(st)&&WTERMSIG(st)==SIGABRT);
        else assert(WIFEXITED(st)&&WEXITSTATUS(st)==0);
    }
#if DM_GAME_PROGRAM_ID == 0x010090C022978003ull
    regall(0);dm_kh2_save_ready();
    g_mod[0].build_id[0]='f'; // already installed metadata cannot silently rebind
#else
    dm_kh2_save_ready(); // sibling with no repair metadata is untouched
#endif
    free(g_mod[0].base);puts("PASS title/build/site/missing-gate/body-byte fail-closed CPU metadata controls");return 0;
}
