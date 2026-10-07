import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
import telebot
from telebot import types


# =========================================================
# НАСТРОЙКИ
# =========================================================

TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
VENDORIA_TOKEN = os.getenv("VENDORIA_TOKEN")

VENDORIA_URL = "https://vendoria.amadeustech.dev"
SERVICE_ID = 500

# Категории Z Route: Redemption
CATEGORY_PASS = 1367
CATEGORY_VOUCHERS = 1368
CATEGORY_DIAMONDS = 1369

SUPPORT_USERNAME = "@Darkwolfan"

PORT = int(os.getenv("PORT", "10000"))


# =========================================================
# ПРОВЕРКА ТОКЕНОВ
# =========================================================

if not TELEGRAM_TOKEN:
    raise RuntimeError("❌ Не найдена переменная BOT_TOKEN")

if not VENDORIA_TOKEN:
    raise RuntimeError("❌ Не найдена переменная VENDORIA_TOKEN")


# =========================================================
# TELEGRAM
# =========================================================

bot = telebot.TeleBot(TELEGRAM_TOKEN)


# =========================================================
# VENDORIA
# =========================================================

HEADERS = {
    "Authorization": f"Shop {VENDORIA_TOKEN}",
    "Accept-Language": "ru",
    "Content-Type": "application/json",
}


def vendoria_get(endpoint, params=None):
    """GET-запрос к Vendoria."""
    try:
        response = requests.get(
            VENDORIA_URL + endpoint,
            headers=HEADERS,
            params=params,
            timeout=30,
        )

        print(
            f"Vendoria GET {endpoint} -> "
            f"{response.status_code}"
        )

        if response.status_code != 200:
            print("Vendoria error:", response.text)
            return None

        return response.json()

    except Exception as e:
        print("Vendoria GET exception:", e)
        return None


def get_categories():
    """Получает категории Z Route."""
    return vendoria_get(
        "/api/categories",
        {"serviceId": SERVICE_ID},
    )


def get_products():
    """Получает товары Z Route."""
    return vendoria_get(
        "/api/products",
        {"prices": "true"},
    )


def get_forms():
    """Получает формы доставки Z Route."""
    return vendoria_get(
        "/api/forms",
        {"serviceId": SERVICE_ID},
    )


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================================================

def money(value):
    """Красивый вывод цены."""
    try:
        number = float(value)

        if number.is_integer():
            return f"{int(number)}"

        return f"{number:.2f}".rstrip("0").rstrip(".")

    except Exception:
        return str(value)


def get_category_products(category_id):
    """
    Возвращает товары конкретной категории.
    Используем ID напрямую, поэтому ошибка
    'Категория не найдена' больше не нужна.
    """

    data = get_products()

    if not data:
        return []

    # Vendoria может вернуть список напрямую
    if isinstance(data, list):
        products = data

    # Или объект с products
    elif isinstance(data, dict):
        products = data.get("products", [])

    else:
        return []

    result = []

    for product in products:
        if not isinstance(product, dict):
            continue

        product_category = (
            product.get("categoryId")
            or product.get("category_id")
        )

        try:
            if int(product_category) == int(category_id):
                result.append(product)
        except Exception:
            continue

    return result


def product_name(product):
    return (
        product.get("name")
        or product.get("title")
        or product.get("productName")
        or f"Товар #{product.get('id', '?')}"
    )


def product_price(product):
    """
    Пытаемся получить цену из разных вариантов
    структуры Vendoria.
    """

    price = product.get("price")

    if price is not None:
        return price

    prices = product.get("prices")

    if isinstance(prices, dict):
        for key in ("price", "RUB", "USD", "usd"):
            if prices.get(key) is not None:
                return prices.get(key)

    if isinstance(prices, list) and prices:
        first = prices[0]

        if isinstance(first, dict):
            return (
                first.get("price")
                or first.get("amount")
            )

    return "—"


# =========================================================
# КЛАВИАТУРА ГЛАВНОГО МЕНЮ
# =========================================================

def main_menu():
    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    markup.row(
        "💎 Diamonds",
        "🎟 Vouchers",
    )

    markup.row(
        "⭐ Monthly Pass",
    )

    markup.row(
        "📦 Мои заказы",
        "💬 Поддержка",
    )

    return markup


# =========================================================
# КОМАНДА START
# =========================================================

