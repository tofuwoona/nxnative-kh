// Both exact maps: exhaustive slot corruption plus non-target no-op controls.
#include "game_profile.h"
#define main metadata_main
#if DM_GAME_PROGRAM_ID == 0x010090C022978001ull
#include "t_kh1_gates.c"
#define LAST 18
#define REGISTER_ALL() regall(0)
#else
#include "t_kh2_gates.c"
#define LAST 17
#define REGISTER_ALL() regall(0)
#endif
#undef main
static int trials;
static void one(int slot,int mode,int reject){
    pid_t p=fork();assert(p>=0);
    if(!p){
        uint64_t ret=ret_for(slot);
        if(mode<5){
            uint64_t off=mode==0?ret-32:mode==1?ret-4:mode==2?ret:mode==3?ret+4:offsets[slot];
            put(off,0xd503201f);
        }
        if(mode==5 && iswrap(slot))put(ret+8,0xd503201f);
        if(mode==6)dm_kh2_save_ready(); // no gates for exact build must fail
        if(mode==7)strcpy(g_mod[0].name,"other");
        if(mode==8)strcpy(g_mod[0].build_id,DM_GAME_PROGRAM_ID==0x010090C022978001ull?"e1bced80ffd14436980f7490b1d3c3e7":"badf2faf580b712464365c4d529d92c9");
        if(mode==9)setenv("DM_PROGRAM_ID","",1);
        if(mode==10)setenv("DM_PROGRAM_ID"," 10090C022978001",1);
        if(mode==11)setenv("DM_PROGRAM_ID","+10090C022978001",1);
        if(mode==12)setenv("DM_PROGRAM_ID","0x0090C022978001",1);
        if(mode==13)setenv("DM_PROGRAM_ID","010090C022978002",1);
        if(mode==14)setenv("DM_PROGRAM_ID","010090C022978000",1);
        if(mode==15)setenv("DM_PROGRAM_ID","fffffffffffffffff",1);
        if(mode==16)setenv("DM_PROGRAM_ID",DM_GAME_PROGRAM_ID==0x010090C022978001ull?"010090c022978001":"010090c022978003",1);
        if(mode==17){dm_kh2_save_ready();_exit(0);} // non-target no metadata
        if(mode==18){g_mod[0].build_id[0]='f';dm_kh2_save_ready();_exit(0);}
        if(mode==19){REGISTER_ALL();dm_kh2_save_ready();setenv("DM_PROGRAM_ID","010090C022978002",1);
            uint64_t r[31]={0};dm_kh2_save_dispatch((uintptr_t)g_mod[0].base+ret,r);_exit(0);}
        if(mode==31){REGISTER_ALL();setenv("DM_PROGRAM_ID","010090C022978002",1);dm_kh2_save_ready();_exit(0);}
        if(mode==20)dm_kh2_save_register(g_mod,(uintptr_t)g_mod[0].base+ret,"kh2wrap",INT32_MAX,offsets[slot]);
        if(mode==21)dm_kh2_save_register(g_mod,(uintptr_t)g_mod[0].base+ret,"svc",0x7f08,offsets[slot]);
        if(mode==22)dm_kh2_save_register(g_mod,(uintptr_t)g_mod[0].base+ret+4,iswrap(slot)?"kh2wrap":"svc",gatearg(slot),offsets[slot]);
        if(mode==23)dm_kh2_save_register(g_mod,(uintptr_t)g_mod[0].base+ret,iswrap(slot)?"kh2wrap":"svc",gatearg(slot),offsets[slot]+4);
        if(mode==24){REGISTER_ALL();dm_kh2_save_ready();dm_kh2_save_register(g_mod,(uintptr_t)g_mod[0].base+ret,iswrap(slot)?"kh2wrap":"svc",gatearg(slot),offsets[slot]);}
        if(mode==28){
            for(int i=1;i<=LAST;i++)if(i!=slot)dm_kh2_save_register(g_mod,(uintptr_t)g_mod[0].base+ret_for(i),iswrap(i)?"kh2wrap":"svc",gatearg(i),offsets[i]);
            dm_kh2_save_ready();_exit(0);
        }
        if(mode==29)put(ret+12,0xd503201f);
        dm_kh2_save_register(g_mod,(uintptr_t)g_mod[0].base+ret,iswrap(slot)?"kh2wrap":"svc",gatearg(slot),offsets[slot]);
        if(mode==25)dm_kh2_save_register(g_mod,(uintptr_t)g_mod[0].base+ret,iswrap(slot)?"kh2wrap":"svc",gatearg(slot),offsets[slot]);
        if(mode==26){dm_kh2_save_ready();_exit(0);} // each single slot is incomplete
        _exit(0);
    }
    int st;assert(waitpid(p,&st,0)==p);trials++;
    if(reject)assert(WIFSIGNALED(st)&&WTERMSIG(st)==SIGABRT);
    else assert(WIFEXITED(st)&&WEXITSTATUS(st)==0);
}
int main(void){
    unsetenv("DM_PROGRAM_ID");synthetic();
    int target=DM_GAME_PROGRAM_ID==0x010090C022978001ull || DM_GAME_PROGRAM_ID==0x010090C022978003ull;
    if(target){
        for(int i=1;i<=LAST;i++){
            for(int m=0;m<5;m++)one(i,m,1);
            if(iswrap(i)){one(i,5,1);one(i,29,1);}
            for(int m=22;m<=26;m++)one(i,m,1);
            one(i,28,1);
        }
        for(int m=6;m<=15;m++)one(1,m,1);
        one(1,16,0);one(1,18,0);one(1,19,1);one(1,20,1);one(1,21,1);
        one(1,31,1);
    }else{
        one(1,17,0);one(1,18,0);one(1,27,1);
        strcpy(g_mod[0].build_id,"badf2faf580b712464365c4d529d92c9");
        one(1,17,0);one(1,27,1);
    }
    free(g_mod[0].base);printf("PASS %d exact-map/no-op negative control trials\n",trials);return 0;
}
