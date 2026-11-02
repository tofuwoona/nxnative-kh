"""Run the production ObjC face geometry, label wiring and input path on macOS.

UIKit setup is replaced with Core Animation layers; the input sink is captured
and haptics are disabled. Production label/layout code, geometry, hit testing,
publish and read_pad run verbatim. GameController's software controller drives
read_pad without a device or GPU rendering.
Run: python3 dm/ios/tests/test_touch_face_positions.py
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "dm/ios/Sources/DmGamepad.m"
PROFILES = ("0x010090C022978003ull", "0x010090C022978001ull",
            "0x010090C022978000ull", "0x010015100B514000ull", "0ull")


def block(source, marker):
    """Extract a production function/method verbatim, including its signature."""
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def harness(source):
    enum, = re.findall(r"enum \{ B_A = 0,.*?;", source)
    constants = source[source.index("static const CGFloat"):source.index("static const int k_btns")]
    # Ignore semicolons inside the layout comments when finding the declaration.
    constants = re.sub(r"//[^\n]*", "", constants).split(";", 1)[0] + ";"
    globals_ = source[source.index("static pthread_mutex_t g_mu"):
                      source.index("// ---- Shaking the phone ----")]
    names = source[source.index("static NSString *const names[B_N]"):
                   source.index("        _swap = shape(_controls)")]
    layout = block(source, "for (int b = B_A; b <= B_Y; b++) { CGPoint c = [self facePos:b]")
    return r'''
#import <Foundation/Foundation.h>
#import <QuartzCore/QuartzCore.h>
#import <CoreText/CoreText.h>
#import <GameController/GameController.h>
#include <pthread.h>
#include <assert.h>
#include <math.h>
#include "face_swap.h"
static uint64_t published;
static void dm_input_set(uint64_t m, int32_t lx, int32_t ly, int32_t rx, int32_t ry) {
    published = m; (void)lx; (void)ly; (void)rx; (void)ry;
}
static void dm_haptics_apple_controller(int slot, GCController *controller) {
    (void)slot; (void)controller;
}
''' + enum + '\n' + constants + '\n' + globals_ + r'''
static CAShapeLayer *shape(CALayer *parent) {
    CAShapeLayer *layer = [CAShapeLayer layer]; [parent addSublayer:layer]; return layer;
}
static CATextLayer *label(CALayer *parent, NSString *text) {
    CATextLayer *layer = [CATextLayer layer]; layer.string = text;
    [parent addSublayer:layer]; return layer;
}
''' + '\n'.join(block(source, marker) for marker in (
        "static CGFloat dist(", "static CGPathRef circlePath(",
        "static void setPath(", "static void placeLabel(")) + r'''
@interface FaceHarness : NSObject {
@public
    CAShapeLayer *_key[B_N]; CATextLayer *_label[B_N]; CALayer *_controls;
}
@property CGPoint faceCenter;
@property CGFloat u;
- (CGFloat)faceGap;
- (CGFloat)faceR;
- (CGPoint)facePos:(int)b;
- (uint64_t)faceAt:(CGPoint)p;
- (void)createLabels;
- (void)layoutFaces;
@end
@implementation FaceHarness
''' + '\n'.join(block(source, marker) for marker in (
        "- (CGFloat)faceGap", "- (CGFloat)faceR", "- (CGPoint)facePos:",
        "- (uint64_t)faceAt:")) + '\n- (void)createLabels {\n_controls = [CALayer layer];\n' + names + '\n}\n- (void)layoutFaces { CGFloat u = self.u;\n' + layout + '\n}\n@end\n' + '\n'.join(block(source, marker) for marker in (
        "static int32_t axis(", "static void read_pad(")) + r'''
static int failures;
#define CHECK(expr, msg) do { if (!(expr)) { \
    fprintf(stderr, "FAIL profile=%llx swap=%d: %s\n", \
            (unsigned long long)DM_GAME_PROGRAM_ID, g_face_swap, msg); failures++; \
} } while (0)
static BOOL closePoint(CGPoint a, CGPoint b) { return hypot(a.x-b.x, a.y-b.y)<0.0001; }
int main(void) { @autoreleasepool {
    for (int swap = 0; swap <= 1; swap++) {
        g_face_swap = swap;
        FaceHarness *view = [FaceHarness new]; [view createLabels];
        CHECK([view->_label[B_X].string isEqual:@"X"], "X label belongs to X key");
        CHECK([view->_label[B_Y].string isEqual:@"Y"], "Y label belongs to Y key");
        CHECK([view->_label[B_A].string isEqual:swap ? @"B" : @"A"], "existing A label");
        CHECK([view->_label[B_B].string isEqual:swap ? @"A" : @"B"], "existing B label");
        const CGFloat scales[] = {0.6, 1.0, 1.3};
        for (unsigned s = 0; s < sizeof scales / sizeof *scales; s++) {
            view.u = scales[s]; view.faceCenter = CGPointMake(700, 300);
            [view layoutFaces];
            CGPoint c = view.faceCenter; CGFloat gap = view.faceGap;
            CGPoint expected[] = {{c.x+gap,c.y}, {c.x,c.y+gap},
                                  {c.x,c.y-gap}, {c.x-gap,c.y}};
            if (DM_GAME_PROGRAM_ID == 0x010090C022978003ull) {
                CGPoint top = expected[B_X]; expected[B_X] = expected[B_Y]; expected[B_Y] = top;
            }
            for (int b = B_A; b <= B_Y; b++) {
                CHECK(closePoint([view facePos:b], expected[b]), "expected button center");
                CGRect bounds = CGPathGetBoundingBox(view->_key[b].path);
                CGPoint shapeCenter = CGPointMake(CGRectGetMidX(bounds), CGRectGetMidY(bounds));
                CGRect frame = view->_label[b].frame;
                CGPoint labelCenter = CGPointMake(CGRectGetMidX(frame), CGRectGetMidY(frame));
                CHECK(closePoint(shapeCenter, expected[b]), "shape follows key center");
                CHECK(closePoint(labelCenter, expected[b]), "label follows key center");
                CHECK([view faceAt:expected[b]] == (1ull << b), "hit at expected center retains key identity");
                // Each named button must publish its previous action, for both preferences.
                g_touch_btn = [view faceAt:[view facePos:b]];
                g_pad_btn = 0; g_shake_btn = 0; publish();
                CHECK(published == (1ull << (swap ? (b ^ 1) : b)), "same labeled key keeps downstream action");
            }
            CHECK([view faceAt:CGPointMake(c.x+4*gap,c.y)] == 0, "outside face keys");
        }
        GCController *controller = [GCController controllerWithExtendedGamepad];
        GCExtendedGamepad *pad = controller.extendedGamepad;
        CHECK(pad != nil, "software physical controller available");
        for (uint64_t bits = 0; bits < 16; bits++) {
            // Apple positions: B=right/A, A=bottom/B, Y=top/X, X=left/Y.
            [pad.buttonB setValue:(bits & 1) != 0]; [pad.buttonA setValue:(bits & 2) != 0];
            [pad.buttonY setValue:(bits & 4) != 0]; [pad.buttonX setValue:(bits & 8) != 0];
            g_touch_btn = 0; g_shake_btn = 1ull << 63;
            read_pad(pad);
            uint64_t physical = swap ? ((bits & 1) << 1) | ((bits & 2) >> 1) | (bits & 12) : bits;
            CHECK(published == (physical | (1ull << 63)), "existing physical mapping unchanged");
            for (uint64_t touch = 0; touch < 16; touch++) {
                g_touch_btn = touch; read_pad(pad);
                uint64_t expectedTouch = swap ? ((touch & 1) << 1) | ((touch & 2) >> 1)
                                              | ((touch & 4) << 1) | ((touch & 8) >> 1) : touch;
                CHECK(published == (physical | expectedTouch | (1ull << 63)), "merged input/preferences unchanged");
            }
        }
    }
    printf("%s production face geometry/labels/hits/publish/physical profile=%llx\n",
           failures ? "FAIL" : "PASS", (unsigned long long)DM_GAME_PROGRAM_ID);
    return failures ? 1 : 0;
} }
'''


class TouchFacePositions(unittest.TestCase):
    def test_production_faces(self):
        source = SOURCE.read_text()
        scratch = Path(os.environ.get("TMPDIR", ROOT / "dm/host/tests/build"))
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="touch-face-", dir=scratch) as directory:
            path = Path(directory)
            obj = path / "faces.m"
            obj.write_text(harness(source))
            for profile in PROFILES:
                with self.subTest(profile=profile):
                    binary = path / "faces"
                    subprocess.run(["xcrun", "--sdk", "macosx", "clang", "-fobjc-arc",
                                    "-Wall", "-Wextra", "-Werror", "-Wno-unused-const-variable",
                                    "-I" + str(ROOT / "dm/ios/Sources"),
                                    "-DDM_GAME_PROGRAM_ID=" + profile, str(obj),
                                    "-framework", "Foundation", "-framework", "QuartzCore",
                                    "-framework", "CoreText", "-framework", "CoreGraphics",
                                    "-framework", "GameController",
                                    "-o", str(binary)], check=True)
                    result = subprocess.run([str(binary)], capture_output=True, text=True)
                    print(result.stdout, end="")
                    self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
