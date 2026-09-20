#!/usr/bin/env python3
"""Compile actual generated yaw code, rather than reimplement its multiplier.

No ROM/SDL/Android runtime is simulated: device input is supplied at the SDL
axis boundary. Collision/rooms are excluded because pure yaw has zero movement.
Camera check uses the engine's Y rotation matrix with head roll disabled.
"""
from pathlib import Path
import hashlib
import json
import subprocess


def function(source, name):
    import re
    m = re.search(r'^[^\n;{}]*\b' + name + r'\([^;]*?\)\n\{', source, re.M)
    assert m, name
    begin = source.index('{', m.start())
    depth = 1
    end = begin + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[m.start():end] + '\n'


move = Path('src/game/bondmove.c').read_text()
walk = Path('src/game/bondwalk.c').read_text()
inp = Path('port/src/input.c').read_text()
mtx = Path('src/lib/mtx.c').read_text()
out = Path('turn-validation')
out.mkdir(exist_ok=True)
start = move.index('#ifndef PLATFORM_N64\n\tstatic f32 turnboostlevel')
end = move.index('\n\tif (movedata.detonating)', start)
turn = move[start:end]
apply_start = walk.index('\t\tf32 angle = g_Vars.currentplayer->vv_theta +')
apply_end = walk.index('\n\n\t\tg_Vars.currentplayer->prop->pos.x', apply_start)
apply_yaw = walk[apply_start:apply_end]
source = r'''
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
typedef float f32;
typedef int s32;
typedef unsigned long long u64;
#define INPUT_MAX_CONTROLLERS 4
#define PLAYER_DEFAULT_FOV 60.f
#define CONTROLMODE_PC 13
#define M_BADPI 3.141092641f
#define M_BADTAU (M_BADPI * 2)
#define BADDEG2RAD(deg) ((deg) * (M_BADPI / 180.f))
#define CDTYPE_ALL 0
#define turnBoostDiagControl(...) ((void)0)
struct coord { float x,y,z; };
typedef struct {float m[4][4];} Mtxf;
struct {float speedtheta, speedthetacontrol, vv_theta; int insightaimmode;} player;
struct {__typeof__(player) *currentplayer; float lvupdate60freal;} g_Vars = {&player, 1.f};
struct {int cannaturalturn, analogturn; float aimturnleftspeed, aimturnrightspeed, freelookdx;} movedata;
static float strength, fov=60, threshold=.5f, ramp=3, release=.05f;
static int curve=2, swapped=1, aim=0;
static u64 now;
u64 sysGetMicroseconds(void) {return now;}
float viGetFovY(void) {return fov;}
int inputControllerGetSticksSwapped(int c) {return swapped;}
int inputControllerUsesFullRightStickRange(int c) {return curve != 0;}
float inputControllerGetTurnBoost(int c) {return strength;}
float inputControllerGetTurnBoostThreshold(int c) {return threshold;}
float inputControllerGetTurnBoostRamp(int c) {return ramp;}
float inputControllerGetTurnBoostRelease(int c) {return release;}
int inputControllerGetTurnBoostAimMode(int c) {return aim;}
void bwalkCalculateNewPositionWithPush(struct coord *delta, float rotateamount, int a, int b, int c) {
''' + apply_yaw + '\n}\n'
for name in ['inputAxisScale', 'inputClampUnit', 'inputRightStickShape']:
    source += function(inp, name)
source += inp[inp.index('static f32 rstickSmoothed'):inp.index('static s32 bindCaptureActive')]
for name in ['bmoveGetSpeedThetaControlLimit', 'bmoveUpdateSpeedThetaControl']:
    source += function(move, name)
