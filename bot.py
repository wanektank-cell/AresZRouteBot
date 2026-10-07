# AresZRouteBot
# ARES SHOP — Z Route: Redemption

import os
import threading
import requests
import telebot
from telebot import types
from http.server import BaseHTTPRequestHandler, HTTPServer


# =========================
# SETTINGS
# =========================

TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
VENDORIA_TOKEN = os.getenv("VENDORIA_TOKEN")

VENDORIA_URL = "https://vendoria.amadeustech.dev"
SERVICE_ID = 500

PORT = int(os.getenv("PORT", "10000"))

bot = telebot.TeleBot(TELEGRAM_TOKEN)

HEADERS = {
    "Authorization": f"Shop {VENDORIA_TOKEN}",
    "Accept-Language": "ru"
}


# =========================
# RENDER HEALTH SERVER
# =========================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ARES SHOP is running!")

    def log_message(self, format, *args):
        return


def start_web_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    print(f"🌐 Render server started on port {PORT}")
    server.serve_forever()


# =========================
# VENDORIA
# =========================

def get_categories():

    url = f"{VENDORIA_URL}/api/categories"

    response = requests.get(
        url,
        headers=HEADERS,
        params={"serviceId": SERVICE_ID},
        timeout=20
    )

    response.raise_for_status()

    return response.json()


def get_products():

    url = f"{VENDORIA_URL}/api/products"

    response = requests.get(
        url,
        headers=HEADERS,
        params={"prices": "true"},
        timeout=20
    )

    response.raise_for_status()

    products = response.json()

    categories = get_categories()

    category_ids = {
        category["id"]
        for category in categories
    }

    return [
        product
        for product in products
        if product.get("categoryId") in category_ids
    ]


def get_forms():

    url = f"{VENDORIA_URL}/api/forms"

    response = requests.get(
        url,
        headers=HEADERS,
        params={"serviceId": SERVICE_ID},
        timeout=20
    )

    response.raise_for_status()

    return response.json()


# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(message):

    keyboard = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )
    
elif message.text == "💎 Diamonds":
    show_category(message, "Алмазы")
elif message.text == "🎟 Vouchers":
    show_category(message, "Ваучеры")
elif message.text == "⭐ Monthly Pass":
    show_category(message, "Пропуск")
    btn4 = types.KeyboardButton("📦 Мои заказы")
    btn5 = types.KeyboardButton("💬 Поддержка")

    keyboard.add(btn1, btn2)
    keyboard.add(btn3)
    keyboard.add(btn4, btn5)

    bot.send_message(
        message.chat.id,
        "🔥 ARES SHOP\n\n"
        "Z Route: Redemption\n\n"
        "Выберите раздел:",
        reply_markup=keyboard
    )


# =========================
# CATALOG
# =========================

def show_category(message, category_name):

    try:

        categories = get_categories()

        category = next(
            (
                c for c in categories
                if c["name"].lower() == category_name.lower()
            ),
            None
        )

        if not category:

            names = "\n".join(
                f"• {c.get('name')} — ID {c.get('id')}"
                for c in categories
            )

            bot.send_message(
                message.chat.id,
                "❌ Категория не найдена.\n\n"
                "Вот что реально отдаёт Vendoria:\n\n"
                + names
            )

            return

        products = get_products()

        category_products = [
            p for p in products
            if p.get("categoryId") == category["id"]
        ]

        if not category_products:

            bot.send_message(
                message.chat.id,
                "❌ В этой категории пока нет товаров."
            )

            return

        text = (
            f"🔥 ARES SHOP\n\n"
            f"{category_name}\n\n"
        )

        for product in category_products:

            prices = product.get("prices", {})

            if not prices:
                continue

            price_usd = list(prices.values())[0]

            text += (
                f"• {product['name']}\n"
                f"  Цена поставщика: ${price_usd:.2f}\n\n"
            )

        bot.send_message(
            message.chat.id,
            text
        )

    except Exception as e:

        print("VENDORIA ERROR:", e)

        bot.send_message(
            message.chat.id,
            "⚠️ Не удалось загрузить каталог.\n"
            "Попробуйте ещё раз через несколько секунд."
        )


# =========================
# MENU
# =========================

@bot.message_handler(func=lambda message: True)
def menu(message):

    if message.text == "💎 Diamonds":

        show_category(
            message,
            "Diamonds"
        )

    elif message.text == "🎟 Vouchers":

        show_category(
            message,
            "Vouchers"
        )

    elif message.text == "⭐ Monthly Pass":

        show_category(
            message,
            "Pass"
        )

    elif message.text == "📦 Мои заказы":

        bot.send_message(
            message.chat.id,
            "📦 Раздел заказов пока находится в разработке."
        )

    elif message.text == "💬 Поддержка":

        bot.send_message(
            message.chat.id,
            "💬 Поддержка ARES SHOP\n\n"
            "Если возникла проблема с заказом — "
            "напишите сюда: @Darkwolfan"
        )


# =========================
# RUN
# =========================

print("🔥 ARES SHOP запускается...")

# Запускаем HTTP-сервер для Render
web_thread = threading.Thread(
    target=start_web_server,
    daemon=True
)

web_thread.start()

# Запускаем Telegram-бота
bot.infinity_polling()
