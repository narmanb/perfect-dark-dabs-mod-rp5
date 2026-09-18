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

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
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
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * Android front end for Dab's texture packs, model packs and user-supplied XBLA assets.
 *
 * The native port chooses writable graphics-pack directories beside the executable or
 * in the save directory. Android's executable directory is read-only, while MainActivity
 * passes getExternalFilesDir(null)/data as --savedir, so the matching writable locations
 * are data/texture-packs, data/model-packs and data/xbla.
 */
public class GraphicsManagerActivity extends AppCompatActivity {
    private static final String CONFIG_SECTION = "Mod";

    private static final int IMPORT_NONE = 0;
    private static final int IMPORT_TEXTURE = 1;
    private static final int IMPORT_MODEL = 2;
    private static final int IMPORT_XBLA = 3;

    private int pendingImport = IMPORT_NONE;

    private LinearLayout textureList;
    private LinearLayout modelList;
    private TextView textureStatus;
    private TextView modelStatus;
    private TextView xblaStatus;
    private Button modelPreferenceButton;
    private Button xblaModelsButton;
    private Button xblaStagesButton;
    private Button xblaTexturesButton;

    private final ActivityResultLauncher<String[]> assetPicker =
            registerForActivityResult(new ActivityResultContracts.OpenDocument(), this::onAssetPicked);

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(buildUi());
        ensureDirectories();
        refresh();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (textureList != null) refresh();
    }

    private View buildUi() {
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(Color.BLACK);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(22), dp(18), dp(22), dp(30));
        scroll.addView(root, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT, ScrollView.LayoutParams.WRAP_CONTENT));

        TextView title = makeText("GRAPHICS", 26, Color.WHITE);
        title.setTypeface(title.getTypeface(), android.graphics.Typeface.BOLD);
        root.addView(title);

        TextView intro = makeText(
                "Texture packs and model packs are independent of gameplay mods. "
                        + "Ultimate Plus HD and XBLA Plus HD are texture packs intended for XBLA models; "
                        + "PD Forever Plus HD is intended for the original N64 models.",
                15, 0xffcccccc);
        addWithTop(root, intro, 8);

        addDivider(root);
        root.addView(sectionTitle("HD TEXTURE PACKS"));

        TextView textureHelp = makeText(
                "Import a ZIP or 7Z texture pack. The native engine reads the archive directly and "
                        + "unpacks it on first use. Importing a pack selects it automatically.",
                14, 0xffaaaaaa);
        addWithTop(root, textureHelp, 4);

        LinearLayout textureActions = new LinearLayout(this);
        textureActions.setOrientation(LinearLayout.HORIZONTAL);
        addWithTop(root, textureActions, 10);

        Button importTexture = new Button(this);
        importTexture.setText("Import Texture Pack");
        importTexture.setOnClickListener(v -> openPicker(IMPORT_TEXTURE));
        textureActions.addView(importTexture, weightedButtonParams());

        Button disableTextures = new Button(this);
        disableTextures.setText("Disable Textures");
        disableTextures.setOnClickListener(v -> {
            try {
                writeModValues(mapOf("LoadTextures", "0"));
                Toast.makeText(this, "Texture packs disabled for next launch", Toast.LENGTH_SHORT).show();
                refresh();
            } catch (IOException e) {
                showError("Could not update texture-pack setting", e);
            }
        });
        LinearLayout.LayoutParams disableTextureLp = weightedButtonParams();
        disableTextureLp.setMarginStart(dp(8));
        textureActions.addView(disableTextures, disableTextureLp);

        textureStatus = makeText("", 14, Color.WHITE);
        addWithTop(root, textureStatus, 8);

        textureList = new LinearLayout(this);
        textureList.setOrientation(LinearLayout.VERTICAL);
        addWithTop(root, textureList, 6);

        addDivider(root);
        root.addView(sectionTitle("MODEL PACKS"));

        TextView modelHelp = makeText(
                "Import a ZIP containing an n64/ and/or xbla/ model-pack folder. "
                        + "The Android launcher extracts model packs because the native model-pack loader expects a directory.",
                14, 0xffaaaaaa);
        addWithTop(root, modelHelp, 4);

        LinearLayout modelActions = new LinearLayout(this);
        modelActions.setOrientation(LinearLayout.HORIZONTAL);
        addWithTop(root, modelActions, 10);

        Button importModel = new Button(this);
        importModel.setText("Import Model Pack ZIP");
        importModel.setOnClickListener(v -> openPicker(IMPORT_MODEL));
        modelActions.addView(importModel, weightedButtonParams());

        Button disableModels = new Button(this);
        disableModels.setText("Disable Model Pack");
        disableModels.setOnClickListener(v -> {
            try {
                writeModValues(mapOf("LoadModels", "0"));
                Toast.makeText(this, "Model pack disabled for next launch", Toast.LENGTH_SHORT).show();
                refresh();
            } catch (IOException e) {
                showError("Could not update model-pack setting", e);
            }
        });
        LinearLayout.LayoutParams disableModelLp = weightedButtonParams();
        disableModelLp.setMarginStart(dp(8));
        modelActions.addView(disableModels, disableModelLp);

        modelStatus = makeText("", 14, Color.WHITE);
        addWithTop(root, modelStatus, 8);

        modelPreferenceButton = new Button(this);
        modelPreferenceButton.setOnClickListener(v -> {
            int current = readInt("ModelPackPrefer", 0);
            try {
                writeModValues(mapOf("ModelPackPrefer", current == 0 ? "1" : "0"));
                refresh();
            } catch (IOException e) {
                showError("Could not update model preference", e);
            }
        });
        addWithTop(root, modelPreferenceButton, 6);

        modelList = new LinearLayout(this);
        modelList.setOrientation(LinearLayout.VERTICAL);
        addWithTop(root, modelList, 6);

        addDivider(root);
        root.addView(sectionTitle("XBLA GRAPHICS"));

        TextView xblaHelp = makeText(
                "Import your own Perfect Dark XBLA archive/package here. This is separate from the HD texture packs. "
                        + "Ultimate Plus HD is normally paired with XBLA Models ON; PD Forever Plus HD is normally used with XBLA Models OFF.",
                14, 0xffaaaaaa);
        addWithTop(root, xblaHelp, 4);

        Button importXbla = new Button(this);
        importXbla.setText("Import XBLA Archive / Package");
        importXbla.setOnClickListener(v -> openPicker(IMPORT_XBLA));
        addWithTop(root, importXbla, 10);

        xblaStatus = makeText("", 14, Color.WHITE);
        addWithTop(root, xblaStatus, 8);

        LinearLayout xblaToggles = new LinearLayout(this);
        xblaToggles.setOrientation(LinearLayout.HORIZONTAL);
        addWithTop(root, xblaToggles, 6);

        xblaModelsButton = new Button(this);
        xblaModelsButton.setOnClickListener(v -> toggleInt("XblaMeshes", 0));
        xblaToggles.addView(xblaModelsButton, weightedButtonParams());

        xblaStagesButton = new Button(this);
        xblaStagesButton.setOnClickListener(v -> toggleInt("XblaStages", 1));
        LinearLayout.LayoutParams stageLp = weightedButtonParams();
        stageLp.setMarginStart(dp(8));
        xblaToggles.addView(xblaStagesButton, stageLp);

        xblaTexturesButton = new Button(this);
        xblaTexturesButton.setOnClickListener(v -> toggleInt("XblaMeshTextures", 1));
        LinearLayout.LayoutParams texLp = weightedButtonParams();
        texLp.setMarginStart(dp(8));
        xblaToggles.addView(xblaTexturesButton, texLp);

        addDivider(root);
        TextView applyHelp = makeText(
                "Selections are written to pd.ini immediately. Launch the game to apply newly imported packs/assets.",
                14, 0xffaaaaaa);
        root.addView(applyHelp);

        Button launch = new Button(this);
        launch.setText("Launch Perfect Dark");
        launch.setOnClickListener(v -> {
            Intent intent = new Intent(this, MainActivity.class);
            intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
            finish();
        });
        addWithTop(root, launch, 10);

        return scroll;
    }

    private void openPicker(int type) {
        pendingImport = type;
        assetPicker.launch(new String[]{"*/*"});
    }

    private void onAssetPicked(@Nullable Uri uri) {
        if (uri == null) {
            pendingImport = IMPORT_NONE;
            return;
        }

        String displayName = sanitizeFilename(getDisplayName(uri));
        if (displayName.isEmpty()) {
            Toast.makeText(this, "Could not determine selected filename", Toast.LENGTH_LONG).show();
            pendingImport = IMPORT_NONE;
            return;
        }

        final int type = pendingImport;
        pendingImport = IMPORT_NONE;

        if (type == IMPORT_TEXTURE) {
            if (!hasExtension(displayName, ".zip") && !hasExtension(displayName, ".7z")) {
                showMessage("Unsupported texture pack",
                        "Choose the texture pack's .zip or .7z archive.");
                return;
            }
            importTexturePack(uri, displayName);
        } else if (type == IMPORT_MODEL) {
            if (!hasExtension(displayName, ".zip")) {
                showMessage("Unsupported model pack",
                        "Model-pack importing currently expects a .zip containing n64/ and/or xbla/.");
                return;
            }
            importModelPack(uri, displayName);
        } else if (type == IMPORT_XBLA) {
            importXbla(uri, displayName);
        }
    }

    private void importTexturePack(Uri uri, String name) {
        ensureDirectories();
        File target = new File(getTexturePacksDir(), name);
        Runnable action = () -> copyAssetAsync(uri, target, "texture pack", () -> {
            String packName = stripArchiveExtension(name);
            try {
                writeModValues(mapOf(
                        "TexturePack", packName,
                        "LoadTextures", "1"));
                Toast.makeText(this, packName + " imported and selected", Toast.LENGTH_LONG).show();
            } catch (IOException e) {
                showError("Texture pack imported, but selection could not be saved", e);
            }
            refresh();
        });

        confirmReplaceIfNeeded(target, "texture pack", action);
    }

    private void importModelPack(Uri uri, String name) {
        ensureDirectories();
        String packName = stripArchiveExtension(name);
        File target = new File(getModelPacksDir(), packName);

        Runnable action = () -> {
            Toast.makeText(this, "Importing model pack…", Toast.LENGTH_SHORT).show();
            new Thread(() -> {
                File temp = new File(getModelPacksDir(), ".import-" + packName);
                try {
                    deleteTree(temp);
                    if (!temp.mkdirs()) throw new IOException("Could not create temporary model-pack folder");
                    extractZip(uri, temp);

                    File packRoot = findModelPackRoot(temp, 0);
                    if (packRoot == null) {
                        throw new IOException("ZIP contains no n64/ or xbla/ model-pack folder");
                    }

                    if (target.exists() && !deleteTree(target)) {
                        throw new IOException("Could not replace existing model pack");
                    }

                    if (!packRoot.renameTo(target)) {
                        copyTree(packRoot, target);
                    }

                    deleteTree(temp);

                    runOnUiThread(() -> {
                        try {
                            writeModValues(mapOf(
                                    "ModelPack", packName,
                                    "LoadModels", "1"));
                            Toast.makeText(this, packName + " imported and selected", Toast.LENGTH_LONG).show();
                        } catch (IOException e) {
                            showError("Model pack imported, but selection could not be saved", e);
                        }
                        refresh();
                    });
                } catch (Exception e) {
                    deleteTree(temp);
                    runOnUiThread(() -> showError("Model-pack import failed", e));
                }
            }, "PD-model-pack-import").start();
        };

        confirmReplaceIfNeeded(target, "model pack", action);
    }

    private void importXbla(Uri uri, String name) {
        ensureDirectories();

        String lower = name.toLowerCase(Locale.ROOT);
        final String targetName;
        if (lower.endsWith(".7z")) {
            targetName = "Perfect Dark XBLA.7z";
        } else if (lower.endsWith(".zip")) {
            targetName = "Perfect Dark XBLA.zip";
        } else if (looksLikeStfsPackage(uri)) {
            targetName = "Perfect Dark XBLA";
        } else {
            showMessage("Unsupported XBLA file",
                    "Choose the Perfect Dark XBLA .7z/.zip archive or its LIVE/CON/PIRS package.");
            return;
        }

        File target = new File(getXblaDir(), targetName);
        Runnable action = () -> {
            // Keep a single explicit source so the native detector cannot pick an older archive first.
            deleteTree(new File(getXblaDir(), "Perfect Dark XBLA.7z"));
            deleteTree(new File(getXblaDir(), "Perfect Dark XBLA.zip"));
            deleteTree(new File(getXblaDir(), "Perfect Dark XBLA"));

            copyAssetAsync(uri, target, "XBLA package", () -> {
                try {
                    writeModValues(mapOf(
                            "XblaPackage", target.getAbsolutePath(),
                            "XblaMeshes", "1",
                            "XblaMeshTextures", "1",
                            "XblaStages", "1"));
                    Toast.makeText(this, "XBLA assets imported; XBLA graphics enabled", Toast.LENGTH_LONG).show();
                } catch (IOException e) {
                    showError("XBLA assets imported, but settings could not be saved", e);
                }
                refresh();
            });
        };

        confirmReplaceIfNeeded(target, "XBLA package", action);
    }

    private void copyAssetAsync(Uri uri, File target, String label, Runnable success) {
        Toast.makeText(this, "Importing " + label + "…", Toast.LENGTH_SHORT).show();
        new Thread(() -> {
            File temp = new File(target.getParentFile(), ".import-" + target.getName() + ".tmp");
            try {
                if (temp.exists() && !temp.delete()) {
                    throw new IOException("Could not clear previous temporary import");
                }
                long copied = copyUri(uri, temp);
                if (copied <= 0 || temp.length() != copied) {
                    throw new IOException("Imported file was empty or incomplete");
                }
                if (target.exists() && !deleteTree(target)) {
                    throw new IOException("Could not replace existing " + label);
                }
                if (!temp.renameTo(target)) {
                    throw new IOException("Could not move imported file into place");
                }
                runOnUiThread(success);
            } catch (Exception e) {
                temp.delete();
                runOnUiThread(() -> showError("Failed to import " + label, e));
            }
        }, "PD-graphics-import").start();
    }

    private long copyUri(Uri uri, File target) throws IOException {
        File parent = target.getParentFile();
        if (parent != null && !parent.exists() && !parent.mkdirs()) {
            throw new IOException("Could not create destination folder");
        }

        long copied = 0;
        try (InputStream raw = getContentResolver().openInputStream(uri);
             BufferedInputStream in = raw == null ? null : new BufferedInputStream(raw);
             FileOutputStream fos = new FileOutputStream(target);
             BufferedOutputStream out = new BufferedOutputStream(fos)) {
            if (in == null) throw new IOException("Unable to open selected file");
            byte[] buffer = new byte[64 * 1024];
            int n;
            while ((n = in.read(buffer)) != -1) {
                if (n == 0) continue;
                out.write(buffer, 0, n);
                copied += n;
            }
            out.flush();
            fos.getFD().sync();
        }
        return copied;
    }

    private void extractZip(Uri uri, File root) throws IOException {
        String rootPath = root.getCanonicalPath() + File.separator;
        try (InputStream raw = getContentResolver().openInputStream(uri);
             ZipInputStream zip = raw == null ? null : new ZipInputStream(new BufferedInputStream(raw))) {
            if (zip == null) throw new IOException("Unable to open selected ZIP");

            byte[] buffer = new byte[64 * 1024];
            ZipEntry entry;
            int files = 0;
            while ((entry = zip.getNextEntry()) != null) {
                String entryName = entry.getName().replace('\\', '/');
                if (entryName.isEmpty()) {
                    zip.closeEntry();
                    continue;
                }

                File outFile = new File(root, entryName);
                String outPath = outFile.getCanonicalPath();
                if (!outPath.equals(root.getCanonicalPath()) && !outPath.startsWith(rootPath)) {
                    throw new IOException("ZIP contains an unsafe path: " + entryName);
                }

                if (entry.isDirectory()) {
                    if (!outFile.exists() && !outFile.mkdirs()) {
                        throw new IOException("Could not create " + entryName);
                    }
                } else {
                    File parent = outFile.getParentFile();
                    if (parent != null && !parent.exists() && !parent.mkdirs()) {
                        throw new IOException("Could not create folder for " + entryName);
                    }
                    try (BufferedOutputStream out = new BufferedOutputStream(new FileOutputStream(outFile))) {
                        int n;
                        while ((n = zip.read(buffer)) != -1) {
                            if (n == 0) continue;
                            out.write(buffer, 0, n);
                        }
                    }
                    files++;
                }
                zip.closeEntry();
            }

            if (files == 0) throw new IOException("ZIP contained no files");
        }
    }

    private File findModelPackRoot(File dir, int depth) {
        if (dir == null || !dir.isDirectory() || depth > 4) return null;
        if (new File(dir, "n64").isDirectory() || new File(dir, "xbla").isDirectory()) {
            return dir;
        }
        File[] children = dir.listFiles();
        if (children == null) return null;
        for (File child : children) {
            if (!child.isDirectory() || child.getName().startsWith(".")) continue;
            File found = findModelPackRoot(child, depth + 1);
            if (found != null) return found;
        }
        return null;
    }

    private void copyTree(File src, File dst) throws IOException {
        if (src.isDirectory()) {
            if (!dst.exists() && !dst.mkdirs()) {
                throw new IOException("Could not create " + dst.getName());
            }
            File[] children = src.listFiles();
            if (children != null) {
                for (File child : children) copyTree(child, new File(dst, child.getName()));
            }
            return;
        }

        try (BufferedInputStream in = new BufferedInputStream(new java.io.FileInputStream(src));
             BufferedOutputStream out = new BufferedOutputStream(new FileOutputStream(dst))) {
            byte[] buffer = new byte[64 * 1024];
            int n;
            while ((n = in.read(buffer)) != -1) {
                if (n > 0) out.write(buffer, 0, n);
            }
        }
    }

    private void refresh() {
        ensureDirectories();

        String texturePack = readString("TexturePack", "");
        int loadTextures = readInt("LoadTextures", 1);
        textureStatus.setText(texturePack.isEmpty()
                ? "Selected texture pack: None"
                : "Selected texture pack: " + texturePack + (loadTextures != 0 ? " • ENABLED" : " • disabled"));

        textureList.removeAllViews();
        List<PackEntry> textures = listTexturePacks();
        if (textures.isEmpty()) {
            textureList.addView(makeText("No texture packs imported.", 14, 0xff888888));
        } else {
            for (PackEntry entry : textures) {
                textureList.addView(buildTextureRow(entry, texturePack, loadTextures != 0));
            }
        }

        String modelPack = readString("ModelPack", "");
        int loadModels = readInt("LoadModels", 0);
        modelStatus.setText(modelPack.isEmpty()
                ? "Selected model pack: None"
                : "Selected model pack: " + modelPack + (loadModels != 0 ? " • ENABLED" : " • disabled"));

        int prefer = readInt("ModelPackPrefer", 0);
        modelPreferenceButton.setText(prefer == 0
                ? "When both exist: Prefer Model Pack"
                : "When both exist: Prefer XBLA Mesh");

        modelList.removeAllViews();
        List<File> models = listModelPacks();
        if (models.isEmpty()) {
            modelList.addView(makeText("No model packs imported.", 14, 0xff888888));
        } else {
            for (File dir : models) {
                modelList.addView(buildModelRow(dir, modelPack, loadModels != 0));
            }
        }

        File configuredXbla = configuredXblaFile();
        String xblaText = configuredXbla != null && configuredXbla.isFile()
                ? "XBLA source: " + configuredXbla.getName() + " • " + humanSize(configuredXbla.length())
                : "XBLA source: not imported";
        xblaStatus.setText(xblaText);

        int xblaModels = readInt("XblaMeshes", 0);
        int xblaStages = readInt("XblaStages", 1);
        int xblaTextures = readInt("XblaMeshTextures", 1);
        xblaModelsButton.setText("Models: " + onOff(xblaModels));
        xblaStagesButton.setText("Levels: " + onOff(xblaStages));
        xblaTexturesButton.setText("Textures: " + onOff(xblaTextures));
    }

    private View buildTextureRow(PackEntry entry, String selected, boolean enabled) {
        LinearLayout card = makeCard();
        boolean active = enabled && entry.name.equalsIgnoreCase(selected);

        card.addView(makeText(entry.name, 16, Color.WHITE));
        addWithTop(card, makeText(
                (active ? "ACTIVE • " : "") + (entry.archive ? "Archive" : "Folder")
                        + " • " + humanSize(sizeOf(entry.file)),
                13, active ? 0xff88dd88 : 0xffaaaaaa), 2);

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        addWithTop(card, buttons, 6);

        Button use = new Button(this);
        use.setText(active ? "Disable" : "Use");
        use.setOnClickListener(v -> {
            try {
                if (active) {
                    writeModValues(mapOf("LoadTextures", "0"));
                } else {
                    writeModValues(mapOf("TexturePack", entry.name, "LoadTextures", "1"));
                }
                refresh();
            } catch (IOException e) {
                showError("Could not update texture pack", e);
            }
        });
        buttons.addView(use, weightedButtonParams());

        Button remove = new Button(this);
        remove.setText("Remove");
        remove.setOnClickListener(v -> new AlertDialog.Builder(this)
                .setTitle("Remove " + entry.name + "?")
                .setMessage("This deletes the imported texture pack from app storage.")
                .setPositiveButton("Remove", (d, w) -> {
                    try {
                        if (entry.name.equalsIgnoreCase(selected)) {
                            writeModValues(mapOf("LoadTextures", "0", "TexturePack", ""));
                        }
                    } catch (IOException e) {
                        showError("Could not update texture selection", e);
                    }
                    deleteTree(entry.file);
                    deleteTree(new File(getTexturePacksDir(), ".cache/" + entry.name));
                    refresh();
                })
                .setNegativeButton("Cancel", null)
                .show());
        LinearLayout.LayoutParams removeLp = weightedButtonParams();
        removeLp.setMarginStart(dp(8));
        buttons.addView(remove, removeLp);

        return card;
    }

    private View buildModelRow(File dir, String selected, boolean enabled) {
        LinearLayout card = makeCard();
        boolean active = enabled && dir.getName().equalsIgnoreCase(selected);
        boolean hasN64 = new File(dir, "n64").isDirectory();
        boolean hasXbla = new File(dir, "xbla").isDirectory();

        card.addView(makeText(dir.getName(), 16, Color.WHITE));
        String kinds = hasN64 && hasXbla ? "N64 + XBLA models" : (hasXbla ? "XBLA models" : "N64 models");
        addWithTop(card, makeText((active ? "ACTIVE • " : "") + kinds,
                13, active ? 0xff88dd88 : 0xffaaaaaa), 2);

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        addWithTop(card, buttons, 6);

        Button use = new Button(this);
        use.setText(active ? "Disable" : "Use");
        use.setOnClickListener(v -> {
            try {
                if (active) {
                    writeModValues(mapOf("LoadModels", "0"));
                } else {
                    writeModValues(mapOf("ModelPack", dir.getName(), "LoadModels", "1"));
                }
                refresh();
            } catch (IOException e) {
                showError("Could not update model pack", e);
            }
        });
        buttons.addView(use, weightedButtonParams());

        Button remove = new Button(this);
        remove.setText("Remove");
        remove.setOnClickListener(v -> new AlertDialog.Builder(this)
                .setTitle("Remove " + dir.getName() + "?")
                .setMessage("This deletes the extracted model pack from app storage.")
                .setPositiveButton("Remove", (d, w) -> {
                    try {
                        if (dir.getName().equalsIgnoreCase(selected)) {
                            writeModValues(mapOf("LoadModels", "0", "ModelPack", ""));
                        }
                    } catch (IOException e) {
                        showError("Could not update model selection", e);
                    }
                    deleteTree(dir);
                    refresh();
                })
                .setNegativeButton("Cancel", null)
                .show());
        LinearLayout.LayoutParams removeLp = weightedButtonParams();
        removeLp.setMarginStart(dp(8));
        buttons.addView(remove, removeLp);

        return card;
    }

    private List<PackEntry> listTexturePacks() {
        List<PackEntry> result = new ArrayList<>();
        Set<String> names = new LinkedHashSet<>();
        File[] files = getTexturePacksDir().listFiles();
        if (files != null) {
            // Folders outrank archives in the native loader, so list them first.
            List<File> ordered = new ArrayList<>();
            Collections.addAll(ordered, files);
            Collections.sort(ordered, (a, b) -> {
                if (a.isDirectory() != b.isDirectory()) return a.isDirectory() ? -1 : 1;
                return a.getName().compareToIgnoreCase(b.getName());
            });
            for (File file : ordered) {
                if (file.getName().startsWith(".")) continue;
                boolean archive = file.isFile()
                        && (hasExtension(file.getName(), ".zip") || hasExtension(file.getName(), ".7z"));
                if (!file.isDirectory() && !archive) continue;
                String name = archive ? stripArchiveExtension(file.getName()) : file.getName();
                String key = name.toLowerCase(Locale.ROOT);
                if (names.add(key)) result.add(new PackEntry(name, file, archive));
            }
        }
        Collections.sort(result, Comparator.comparing(a -> a.name.toLowerCase(Locale.ROOT)));
        return result;
    }

    private List<File> listModelPacks() {
        List<File> result = new ArrayList<>();
        File[] files = getModelPacksDir().listFiles();
        if (files != null) {
            for (File file : files) {
                if (!file.isDirectory() || file.getName().startsWith(".")) continue;
                if (new File(file, "n64").isDirectory() || new File(file, "xbla").isDirectory()) {
                    result.add(file);
                }
            }
        }
        Collections.sort(result, Comparator.comparing(a -> a.getName().toLowerCase(Locale.ROOT)));
        return result;
    }

    private void toggleInt(String key, int defaultValue) {
        int current = readInt(key, defaultValue);
        try {
            writeModValues(mapOf(key, current == 0 ? "1" : "0"));
            refresh();
        } catch (IOException e) {
            showError("Could not update " + key, e);
        }
    }

    private String onOff(int value) {
        return value != 0 ? "ON" : "OFF";
    }

    private void confirmReplaceIfNeeded(File target, String label, Runnable action) {
        if (!target.exists()) {
            action.run();
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("Replace " + label + "?")
                .setMessage(target.getName() + " already exists.")
                .setPositiveButton("Replace", (d, w) -> action.run())
                .setNegativeButton("Cancel", null)
                .show();
    }

    private boolean looksLikeStfsPackage(Uri uri) {
        try (InputStream in = getContentResolver().openInputStream(uri)) {
            if (in == null) return false;
            byte[] magic = new byte[4];
            int n = in.read(magic);
            if (n != 4) return false;
            String s = new String(magic, java.nio.charset.StandardCharsets.US_ASCII);
            return "LIVE".equals(s) || "CON ".equals(s) || "PIRS".equals(s);
        } catch (IOException e) {
            return false;
        }
    }

    private File configuredXblaFile() {
        String configured = readString("XblaPackage", "");
        if (!configured.isEmpty()) {
            File f = new File(configured);
            if (f.isFile()) return f;
        }

        File[] known = {
                new File(getXblaDir(), "Perfect Dark XBLA.7z"),
                new File(getXblaDir(), "Perfect Dark XBLA.zip"),
                new File(getXblaDir(), "Perfect Dark XBLA")
        };
        for (File f : known) if (f.isFile()) return f;
        return null;
    }

    private File getGameDataDir() {
        File external = getExternalFilesDir(null);
        return new File(external, "data");
    }

    private File getTexturePacksDir() {
        return new File(getGameDataDir(), "texture-packs");
    }

    private File getModelPacksDir() {
        return new File(getGameDataDir(), "model-packs");
    }

    private File getXblaDir() {
        return new File(getGameDataDir(), "xbla");
    }

    private File getConfigFile() {
        return new File(getGameDataDir(), "pd.ini");
    }

    private void ensureDirectories() {
        mkdirs(getGameDataDir());
        mkdirs(getTexturePacksDir());
        mkdirs(getModelPacksDir());
        mkdirs(getXblaDir());
    }

    private void mkdirs(File dir) {
        if (!dir.exists() && !dir.mkdirs()) {
            Toast.makeText(this, "Unable to create " + dir.getName() + " folder", Toast.LENGTH_LONG).show();
        }
    }

    private String readString(String key, String defaultValue) {
        File cfg = getConfigFile();
        if (!cfg.isFile()) return defaultValue;

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
                String found = trimmed.substring(0, eq).trim();
                if (found.equalsIgnoreCase(key)) {
                    return trimmed.substring(eq + 1).trim();
                }
            }
        } catch (IOException ignored) {
        }
        return defaultValue;
    }

    private int readInt(String key, int defaultValue) {
        try {
            return Integer.parseInt(readString(key, Integer.toString(defaultValue)));
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    private void writeModValues(Map<String, String> values) throws IOException {
        ensureDirectories();
        File cfg = getConfigFile();
        List<String> lines = new ArrayList<>();

        if (cfg.isFile()) {
            try (BufferedReader in = new BufferedReader(new FileReader(cfg))) {
                String line;
                while ((line = in.readLine()) != null) lines.add(line);
            }
        }

        int sectionStart = -1;
        int sectionEnd = lines.size();
        for (int i = 0; i < lines.size(); i++) {
            String t = lines.get(i).trim();
            if (t.startsWith("[") && t.endsWith("]")) {
                String name = t.substring(1, t.length() - 1).trim();
                if (sectionStart >= 0) {
                    sectionEnd = i;
                    break;
                }
                if (name.equalsIgnoreCase(CONFIG_SECTION)) {
                    sectionStart = i;
                }
            }
        }

        if (sectionStart < 0) {
            if (!lines.isEmpty() && !lines.get(lines.size() - 1).isEmpty()) lines.add("");
            sectionStart = lines.size();
            lines.add("[" + CONFIG_SECTION + "]");
            sectionEnd = lines.size();
        }

        Map<String, String> remaining = new LinkedHashMap<>(values);
        for (int i = sectionStart + 1; i < sectionEnd; i++) {
            String trimmed = lines.get(i).trim();
            int eq = trimmed.indexOf('=');
            if (eq <= 0) continue;
            String found = trimmed.substring(0, eq).trim();

            String matching = null;
            for (String key : remaining.keySet()) {
                if (key.equalsIgnoreCase(found)) {
                    matching = key;
                    break;
                }
            }
            if (matching != null) {
                lines.set(i, matching + "=" + remaining.remove(matching));
            }
        }

        int insert = sectionEnd;
        for (Map.Entry<String, String> entry : remaining.entrySet()) {
            lines.add(insert++, entry.getKey() + "=" + entry.getValue());
        }

        File temp = new File(cfg.getParentFile(), "pd.ini.graphics.tmp");
        try (BufferedWriter out = new BufferedWriter(new FileWriter(temp))) {
            for (String line : lines) {
                out.write(line);
                out.newLine();
            }
        }

        if (cfg.exists() && !cfg.delete()) {
            temp.delete();
            throw new IOException("Could not replace pd.ini");
        }
        if (!temp.renameTo(cfg)) {
            throw new IOException("Could not save pd.ini");
        }
    }

    private Map<String, String> mapOf(String... pairs) {
        LinkedHashMap<String, String> map = new LinkedHashMap<>();
        for (int i = 0; i + 1 < pairs.length; i += 2) {
            map.put(pairs[i], pairs[i + 1]);
        }
        return map;
    }

    private String getDisplayName(Uri uri) {
        if (uri == null) return "";
        try (Cursor cursor = getContentResolver().query(uri,
                new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (cursor != null && cursor.moveToFirst()) {
                int index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);
                if (index >= 0) {
                    String name = cursor.getString(index);
                    if (name != null) return name;
                }
            }
        } catch (Exception ignored) {
        }
        String last = uri.getLastPathSegment();
        return last == null ? "" : last;
    }

    private String sanitizeFilename(String name) {
        if (name == null) return "";
        return name.replace('/', '_').replace('\\', '_').replace('\0', '_').trim();
    }

    private boolean hasExtension(String name, String ext) {
        return name.toLowerCase(Locale.ROOT).endsWith(ext);
    }

    private String stripArchiveExtension(String name) {
        String lower = name.toLowerCase(Locale.ROOT);
        if (lower.endsWith(".zip") || lower.endsWith(".7z")) {
            return name.substring(0, name.lastIndexOf('.'));
        }
        return name;
    }

    private boolean deleteTree(File file) {
        if (file == null || !file.exists()) return true;
        boolean ok = true;
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children) ok &= deleteTree(child);
            }
        }
        return file.delete() && ok;
    }

    private long sizeOf(File file) {
        if (file == null || !file.exists()) return 0;
        if (file.isFile()) return file.length();
        long total = 0;
        File[] children = file.listFiles();
        if (children != null) for (File child : children) total += sizeOf(child);
        return total;
    }

    private String humanSize(long bytes) {
        if (bytes < 1024) return bytes + " B";
        double value = bytes / 1024.0;
        if (value < 1024) return String.format(Locale.US, "%.1f KiB", value);
        value /= 1024.0;
        if (value < 1024) return String.format(Locale.US, "%.1f MiB", value);
        value /= 1024.0;
        return String.format(Locale.US, "%.2f GiB", value);
    }

    private void showMessage(String title, String message) {
        new AlertDialog.Builder(this)
                .setTitle(title)
                .setMessage(message)
                .setPositiveButton("OK", null)
                .show();
    }

    private void showError(String title, Exception e) {
        showMessage(title, e.getMessage() == null ? e.toString() : e.getMessage());
    }

    private TextView makeText(String text, int sp, int color) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(sp);
        view.setTextColor(color);
        return view;
    }

    private TextView sectionTitle(String text) {
        TextView title = makeText(text, 20, Color.WHITE);
        title.setTypeface(title.getTypeface(), android.graphics.Typeface.BOLD);
        return title;
    }

    private LinearLayout makeCard() {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(12), dp(10), dp(12), dp(10));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(6);
        card.setLayoutParams(lp);
        card.setBackgroundColor(0xff181818);
        return card;
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

    private void addWithTop(LinearLayout parent, View child, int topDp) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = dp(topDp);
        parent.addView(child, lp);
    }

    private LinearLayout.LayoutParams weightedButtonParams() {
        return new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
    }

    private int dp(int dp) {
        return Math.round(dp * getResources().getDisplayMetrics().density);
    }

    private static class PackEntry {
        final String name;
        final File file;
        final boolean archive;

        PackEntry(String name, File file, boolean archive) {
            this.name = name;
            this.file = file;
            this.archive = archive;
        }
    }
}
