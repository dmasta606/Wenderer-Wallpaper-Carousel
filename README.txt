Wenderer Wallpaper Carousel — personal installer v2.1
=======================================================

Purpose
-------
This is a personal installer for the tested Wallpaper Carousel v7.7 used with
the current Caelestia + Hyprland + Quickshell setup.

The main goal is to avoid repeating the entire manual setup after reinstalling
Arch Linux:

  extract / clone -> run Install.desktop -> get the working carousel,
  SUPER+W keybind, autostart and a starter wallpaper pack.

This is NOT a standalone application. The current shell.qml is still integrated
with Caelestia. It uses Caelestia for the current wallpaper state, dynamic
colour scheme and wallpaper application.

The installer is designed specifically for a Caelestia-based setup.


Credits / Inspiration
---------------------
The wallpaper carousel concept and much of its visual direction were inspired
by Serpantinum:

  https://github.com/ilyamiro/serpantinum

Serpantinum is created by Illia Miroshnichenko (@ilyamiro):

  https://github.com/ilyamiro

Serpantinum was the main reference and inspiration for the wallpaper picker /
carousel idea and its overall animation feel.

This repository is a separate personal implementation made for Caelestia and
is not affiliated with or endorsed by the Serpantinum project.

Special thanks to Illia for making Serpantinum public and for the original
inspiration.


Quick installation
------------------
1. Install and configure Caelestia first, then launch a normal Hyprland session
   at least once.
2. Clone this repository or extract the installer archive anywhere, for example
   into Downloads.
3. Double-click Install.desktop.
4. If the file manager does not allow launching .desktop files from the
   extracted directory, run Install.sh using the file manager's "Run" action
   or from a terminal.

After installation:

  SUPER+B -> browser
  SUPER+W -> Wallpaper Carousel

The carousel starts automatically together with Hyprland.


Repository / installer contents
-------------------------------
Install.desktop        — graphical installation launcher
Uninstall.desktop      — graphical uninstall launcher
Install.sh             — fallback installation entry point
Uninstall.sh           — fallback uninstall entry point
installer.py           — all installation / uninstall logic
README.txt             — this file
payload/shell.qml      — working Wallpaper Carousel v7.7
payload/colour_indexer.py
payload/wallpapers/    — starter wallpaper pack

Starter wallpaper pack v2:

  58 files
  approximately 192 MiB of original images

Categories:

  Anime
  Cosmo
  CyberPunk
  Nature

No 7z or zip extraction is required for the wallpaper pack. The images are
already stored as normal files inside the installer / repository.


Installation paths
------------------
Carousel:

  ~/.config/quickshell/wallpaper-carousel/shell.qml
  ~/.config/quickshell/wallpaper-carousel/colour_indexer.py

Wallpapers:

  <XDG Pictures>/Wallpapers/

On the current standard setup this is:

  ~/Pictures/Wallpapers/

The installer tries to resolve the Pictures directory using:

  xdg-user-dir PICTURES

If that is unavailable, the fallback is:

  ~/Pictures

Carousel cache:

  ~/.cache/wallpaper-carousel/

Installer state / backups:

  ~/.local/state/wenderer-wallpaper-carousel-installer/

Configuration backups:

  ~/.local/state/wenderer-wallpaper-carousel-installer/backups/

Manifest of bundled wallpapers installed by the installer:

  ~/.local/state/wenderer-wallpaper-carousel-installer/wallpapers-installed.json

Log:

  ~/.cache/wenderer-wallpaper-carousel-installer.log


Hyprland files modified by the installer
----------------------------------------

1) ~/.config/hypr/variables.lua

Expected current anchor:

  kbBrowser = "SUPER + W"

On a clean current Caelestia setup, the installer changes the browser binding
to:

  kbBrowser = "SUPER + B"

and adds:

  kbWallpaperCarousel = "SUPER + W"

If kbBrowser has already been manually assigned to another shortcut, the
installer tries not to overwrite it unnecessarily.


2) ~/.config/hypr/hyprland/keybinds.lua

Expected anchor:

  create_bind(vars.kbBrowser, hl.dsp.exec_cmd(vars.browser))

Immediately after it, the installer adds:

  create_bind(
      vars.kbWallpaperCarousel,
      hl.dsp.exec_cmd("qs -c wallpaper-carousel ipc call carousel toggle")
  )

In the managed installation, this block is surrounded by
WENDERER_WALLPAPER_CAROUSEL marker comments so the uninstaller can remove the
exact block it created.


3) ~/.config/hypr/hyprland/execs.lua

Expected anchor:

  hl.exec_cmd("caelestia shell -d")

Immediately after it, the installer adds:

  hl.exec_cmd("qs -c wallpaper-carousel -n -d")


Why the installer validates anchors
-----------------------------------
Caelestia / Hyprland may change their configuration layout in the future.

Before the first write, the installer validates the expected anchor points in:

  variables.lua
  keybinds.lua
  execs.lua

If the structure no longer resembles the current setup, installation stops
BEFORE making potentially unsafe changes.

This is intentional: receiving an installation error is better than
automatically breaking a newer configuration.


Reinstalling / updating
-----------------------
The installer is designed to be safely executed more than once:

- the carousel keybind is not duplicated;
- the autostart entry is not duplicated;
- the carousel payload is updated;
- a new configuration backup is created before every installation;
- bundled wallpapers are not copied again unless necessary.

A bundled wallpaper is updated only when:

1. it was previously installed by this installer; and
2. the user has not modified the installed file since then.


Safety of user wallpapers
-------------------------
The installer does NOT overwrite an already existing wallpaper with the same
path / filename unless it can confirm from the manifest that the file was
installed by a previous version of this installer.

During uninstall, a bundled wallpaper is removed only when:

