import os
import threading
import re
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
USD_RUB = 85.5

CATEGORY_PASS = 1367
CATEGORY_VOUCHERS = 1368
CATEGORY_DIAMONDS = 1369


# Цены ARES SHOP для Vouchers
VOUCHER_PRICES = {
    99: None,
    499: None,
    999: 889,
    1999: 1769,
    4999: 4449,
    9999: 8899,
}


if not TELEGRAM_TOKEN:
    raise RuntimeError("Не найдена переменная BOT_TOKEN")

if not VENDORIA_TOKEN:
    raise RuntimeError("Не найдена переменная VENDORIA_TOKEN")


bot = telebot.TeleBot(TELEGRAM_TOKEN)


HEADERS = {
    "Authorization": f"Shop {VENDORIA_TOKEN}",
    "Accept-Language": "ru",
}


# =========================================================
# ВРЕМЕННОЕ ХРАНИЛИЩЕ ДАННЫХ ФОРМЫ
# =========================================================

user_states = {}


# =========================================================
# VENDORIA API
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
            print("Vendoria error:")
            print(response.text)
            return None

        return response.json()

    except Exception as e:
        print("Vendoria exception:", e)
        return None


def get_products():
    return vendoria_get(
        "/api/products",
        {"prices": "true"}
    )


def get_forms():
    return vendoria_get(
        "/api/forms",
        {"serviceId": SERVICE_ID}
    )


# =========================================================
# ЦЕНЫ
# =========================================================

def product_name(product):
    return (
        product.get("name")
        or product.get("title")
        or product.get("productName")
        or f"Товар #{product.get('id', '?')}"
    )


def extract_price(value):

    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

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

    if isinstance(value, dict):

        for key in [
            "price",
            "amount",
            "value",
            "USD",
            "usd",
            "cost",
        ]:

            if key in value:

                result = extract_price(
                    value[key]
                )

                if result is not None:
                    return result

        return None

    if isinstance(value, list):

        for item in value:

            result = extract_price(item)

            if result is not None:
                return result

    return None


def product_supplier_price(product):

    fields = [
        product.get("price"),
        product.get("prices"),
        product.get("cost"),
        product.get("amount"),
    ]

    for field in fields:

        price = extract_price(field)

        if price is not None:
            return price

    return None


def get_voucher_nominal(name):

    clean_name = name.replace(",", "")

    numbers = re.findall(
        r"\d+",
        clean_name
    )

    if not numbers:
        return None

    for number in numbers:

        try:

            value = int(number)

            if value in VOUCHER_PRICES:
                return value

        except Exception:
            continue

    return None


def get_retail_price(
    name,
    supplier_price=None,
    category_id=None
):

    # VOUCHERS
    if category_id == CATEGORY_VOUCHERS:

        nominal = get_voucher_nominal(name)

        print(
            f"Voucher: {name} "
            f"-> nominal={nominal}"
        )

        if nominal is None:
            return None

        return VOUCHER_PRICES.get(nominal)

    # DIAMONDS
    if category_id == CATEGORY_DIAMONDS:

        if supplier_price is None:
            return None

        rub = supplier_price * USD_RUB
        retail = rub * 1.10

        return int(
            round(retail / 10) * 10
        )

    # PASS
    if category_id == CATEGORY_PASS:

        if supplier_price is None:
            return None

        rub = supplier_price * USD_RUB
        retail = rub * 1.10

        return int(
            round(retail / 10) * 10
        )

    return None


# =========================================================
# ТОВАРЫ
# =========================================================

def get_category_products(category_id):

    data = get_products()

    if not data:
        return []

    if isinstance(data, list):

        products = data

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

            if int(product_category) == int(category_id):
                result.append(product)

        except Exception:
            continue

    return result


def find_product(product_id):

    data = get_products()

    if not data:
        return None

    if isinstance(data, list):

        products = data

    elif isinstance(data, dict):

        products = data.get(
            "products",
            []
        )

    else:
        return None

    for product in products:

        if not isinstance(product, dict):
            continue

        try:

            if int(product.get("id")) == int(product_id):
                return product

        except Exception:
            continue

    return None


# =========================================================
# МЕНЮ
# =========================================================

def main_menu():

    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    markup.row(
        "💎 Diamonds",
        "🎟 Vouchers"
    )

    markup.row(
        "⭐ Monthly Pass"
    )

    markup.row(
        "📦 Мои заказы",
        "💬 Поддержка"
    )

    return markup


