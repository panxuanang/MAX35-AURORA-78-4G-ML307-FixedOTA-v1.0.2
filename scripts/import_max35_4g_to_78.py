#!/usr/bin/env python3
"""Import SpotPear MAX35 4G/ML307 hardware into current 78/xiaozhi-esp32.

Architecture rule:
- Current 78/xiaozhi owns Application / AudioService / Protocol / MCP / ML307.
- SpotPear vendor source contributes the physical MAX35 4G board implementation.
- This repository contributes only the AURORA LVGL presentation layer and a
  deterministic rear-camera 4G build configuration.

The official MAX35 4G SKU is rear-camera + touch + ML307. Touch hardware is
preserved if the vendor board initializes it, but AURORA itself does not depend
on touch and this importer never adds a touch-shutter gate to MCP.
"""

from pathlib import Path
import argparse
import json
import re
import shutil

PRODUCT_BOARD_SYMBOL = "BOARD_TYPE_SPOTPEAR_MAX35_4G"
PRODUCT_BOARD_CONFIG = f"CONFIG_{PRODUCT_BOARD_SYMBOL}"
PRODUCT_BOARD_DIR = Path("spotpear/max35-4g")
PRODUCT_NAME = "max35-4g-ml307-gc0308"
PRODUCT_TYPE = "max35-4g"
FIXED_OTA_URL = "http://124.221.112.55:8002/xiaozhi/ota/"
SRC_SUFFIXES = {".c", ".cc", ".cpp", ".h", ".hpp"}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def source_files(directory: Path):
    return [
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in SRC_SUFFIXES
    ]


def has_ml307_signature(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in (
        "ml307board",
        "ml307_board",
        "dualnetworkboard",
        "dual_network_board",
        "ml307_tx",
        "ml307_rx",
        "ml307r",
        "ml307a",
    ))


def _kconfig_blocks(text: str):
    """Yield (symbol, block_text) for Kconfig `config` blocks."""
    matches = list(re.finditer(r"(?m)^\s*config\s+([A-Za-z0-9_]+)\s*$", text))
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        yield match.group(1), text[match.start():end]


def discover_vendor_4g_symbol(vendor: Path) -> str | None:
    """Find the vendor's *actual* MAX35 ML307 menuconfig symbol.

    Do not guess from generic `main/boards/common/ml307_board.*`: that was the
    bug in v1.0.1.  SpotPear exposes a dedicated menu item named roughly
    `Spotpear ESP32-S3-3.5-LCD-cam-ML307`; use that source-of-truth first.
    """
    candidates = []
    for kconfig in (vendor / "main").rglob("Kconfig*"):
        if not kconfig.is_file():
            continue
        text = read(kconfig)
        for symbol, block in _kconfig_blocks(text):
            low = block.lower()
            if "spotpear" not in low:
                continue
            if "ml307" not in low and "4g" not in low:
                continue
            if not any(token in low for token in ("3.5", "3_5", "max35", "lcd-cam", "lcd cam")):
                continue
            score = 0
            if "ml307" in low: score += 80
            if "3.5" in low or "3_5" in low: score += 60
            if "lcd-cam" in low or "lcd cam" in low: score += 40
            if "max35" in low: score += 35
            if symbol.startswith("BOARD_TYPE_"): score += 20
            candidates.append((score, symbol, kconfig, block))

    if not candidates:
        print("[vendor] no explicit MAX35-ML307 Kconfig symbol found; will use strict hardware-folder fallback")
        return None

    candidates.sort(key=lambda item: (-item[0], item[1]))
    best = candidates[0]
    if len(candidates) > 1 and candidates[1][0] == best[0] and candidates[1][1] != best[1]:
        detail = ", ".join(f"{sym}@{path.name}" for _, sym, path, _ in candidates[:6])
        raise SystemExit("Ambiguous SpotPear MAX35 ML307 Kconfig options: " + detail)

    print(f"[vendor] 4G board menuconfig symbol: CONFIG_{best[1]} ({best[2]})")
    return best[1]


