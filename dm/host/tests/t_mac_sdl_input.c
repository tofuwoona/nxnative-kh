#include <SDL.h>
#include <assert.h>
#include "../dm_input.h"
#include "../mac_sdl_input.h"
int main(void) {
    mac_pad_state s = mac_sdl_map(0, 0, 0, 0, 0, 0, 0);
    assert(!s.buttons && !s.lx && !s.ly && !s.rx && !s.ry);
    s=mac_sdl_map(0,1200,-1400,1900,2400,0,0);
    assert(!s.lx && !s.ly && !s.rx && !s.ry);
    assert(mac_sdl_map(1u<<SDL_CONTROLLER_BUTTON_A,0,0,0,0,0,0).buttons==DM_BTN_B);
    assert(mac_sdl_map(1u<<SDL_CONTROLLER_BUTTON_B,0,0,0,0,0,0).buttons==DM_BTN_A);
    assert(mac_sdl_map(1u<<SDL_CONTROLLER_BUTTON_X,0,0,0,0,0,0).buttons==DM_BTN_Y);
    assert(mac_sdl_map(1u<<SDL_CONTROLLER_BUTTON_Y,0,0,0,0,0,0).buttons==DM_BTN_X);
    assert(mac_sdl_map(1u<<SDL_CONTROLLER_BUTTON_DPAD_UP,0,0,0,0,0,0).buttons==DM_BTN_UP);
    assert(mac_sdl_map(1u<<SDL_CONTROLLER_BUTTON_LEFTSHOULDER,0,0,0,0,0,0).buttons==DM_BTN_L);
    assert(mac_sdl_map(0,0,0,0,0,16383,16383).buttons==0);
    assert(mac_sdl_map(0,0,0,0,0,16384,16384).buttons==(DM_BTN_ZL|DM_BTN_ZR));
    s=mac_sdl_map(0,-32768,-32768,32767,32767,0,0);
    assert(s.lx==-32767 && s.ly==32767 && s.rx==32767 && s.ry==-32767);
    return 0;
}
