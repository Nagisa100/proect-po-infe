import telebot
import json
import logging
import os
import sys
from datetime import datetime
from telebot import types

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from config import BOT_TOKEN
from bot.schedule import SCHEDULE_DATA

bot = telebot.TeleBot(BOT_TOKEN)

json_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'stops.json')
with open(json_path, 'r', encoding='utf-8') as f:
    STOPS_DATABASE = json.load(f)

all_stops = list(STOPS_DATABASE.keys())
all_stops.sort()
stop_names_by_index = {idx: name for idx, name in enumerate(all_stops)}
index_by_stop_name = {name: idx for idx, name in enumerate(all_stops)}

def get_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton('Выбрать троллейбус'),
        types.KeyboardButton('Найти остановку'),
        types.KeyboardButton('Все остановки'),
        types.KeyboardButton('Помощь')
    )
    return markup

def get_routes_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("10", callback_data="route_10"),
        types.InlineKeyboardButton("12", callback_data="route_12"),
        types.InlineKeyboardButton("16", callback_data="route_16"),
        types.InlineKeyboardButton("19", callback_data="route_19")
    )
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    user = message.from_user
    route_stats = {"10": 0, "12": 0, "16": 0, "19": 0}
    for routes in STOPS_DATABASE.values():
        for r in routes:
            if r in route_stats:
                route_stats[r] += 1
    stats_text = "\n".join([f"  {r}: {c} остановок" for r, c in route_stats.items()])
    text = f"Привет, {user.first_name}!\n\nЯ бот расписания троллейбусов Челябинска\n\nДоступные маршруты:\n{stats_text}\n\nВсего в базе: {len(STOPS_DATABASE)} остановок"
    bot.send_message(message.chat.id, text, reply_markup=get_main_keyboard())

@bot.message_handler(commands=['help'])
def send_help(message):
    text = "Помощь\n\nКак пользоваться:\n1. Нажми 'Выбрать троллейбус' — выбери маршрут\n2. Выбери остановку\n3. Получи расписание\n\nИли нажми 'Найти остановку' — введи название"
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda message: message.text == 'Найти остановку')
def find_stop(message):
    msg = bot.send_message(message.chat.id, "Введите название остановки:")
    bot.register_next_step_handler(msg, process_stop_search)

def process_stop_search(message):
    query = message.text.strip().lower()
    if len(query) < 2:
        bot.send_message(message.chat.id, "Введите хотя бы 2 символа")
        return
    results = [s for s in STOPS_DATABASE.keys() if query in s.lower()]
    if not results:
        bot.send_message(message.chat.id, f"Остановка '{message.text}' не найдена", reply_markup=get_main_keyboard())
        return
    results.sort()
    markup = types.InlineKeyboardMarkup()
    for stop_name in results[:15]:
        idx = index_by_stop_name[stop_name]
        routes = STOPS_DATABASE[stop_name]
        markup.add(types.InlineKeyboardButton(f"{stop_name[:30]} ({', '.join(routes)})", callback_data=f"stop_{idx}"))
    bot.send_message(message.chat.id, f"Найдено остановок: {len(results)}", reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == 'Все остановки')
def all_stops(message):
    stops_list = list(STOPS_DATABASE.keys())
    stops_list.sort()
    text = "Все остановки:\n\n"
    for i, stop in enumerate(stops_list[:20]):
        routes = STOPS_DATABASE[stop]
        text += f"{i+1}. {stop[:35]} — {', '.join(routes)}\n"
    if len(stops_list) > 20:
        text += f"\n... и ещё {len(stops_list) - 20} остановок"
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda message: message.text == 'Выбрать троллейбус')
def choose_trolley(message):
    bot.send_message(message.chat.id, "Выберите троллейбус:", reply_markup=get_routes_keyboard())

def show_stops_for_route(message, route_num):
    stops = [s for s, r in STOPS_DATABASE.items() if route_num in r]
    stops.sort()
    if not stops:
        bot.send_message(message.chat.id, f"Для маршрута {route_num} нет остановок")
        return
    page_size = 15
    pages = [stops[i:i+page_size] for i in range(0, len(stops), page_size)]
    text = f"Троллейбус {route_num}\nВсего остановок: {len(stops)}\n\n"
    markup = types.InlineKeyboardMarkup()
    for i, stop_name in enumerate(pages[0]):
        idx = index_by_stop_name[stop_name]
        display = stop_name[:20] + "..." if len(stop_name) > 20 else stop_name
        markup.add(types.InlineKeyboardButton(f"{i+1}. {display}", callback_data=f"stop_{idx}"))
    if len(pages) > 1:
        markup.add(types.InlineKeyboardButton("Далее", callback_data=f"route_page_{route_num}_1"))
    bot.send_message(message.chat.id, text, reply_markup=markup)