def _extract_cmake_branch(text: str, config_symbol: str) -> str | None:
    token = f"CONFIG_{config_symbol}"
    match = re.search(rf"(?m)^\s*(?:if|elseif)\s*\(\s*{re.escape(token)}\s*\)\s*$", text)
    if not match:
        return None
    tail = text[match.end():]
    stop = re.search(r"(?m)^\s*(?:elseif\s*\(|else\s*\(\s*\)|endif\s*\(\s*\))", tail)
    end = match.end() + (stop.start() if stop else len(tail))
    return text[match.start():end]


def _resolve_vendor_board_dir(boards: Path, raw: str) -> Path | None:
    raw = raw.strip().strip('"').strip("'")
    if not raw or "$" in raw or "{" in raw:
        return None
    raw = raw.replace("\\", "/")
    if raw.startswith("main/boards/"):
        raw = raw[len("main/boards/"):]
    if raw.startswith("boards/"):
        raw = raw[len("boards/"):]
    candidate = boards / raw
    return candidate if candidate.is_dir() else None


def locate_vendor_board(vendor: Path) -> tuple[Path, str | None]:
    """Locate the real MAX35 hardware folder, never `main/boards/common`.

    v1.0.1 ranked folders by the presence of "ML307" and accidentally selected
    the generic common network base.  That directory has no ST7796/MAX35 display,
    which is exactly why the user's Action failed with "no SpiLcdDisplay".

    This version follows SpotPear's own Kconfig -> CMake board mapping first,
    then falls back to the exact MAX35 hardware folder proven by the working
    rear-camera project (`sp-esp32-s3-lcd-3.5`).
    """
    boards = vendor / "main" / "boards"
    if not boards.is_dir():
        raise SystemExit(f"Vendor source has no main/boards directory: {boards}")

    vendor_symbol = discover_vendor_4g_symbol(vendor)
    mapped = []
    if vendor_symbol:
        cmake_files = [vendor / "main" / "CMakeLists.txt"]
        cmake_files += [p for p in (vendor / "main").rglob("*.cmake") if p.is_file()]
        for cmake in cmake_files:
            if not cmake.is_file():
                continue
            text = read(cmake)
            branch = _extract_cmake_branch(text, vendor_symbol)
            if not branch:
                continue
            print("[vendor] matched CMake branch for 4G option in", cmake)
            for pattern in (
                r"set\s*\(\s*BOARD_DIR\s+[\"']([^\"']+)[\"']\s*\)",
                r"set\s*\(\s*BOARD_TYPE\s+[\"']([^\"']+)[\"']\s*\)",
            ):
                for raw in re.findall(pattern, branch, flags=re.I):
                    resolved = _resolve_vendor_board_dir(boards, raw)
                    if resolved is not None:
                        mapped.append(resolved)
                        print(f"[vendor] CMake maps 4G option -> {resolved.relative_to(boards)}")

    # SpotPear's MAX35 hardware folder used by the already-working rear-camera
    # project.  The 4G menu option can select a conditional ML307 branch inside
    # this same physical-board implementation.
    exact_names = (
        "sp-esp32-s3-lcd-3.5",
        "sp-esp32-s3-lcd-3.5-ml307",
        "sp-esp32-s3-lcd-3.5-ML307",
        "sp-esp32-s3-lcd-3.5-4g",
        "sp-esp32-s3-lcd-3.5-4G",
    )
    exact = [boards / name for name in exact_names if (boards / name).is_dir()]

    ordered = []
    seen = set()
    for candidate in mapped + exact:
        key = candidate.resolve()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(candidate)

    def is_real_max35_hw(candidate: Path) -> tuple[bool, int, str]:
        try:
            rel = candidate.relative_to(boards).as_posix().lower()
        except ValueError:
            return False, 0, "outside boards"
        if rel == "common" or rel.startswith("common/"):
            return False, 0, "generic common board directory"
        files = source_files(candidate)
        if not files:
            return False, 0, "no board source files"
        blob = "\n".join(read(p) for p in files)
        low = blob.lower()
        score = 0
        if "spilcddisplay" in low: score += 120
        if "st7796" in low: score += 60
        if "esp_video_init_dvp_config_t" in low or "esp_cam_ctlr_dvp_pin_config_t" in low: score += 55
        if "gc0308" in low: score += 35
        if "es8311" in low: score += 25
        if "3.5" in rel or "3.5" in low: score += 20
        if "max35" in rel or "max35" in low: score += 20
        return score >= 120, score, f"score={score}"

    for candidate in ordered:
        ok, score, reason = is_real_max35_hw(candidate)
        print(f"[vendor] candidate {candidate.relative_to(boards)}: {reason}")
        if ok:
            return candidate, vendor_symbol

    # Last-resort search is hardware-first, not ML307-first.  Generic common
    # networking code can never win this ranking.
    ranked = []
    for d in boards.rglob("*"):
        if not d.is_dir():
            continue
        ok, score, _ = is_real_max35_hw(d)
        if not ok:
            continue
        rel = d.relative_to(boards).as_posix().lower()
        if "sp-esp32-s3-lcd-3.5" in rel: score += 150
        if "spotpear" in rel: score += 30
        ranked.append((score, d))

    if not ranked:
        raise SystemExit(
            "Could not locate the real SpotPear MAX35 hardware board. "
            "The importer intentionally refuses to use main/boards/common."
        )
    ranked.sort(key=lambda item: (-item[0], len(str(item[1]))))
    best = ranked[0][1]
    print(f"[vendor] hardware-first fallback -> {best.relative_to(boards)}")
    return best, vendor_symbol

