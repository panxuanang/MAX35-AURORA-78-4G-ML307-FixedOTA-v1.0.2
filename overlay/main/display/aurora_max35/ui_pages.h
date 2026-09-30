#pragma once

#include <cstdint>
#include <lvgl.h>

namespace aurora_max35 {

struct HomeUi {
    lv_obj_t* root = nullptr;
    lv_obj_t* brand = nullptr;
    lv_obj_t* clock = nullptr;
    lv_obj_t* date = nullptr;
    lv_obj_t* orb_outer = nullptr;
    lv_obj_t* orb_mid = nullptr;
    lv_obj_t* orb_core = nullptr;
    lv_obj_t* orb_text = nullptr;
    lv_obj_t* status = nullptr;
    lv_obj_t* hint = nullptr;
};

struct ChatUi {
    lv_obj_t* root = nullptr;
    lv_obj_t* title = nullptr;
    lv_obj_t* state = nullptr;
    lv_obj_t* user_box = nullptr;
    lv_obj_t* user = nullptr;
    lv_obj_t* answer_box = nullptr;
    lv_obj_t* answer = nullptr;
    lv_obj_t* footer = nullptr;
};

void BuildHomeUi(lv_obj_t* screen, HomeUi* ui);
void HomeUiSetClock(HomeUi* ui, const char* time_text, const char* date_text);
void HomeUiSetState(HomeUi* ui, const char* text, uint32_t color, const char* orb_text = "AI");

void BuildChatUi(lv_obj_t* screen, ChatUi* ui);
void ChatUiSetUser(ChatUi* ui, const char* text);
void ChatUiSetAnswer(ChatUi* ui, const char* text);
void ChatUiSetState(ChatUi* ui, const char* text, uint32_t color);
void ChatUiStopScroll(ChatUi* ui);
int64_t ChatUiStartReadableScroll(ChatUi* ui, int delay_ms, int ms_per_pixel);

}  // namespace aurora_max35