@bot.message_handler(commands=["start"])
def start(message):

    text = (
        "🔥 <b>ARES SHOP</b>\n\n"
        "Магазин цифровых товаров "
        "для <b>Z Route: Redemption</b>.\n\n"
        "💎 Diamonds\n"
        "🎟 Vouchers\n"
        "⭐ Monthly Pass\n\n"
        "Выбери нужный раздел ниже."
    )

    bot.send_message(
        message.chat.id,
        text,
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# =========================================================
# ПОКАЗ КАТЕГОРИИ
# =========================================================

def show_category(message, category_id, title):

    bot.send_message(
        message.chat.id,
        "⏳ Загружаю товары..."
    )

    products = get_category_products(category_id)

    if not products:

        bot.send_message(
            message.chat.id,
            (
                "❌ Не удалось получить товары.\n\n"
                "Попробуй ещё раз через несколько секунд."
            ),
            reply_markup=main_menu(),
        )

        return

    markup = types.InlineKeyboardMarkup()

    for product in products:

        product_id = product.get("id")

        if product_id is None:
            continue

        name = product_name(product)
        price = product_price(product)

        button_text = f"{name} — {money(price)}"

        markup.add(
            types.InlineKeyboardButton(
                button_text,
                callback_data=f"product:{product_id}",
            )
        )

    bot.send_message(
        message.chat.id,
        f"<b>{title}</b>\n\nВыбери товар:",
        parse_mode="HTML",
        reply_markup=markup,
    )


# =========================================================
# КНОПКИ КАТЕГОРИЙ
# =========================================================

@bot.message_handler(
    func=lambda message: message.text == "💎 Diamonds"
)
def diamonds(message):

    show_category(
        message,
        CATEGORY_DIAMONDS,
        "💎 Diamonds",
    )


@bot.message_handler(
    func=lambda message: message.text == "🎟 Vouchers"
)
def vouchers(message):

    show_category(
        message,
        CATEGORY_VOUCHERS,
        "🎟 Vouchers",
    )


@bot.message_handler(
    func=lambda message: message.text == "⭐ Monthly Pass"
)
def monthly_pass(message):

    show_category(
        message,
        CATEGORY_PASS,
        "⭐ Monthly Pass",
    )


# =========================================================
# ВЫБОР ТОВАРА
# =========================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("product:")
)
def product_selected(call):

    try:
        product_id = int(
            call.data.split(":")[1]
        )
    except Exception:

        bot.answer_callback_query(
            call.id,
            "Ошибка товара",
            show_alert=True,
        )

        return

    data = get_products()

    if not data:

        bot.answer_callback_query(
            call.id,
            "Не удалось получить товар",
            show_alert=True,
        )

        return

    if isinstance(data, list):
        products = data
    elif isinstance(data, dict):
        products = data.get("products", [])
    else:
        products = []

    selected = None

    for product in products:

        if not isinstance(product, dict):
            continue

        try:
            if int(product.get("id")) == product_id:
                selected = product
                break
        except Exception:
            continue

    if not selected:

        bot.answer_callback_query(
            call.id,
            "Товар не найден",
            show_alert=True,
        )

        return

    name = product_name(selected)
    price = product_price(selected)

    text = (
        f"🛒 <b>{name}</b>\n\n"
        f"💰 Цена поставщика: <b>{money(price)}</b>\n\n"
        "Для продолжения напиши в поддержку "
        "и укажи название товара."
    )

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "💬 Поддержка",
            url="https://t.me/Darkwolfan",
        )
    )

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup,
    )

    bot.answer_callback_query(call.id)


# =========================================================
# МОИ ЗАКАЗЫ
# =========================================================

@bot.message_handler(
    func=lambda message: message.text == "📦 Мои заказы"
)
def my_orders(message):

    bot.send_message(
        message.chat.id,
        (
            "📦 <b>Мои заказы</b>\n\n"
            "Раздел пока находится в разработке.\n\n"
            "После подключения оплаты здесь "
            "будет отображаться история заказов."
        ),
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


# =========================================================
# ПОДДЕРЖКА
# =========================================================

@bot.message_handler(
    func=lambda message: message.text == "💬 Поддержка"
)
def support(message):

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "💬 Написать в поддержку",
            url="https://t.me/Darkwolfan",
        )
    )

    bot.send_message(
        message.chat.id,
        (
            "💬 <b>Поддержка ARES SHOP</b>\n\n"
            "Если возник вопрос по товару или заказу, "
            "напиши нашей поддержке."
        ),
        parse_mode="HTML",
        reply_markup=markup,
    )


# =========================================================
# ЛЮБОЙ ДРУГОЙ ТЕКСТ
# =========================================================

@bot.message_handler(
    func=lambda message: True
)
def other_message(message):

    bot.send_message(
        message.chat.id,
        (
            "Выбери нужный раздел в меню 👇"
        ),
        reply_markup=main_menu(),
    )


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)

        self.send_header(
            "Content-type",
            "text/plain; charset=utf-8"
        )

        self.end_headers()

        self.wfile.write(
            b"ARES SHOP is running!"
        )

    def log_message(self, format, *args):
        return


def start_web_server():

    server = HTTPServer(
        ("0.0.0.0", PORT),
        HealthHandler,
    )

    print(
        f"🌐 Render server started on port {PORT}"
    )

    server.serve_forever()


# =========================================================
# ЗАПУСК
# =========================================================

if __name__ == "__main__":

    print("🔥 ARES SHOP запускается...")

    web_thread = threading.Thread(
        target=start_web_server,
        daemon=True,
    )

    web_thread.start()

    print("🤖 Telegram bot запускается...")

    bot.infinity_polling(
        skip_pending=True,
        timeout=30,
        long_polling_timeout=30,
    )