def patch_kconfig(upstream: Path) -> None:
    path = upstream / "main" / "Kconfig.projbuild"
    text = read(path)
    if re.search(rf"(?m)^\s*config\s+{PRODUCT_BOARD_SYMBOL}\s*$", text):
        return

    anchor = re.search(
        r"(?m)^\s*config\s+BOARD_TYPE_SPOTPEAR_ESP32_S3_1_54_MUMA\s*$", text
    )
    if not anchor:
        raise SystemExit("Current 78 Kconfig SpotPear anchor not found")
    remainder = text[anchor.end():]
    next_cfg = re.search(r"(?m)^\s*config\s+BOARD_TYPE_", remainder)
    if not next_cfg:
        raise SystemExit("Could not find insertion point after SpotPear Kconfig anchor")
    pos = anchor.end() + next_cfg.start()
    block = (
        f"    config {PRODUCT_BOARD_SYMBOL}\n"
        "        bool \"SpotPear MAX35 3.5-inch 4G ML307\"\n"
        "        depends on IDF_TARGET_ESP32S3\n"
    )
    text = text[:pos] + block + text[pos:]
    write(path, text)
    print("[patch] registered Kconfig board", PRODUCT_BOARD_SYMBOL)


def patch_cmake(upstream: Path) -> None:
    path = upstream / "main" / "CMakeLists.txt"
    text = read(path)

    board_block = (
        f"elseif(CONFIG_{PRODUCT_BOARD_SYMBOL})\n"
        f"    set(BOARD_DIR \"{PRODUCT_BOARD_DIR.as_posix()}\")\n"
        "    set(BUILTIN_TEXT_FONT font_noto_sans_basic_20_4)\n"
        "    set(BUILTIN_ICON_FONT font_material_symbols_20_4)\n"
        "    set(DEFAULT_EMOJI_COLLECTION noto-color-emoji_64)\n"
    )
    if f"CONFIG_{PRODUCT_BOARD_SYMBOL}" not in text:
        anchor = "elseif(CONFIG_BOARD_TYPE_SPOTPEAR_ESP32_S3_1_54_MUMA)"
        idx = text.find(anchor)
        if idx < 0:
            raise SystemExit("Current 78 CMake SpotPear anchor not found")
        text = text[:idx] + board_block + text[idx:]
        print("[patch] registered CMake BOARD_DIR", PRODUCT_BOARD_DIR)

    sources = [
        "display/aurora_max35/aurora_max35_display.cc",
        "display/aurora_max35/ui_home.cc",
        "display/aurora_max35/ui_chat.cc",
    ]
    missing = [src for src in sources if f'"{src}"' not in text]
    if missing:
        anchor = '            "display/lcd_display.cc"'
        if anchor not in text:
            raise SystemExit("Current 78 CMake display source anchor not found")
        addition = "\n".join(f'            "{src}"' for src in missing)
        text = text.replace(anchor, anchor + "\n" + addition, 1)
        print("[patch] registered AURORA UI sources")

    write(path, text)


