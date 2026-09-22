package com.perfectdark.port;

import androidx.appcompat.app.AppCompatActivity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AlertDialog;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.security.DigestInputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * Launcher that ensures the Perfect Dark ROM exists in
 * getExternalFilesDir(null)/data as pd.ntsc-final.z64 before starting SDL.
 */
public class LauncherActivity extends AppCompatActivity {
    private static final String ROM_FILE_NAME = "pd.ntsc-final.z64";
    private static final String ROM_TEMP_FILE_NAME = ROM_FILE_NAME + ".tmp";
    private static final String GE_ROM_FILE_NAME = "goldeneye-007-us.z64";
    private static final String GE_ROM_TEMP_FILE_NAME = GE_ROM_FILE_NAME + ".tmp";
    private static final long EXPECTED_GE_ROM_SIZE = 0xC00000L;
    private static final long EXPECTED_ROM_SIZE = 32L * 1024L * 1024L;

    // Primary: NTSC-U Rev 1 (v1.1) .z64 (recommended)
    private static final String MD5_NTSC_V11 = "e03b088b6ac9e0080440efed07c1e40f";
    // Secondary: NTSC-U v1.0 .z64 (not recommended, but optionally allowed)
    private static final String MD5_NTSC_V10 = "7f4171b0c8d17815be37913f535e4e93";

    private View missingRomView;
    private TextView infoText;
    private Button pickRomButton;
    private TextView geStatusText;
    private Button pickGeRomButton;
    private Button playButton;
    private boolean pickingGoldenEye;

