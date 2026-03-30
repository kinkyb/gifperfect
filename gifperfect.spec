import sys, os, shutil

# Download static ffmpeg and add to PATH, then locate via which
import static_ffmpeg
static_ffmpeg.add_paths()

ff      = shutil.which('ffmpeg')
ffprobe = shutil.which('ffprobe')
if not ff:
    raise RuntimeError("ffmpeg not found after static_ffmpeg.add_paths()")
if not ffprobe:
    raise RuntimeError("ffprobe not found after static_ffmpeg.add_paths()")

ff_bins = [(ff, '.'), (ffprobe, '.')]

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[os.path.dirname(os.path.abspath('app.py'))],
    binaries=ff_bins,
    datas=[],
    hiddenimports=[
        'customtkinter',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'darkdetect',
        'packaging',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GifPerfect',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.icns' if sys.platform == 'darwin' else 'icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GifPerfect',
)

# macOS .app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='GifPerfect.app',
        icon='icon.icns',
        bundle_identifier='com.gifperfect.app',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': True,
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleName': 'GIF Perfect',
            'CFBundleDisplayName': 'GIF Perfect',
            'NSHumanReadableCopyright': '© 2026 GIF Perfect',
        },
    )
