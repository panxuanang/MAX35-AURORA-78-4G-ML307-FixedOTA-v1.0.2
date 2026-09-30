#include "ui_pages.h"

namespace aurora_max35 {
namespace {
constexpr uint32_t kBgTop = 0x07101C;
constexpr uint32_t kBgBottom = 0x0A2532;
constexpr uint32_t kText = 0xEAF7FF;
constexpr uint32_t kMuted = 0x8BA4B7;
constexpr uint32_t kLine = 0x17384A;
constexpr uint32_t kIdle = 0x46D7C6;

lv_obj_t* Label(lv_obj_t* parent, const char* text, int x, int y, int w,
                uint32_t color, lv_text_align_t align = LV_TEXT_ALIGN_LEFT) {
    auto* o = lv_label_create(parent);
    lv_label_set_text(o, text);
    lv_obj_set_pos(o, x, y);
    lv_obj_set_width(o, w);
    lv_obj_set_style_text_color(o, lv_color_hex(color), 0);
    lv_obj_set_style_text_align(o, align, 0);
    return o;
}

lv_obj_t* Ring(lv_obj_t* parent, int size, uint32_t border, uint32_t fill, lv_opa_t fill_opa) {
    auto* o = lv_obj_create(parent);
    lv_obj_set_size(o, size, size);
    lv_obj_set_style_radius(o, LV_RADIUS_CIRCLE, 0);
    lv_obj_set_style_bg_color(o, lv_color_hex(fill), 0);
    lv_obj_set_style_bg_opa(o, fill_opa, 0);
    lv_obj_set_style_border_color(o, lv_color_hex(border), 0);
    lv_obj_set_style_border_width(o, 2, 0);
    lv_obj_set_style_shadow_color(o, lv_color_hex(border), 0);
    lv_obj_set_style_shadow_width(o, 18, 0);
    lv_obj_set_style_shadow_opa(o, LV_OPA_20, 0);
    lv_obj_remove_flag(o, LV_OBJ_FLAG_SCROLLABLE);
    return o;
}
}  // namespace

void BuildHomeUi(lv_obj_t* screen, HomeUi* ui) {
    ui->root = lv_obj_create(screen);
    lv_obj_set_pos(ui->root, 0, 0);
    lv_obj_set_size(ui->root, 480, 320);
    lv_obj_set_style_radius(ui->root, 0, 0);
    lv_obj_set_style_border_width(ui->root, 0, 0);
    lv_obj_set_style_pad_all(ui->root, 0, 0);
    lv_obj_set_style_bg_color(ui->root, lv_color_hex(kBgTop), 0);
    lv_obj_set_style_bg_grad_color(ui->root, lv_color_hex(kBgBottom), 0);
    lv_obj_set_style_bg_grad_dir(ui->root, LV_GRAD_DIR_VER, 0);
    lv_obj_remove_flag(ui->root, LV_OBJ_FLAG_SCROLLABLE);

    ui->brand = Label(ui->root, "XIAOZHI // MAX35 4G", 18, 14, 220, kMuted);
    ui->clock = Label(ui->root, "--:--", 300, 8, 160, kText, LV_TEXT_ALIGN_RIGHT);
    lv_obj_set_style_text_font(ui->clock, &lv_font_montserrat_48, 0);
    ui->date = Label(ui->root, "时间同步中", 292, 61, 168, kMuted, LV_TEXT_ALIGN_RIGHT);

    auto* line = lv_obj_create(ui->root);
    lv_obj_set_pos(line, 18, 86);
    lv_obj_set_size(line, 444, 1);
    lv_obj_set_style_border_width(line, 0, 0);
    lv_obj_set_style_bg_color(line, lv_color_hex(kLine), 0);
    lv_obj_set_style_bg_opa(line, LV_OPA_COVER, 0);
    lv_obj_remove_flag(line, LV_OBJ_FLAG_SCROLLABLE);

    ui->orb_outer = Ring(ui->root, 146, kIdle, 0x0B2430, LV_OPA_50);
    lv_obj_set_pos(ui->orb_outer, 167, 100);

    ui->orb_mid = Ring(ui->root, 110, kIdle, 0x0A3040, LV_OPA_50);
    lv_obj_set_pos(ui->orb_mid, 185, 118);

    ui->orb_core = Ring(ui->root, 78, kIdle, 0x123F4B, LV_OPA_COVER);
    lv_obj_set_pos(ui->orb_core, 201, 134);

    ui->orb_text = Label(ui->orb_core, "AI", 0, 12, 74, kText, LV_TEXT_ALIGN_CENTER);
    lv_obj_set_style_text_font(ui->orb_text, &lv_font_montserrat_48, 0);

    ui->status = Label(ui->root, "小智待命中", 20, 258, 440, kText, LV_TEXT_ALIGN_CENTER);
    ui->hint = Label(ui->root, "说「你好小智」开始对话", 20, 290, 440, kMuted, LV_TEXT_ALIGN_CENTER);
}

void HomeUiSetClock(HomeUi* ui, const char* time_text, const char* date_text) {
    if (!ui) return;
    if (ui->clock) lv_label_set_text(ui->clock, time_text ? time_text : "--:--");
    if (ui->date) lv_label_set_text(ui->date, date_text ? date_text : "");
}

void HomeUiSetState(HomeUi* ui, const char* text, uint32_t color, const char* orb_text) {
    if (!ui) return;
    if (ui->status) {
        lv_label_set_text(ui->status, text ? text : "小智待命中");
        lv_obj_set_style_text_color(ui->status, lv_color_hex(color), 0);
    }
    lv_obj_t* rings[] = {ui->orb_outer, ui->orb_mid, ui->orb_core};
    for (auto* o : rings) {
        if (!o) continue;
        lv_obj_set_style_border_color(o, lv_color_hex(color), 0);
        lv_obj_set_style_shadow_color(o, lv_color_hex(color), 0);
    }
    if (ui->orb_core) lv_obj_set_style_bg_color(ui->orb_core, lv_color_hex(color), 0);
    if (ui->orb_text) lv_label_set_text(ui->orb_text, orb_text ? orb_text : "AI");
}

}  // namespace aurora_max35