def create_current_config(board_dst: Path) -> None:
    # Official MAX35 4G retail SKU is rear camera + touch + ML307. SpotPear's
    # instructions use 90 degree camera rotation for rear camera. GC0308 is the
    # default 0.3MP module and YUV422 is required by the vendor instructions.
    sdk = [
        f"{PRODUCT_BOARD_CONFIG}=y",
        "CONFIG_USE_DEFAULT_MESSAGE_STYLE=y",
        "CONFIG_USE_WECHAT_MESSAGE_STYLE=n",
        "CONFIG_ESPTOOLPY_FLASHSIZE_16MB=y",
        "CONFIG_LV_FONT_MONTSERRAT_48=y",
        "CONFIG_ESP_VIDEO_ENABLE_DVP_VIDEO_DEVICE=y",
        "CONFIG_CAMERA_OV2640=n",
        "CONFIG_CAMERA_OV2640_AUTO_DETECT_DVP_INTERFACE_SENSOR=n",
        "CONFIG_CAMERA_OV5640=n",
        "CONFIG_CAMERA_OV5640_AUTO_DETECT_DVP_INTERFACE_SENSOR=n",
        "CONFIG_CAMERA_GC0308=y",
        "CONFIG_CAMERA_GC0308_AUTO_DETECT_DVP_INTERFACE_SENSOR=y",
        "CONFIG_CAMERA_GC0308_DVP_YUV422_YUYV_640X480_16FPS=y",
        "CONFIG_CAMERA_GC0308_DVP_DEFAULT_FMT_YUV422_YUYV_640X480_16FPS=y",
        "CONFIG_XIAOZHI_ENABLE_ROTATE_CAMERA_IMAGE=y",
        "CONFIG_XIAOZHI_CAMERA_IMAGE_ROTATION_ANGLE_90=y",
        # 78/esp-ml307 recommends keeping UART interrupt handling in IRAM when
        # a UI/camera workload may delay the modem UART service path.
        "CONFIG_UART_ISR_IN_IRAM=y",
    ]

    sdk.append(f'CONFIG_OTA_URL="{FIXED_OTA_URL}"')
    print(f"[config] fixed OTA/backend discovery URL: {FIXED_OTA_URL}")

    cfg = {
        "manufacturer": "spotpear",
        "type": PRODUCT_TYPE,
        "target": "esp32s3",
        "builds": [{"name": PRODUCT_NAME, "sdkconfig_append": sdk}],
    }
    write(board_dst / "config.json", json.dumps(cfg, ensure_ascii=False, indent=4) + "\n")
    print("[config] wrote MAX35 4G ML307 config: rear GC0308 + 90-degree rotation")