# =========================================================
# START
# =========================================================

@bot.message_handler(commands=["start"])
def start(message):

    text = (
        "🔥 <b>ARES SHOP</b>\n\n"
        "Магазин цифровых товаров для "
        "<b>Z Route: Redemption</b>.\n\n"
        "💎 Diamonds\n"
        "🎟 Vouchers\n"
        "⭐ Monthly Pass\n\n"
        "Выбери нужный раздел ниже."
    )

    bot.send_message(
        message.chat.id,
        text,
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# =========================================================
# КАТЕГОРИЯ
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
            "❌ Не удалось получить товары.\n\n"
            "Попробуй ещё раз через несколько секунд.",
            reply_markup=main_menu()
        )

        return

    markup = types.InlineKeyboardMarkup()

    visible_count = 0

    for product in products:

        product_id = product.get("id")

        if product_id is None:
            continue

        name = product_name(product)

        supplier_price = product_supplier_price(
            product
        )

        retail_price = get_retail_price(
            name,
            supplier_price,
            category_id
        )

        if retail_price is None:
            continue

        button_text = (
            f"{name} — {retail_price} ₽"
        )

        markup.add(
            types.InlineKeyboardButton(
                button_text,
                callback_data=f"product:{product_id}"
            )
        )

        visible_count += 1

    if visible_count == 0:

        bot.send_message(
            message.chat.id,
            f"<b>{title}</b>\n\n"
            "Сейчас в этом разделе нет "
            "доступных товаров.",
            parse_mode="HTML",
            reply_markup=main_menu()
        )

        return

    bot.send_message(
        message.chat.id,
        f"<b>{title}</b>\n\n"
        "Выбери товар:",
        parse_mode="HTML",
        reply_markup=markup
    )


@bot.message_handler(
    func=lambda message:
    message.text == "💎 Diamonds"
)
def diamonds(message):

    show_category(
        message,
        CATEGORY_DIAMONDS,
        "💎 Diamonds"
    )


@bot.message_handler(
    func=lambda message:
    message.text == "🎟 Vouchers"
)
def vouchers(message):

    show_category(
        message,
        CATEGORY_VOUCHERS,
        "🎟 Vouchers"
    )


@bot.message_handler(
    func=lambda message:
    message.text == "⭐ Monthly Pass"
)
def monthly_pass(message):

    show_category(
        message,
        CATEGORY_PASS,
        "⭐ Monthly Pass"
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
            show_alert=True
        )

        return

    selected = find_product(
        product_id
    )

    if not selected:

        bot.answer_callback_query(
            call.id,
            "Товар не найден",
            show_alert=True
        )

        return

    name = product_name(selected)

    category_id = (
        selected.get("categoryId")
        or selected.get("category_id")
    )

    try:

        category_id = int(category_id)

    except Exception:

        category_id = None

    supplier_price = product_supplier_price(
        selected
    )

    retail_price = get_retail_price(
        name,
        supplier_price,
        category_id
    )

    if retail_price is None:

        bot.answer_callback_query(
            call.id,
            "Товар временно недоступен",
            show_alert=True
        )

        return

    text = (
        f"🛒 <b>{name}</b>\n\n"
        f"💰 Цена: <b>{retail_price} ₽</b>\n\n"
        "⏱ Выдача заказа: "
        "<b>20–90 минут</b>\n\n"
        "После оплаты потребуется "
        "указать данные, необходимые "
        "для выдачи товара."
    )

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "🛒 Купить",
            callback_data=f"buy:{product_id}"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "💬 Поддержка",
            url="https://t.me/Darkwolfan"
        )
    )

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="HTML",
        reply_markup=markup
    )

    bot.answer_callback_query(call.id)


# =========================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ФОРМЫ
# =========================================================

def normalize_forms(data):

    if not data:
        return []

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        for key in [
            "forms",
            "data",
            "items",
        ]:

            value = data.get(key)

            if isinstance(value, list):
                return value

    return []


def get_form_fields(form):

    if not isinstance(form, dict):
        return []

    for key in [
        "fields",
        "items",
        "formFields",
        "inputs",
    ]:

        value = form.get(key)

        if isinstance(value, list):
            return value

    return []


def field_name(field):

    return (
        field.get("name")
        or field.get("label")
        or field.get("title")
        or field.get("key")
        or "Поле"
    )


def field_key(field, index):

    return (
        field.get("key")
        or field.get("name")
        or field.get("id")
        or f"field_{index}"
    )


