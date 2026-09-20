#!/usr/bin/env python3
"""Run the workflow-generated C++ post pass on real surfaceless GLES (Mesa in CI).

Requires g++, libEGL, a GLES Mesa driver, and numpy. No game ROM or display needed.
The shader strings, GL calls, lookups, and state handling come from gfx_opengl.cpp.
"""
from pathlib import Path
import argparse
import ctypes as c
import hashlib
import json
import os
import re
import subprocess
import numpy as np

parser = argparse.ArgumentParser()
parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
parser.add_argument('--output', type=Path, default=Path('smaa-validation'))
parser.add_argument('--baseline', action='store_true', help='report old first-use failure without accepting it')
args = parser.parse_args()
root, out = args.root.resolve(), args.output.resolve()
out.mkdir(parents=True, exist_ok=True)
src = (root/'port/fast3d/gfx_opengl.cpp').read_text()
block = src[src.index('static GLuint grade_prog,'):src.index('static void gfx_opengl_finish_render(void)')]
pc = (root/'port/fast3d/gfx_pc.cpp').read_text()
# Check the canonical lookup payloads independently of line endings/comments.
for name, digest in [('Area','35065cef2a02cabcad711d6bf430239ae64e27d71c4e4fa06f29cce2c992f0d2'),
                     ('Search','3694eae5e9d44b8ebb4415a13f8c7b94dc08a2fc86658434d771c4610fe5744d')]:
    header=(root/f'port/fast3d/smaa_ref/{name}Tex.h').read_text()
    payload=bytes(int(v,16) for v in re.findall(r'0x([0-9a-fA-F]{2})',header))
    assert hashlib.sha256(payload).hexdigest()==digest, name+' lookup payload changed'
globals_ = '\n'.join(re.findall(r'^(?:float|int) gfx_(?:post_|color_|smaa_)[^;]+;', pc, re.M))
if 'int gfx_smaa_debug' not in globals_:
    globals_ += '\nint gfx_smaa_debug = 0;'
prefix = r'''#include "glad/glad.h"
#include <cstdio>
#include <cstdarg>
#include <cmath>
#include <vector>
#include <string>
#include "smaa_ref/AreaTex.h"
#include "smaa_ref/SearchTex.h"
#include "smaa_ref/SMAASource.h"
static bool gl_es = true;
static unsigned frame_count = 0;
static int current_framebuffer = 0;
struct Framebuffer {unsigned width = 0, height = 0, fbo = 0;};
static std::vector<Framebuffer> framebuffers(1);
enum {LOG_WARNING, LOG_NOTE};
char gfx_smaa_status[96] = {};
static void sysLogPrintf(int, const char *fmt, ...) {
    va_list a;va_start(a,fmt);vfprintf(stderr,fmt,a);fputc('\n',stderr);va_end(a);
}
'''
harness = Path(__file__).with_name('smaa-harness.inc').read_text()
(out/'harness.cpp').write_text(prefix+globals_+'\n'+block+harness)
subprocess.run(['g++', '-shared', '-fPIC', '-O1', '-std=c++17', '-I'+str(root/'port/fast3d'),
                str(out/'harness.cpp'), str(root/'port/fast3d/glad/glad.c'), '-o', str(out/'harness.so')], check=True)

os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE', '1')
os.environ.setdefault('MESA_GLES_VERSION_OVERRIDE', '3.0')
E = c.CDLL('libEGL.so.1')
ptr, i, u = c.c_void_p, c.c_int, c.c_uint
def ef(name, rest, arguments):
    fn = getattr(E, name); fn.restype = rest; fn.argtypes = arguments; return fn
