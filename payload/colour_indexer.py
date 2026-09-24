#!/usr/bin/env python3
import colorsys
import json
import math
import os
import subprocess
import sys
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

ALGORITHM_VERSION = 6
SAMPLE_SIZE = 64
K_CLUSTERS = 6
KMEANS_ITERATIONS = 14

BUCKET_ORDER = {
    "Red": 1,
    "Orange": 2,
    "Yellow": 3,
    "Green": 4,
    "Cyan": 5,
    "Blue": 6,
    "Purple": 7,
    "Pink": 8,
    "Black": 9,
    "Monochrome": 10,
}

COLOUR_BUCKETS = [
    "Red", "Orange", "Yellow", "Green",
    "Cyan", "Blue", "Purple", "Pink",
]


def load_cache(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if data.get("algorithmVersion") != ALGORITHM_VERSION:
            return {}

        return {
            item["path"]: item
            for item in data.get("items", [])
            if item.get("path")
        }
    except Exception:
        return {}


def decode_pixels(path):
    try:
        from PIL import Image

        with Image.open(path) as image:
            if getattr(image, "is_animated", False):
                try:
                    image.seek(0)
                except Exception:
                    pass

            image = image.convert("RGB").resize(
                (SAMPLE_SIZE, SAMPLE_SIZE),
                Image.Resampling.BOX,
            )
            return list(image.getdata())
    except Exception:
        pass

    for command in ("magick", "convert"):
        try:
            raw = subprocess.check_output(
                [
                    command,
                    f"{path}[0]",
                    "-resize",
                    f"{SAMPLE_SIZE}x{SAMPLE_SIZE}!",
                    "-depth",
                    "8",
                    "rgb:-",
                ],
                stderr=subprocess.DEVNULL,
                timeout=10,
            )

            expected = SAMPLE_SIZE * SAMPLE_SIZE * 3
            if len(raw) >= expected:
                raw = raw[:expected]
                return [
                    (raw[i], raw[i + 1], raw[i + 2])
                    for i in range(0, expected, 3)
                ]
        except Exception:
            continue

    try:
        raw = subprocess.check_output(
            [
                "ffmpeg",
                "-v", "error",
                "-i", path,
                "-vf", f"scale={SAMPLE_SIZE}:{SAMPLE_SIZE}",
                "-frames:v", "1",
                "-f", "rawvideo",
                "-pix_fmt", "rgb24",
                "pipe:1",
            ],
            stderr=subprocess.DEVNULL,
            timeout=10,
        )

        expected = SAMPLE_SIZE * SAMPLE_SIZE * 3
        if len(raw) >= expected:
            raw = raw[:expected]
            return [
                (raw[i], raw[i + 1], raw[i + 2])
                for i in range(0, expected, 3)
            ]
    except Exception:
        pass

    return [(128, 128, 128)]


def srgb_to_linear(c):
    c /= 255.0
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def rgb_to_lab(rgb):
    r, g, b = [srgb_to_linear(v) for v in rgb]

    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041

    x /= 0.95047
    z /= 1.08883

    def f(t):
        delta = 6 / 29
        if t > delta ** 3:
            return t ** (1 / 3)
        return t / (3 * delta * delta) + 4 / 29

    fx, fy, fz = f(x), f(y), f(z)

    return (
        116 * fy - 16,
        500 * (fx - fy),
        200 * (fy - fz),
    )


def dist2(a, b):
    return (
        (a[0] - b[0]) ** 2
        + (a[1] - b[1]) ** 2
        + (a[2] - b[2]) ** 2
    )


def quantize_pixels(pixels):
    bins = {}

    for r, g, b in pixels:
        key = (r // 8, g // 8, b // 8)

        if key not in bins:
            bins[key] = [0, 0, 0, 0]

        rec = bins[key]
        rec[0] += r
        rec[1] += g
        rec[2] += b
        rec[3] += 1

    points = []

    for total_r, total_g, total_b, count in bins.values():
        rgb = (
            total_r / count,
            total_g / count,
            total_b / count,
        )

        points.append({
            "rgb": rgb,
            "lab": rgb_to_lab(rgb),
            "weight": count,
        })

    return points


def initial_centers(points, k):
    if not points:
        return [(50.0, 0.0, 0.0)]

    first = max(points, key=lambda p: p["weight"])
    centers = [first["lab"]]

    while len(centers) < min(k, len(points)):
        best = None
        best_score = -1.0

        for point in points:
            nearest = min(dist2(point["lab"], c) for c in centers)
            score = nearest * math.sqrt(point["weight"])

            if score > best_score:
                best_score = score
                best = point

        if best is None:
            break

        centers.append(best["lab"])

    return centers


def kmeans(points, k=K_CLUSTERS):
    if not points:
        return []

    centers = initial_centers(points, k)

    for _ in range(KMEANS_ITERATIONS):
        groups = [
            {
                "w": 0.0,
                "lab": [0.0, 0.0, 0.0],
                "rgb": [0.0, 0.0, 0.0],
            }
            for _ in centers
        ]

        for point in points:
            idx = min(
                range(len(centers)),
                key=lambda i: dist2(point["lab"], centers[i]),
            )

            w = point["weight"]
            group = groups[idx]
            group["w"] += w

            for j in range(3):
                group["lab"][j] += point["lab"][j] * w
                group["rgb"][j] += point["rgb"][j] * w

        new_centers = []

        for idx, group in enumerate(groups):
            if group["w"] <= 0:
                new_centers.append(centers[idx])
                continue

            new_centers.append(tuple(
                value / group["w"]
                for value in group["lab"]
            ))

        movement = sum(
            dist2(centers[i], new_centers[i])
            for i in range(len(centers))
        )

        centers = new_centers

        if movement < 0.01:
            break

    groups = [
        {
            "w": 0.0,
            "rgb": [0.0, 0.0, 0.0],
        }
        for _ in centers
    ]

    for point in points:
        idx = min(
            range(len(centers)),
            key=lambda i: dist2(point["lab"], centers[i]),
        )

        w = point["weight"]
        group = groups[idx]
        group["w"] += w

        for j in range(3):
            group["rgb"][j] += point["rgb"][j] * w

    total_weight = sum(group["w"] for group in groups) or 1.0
    clusters = []

    for group in groups:
        if group["w"] <= 0:
            continue

        rgb = tuple(value / group["w"] for value in group["rgb"])

        r, g, b = rgb
        rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
        h, s, v = colorsys.rgb_to_hsv(rf, gf, bf)

        luma = (
            0.2126 * r
            + 0.7152 * g
            + 0.0722 * b
        ) / 255.0

        clusters.append({
            "rgb": rgb,
            "share": group["w"] / total_weight,
            "hue": h * 360.0,
            "saturation": s,
            "value": v,
            "luma": luma,
        })

    clusters.sort(key=lambda c: c["share"], reverse=True)
    return clusters


def hue_bucket(hue):
    if hue >= 345 or hue < 15:
        return "Red"
    if hue < 45:
        return "Orange"
    if hue < 75:
        return "Yellow"
    if hue < 165:
        return "Green"
    if hue < 200:
        return "Cyan"
    if hue < 245:
        return "Blue"
    if hue < 300:
        return "Purple"
    return "Pink"


def cluster_salience(cluster):
    """
    Human-ish visual salience:
    - area matters, but sub-linearly so a huge dull background is not unbeatable
    - saturation matters strongly
    - brightness matters only mildly
    """
    share = max(cluster["share"], 0.0001)
    sat = cluster["saturation"]
    value = cluster["value"]

    return (
        (share ** 0.72)
        * (0.18 + 1.82 * (sat ** 1.55))
        * (0.88 + 0.12 * min(value, 0.90))
    )


def classify_clusters(clusters):
    if not clusters:
        return {
            "bucket": "Monochrome",
            "hex": "#808080",
            "hue": 999.0,
            "saturation": 0.0,
            "value": 0.5,
            "darkRatio": 0.0,
            "dominantShare": 1.0,
            "bucketScores": {},
            "clusters": [],
        }

    dark_ratio = sum(
        c["share"]
        for c in clusters
        if c["luma"] < 0.16 or c["value"] < 0.18
    )

    neutral_ratio = sum(
        c["share"]
        for c in clusters
        if c["saturation"] < 0.12
    )

    bucket_scores = {name: 0.0 for name in COLOUR_BUCKETS}
    bucket_shares = {name: 0.0 for name in COLOUR_BUCKETS}
    bucket_clusters = {name: [] for name in COLOUR_BUCKETS}

    for cluster in clusters:
        # Do not let genuinely black/grey clusters pretend to be coloured.
        if (
            cluster["saturation"] < 0.14
            or cluster["value"] < 0.16
            or cluster["luma"] < 0.055
        ):
            continue

        bucket = hue_bucket(cluster["hue"])
        score = cluster_salience(cluster)

        bucket_scores[bucket] += score
        bucket_shares[bucket] += cluster["share"]
        bucket_clusters[bucket].append(cluster)

    top_bucket = max(bucket_scores, key=bucket_scores.get)
    top_score = bucket_scores[top_bucket]
    top_share = bucket_shares[top_bucket]

    sorted_scores = sorted(bucket_scores.values(), reverse=True)
    second_score = sorted_scores[1] if len(sorted_scores) > 1 else 0.0

    # How convincing is the best colour compared to the alternatives?
    dominance = (
        top_score / (second_score + 1e-6)
        if top_score > 0
        else 0.0
    )

    # Accent-aware rule:
    # ~10-15% strongly saturated red/yellow/purple can legitimately define
    # the visual identity of a black wallpaper.
    meaningful_colour = (
        top_score >= 0.105
        and (
            top_share >= 0.10
            or top_score >= 0.19
        )
    )

    # If a colour is quite small, require it to be very clearly stronger than
    # competing colours. This stops tiny red eyes from changing a monochrome image.
    if top_share < 0.10 and dominance < 1.65:
        meaningful_colour = False

    # Black is now a fallback, not a first-pass winner.
    if meaningful_colour:
        representatives = bucket_clusters[top_bucket]

        # Representative cluster for hex/hue metadata:
        representative = max(
            representatives,
            key=cluster_salience,
        )

        r, g, b = [round(v) for v in representative["rgb"]]

        result = {
            "bucket": top_bucket,
            "hex": f"#{r:02x}{g:02x}{b:02x}",
            "hue": round(representative["hue"], 3),
            "saturation": round(representative["saturation"], 5),
            "value": round(representative["value"], 5),
            "darkRatio": round(dark_ratio, 5),
            "dominantShare": round(top_share, 5),
        }
    else:
        dominant = clusters[0]
        r, g, b = [round(v) for v in dominant["rgb"]]

        # A truly dark image with no meaningful colour identity is Black.
        # Otherwise neutral / silver / grey / white is Monochrome.
        if dark_ratio >= 0.42:
            bucket = "Black"
        elif neutral_ratio >= 0.62:
            bucket = "Monochrome"
        elif dark_ratio >= 0.30 and top_score < 0.075:
            bucket = "Black"
        else:
            bucket = "Monochrome"

        result = {
            "bucket": bucket,
            "hex": f"#{r:02x}{g:02x}{b:02x}",
            "hue": 999.0,
            "saturation": round(dominant["saturation"], 5),
            "value": round(dominant["value"], 5),
            "darkRatio": round(dark_ratio, 5),
            "dominantShare": round(dominant["share"], 5),
        }

    debug_clusters = []

    for cluster in clusters:
        r, g, b = [round(v) for v in cluster["rgb"]]

        debug_clusters.append({
            "hex": f"#{r:02x}{g:02x}{b:02x}",
            "share": round(cluster["share"], 5),
            "hue": round(cluster["hue"], 2),
            "saturation": round(cluster["saturation"], 4),
            "value": round(cluster["value"], 4),
            "luma": round(cluster["luma"], 4),
            "bucket": (
                hue_bucket(cluster["hue"])
                if cluster["saturation"] >= 0.14
                else "Neutral"
            ),
            "salience": round(cluster_salience(cluster), 5),
        })

    result["bucketScores"] = {
        bucket: round(score, 5)
        for bucket, score in bucket_scores.items()
        if score > 0
    }
    result["bucketShares"] = {
        bucket: round(share, 5)
        for bucket, share in bucket_shares.items()
        if share > 0
    }
    result["topColourScore"] = round(top_score, 5)
    result["topColourShare"] = round(top_share, 5)
    result["colourDominance"] = round(dominance, 5)
    result["neutralRatio"] = round(neutral_ratio, 5)
    result["clusters"] = debug_clusters

    return result


def classify_pixels(pixels):
    return classify_clusters(
        kmeans(
            quantize_pixels(pixels)
        )
    )


def sort_key(item):
    return (
        BUCKET_ORDER.get(item["bucket"], 99),
        item.get("name", "").casefold(),
    )


def iter_images(root):
    root = os.path.abspath(os.path.expanduser(root))
    result = []

    for current_root, dirs, files in os.walk(root):
        dirs.sort(key=str.casefold)

        for name in sorted(files, key=str.casefold):
            path = os.path.join(current_root, name)

            if Path(name).suffix.lower() in IMAGE_EXTS:
                result.append(path)

    return result


def main():
    if len(sys.argv) < 3:
        print(json.dumps({
            "algorithmVersion": ALGORITHM_VERSION,
            "items": [],
        }))
        return

    wallpaper_dir = os.path.abspath(os.path.expanduser(sys.argv[1]))
    cache_path = os.path.abspath(os.path.expanduser(sys.argv[2]))
    old = load_cache(cache_path)

    items = []

    for path in iter_images(wallpaper_dir):
        try:
            stat = os.stat(path)
        except OSError:
            continue

        cached = old.get(path)

        if (
            cached
            and cached.get("mtime_ns") == stat.st_mtime_ns
            and cached.get("size") == stat.st_size
            and cached.get("bucket")
            and cached.get("hex")
        ):
            items.append(cached)
            continue

        item = {
            "path": path,
            "name": os.path.basename(path),
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
        }

        item.update(
            classify_pixels(
                decode_pixels(path)
            )
        )

        items.append(item)

    items.sort(key=sort_key)

    data = {
        "algorithmVersion": ALGORITHM_VERSION,
        "sourceDir": wallpaper_dir,
        "items": items,
    }

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    tmp = cache_path + ".tmp"

    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    os.replace(tmp, cache_path)

    sys.stdout.write(
        json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    sys.stdout.flush()


if __name__ == "__main__":
    main()