def field_type(field):

    value = (
        field.get("type")
        or field.get("fieldType")
        or "text"
    )

    return str(value).lower()


def field_options(field):

    options = (
        field.get("options")
        or field.get("values")
        or field.get("choices")
        or []
    )

    if isinstance(options, dict):

        result = []

        for key, value in options.items():

            result.append(
                {
                    "key": key,
                    "name": value
                }
            )

        return result

    if isinstance(options, list):

        return options

    return []


def find_form_for_product(forms, product):

    product_form_id = (
        product.get("formId")
        or product.get("form_id")
    )

    if product_form_id is not None:

        for form in forms:

            if not isinstance(form, dict):
                continue

            form_id = (
                form.get("id")
                or form.get("formId")
            )

            try:

                if int(form_id) == int(product_form_id):
                    return form

            except Exception:
                continue

    # Если форма одна — используем её
    if len(forms) == 1:
        return forms[0]

    # Пытаемся найти форму по product/service
    for form in forms:

        if not isinstance(form, dict):
            continue

        if (
            form.get("serviceId") == SERVICE_ID
            or form.get("service_id") == SERVICE_ID
        ):
            return form

    return None


# =========================================================
# НАЖАТИЕ КУПИТЬ
# =========================================================

@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("buy:")
)
def buy_product(call):

    try:

        product_id = int(
            call.data.split(":")[1]
        )

    except Exception:

        bot.answer_callback_query(
            call.id,
            "Ошибка товара",
            show_alert=True
        )

        return

    product = find_product(
        product_id
    )

    if not product:

        bot.answer_callback_query(
            call.id,
            "Товар не найден",
            show_alert=True
        )

        return

    bot.answer_callback_query(
        call.id
    )

    bot.send_message(
        call.message.chat.id,
        "⏳ Получаю форму для оформления заказа..."
    )

    forms_data = get_forms()

    if not forms_data:

        bot.send_message(
            call.message.chat.id,
            "❌ Не удалось получить форму Vendoria.\n\n"
            "Попробуй ещё раз через несколько секунд."
        )

        return

    forms = normalize_forms(
        forms_data
    )

    print("VENDORA FORMS:")
    print(forms_data)

    form = find_form_for_product(
        forms,
        product
    )

    if not form:

        bot.send_message(
            call.message.chat.id,
            "❌ Не удалось определить форму "
            "для этого товара.\n\n"
            "Я вывел ответ Vendoria в лог Render."
        )

        return

    fields = get_form_fields(
        form
    )

    print("SELECTED FORM:")
    print(form)

    print("FORM FIELDS:")
    print(fields)

    if not fields:

        bot.send_message(
            call.message.chat.id,
            "⚠️ Vendoria вернула форму без полей.\n\n"
            "Проверим ответ API перед следующим этапом."
        )

        return

    # Сохраняем состояние пользователя
    user_states[call.message.chat.id] = {
        "product_id": product_id,
        "product": product,
        "form": form,
        "fields": fields,
        "current_field": 0,
        "answers": {},
    }

    ask_next_form_field(
        call.message.chat.id
    )


# =========================================================
# ЗАПРОС СЛЕДУЮЩЕГО ПОЛЯ
# =========================================================

def ask_next_form_field(chat_id):

    state = user_states.get(
        chat_id
    )

    if not state:
        return

    fields = state["fields"]
    index = state["current_field"]

    # Все поля заполнены
    if index >= len(fields):

        finish_form(
            chat_id
        )

        return

    field = fields[index]

    name = field_name(
        field
    )

    ftype = field_type(
        field
    )

    # SELECT
    if ftype in [
        "select",
        "dropdown",
        "choice",
    ]:

        options = field_options(
            field
        )

        if options:

            markup = types.InlineKeyboardMarkup()

            for option in options:

                if isinstance(option, dict):

                    option_key = (
                        option.get("key")
                        or option.get("value")
                        or option.get("id")
                        or option.get("name")
                    )

                    option_name = (
                        option.get("name")
                        or option.get("label")
                        or option.get("title")
                        or str(option_key)
                    )

                else:

                    option_key = str(option)
                    option_name = str(option)

                markup.add(
                    types.InlineKeyboardButton(
                        str(option_name),
                        callback_data=(
                            f"formselect:"
                            f"{index}:"
                            f"{option_key}"
                        )
                    )
                )

            bot.send_message(
                chat_id,
                f"📝 <b>{name}</b>\n\n"
                "Выбери вариант:",
                parse_mode="HTML",
                reply_markup=markup
            )

            return

    # Остальные типы пока вводим текстом
    bot.send_message(
        chat_id,
        f"📝 <b>{name}</b>\n\n"
        "Отправь значение сообщением.",
        parse_mode="HTML"
    )


