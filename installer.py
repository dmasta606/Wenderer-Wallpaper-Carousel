#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import hashlib
import os
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

APP_NAME = "Wenderer Wallpaper Carousel"
MARK = "WENDERER_WALLPAPER_CAROUSEL"
BROWSER_MARK = "WENDERER_WALLPAPER_CAROUSEL_BROWSER"

# Hidden test override is harmless in normal use and lets the installer be tested safely.
HOME = Path(os.environ.get("WENDERER_CAROUSEL_TEST_HOME", str(Path.home()))).expanduser()
CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", str(HOME / ".config"))).expanduser()
STATE_HOME = Path(os.environ.get("XDG_STATE_HOME", str(HOME / ".local/state"))).expanduser()
CACHE_HOME = Path(os.environ.get("XDG_CACHE_HOME", str(HOME / ".cache"))).expanduser()

HYPR_ROOT = CONFIG_HOME / "hypr"
VARIABLES = HYPR_ROOT / "variables.lua"
KEYBINDS = HYPR_ROOT / "hyprland" / "keybinds.lua"
EXECS = HYPR_ROOT / "hyprland" / "execs.lua"
DEST = CONFIG_HOME / "quickshell" / "wallpaper-carousel"
INSTALLER_STATE = STATE_HOME / "wenderer-wallpaper-carousel-installer"
LOG = CACHE_HOME / "wenderer-wallpaper-carousel-installer.log"

SCRIPT_DIR = Path(__file__).resolve().parent
PAYLOAD = SCRIPT_DIR / "payload"
WALLPAPER_PAYLOAD = PAYLOAD / "wallpapers"
WALLPAPER_MANIFEST = INSTALLER_STATE / "wallpapers-installed.json"


