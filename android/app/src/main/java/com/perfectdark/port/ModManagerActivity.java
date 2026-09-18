package com.perfectdark.port;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.annotation.Nullable;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;

import android.content.Intent;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.OpenableColumns;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileOutputStream;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Android front end for Dab's native mod loader.
 *
 * Packages are copied into SDL's Android preference directory (getFilesDir()),
 * under mods/. The native mod scanner already treats $H/mods as an install
 * source and performs archive extraction / console-patch conversion at game
 * startup. Installed directories are selected by writing the same [Mod]
 * ModDir value used by the in-game Load Mods menu.
 */
public class ModManagerActivity extends AppCompatActivity {
    private static final int MAX_SCAN_DEPTH = 4;
    private static final String CONFIG_FILE = "pd.ini";
    private static final String CONFIG_SECTION = "Mod";
    private static final String CONFIG_KEY = "ModDir";

    private LinearLayout packageList;
    private LinearLayout installedList;
    private TextView activeText;
    private TextView summaryText;

    private final ActivityResultLauncher<String[]> modPicker =
            registerForActivityResult(new ActivityResultContracts.OpenDocument(), this::onModPicked);

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(buildUi());
        ensureModsDir();
        refreshLists();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (installedList != null) {
            refreshLists();
        }
    }

    private View buildUi() {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Color.BLACK);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(22), dp(18), dp(22), dp(28));
        scroll.addView(root, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT, ScrollView.LayoutParams.WRAP_CONTENT));

        TextView title = makeText("MOD MANAGER", 26, Color.WHITE);
        title.setTypeface(title.getTypeface(), android.graphics.Typeface.BOLD);
        root.addView(title);

        TextView help = makeText(
                "Import ZIP, 7Z, PK3, RAR, XDelta, BPS or IPS packages. "
                        + "New packages are unpacked/converted by the game on its next startup. "
                        + "Then reopen Mods and enable the installed mod. Only one general mod can be active at a time.",
                15, 0xffcccccc);
        addWithTop(root, help, 10);

        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        addWithTop(root, actions, 14);

        Button importButton = new Button(this);
        importButton.setText("Import Mod");
        importButton.setOnClickListener(v -> modPicker.launch(new String[]{"*/*"}));
        actions.addView(importButton, weightedButtonParams());

        Button refreshButton = new Button(this);
        refreshButton.setText("Refresh");
        refreshButton.setOnClickListener(v -> refreshLists());
        LinearLayout.LayoutParams refreshLp = weightedButtonParams();
        refreshLp.setMarginStart(dp(8));
        actions.addView(refreshButton, refreshLp);

        Button processButton = new Button(this);
        processButton.setText("Launch / Process Mods");
        processButton.setOnClickListener(v -> {
            Intent intent = new Intent(this, MainActivity.class);
            intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
            finish();
        });
        LinearLayout.LayoutParams processLp = weightedButtonParams();
        processLp.setMarginStart(dp(8));
        actions.addView(processButton, processLp);

        activeText = makeText("", 16, Color.WHITE);
        addWithTop(root, activeText, 16);

        Button disableAll = new Button(this);
        disableAll.setText("Disable Active Mod");
        disableAll.setOnClickListener(v -> {
            try {
                writeActiveMod("");
                Toast.makeText(this, "General mod disabled for next launch", Toast.LENGTH_SHORT).show();
                refreshLists();
            } catch (IOException e) {
                showError("Could not update mod selection", e);
            }
        });
        addWithTop(root, disableAll, 8);

        addDivider(root);
        root.addView(sectionTitle("IMPORTED PACKAGES"));
        summaryText = makeText("", 14, 0xffaaaaaa);
        addWithTop(root, summaryText, 4);
        packageList = new LinearLayout(this);
        packageList.setOrientation(LinearLayout.VERTICAL);
        addWithTop(root, packageList, 8);

        addDivider(root);
        root.addView(sectionTitle("INSTALLED MODS"));
        TextView installedHelp = makeText(
                "Enable chooses the mod for the next game launch. Mods containing segs/ are marked restart-required because those assets load only at startup.",
                14, 0xffaaaaaa);
        addWithTop(root, installedHelp, 4);
        installedList = new LinearLayout(this);
        installedList.setOrientation(LinearLayout.VERTICAL);
        addWithTop(root, installedList, 8);

        return scroll;
    }

    private void onModPicked(@Nullable Uri uri) {
        if (uri == null) return;

        String name = getDisplayName(uri);
        if (name == null || name.trim().isEmpty()) {
            Toast.makeText(this, "Could not determine selected filename", Toast.LENGTH_LONG).show();
            return;
        }
        name = sanitizeFilename(name);

        if (!isSupportedPackage(name)) {
            new AlertDialog.Builder(this)
                    .setTitle("Unsupported mod file")
                    .setMessage("Choose a .zip, .7z, .pk3, .rar, .xdelta, .bps or .ips mod package.")
                    .setPositiveButton("OK", null)
                    .show();
            return;
        }

        final File target = new File(getModsDir(), name);
        final String finalName = name;
        if (target.exists()) {
            new AlertDialog.Builder(this)
                    .setTitle("Replace imported package?")
                    .setMessage(finalName + " is already in the mod import folder.")
                    .setPositiveButton("Replace", (d, w) -> copyPackage(uri, target))
                    .setNegativeButton("Cancel", null)
                    .show();
        } else {
            copyPackage(uri, target);
        }
    }

    private void copyPackage(Uri uri, File target) {
        ensureModsDir();
        File temp = new File(getModsDir(), ".import-" + target.getName() + ".tmp");
        try {
            if (temp.exists() && !temp.delete()) {
                throw new IOException("Could not clear temporary import file");
            }

            long copied = 0;
            try (InputStream in = getContentResolver().openInputStream(uri);
                 FileOutputStream out = new FileOutputStream(temp)) {
                if (in == null) throw new IOException("Unable to open selected file");
                byte[] buffer = new byte[64 * 1024];
                int n;
                while ((n = in.read(buffer)) != -1) {
                    if (n == 0) continue;
                    out.write(buffer, 0, n);
                    copied += n;
                }
                out.flush();
                out.getFD().sync();
            }

            if (copied <= 0 || temp.length() != copied) {
                throw new IOException("Imported file was empty or incomplete");
            }
            if (target.exists() && !target.delete()) {
                throw new IOException("Could not replace existing package");
            }
            if (!temp.renameTo(target)) {
                throw new IOException("Could not move imported package into mods folder");
            }

            Toast.makeText(this,
                    "Imported " + target.getName() + ". Launch the game once to unpack/convert it.",
                    Toast.LENGTH_LONG).show();
            refreshLists();
        } catch (IOException e) {
            temp.delete();
            showError("Mod import failed", e);
        }
    }

    private void refreshLists() {
        ensureModsDir();
        String active = readActiveMod();
        activeText.setText(active.isEmpty() ? "Active general mod: None" : "Active general mod: " + active);

        List<File> packages = listPackages();
        List<ModEntry> mods = new ArrayList<>();
        collectMods(getModsDir(), 0, mods, new HashSet<>());
        Collections.sort(mods, Comparator.comparing(a -> a.name.toLowerCase(Locale.ROOT)));

        packageList.removeAllViews();
        installedList.removeAllViews();

        int pending = 0;
        if (packages.isEmpty()) {
            packageList.addView(makeText("No imported packages yet.", 14, 0xff888888));
        } else {
            for (File pkg : packages) {
                boolean processed = packageLooksProcessed(pkg);
                if (!processed) pending++;
                packageList.addView(buildPackageRow(pkg, processed));
            }
        }
        summaryText.setText(packages.size() + " package(s) • " + pending + " waiting for game startup processing");

        if (mods.isEmpty()) {
            installedList.addView(makeText(
                    "No installed mod directories found yet. Import a package and launch the game once so the native importer can create them.",
                    14, 0xff888888));
        } else {
            for (ModEntry mod : mods) {
                installedList.addView(buildModRow(mod, active));
            }
        }
    }

    private View buildPackageRow(File pkg, boolean processed) {
        LinearLayout card = makeCard();
        String state = processed ? "Processed/source package" : "Pending processing";
        card.addView(makeText(pkg.getName(), 16, Color.WHITE));
        TextView status = makeText(state + " • " + humanSize(pkg.length()), 13,
                processed ? 0xff9bc59b : 0xffffcc66);
        addWithTop(card, status, 2);

        Button remove = new Button(this);
        remove.setText("Remove Package");
        remove.setOnClickListener(v -> new AlertDialog.Builder(this)
                .setTitle("Remove imported package?")
                .setMessage("This removes the source package from the import folder. Already installed mod directories are not deleted.")
                .setPositiveButton("Remove", (d, w) -> {
                    if (!pkg.delete()) {
                        Toast.makeText(this, "Could not remove package", Toast.LENGTH_LONG).show();
                    }
                    refreshLists();
                })
                .setNegativeButton("Cancel", null)
                .show());
        addWithTop(card, remove, 6);
        return card;
    }

    private View buildModRow(ModEntry mod, String active) {
        LinearLayout card = makeCard();
        boolean isActive = mod.name.equalsIgnoreCase(active);
        boolean systemGe = mod.name.equalsIgnoreCase("GoldenEye Arenas");

        card.addView(makeText(mod.name, 17, Color.WHITE));
        StringBuilder state = new StringBuilder();
        if (systemGe) {
            state.append("GE-X Plus content • managed automatically");
        } else {
            state.append(isActive ? "ACTIVE" : "Inactive");
            if (mod.restartRequired) state.append(" • Restart required");
        }
        TextView status = makeText(state.toString(), 13,
                isActive ? 0xff88dd88 : (mod.restartRequired ? 0xffffcc66 : 0xffaaaaaa));
        addWithTop(card, status, 2);
        addWithTop(card, makeText(relativeModPath(mod.dir), 12, 0xff777777), 2);

        if (!systemGe) {
            LinearLayout buttons = new LinearLayout(this);
            buttons.setOrientation(LinearLayout.HORIZONTAL);
            addWithTop(card, buttons, 6);

            Button toggle = new Button(this);
            toggle.setText(isActive ? "Disable" : "Enable");
            toggle.setOnClickListener(v -> {
                try {
                    writeActiveMod(isActive ? "" : mod.name);
                    Toast.makeText(this,
                            isActive ? "Mod disabled for next launch" : mod.name + " enabled for next launch",
                            Toast.LENGTH_SHORT).show();
                    refreshLists();
                } catch (IOException e) {
                    showError("Could not update mod selection", e);
                }
            });
            buttons.addView(toggle, weightedButtonParams());

            Button delete = new Button(this);
            delete.setText("Delete Installed Files");
            LinearLayout.LayoutParams deleteLp = weightedButtonParams();
            deleteLp.setMarginStart(dp(8));
            buttons.addView(delete, deleteLp);
            delete.setOnClickListener(v -> confirmDeleteMod(mod, isActive));
        }

        return card;
    }

    private void confirmDeleteMod(ModEntry mod, boolean active) {
        new AlertDialog.Builder(this)
                .setTitle("Delete " + mod.name + "?")
                .setMessage("This deletes the installed mod directory. Source archives/patches are kept in the list above; remove those too if you do not want the native importer to recreate the mod.")
                .setPositiveButton("Delete", (d, w) -> {
                    try {
                        if (active) writeActiveMod("");
                        if (!deleteTree(mod.dir)) {
                            Toast.makeText(this, "Some mod files could not be deleted", Toast.LENGTH_LONG).show();
                        }
                        refreshLists();
                    } catch (IOException e) {
                        showError("Could not delete mod", e);
                    }
                })
                .setNegativeButton("Cancel", null)
                .show();
    }

    private List<File> listPackages() {
        List<File> result = new ArrayList<>();
        File[] files = getModsDir().listFiles();
        if (files != null) {
            for (File f : files) {
                if (f.isFile() && isSupportedPackage(f.getName())) result.add(f);
            }
        }
        Collections.sort(result, Comparator.comparing(a -> a.getName().toLowerCase(Locale.ROOT)));
        return result;
    }

    private void collectMods(File dir, int depth, List<ModEntry> out, Set<String> seen) {
        if (depth > MAX_SCAN_DEPTH || dir == null || !dir.isDirectory()) return;
        File[] children = dir.listFiles();
        if (children == null) return;

        for (File child : children) {
            if (!child.isDirectory()) continue;
            if (child.getName().startsWith(".") || child.getName().endsWith(".converting")) continue;

            if (looksLikeMod(child)) {
                try {
                    String canonical = child.getCanonicalPath();
                    if (seen.add(canonical)) {
                        out.add(new ModEntry(child, child.getName(), new File(child, "segs").isDirectory()));
                    }
                } catch (IOException ignored) {
                    String absolute = child.getAbsolutePath();
                    if (seen.add(absolute)) {
                        out.add(new ModEntry(child, child.getName(), new File(child, "segs").isDirectory()));
                    }
                }
            } else {
                collectMods(child, depth + 1, out, seen);
            }
        }
    }

    private boolean looksLikeMod(File dir) {
        return new File(dir, "files").isDirectory()
                || new File(dir, "segs").isDirectory()
                || new File(dir, "textures").isDirectory()
                || new File(dir, "modconfig.txt").isFile();
    }

    private boolean packageLooksProcessed(File pkg) {
        String stem = stripSupportedExtension(pkg.getName());
        return new File(getModsDir(), stem).exists();
    }

    private String readActiveMod() {
        File cfg = getConfigFile();
        if (!cfg.isFile()) return "";
        String section = "";
        try (BufferedReader in = new BufferedReader(new FileReader(cfg))) {
            String line;
            while ((line = in.readLine()) != null) {
                String trimmed = line.trim();
                if (trimmed.startsWith("[") && trimmed.endsWith("]")) {
                    section = trimmed.substring(1, trimmed.length() - 1).trim();
                    continue;
                }
                if (!section.equalsIgnoreCase(CONFIG_SECTION)) continue;
                int eq = trimmed.indexOf('=');
                if (eq <= 0) continue;
                String key = trimmed.substring(0, eq).trim();
                if (key.equalsIgnoreCase(CONFIG_KEY)) return trimmed.substring(eq + 1).trim();
            }
        } catch (IOException ignored) {
        }
        return "";
    }

    private void writeActiveMod(String value) throws IOException {
        File cfg = getConfigFile();
        List<String> lines = new ArrayList<>();
        if (cfg.isFile()) {
            try (BufferedReader in = new BufferedReader(new FileReader(cfg))) {
                String line;
                while ((line = in.readLine()) != null) lines.add(line);
            }
        }

        List<String> out = new ArrayList<>();
        boolean inMod = false;
        boolean foundSection = false;
        boolean wroteKey = false;

        for (String line : lines) {
            String trimmed = line.trim();
            boolean isSection = trimmed.startsWith("[") && trimmed.endsWith("]");
            if (isSection) {
                if (inMod && !wroteKey) {
                    out.add(CONFIG_KEY + "=" + value);
                    wroteKey = true;
                }
                String name = trimmed.substring(1, trimmed.length() - 1).trim();
                inMod = name.equalsIgnoreCase(CONFIG_SECTION);
                if (inMod) foundSection = true;
                out.add(line);
                continue;
            }

            if (inMod) {
                int eq = trimmed.indexOf('=');
                if (eq > 0 && trimmed.substring(0, eq).trim().equalsIgnoreCase(CONFIG_KEY)) {
                    out.add(CONFIG_KEY + "=" + value);
                    wroteKey = true;
                    continue;
                }
            }
            out.add(line);
        }

        if (!foundSection) {
            if (!out.isEmpty() && !out.get(out.size() - 1).isEmpty()) out.add("");
            out.add("[" + CONFIG_SECTION + "]");
            out.add(CONFIG_KEY + "=" + value);
        } else if (!wroteKey) {
            out.add(CONFIG_KEY + "=" + value);
        }

        File temp = new File(cfg.getParentFile(), CONFIG_FILE + ".modmanager.tmp");
        try (BufferedWriter writer = new BufferedWriter(new FileWriter(temp))) {
            for (String line : out) {
                writer.write(line);
                writer.newLine();
            }
        }
        if (cfg.exists() && !cfg.delete()) {
            temp.delete();
            throw new IOException("Could not replace " + CONFIG_FILE);
        }
        if (!temp.renameTo(cfg)) throw new IOException("Could not save " + CONFIG_FILE);
    }

    private File getConfigFile() {
        File dir = new File(getExternalFilesDir(null), "data");
        if (!dir.exists()) dir.mkdirs();
        return new File(dir, CONFIG_FILE);
    }

    /** SDL_GetPrefPath on Android resolves to the app's internal files directory. */
    private File getModsDir() {
        return new File(getFilesDir(), "mods");
    }

    private void ensureModsDir() {
        File dir = getModsDir();
        if (!dir.exists() && !dir.mkdirs()) {
            Toast.makeText(this, "Unable to create mod folder", Toast.LENGTH_LONG).show();
        }
    }

    private boolean isSupportedPackage(String name) {
        String lower = name.toLowerCase(Locale.ROOT);
        return lower.endsWith(".zip") || lower.endsWith(".7z") || lower.endsWith(".pk3")
                || lower.endsWith(".rar") || lower.endsWith(".xdelta")
                || lower.endsWith(".bps") || lower.endsWith(".ips");
    }

    private String stripSupportedExtension(String name) {
        String lower = name.toLowerCase(Locale.ROOT);
        String[] exts = {".xdelta", ".zip", ".7z", ".pk3", ".rar", ".bps", ".ips"};
        for (String ext : exts) {
            if (lower.endsWith(ext)) return name.substring(0, name.length() - ext.length());
        }
        return name;
    }

    private String sanitizeFilename(String name) {
        String cleaned = name.replace('\\', '_').replace('/', '_').replace(':', '_');
        cleaned = cleaned.replaceAll("[\\p{Cntrl}]", "_").trim();
        return cleaned.isEmpty() ? "mod-package" : cleaned;
    }

    @Nullable
    private String getDisplayName(Uri uri) {
        try (Cursor cursor = getContentResolver().query(uri,
                new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (index >= 0) return cursor.getString(index);
            }
        } catch (Exception ignored) {
        }
        return uri.getLastPathSegment();
    }

    private boolean deleteTree(File file) {
        boolean ok = true;
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children) ok &= deleteTree(child);
            }
        }
        return file.delete() && ok;
    }

    private String relativeModPath(File file) {
        try {
            String root = getModsDir().getCanonicalPath();
            String path = file.getCanonicalPath();
            if (path.startsWith(root)) return "mods" + path.substring(root.length());
        } catch (IOException ignored) {
        }
        return file.getName();
    }

    private String humanSize(long bytes) {
        if (bytes >= 1024L * 1024L) return String.format(Locale.US, "%.1f MiB", bytes / (1024.0 * 1024.0));
        if (bytes >= 1024L) return String.format(Locale.US, "%.1f KiB", bytes / 1024.0);
        return bytes + " B";
    }

    private LinearLayout makeCard() {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(12), dp(10), dp(12), dp(10));
        card.setBackgroundColor(0xff181818);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(7);
        card.setLayoutParams(lp);
        return card;
    }

    private TextView sectionTitle(String text) {
        TextView view = makeText(text, 20, Color.WHITE);
        view.setTypeface(view.getTypeface(), android.graphics.Typeface.BOLD);
        return view;
    }

    private void addDivider(LinearLayout root) {
        View divider = new View(this);
        divider.setBackgroundColor(0xff555555);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, dp(1));
        lp.topMargin = dp(22);
        lp.bottomMargin = dp(18);
        root.addView(divider, lp);
    }

    private TextView makeText(String text, int sp, int color) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(sp);
        view.setTextColor(color);
        return view;
    }

    private void addWithTop(LinearLayout parent, View child, int topDp) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(topDp);
        parent.addView(child, lp);
    }

    private LinearLayout.LayoutParams weightedButtonParams() {
        return new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private void showError(String title, Exception e) {
        new AlertDialog.Builder(this)
                .setTitle(title)
                .setMessage(e.getMessage() == null ? e.toString() : e.getMessage())
                .setPositiveButton("OK", null)
                .show();
    }

    private static class ModEntry {
        final File dir;
        final String name;
        final boolean restartRequired;

        ModEntry(File dir, String name, boolean restartRequired) {
            this.dir = dir;
            this.name = name;
            this.restartRequired = restartRequired;
        }
    }
}