# =========================================================
# SELECT В ФОРМЕ
# =========================================================

@bot.callback_query_handler(
    func=lambda call:
    call.data.startswith("formselect:")
)
def form_select(call):

    try:

        parts = call.data.split(
            ":",
            2
        )

        index = int(parts[1])
        value = parts[2]

    except Exception:

        bot.answer_callback_query(
            call.id,
            "Ошибка выбора",
            show_alert=True
        )

        return

    chat_id = call.message.chat.id

    state = user_states.get(
        chat_id
    )

    if not state:

        bot.answer_callback_query(
            call.id,
            "Сессия устарела",
            show_alert=True
        )

        return

    fields = state["fields"]

    if index >= len(fields):

        bot.answer_callback_query(
            call.id,
            "Поле не найдено",
            show_alert=True
        )

        return

    field = fields[index]

    key = field_key(
        field,
        index
    )

    state["answers"][str(key)] = value

    state["current_field"] += 1

    bot.answer_callback_query(
        call.id,
        "Выбрано"
    )

    ask_next_form_field(
        chat_id
    )


# =========================================================
# ТЕКСТОВЫЕ ПОЛЯ ФОРМЫ
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.chat.id in user_states
)
def form_text_input(message):

    state = user_states.get(
        message.chat.id
    )

    if not state:
        return

    fields = state["fields"]
    index = state["current_field"]

    if index >= len(fields):
        return

    field = fields[index]

    ftype = field_type(
        field
    )

    # SELECT обрабатывается кнопками
    if ftype in [
        "select",
        "dropdown",
        "choice",
    ]:
        return

    key = field_key(
        field,
        index
    )

    state["answers"][str(key)] = (
        message.text
    )

    state["current_field"] += 1

    ask_next_form_field(
        message.chat.id
    )


# =========================================================
# ЗАВЕРШЕНИЕ ФОРМЫ
# =========================================================

def finish_form(chat_id):

    state = user_states.get(
        chat_id
    )

    if not state:
        return

    product = state["product"]
    answers = state["answers"]

    name = product_name(
        product
    )

    category_id = (
        product.get("categoryId")
        or product.get("category_id")
    )

    try:

        category_id = int(
            category_id
        )

    except Exception:

        category_id = None

    supplier_price = product_supplier_price(
        product
    )

    retail_price = get_retail_price(
        name,
        supplier_price,
        category_id
    )

    text = (
        "✅ <b>Данные получены</b>\n\n"
        f"🛒 Товар: <b>{name}</b>\n"
        f"💰 Цена: <b>{retail_price} ₽</b>\n\n"
        "📋 Данные для выдачи сохранены.\n\n"
        "⚠️ Оплата пока не подключена, "
        "поэтому заказ в Vendoria ещё "
        "НЕ создаётся.\n\n"
        "Следующим этапом подключим "
        "оплату и создание реального заказа."
    )

    bot.send_message(
        chat_id,
        text,
        parse_mode="HTML"
    )

    print(
        "FORM ANSWERS:",
        answers
    )

    # Состояние пока сохраняем для тестирования
    state["completed"] = True


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
        "📦 <b>Мои заказы</b>\n\n"
        "Раздел находится в разработке.\n\n"
        "После подключения оплаты здесь "
        "будет история заказов.",
        parse_mode="HTML",
        reply_markup=main_menu()
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
            url="https://t.me/Darkwolfan"
        )
    )

    bot.send_message(
        message.chat.id,
        "💬 <b>Поддержка ARES SHOP</b>\n\n"
        "Если возник вопрос по товару "
        "или заказу, напиши нашей поддержке.",
        parse_mode="HTML",
        reply_markup=markup
    )


# =========================================================
# ПРОЧИЕ СООБЩЕНИЯ
# =========================================================

@bot.message_handler(
    func=lambda message: True
)
def other_message(message):

    bot.send_message(
        message.chat.id,
        "Выбери нужный раздел в меню 👇",
        reply_markup=main_menu()
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
        HealthHandler
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
        daemon=True
    )

    web_thread.start()

    print(
        "🤖 Telegram bot запускается..."
    )

    bot.infinity_polling(
        skip_pending=True,
        timeout=30,
        long_polling_timeout=30
    )