    private final ActivityResultLauncher<String[]> romPicker =
            registerForActivityResult(new ActivityResultContracts.OpenDocument(), this::onRomPicked);

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_launcher);

        missingRomView = findViewById(R.id.missingRomContainer);
        infoText = findViewById(R.id.infoText);
        pickRomButton = findViewById(R.id.pickRomButton);
        geStatusText = findViewById(R.id.geStatusText);
        pickGeRomButton = findViewById(R.id.pickGeRomButton);
        playButton = findViewById(R.id.playButton);

        pickRomButton.setOnClickListener(v -> { pickingGoldenEye = false; openRomPicker(); });
        pickGeRomButton.setOnClickListener(v -> { pickingGoldenEye = true; openRomPicker(); });
        playButton.setOnClickListener(v -> startGame());

        ensureDataDir();
        cleanupInterruptedCopy();
        cleanupInterruptedGeCopy();

        updateGoldenEyeStatus();

        if (romExists()) {
            File target = getRomFile();
            int hashStatus = checkRomHash(target);
            if (hashStatus == 0) {
                showLauncherReady();
            } else if (hashStatus == 1) {
                showV10WarningDialog(target);
            } else {
                showHashMismatchDialog(target, safeMd5(target), target.length(), false);
            }
        } else {
            showMissingRomUi();
        }
    }

    private File getGameDataDir() {
        return new File(getExternalFilesDir(null), "data");
    }

    private File getRomFile() {
        return new File(getGameDataDir(), ROM_FILE_NAME);
    }

    private File getGoldenEyeRomFile() {
        return new File(getGameDataDir(), GE_ROM_FILE_NAME);
    }

    private File getGoldenEyeTempFile() {
        return new File(getGameDataDir(), GE_ROM_TEMP_FILE_NAME);
    }

    private File getTempRomFile() {
        return new File(getGameDataDir(), ROM_TEMP_FILE_NAME);
    }

    private void ensureDataDir() {
        File dataDir = getGameDataDir();
        if (!dataDir.exists() && !dataDir.mkdirs()) {
            Toast.makeText(this, "Unable to create game data folder", Toast.LENGTH_LONG).show();
        }
    }

    private void cleanupInterruptedCopy() {
        File temp = getTempRomFile();
        if (temp.exists()) {
            //noinspection ResultOfMethodCallIgnored
            temp.delete();
        }
    }

    private void cleanupInterruptedGeCopy() {
        File temp = getGoldenEyeTempFile();
        if (temp.exists()) temp.delete();
    }

    private boolean romExists() {
        File target = getRomFile();
        return target.exists() && target.length() > 0;
    }

    private void showLauncherReady() {
        missingRomView.setVisibility(View.VISIBLE);
        infoText.setText("Perfect Dark ROM: verified and ready.");
        pickRomButton.setText("Replace Perfect Dark ROM");
        playButton.setVisibility(View.VISIBLE);
        updateGoldenEyeStatus();
    }

    private void updateGoldenEyeStatus() {
        File ge = getGoldenEyeRomFile();
        if (ge.exists() && ge.length() == EXPECTED_GE_ROM_SIZE) {
            geStatusText.setText("GoldenEye 007 ROM: imported — GE-X Plus conversion will run automatically.");
            pickGeRomButton.setText("Replace GoldenEye ROM");
        } else {
            geStatusText.setText("GoldenEye 007 ROM: optional — not imported.");
            pickGeRomButton.setText("Select GoldenEye 007 ROM");
        }
    }

    private void showMissingRomUi() {
        missingRomView.setVisibility(View.VISIBLE);
        infoText.setText("ROM not found. Select your Perfect Dark NTSC-U ROM.\n"
                + "The filename does not matter. A verified copy will be stored as "
                + ROM_FILE_NAME + ".");
    }

    private void openRomPicker() {
        romPicker.launch(new String[]{"application/octet-stream", "*/*"});
    }

    private void onRomPicked(@Nullable Uri uri) {
        if (pickingGoldenEye) {
            onGoldenEyeRomPicked(uri);
            return;
        }
        if (uri == null) {
            Toast.makeText(this, "No file selected", Toast.LENGTH_SHORT).show();
            return;
        }

        final int flags = Intent.FLAG_GRANT_READ_URI_PERMISSION;
        try {
            getContentResolver().takePersistableUriPermission(uri, flags);
        } catch (Exception ignored) {
            // Some providers do not support persistable permissions. The copy below still works.
        }

        final CopyResult result;
        try {
            result = copyAndVerifyRom(uri);
        } catch (IOException | NoSuchAlgorithmException e) {
            cleanupInterruptedCopy();
            Toast.makeText(this, "Failed to import ROM: " + e.getMessage(), Toast.LENGTH_LONG).show();
            return;
        }

        if (result.hashStatus == 0) {
            Toast.makeText(this, "NTSC-U v1.1 verified — launcher ready", Toast.LENGTH_SHORT).show();
            showLauncherReady();
        } else if (result.hashStatus == 1) {
            showV10WarningDialog(getRomFile());
        } else {
            // A wrong source is never installed over a previously verified ROM.
            showHashMismatchDialog(getTempRomFile(), result.md5, result.bytes, true);
        }
    }

    /**
     * Copies the selected URI to a temporary file while hashing the exact bytes received.
     * It then hashes the temporary file independently. Only a byte-for-byte verified copy
     * replaces pd.ntsc-final.z64.
     */
    private CopyResult copyAndVerifyRom(Uri sourceUri) throws IOException, NoSuchAlgorithmException {
        ensureDataDir();

        File temp = getTempRomFile();
        if (temp.exists() && !temp.delete()) {
            throw new IOException("Could not clear previous temporary ROM copy");
        }

        MessageDigest sourceDigest = MessageDigest.getInstance("MD5");
        long bytesCopied = 0;

        try (InputStream in = getContentResolver().openInputStream(sourceUri);
             FileOutputStream out = new FileOutputStream(temp)) {
            if (in == null) {
                throw new IOException("Unable to open selected file");
            }

            byte[] buf = new byte[64 * 1024];
            int read;
            while ((read = in.read(buf)) != -1) {
                if (read == 0) continue;
                out.write(buf, 0, read);
                sourceDigest.update(buf, 0, read);
                bytesCopied += read;
            }
            out.flush();
            out.getFD().sync();
        }

        String sourceMd5 = toHex(sourceDigest.digest());

        if (temp.length() != bytesCopied) {
            throw new IOException("Copy size mismatch: read " + bytesCopied
                    + " bytes but wrote " + temp.length());
        }

        String copiedMd5 = computeMd5(temp);
        if (!sourceMd5.equalsIgnoreCase(copiedMd5)) {
            throw new IOException("Copy verification failed: source MD5 " + sourceMd5
                    + " but copied MD5 " + copiedMd5);
        }

        int status = classifyMd5(sourceMd5);
        if (status < 0) {
            return new CopyResult(status, sourceMd5, bytesCopied);
        }

        File target = getRomFile();
        if (target.exists() && !target.delete()) {
            throw new IOException("Could not replace existing ROM");
        }
        if (!temp.renameTo(target)) {
            throw new IOException("Verified ROM could not be moved into the game data folder");
        }

        // One final independent verification of the installed file.
        if (target.length() != bytesCopied) {
            throw new IOException("Installed ROM size changed unexpectedly");
        }
        String installedMd5 = computeMd5(target);
        if (!sourceMd5.equalsIgnoreCase(installedMd5)) {
            throw new IOException("Installed ROM failed final verification");
        }

        return new CopyResult(status, installedMd5, bytesCopied);
    }


    private void onGoldenEyeRomPicked(@Nullable Uri uri) {
        if (uri == null) {
            Toast.makeText(this, "No file selected", Toast.LENGTH_SHORT).show();
            return;
        }
        ensureDataDir();
        File temp = getGoldenEyeTempFile();
        File target = getGoldenEyeRomFile();
        try {
            if (temp.exists()) temp.delete();
            long bytes = 0;
            byte[] header = new byte[0x40];
            int headerFilled = 0;
            try (InputStream in = getContentResolver().openInputStream(uri);
                 FileOutputStream out = new FileOutputStream(temp)) {
                if (in == null) throw new IOException("Unable to open selected file");
                byte[] buf = new byte[64 * 1024];
                int read;
                while ((read = in.read(buf)) != -1) {
                    if (read == 0) continue;
                    if (headerFilled < header.length) {
                        int n = Math.min(read, header.length - headerFilled);
                        System.arraycopy(buf, 0, header, headerFilled, n);
                        headerFilled += n;
                    }
                    out.write(buf, 0, read);
                    bytes += read;
                }
                out.flush();
                out.getFD().sync();
            }
            if (bytes != EXPECTED_GE_ROM_SIZE || headerFilled < header.length || !isGoldenEyeUsHeader(header)) {
                temp.delete();
                new AlertDialog.Builder(this)
                        .setTitle("GoldenEye ROM not supported")
                        .setMessage("GE-X Plus requires the 12 MiB GoldenEye 007 USA ROM. The filename and N64 dump byte order do not matter.")
                        .setPositiveButton("OK", null).show();
                return;
            }
            if (target.exists() && !target.delete()) throw new IOException("Could not replace existing GoldenEye ROM");
            if (!temp.renameTo(target)) throw new IOException("Could not install GoldenEye ROM");
            Toast.makeText(this, "GoldenEye 007 USA ROM imported", Toast.LENGTH_SHORT).show();
            updateGoldenEyeStatus();
        } catch (IOException e) {
            temp.delete();
            Toast.makeText(this, "Failed to import GoldenEye ROM: " + e.getMessage(), Toast.LENGTH_LONG).show();
        }
    }

    private boolean isGoldenEyeUsHeader(byte[] source) {
        if (source.length < 0x40) return false;
        byte[] h = source.clone();
        int magic = ((h[0] & 255) << 24) | ((h[1] & 255) << 16) | ((h[2] & 255) << 8) | (h[3] & 255);
        if (magic == 0x37804012) {
            for (int i = 0; i < h.length; i += 2) { byte t=h[i]; h[i]=h[i+1]; h[i+1]=t; }
        } else if (magic == 0x40123780) {
            for (int i = 0; i < h.length; i += 4) { byte t=h[i]; h[i]=h[i+3]; h[i+3]=t; t=h[i+1]; h[i+1]=h[i+2]; h[i+2]=t; }
        } else if (magic != 0x80371240) return false;
        byte[] crc = {(byte)0xdc,(byte)0xbc,0x50,(byte)0xd1,0x09,(byte)0xfd,0x1a,(byte)0xa3};
        byte[] name = "GOLDENEYE".getBytes(java.nio.charset.StandardCharsets.US_ASCII);
        byte[] code = "NGEE".getBytes(java.nio.charset.StandardCharsets.US_ASCII);
        for (int i=0;i<crc.length;i++) if (h[0x10+i]!=crc[i]) return false;
        for (int i=0;i<name.length;i++) if (h[0x20+i]!=name[i]) return false;
        for (int i=0;i<code.length;i++) if (h[0x3b+i]!=code[i]) return false;
        return true;
    }

    private void startGame() {
        // Keep the launcher as the task root. This makes the pre-game managers
        // reachable again after SDL exits and allows a home-screen relaunch to
        // reset the task back to the launcher instead of resuming MainActivity.
        startActivity(new Intent(this, MainActivity.class));
    }

    // 0 = v1.1, 1 = v1.0, -1 = mismatch
    private int classifyMd5(String md5) {
        if (MD5_NTSC_V11.equalsIgnoreCase(md5)) return 0;
        if (MD5_NTSC_V10.equalsIgnoreCase(md5)) return 1;
        return -1;
    }

    private int checkRomHash(File file) {
        try {
            return classifyMd5(computeMd5(file));
        } catch (Exception e) {
            Toast.makeText(this, "Hash check failed: " + e.getMessage(), Toast.LENGTH_SHORT).show();
            return -1;
        }
    }

    private void showHashMismatchDialog(File file, String computed, long bytes, boolean selectedSource) {
        String sizeText = bytes + " bytes";
        if (bytes == EXPECTED_ROM_SIZE) {
            sizeText += " (32 MiB)";
        }

        String origin = selectedSource ? "Selected file" : "Stored ROM";
        new AlertDialog.Builder(this)
                .setTitle("ROM verification failed")
                .setMessage(origin + " does not match the clean NTSC-U ROM expected by the port.\n\n"
                        + "Expected v1.1 MD5:\n" + MD5_NTSC_V11 + "\n\n"
                        + "Got:\n" + computed + "\n\n"
                        + "Size: " + sizeText + "\n\n"
                        + "The filename is not checked.")
                .setPositiveButton("Pick another", (d, w) -> {
                    if (file.exists()) {
                        //noinspection ResultOfMethodCallIgnored
                        file.delete();
                    }
                    showMissingRomUi();
                    openRomPicker();
                })
                .setNegativeButton("Cancel", (d, w) -> {
                    if (selectedSource && file.exists()) {
                        //noinspection ResultOfMethodCallIgnored
                        file.delete();
                    }
                    showMissingRomUi();
                })
                .setCancelable(false)
                .show();
    }

    private void showV10WarningDialog(File target) {
        new AlertDialog.Builder(this)
                .setTitle("NTSC v1.0 detected")
                .setMessage("You selected NTSC-U v1.0 (not recommended).\n"
                        + "The port targets v1.1; some content may not work.\n\n"
                        + "Use v1.0 or pick a different ROM?")
                .setPositiveButton("Use ROM", (d, w) -> showLauncherReady())
                .setNegativeButton("Pick another", (d, w) -> {
                    try {
                        //noinspection ResultOfMethodCallIgnored
                        target.delete();
                    } catch (Exception ignored) {}
                    showMissingRomUi();
                    openRomPicker();
                })
                .setCancelable(false)
                .show();
    }

    private String safeMd5(File file) {
        try {
            return computeMd5(file);
        } catch (Exception e) {
            return "<error: " + e.getMessage() + ">";
        }
    }

    private String computeMd5(File file) throws IOException, NoSuchAlgorithmException {
        MessageDigest md = MessageDigest.getInstance("MD5");
        byte[] buffer = new byte[64 * 1024];
        try (InputStream in = new FileInputStream(file);
             DigestInputStream din = new DigestInputStream(in, md)) {
            while (din.read(buffer) != -1) {
                // DigestInputStream updates md.
            }
        }
        return toHex(md.digest());
    }

    private String toHex(byte[] digest) {
        StringBuilder sb = new StringBuilder(digest.length * 2);
        for (byte b : digest) {
            sb.append(Character.forDigit((b >>> 4) & 0x0f, 16));
            sb.append(Character.forDigit(b & 0x0f, 16));
        }
        return sb.toString();
    }

    private static class CopyResult {
        final int hashStatus;
        final String md5;
        final long bytes;

        CopyResult(int hashStatus, String md5, long bytes) {
            this.hashStatus = hashStatus;
            this.md5 = md5;
            this.bytes = bytes;
        }
    }
}
