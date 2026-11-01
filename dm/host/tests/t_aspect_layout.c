#include <assert.h>
#include <math.h>
#include <stdio.h>
#include "../aspect_fill.h"
#define NEAR(a,b) assert(fabs((a)-(b)) < 1e-8)
int main(void) {
#ifndef DM_ASPECT_LAYOUT_VERSION
    assert(0 && "shared safe-area frame and touch mapping missing");
#else
    // All four switch states; iOS landscape left/right plus portrait geometry
    // (iOS app remains landscape-only), 16:9 and 4:3. Mac uses zero insets.
    double sizes[][2] = {{2556,1179},{1179,2556},{1920,1080},{2048,1536}};
    unsigned layouts=0;
    for (int fill=0;fill<2;fill++) for (int keep=0;keep<2;keep++) {
        setenv("DM_ASPECT_FILL", fill?"1":"0",1);
        setenv("DM_PRESERVE_FULL_HUD", keep?"1":"0",1);
        for (unsigned i=0;i<sizeof sizes/sizeof *sizes;i++) for (int rotation=0;rotation<3;rotation++) {
            layouts++;
            double w=sizes[i][0],h=sizes[i][1];
            double l=rotation==1?0:177,r=rotation==0?0:177,t=0,b=63;
            dm_aspect_rect f=dm_aspect_frame(w,h,l,t,r,b);
            assert(f.w>0 && f.h>0);
            if (keep) {
                NEAR(f.w/f.h,16.0/9.0);
                assert(f.x>=l && f.y>=t && f.x+f.w<=w-r+1e-8 && f.y+f.h<=h-b+1e-8);
            } else if (fill) { NEAR(f.x,0); NEAR(f.y,0); NEAR(f.w,w); NEAR(f.h,h); }
            else { // Existing fit baseline ignores safe area, unchanged.
                NEAR(f.w/f.h,16.0/9.0); NEAR(f.x,(w-f.w)/2); NEAR(f.y,(h-f.h)/2);
            }
            double ox,oy,fx,fy; dm_aspect_visible(f.w,f.h,&ox,&oy,&fx,&fy);
            for (int corner=0;corner<5;corner++) {
                double u=corner==4?0.5:(corner&1),v=corner==4?0.5:((corner>>1)&1),nx,ny;
                dm_aspect_touch(f,u*f.w+f.x,v*f.h+f.y,&nx,&ny);
                NEAR(nx,ox+u*fx); NEAR(ny,oy+v*fy);
            }
            double nx,ny;
            dm_aspect_touch(f,-100,-100,&nx,&ny); NEAR(nx,ox); NEAR(ny,oy);
            dm_aspect_touch(f,w+100,h+100,&nx,&ny); NEAR(nx,ox+fx); NEAR(ny,oy+fy);
            // Points and pixels give identical normalized coordinates.
            dm_aspect_rect p=dm_aspect_frame(w/3,h/3,l/3,t/3,r/3,b/3);
            NEAR(f.x,p.x*3); NEAR(f.y,p.y*3); NEAR(f.w,p.w*3); NEAR(f.h,p.h*3);
        }
    }
    dm_aspect_rect zero=dm_aspect_frame(0,0,0,0,0,0);
    double x,y; dm_aspect_touch(zero,0,0,&x,&y); NEAR(x,0); NEAR(y,0);
    printf("PASS %u layouts: precedence, fit/fill baselines, mirrored/symmetric notch insets, portrait/4:3, safe-area corners, clamping and point/pixel touch mapping\n",layouts);
#endif
}
