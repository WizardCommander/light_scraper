# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

# Build datas list - only include .env if it exists
datas_list = [('src', 'src')]
if os.path.exists('.env'):
    datas_list.append(('.env', '.'))

a = Analysis(
    ['src/cli.py'],
    pathex=[],
    binaries=[],
    datas=datas_list,
    hiddenimports=[
        'anthropic',
        'playwright',
        'playwright.sync_api',
        'playwright._impl._api_structures',
        'playwright._impl._api_types',
        'playwright._impl._browser',
        'playwright._impl._browser_context',
        'playwright._impl._browser_type',
        'playwright._impl._connection',
        'playwright._impl._download',
        'playwright._impl._element_handle',
        'playwright._impl._file_chooser',
        'playwright._impl._frame',
        'playwright._impl._js_handle',
        'playwright._impl._network',
        'playwright._impl._page',
        'playwright._impl._playwright',
        'playwright._impl._selectors',
        'playwright._impl._transport',
        'playwright._impl._web_socket',
        'bs4',
        'lxml',
        'pandas',
        'openpyxl',
        'aiohttp',
        'httpx',
        'httpx._transports',
        'httpx._transports.default',
        'h2',
        'h2.connection',
        'h2.config',
        'requests',
        'loguru',
        'langdetect',
        'dotenv',
        'openai',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='scraper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disable UPX - can cause issues
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
