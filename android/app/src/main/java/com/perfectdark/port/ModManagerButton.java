package com.perfectdark.port;

import android.content.Context;
import android.content.Intent;
import android.util.AttributeSet;

import androidx.annotation.Nullable;
import androidx.appcompat.widget.AppCompatButton;

/** Launcher button kept self-contained so the ROM launcher does not own mod-manager logic. */
public class ModManagerButton extends AppCompatButton {
    public ModManagerButton(Context context) {
        super(context);
        init();
    }

    public ModManagerButton(Context context, @Nullable AttributeSet attrs) {
        super(context, attrs);
        init();
    }

    public ModManagerButton(Context context, @Nullable AttributeSet attrs, int defStyleAttr) {
        super(context, attrs, defStyleAttr);
        init();
    }

    private void init() {
        setOnClickListener(v -> getContext().startActivity(new Intent(getContext(), ModManagerActivity.class)));
    }
}
