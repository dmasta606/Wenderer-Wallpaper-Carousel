Wenderer Wallpaper Carousel — personal installer v2.1
===================================================

Назначение
----------
Это личный установщик проверенной версии Wallpaper Carousel v7.7 для текущего
сетапа Caelestia + Hyprland + Quickshell.

Главная цель — после переустановки Arch не повторять ручную настройку:
распаковать архив -> запустить Install.desktop -> получить готовую карусель,
бинд SUPER+W, автозапуск и стартовый пак обоев.

Это НЕ standalone-программа: текущая shell.qml всё ещё интегрирована с
Caelestia. Она использует Caelestia для текущих обоев/динамической схемы и
применения wallpaper. Установщик рассчитан именно на Caelestia-сетап.


Быстрая установка
-----------------
1. Сначала установить/настроить Caelestia и один раз запустить обычный Hyprland.
2. Распаковать этот архив куда угодно, например в Downloads.
3. Двойной клик по Install.desktop.
4. Если файловый менеджер не разрешает запуск .desktop из распакованной папки,
   запустить Install.sh через пункт «Запустить».

После установки:
  SUPER+B -> браузер
  SUPER+W -> Wallpaper Carousel

Карусель запускается автоматически вместе с Hyprland.


Что находится внутри
--------------------
Install.desktop        — графический ярлык установки
Uninstall.desktop      — графический ярлык удаления
Install.sh             — запасной запуск установки
Uninstall.sh           — запасной запуск удаления
installer.py           — вся логика установки/удаления
README.txt             — этот файл
payload/shell.qml      — рабочая карусель v7.7
payload/colour_indexer.py
payload/wallpapers/    — стартовый пак обоев

Стартовый пак v2:
  58 файлов, примерно 192 MiB исходных изображений
  категории: Anime, Cosmo, CyberPunk, Nature

Для установки обоев НЕ нужен 7z/zip: изображения уже лежат внутри установщика
обычными файлами.


Куда ставятся файлы
-------------------
Карусель:
  ~/.config/quickshell/wallpaper-carousel/shell.qml
  ~/.config/quickshell/wallpaper-carousel/colour_indexer.py

Обои:
  <XDG Pictures>/Wallpapers/

На обычном текущем сетапе это:
  ~/Pictures/Wallpapers/

Установщик пытается получить Pictures через:
  xdg-user-dir PICTURES

Если это недоступно, fallback:
  ~/Pictures

Кэш самой карусели:
  ~/.cache/wallpaper-carousel/

Состояние/бэкапы установщика:
  ~/.local/state/wenderer-wallpaper-carousel-installer/

Бэкапы конфигов:
  ~/.local/state/wenderer-wallpaper-carousel-installer/backups/

Manifest установленных комплектных обоев:
  ~/.local/state/wenderer-wallpaper-carousel-installer/wallpapers-installed.json

Лог:
  ~/.cache/wenderer-wallpaper-carousel-installer.log


Какие Hyprland-файлы меняет установщик
--------------------------------------
1) ~/.config/hypr/variables.lua

Ожидаемый текущий anchor:
  kbBrowser = "SUPER + W"

На чистом текущем Caelestia-сетапе установщик меняет браузер на:
  kbBrowser = "SUPER + B"

и добавляет:
  kbWallpaperCarousel = "SUPER + W"

Если kbBrowser уже вручную назначен на другое сочетание, установщик старается
его не перезаписывать без необходимости.


2) ~/.config/hypr/hyprland/keybinds.lua

Ожидаемый anchor:
  create_bind(vars.kbBrowser, hl.dsp.exec_cmd(vars.browser))

Сразу после него добавляется блок:

  create_bind(
      vars.kbWallpaperCarousel,
      hl.dsp.exec_cmd("qs -c wallpaper-carousel ipc call carousel toggle")
  )

В установленной версии блок окружён служебными комментариями-маркерами
WENDERER_WALLPAPER_CAROUSEL, чтобы uninstall мог удалить именно его.


3) ~/.config/hypr/hyprland/execs.lua

Ожидаемый anchor:
  hl.exec_cmd("caelestia shell -d")

После него добавляется:
  hl.exec_cmd("qs -c wallpaper-carousel -n -d")


Почему установщик проверяет anchors
-----------------------------------
Caelestia/Hyprland могут изменить структуру конфигов в будущем.
Перед первой записью установщик проверяет ожидаемые точки в:
  variables.lua
  keybinds.lua
  execs.lua

Если структура не похожа на текущую, установка прерывается ДО опасной правки.
Это намеренно: лучше получить ошибку, чем автоматически сломать новый конфиг.


Повторная установка
-------------------
Установщик рассчитан на повторный запуск:
- bind карусели не дублируется;
- автозапуск не дублируется;
- payload карусели обновляется;
- новый бэкап конфигов создаётся перед каждой установкой;
- комплектные обои повторно не копируются без необходимости.

Комплектные обои обновляются только если файл ранее был установлен этим
установщиком И после установки пользователь его не изменял.


Безопасность пользовательских обоев
------------------------------------
Установщик НЕ затирает уже существующий файл с таким же путём/именем, если не
может доказать по manifest, что этот файл был установлен предыдущей версией
этого же установщика.

При uninstall удаляются только комплектные обои, которые:
1. записаны в wallpapers-installed.json;
2. всё ещё имеют тот же SHA-256, что был записан установщиком.

