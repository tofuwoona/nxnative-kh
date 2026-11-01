// Compile with DM_GAME_PROGRAM_ID for KH2 and a sibling to test isolation.
#include <assert.h>
#include <stdio.h>
#include "../aspect_fill.h"
int main(void) {
    unsetenv("DM_ASPECT_FILL"); unsetenv("DM_PRESERVE_FULL_HUD");
    assert(!dm_aspect_fill_on());
    setenv("DM_ASPECT_FILL", "1", 1);
    assert(dm_aspect_fill_on());
    setenv("DM_PRESERVE_FULL_HUD", "1", 1);
#if DM_GAME_PROGRAM_ID == 0x010090C022978003ull
    assert(!dm_aspect_fill_on() && "Preserve full HUD must override crop");
#else
    assert(dm_aspect_fill_on() && "KH2 setting must not affect sibling games");
#endif
    setenv("DM_PRESERVE_FULL_HUD", "0", 1);
    assert(dm_aspect_fill_on());
    unsetenv("DM_PRESERVE_FULL_HUD");
    assert(dm_aspect_fill_on());
    puts("PASS HUD/crop precedence, defaults and profile isolation");
}
