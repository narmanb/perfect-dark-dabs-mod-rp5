// This harness calls the production-generated grade_frame; it does not reimplement SMAA.
static int state_errors, trace_errors, draw_count, gl_errors;
static PFNGLDRAWARRAYSPROC real_draw;
static std::vector<GLint> capture_state() {
    std::vector<GLint> state;
    const GLenum names[] = {GL_CURRENT_PROGRAM, GL_VERTEX_ARRAY_BINDING, GL_ACTIVE_TEXTURE,
        GL_READ_FRAMEBUFFER_BINDING, GL_DRAW_FRAMEBUFFER_BINDING, GL_READ_BUFFER,
        GL_PIXEL_UNPACK_BUFFER_BINDING, GL_UNPACK_ALIGNMENT, GL_UNPACK_ROW_LENGTH,
        GL_UNPACK_SKIP_ROWS, GL_UNPACK_SKIP_PIXELS, GL_PIXEL_PACK_BUFFER_BINDING,
        GL_PACK_ALIGNMENT, GL_PACK_ROW_LENGTH, GL_PACK_SKIP_ROWS, GL_PACK_SKIP_PIXELS};
    for (GLenum name : names) {GLint value;glGetIntegerv(name,&value);state.push_back(value);}
    GLint values[4];glGetIntegerv(GL_VIEWPORT,values);state.insert(state.end(),values,values+4);
    glGetIntegerv(GL_COLOR_WRITEMASK,values);state.insert(state.end(),values,values+4);
    const GLenum caps[]={GL_BLEND,GL_DEPTH_TEST,GL_SCISSOR_TEST,GL_CULL_FACE,GL_STENCIL_TEST,
        GL_RASTERIZER_DISCARD,GL_SAMPLE_ALPHA_TO_COVERAGE,GL_SAMPLE_COVERAGE,GL_DITHER};
    for(GLenum cap:caps)state.push_back(glIsEnabled(cap));
    GLint active;glGetIntegerv(GL_ACTIVE_TEXTURE,&active);
    for(int n=0;n<3;n++) {
        glActiveTexture(GL_TEXTURE0+n);
        GLint value;glGetIntegerv(GL_TEXTURE_BINDING_2D,&value);state.push_back(value);
        glGetIntegerv(GL_SAMPLER_BINDING,&value);state.push_back(value);
    }
    glActiveTexture(active);
    return state;
}
static void check_input(GLuint prog,const char *name,GLuint expected,int unit) {
    GLint loc=glGetUniformLocation(prog,name),value=-1;
    if(loc<0){trace_errors++;return;}
    glGetUniformiv(prog,loc,&value);
    if(value!=unit){trace_errors++;return;}
    glActiveTexture(GL_TEXTURE0+unit);glGetIntegerv(GL_TEXTURE_BINDING_2D,&value);
    if((GLuint)value!=expected)trace_errors++;
    GLint target;glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING,&target);
    if(target) {
        GLint attached;glGetFramebufferAttachmentParameteriv(GL_DRAW_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,
            GL_FRAMEBUFFER_ATTACHMENT_OBJECT_NAME,&attached);
        if(attached==value)trace_errors++; // Illegal texture feedback.
    }
}
static void APIENTRY traced_draw(GLenum mode,GLint first,GLsizei count) {
    draw_count++;
    GLint active,prog,target,viewport[4];
    glGetIntegerv(GL_ACTIVE_TEXTURE,&active);glGetIntegerv(GL_CURRENT_PROGRAM,&prog);
    glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING,&target);glGetIntegerv(GL_VIEWPORT,viewport);
    int w=framebuffers[0].width,h=framebuffers[0].height;
    if(viewport[0]||viewport[1]||viewport[2]!=w||viewport[3]!=h)trace_errors++;
    int q=gfx_post_aa==4;
    if((GLuint)prog==grade_prog) {
        check_input(prog,"uTex",grade_tex,0);
        bool aa=gfx_post_aa>=3&&smaa_ready[q];
        if((GLuint)target!=(aa?smaa_fbo[0]:0))trace_errors++;
    } else {
        GLfloat metrics[4];glGetUniformfv(prog,glGetUniformLocation(prog,"uSmaaMetrics"),metrics);
        if(fabs(metrics[0]-1.f/w)>1e-8||fabs(metrics[1]-1.f/h)>1e-8||metrics[2]!=w||metrics[3]!=h)trace_errors++;
        if((GLuint)prog==smaa_edge_prog[q]) {
            if((GLuint)target!=smaa_fbo[1])trace_errors++;
            check_input(prog,"uColorTex",smaa_tex[0],0);
        } else if((GLuint)prog==smaa_weight_prog[q]) {
            if((GLuint)target!=smaa_fbo[2])trace_errors++;
            check_input(prog,"uEdges",smaa_tex[1],0);
            check_input(prog,"uArea",smaa_area_tex,1);check_input(prog,"uSearch",smaa_search_tex,2);
            for(int n=0;n<3;n++) {
                glActiveTexture(GL_TEXTURE0+n);
                GLint v;
                for(GLenum p:{GL_TEXTURE_MIN_FILTER,GL_TEXTURE_MAG_FILTER}){
                    glGetTexParameteriv(GL_TEXTURE_2D,p,&v);if(v!=GL_LINEAR)trace_errors++;
                }
                for(GLenum p:{GL_TEXTURE_WRAP_S,GL_TEXTURE_WRAP_T}){
                    glGetTexParameteriv(GL_TEXTURE_2D,p,&v);if(v!=GL_CLAMP_TO_EDGE)trace_errors++;
                }
            }
        } else if((GLuint)prog==smaa_neighborhood_prog[q]) {
            if(target)trace_errors++;
            check_input(prog,"uColorTex",smaa_tex[0],0);check_input(prog,"uBlendTex",smaa_tex[2],1);
        } else trace_errors++;
    }
    glActiveTexture(active);
    real_draw(mode,first,count);
}
extern "C" int init(GLADloadproc loader) {int ok=gladLoadGLES2Loader(loader);real_draw=glad_glDrawArrays;return ok;}
extern "C" const char *shader(int pass,int ultra) {static std::string s;s=gfx_opengl_smaa_fragment_source(ultra,pass);return s.c_str();}
extern "C" const char *status() {return gfx_smaa_status;}
extern "C" int ready(int q) {return smaa_ready[q];}
extern "C" int errors(int which) {return which==0?state_errors:which==1?trace_errors:which==2?gl_errors:draw_count;}
extern "C" void free_grade() {gfx_opengl_grade_free();grade_failed=false;}
extern "C" void set_view(int view) {gfx_smaa_debug=view;}
extern "C" void set_sharpen(int value) {gfx_post_sharpen=value;}
extern "C" void render(int w,int h,int aa,int hostile,const unsigned char *input,
        unsigned char *output,unsigned char *edges,unsigned char *weights,unsigned char *graded) {
    framebuffers[0].width=w;framebuffers[0].height=h;frame_count++;
    state_errors=trace_errors=draw_count=gl_errors=0;
    const GLenum caps[]={GL_SCISSOR_TEST,GL_BLEND,GL_DEPTH_TEST,GL_CULL_FACE,GL_STENCIL_TEST,
        GL_RASTERIZER_DISCARD,GL_SAMPLE_ALPHA_TO_COVERAGE,GL_SAMPLE_COVERAGE};
    for(GLenum cap:caps)glDisable(cap);
    glColorMask(1,1,1,1);glBindBuffer(GL_PIXEL_UNPACK_BUFFER,0);glBindBuffer(GL_PIXEL_PACK_BUFFER,0);
    for(GLenum p:{GL_UNPACK_ROW_LENGTH,GL_UNPACK_SKIP_ROWS,GL_UNPACK_SKIP_PIXELS,
            GL_PACK_ROW_LENGTH,GL_PACK_SKIP_ROWS,GL_PACK_SKIP_PIXELS})glPixelStorei(p,0);
    glActiveTexture(GL_TEXTURE0);glBindSampler(0,0);
    GLuint t[3],f;glGenTextures(3,t);glBindTexture(GL_TEXTURE_2D,t[0]);
    glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA8,w,h,0,GL_RGBA,GL_UNSIGNED_BYTE,input);
    glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
    glGenFramebuffers(1,&f);glBindFramebuffer(GL_READ_FRAMEBUFFER,f);
    glFramebufferTexture2D(GL_READ_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,t[0],0);
    glBindFramebuffer(GL_DRAW_FRAMEBUFFER,0);
    glBlitFramebuffer(0,0,w,h,0,0,w,h,GL_COLOR_BUFFER_BIT,GL_NEAREST);
    glBindFramebuffer(GL_FRAMEBUFFER,0);
    for(int n=0;n<3;n++){glActiveTexture(GL_TEXTURE0+n);glBindTexture(GL_TEXTURE_2D,t[n]);}
    GLuint sampler=0,buffer=0;
    if(hostile) {
        glGenSamplers(1,&sampler);glSamplerParameteri(sampler,GL_TEXTURE_MIN_FILTER,GL_NEAREST);
        glSamplerParameteri(sampler,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
        for(int n=0;n<3;n++)glBindSampler(n,sampler);
        glGenBuffers(1,&buffer);glBindBuffer(GL_PIXEL_UNPACK_BUFFER,buffer);
        glBufferData(GL_PIXEL_UNPACK_BUFFER,64,NULL,GL_STATIC_DRAW);
        glBindBuffer(GL_PIXEL_PACK_BUFFER,buffer);
        glPixelStorei(GL_UNPACK_ROW_LENGTH,7);glPixelStorei(GL_UNPACK_SKIP_ROWS,1);glPixelStorei(GL_UNPACK_SKIP_PIXELS,1);
        glPixelStorei(GL_PACK_ROW_LENGTH,7);glPixelStorei(GL_PACK_SKIP_ROWS,1);glPixelStorei(GL_PACK_SKIP_PIXELS,1);
        glEnable(GL_STENCIL_TEST);glStencilFunc(GL_NEVER,0,0xff);
        glEnable(GL_SCISSOR_TEST);glScissor(17,13,9,7);glEnable(GL_BLEND);glEnable(GL_DEPTH_TEST);glEnable(GL_CULL_FACE);
        glEnable(GL_RASTERIZER_DISCARD);glEnable(GL_SAMPLE_ALPHA_TO_COVERAGE);glEnable(GL_SAMPLE_COVERAGE);
        glColorMask(1,0,1,0);glViewport(9,11,w-30,h-30);
        glBindFramebuffer(GL_READ_FRAMEBUFFER,f);
    }
    glActiveTexture(GL_TEXTURE1); // Mimic a game draw ending on tile 1.
    auto before=capture_state();
    gfx_post_aa=aa;glad_glDrawArrays=traced_draw;
    gfx_opengl_grade_frame();
    glad_glDrawArrays=real_draw;
    auto after=capture_state();
    for(size_t n=0;n<before.size();n++) if(before[n]!=after[n]) {
        fprintf(stderr,"State slot %zu changed: %d -> %d\n",n,before[n],after[n]);state_errors++;
    }
    for(GLenum cap:caps)glDisable(cap);
    glColorMask(1,1,1,1);
    glBindBuffer(GL_PIXEL_PACK_BUFFER,0);glBindBuffer(GL_PIXEL_UNPACK_BUFFER,0);
    for(GLenum p:{GL_PACK_ROW_LENGTH,GL_PACK_SKIP_ROWS,GL_PACK_SKIP_PIXELS,
            GL_UNPACK_ROW_LENGTH,GL_UNPACK_SKIP_ROWS,GL_UNPACK_SKIP_PIXELS})glPixelStorei(p,0);
    glBindFramebuffer(GL_FRAMEBUFFER,0);glReadBuffer(GL_BACK);
    glReadPixels(0,0,w,h,GL_RGBA,GL_UNSIGNED_BYTE,output);
    unsigned char *targets[]={graded,edges,weights};
    if(smaa_ready[0]||smaa_ready[1])for(int k=0;k<3;k++){
        glBindFramebuffer(GL_FRAMEBUFFER,smaa_fbo[k]);glReadPixels(0,0,w,h,GL_RGBA,GL_UNSIGNED_BYTE,targets[k]);
    }
    glBindFramebuffer(GL_FRAMEBUFFER,0);
    for(int n=0;n<3;n++){glBindSampler(n,0);glActiveTexture(GL_TEXTURE0+n);glBindTexture(GL_TEXTURE_2D,0);}
    glDeleteFramebuffers(1,&f);glDeleteTextures(3,t);
    if(sampler)glDeleteSamplers(1,&sampler);if(buffer)glDeleteBuffers(1,&buffer);
    GLenum e;while((e=glGetError())!=GL_NO_ERROR){fprintf(stderr,"GL error: 0x%x\n",e);gl_errors++;}
}
