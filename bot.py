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

PORT = int(os.getenv("PORT", "10000"))

SUPPORT_USERNAME = "@Darkwolfan"

# Курс USD/RUB для предварительного расчёта
USD_RUB = 85.5


# =========================================================
# КАТЕГОРИИ Z ROUTE
# =========================================================

CATEGORY_PASS = 1367
CATEGORY_VOUCHERS = 1368
CATEGORY_DIAMONDS = 1369


# =========================================================
# ЦЕНЫ ARES SHOP
# =========================================================
#
# Здесь цены уже учитывают цены в самой игре.
#
# Официальные цены игры, которые мы используем:
#
# 99      = 99 ₽
# 499     = 449 ₽
# 999     = 899 ₽
# 1999    = 1790 ₽
# 4999    = 4490 ₽
# 9999    = 8990 ₽
#
# Цены ARES SHOP:
#
# 99      = не продаём
# 499     = не продаём
# 999     = 889 ₽
# 1999    = 1769 ₽
# 4999    = 4449 ₽
# 9999    = 8899 ₽
#
# None означает, что товар НЕ показывается.
# =========================================================

RETAIL_PRICES = {

    # -------------------------
    # VOUCHERS
    # -------------------------

    "99": None,
    "499": None,

    "999": 889,

    "1,999": 1769,
    "1999": 1769,

    "4,999": 4449,
    "4999": 4449,

    "9,999": 8899,
    "9999": 8899,
}


# =========================================================
# ПРОВЕРКА ПЕРЕМЕННЫХ
# =========================================================

if not TELEGRAM_TOKEN:
    raise RuntimeError(
        "❌ Не найдена переменная BOT_TOKEN"
    )

if not VENDORIA_TOKEN:
    raise RuntimeError(
        "❌ Не найдена переменная VENDORIA_TOKEN"
    )


# =========================================================
# TELEGRAM BOT
# =========================================================

bot = telebot.TeleBot(TELEGRAM_TOKEN)


# =========================================================
# VENDORIA HEADERS
# =========================================================

HEADERS = {
    "Authorization": f"Shop {VENDORIA_TOKEN}",
    "Accept-Language": "ru",
}


# =========================================================
# VENDORIA GET
# =========================================================

def vendoria_get(endpoint, params=None):

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

            print(
                "Vendoria error:",
                response.text
            )

            return None

        return response.json()

    except Exception as e:

        print(
            "Vendoria exception:",
            e
        )

        return None


# =========================================================
# ПОЛУЧИТЬ ВСЕ ТОВАРЫ
# =========================================================

def get_products():

    return vendoria_get(
        "/api/products",
        {
            "prices": "true"
        }
    )


# =========================================================
# НАЗВАНИЕ ТОВАРА
# =========================================================

def product_name(product):

    return (
        product.get("name")
        or product.get("title")
        or product.get("productName")
        or f"Товар #{product.get('id', '?')}"
    )


# =========================================================
# РАЗБОР ЦЕНЫ
# =========================================================

def extract_price(value):

    if value is None:
        return None

    # Если это число
    if isinstance(value, (int, float)):

        return float(value)

    # Если это строка
    if isinstance(value, str):

        cleaned = (
            value
            .replace("$", "")
            .replace("USD", "")
            .replace("usd", "")
            .replace(",", ".")
            .strip()
        )

        try:

            return float(cleaned)

        except Exception:

            return None

    # Если словарь
    if isinstance(value, dict):

        possible_keys = [
            "price",
            "amount",
            "value",
            "USD",
            "usd",
            "cost",
        ]

        for key in possible_keys:

            if key in value:

                result = extract_price(
                    value[key]
                )

                if result is not None:
                    return result

        return None

    # Если список
    if isinstance(value, list):

        for item in value:

            result = extract_price(item)

            if result is not None:
                return result

    return None


# =========================================================
# ЦЕНА ПОСТАВЩИКА
# =========================================================

def product_supplier_price(product):

    possible_fields = [

        product.get("price"),

        product.get("prices"),

        product.get("cost"),

        product.get("amount"),

    ]

    for field in possible_fields:

        price = extract_price(field)

        if price is not None:

            return price

    return None


# =========================================================
# ЦЕНА ARES SHOP
# =========================================================

def get_retail_price(
    name,
    supplier_price=None
):

    name_lower = name.lower()

    # -----------------------------------------------------
    # Сначала проверяем вручную заданные цены.
    # Это особенно важно для Vouchers.
    # -----------------------------------------------------

    for key, price in RETAIL_PRICES.items():

        if key.lower() in name_lower:

            return price

    # -----------------------------------------------------
    # Для остальных товаров пока используем
    # предварительный автоматический расчёт.
    #
    # В дальнейшем заменим на реальные цены игры.
    # -----------------------------------------------------

    if supplier_price is not None:

        rub = supplier_price * USD_RUB

        retail = rub * 1.10

        return int(
            round(retail / 10) * 10
        )

    return None


# =========================================================
# ТОВАРЫ КАТЕГОРИИ
# =========================================================