def rewrite_vendor_board_symbols(board_dst: Path, vendor_symbol: str | None = None) -> None:
    # Vendor branches have used several menuconfig names. Prefer symbols that
    # explicitly identify ML307/4G. Only if the selected dedicated board folder
    # has no such symbol do we rewrite a single MAX35/3.5 SpotPear symbol. This
    # avoids accidentally enabling both Wi-Fi and ML307 branches when a vendor
    # source file contains both variants.
    symbol_re = re.compile(r"\bCONFIG_BOARD_TYPE_SPOTPEAR_[A-Z0-9_]+\b")
    files = [
        path for path in board_dst.rglob("*")
        if path.is_file() and path.suffix.lower() in SRC_SUFFIXES
    ]
    symbols = sorted({
        sym
        for path in files
        for sym in symbol_re.findall(read(path))
        if "3_5" in sym or "MAX35" in sym
    })
    four_g = [sym for sym in symbols if "ML307" in sym or "4G" in sym]
    explicit = f"CONFIG_{vendor_symbol}" if vendor_symbol else None

    if explicit and explicit in symbols:
        replace_set = {explicit}
    elif four_g:
        replace_set = set(four_g)
    elif len(symbols) == 1:
        replace_set = set(symbols)
    else:
        known = {
            "CONFIG_BOARD_TYPE_SPOTPEAR_ESP32_S3_3_5_LCD",
            "CONFIG_BOARD_TYPE_SPOTPEAR_ESP32_S3_3_5_LCD_CAM",
        }
        candidates = [sym for sym in symbols if sym in known]
        if len(candidates) == 1:
            replace_set = set(candidates)
        elif not symbols:
            replace_set = set()
        else:
            raise SystemExit(
                "Ambiguous SpotPear board-choice symbols inside selected ML307 directory: "
                + ", ".join(symbols)
            )

    changed = 0
    for path in files:
        text = read(path)
        original = text
        for token in replace_set:
            text = text.replace(token, PRODUCT_BOARD_CONFIG)
        if text != original:
            write(path, text)
            changed += 1

    if replace_set:
        print("[patch] vendor board symbol(s):", ", ".join(sorted(replace_set)), "->", PRODUCT_BOARD_CONFIG)
    else:
        print("[patch] vendor board has no local SpotPear board-choice macro to rewrite")
    print(f"[patch] normalized vendor SpotPear board symbols in {changed} file(s)")


def patch_board_display(board_dst: Path) -> None:
    include = '#include "display/aurora_max35/aurora_max35_display.h"'
    patched = False

    for path in board_dst.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".h", ".hpp", ".cc", ".cpp"}:
            continue
        text = read(path)
        original = text

        if "SpiLcdDisplay" not in text and "AuroraMax35Display" not in text:
            continue

        if include not in text:
            old_inc = '#include "display/lcd_display.h"'
            if old_inc in text:
                text = text.replace(old_inc, old_inc + "\n" + include, 1)
            else:
                text = include + "\n" + text

        text, count = re.subn(r"new\s+SpiLcdDisplay\s*\(", "new AuroraMax35Display(", text)
        if count:
            patched = True
            print("[patch] direct display construction:", path.name)

        classes = re.findall(
            r"class\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*public\s+SpiLcdDisplay", text
        )
        for cls in classes:
            text = re.sub(
                rf"class\s+{re.escape(cls)}\s*:\s*public\s+SpiLcdDisplay",
                f"class {cls} : public AuroraMax35Display",
                text,
                count=1,
            )
            text = text.replace(
                "using SpiLcdDisplay::SpiLcdDisplay;",
                "using AuroraMax35Display::AuroraMax35Display;",
            )
            text = re.sub(r":\s*SpiLcdDisplay\s*\(", ": AuroraMax35Display(", text)
            text = text.replace(
                "SpiLcdDisplay::SetupUI();", "AuroraMax35Display::SetupUI();"
            )
            patched = True
            print(f"[patch] preserved vendor {cls}, changed display base")

        if text != original:
            write(path, text)

    if not patched:
        raise SystemExit(
            "Vendor MAX35 4G board has no SpiLcdDisplay construction/subclass to attach AURORA UI"
        )


