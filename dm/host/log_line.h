// The single-fprintf-call-per-line primitive that dm.h's LOG() and
// nvn_mtl.m's MLOG() both expand to. Pulled out on its own (no other
// dependencies) so dm/ios/tests/t_log_rotation.c can #include this file
// directly and exercise the exact code the real macros use, instead of a
// hand-written lookalike that could silently drift from them.
#pragma once
#include <stdio.h>

#define DM_LOG_LINE(stream, prefix, fmt, ...) fprintf((stream), prefix fmt "\n", ##__VA_ARGS__)