def get_category_products(category_id):

    data = get_products()

    if not data:

        return []

    # Vendoria может вернуть список
    if isinstance(data, list):

        products = data

    # Или объект с products
    elif isinstance(data, dict):

        products = data.get(
            "products",
            []
        )

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

            if int(product_category) == int(
                category_id
            ):

                result.append(product)

        except Exception:

            continue

    return result


# =========================================================
# ГЛАВНОЕ МЕНЮ
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
# /START
# =========================================================

@bot.message_handler(
    commands=["start"]
)
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

def show_category(
    message,
    category_id,
    title
):

    bot.send_message(
        message.chat.id,
        "⏳ Загружаю товары..."
    )

    products = get_category_products(
        category_id
    )

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

    visible_count = 0

    for product in products:

        product_id = product.get("id")

        if product_id is None:
            continue

        name = product_name(product)

        supplier_price = (
            product_supplier_price(product)
        )

        retail_price = get_retail_price(
            name,
            supplier_price
        )

        # Если наша цена None,
        # товар вообще не показываем.
        if retail_price is None:
            continue

        button_text = (
            f"{name} — {retail_price} ₽"
        )

        markup.add(
            types.InlineKeyboardButton(
                button_text,
                callback_data=(
                    f"product:{product_id}"
                ),
            )
        )

        visible_count += 1

    if visible_count == 0:

        bot.send_message(
            message.chat.id,

            (
                f"<b>{title}</b>\n\n"
                "Сейчас в этом разделе нет "
                "доступных товаров."
            ),

            parse_mode="HTML",
            reply_markup=main_menu(),
        )

        return

    bot.send_message(
        message.chat.id,

        f"<b>{title}</b>\n\n"
        "Выбери товар:",

        parse_mode="HTML",
        reply_markup=markup,
    )


# =========================================================
# DIAMONDS
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.text == "💎 Diamonds"
)
def diamonds(message):

    show_category(
        message,
        CATEGORY_DIAMONDS,
        "💎 Diamonds",
    )


# =========================================================
# VOUCHERS
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.text == "🎟 Vouchers"
)
def vouchers(message):

    show_category(
        message,
        CATEGORY_VOUCHERS,
        "🎟 Vouchers",
    )


# =========================================================
# MONTHLY PASS
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.text == "⭐ Monthly Pass"
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
    func=lambda call:
    call.data.startswith("product:")
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

        products = data.get(
            "products",
            []
        )

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

    supplier_price = (
        product_supplier_price(selected)
    )

    retail_price = get_retail_price(
        name,
        supplier_price
    )

    if retail_price is None:

        bot.answer_callback_query(
            call.id,
            "Товар временно недоступен",
            show_alert=True,
        )

        return

    text = (
        f"🛒 <b>{name}</b>\n\n"

        f"💰 Цена: "
        f"<b>{retail_price} ₽</b>\n\n"

        "⏱ Выдача заказа: "
        "<b>20–90 минут</b>\n\n"

        "После оплаты потребуется указать "
        "данные, необходимые для выдачи товара."
    )

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "🛒 Купить",
            callback_data=(
                f"buy:{product_id}"
            ),
        )
    )

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

    bot.answer_callback_query(
        call.id
    )


# =========================================================
# КНОПКА КУПИТЬ
# =========================================================

@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("buy:")
)
def buy_product(call):

    bot.answer_callback_query(
        call.id
    )

    bot.send_message(
        call.message.chat.id,

        (
            "🛒 <b>Покупка товара</b>\n\n"

            "Система оплаты ещё подключается.\n\n"

            "Пока заказ можно оформить через "
            "поддержку:"
        ),

        parse_mode="HTML",
    )

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "💬 Написать в поддержку",
            url="https://t.me/Darkwolfan",
        )
    )

    bot.send_message(
        call.message.chat.id,

        "Нажми кнопку ниже:",

        reply_markup=markup,
    )


# =========================================================
# МОИ ЗАКАЗЫ
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.text == "📦 Мои заказы"
)
def my_orders(message):

    bot.send_message(
        message.chat.id,

        (
            "📦 <b>Мои заказы</b>\n\n"

            "Раздел находится в разработке.\n\n"

            "После подключения оплаты здесь "
            "будет история заказов."
        ),

        parse_mode="HTML",

        reply_markup=main_menu(),
    )


# =========================================================
# ПОДДЕРЖКА
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.text == "💬 Поддержка"
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

        "Выбери нужный раздел в меню 👇",

        reply_markup=main_menu(),
    )


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

class HealthHandler(
    BaseHTTPRequestHandler
):

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

    def log_message(
        self,
        format,
        *args
    ):

        return


def start_web_server():

    server = HTTPServer(
        ("0.0.0.0", PORT),
        HealthHandler,
    )

    print(
        f"🌐 Render server started "
        f"on port {PORT}"
    )

    server.serve_forever()


# =========================================================
# ЗАПУСК
# =========================================================

if __name__ == "__main__":

    print(
        "🔥 ARES SHOP запускается..."
    )

    web_thread = threading.Thread(
        target=start_web_server,
        daemon=True,
    )

    web_thread.start()

    print(
        "🤖 Telegram bot запускается..."
    )

    bot.infinity_polling(
        skip_pending=True,
        timeout=30,
        long_polling_timeout=30,
    )
