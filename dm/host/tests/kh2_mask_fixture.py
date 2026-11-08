"""Private-artifact fixture for CPU-only aspect tests; real activation code."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[3]
C=r'''
#include <sys/mman.h>
#include "kh2_mask.h"
static void test_mask_load(module_t *m) {
 const char *path=getenv("KH2_MASK_IMAGE");if(!path)return;
 FILE *f=fopen(path,"rb");assert(f);fseek(f,0,SEEK_END);m->size=ftell(f);rewind(f);
 m->base=mmap(NULL,m->size,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANON,-1,0);
 assert(m->base!=MAP_FAILED);assert(fread(m->base,1,m->size,f)==m->size);fclose(f);
 m->text_end=0x400d50;m->ro_off=0x401000;m->data_off=0x52f000;
 m->key_page_off=0x2d30000;m->key_page_size=0x4000;m->patch_off=0x2d40000;m->loaded=1;
 for(int i=0;i<4;i++)m->key_idx[i]=i;
 assert(!mprotect(m->base+m->key_page_off,0x4000,PROT_READ));
}
'''

def write_image(directory):
 spec=importlib.util.spec_from_file_location('mask',ROOT/'dm/tools/kh2_mask_patch.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 source_env=os.environ.get('KH2_MASK_INPUT')
 if not source_env or not (Path(source_env)/'main.patched.bin').is_file():
  raise unittest.SkipTest('set KH2_MASK_INPUT to the private reconstructed-module directory')
 source=Path(source_env)
 path=Path(directory)/'main.mask.bin'
 path.write_bytes(module.patch_image((source/'main.patched.bin').read_bytes(),cpu_aspect=True))
 return str(path)
