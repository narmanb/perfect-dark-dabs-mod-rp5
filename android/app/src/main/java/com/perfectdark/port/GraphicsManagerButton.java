package com.perfectdark.port;

import android.content.Context;
import android.content.Intent;
import android.util.AttributeSet;

import androidx.annotation.Nullable;
import androidx.appcompat.widget.AppCompatButton;

/** Launcher button kept self-contained so the ROM launcher does not own graphics-manager logic. */
public class GraphicsManagerButton extends AppCompatButton {
    public GraphicsManagerButton(Context context) {
        super(context);
        init();
    }

    public GraphicsManagerButton(Context context, @Nullable AttributeSet attrs) {
        super(context, attrs);
        init();
    }

    public GraphicsManagerButton(Context context, @Nullable AttributeSet attrs, int defStyleAttr) {
        super(context, attrs, defStyleAttr);
        init();
    }

    private void init() {
        setOnClickListener(v -> getContext().startActivity(new Intent(getContext(), GraphicsManagerActivity.class)));
    }
}
