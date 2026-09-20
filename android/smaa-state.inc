// Save before ANY lazy initialization: uploading AreaTex/SearchTex binds textures.
// Saving after init leaks SearchTex into the game's cached texture binding.
struct PostFxState {
    GLint program, vao, active, textures[3], samplers[3] = {};
    GLint read_fbo, draw_fbo, read_buffer, back_read_buffer, viewport[4];
    GLint unpack_buffer, unpack_align, unpack_row, unpack_skip_rows, unpack_skip_pixels;
    GLboolean mask[4];
    const GLenum caps[8] = { GL_BLEND, GL_DEPTH_TEST, GL_SCISSOR_TEST, GL_CULL_FACE,
        GL_STENCIL_TEST, GL_RASTERIZER_DISCARD, GL_SAMPLE_ALPHA_TO_COVERAGE, GL_SAMPLE_COVERAGE };
    GLboolean enabled[8], dither;

    PostFxState() {
        glGetIntegerv(GL_CURRENT_PROGRAM, &program);
        glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &vao);
        glGetIntegerv(GL_ACTIVE_TEXTURE, &active);
        glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &read_fbo);
        glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &draw_fbo);
        glGetIntegerv(GL_READ_BUFFER, &read_buffer);
        glBindFramebuffer(GL_READ_FRAMEBUFFER, 0);
        glGetIntegerv(GL_READ_BUFFER, &back_read_buffer);
        glBindFramebuffer(GL_READ_FRAMEBUFFER, read_fbo);
        glGetIntegerv(GL_VIEWPORT, viewport);
        glGetBooleanv(GL_COLOR_WRITEMASK, mask);
        for (int n = 0; n < 3; ++n) {
            glActiveTexture(GL_TEXTURE0 + n);
            glGetIntegerv(GL_TEXTURE_BINDING_2D, &textures[n]);
            if (glad_glBindSampler) {
                glGetIntegerv(GL_SAMPLER_BINDING, &samplers[n]);
                glBindSampler(n, 0);
            }
        }
        glGetIntegerv(GL_PIXEL_UNPACK_BUFFER_BINDING, &unpack_buffer);
        glGetIntegerv(GL_UNPACK_ALIGNMENT, &unpack_align);
        glGetIntegerv(GL_UNPACK_ROW_LENGTH, &unpack_row);
        glGetIntegerv(GL_UNPACK_SKIP_ROWS, &unpack_skip_rows);
        glGetIntegerv(GL_UNPACK_SKIP_PIXELS, &unpack_skip_pixels);
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0);
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
        glPixelStorei(GL_UNPACK_ROW_LENGTH, 0);
        glPixelStorei(GL_UNPACK_SKIP_ROWS, 0);
        glPixelStorei(GL_UNPACK_SKIP_PIXELS, 0);
        for (int n = 0; n < 8; ++n) {
            enabled[n] = glIsEnabled(caps[n]);
            glDisable(caps[n]);
        }
        dither = glIsEnabled(GL_DITHER);
        glDisable(GL_DITHER); // Edge and weight channels are data, not display colors.
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
        glActiveTexture(GL_TEXTURE0);
    }

    ~PostFxState() {
        for (int n = 0; n < 8; ++n) {
            if (enabled[n]) glEnable(caps[n]); else glDisable(caps[n]);
        }
        if (dither) glEnable(GL_DITHER); else glDisable(GL_DITHER);
        glColorMask(mask[0], mask[1], mask[2], mask[3]);
        glBindFramebuffer(GL_READ_FRAMEBUFFER, 0);
        glReadBuffer(back_read_buffer);
        glBindFramebuffer(GL_READ_FRAMEBUFFER, read_fbo);
        glReadBuffer(read_buffer);
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, draw_fbo);
        glUseProgram(program);
        glBindVertexArray(vao);
        for (int n = 0; n < 3; ++n) {
            glActiveTexture(GL_TEXTURE0 + n);
            glBindTexture(GL_TEXTURE_2D, textures[n]);
            if (glad_glBindSampler) glBindSampler(n, samplers[n]);
        }
        glActiveTexture(active);
        glViewport(viewport[0], viewport[1], viewport[2], viewport[3]);
        glBindBuffer(GL_PIXEL_UNPACK_BUFFER, unpack_buffer);
        glPixelStorei(GL_UNPACK_ALIGNMENT, unpack_align);
        glPixelStorei(GL_UNPACK_ROW_LENGTH, unpack_row);
        glPixelStorei(GL_UNPACK_SKIP_ROWS, unpack_skip_rows);
        glPixelStorei(GL_UNPACK_SKIP_PIXELS, unpack_skip_pixels);
    }
};