def show_stops_page(message, route_num, page):
    stops = [s for s, r in STOPS_DATABASE.items() if route_num in r]
    stops.sort()
    page_size = 15
    pages = [stops[i:i+page_size] for i in range(0, len(stops), page_size)]
    if page >= len(pages):
        return
    text = f"Троллейбус {route_num} (стр. {page+1}/{len(pages)})\nВсего: {len(stops)}\n\n"
    markup = types.InlineKeyboardMarkup()
    start_idx = page * page_size
    for i, stop_name in enumerate(pages[page]):
        idx = index_by_stop_name[stop_name]
        display = stop_name[:20] + "..." if len(stop_name) > 20 else stop_name
        markup.add(types.InlineKeyboardButton(f"{start_idx + i + 1}. {display}", callback_data=f"stop_{idx}"))
    nav_row = []
    if page > 0:
        nav_row.append(types.InlineKeyboardButton("Назад", callback_data=f"route_page_{route_num}_{page-1}"))
    if page < len(pages) - 1:
        nav_row.append(types.InlineKeyboardButton("Далее", callback_data=f"route_page_{route_num}_{page+1}"))
    if nav_row:
        markup.row(*nav_row)
    bot.edit_message_text(text, chat_id=message.chat.id, message_id=message.message_id, reply_markup=markup)

def show_schedule(message, stop_name):
    routes = STOPS_DATABASE.get(stop_name, [])
    if not routes:
        bot.send_message(message.chat.id, f"Для остановки '{stop_name}' нет данных о маршрутах")
        return
    status_msg = bot.send_message(message.chat.id, f"Загружаю расписание для {stop_name}...")
    schedule = {}
    for route in routes:
        if route in SCHEDULE_DATA and stop_name in SCHEDULE_DATA[route]:
            schedule[route] = SCHEDULE_DATA[route][stop_name]
    if not schedule:
        bot.edit_message_text(f"Нет расписания для {stop_name}\n\nДоступные маршруты: {', '.join(routes)}", chat_id=message.chat.id, message_id=status_msg.message_id)
        return
    current_time = datetime.now().strftime("%H:%M")
    current_minutes = int(current_time[:2]) * 60 + int(current_time[3:])
    response = f"{stop_name}\nТекущее время: {current_time}\nМаршруты: {', '.join(routes)}\n\n"
    for route in sorted(schedule.keys()):
        times = schedule[route]
        upcoming = [t for t in times if int(t[:2])*60+int(t[3:]) >= current_minutes]
        response += f"Троллейбус {route}:\n"
        if upcoming:
            next_times = upcoming[:5]
            response += f"Ближайшие: {', '.join(next_times)}"
            if len(upcoming) > 5:
                response += f" и ещё {len(upcoming) - 5}"
            first_min = int(upcoming[0][:2])*60 + int(upcoming[0][3:])
            wait = first_min - current_minutes
            if wait > 0:
                h = wait // 60
                m = wait % 60
                response += f"\n   Первый через {h} ч {m} мин" if h > 0 else f"\n   Первый через {m} мин"
        else:
            response += f"На сегодня рейсов больше нет\nПервый завтра: {times[0]}" if times else "Нет данных"
        response += "\n\n"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Обновить", callback_data=f"refresh_{index_by_stop_name[stop_name]}"))
    bot.edit_message_text(response, chat_id=message.chat.id, message_id=status_msg.message_id, reply_markup=markup)

@bot.message_handler(content_types=['sticker'])
def handle_sticker(message):
    bot.send_message(message.chat.id, "Фигня")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    data = call.data
    if data.startswith("route_"):
        if "_page_" in data:
            parts = data.split("_")
            show_stops_page(call.message, parts[2], int(parts[3]))
        else:
            show_stops_for_route(call.message, data.split("_")[1])
    elif data.startswith("stop_"):
        show_schedule(call.message, stop_names_by_index[int(data.split("_")[1])])
    elif data.startswith("refresh_"):
        show_schedule(call.message, stop_names_by_index[int(data.split("_")[1])])
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: True)
def handle_other(message):
    if message.text == 'Помощь':
        send_help(message)
    else:
        bot.send_message(message.chat.id, "Я не понял команду. Используй кнопки внизу", reply_markup=get_main_keyboard())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(f"Загружено остановок: {len(STOPS_DATABASE)}")
    bot.polling(none_stop=True)