def verify_ml307_board(board_dst: Path) -> None:
    texts = []
    for path in board_dst.rglob("*"):
        if path.is_file() and path.suffix.lower() in SRC_SUFFIXES:
            texts.append(read(path))
    blob = "\n".join(texts)
    low = blob.lower()

    base_ok = any(token in low for token in (
        "ml307board",
        "ml307_board",
        "dualnetworkboard",
        "dual_network_board",
    ))
    pin_ok = (
        ("ml307" in low and "tx" in low and "rx" in low)
        or re.search(r"Ml307Board\s*\(", blob) is not None
        or re.search(r"DualNetworkBoard\s*\(", blob) is not None
    )
    if not base_ok or not pin_ok:
        raise SystemExit(
            "Selected vendor board does not contain a convincing ML307 network implementation. "
            "Refusing to produce a Wi-Fi-only firmware mislabeled as 4G."
        )
    print("[OK] vendor board contains ML307/DualNetwork integration")


def patch_max35_camera(board_dst: Path) -> None:
    """Migrate the SpotPear IDF5-era esp_video wrapper to current 78 EspVideo."""
    patched_files = 0
    migrated_ctor = 0
    migrated_member = 0
    old_include = re.compile(r'#\s*include\s*[<"](?:boards/common/)?esp32_camera\.h[>"]')
    old_ctor = re.compile(r"new\s+Esp32Camera\s*\(\s*video_config\s*\)")
    old_member = re.compile(r"\bEsp32Camera\s*\*\s*camera_\b")
    camera_sources = []

    for path in board_dst.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".h", ".hpp", ".cc", ".cpp"}:
            continue
        text = read(path)
        if not any(
            token in text
            for token in (
                "esp_video_init_config_t",
                "esp_video_init_dvp_config_t",
                "esp_video_init_sccb_config_t",
                "esp_cam_ctlr_dvp_pin_config_t",
            )
        ):
            continue

        camera_sources.append(path)
        original = text
        text, inc_count = old_include.subn('#include "esp_video.h"', text)
        if inc_count == 0 and '#include "esp_video.h"' not in text:
            match = re.search(r"(?m)^#\s*include[^\n]*$", text)
            if not match:
                raise SystemExit(f"MAX35 camera source has no include block: {path}")
            text = text[:match.end()] + '\n#include "esp_video.h"' + text[match.end():]

        text, member_count = old_member.subn("EspVideo* camera_", text)
        text, ctor_count = old_ctor.subn("new EspVideo(video_config)", text)
        migrated_member += member_count
        migrated_ctor += ctor_count

        if text != original:
            write(path, text)
            patched_files += 1
            print(f"[patch] current-78 EspVideo camera wrapper: {path.name}")

    if not camera_sources:
        raise SystemExit("MAX35 4G vendor board has no esp_video DVP camera source to migrate")

    for path in camera_sources:
        text = read(path)
        if old_include.search(text):
            raise SystemExit(f"old esp32_camera.h include remains in MAX35 DVP source: {path}")
        if old_ctor.search(text):
            raise SystemExit(f"old Esp32Camera(video_config) constructor remains: {path}")
        if old_member.search(text):
            raise SystemExit(f"old Esp32Camera* camera_ member remains: {path}")
        if '#include "esp_video.h"' not in text:
            raise SystemExit(f"MAX35 DVP source does not include current 78 esp_video.h: {path}")

    all_camera_text = "\n".join(read(path) for path in camera_sources)
    if "new EspVideo(video_config)" not in all_camera_text:
        raise SystemExit("MAX35 camera migration did not produce EspVideo(video_config)")
    if "EspVideo* camera_" not in all_camera_text and "EspVideo *camera_" not in all_camera_text:
        raise SystemExit("MAX35 camera migration did not produce an EspVideo camera_ member")

    print(
        "[OK] MAX35 DVP camera migrated to current 78 EspVideo "
        f"({patched_files} file(s), {migrated_member} member, {migrated_ctor} constructor)"
    )