1. it is recorded in wallpapers-installed.json; and
2. its SHA-256 still matches the hash recorded by the installer.

If a bundled wallpaper is edited or replaced after installation, the
uninstaller leaves it untouched.

Any wallpapers manually added by the user are also preserved.


First uninstall of an existing manual installation
--------------------------------------------------
v2.1 can recognize the exact manual / legacy setup that existed before this
installer was created:

  kbBrowser = "SUPER + B"
  kbWallpaperCarousel = "SUPER + W"

  create_bind(
      vars.kbWallpaperCarousel,
      hl.dsp.exec_cmd("qs -c wallpaper-carousel ipc call carousel toggle")
  )

  hl.exec_cmd("qs -c wallpaper-carousel -n -d")

If the entire pattern is present and the installer marker comments are not yet
present, Uninstall treats it as the old manual setup and:

- removes the carousel keybind;
- removes the carousel autostart entry;
- removes kbWallpaperCarousel;
- restores the browser shortcut from SUPER+B back to SUPER+W.

This exists specifically so the following migration path can be tested safely:

  legacy/manual setup -> Uninstall -> stock-like state -> Install -> managed setup

If the complete pattern does not match, the installer does not make this
assumption blindly.


What Uninstall does
-------------------
- stops qs -c wallpaper-carousel;
- creates a fresh backup of the Hyprland configuration files;
- removes the carousel variable / keybind / autostart entry;
- restores the browser shortcut to SUPER+W if the installer was the component
  that changed it from SUPER+W to SUPER+B;
- removes ~/.config/quickshell/wallpaper-carousel/;
- removes the carousel cache;
- removes only unchanged bundled wallpapers recorded in the manifest;
- preserves user-added and user-modified wallpapers;
- runs hyprctl reload when Hyprland is currently running.

Old backups are intentionally preserved.


Diagnostics
-----------
From the installer directory, the current state can be checked with:

  python3 installer.py status

Main log:

  ~/.cache/wenderer-wallpaper-carousel-installer.log

If installation stops working after a future Caelestia update, the most useful
files to keep / provide when updating the installer are:

  ~/.config/hypr/variables.lua
  ~/.config/hypr/hyprland/keybinds.lua
  ~/.config/hypr/hyprland/execs.lua
  this README.txt
  installer.py

Short relevant configuration excerpts can also be collected with:

  grep -n -A8 -B8 'kbBrowser' ~/.config/hypr/variables.lua
  grep -n -A10 -B10 'kbBrowser' ~/.config/hypr/hyprland/keybinds.lua
  grep -n -A8 -B8 'caelestia shell -d' ~/.config/hypr/hyprland/execs.lua

This should be enough to adapt the installer anchors to a future configuration
layout without repeating the entire original investigation.


Current carousel implementation notes
-------------------------------------
Payload version:

  v7.7

Main properties:

- standalone Quickshell configuration, while backend / colour scheme handling
  remain integrated with Caelestia;
- persistent qs service;
- IPC target:

    carousel

- toggle command:

    qs -c wallpaper-carousel ipc call carousel toggle

- start command:

    qs -c wallpaper-carousel -n -d

- stop command:

    qs -c wallpaper-carousel kill

- right-edge entrance animation;
- image warming / preloading for near-instant reopening;
- live wallpaper switching when the centered card changes;
- wallpaper colour classification and filtering;
- algorithmVersion = 6;
- colour groups:

    Red
    Orange
    Yellow
    Green
    Cyan
    Blue
    Purple
    Pink
    Black
    Monochrome

- colour clusters are aggregated by group using the v7.7 logic.

The current shell.qml uses the following Caelestia integration points:

  ~/.config/caelestia/shell.json
  ~/.local/state/caelestia/scheme.json
  ~/.local/state/caelestia/wallpaper/path.txt
  caelestia wallpaper -f <path>

Because of this, fully removing the Caelestia dependency would require a
separate backend / state / theme implementation. Updating installer.py alone
would not be enough.


Installer v2 validation
-----------------------
Installer v2 was tested in an isolated HOME using the following cycle:

  install -> status -> install again -> uninstall

The test additionally verified that:

- an existing user wallpaper in Wallpapers was preserved;
- a wallpaper added by the user after installation was preserved;
- one intentionally modified bundled wallpaper was preserved;
- the other 57 unchanged bundled wallpapers were removed;
- variables.lua returned to the original SUPER+W browser shortcut;
- the carousel keybind block was removed;
- the carousel autostart line was removed;
- running the installer twice did not create duplicate entries.

This validates the installer logic against test copies of the configuration
files.

No installer can mathematically guarantee compatibility with future Caelestia
changes, which is why the project includes preflight validation, backups and
logging.


Additional v2.1 validation
--------------------------
The first migration from the old manual setup was tested separately.

Initial state:

- browser = SUPER+B without an installer marker;
- kbWallpaperCarousel = SUPER+W without an installer marker;
- manual carousel keybind;
- manual carousel autostart.

After Uninstall:

- browser returned to SUPER+W;
- kbWallpaperCarousel was absent;
- carousel keybind was absent;
- carousel autostart was absent.

After running Install again:

- browser returned to SUPER+B, now managed by the installer;
- carousel shortcut returned to SUPER+W;
- keybind and autostart returned as managed installer changes.


Real-system validation
----------------------
v2.1 was also tested on the actual target system.

The following sequence was completed successfully:

  existing manual setup
  -> Uninstall
  -> verification
  -> Install
  -> reboot
  -> verification

After reboot:

- Wallpaper Carousel started automatically;
- SUPER+W opened the carousel;
- SUPER+B opened the browser;
- the carousel worked normally.

This confirms the current installer on the intended system configuration.

Future Caelestia / Hyprland updates may still require changes to installer
anchors or integration paths.
