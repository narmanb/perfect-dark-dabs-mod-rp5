package com.perfectdark.port;

import org.libsdl.app.SDLActivity;
import android.app.Activity;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.os.Environment;
import android.view.View;
import android.view.WindowManager;
import android.widget.Toast;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import java.io.File;

public class MainActivity extends SDLActivity {
    private static final int PERMISSION_REQUEST_CODE = 1;
    
    static {
        System.loadLibrary("SDL2");
        System.loadLibrary("pd");
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        android.util.Log.i("PerfectDark", "MainActivity onCreate start");
        
        super.onCreate(savedInstanceState);
        android.util.Log.i("PerfectDark", "MainActivity super.onCreate complete");
        
        // Keep screen on and hide system UI
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        
        // Handle display cutouts (remove white bars)
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.P) {
            getWindow().getAttributes().layoutInDisplayCutoutMode = 
                WindowManager.LayoutParams.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES;
        }
        
        hideSystemUI();
        
        // No external storage permissions needed with SAF + app-scoped storage
        initializeGame();
        android.util.Log.i("PerfectDark", "MainActivity onCreate complete");
    }
    
    private void hideSystemUI() {
        View decorView = getWindow().getDecorView();
        int uiOptions = View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_STABLE;
        decorView.setSystemUiVisibility(uiOptions);
    }
    
    private boolean checkPermissions() { return true; }
    
    private void requestPermissions() { /* no-op */ }
    
    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        // No storage permissions requested; proceed regardless
    }
    
    private void initializeGame() {
        android.util.Log.i("PerfectDark", "initializeGame start");
        
        // Create data directory in external storage
        File dataDir = new File(getExternalFilesDir(null), "data");
        android.util.Log.i("PerfectDark", "Data dir: " + dataDir.getAbsolutePath());
        if (!dataDir.exists()) {
            dataDir.mkdirs();
        }
        
        // Initialize native game
        android.util.Log.i("PerfectDark", "Calling nativeInit");
        nativeInit(dataDir.getAbsolutePath());
        
        android.util.Log.i("PerfectDark", "initializeGame complete");
    }
    
    @Override
    protected void onResume() {
        super.onResume();
        hideSystemUI();
    }
    
    @Override
    protected void onPause() {
        super.onPause();
    }
    
    @Override
    protected void onDestroy() {
        super.onDestroy();
        nativeDestroy();
    }

    // Native methods
    public native void nativeInit(String dataPath);
    public native void nativeStartGame();
    public native void nativeDestroy();
}
