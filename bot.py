import os
import re
import html
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
USD_RUB = 85.5

CATEGORY_PASS = 1367
CATEGORY_VOUCHERS = 1368
CATEGORY_DIAMONDS = 1369

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

# Данные незавершённых форм пользователей
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
            f"Vendoria GET {endpoint}: "
            f"{response.status_code}"
        )

        if response.status_code != 200:
            print("Vendoria error:", response.text)
            return None

        return response.json()

    except Exception as error:
        print("Vendoria connection error:", error)
        return None


def get_products():
    return vendoria_get(
        "/api/products",
        {"prices": "true"},
    )


def get_forms():
    return vendoria_get(
        "/api/forms",
        {"serviceId": SERVICE_ID},
    )


def normalize_products(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("products", "data", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return value

    return []


# =========================================================
# ОБРАБОТКА ТОВАРОВ И ЦЕН
# =========================================================

def product_name(product):
    return str(
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
            value.replace("$", "")
            .replace("USD", "")
            .replace("usd", "")
            .replace(",", ".")
            .strip()
        )

        try:
            return float(cleaned)
        except ValueError:
            return None

    if isinstance(value, dict):
        for key in (
            "price",
            "amount",
            "value",
            "USD",
            "usd",
            "cost",
        ):
            if key in value:
                result = extract_price(value[key])
                if result is not None:
                    return result

    if isinstance(value, list):
        for item in value:
            result = extract_price(item)
            if result is not None:
                return result

    return None


def product_supplier_price(product):
    for field in (
        product.get("price"),
        product.get("prices"),
        product.get("cost"),
        product.get("amount"),
    ):
        price = extract_price(field)
        if price is not None:
            return price

    return None


def get_voucher_nominal(name):
    numbers = re.findall(r"\d+", name.replace(",", ""))

    for number in numbers:
        value = int(number)
        if value in VOUCHER_PRICES:
            return value

    return None


def get_retail_price(name, supplier_price=None, category_id=None):
    if category_id == CATEGORY_VOUCHERS:
        nominal = get_voucher_nominal(name)

        if nominal is None:
            return None

        return VOUCHER_PRICES[nominal]

    # Для Diamonds и Monthly Pass пока используется
    # ориентировочная наценка 10%.
    # Перед продажами обязательно проверь реальные цены.
    if category_id in (CATEGORY_DIAMONDS, CATEGORY_PASS):
        if supplier_price is None:
            return None

        rubles = supplier_price * USD_RUB
        retail = rubles * 1.10

        return int(round(retail / 10) * 10)

    return None


def get_category_products(category_id):
    data = get_products()
    products = normalize_products(data)
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
        except (TypeError, ValueError):
            continue

    return result


def find_product(product_id):
    products = normalize_products(get_products())

    for product in products:
        if not isinstance(product, dict):
            continue

        try:
            if int(product.get("id")) == int(product_id):
                return product
        except (TypeError, ValueError):
            continue

    return None


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

    markup.row("⭐ Monthly Pass")

    markup.row(
        "📦 Мои заказы",
        "💬 Поддержка",
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
        reply_markup=main_menu(),
    )


# =========================================================
# ПОКАЗ КАТЕГОРИИ
# =========================================================

def show_category(message, category_id, title):
    bot.send_message(
        message.chat.id,
        "⏳ Загружаю товары...",
    )

    products = get_category_products(category_id)

    if not products:
        bot.send_message(
            message.chat.id,
            "❌ Не удалось получить товары.\n\n"
            "Попробуй ещё раз через несколько секунд.",
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
        supplier_price = product_supplier_price(product)

        retail_price = get_retail_price(
            name,
            supplier_price,
            category_id,
        )

        if retail_price is None:
            continue

        button_text = f"{name} — {retail_price} ₽"

        markup.add(
            types.InlineKeyboardButton(
                button_text,
                callback_data=f"product:{product_id}",
            )
        )

        visible_count += 1

    if visible_count == 0:
        bot.send_message(
            message.chat.id,
            f"<b>{html.escape(title)}</b>\n\n"
            "Сейчас в этом разделе нет доступных товаров.",
            parse_mode="HTML",
            reply_markup=main_menu(),
        )
        return

    bot.send_message(
        message.chat.id,
        f"<b>{html.escape(title)}</b>\n\n"
        "Выбери товар:",
        parse_mode="HTML",
        reply_markup=markup,
    )


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
        product_id = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        bot.answer_callback_query(
            call.id,
            "Ошибка выбора товара",
            show_alert=True,
        )
        return

    product = find_product(product_id)

    if not product:
        bot.answer_callback_query(
            call.id,
            "Товар не найден",
            show_alert=True,
        )
        return

    name = product_name(product)

    category_id = (
        product.get("categoryId")
        or product.get("category_id")
    )

    try:
        category_id = int(category_id)
    except (TypeError, ValueError):
        category_id = None

    supplier_price = product_supplier_price(product)

    retail_price = get_retail_price(
        name,
        supplier_price,
        category_id,
    )

    if retail_price is None:
        bot.answer_callback_query(
            call.id,
            "Товар временно недоступен",
            show_alert=True,
        )
        return

    safe_name = html.escape(name)

    text = (
        f"🛒 <b>{safe_name}</b>\n\n"
        f"💰 Цена: <b>{retail_price} ₽</b>\n\n"
        "⏱ Ориентировочное время выдачи: "
        "<b>20–90 минут</b>.\n\n"
        "Перед выдачей потребуется указать данные, "
        "которые запросит форма оформления заказа.\n\n"
        "⚠️ Онлайн-оплата пока не подключена. "
        "Не отправляй деньги до появления официального "
        "способа оплаты в боте."
    )

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "🛒 Продолжить",
            callback_data=f"buy:{product_id}",
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

    bot.answer_callback_query(call.id)


# =========================================================
# ОБРАБОТКА ФОРМ VENDORIA
# =========================================================

def normalize_forms(data):
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        for key in ("forms", "data", "items"):
            value = data.get(key)
            if isinstance(value, list):
                return value

    return []


def get_form_fields(form):
    if not isinstance(form, dict):
        return []

    for key in ("fields", "items", "formFields", "inputs"):
        value = form.get(key)
        if isinstance(value, list):
            return value

    return []


def field_name(field):
    return str(
        field.get("name")
        or field.get("label")
        or field.get("title")
        or field.get("key")
        or "Поле"
    )


def field_key(field, index):
    return str(
        field.get("key")
        or field.get("name")
        or field.get("id")
        or f"field_{index}"
    )


def field_type(field):
    return str(
        field.get("type")
        or field.get("fieldType")
        or "text"
    ).lower()


def field_options(field):
    options = (
        field.get("options")
        or field.get("values")
        or field.get("choices")
        or []
    )

    if isinstance(options, dict):
        return [
            {"key": key, "name": value}
            for key, value in options.items()
        ]

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

            form_id = form.get("id") or form.get("formId")

            try:
                if int(form_id) == int(product_form_id):
                    return form
            except (TypeError, ValueError):
                continue

    if len(forms) == 1:
        return forms[0]

    for form in forms:
        if not isinstance(form, dict):
            continue

        service_id = (
            form.get("serviceId")
            or form.get("service_id")
        )

        try:
            if int(service_id) == SERVICE_ID:
                return form
        except (TypeError, ValueError):
            continue

    return None


# =========================================================
# НАЧАЛО ОФОРМЛЕНИЯ
# =========================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("buy:")
)
def buy_product(call):
    try:
        product_id = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        bot.answer_callback_query(
            call.id,
            "Ошибка выбора товара",
            show_alert=True,
        )
        return

    product = find_product(product_id)

    if not product:
        bot.answer_callback_query(
            call.id,
            "Товар не найден",
            show_alert=True,
        )
        return

    bot.answer_callback_query(call.id)

    bot.send_message(
        call.message.chat.id,
        "⏳ Получаю форму оформления заказа...",
    )

    forms_data = get_forms()

    if not forms_data:
        bot.send_message(
            call.message.chat.id,
            "❌ Не удалось получить форму Vendoria.\n\n"
            "Попробуй ещё раз позже.",
        )
        return

    forms = normalize_forms(forms_data)

    print("VENDORIA FORMS:", forms_data)

    form = find_form_for_product(forms, product)

    if not form:
        bot.send_message(
            call.message.chat.id,
            "❌ Не удалось определить форму этого товара.\n"
            "Проверь ответ Vendoria в логах Render.",
        )
        return

    fields = get_form_fields(form)

    print("SELECTED FORM:", form)
    print("FORM FIELDS:", fields)

    if not fields:
        bot.send_message(
            call.message.chat.id,
            "⚠️ Vendoria вернула форму без полей. "
            "Нужно проверить формат ответа API.",
        )
        return

    user_states[call.message.chat.id] = {
        "product_id": product_id,
        "product": product,
        "form": form,
        "fields": fields,
        "current_field": 0,
        "answers": {},
    }

    ask_next_form_field(call.message.chat.id)


# =========================================================
# ЗАПРОС СЛЕДУЮЩЕГО ПОЛЯ
# =========================================================

def ask_next_form_field(chat_id):
    state = user_states.get(chat_id)

    if not state:
        return

    fields = state["fields"]
    index = state["current_field"]

    if index >= len(fields):
        finish_form(chat_id)
        return

    field = fields[index]
    name = field_name(field)
    ftype = field_type(field)

    if ftype in ("select", "dropdown", "choice"):
        options = field_options(field)

        if options:
            markup = types.InlineKeyboardMarkup()

            for option_index, option in enumerate(options):
                if isinstance(option, dict):
                    option_value = (
                        option.get("key")
                        or option.get("value")
                        or option.get("id")
                        or option.get("name")
                        or str(option_index)
                    )

                    option_name = (
                        option.get("name")
                        or option.get("label")
                        or option.get("title")
                        or str(option_value)
                    )
                else:
                    option_value = str(option)
                    option_name = str(option)

                # Индекс нужен, чтобы значения с двоеточиями
                # не ломали callback_data.
                markup.add(
                    types.InlineKeyboardButton(
                        str(option_name)[:60],
                        callback_data=(
                            f"formselect:{index}:{option_index}"
                        ),
                    )
                )

            bot.send_message(
                chat_id,
                f"📝 <b>{html.escape(name)}</b>\n\n"
                "Выбери вариант:",
                parse_mode="HTML",
                reply_markup=markup,
            )
            return

    bot.send_message(
        chat_id,
        f"📝 <b>{html.escape(name)}</b>\n\n"
        "Отправь значение одним сообщением.",
        parse_mode="HTML",
    )


# =========================================================
# ВЫБОР ВАРИАНТА В ФОРМЕ
# =========================================================

@bot.callback_query_handler(
    func=lambda call: call.data.startswith("formselect:")
)
def form_select(call):
    try:
        _, index_text, option_index_text = call.data.split(":", 2)
        index = int(index_text)
        option_index = int(option_index_text)
    except (ValueError, IndexError):
        bot.answer_callback_query(
            call.id,
            "Ошибка выбора",
            show_alert=True,
        )
        return

    chat_id = call.message.chat.id
    state = user_states.get(chat_id)

    if not state:
        bot.answer_callback_query(
            call.id,
            "Сессия оформления не найдена",
            show_alert=True,
        )
        return

    fields = state["fields"]

    if index >= len(fields) or index != state["current_field"]:
        bot.answer_callback_query(
            call.id,
            "Это поле уже обработано",
            show_alert=True,
        )
        return

    field = fields[index]
    options = field_options(field)

    if option_index < 0 or option_index >= len(options):
        bot.answer_callback_query(
            call.id,
            "Вариант не найден",
            show_alert=True,
        )
        return

    option = options[option_index]

    if isinstance(option, dict):
        value = (
            option.get("key")
            or option.get("value")
            or option.get("id")
            or option.get("name")
            or str(option_index)
        )
    else:
        value = str(option)

    state["answers"][field_key(field, index)] = value
    state["current_field"] += 1

    bot.answer_callback_query(call.id, "Выбрано")
    ask_next_form_field(chat_id)


# =========================================================
# ТЕКСТОВЫЕ ПОЛЯ ФОРМЫ
# =========================================================

@bot.message_handler(
    func=lambda message: message.chat.id in user_states
)
def form_text_input(message):
    state = user_states.get(message.chat.id)

    if not state or not message.text:
        return

    fields = state["fields"]
    index = state["current_field"]

    if index >= len(fields):
        return

    field = fields[index]
    ftype = field_type(field)

    if ftype in ("select", "dropdown", "choice"):
        return

    key = field_key(field, index)
    state["answers"][key] = message.text.strip()
    state["current_field"] += 1

    ask_next_form_field(message.chat.id)


# =========================================================
# ЗАВЕРШЕНИЕ ФОРМЫ
# =========================================================

def finish_form(chat_id):
    state = user_states.get(chat_id)

    if not state:
        return

    product = state["product"]
    answers = state["answers"]
    name = product_name(product)

    category_id = (
        product.get("categoryId")
        or product.get("category_id")
    )

    try:
        category_id = int(category_id)
    except (TypeError, ValueError):
        category_id = None

    supplier_price = product_supplier_price(product)

    retail_price = get_retail_price(
        name,
        supplier_price,
        category_id,
    )

    if retail_price is None:
        retail_text = "не определена"
    else:
        retail_text = f"{retail_price} ₽"

    text = (
        "✅ <b>Данные получены</b>\n\n"
        f"🛒 Товар: <b>{html.escape(name)}</b>\n"
        f"💰 Цена: <b>{retail_text}</b>\n\n"
        "📋 Данные формы сохранены в текущей сессии.\n\n"
        "⚠️ Оплата ещё не подключена. "
        "Реальный заказ в Vendoria не создавался.\n\n"
        "Не отправляй пароль от игрового аккаунта "
        "через этот бот, пока не проверишь необходимость "
        "и безопасность такого способа выдачи."
    )

    bot.send_message(
        chat_id,
        text,
        parse_mode="HTML",
        reply_markup=main_menu(),
    )

    # Важно: ответы пока не сохраняются в базу данных.
    # Не выводим персональные данные клиентов в логи.
    state["completed"] = True

    print(
        f"Form completed for chat {chat_id}; "
        f"product_id={state['product_id']}"
    )

    user_states.pop(chat_id, None)


# =========================================================
# МОИ ЗАКАЗЫ
# =========================================================

@bot.message_handler(
    func=lambda message: message.text == "📦 Мои заказы"
)
def my_orders(message):
    bot.send_message(
        message.chat.id,
        "📦 <b>Мои заказы</b>\n\n"
        "История заказов пока не подключена.\n"
        "Она появится после подключения оплаты, "
        "создания заказов и хранения истории.",
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
        "💬 <b>Поддержка ARES SHOP</b>\n\n"
        "Если возник вопрос по товару или оформлению, "
        "напиши нашей поддержке.",
        parse_mode="HTML",
        reply_markup=markup,
    )


# =========================================================
# ПРОЧИЕ СООБЩЕНИЯ
# =========================================================

@bot.message_handler(func=lambda message: True)
def other_message(message):
    bot.send_message(
        message.chat.id,
        "Выбери нужный раздел в меню 👇",
        reply_markup=main_menu(),
    )


# =========================================================
# САЙТ ДЛЯ RENDER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        path = self.path.split("?")[0]

        pages = {
            "/": "index.html",
            "/index.html": "index.html",
            "/offer": "offer.html",
            "/offer.html": "offer.html",
            "/privacy": "privacy.html",
            "/privacy.html": "privacy.html",
            "/contacts": "contacts.html",
            "/contacts.html": "contacts.html",
        }

        filename = pages.get(path)

        if filename is None:
            self.send_response(404)
            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8",
            )
            self.end_headers()
            self.wfile.write(
                "<h1>404</h1><p>Страница не найдена</p>".encode("utf-8")
            )
            return

        try:
            file_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "site",
                filename,
            )

            with open(file_path, "rb") as file:
                content = file.read()

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/html; charset=utf-8",
            )
            self.send_header(
                "Content-Length",
                str(len(content)),
            )
            self.end_headers()
            self.wfile.write(content)

        except Exception as error:
            print("SITE ERROR:", error)

            self.send_response(500)
            self.send_header(
                "Content-Type",
                "text/plain; charset=utf-8",
            )
            self.end_headers()
            self.wfile.write(
                "Ошибка загрузки страницы".encode("utf-8")
            )

    def log_message(self, format, *args):
        return


def start_web_server():
    server = HTTPServer(
        ("0.0.0.0", PORT),
        HealthHandler,
    )

    print(f"Render server started on port {PORT}")
    server.serve_forever()


# =========================================================
# ЗАПУСК
# =========================================================

if __name__ == "__main__":
    print("ARES SHOP запускается...")

    web_thread = threading.Thread(
        target=start_web_server,
        daemon=True,
    )
    web_thread.start()

    print("Telegram bot запускается...")

    bot.infinity_polling(
        skip_pending=True,
        timeout=30,
        long_polling_timeout=30,
    )