def patch_max35_adc(board_dst: Path) -> None:
    """Redirect SpotPear's removed driver/adc.h API to IDF6 adc_oneshot."""
    shim = board_dst / "legacy_adc_compat.h"
    shim.write_text(
        r'''#pragma once
// SpotPear MAX35 legacy ADC compatibility for ESP-IDF 6.x.
#include <stdint.h>
#include "esp_adc/adc_oneshot.h"
#include "esp_err.h"

typedef adc_channel_t adc1_channel_t;
typedef adc_bitwidth_t adc_bits_width_t;
#ifndef ADC1_CHANNEL_0
#define ADC1_CHANNEL_0 ADC_CHANNEL_0
#define ADC1_CHANNEL_1 ADC_CHANNEL_1
#define ADC1_CHANNEL_2 ADC_CHANNEL_2
#define ADC1_CHANNEL_3 ADC_CHANNEL_3
#define ADC1_CHANNEL_4 ADC_CHANNEL_4
#define ADC1_CHANNEL_5 ADC_CHANNEL_5
#define ADC1_CHANNEL_6 ADC_CHANNEL_6
#define ADC1_CHANNEL_7 ADC_CHANNEL_7
#define ADC1_CHANNEL_8 ADC_CHANNEL_8
#define ADC1_CHANNEL_9 ADC_CHANNEL_9
#endif
#ifndef ADC_WIDTH_BIT_9
#define ADC_WIDTH_BIT_9  ADC_BITWIDTH_9
#define ADC_WIDTH_BIT_10 ADC_BITWIDTH_10
#define ADC_WIDTH_BIT_11 ADC_BITWIDTH_11
#define ADC_WIDTH_BIT_12 ADC_BITWIDTH_12
#endif
#ifndef ADC_ATTEN_DB_11
#define ADC_ATTEN_DB_11 ADC_ATTEN_DB_12
#endif

namespace max35_legacy_adc {
inline adc_oneshot_unit_handle_t& Unit() {
    static adc_oneshot_unit_handle_t handle = nullptr;
    return handle;
}
inline adc_bitwidth_t& Width() {
    static adc_bitwidth_t width = ADC_BITWIDTH_12;
    return width;
}
inline esp_err_t EnsureUnit() {
    if (Unit() != nullptr) return ESP_OK;
    adc_oneshot_unit_init_cfg_t cfg = {};
    cfg.unit_id = ADC_UNIT_1;
    cfg.ulp_mode = ADC_ULP_MODE_DISABLE;
    return adc_oneshot_new_unit(&cfg, &Unit());
}
}  // namespace max35_legacy_adc

static inline esp_err_t adc1_config_width(adc_bits_width_t width) {
    max35_legacy_adc::Width() = width;
    return max35_legacy_adc::EnsureUnit();
}
static inline esp_err_t adc1_config_channel_atten(adc1_channel_t channel, adc_atten_t atten) {
    esp_err_t err = max35_legacy_adc::EnsureUnit();
    if (err != ESP_OK) return err;
    adc_oneshot_chan_cfg_t cfg = {};
    cfg.atten = atten;
    cfg.bitwidth = max35_legacy_adc::Width();
    return adc_oneshot_config_channel(max35_legacy_adc::Unit(), channel, &cfg);
}
static inline int adc1_get_raw(adc1_channel_t channel) {
    if (max35_legacy_adc::EnsureUnit() != ESP_OK) return -1;
    int raw = 0;
    if (adc_oneshot_read(max35_legacy_adc::Unit(), channel, &raw) != ESP_OK) return -1;
    return raw;
}
''',
        encoding="utf-8",
    )

    changed = 0
    legacy_include = re.compile(
        r'#\s*include\s*[<"](?:driver/adc\.h|driver/deprecated/driver/adc\.h)[>"]'
    )
    for path in board_dst.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".h", ".hpp", ".c", ".cc", ".cpp"}:
            continue
        if path.name == shim.name:
            continue
        text = read(path)
        patched, count = legacy_include.subn('#include "legacy_adc_compat.h"', text)
        if count:
            write(path, patched)
            changed += count
            print(f"[patch] redirected legacy ADC include: {path} ({count})")

    if changed == 0:
        print("[adc] no legacy driver/adc.h include found; vendor board may already support IDF 6")

    board_text = "\n".join(
        read(path)
        for path in board_dst.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".h", ".hpp", ".c", ".cc", ".cpp"}
        and path.name != shim.name
    )
    if legacy_include.search(board_text):
        raise SystemExit("legacy driver/adc.h still present after MAX35 ADC compatibility patch")
    print("[OK] MAX35 legacy ADC calls are backed by adc_oneshot on IDF 6")