getproc = ef('eglGetProcAddress', ptr, [c.c_char_p])
getdisplay = c.CFUNCTYPE(ptr,u,ptr,c.POINTER(i))(getproc(b'eglGetPlatformDisplayEXT'))
display = getdisplay(0x31DD, None, None)
a, b = i(), i()
assert ef('eglInitialize',u,[ptr,c.POINTER(i),c.POINTER(i)])(display,c.byref(a),c.byref(b))
assert ef('eglBindAPI',u,[u])(0x30A0)
attrs = (i*13)(0x3033,1,0x3040,0x40,0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3038)
config, n = ptr(), i()
assert ef('eglChooseConfig',u,[ptr,c.POINTER(i),c.POINTER(ptr),i,c.POINTER(i)])(display,attrs,c.byref(config),1,c.byref(n)) and n.value
context = ef('eglCreateContext',ptr,[ptr,ptr,ptr,c.POINTER(i)])(display,config,None,(i*3)(0x3098,3,0x3038))
surface = ef('eglCreatePbufferSurface',ptr,[ptr,ptr,c.POINTER(i)])(display,config,(i*5)(0x3057,1920,0x3056,1080,0x3038))
assert ef('eglMakeCurrent',u,[ptr,ptr,ptr,ptr])(display,surface,surface,context)
gl_string = c.CFUNCTYPE(c.c_char_p,u)(getproc(b'glGetString'))
report = {'gl_version':gl_string(0x1F02).decode(), 'renderer':gl_string(0x1F01).decode(), 'cases':[]}
print(report['gl_version'], report['renderer'], flush=True)
H = c.CDLL(str(out/'harness.so'))
H.init.argtypes=[ptr]; assert H.init(c.cast(E.eglGetProcAddress,ptr))
H.render.argtypes=[i,i,i,i]+[ptr]*5
H.shader.argtypes=[i,i]; H.shader.restype=c.c_char_p
H.status.restype=c.c_char_p
for q in range(2):
    for p in range(3):
        (out/f'smaa-{q}-{p}.frag').write_bytes(H.shader(p,q))

def frame(source, mode=4, hostile=False):
    source = np.ascontiguousarray(source, dtype=np.uint8)
    h,w = source.shape[:2]
    arrays = [np.zeros_like(source) for _ in range(4)]
    H.render(w,h,mode,hostile,source.ctypes.data,*[a.ctypes.data for a in arrays])
    errors = [H.errors(j) for j in range(3)]
    if args.baseline:
        print('baseline state/trace/GL errors:', errors, flush=True)
        return arrays
    assert errors == [0,0,0], errors
    if mode>=3:
        assert H.ready(mode==4), H.status().decode()
        assert H.errors(3) == (5 if view else 4), H.errors(3)
    return arrays

def rgba(gray):
    return np.dstack([gray,gray,gray,np.full_like(gray,255)]).astype('uint8')

def pattern(w,h,slope):
    y,x=np.mgrid[:h,:w]
    f=y+0.5-slope*(x+0.5)-h*0.35
    # Pixel-center rasterization and an independent 8x8 coverage reference.
    ideal=np.zeros_like(f)
    for sy in (np.arange(8)+0.5)/8-0.5:
        for sx in (np.arange(8)+0.5)/8-0.5:
            ideal+=(f+sy-slope*sx>0)/64
    return rgba(np.where(f>0,220,25)),25+195*ideal

def measure(name, source, ideal=None, hostile=False, mode=4):
    dst,edge,weight,graded=frame(source,mode,hostile)
    delta=np.max(abs(dst[:,:,:3].astype(int)-graded[:,:,:3].astype(int)),axis=2)
    detected=np.any(edge[:,:,:2],axis=2)
    padded=np.pad(detected,2)
    nearby=np.zeros_like(detected)
    for dy in range(5):
        for dx in range(5):nearby |= padded[dy:dy+len(detected),dx:dx+detected.shape[1]]
    item={'name':name,'mode':mode,'width':source.shape[1],'height':source.shape[0],
          'edges':int(detected.sum()),'weights':int(np.any(weight,axis=2).sum()),
          'changed':int(np.count_nonzero(delta)),'max_delta':int(delta.max()),
          'changed_outside_edge_neighborhood':int(np.count_nonzero(delta[~nearby]))}
    assert item['edges']>0 and item['weights']>0 and item['changed']>0, item
    assert item['changed_outside_edge_neighborhood']==0, item
    if ideal is not None:
        old=np.mean((source[:,:,0].astype(float)-ideal)**2)
        new=np.mean((dst[:,:,0].astype(float)-ideal)**2)
        item.update(aliased_mse=old,smaa_mse=new)
        assert new<old, item
    report['cases'].append(item); print(json.dumps(item),flush=True)
    return dst,edge,weight,graded

