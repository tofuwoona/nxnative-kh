// Static CPU call adapters. No runtime executable writes or game module image.
.text
.p2align 2
.globl _abi_on_stack
_abi_on_stack:
    stp x29,x30,[sp,#-16]!
    mov x29,sp
    mov x9,sp
    mov sp,x1
    stp x9,xzr,[sp,#-16]!
    bl _abi_exercise
    ldr x9,[sp]
    mov sp,x9
    ldp x29,x30,[sp],#16
    ret
.globl _abi_exercise
_abi_exercise:
    stp x29,x30,[sp,#-96]!
    stp x19,x20,[sp,#16]
    stp x23,x24,[sp,#32]
    str q8,[sp,#48]
    mrs x10,fpcr
    str x10,[sp,#64]
    mrs x10,fpsr
    str x10,[sp,#72]
    msr fpcr,xzr
    mov x10,#1
    msr fpsr,x10
    mov x29,sp
    mov x9,#0x1357
    mov x19,#0x2468
    mov x20,#0x5432
    mov x23,#0x369a
    mov x24,#0xabcd
    movi v0.16b,#0x5a
    movi v8.16b,#0x3b
    movi v31.16b,#0x6c
    bl Lwrapped
    cmp w0,#1024
    b.ne Lfail
    mov x10,#0x1357
    cmp x9,x10
    b.ne Lfail
    mov x10,#0x2468
    cmp x19,x10
    b.ne Lfail
    mov x10,#0x369a
    cmp x23,x10
    b.ne Lfail
    mov x10,#0x5432
    cmp x20,x10
    b.ne Lfail
    mov x10,#0xabcd
    cmp x24,x10
    b.ne Lfail
    mrs x10,fpcr
    cbnz x10,Lfail
    mrs x10,fpsr
    cmp x10,#1
    b.ne Lfail
    movi v1.16b,#0x3b
    cmeq v1.16b,v8.16b,v1.16b
    uminv b1,v1.16b
    fmov w10,s1
    and w10,w10,#0xff
    cmp w10,#0xff
    b.ne Lfail
    movi v1.16b,#0x6c
    cmeq v1.16b,v31.16b,v1.16b
    uminv b1,v1.16b
    fmov w10,s1
    and w10,w10,#0xff
    cmp w10,#0xff
    b.ne Lfail
    movi v1.16b,#0x5a
    cmeq v0.16b,v0.16b,v1.16b
    uminv b0,v0.16b
    fmov w10,s0
    and w10,w10,#0xff
    cmp w10,#0xff
    cset w0,eq
    b Ldone
Lfail:
    mov w0,#0
Ldone:
    ldr x10,[sp,#64]
    msr fpcr,x10
    ldr x10,[sp,#72]
    msr fpsr,x10
    ldr q8,[sp,#48]
    ldp x23,x24,[sp,#32]
    ldp x19,x20,[sp,#16]
    ldp x29,x30,[sp],#96
    ret
Lwrapped:
    b Lwrapper
Loriginal_cont:
    stp x29,x30,[sp,#0x110]
    stp x28,x23,[sp,#0x120]
    stp x22,x21,[sp,#0x130]
    stp x20,x19,[sp,#0x140]
    add x29,sp,#0x110
    mov x19,x0
    bl _abi_guest_payload
    ldr w0,[x19,#0x6c]
    ldp x20,x19,[sp,#0x140]
    ldp x22,x21,[sp,#0x130]
    ldp x28,x23,[sp,#0x120]
    ldp x29,x30,[sp,#0x110]
    add sp,sp,#0x150
    ret
// Same wrapper layout as site_wrap; replace ONLY the six-instruction TSD
// lookup with a six-instruction static address adapter for this Mach-O fixture.
Lwrapper:
    stp x29,x30,[sp,#-16]!
    adrp x30,_dm_gate@PAGE
    add x30,x30,_dm_gate@PAGEOFF
    nop
    nop
    nop
    nop
    blr x30
.globl _abi_ret
_abi_ret:
    ldp x29,x30,[sp],#16
    ret
.globl _abi_body
_abi_body:
    sub sp,sp,#0x150
    b Loriginal_cont
.globl _abi_nested_big
_abi_nested_big:
    adrp x16,_abi_nested_impl@PAGE
    add x16,x16,_abi_nested_impl@PAGEOFF
    b _dm_bigstack_enter

// Original-writer-shaped body and normal gate wrapper. All captures go through
// real dm_gate/dm_bigstack_enter; only gate-address TSD lookup is substituted.
.globl _abi_png_wrapped
_abi_png_wrapped:
    stp x29,x30,[sp,#-16]!
    adrp x30,_dm_gate@PAGE
    add x30,x30,_dm_gate@PAGEOFF
    nop
    nop
    nop
    nop
    blr x30
.globl _abi_png_ret
_abi_png_ret:
    ldp x29,x30,[sp],#16
    ret
.globl _abi_png_body
_abi_png_body:
    sub sp,sp,#0x90
    stp x29,x30,[sp,#0x50]
    str x23,[sp,#0x60]
    stp x22,x21,[sp,#0x70]
    stp x20,x19,[sp,#0x80]
    add x29,sp,#0x50
    bl _abi_png_payload
    mov w0,#1
    ldp x20,x19,[sp,#0x80]
    ldp x22,x21,[sp,#0x70]
    ldr x23,[sp,#0x60]
    ldp x29,x30,[sp,#0x50]
    add sp,sp,#0x90
    ret

.globl _abi_png_captures
_abi_png_captures:
    stp x29,x30,[sp,#-64]!
    stp x19,x20,[sp,#16]
    stp x21,x22,[sp,#32]
    stp x1,x2,[sp,#48]
    bl Lcap_file
    bl Lcap_error
    mov x20,x2
    ldr x0,[sp,#48]
    bl Lcap_png
    ldr x0,[sp,#56]
    bl Lcap_info
    mov x0,x20
    ldp x21,x22,[sp,#32]
    ldp x19,x20,[sp,#16]
    ldp x29,x30,[sp],#64
    ret
.macro capture label, returnlabel
\label:
    stp x29,x30,[sp,#-16]!
    adrp x30,_dm_gate@PAGE
    add x30,x30,_dm_gate@PAGEOFF
    nop
    nop
    nop
    nop
    blr x30
.globl \returnlabel
\returnlabel:
    ldp x29,x30,[sp],#16
    ret
.endm
capture Lcap_file, _abi_cap_file_ret
capture Lcap_error, _abi_cap_error_ret
capture Lcap_png, _abi_cap_png_ret
capture Lcap_info, _abi_cap_info_ret

// Like a rewritten guest callee, deliberately leave virtual x18 to TSD (never
// write Apple's platform x18). No return: Darwin longjmp must restore the host
// frame, and the still-live outer dm_gate restores full guest GPR/SIMD/FP state.
.globl _abi_png_error_jump
_abi_png_error_jump:
    mov x16,x0
    mov x0,x1
    mov x1,xzr
    mov x19,#0xdead
    mov x20,#0xdead
    mov x21,#0xdead
    mov x22,#0xdead
    mov x23,#0xdead
    mov x24,#0xdead
    mov x25,#0xdead
    mov x26,#0xdead
    mov x27,#0xdead
    mov x28,#0xdead
    movi v0.16b,#0xde
    movi v8.16b,#0xde
    movi v9.16b,#0xde
    movi v10.16b,#0xde
    movi v11.16b,#0xde
    movi v12.16b,#0xde
    movi v13.16b,#0xde
    movi v14.16b,#0xde
    movi v15.16b,#0xde
    movi v31.16b,#0xde
    mov x9,#0x1000000
    msr fpcr,x9
    mov x9,#0x80
    msr fpsr,x9
    br x16
