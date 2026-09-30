#include "ui_pages.h"

#include <algorithm>
#include <esp_timer.h>

namespace aurora_max35 {
namespace {
constexpr uint32_t kBgTop = 0x07101C;
constexpr uint32_t kBgBottom = 0x0A2532;
constexpr uint32_t kText = 0xEAF7FF;
constexpr uint32_t kMuted = 0x8BA4B7;
constexpr uint32_t kPanel = 0x0E2230;
constexpr uint32_t kPanel2 = 0x102B39;
constexpr uint32_t kLine = 0x1D4558;
constexpr uint32_t kAccent = 0x46D7C6;

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
}  // namespace

void BuildChatUi(lv_obj_t* screen, ChatUi* ui) {
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

    ui->title = Label(ui->root, "DIALOG", 16, 10, 120, kMuted);
    ui->state = Label(ui->root, "●  待命", 210, 10, 252, kAccent, LV_TEXT_ALIGN_RIGHT);

    ui->user_box = lv_obj_create(ui->root);
    lv_obj_set_pos(ui->user_box, 14, 38);
    lv_obj_set_size(ui->user_box, 452, 48);
    lv_obj_set_style_radius(ui->user_box, 14, 0);
    lv_obj_set_style_bg_color(ui->user_box, lv_color_hex(kPanel2), 0);
    lv_obj_set_style_bg_opa(ui->user_box, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(ui->user_box, lv_color_hex(kLine), 0);
    lv_obj_set_style_border_width(ui->user_box, 1, 0);
    lv_obj_set_style_pad_all(ui->user_box, 10, 0);
    lv_obj_remove_flag(ui->user_box, LV_OBJ_FLAG_SCROLLABLE);

    ui->user = lv_label_create(ui->user_box);
    lv_obj_set_pos(ui->user, 0, 0);
    lv_obj_set_width(ui->user, 430);
    lv_label_set_long_mode(ui->user, LV_LABEL_LONG_DOT);
    lv_label_set_text(ui->user, "你：正在聆听…");
    lv_obj_set_style_text_color(ui->user, lv_color_hex(kMuted), 0);

    ui->answer_box = lv_obj_create(ui->root);
    lv_obj_set_pos(ui->answer_box, 14, 96);
    lv_obj_set_size(ui->answer_box, 452, 188);
    lv_obj_set_style_radius(ui->answer_box, 18, 0);
    lv_obj_set_style_bg_color(ui->answer_box, lv_color_hex(kPanel), 0);
    lv_obj_set_style_bg_opa(ui->answer_box, LV_OPA_COVER, 0);
    lv_obj_set_style_border_color(ui->answer_box, lv_color_hex(kLine), 0);
    lv_obj_set_style_border_width(ui->answer_box, 1, 0);
    lv_obj_set_style_shadow_color(ui->answer_box, lv_color_hex(kAccent), 0);
    lv_obj_set_style_shadow_width(ui->answer_box, 12, 0);
    lv_obj_set_style_shadow_opa(ui->answer_box, LV_OPA_10, 0);
    lv_obj_set_style_pad_all(ui->answer_box, 14, 0);
    lv_obj_set_style_clip_corner(ui->answer_box, true, 0);
    lv_obj_set_scrollbar_mode(ui->answer_box, LV_SCROLLBAR_MODE_OFF);
    lv_obj_remove_flag(ui->answer_box, LV_OBJ_FLAG_SCROLLABLE);

    ui->answer = lv_label_create(ui->answer_box);
    lv_obj_set_pos(ui->answer, 0, 0);
    lv_obj_set_width(ui->answer, 422);
    lv_label_set_long_mode(ui->answer, LV_LABEL_LONG_WRAP);
    lv_label_set_text(ui->answer, "你好，我是小智。\n你说话时，我会自动切换到这里。长回答会缓慢滚动，直到内容显示完整。");
    lv_obj_set_style_text_color(ui->answer, lv_color_hex(kText), 0);
    lv_obj_set_style_text_line_space(ui->answer, 7, 0);

    ui->footer = Label(ui->root, "MAX35 4G  •  ML307", 16, 296, 448, kMuted, LV_TEXT_ALIGN_CENTER);
}

void ChatUiSetUser(ChatUi* ui, const char* text) {
    if (!ui || !ui->user) return;
    lv_label_set_text_fmt(ui->user, "你：%s", text ? text : "");
}

void ChatUiStopScroll(ChatUi* ui) {
    if (!ui || !ui->answer) return;
    lv_anim_delete(ui->answer, nullptr);
    lv_obj_set_y(ui->answer, 0);
}

void ChatUiSetAnswer(ChatUi* ui, const char* text) {
    if (!ui || !ui->answer) return;
    ChatUiStopScroll(ui);
    lv_label_set_text(ui->answer, text ? text : "");
    lv_obj_set_y(ui->answer, 0);
}

int64_t ChatUiStartReadableScroll(ChatUi* ui, int delay_ms, int ms_per_pixel) {
    if (!ui || !ui->answer || !ui->answer_box) return 0;
    lv_obj_update_layout(ui->answer);
    const int visible = lv_obj_get_height(ui->answer_box) - 28;
    const int content_height = lv_obj_get_height(ui->answer);
    if (content_height <= visible) return 0;

    const int distance = content_height - visible;
    const int duration = std::max(2600, distance * ms_per_pixel);
    lv_anim_t a;
    lv_anim_init(&a);
    lv_anim_set_var(&a, ui->answer);
    lv_anim_set_values(&a, 0, -distance);
    lv_anim_set_delay(&a, delay_ms);
    lv_anim_set_duration(&a, duration);
    lv_anim_set_exec_cb(&a, [](void* obj, int32_t value) {
        lv_obj_set_y(static_cast<lv_obj_t*>(obj), value);
    });
    lv_anim_start(&a);

    return esp_timer_get_time() + static_cast<int64_t>(delay_ms + duration) * 1000LL;
}

void ChatUiSetState(ChatUi* ui, const char* text, uint32_t color) {
    if (!ui || !ui->state) return;
    lv_label_set_text_fmt(ui->state, "●  %s", text ? text : "");
    lv_obj_set_style_text_color(ui->state, lv_color_hex(color), 0);
}

}  // namespace aurora_max35
