import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland

ShellRoot {
    id: root

    readonly property string home: Quickshell.env("HOME")
    readonly property string configHome: Quickshell.env("XDG_CONFIG_HOME") || (home + "/.config")
    readonly property string stateHome: Quickshell.env("XDG_STATE_HOME") || (home + "/.local/state")
    readonly property string picturesHome: Quickshell.env("XDG_PICTURES_DIR") || (home + "/Pictures")
    readonly property string cacheHome: Quickshell.env("XDG_CACHE_HOME") || (home + "/.cache")
    readonly property string colourIndexPath: cacheHome + "/wallpaper-carousel/colour-index.json"

    readonly property string caelestiaConfigPath: configHome + "/caelestia/shell.json"
    readonly property string caelestiaSchemePath: stateHome + "/caelestia/scheme.json"
    readonly property string caelestiaWallpaperStatePath: stateHome + "/caelestia/wallpaper/path.txt"

    property string wallpaperDir: {
        const envDir = Quickshell.env("CAELESTIA_WALLPAPERS_DIR");
        return envDir && envDir.length > 0 ? expandPath(envDir) : picturesHome + "/Wallpapers";
    }

    property bool smartScheme: true
    property real roundingScale: 1.0
    property real animScale: 1.0

    property string actualCurrent: ""
    property bool opened: false
    property bool initialIndexSynced: false
    property string lastRequestedPath: ""
    property string schemeName: ""
    property bool schemeLight: false

    property color palettePrimary: "#ffb0ca"
    property color paletteSurface: "#191114"
    property color paletteOnSurface: "#efdfe2"
    property color paletteOutline: "#9e8c91"

    // Same base geometry as Serpantinum's WallpaperPicker.
    readonly property real itemWidth: 400
    readonly property real itemHeight: 420
    readonly property real borderWidth: 3
    readonly property real skewFactor: -0.35
    readonly property real selectedCenterOffset: (skewFactor * itemHeight) / 2
    readonly property int carouselHeight: 650
    readonly property int animDuration: Math.max(1, Math.round(400 * animScale))
    readonly property int entranceDuration: Math.max(1, Math.round(650 * animScale))

    property real entranceOffset: 0
    property int scrollAccum: 0
    property bool rebuildingModel: false
    property bool colourIndexDirty: false
    property string lastScanSignature: ""
    property string lastColourSignature: ""
    property var latestPaths: []
    property var colourIndex: ({})
    property string currentBucket: "Unsorted"
    property int bucketRevision: 0

    readonly property var colourBuckets: [
        { name: "Red",        hex: "#FF4500" },
        { name: "Orange",     hex: "#FFA500" },
        { name: "Yellow",     hex: "#FFD700" },
        { name: "Green",      hex: "#32CD32" },
        { name: "Cyan",       hex: "#20C8D8" },
        { name: "Blue",       hex: "#1E90FF" },
        { name: "Purple",     hex: "#8A2BE2" },
        { name: "Pink",       hex: "#FF69B4" },
        { name: "Black",      hex: "#111111" },
        { name: "Monochrome", hex: "#A9A9A9" }
    ]
    property real scrollThreshold: 45
    property bool initialFocusSet: false

    function expandPath(path) {
        if (!path)
            return "";
        let p = String(path);
        p = p.replace(/^~(?=\/|$)/, home);
        p = p.replace(/\$HOME/g, home);
        return p;
    }

    function fileUrl(path) {
        if (!path)
            return "";
        return encodeURI("file://" + path);
    }

    function bucketRank(bucket) {
        switch (bucket) {
        case "Red": return 1;
        case "Orange": return 2;
        case "Yellow": return 3;
        case "Green": return 4;
        case "Cyan": return 5;
        case "Blue": return 6;
        case "Purple": return 7;
        case "Pink": return 8;
        case "Black": return 9;
        case "Monochrome": return 10;
        default: return 99;
        }
    }

    function bucketCount(bucket) {
        const revision = bucketRevision;
        let count = 0;

        for (let i = 0; i < walls.count; ++i) {
            if (walls.get(i).bucket === bucket)
                count++;
        }

        return count;
    }

    function loadColourIndex(text) {
        try {
            const data = JSON.parse(text);
            const items = (data && data.items) ? data.items : [];

            const signature = items.map(function(item) {
                return [
                    item.path || "",
                    item.mtime_ns || 0,
                    item.size || 0,
                    item.bucket || "",
                    item.hex || "",
                    item.hue !== undefined ? item.hue : ""
                ].join("|");
            }).join("\n");

            // The indexer result can arrive once through stdout and once again
            // through FileView. If nothing actually changed, do absolutely nothing.
            if (signature === lastColourSignature)
                return;

            lastColourSignature = signature;

            const map = {};
            for (const item of items) {
                if (item && item.path)
                    map[item.path] = item;
            }

            colourIndex = map;

            if (latestPaths && latestPaths.length > 0)
                rebuildWalls(latestPaths);
        } catch (e) {
            console.warn("wallpaper-carousel: cannot parse colour index:", e);
        }
    }

    function runColourIndexer() {
        if (!wallpaperDir || wallpaperDir.length === 0)
            return;

        if (colourIndexProc.running) {
            colourIndexDirty = true;
            return;
        }

        colourIndexDirty = false;
        colourIndexProc.command = [
            "python3",
            Quickshell.shellDir + "/colour_indexer.py",
            wallpaperDir,
            colourIndexPath
        ];
        colourIndexProc.running = true;
    }

    function rebuildWalls(paths) {
        if (!paths)
            return;

        let selectedPath = actualCurrent;
        if (carousel.currentIndex >= 0 && carousel.currentIndex < walls.count)
            selectedPath = walls.get(carousel.currentIndex).path;

        let items = [];

        for (const path of paths) {
            const slash = path.lastIndexOf("/");
            const info = colourIndex[path] || ({});
            const bucket = info.bucket || "Unsorted";
            const hex = info.hex || "#808080";
            const hue = info.hue !== undefined ? Number(info.hue) : 999;
            const saturation = info.saturation !== undefined ? Number(info.saturation) : 0;
            const value = info.value !== undefined ? Number(info.value) : 0;

            items.push({
                path: path,
                name: slash >= 0 ? path.slice(slash + 1) : path,
                bucket: bucket,
                hex: hex,
                hue: hue,
                saturation: saturation,
                value: value
            });
        }

        items.sort(function(a, b) {
            const ra = root.bucketRank(a.bucket);
            const rb = root.bucketRank(b.bucket);
            if (ra !== rb)
                return ra - rb;

            // Only broad/basic colour groups matter.
            return String(a.name).localeCompare(String(b.name));
        });

        rebuildingModel = true;

        // A model rebuild is internal housekeeping, not user navigation.
        // Kill any pending live-wallpaper request before indices move around.
        liveWallpaperTimer.stop();
        liveWallpaperTimer.pendingPath = "";

        walls.clear();

        for (const item of items)
            walls.append(item);

        bucketRevision++;

        let selectedIndex = -1;
        if (selectedPath) {
            for (let i = 0; i < walls.count; ++i) {
                if (walls.get(i).path === selectedPath) {
                    selectedIndex = i;
                    break;
                }
            }
        }

        if (selectedIndex >= 0)
            carousel.currentIndex = selectedIndex;
        else if (walls.count > 0 && carousel.currentIndex < 0)
            carousel.currentIndex = 0;

        if (carousel.currentIndex >= 0 && carousel.currentIndex < walls.count)
            currentBucket = walls.get(carousel.currentIndex).bucket || "Unsorted";

        Qt.callLater(function() {
            rebuildingModel = false;

            if (!initialIndexSynced)
                syncCurrentIndex(false);
        });
    }

    function jumpToBucket(bucket) {
        if (!bucket || walls.count <= 0)
            return;

        for (let i = 0; i < walls.count; ++i) {
            if (walls.get(i).bucket === bucket) {
                initialFocusSet = true;
                carousel.currentIndex = i;
                carousel.forceActiveFocus();
                return;
            }
        }
    }

    function loadCaelestiaConfig(text) {
        try {
            const data = JSON.parse(text);
            const envDir = Quickshell.env("CAELESTIA_WALLPAPERS_DIR");

            if (envDir && envDir.length > 0)
                wallpaperDir = expandPath(envDir);
            else if (data.paths && data.paths.wallpaperDir)
                wallpaperDir = expandPath(data.paths.wallpaperDir);
            else
                wallpaperDir = picturesHome + "/Wallpapers";

            smartScheme = !(data.services && data.services.smartScheme === false);

            if (data.appearance && data.appearance.rounding && data.appearance.rounding.scale !== undefined)
                roundingScale = Number(data.appearance.rounding.scale);
            else
                roundingScale = 1.0;

            if (data.appearance && data.appearance.anim &&
                data.appearance.anim.durations &&
                data.appearance.anim.durations.scale !== undefined)
                animScale = Number(data.appearance.anim.durations.scale);
            else
                animScale = 1.0;

            Qt.callLater(reloadWallpapers);
        } catch (e) {
            console.warn("wallpaper-carousel: cannot parse Caelestia shell.json:", e);
            Qt.callLater(reloadWallpapers);
        }
    }

    function loadScheme(text) {
        try {
            const data = JSON.parse(text);
            schemeName = data.name || "";
            schemeLight = data.mode === "light";

            const c = data.colours || {};
            if (c.primary) palettePrimary = "#" + c.primary;
            if (c.surface) paletteSurface = "#" + c.surface;
            if (c.onSurface) paletteOnSurface = "#" + c.onSurface;
            if (c.outline) paletteOutline = "#" + c.outline;
        } catch (e) {
            console.warn("wallpaper-carousel: cannot parse Caelestia scheme.json:", e);
        }
    }

    function reloadWallpapers() {
        if (!wallpaperDir || wallpaperDir.length === 0)
            return;

        scanProc.running = false;
        scanProc.command = [
            "find", wallpaperDir, "-type", "f",
            "(",
                "-iname", "*.jpg", "-o",
                "-iname", "*.jpeg", "-o",
                "-iname", "*.png", "-o",
                "-iname", "*.webp", "-o",
                "-iname", "*.gif", "-o",
                "-iname", "*.bmp",
            ")",
            "-print"
        ];
        scanProc.running = true;
    }

    function syncCurrentIndex(force) {
        if ((!force && initialIndexSynced) || walls.count <= 0)
            return;

        let found = -1;
        for (let i = 0; i < walls.count; ++i) {
            if (walls.get(i).path === actualCurrent) {
                found = i;
                break;
            }
        }

        carousel.currentIndex = found >= 0 ? found : 0;
        lastRequestedPath = actualCurrent;
        initialIndexSynced = true;

        Qt.callLater(function() {
            carousel.forceLayout();
            if (carousel.currentIndex >= 0)
                carousel.positionViewAtIndex(carousel.currentIndex, ListView.Center);
            carousel.forceActiveFocus();
            root.initialFocusSet = true;
        });
    }

    function openCarousel() {
        syncCurrentIndex(true);

        entranceAnim.stop();
        entranceOffset = win.width;
        opened = true;

        Qt.callLater(function() {
            carousel.forceActiveFocus();
            entranceAnim.restart();
        });
    }

    function closeCarousel() {
        entranceAnim.stop();
        opened = false;
        entranceOffset = win.width;
    }

    function toggleCarousel() {
        if (opened)
            closeCarousel();
        else
            openCarousel();
    }

    function applyPath(path) {
        if (!path || path.length === 0)
            return;

        const args = ["caelestia", "wallpaper", "-f", path];
        if (!smartScheme)
            args.push("--no-smart");

        lastRequestedPath = path;
        Quickshell.execDetached(args);
    }

    function scheduleLiveWallpaper() {
        if (rebuildingModel || !opened || !initialIndexSynced || carousel.currentIndex < 0 || carousel.currentIndex >= walls.count)
            return;

        liveWallpaperTimer.pendingPath = walls.get(carousel.currentIndex).path;
        liveWallpaperTimer.restart();
    }

    function applyCurrentAndClose() {
        if (carousel.currentIndex >= 0 && carousel.currentIndex < walls.count) {
            const path = walls.get(carousel.currentIndex).path;
            liveWallpaperTimer.stop();

            if (path !== lastRequestedPath)
                applyPath(path);
        }

        root.closeCarousel();
    }

    function selectPrevious() {
        if (walls.count <= 0)
            return;
        initialFocusSet = true;
        carousel.currentIndex = Math.max(0, carousel.currentIndex - 1);
    }

    function selectNext() {
        if (walls.count <= 0)
            return;
        initialFocusSet = true;
        carousel.currentIndex = Math.min(walls.count - 1, carousel.currentIndex + 1);
    }

    readonly property var targetScreen: {
        try {
            const monitor = Hyprland.focusedMonitor;
            const screens = Quickshell.screens;
            if (monitor && screens) {
                const count = screens.length !== undefined ? screens.length : screens.count;
                for (let i = 0; i < count; ++i) {
                    const s = screens[i] !== undefined ? screens[i] : screens.get(i);
                    if (s && s.name === monitor.name)
                        return s;
                }
            }
        } catch (e) {}

        try {
            return Quickshell.screens[0] || Quickshell.screens.get(0);
        } catch (e) {
            return null;
        }
    }

    FileView {
        path: root.caelestiaConfigPath
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: root.loadCaelestiaConfig(text())
        onLoadFailed: root.reloadWallpapers()
    }

    FileView {
        path: root.caelestiaSchemePath
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: root.loadScheme(text())
    }

    FileView {
        path: root.colourIndexPath
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: root.loadColourIndex(text())
    }

    FileView {
        path: root.caelestiaWallpaperStatePath
        watchChanges: true
        printErrors: false
        onFileChanged: reload()
        onLoaded: {
            root.actualCurrent = text().trim();
            if (!root.initialIndexSynced)
                root.syncCurrentIndex(false);
        }
    }

    ListModel {
        id: walls
    }

    Timer {
        id: liveWallpaperTimer

        property string pendingPath: ""
        interval: 70
        repeat: false

        onTriggered: {
            if (root.rebuildingModel)
                return;

            if (pendingPath.length > 0 && pendingPath !== root.lastRequestedPath)
                root.applyPath(pendingPath);
        }
    }

    Process {
        id: scanProc

        stdout: StdioCollector {
            onStreamFinished: {
                const raw = this.text || "";
                let paths = raw.split("\n").map(p => p.trim()).filter(p => p.length > 0);
                paths.sort((a, b) => a.localeCompare(b));

                const signature = paths.join("\n");

                // Polling the directory must not rebuild the ListModel when
                // nothing changed. Rebuilding changes currentIndex and would
                // otherwise look like real user navigation.
                if (signature === root.lastScanSignature)
                    return;

                root.lastScanSignature = signature;
                root.latestPaths = paths;
                root.rebuildWalls(paths);
                root.runColourIndexer();
            }
        }
    }

    Process {
        id: colourIndexProc

        stdout: StdioCollector {
            onStreamFinished: {
                const raw = this.text || "";
                if (raw.trim().length > 0)
                    root.loadColourIndex(raw);

                if (root.colourIndexDirty)
                    Qt.callLater(root.runColourIndexer);
            }
        }

        onExited: (exitCode) => {
            if (exitCode !== 0)
                console.warn("wallpaper-carousel: colour indexer exited with code", exitCode);

            if (root.colourIndexDirty)
                Qt.callLater(root.runColourIndexer);
        }
    }

    Timer {
        id: wallpaperFolderPoller
        interval: 4000
        repeat: true
        running: true

        onTriggered: {
            if (!scanProc.running)
                root.reloadWallpapers();
        }
    }

    NumberAnimation {
        id: entranceAnim
        target: root
        property: "entranceOffset"
        from: win.width
        to: 0
        duration: root.entranceDuration
        easing.type: Easing.OutCubic
    }

    IpcHandler {
        target: "carousel"

        function open(): void {
            root.openCarousel();
        }

        function close(): void {
            root.closeCarousel();
        }

        function toggle(): void {
            root.toggleCarousel();
        }
    }

    PanelWindow {
        id: win

        screen: root.targetScreen
        color: "transparent"

        WlrLayershell.namespace: "wallpaper-carousel"
        WlrLayershell.layer: WlrLayer.Overlay
        WlrLayershell.exclusionMode: ExclusionMode.Ignore
        WlrLayershell.keyboardFocus: root.opened ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

        anchors.top: true
        anchors.bottom: true
        anchors.left: true
        anchors.right: true

        visible: true
        mask: root.opened ? null : emptyInputRegion

        Region {
            id: emptyInputRegion
        }

        Shortcut {
            sequence: "Escape"
            context: Qt.WindowShortcut
            onActivated: root.closeCarousel()
        }

        Shortcut {
            sequence: "Left"
            context: Qt.WindowShortcut
            onActivated: root.selectPrevious()
        }

        Shortcut {
            sequence: "Right"
            context: Qt.WindowShortcut
            onActivated: root.selectNext()
        }

        Shortcut {
            sequence: "Return"
            context: Qt.WindowShortcut
            onActivated: root.applyCurrentAndClose()
        }

        Shortcut {
            sequence: "Enter"
            context: Qt.WindowShortcut
            onActivated: root.applyCurrentAndClose()
        }

        MouseArea {
            anchors.fill: parent
            onClicked: root.closeCarousel()
        }

        Item {
            id: carouselStage

            opacity: root.opened ? 1.0 : 0.0
            width: parent.width

            transform: Translate {
                x: root.entranceOffset
            }
            height: Math.min(root.carouselHeight, parent.height)
            anchors.verticalCenter: parent.verticalCenter

            MouseArea {
                anchors.fill: parent
                // Prevent a click on the carousel area itself from closing the overlay.
            }


            Rectangle {
                id: paletteBar

                anchors.top: parent.top
                anchors.topMargin: 65
                anchors.horizontalCenter: parent.horizontalCenter

                z: 500
                height: 48
                width: paletteRow.implicitWidth + 22
                radius: Math.max(10, 18 * root.roundingScale)

                color: Qt.rgba(
                    root.paletteSurface.r,
                    root.paletteSurface.g,
                    root.paletteSurface.b,
                    0.92
                )
                border.width: 1
                border.color: Qt.rgba(
                    root.paletteOutline.r,
                    root.paletteOutline.g,
                    root.paletteOutline.b,
                    0.55
                )

                Row {
                    id: paletteRow

                    anchors.centerIn: parent
                    spacing: 8

                    Rectangle {
                        height: 32
                        width: bucketName.implicitWidth + 20
                        radius: Math.max(8, 11 * root.roundingScale)
                        color: Qt.rgba(
                            root.paletteOnSurface.r,
                            root.paletteOnSurface.g,
                            root.paletteOnSurface.b,
                            0.10
                        )

                        Text {
                            id: bucketName
                            anchors.centerIn: parent
                            text: root.currentBucket === "Unsorted" ? "…" : root.currentBucket
                            color: root.paletteOnSurface
                            font.pixelSize: 12
                            font.bold: true
                        }
                    }

                    Rectangle {
                        width: 1
                        height: 24
                        anchors.verticalCenter: parent.verticalCenter
                        color: Qt.rgba(
                            root.paletteOutline.r,
                            root.paletteOutline.g,
                            root.paletteOutline.b,
                            0.45
                        )
                    }

                    Repeater {
                        model: root.colourBuckets

                        delegate: Item {
                            required property var modelData

                            readonly property int groupCount: root.bucketCount(modelData.name)
                            visible: groupCount > 0
                            width: visible ? 30 : 0
                            height: 32

                            Rectangle {
                                anchors.centerIn: parent
                                width: root.currentBucket === modelData.name ? 28 : 26
                                height: width
                                radius: Math.max(7, 9 * root.roundingScale)

                                color: modelData.hex
                                border.width: root.currentBucket === modelData.name ? 3 : 1
                                border.color: root.currentBucket === modelData.name
                                    ? root.paletteOnSurface
                                    : Qt.rgba(
                                        root.paletteOnSurface.r,
                                        root.paletteOnSurface.g,
                                        root.paletteOnSurface.b,
                                        0.28
                                    )

                                Behavior on width {
                                    NumberAnimation {
                                        duration: Math.max(1, Math.round(180 * root.animScale))
                                        easing.type: Easing.OutCubic
                                    }
                                }

                                Behavior on height {
                                    NumberAnimation {
                                        duration: Math.max(1, Math.round(180 * root.animScale))
                                        easing.type: Easing.OutCubic
                                    }
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.jumpToBucket(modelData.name)
                            }
                        }
                    }
                }
            }

            ListView {
                id: carousel

                anchors.fill: parent
                orientation: ListView.Horizontal
                spacing: 0
                clip: false
                interactive: true
                cacheBuffer: Math.max(width * 2, root.itemWidth * 10)
                reuseItems: true
                focus: true

                model: walls

                highlightRangeMode: ListView.StrictlyEnforceRange
                preferredHighlightBegin: (width / 2) - ((root.itemWidth * 1.5 + 4) / 2) + root.selectedCenterOffset
                preferredHighlightEnd: (width / 2) + ((root.itemWidth * 1.5 + 4) / 2) + root.selectedCenterOffset
                highlightMoveDuration: root.animDuration

                header: Item {
                    width: Math.max(0, (carousel.width / 2) - ((root.itemWidth * 1.5) / 2) + root.selectedCenterOffset)
                }

                footer: Item {
                    width: Math.max(0, (carousel.width / 2) - ((root.itemWidth * 1.5) / 2) - root.selectedCenterOffset)
                }

                onCurrentIndexChanged: {
                    if (currentIndex >= 0 && currentIndex < walls.count)
                        root.currentBucket = walls.get(currentIndex).bucket || "Unsorted";

                    scrollDebounce.restart();
                    root.scheduleLiveWallpaper();
                }

                add: Transition {
                    NumberAnimation {
                        properties: "x,y"
                        duration: root.animDuration
                        easing.type: Easing.OutCubic
                    }
                }

                addDisplaced: Transition {
                    NumberAnimation {
                        properties: "x,y"
                        duration: root.animDuration
                        easing.type: Easing.OutCubic
                    }
                }

                move: Transition {
                    NumberAnimation {
                        properties: "x,y"
                        duration: root.animDuration
                        easing.type: Easing.OutCubic
                    }
                }

                moveDisplaced: Transition {
                    NumberAnimation {
                        properties: "x,y"
                        duration: root.animDuration
                        easing.type: Easing.OutCubic
                    }
                }

                remove: Transition {
                    NumberAnimation {
                        properties: "x,y"
                        duration: root.animDuration
                        easing.type: Easing.OutCubic
                    }
                }

                removeDisplaced: Transition {
                    NumberAnimation {
                        properties: "x,y"
                        duration: root.animDuration
                        easing.type: Easing.OutCubic
                    }
                }

                displaced: Transition {
                    NumberAnimation {
                        properties: "x,y"
                        duration: root.animDuration
                        easing.type: Easing.OutCubic
                    }
                }

                Timer {
                    id: scrollDebounce
                    interval: 1
                    onTriggered: carousel.forceActiveFocus()
                }

                MouseArea {
                    anchors.fill: parent
                    acceptedButtons: Qt.NoButton

                    onWheel: wheel => {
                        const dx = wheel.angleDelta.x;
                        const dy = wheel.angleDelta.y;
                        const delta = Math.abs(dx) > Math.abs(dy) ? dx : dy;

                        root.scrollAccum += delta;

                        if (Math.abs(root.scrollAccum) >= root.scrollThreshold) {
                            if (root.scrollAccum > 0)
                                root.selectPrevious();
                            else
                                root.selectNext();

                            root.scrollAccum = 0;
                        }

                        wheel.accepted = true;
                    }
                }

                delegate: Item {
                    id: card

                    required property int index
                    required property string path
                    required property string name

                    readonly property bool isCurrent: ListView.isCurrentItem
                    readonly property int dist: Math.abs(index - carousel.currentIndex)
                    readonly property real sideScale: Math.max(0.58, Math.pow(0.88, Math.max(0, dist - 1)))

                    readonly property real cellWidth: isCurrent
                        ? (root.itemWidth * 1.5 + 4)
                        : (root.itemWidth * 0.48 * sideScale)

                    readonly property real targetWidth: isCurrent
                        ? (root.itemWidth * 1.5)
                        : (root.itemWidth * 0.48 * sideScale)

                    readonly property real targetHeight: isCurrent
                        ? (root.itemHeight + 30)
                        : (root.itemHeight * Math.max(0.62, Math.pow(0.90, Math.max(0, dist - 1))))

                    readonly property real radiusValue: {
                        const baseRadius = 24 * root.roundingScale;
                        if (baseRadius <= 0)
                            return 0;

                        const k = Math.min(1.0, Math.pow(baseRadius / 48, 2));
                        const decay = Math.max(0.45, Math.pow(0.85, dist));
                        return baseRadius * (1.0 - k * (1.0 - decay));
                    }

                    width: cellWidth
                    height: targetHeight
                    anchors.verticalCenter: parent ? parent.verticalCenter : undefined
                    anchors.verticalCenterOffset: 25
                    z: isCurrent ? 100 : Math.max(1, 50 - dist)

                    Behavior on width {
                        enabled: root.initialFocusSet
                        NumberAnimation {
                            duration: root.animDuration
                            easing.type: Easing.OutCubic
                        }
                    }

                    Behavior on height {
                        enabled: root.initialFocusSet
                        NumberAnimation {
                            duration: root.animDuration
                            easing.type: Easing.OutCubic
                        }
                    }

                    Item {
                        id: skewedWrapper

                        anchors.centerIn: parent
                        anchors.horizontalCenterOffset: -(root.skewFactor * height) / 2

                        property real targetPadding: 0

                        Behavior on targetPadding {
                            NumberAnimation {
                                duration: root.animDuration
                                easing.type: Easing.OutCubic
                            }
                        }

                        width: parent.width - targetPadding
                        height: parent ? parent.height : 0

                        transform: Matrix4x4 {
                            property real s: root.skewFactor
                            matrix: Qt.matrix4x4(
                                1, s, 0, 0,
                                0, 1, 0, 0,
                                0, 0, 1, 0,
                                0, 0, 0, 1
                            )
                        }

                        MouseArea {
                            anchors.fill: parent

                            onClicked: {
                                if (card.index !== carousel.currentIndex) {
                                    root.initialFocusSet = true;
                                    carousel.currentIndex = card.index;
                                    carousel.forceActiveFocus();
                                } else {
                                    root.applyCurrentAndClose();
                                }
                            }
                        }

                        Rectangle {
                            anchors.fill: parent
                            radius: card.radiusValue
                            color: root.paletteSurface
                        }

                        Rectangle {
                            id: imageMask
                            anchors.fill: parent
                            radius: card.radiusValue
                            visible: false
                            layer.enabled: true
                        }

                        Item {
                            anchors.fill: parent
                            layer.enabled: true

                            layer.effect: MultiEffect {
                                maskEnabled: true
                                maskSource: imageMask
                            }

                            Image {
                                anchors.centerIn: parent
                                anchors.horizontalCenterOffset: -50

                                width: (root.itemWidth * 1.5) + ((root.itemHeight + 30) * Math.abs(root.skewFactor)) + 50
                                height: root.itemHeight + 30

                                source: root.fileUrl(card.path)
                                fillMode: Image.PreserveAspectCrop
                                asynchronous: true
                                cache: true
                                smooth: true
                                antialiasing: true

                                sourceSize.width: Math.round(
                                    (root.itemWidth * 1.5) +
                                    ((root.itemHeight + 30) * Math.abs(root.skewFactor)) +
                                    50
                                )
                                sourceSize.height: Math.round(root.itemHeight + 30)

                                transform: Matrix4x4 {
                                    property real s: -root.skewFactor
                                    matrix: Qt.matrix4x4(
                                        1, s, 0, 0,
                                        0, 1, 0, 0,
                                        0, 0, 1, 0,
                                        0, 0, 0, 1
                                    )
                                }
                            }
                        }
                    }
                }
            }

            Text {
                anchors.centerIn: parent
                visible: walls.count === 0 && !scanProc.running

                text: "No wallpapers found\n" + root.wallpaperDir
                color: root.paletteOnSurface
                horizontalAlignment: Text.AlignHCenter
                font.pixelSize: 16
                opacity: 0.85
            }
        }
    }

    Component.onCompleted: {
        Qt.callLater(reloadWallpapers);
    }
}
