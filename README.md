# Wenderer Wallpaper Carousel

An animated wallpaper carousel for **Caelestia + Hyprland + Quickshell**.

This repository contains the tested **Wallpaper Carousel v7.7**, a one-click installer/uninstaller and a bundled wallpaper pack.

## Features

- Animated wallpaper carousel
- Live wallpaper switching through Caelestia
- Automatic colour grouping and filtering
- Warmed image cache for fast reopening
- `SUPER + W` shortcut for the carousel
- Automatic startup with Hyprland
- One-click install / uninstall
- Bundled starter wallpaper pack

## Preview

![Wallpaper Carousel — Blue filter](docs/screenshots/blue.jpg)

## Installation

```bash
git clone https://github.com/dmasta606/Wenderer-Wallpaper-Carousel.git
cd Wenderer-Wallpaper-Carousel
./Install.sh
```

After installation:

```text
SUPER + B  -> browser
SUPER + W  -> Wallpaper Carousel
```

## Uninstall

```bash
./Uninstall.sh
```

## Important

This is not a standalone wallpaper engine. The current version integrates with Caelestia.

Detailed compatibility notes, exact Hyprland paths, installer anchors, backups and future-maintenance information are kept in [`README.txt`](README.txt).

## Credits / Inspiration

The wallpaper carousel concept and much of its visual direction were inspired by [Serpantinum](https://github.com/ilyamiro/serpantinum) by [Illia Miroshnichenko (@ilyamiro)](https://github.com/ilyamiro).

Serpantinum was the main reference and inspiration for the wallpaper picker / carousel idea and its overall animation feel.

This repository is a separate personal implementation made for Caelestia and is not affiliated with or endorsed by the Serpantinum project.

Special thanks to Illia for making Serpantinum public and for the original inspiration.

## Version

- installer: **v2.1**
- carousel: **v7.7**
- colour index algorithm: **6**