Если комплектную картинку после установки отредактировать/заменить — uninstall
её оставит.

Любые добавленные вручную пользовательские обои uninstall не удаляет.


Первое удаление существующей ручной установки
------------------------------------------------
v2.1 умеет распознать именно тот manual/legacy-сетап, который был настроен
до появления этого установщика:

  kbBrowser = "SUPER + B"
  kbWallpaperCarousel = "SUPER + W"

  create_bind(
      vars.kbWallpaperCarousel,
      hl.dsp.exec_cmd("qs -c wallpaper-carousel ipc call carousel toggle")
  )

  hl.exec_cmd("qs -c wallpaper-carousel -n -d")

Если одновременно присутствует весь этот шаблон и служебных маркеров
установщика ещё нет, Uninstall считает его старой ручной установкой и:
- удаляет carousel bind;
- удаляет autostart;
- удаляет kbWallpaperCarousel;
- возвращает браузер SUPER+B -> SUPER+W.

Это сделано специально, чтобы можно было безопасно проверить цикл:
  legacy/manual setup -> Uninstall -> stock-like state -> Install -> managed setup

Если шаблон не совпадает полностью, установщик не делает это предположение
вслепую.

Что делает Uninstall
--------------------
- останавливает qs -c wallpaper-carousel;
- делает новый бэкап Hyprland-конфигов;
- убирает переменную/бинд/автозапуск карусели;
- если браузер SUPER+W -> SUPER+B менял именно установщик, возвращает SUPER+W;
- удаляет ~/.config/quickshell/wallpaper-carousel/;
- удаляет кэш карусели;
- удаляет только неизменённые комплектные обои из manifest;
- оставляет пользовательские и изменённые обои;
- делает hyprctl reload, если Hyprland сейчас запущен.

Старые бэкапы намеренно не удаляются.


Диагностика
-----------
Из папки установщика можно проверить состояние командой:

  python3 installer.py status

Основной лог:
  ~/.cache/wenderer-wallpaper-carousel-installer.log

Если установка не сработала после будущего обновления Caelestia, для ремонта
установщика полезно сохранить/передать:

  ~/.config/hypr/variables.lua
  ~/.config/hypr/hyprland/keybinds.lua
  ~/.config/hypr/hyprland/execs.lua
  этот README.txt
  installer.py

Можно также получить короткие фрагменты командами:

  grep -n -A8 -B8 'kbBrowser' ~/.config/hypr/variables.lua
  grep -n -A10 -B10 'kbBrowser' ~/.config/hypr/hyprland/keybinds.lua
  grep -n -A8 -B8 'caelestia shell -d' ~/.config/hypr/hyprland/execs.lua

Этого достаточно, чтобы переписать anchors под новую структуру без повторного
расследования всего сегодняшнего сетапа.


Текущая логика самой карусели (важно для будущего)
--------------------------------------------------
Версия payload: v7.7.

Основные свойства:
- standalone Quickshell-конфиг, но backend/схема интегрированы с Caelestia;
- persistent qs service;
- IPC target: carousel;
- toggle:
    qs -c wallpaper-carousel ipc call carousel toggle
- запуск:
    qs -c wallpaper-carousel -n -d
- остановка:
    qs -c wallpaper-carousel kill
- входная анимация карусели справа;
- прогрев изображений для мгновенного открытия;
- live wallpaper при смене центральной карточки;
- цветовая фильтрация/индексация;
- algorithmVersion = 6;
- группы: Red, Orange, Yellow, Green, Cyan, Blue, Purple, Pink, Black,
  Monochrome;
- цветовые кластеры агрегируются по группе (логика v7.7).

Caelestia-интеграция текущего shell.qml использует:
  ~/.config/caelestia/shell.json
  ~/.local/state/caelestia/scheme.json
  ~/.local/state/caelestia/wallpaper/path.txt
  caelestia wallpaper -f <path>

Именно поэтому при полном отказе от Caelestia потребуется отдельная переделка
backend/state/theme, а не только installer.py.


Проверка v2.1 перед упаковкой
---------------------------
Установщик v2 был прогнан в изолированном тестовом HOME по циклу:
  install -> status -> повторный install -> uninstall

В тесте дополнительно:
- существующий пользовательский файл в Wallpapers сохранился;
- файл, добавленный пользователем после установки, сохранился;
- один намеренно изменённый комплектный wallpaper сохранился;
- остальные 57 неизменённых комплектных wallpaper удалились;
- variables.lua вернулся к исходному SUPER+W для браузера;
- блок keybind карусели удалился;
- строка autostart карусели удалилась;
- повторная установка не создала дубликаты.

Это проверяет логику установщика на тестовой копии конфигов. Реальную систему
всё равно нельзя математически гарантировать после будущих изменений Caelestia;
поэтому существуют preflight-проверки, бэкапы и лог.



Дополнительная проверка v2.1
----------------------------
Отдельно проверен сценарий первой миграции с ручной установки:
- browser = SUPER+B без installer marker;
- kbWallpaperCarousel = SUPER+W без installer marker;
- manual carousel bind;
- manual autostart.

После Uninstall:
- browser снова SUPER+W;
- kbWallpaperCarousel отсутствует;
- carousel bind отсутствует;
- autostart отсутствует.

После следующего Install:
- browser снова SUPER+B уже с installer marker;
- carousel = SUPER+W;
- bind/autostart возвращаются как managed-изменения.
