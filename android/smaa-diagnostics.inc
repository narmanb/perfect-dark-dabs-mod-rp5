// One audit after a selection/resize and another 120 frames later, not every frame.
// Read the actual presented resolve BEFORE a requested diagnostic visualization.
static void gfx_opengl_smaa_audit(int width, int height) {
    const size_t pixels = (size_t)width * height;
    std::vector<unsigned char> source(pixels * 4), resolved(pixels * 4), data(pixels * 4);
    GLint pack_buffer, pack_align, pack_row, pack_rows, pack_pixels;
    glGetIntegerv(GL_PIXEL_PACK_BUFFER_BINDING, &pack_buffer);
    glGetIntegerv(GL_PACK_ALIGNMENT, &pack_align);
    glGetIntegerv(GL_PACK_ROW_LENGTH, &pack_row);
    glGetIntegerv(GL_PACK_SKIP_ROWS, &pack_rows);
    glGetIntegerv(GL_PACK_SKIP_PIXELS, &pack_pixels);
    glBindBuffer(GL_PIXEL_PACK_BUFFER, 0);
    glPixelStorei(GL_PACK_ALIGNMENT, 1);
    glPixelStorei(GL_PACK_ROW_LENGTH, 0);
    glPixelStorei(GL_PACK_SKIP_ROWS, 0);
    glPixelStorei(GL_PACK_SKIP_PIXELS, 0);

    GLenum prior = glGetError();
    if (prior != GL_NO_ERROR) sysLogPrintf(LOG_WARNING, "SMAA: render GL error 0x%x", prior);
    glBindFramebuffer(GL_READ_FRAMEBUFFER, smaa_fbo[0]);
    glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, source.data());
    glBindFramebuffer(GL_READ_FRAMEBUFFER, 0);
    glReadBuffer(GL_BACK);
    glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, resolved.data());
    unsigned edges = 0, weights = 0, changed = 0, max_delta = 0;
    uint64_t total_delta = 0;
    glBindFramebuffer(GL_READ_FRAMEBUFFER, smaa_fbo[1]);
    glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, data.data());
    for (size_t p = 0; p < pixels; ++p) edges += data[p * 4] || data[p * 4 + 1];
    glBindFramebuffer(GL_READ_FRAMEBUFFER, smaa_fbo[2]);
    glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, data.data());
    for (size_t p = 0; p < pixels; ++p) {
        weights += data[p * 4] || data[p * 4 + 1] || data[p * 4 + 2] || data[p * 4 + 3];
        unsigned delta = 0;
        for (int c = 0; c < 3; ++c) {
            const unsigned d = (unsigned)abs((int)source[p * 4 + c] - (int)resolved[p * 4 + c]);
            if (d > delta) delta = d;
        }
        if (delta != 0) {
            ++changed;
            total_delta += delta;
        }
        if (delta > max_delta) max_delta = delta;
    }
    const double avg_delta = changed ? (double)total_delta / (double)changed : 0.0;
    GLenum error = glGetError();
    glBindFramebuffer(GL_READ_FRAMEBUFFER, 0);
    glBindBuffer(GL_PIXEL_PACK_BUFFER, pack_buffer);
    glPixelStorei(GL_PACK_ALIGNMENT, pack_align);
    glPixelStorei(GL_PACK_ROW_LENGTH, pack_row);
    glPixelStorei(GL_PACK_SKIP_ROWS, pack_rows);
    glPixelStorei(GL_PACK_SKIP_PIXELS, pack_pixels);
    if (error != GL_NO_ERROR || prior != GL_NO_ERROR) {
        snprintf(gfx_smaa_status, 96, "GL ERR 0x%x", error ? error : prior);
    } else {
        // Fit the useful magnitude diagnostics in one menu value column.
        // E keeps the existing CI/status sentinel; W remains in the detailed log.
        // D = changed pixels, M = maximum per-pixel RGB delta, A = average delta
        // among changed pixels, all deltas measured on the 0..255 channel scale.
        snprintf(gfx_smaa_status, 96, "E:%u D%u M%u A%.1f", edges, changed, max_delta, avg_delta);
    }
    sysLogPrintf(LOG_NOTE, "SMAA audit: mode=%d frame=%u size=%dx%d edges=%u weights=%u changed=%u maxDelta=%u avgDelta=%.2f error=0x%x",
        gfx_post_aa, frame_count, width, height, edges, weights, changed, max_delta, avg_delta, error ? error : prior);
}