view=0
source,ideal=pattern(960,540,1/3)
if args.baseline:
    frame(source)
    raise SystemExit(0)
measure('first activation, hostile caller state',source,ideal,True)
first=measure('second frame',source,ideal)[0]
third=measure('third frame with audit',source,ideal,True)[0]
assert np.array_equal(first,third)
assert 'E:' in H.status().decode(),H.status().decode()
off=frame(source,0)[0];assert np.array_equal(off,source)
measure('Off to Ultra again',source,ideal)
measure('High preset',source,ideal,mode=3)
for w,h in [(1920,1080),(641,359)]:
    for slope in [1/3,1,3,-1/3]:
        source,ideal=pattern(w,h,slope)
        # Keep both sides of negative/steep diagonals in the target.
        if not np.any(source[:,:,:3]==220) or not np.any(source[:,:,:3]==25):continue
        measure('diagonal and resize',source,ideal,True)
source,ideal=pattern(960,540,1/3)
resolved,edge,weight,graded=measure('diagnostic baseline',source,ideal)
for view in [1,2,3,4]:
    H.set_view(view)
    dst=frame(source)[0]
    if view==1:
        assert np.array_equal(dst[:,:,:2],edge[:,:,:2]) and not dst[:,:,2].any()
    elif view==2:
        expected=np.stack([np.maximum(weight[:,:,0],weight[:,:,2]),np.maximum(weight[:,:,1],weight[:,:,3]),
            np.maximum(weight[:,:,2],weight[:,:,3])],axis=2)
        assert np.array_equal(dst[:,:,:3],expected)
    elif view==3:assert np.array_equal(dst,resolved)
    else:assert dst[:,:,:3].any() and np.count_nonzero(dst[:,:,:3])<source.size//10
H.set_view(0);view=0
flat=rgba(np.full((540,960),127,dtype='uint8'))
dst,edge,weight,graded=frame(flat)
assert np.array_equal(dst,flat) and not edge[:,:,:2].any() and not weight.any()
# An exactly axis-aligned boundary has no staircase to smooth.
y,x=np.mgrid[:540,:960]
axis=rgba(np.where(x<480,25,220))
assert np.array_equal(frame(axis)[0],axis)
H.set_sharpen(3)
measure('SMAA remains final after sharpening',source,hostile=True)
H.set_sharpen(0)
# Reach the delayed audit with unchanged scene/settings, exercising the runtime
# snapshot during a stable sequence rather than only on the selection frame.
small,_=pattern(96,54,1/3)
for count in range(122):frame(small,hostile=count in (2,120))
assert 'E:' in H.status().decode()
report['status']='passed'
report['checks']=['first activation state restoration','repeat frames','Off to Ultra','High and Ultra',
    'native 1920x1080','odd-sized target','edge-local differences','coverage error decreases',
    'flat fields unchanged','straight boundaries unchanged','all diagnostic views',
    'shader compilation and linking','four production draws','texture units and framebuffer routing',
    'no texture feedback','viewport and texel metrics','linear clamp samplers',
    'state restoration including inherited sampler objects and PBOs','audit at frame 2 and 120',
    'SMAA after sharpening']
(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: production GLES pipeline and all regression checks',flush=True)
