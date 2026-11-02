// Independently pinned Program1 registry fixture; synthetic instructions only.
#include "../hle_kh2_save.c"
#include <assert.h>
#include <signal.h>
#include <sys/wait.h>
#include <unistd.h>
module_t g_mod[MAX_MOD]; int g_nmod=3;
pthread_key_t g_key18,g_keytls,g_keytlr,g_keygate;
int dm_thread_host_wait_begin(void){return 0;}void dm_thread_host_wait_end(int p){(void)p;}
uint32_t dm_fs_reject_save(const char *n,int e){(void)n;(void)e;return 1;}
static const uint32_t offsets[]={0,0x11110,0x10f50,0x12430,0x12530,0x126a0,0x12320,0x11df0,0x12af4,0x12c9c,0x12ca0,0x3e144,0x3dff0,0x3e030,0x3e040,0x3e04c,0x3e058,0x3e130,0x12cd0};
static const uint32_t words[]={0,0xa9ba7bfd,0xa9be7bfd,0xd10103ff,0xa9ba7bfd,0xa9ba7bfd,0xa9bb7bfd,0xd10283ff,0xd10543ff,0,0,0,0xd10243ff,0,0,0,0,0,0xa9bd7bfd};
static int iswrap(int i){return i<=8 || i==12 || i==18;}
static int gatearg(int i){return i==18?10:i==12?9:i<=8?i:i<=11?0x7f00+i-9:0x7f03+i-13;}
static uint32_t branch(uint64_t src,uint64_t dst){return 0x14000000|(((int64_t)(dst-src)/4)&0x3ffffff);}
static void put(uint64_t off,uint32_t w){memcpy(g_mod[0].base+off,&w,4);}
static uint64_t ret_for(int i){return 0x3200020+i*0x80;}
static void synthetic(void){
    module_t *m=g_mod;strcpy(m->name,"main");strcpy(m->build_id,"badf2faf580b712464365c4d529d92c9");
    strcpy(g_mod[1].name,"sdk");strcpy(g_mod[1].build_id,"bc204aae7319bab274894f1cc3f5da92");
    strcpy(g_mod[2].name,"subsdk1");strcpy(g_mod[2].build_id,"99e21f98a397434b534c1459fc38a2b8");
    m->size=0x3300000;m->base=calloc(1,m->size);m->text_end=0x2f0c00;m->patch_off=0x3200000;m->patch_len=0x1000;
    put(0x12c74,0x2a0003f7);put(0x12c78,0xb9406e62);put(0x12c7c,0x14000003);
    for(int i=1;i<=18;i++){
        uint64_t ret=ret_for(i);put(offsets[i],branch(offsets[i],ret-32));put(ret-32,0xa9bf7bfd);put(ret-4,0xd63f03c0);put(ret,0xa8c17bfd);
        if(iswrap(i)){put(ret+4,0xd65f03c0);put(ret+8,words[i]);put(ret+12,branch(ret+12,offsets[i]+4));}
        else put(ret+4,branch(ret+4,offsets[i]+4));
    }
}
static void regall(int skip){for(int i=1;i<=18;i++)if(i!=skip)
    dm_kh2_save_register(g_mod,(uintptr_t)g_mod[0].base+ret_for(i),iswrap(i)?"kh2wrap":"svc",gatearg(i),offsets[i]);}
static void child(int mode){
    if(mode==13)setenv("DM_PROGRAM_ID","010090C022978003",1);
    if(mode==14)setenv("DM_PROGRAM_ID","010090C022978001junk",1);
    if(mode==15)strcpy(g_mod[0].build_id,"e1bced80ffd14436980f7490b1d3c3e7");
    if(mode==16){g_mod[3]=g_mod[0];g_nmod=4;}
    if(mode==17)g_mod[0].patch_off=0x3201000;
    if(mode==18)setenv("DM_PROGRAM_ID","010090C022978001",1);
    if(mode==1)g_mod[0].build_id[0]='f';
    if(mode==2)g_mod[1].build_id[0]='f';
    if(mode==3)g_mod[2].build_id[0]='f';
    if(mode==4)g_nmod=1;
    if(mode==5){g_mod[3]=g_mod[1];g_nmod=4;}
    if(mode==6)put(ret_for(12)+8,0xd503201f);
    if(mode==7)put(ret_for(8)+12,0xd503201f);
    if(mode==8)put(ret_for(9)+4,0xd503201f);
    if(mode==9)g_mod[0].text_end=0x12c00;
    if(mode==10)g_mod[0].size=0x100000;
    if(mode==11)put(0x12c74,0x34000060);
    if(mode==12)dm_kh2_save_register(g_mod,(uintptr_t)g_mod[0].base+ret_for(1),"kh2wrap",1,0x2c040); // KH2 map on KH1
    regall(mode>=100 && mode<200?mode-100:0);
    if(mode>=200)dm_kh2_save_register(g_mod,(uintptr_t)g_mod[0].base+ret_for(mode-200),iswrap(mode-200)?"kh2wrap":"svc",gatearg(mode-200),offsets[mode-200]);
    dm_kh2_save_ready();_exit(0);
}
static void trial(int mode,int reject){pid_t p=fork();assert(p>=0);if(!p)child(mode);int st;assert(waitpid(p,&st,0)==p);
    if(reject)assert(WIFSIGNALED(st)&&WTERMSIG(st)==SIGABRT);else assert(WIFEXITED(st)&&WEXITSTATUS(st)==0);}
int main(void){synthetic();
    trial(0,0); // exact Program1 build/map must now activate, old source refuses
    trial(18,0);
    for(int i=1;i<=17;i++)trial(i,1);
    for(int i=1;i<=18;i++){trial(100+i,1);trial(200+i,1);}
    free(g_mod[0].base);puts("PASS exact Program1 gate set, each missing/duplicate, wrong builds/ranges/body/cross-profile controls");return 0;
}