def patch_fixed_ota(upstream: Path) -> None:
    """Force the 4G product to use CONFIG_OTA_URL and ignore NVS ota_url overrides."""
    path = upstream / "main" / "ota.cc"
    text = read(path)
    signature = "std::string Ota::GetCheckVersionUrl()"
    start = text.find(signature)
    if start < 0:
        raise SystemExit("Current 78 ota.cc no longer contains Ota::GetCheckVersionUrl()")
    brace = text.find("{", start + len(signature))
    if brace < 0:
        raise SystemExit("Cannot locate GetCheckVersionUrl function body")

    depth = 0
    end = None
    for i in range(brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        raise SystemExit("Unbalanced braces in GetCheckVersionUrl function")

    replacement = (
        "std::string Ota::GetCheckVersionUrl() {\n"
        "    // MAX35 4G product policy: backend discovery is fixed at build time.\n"
        "    // Do not allow stale NVS wifi/ota_url values to override this endpoint.\n"
        "    return CONFIG_OTA_URL;\n"
        "}"
    )
    text = text[:start] + replacement + text[end:]
    write(path, text)
    print(f"[patch] OTA endpoint locked to CONFIG_OTA_URL ({FIXED_OTA_URL})")


def copy_overlay(product: Path, upstream: Path) -> None:
    src = product / "overlay" / "main" / "display" / "aurora_max35"
    dst = upstream / "main" / "display" / "aurora_max35"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print("[copy] AURORA display overlay ->", dst)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vendor", required=True)
    parser.add_argument("--upstream", required=True)
    parser.add_argument("--product", required=True)
    args = parser.parse_args()

    vendor = Path(args.vendor).resolve()
    upstream = Path(args.upstream).resolve()
    product = Path(args.product).resolve()

    vendor_board, vendor_symbol = locate_vendor_board(vendor)
    print("[vendor] MAX35 4G/ML307 hardware board:", vendor_board)

    board_dst = upstream / "main" / "boards" / PRODUCT_BOARD_DIR
    if board_dst.exists():
        shutil.rmtree(board_dst)
    board_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(vendor_board, board_dst)
    print("[copy] vendor board ->", board_dst)

    rewrite_vendor_board_symbols(board_dst, vendor_symbol)
    verify_ml307_board(board_dst)
    create_current_config(board_dst)
    patch_fixed_ota(upstream)
    copy_overlay(product, upstream)
    patch_kconfig(upstream)
    patch_cmake(upstream)
    patch_board_display(board_dst)
    patch_max35_camera(board_dst)
    patch_max35_adc(board_dst)
    verify_ml307_board(board_dst)

    # Intentionally no mcp_server.cc patch: native Xiaozhi camera/MCP stays intact.
    (upstream / ".max35_4g_vendor_board_path").write_text(
        str(vendor_board) + "\n", encoding="utf-8"
    )
    print("[done] MAX35 4G/ML307 imported; upstream Xiaozhi logic preserved")


if __name__ == "__main__":
    main()