source += function(walk, 'bwalkUpdateSpeedTheta')
source += '\nvoid bmoveUpdateSpeedTheta(void) { bwalkUpdateSpeedTheta(); }\n'
source += function(walk, 'bwalkUpdateTheta')
source += function(mtx, 'mtx4LoadYRotation')
source += '\nvoid generatedTurn(int controlmode) {\nint contpad1=0; float tmp, fVar25; float mlookscale=1.f;\n' + turn + '\n}\n'
source += r'''
double wrapped(double d) {while(d>180)d-=360;while(d< -180)d+=360;return d;}
double measure(int fps, float boost, int raw, int mode, int natural, float acceleration, float smoothing, int camera) {
    strength=0; movedata.analogturn=0; movedata.aimturnleftspeed=0; movedata.aimturnrightspeed=0;
    player.speedtheta=player.speedthetacontrol=player.vv_theta=0;
    generatedTurn(mode); inputResetRightStickState(0); now=0;
    strength=boost; double total=0, cameraTotal=0, previous=0;
    for(int i=0;i<fps*8;i++) {
        int x=inputRightStickShape(inputAxisScale(raw,4096,1.f),curve,1.f),y=0;
        now += 1000000/fps; inputRightStickDynamic(&x,&y,0,acceleration,smoothing);
        int stick=x/256;
        movedata.analogturn=stick>5?stick-5:stick< -5?stick+5:0;
        movedata.cannaturalturn=natural;
        movedata.aimturnleftspeed=raw<0?1.f:0.f;
        movedata.aimturnrightspeed=raw>0?1.f:0.f;
        g_Vars.lvupdate60freal=60.f/fps;
        generatedTurn(mode);
        float old=player.vv_theta;
        bwalkUpdateTheta();
        Mtxf matrix;
        mtx4LoadYRotation(BADDEG2RAD(360-player.vv_theta), &matrix);
        double yaw=-atan2(matrix.m[2][0], matrix.m[2][2])*180/M_PI;
        if(i>=fps*4) { total+=wrapped(player.vv_theta-old); cameraTotal+=wrapped(yaw-previous); }
        previous=yaw;
    }
    return (camera?cameraTotal:total)/4;
}
int main(void) {
    int count=0;
    for(int fps=30;fps<=120;fps*=2) for(curve=0;curve<4;curve++)
    for(int sign=-1;sign<=1;sign+=2) for(int natural=0;natural<=1;natural++)
    for(int zoom=0;zoom<2;zoom++) for(int dyn=0;dyn<2;dyn++) {
        fov=zoom?30:60;
        float accel=dyn?.7f:0, smooth=dyn?.8f:0;
        int raw=sign*32767;
        double base=measure(fps,0,raw,CONTROLMODE_PC,natural,accel,smooth,0);
        double boosted=measure(fps,1,raw,CONTROLMODE_PC,natural,accel,smooth,0);
        double cbase=measure(fps,0,raw,CONTROLMODE_PC,natural,accel,smooth,1);
        double cboost=measure(fps,1,raw,CONTROLMODE_PC,natural,accel,smooth,1);
        if(fabs(boosted/base-2)>0.001 || fabs(cboost/cbase-2)>0.001) {
            fprintf(stderr,"FAIL fps=%d curve=%d sign=%d natural=%d zoom=%d dyn=%d body=%f camera=%f\n",fps,curve,sign,natural,zoom,dyn,boosted/base,cboost/cbase);
            return 1;
        }
        if(fps==60 && curve==2 && sign==1 && natural && !zoom && !dyn)
            printf("Precision full stick: base=%.6f boosted=%.6f deg/s; yaw ratio=%.6f camera ratio=%.6f\n",base,boosted,boosted/base,cboost/cbase);
        count++;
    }
    printf("PASS %d generated-code sustained yaw/camera scenarios\n",count);
}
'''
(out / 'generated-yaw-test.c').write_text(source)
subprocess.run(['cc', '-std=gnu11', '-O2', str(out/'generated-yaw-test.c'), '-lm', '-o', str(out/'yaw-test')], check=True)
result = subprocess.run([str(out/'yaw-test')], capture_output=True, text=True)
print(result.stdout, end='')
print(result.stderr, end='')
(out / 'results.json').write_text(json.dumps({
    'passed': result.returncode == 0, 'output': result.stdout + result.stderr,
    'scope': 'Generated turn block, input shaping/dynamics, walking yaw and engine yaw matrix. Does not validate physical RP5 input or full game runtime.',
    'sha256': {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in ['src/game/bondmove.c','src/game/bondwalk.c','port/src/input.c','src/lib/mtx.c']}
}, indent=2)+'\n')
raise SystemExit(result.returncode)