def resolve_pictures_dir() -> Path:
    # During isolated tests never consult the real user's xdg-user-dir.
    if os.environ.get("WENDERER_CAROUSEL_TEST_HOME"):
        return HOME / "Pictures"

    if shutil.which("xdg-user-dir"):
        try:
            out = subprocess.check_output(
                ["xdg-user-dir", "PICTURES"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=3,
            ).strip()
            if out:
                return Path(out).expanduser()
        except Exception:
            pass

    return HOME / "Pictures"


WALLPAPER_DEST = resolve_pictures_dir() / "Wallpapers"


def log(msg: str = "") -> None:
    print(msg, flush=True)


def notify(title: str, body: str, urgency: str = "normal") -> None:
    # Prefer normal desktop notification. This keeps the installer independent
    # of any particular terminal emulator.
    if shutil.which("notify-send"):
        try:
            subprocess.run(
                ["notify-send", "-u", urgency, title, body],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
                check=False,
            )
            return
        except Exception:
            pass


def require_layout() -> None:
    missing = [str(p) for p in (VARIABLES, KEYBINDS, EXECS) if not p.is_file()]
    if missing:
        raise RuntimeError(
            "Не найдена ожидаемая структура Caelestia/Hyprland:\n" + "\n".join(missing)
        )

    # Validate the anchors BEFORE writing anything. If Caelestia changes its
    # generated config layout later, we abort safely instead of guessing.
    variables = VARIABLES.read_text(encoding="utf-8")
    keybinds = KEYBINDS.read_text(encoding="utf-8")
    execs = EXECS.read_text(encoding="utf-8")

    if "kbBrowser" not in variables:
        raise RuntimeError("В variables.lua не найден kbBrowser — конфиг имеет неизвестную структуру.")

    if "vars.kbBrowser" not in keybinds or "hl.dsp.exec_cmd(vars.browser)" not in keybinds:
        raise RuntimeError("В keybinds.lua не найден стандартный bind браузера Caelestia.")

    if 'hl.exec_cmd("caelestia shell -d")' not in execs:
        raise RuntimeError("В execs.lua не найден запуск 'caelestia shell -d'.")


def backup_configs() -> Path:
    INSTALLER_STATE.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = INSTALLER_STATE / "backups" / stamp
    backup.mkdir(parents=True, exist_ok=True)

    for src in (VARIABLES, KEYBINDS, EXECS):
        shutil.copy2(src, backup / src.name)

    (INSTALLER_STATE / "last-backup.txt").write_text(str(backup) + "\n", encoding="utf-8")
    return backup


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".wenderer-tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def check_runtime_bind_conflicts() -> None:
    """Best-effort conflict check when Hyprland is currently running."""
    if not shutil.which("hyprctl") or not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return

    try:
        raw = subprocess.check_output(
            ["hyprctl", "binds", "-j"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        binds = json.loads(raw)
    except Exception:
        return

    # modmask 64 == SUPER in the current Hyprland output used by this setup.
    b_binds = [b for b in binds if b.get("modmask") == 64 and str(b.get("key", "")).upper() == "B"]
    w_binds = [b for b in binds if b.get("modmask") == 64 and str(b.get("key", "")).upper() == "W"]

    # On the expected stock setup W is the browser and B is free.
    # If B is already occupied, do not steal it silently.
    if b_binds:
        raise RuntimeError("SUPER+B уже занят в текущем Hyprland. Установщик не будет перезаписывать этот bind.")

    # More than one W bind is suspicious; one is the expected current browser bind.
    if len(w_binds) > 1:
        raise RuntimeError("SUPER+W уже имеет несколько bind'ов. Нужна ручная проверка перед установкой.")


def patch_variables(text: str) -> str:
    # Already installed: normalize carousel shortcut and leave the marked browser change intact.
    carousel_re = re.compile(r'(?m)^(\s*kbWallpaperCarousel\s*=\s*)"[^"]+"(,?.*)$')
    if carousel_re.search(text):
        text = carousel_re.sub(r'\1"SUPER + W"\2', text, count=1)
    else:
        browser_line = re.search(r'(?m)^(?P<indent>\s*)kbBrowser\s*=.*$', text)
        if not browser_line:
            raise RuntimeError("Не удалось определить место kbBrowser в variables.lua.")
        indent = browser_line.group('indent')
        insertion = f'{indent}kbWallpaperCarousel        = "SUPER + W", -- {MARK}\n'
        pos = browser_line.end()
        text = text[:pos] + "\n" + insertion.rstrip("\n") + text[pos:]

    # Browser W -> B only when it is still the expected default.
    browser_w = re.compile(r'(?m)^(?P<indent>\s*)kbBrowser(?P<space>\s*=\s*)"SUPER \+ W"(?P<tail>\s*,?)(?:\s*--.*)?$')
    m = browser_w.search(text)
    if m:
        repl = f'{m.group("indent")}kbBrowser{m.group("space")}"SUPER + B"{m.group("tail")} -- {BROWSER_MARK}'
        text = text[:m.start()] + repl + text[m.end():]
    else:
        # B is also acceptable (e.g. reinstall). Any other value is left alone;
        # that means the user's browser was customized and should not be overridden.
        browser_any = re.search(r'(?m)^\s*kbBrowser\s*=\s*"([^"]+)"', text)
        if browser_any and browser_any.group(1) not in ("SUPER + B", "SUPER + W"):
            log(f"Browser bind уже пользовательский ({browser_any.group(1)}); не меняю его.")

    return text


def patch_keybinds(text: str) -> str:
    if "vars.kbWallpaperCarousel" in text:
        return text

    anchor_re = re.compile(
        r'(?m)^(?P<indent>\s*)create_bind\(vars\.kbBrowser,\s*hl\.dsp\.exec_cmd\(vars\.browser\)\)\s*$'
    )
    m = anchor_re.search(text)
    if not m:
        raise RuntimeError("Не удалось найти строку create_bind для kbBrowser в keybinds.lua.")

    indent = m.group('indent')
    block = (
        f"\n{indent}-- {MARK} BEGIN\n"
        f"{indent}create_bind(\n"
        f"{indent}    vars.kbWallpaperCarousel,\n"
        f"{indent}    hl.dsp.exec_cmd(\"qs -c wallpaper-carousel ipc call carousel toggle\")\n"
        f"{indent})\n"
        f"{indent}-- {MARK} END"
    )
    return text[:m.end()] + block + text[m.end():]


def patch_execs(text: str) -> str:
    if "qs -c wallpaper-carousel -n -d" in text:
        return text

    anchor_re = re.compile(r'(?m)^(?P<indent>\s*)hl\.exec_cmd\("caelestia shell -d"\)\s*$')
    m = anchor_re.search(text)
    if not m:
        raise RuntimeError("Не удалось найти запуск Caelestia в execs.lua.")

    indent = m.group('indent')
    line = f'\n{indent}hl.exec_cmd("qs -c wallpaper-carousel -n -d") -- {MARK}'
    return text[:m.end()] + line + text[m.end():]


def install_payload() -> None:
    for name in ("shell.qml", "colour_indexer.py"):
        if not (PAYLOAD / name).is_file():
            raise RuntimeError(f"В установщике отсутствует payload/{name}")

    DEST.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PAYLOAD / "shell.qml", DEST / "shell.qml")
    shutil.copy2(PAYLOAD / "colour_indexer.py", DEST / "colour_indexer.py")
    os.chmod(DEST / "colour_indexer.py", 0o755)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_wallpaper_manifest() -> dict:
    if not WALLPAPER_MANIFEST.is_file():
        return {"version": 1, "root": str(WALLPAPER_DEST), "files": {}}
    try:
        data = json.loads(WALLPAPER_MANIFEST.read_text(encoding="utf-8"))
        if not isinstance(data.get("files"), dict):
            raise ValueError("bad files field")
        return data
    except Exception as exc:
        raise RuntimeError(f"Не удалось прочитать manifest обоев: {exc}")


def save_wallpaper_manifest(root: Path, files: dict[str, str]) -> None:
    INSTALLER_STATE.mkdir(parents=True, exist_ok=True)
    data = {
        "version": 1,
        "root": str(root),
        "files": dict(sorted(files.items())),
    }
    tmp = WALLPAPER_MANIFEST.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, WALLPAPER_MANIFEST)


def install_wallpapers() -> tuple[int, int, int]:
    """Install bundled wallpapers without clobbering personal files.

    Returns (copied, updated, skipped). Files previously installed by this
    installer may be updated only while the on-disk file still matches the
    hash recorded by the previous manifest. Any user-modified or pre-existing
    file is left untouched.
    """
    if not WALLPAPER_PAYLOAD.is_dir():
        raise RuntimeError("В установщике отсутствует payload/wallpapers")

    old_manifest = load_wallpaper_manifest()
    old_root = Path(old_manifest.get("root", str(WALLPAPER_DEST))).expanduser()
    old_files = old_manifest.get("files", {})

    # If XDG Pictures moved since a previous install, don't treat files in the
    # new location as ours merely because their relative names match.
    if old_root != WALLPAPER_DEST:
        old_files = {}

    WALLPAPER_DEST.mkdir(parents=True, exist_ok=True)
    tracked: dict[str, str] = {}
    copied = updated = skipped = 0

    for src in sorted(WALLPAPER_PAYLOAD.rglob("*")):
        if not src.is_file():
            continue

        rel = src.relative_to(WALLPAPER_PAYLOAD)
        rel_key = rel.as_posix()
        dst = WALLPAPER_DEST / rel
        dst.parent.mkdir(parents=True, exist_ok=True)

        src_hash = sha256_file(src)
        old_hash = old_files.get(rel_key)

        if dst.exists():
            if not dst.is_file():
                skipped += 1
                continue

            # Only overwrite a file we previously installed and that the user
            # has not modified since then.
            if old_hash and sha256_file(dst) == old_hash:
                if old_hash != src_hash:
                    shutil.copy2(src, dst)
                    updated += 1
                tracked[rel_key] = src_hash
            else:
                skipped += 1
            continue

        shutil.copy2(src, dst)
        tracked[rel_key] = src_hash
        copied += 1

    # Preserve tracking for older bundled files that are no longer in this
    # installer version, but only while they remain unchanged. This lets a
    # future uninstall clean them safely without touching edited files.
    for rel_key, old_hash in old_files.items():
        if rel_key in tracked:
            continue
        dst = WALLPAPER_DEST / Path(rel_key)
        try:
            if dst.is_file() and sha256_file(dst) == old_hash:
                tracked[rel_key] = old_hash
        except OSError:
            pass

    save_wallpaper_manifest(WALLPAPER_DEST, tracked)
    return copied, updated, skipped


def uninstall_wallpapers() -> tuple[int, int]:
    """Remove only unchanged files that this installer actually added."""
    if not WALLPAPER_MANIFEST.is_file():
        return 0, 0

    manifest = load_wallpaper_manifest()
    root = Path(manifest.get("root", str(WALLPAPER_DEST))).expanduser()
    files = manifest.get("files", {})
    removed = kept = 0

    for rel_key, expected_hash in files.items():
        rel = Path(rel_key)
        if rel.is_absolute() or ".." in rel.parts:
            kept += 1
            continue
        dst = root / rel
        try:
            if dst.is_file() and sha256_file(dst) == expected_hash:
                dst.unlink()
                removed += 1
            elif dst.exists():
                kept += 1
        except OSError:
            kept += 1

    # Remove only empty category directories, then the Wallpapers directory if
    # it became completely empty. Personal files keep their directories alive.
    if root.is_dir():
        dirs = sorted((d for d in root.rglob("*") if d.is_dir()), key=lambda x: len(x.parts), reverse=True)
        for d in dirs:
            try:
                d.rmdir()
            except OSError:
                pass
        try:
            root.rmdir()
        except OSError:
            pass

    WALLPAPER_MANIFEST.unlink(missing_ok=True)
    return removed, kept


def reload_and_start() -> None:
    # Kill an old copy first so an update always restarts with the bundled files.
    if shutil.which("qs"):
        subprocess.run(
            ["qs", "-c", "wallpaper-carousel", "kill"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )

    if shutil.which("hyprctl") and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        subprocess.run(
            ["hyprctl", "reload"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )

    # If this is run outside a live Hyprland session, autostart will handle the
    # carousel on the next login. In a live session start it immediately too.
    if shutil.which("qs") and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        subprocess.run(
            ["qs", "-c", "wallpaper-carousel", "-n", "-d"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
            check=False,
        )


def install() -> None:
    log(f"{APP_NAME}: установка")
    require_layout()

    already = DEST.is_dir() and "vars.kbWallpaperCarousel" in KEYBINDS.read_text(encoding="utf-8")
    if not already:
        check_runtime_bind_conflicts()

    backup = backup_configs()
    log(f"Бэкап: {backup}")

    variables = patch_variables(VARIABLES.read_text(encoding="utf-8"))
    keybinds = patch_keybinds(KEYBINDS.read_text(encoding="utf-8"))
    execs = patch_execs(EXECS.read_text(encoding="utf-8"))

    atomic_write(VARIABLES, variables)
    atomic_write(KEYBINDS, keybinds)
    atomic_write(EXECS, execs)
    install_payload()
    copied, updated, skipped = install_wallpapers()
    log(f"Обои: добавлено {copied}, обновлено {updated}, пропущено существующих {skipped}")
    log(f"Папка обоев: {WALLPAPER_DEST}")
    reload_and_start()

    log("Готово.")
    log("SUPER+B -> браузер")
    log("SUPER+W -> Wallpaper Carousel")
    notify(APP_NAME, "Установлено. SUPER+B — браузер, SUPER+W — обои.")


def unpatch_variables(text: str, restore_legacy_browser: bool = False) -> str:
    # Remove our carousel variable. The fallback without marker supports the
    # original manual setup that existed before this installer was created.
    text = re.sub(
        rf'(?m)^[ \t]*kbWallpaperCarousel[ \t]*=[ \t]*"SUPER \+ W"[ \t]*,?[ \t]*(?:--[ \t]*{MARK})?[ \t]*\n?',
        '',
        text,
        count=1,
    )

    # Normal installer-managed case: restore browser only when WE marked it.
    marked_re = re.compile(
        rf'(?m)^(?P<prefix>\s*kbBrowser\s*=\s*)"SUPER \+ B"(?P<tail>\s*,?)\s*--\s*{BROWSER_MARK}\s*$'
    )
    if marked_re.search(text):
        return marked_re.sub(r'\g<prefix>"SUPER + W"\g<tail>', text, count=1)

    # Legacy/manual migration:
    # Before this installer existed, this specific setup was configured by hand:
    # browser W -> B, kbWallpaperCarousel -> W, exact carousel bind and autostart.
    # When the caller has verified that complete legacy pattern, restore B -> W
    # so Uninstall -> Install is a clean round trip.
    if restore_legacy_browser:
        text = re.sub(
            r'(?m)^(?P<prefix>\s*kbBrowser\s*=\s*)"SUPER \+ B"(?P<tail>\s*,?)\s*$',
            r'\g<prefix>"SUPER + W"\g<tail>',
            text,
            count=1,
        )

    return text


def unpatch_keybinds(text: str) -> str:
    block_re = re.compile(
        rf'(?ms)^\s*--\s*{MARK}\s+BEGIN\s*\n.*?^\s*--\s*{MARK}\s+END\s*\n?'
    )
    if block_re.search(text):
        return block_re.sub('', text, count=1)

    # Fallback for the exact block that was added manually before this installer existed.
    fallback = re.compile(
        r'(?ms)^\s*create_bind\(\s*\n\s*vars\.kbWallpaperCarousel,\s*\n\s*hl\.dsp\.exec_cmd\("qs -c wallpaper-carousel ipc call carousel toggle"\)\s*\n\s*\)\s*\n?'
    )
    return fallback.sub('', text, count=1)


def unpatch_execs(text: str) -> str:
    return re.sub(
        rf'(?m)^[ \t]*hl\.exec_cmd\("qs -c wallpaper-carousel -n -d"\)[ \t]*(?:--[ \t]*{MARK})?[ \t]*\n?',
        '',
        text,
        count=1,
    )


def uninstall() -> None:
    log(f"{APP_NAME}: удаление")

    if shutil.which("qs"):
        subprocess.run(
            ["qs", "-c", "wallpaper-carousel", "kill"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )

    if all(p.is_file() for p in (VARIABLES, KEYBINDS, EXECS)):
        backup = backup_configs()
        log(f"Бэкап перед удалением: {backup}")

        variables_text = VARIABLES.read_text(encoding="utf-8")
        keybinds_text = KEYBINDS.read_text(encoding="utf-8")
        execs_text = EXECS.read_text(encoding="utf-8")

        # Detect the exact pre-installer/manual layout used on the original
        # machine. This lets a first-ever Uninstall fully undo the manual setup
        # too, including browser SUPER+B -> SUPER+W.
        legacy_manual = (
            BROWSER_MARK not in variables_text
            and re.search(r'(?m)^\s*kbBrowser\s*=\s*"SUPER \+ B"\s*,?\s*$', variables_text) is not None
            and re.search(r'(?m)^\s*kbWallpaperCarousel\s*=\s*"SUPER \+ W"\s*,?\s*$', variables_text) is not None
            and 'vars.kbWallpaperCarousel' in keybinds_text
            and 'qs -c wallpaper-carousel ipc call carousel toggle' in keybinds_text
            and 'qs -c wallpaper-carousel -n -d' in execs_text
        )

        if legacy_manual:
            log("Обнаружена legacy/manual установка: браузер SUPER+B будет возвращён на SUPER+W.")

        atomic_write(
            VARIABLES,
            unpatch_variables(variables_text, restore_legacy_browser=legacy_manual)
        )
        atomic_write(KEYBINDS, unpatch_keybinds(keybinds_text))
        atomic_write(EXECS, unpatch_execs(execs_text))

    if DEST.exists():
        shutil.rmtree(DEST)

    removed_wallpapers, kept_wallpapers = uninstall_wallpapers()
    log(f"Обои: удалено установщиком {removed_wallpapers}, оставлено изменённых/пользовательских {kept_wallpapers}")

    cache = CACHE_HOME / "wallpaper-carousel"
    if cache.exists():
        shutil.rmtree(cache)

    if shutil.which("hyprctl") and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        subprocess.run(
            ["hyprctl", "reload"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )

    log("Удалено.")
    notify(APP_NAME, "Удалено. Бэкап конфигов сохранён в ~/.local/state.")


def status() -> None:
    print(f"Payload installed: {DEST.is_dir()}")
    for p in (VARIABLES, KEYBINDS, EXECS):
        print(f"{p}: {'OK' if p.is_file() else 'MISSING'}")
    if KEYBINDS.is_file():
        print(f"Keybind configured: {'vars.kbWallpaperCarousel' in KEYBINDS.read_text(encoding='utf-8')}")
    if EXECS.is_file():
        print(f"Autostart configured: {'qs -c wallpaper-carousel -n -d' in EXECS.read_text(encoding='utf-8')}")
    print(f"Wallpaper target: {WALLPAPER_DEST}")
    if WALLPAPER_MANIFEST.is_file():
        manifest = load_wallpaper_manifest()
        print(f"Bundled wallpapers tracked: {len(manifest.get('files', {}))}")
    else:
        print("Bundled wallpapers tracked: 0")


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "install"
    CACHE_HOME.mkdir(parents=True, exist_ok=True)

    # Mirror stdout/stderr into a persistent log while still showing it in a terminal.
    class Tee:
        def __init__(self, *streams): self.streams = streams
        def write(self, data):
            for s in self.streams:
                s.write(data); s.flush()
        def flush(self):
            for s in self.streams: s.flush()

    with LOG.open("a", encoding="utf-8") as lf:
        lf.write(f"\n===== {dt.datetime.now().isoformat(timespec='seconds')} {action} =====\n")
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = Tee(old_out, lf)
        sys.stderr = Tee(old_err, lf)
        try:
            if action == "install":
                install()
            elif action == "uninstall":
                uninstall()
            elif action == "status":
                status()
            else:
                raise RuntimeError(f"Неизвестное действие: {action}")
            return 0
        except Exception as exc:
            log(f"ОШИБКА: {exc}")
            traceback.print_exc()
            notify(APP_NAME, f"Ошибка установки. Подробности: {LOG}", "critical")
            return 1
        finally:
            sys.stdout, sys.stderr = old_out, old_err


if __name__ == "__main__":
    raise SystemExit(main())
