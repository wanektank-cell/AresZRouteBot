import os
import threading
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
import telebot
from telebot import types


# =========================================================
# РќРђРЎРўР РћР™РљР
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


# Р¦РµРЅС‹ ARES SHOP РґР»СЏ Vouchers
VOUCHER_PRICES = {
    99: None,
    499: None,
    999: 889,
    1999: 1769,
    4999: 4449,
    9999: 8899,
}


if not TELEGRAM_TOKEN:
    raise RuntimeError("РќРµ РЅР°Р№РґРµРЅР° РїРµСЂРµРјРµРЅРЅР°СЏ BOT_TOKEN")

if not VENDORIA_TOKEN:
    raise RuntimeError("РќРµ РЅР°Р№РґРµРЅР° РїРµСЂРµРјРµРЅРЅР°СЏ VENDORIA_TOKEN")


bot = telebot.TeleBot(TELEGRAM_TOKEN)


HEADERS = {
    "Authorization": f"Shop {VENDORIA_TOKEN}",
    "Accept-Language": "ru",
}


# =========================================================
# Р’Р Р•РњР•РќРќРћР• РҐР РђРќРР›РР©Р• Р”РђРќРќР«РҐ Р¤РћР РњР«
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
# Р¦Р•РќР«
# =========================================================

def product_name(product):
    return (
        product.get("name")
        or product.get("title")
        or product.get("productName")
        or f"РўРѕРІР°СЂ #{product.get('id', '?')}"
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
# РўРћР’РђР Р«
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
# РњР•РќР®
# =========================================================

def main_menu():

    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    markup.row(
        "рџ’Ћ Diamonds",
        "рџЋџ Vouchers"
    )

    markup.row(
        "в­ђ Monthly Pass"
    )

    markup.row(
        "рџ“¦ РњРѕРё Р·Р°РєР°Р·С‹",
        "рџ’¬ РџРѕРґРґРµСЂР¶РєР°"
    )

    return markup


# =========================================================
# START
# =========================================================

@bot.message_handler(commands=["start"])
def start(message):

    text = (
        "рџ”Ґ <b>ARES SHOP</b>\n\n"
        "РњР°РіР°Р·РёРЅ С†РёС„СЂРѕРІС‹С… С‚РѕРІР°СЂРѕРІ РґР»СЏ "
        "<b>Z Route: Redemption</b>.\n\n"
        "рџ’Ћ Diamonds\n"
        "рџЋџ Vouchers\n"
        "в­ђ Monthly Pass\n\n"
        "Р’С‹Р±РµСЂРё РЅСѓР¶РЅС‹Р№ СЂР°Р·РґРµР» РЅРёР¶Рµ."
    )

    bot.send_message(
        message.chat.id,
        text,
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# =========================================================
# РљРђРўР•Р“РћР РРЇ
# =========================================================

def show_category(
    message,
    category_id,
    title
):

    bot.send_message(
        message.chat.id,
        "вЏі Р—Р°РіСЂСѓР¶Р°СЋ С‚РѕРІР°СЂС‹..."
    )

    products = get_category_products(
        category_id
    )

    if not products:

        bot.send_message(
            message.chat.id,
            "вќЊ РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ С‚РѕРІР°СЂС‹.\n\n"
            "РџРѕРїСЂРѕР±СѓР№ РµС‰С‘ СЂР°Р· С‡РµСЂРµР· РЅРµСЃРєРѕР»СЊРєРѕ СЃРµРєСѓРЅРґ.",
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
            f"{name} вЂ” {retail_price} в‚Ѕ"
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
            "РЎРµР№С‡Р°СЃ РІ СЌС‚РѕРј СЂР°Р·РґРµР»Рµ РЅРµС‚ "
            "РґРѕСЃС‚СѓРїРЅС‹С… С‚РѕРІР°СЂРѕРІ.",
            parse_mode="HTML",
            reply_markup=main_menu()
        )

        return

    bot.send_message(
        message.chat.id,
        f"<b>{title}</b>\n\n"
        "Р’С‹Р±РµСЂРё С‚РѕРІР°СЂ:",
        parse_mode="HTML",
        reply_markup=markup
    )


@bot.message_handler(
    func=lambda message:
    message.text == "рџ’Ћ Diamonds"
)
def diamonds(message):

    show_category(
        message,
        CATEGORY_DIAMONDS,
        "рџ’Ћ Diamonds"
    )


@bot.message_handler(
    func=lambda message:
    message.text == "рџЋџ Vouchers"
)
def vouchers(message):

    show_category(
        message,
        CATEGORY_VOUCHERS,
        "рџЋџ Vouchers"
    )


@bot.message_handler(
    func=lambda message:
    message.text == "в­ђ Monthly Pass"
)
def monthly_pass(message):

    show_category(
        message,
        CATEGORY_PASS,
        "в­ђ Monthly Pass"
    )


# =========================================================
# Р’Р«Р‘РћР  РўРћР’РђР Рђ
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
            "РћС€РёР±РєР° С‚РѕРІР°СЂР°",
            show_alert=True
        )

        return

    selected = find_product(
        product_id
    )

    if not selected:

        bot.answer_callback_query(
            call.id,
            "РўРѕРІР°СЂ РЅРµ РЅР°Р№РґРµРЅ",
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
            "РўРѕРІР°СЂ РІСЂРµРјРµРЅРЅРѕ РЅРµРґРѕСЃС‚СѓРїРµРЅ",
            show_alert=True
        )

        return

    text = (
        f"рџ›’ <b>{name}</b>\n\n"
        f"рџ’° Р¦РµРЅР°: <b>{retail_price} в‚Ѕ</b>\n\n"
        "вЏ± Р’С‹РґР°С‡Р° Р·Р°РєР°Р·Р°: "
        "<b>20вЂ“90 РјРёРЅСѓС‚</b>\n\n"
        "РџРѕСЃР»Рµ РѕРїР»Р°С‚С‹ РїРѕС‚СЂРµР±СѓРµС‚СЃСЏ "
        "СѓРєР°Р·Р°С‚СЊ РґР°РЅРЅС‹Рµ, РЅРµРѕР±С…РѕРґРёРјС‹Рµ "
        "РґР»СЏ РІС‹РґР°С‡Рё С‚РѕРІР°СЂР°."
    )

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "рџ›’ РљСѓРїРёС‚СЊ",
            callback_data=f"buy:{product_id}"
        )
    )

    markup.add(
        types.InlineKeyboardButton(
            "рџ’¬ РџРѕРґРґРµСЂР¶РєР°",
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
# Р’РЎРџРћРњРћР“РђРўР•Р›Р¬РќР«Р• Р¤РЈРќРљР¦РР Р¤РћР РњР«
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
        or "РџРѕР»Рµ"
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

    # Р•СЃР»Рё С„РѕСЂРјР° РѕРґРЅР° вЂ” РёСЃРїРѕР»СЊР·СѓРµРј РµС‘
    if len(forms) == 1:
        return forms[0]

    # РџС‹С‚Р°РµРјСЃСЏ РЅР°Р№С‚Рё С„РѕСЂРјСѓ РїРѕ product/service
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
# РќРђР–РђРўРР• РљРЈРџРРўР¬
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
            "РћС€РёР±РєР° С‚РѕРІР°СЂР°",
            show_alert=True
        )

        return

    product = find_product(
        product_id
    )

    if not product:

        bot.answer_callback_query(
            call.id,
            "РўРѕРІР°СЂ РЅРµ РЅР°Р№РґРµРЅ",
            show_alert=True
        )

        return

    bot.answer_callback_query(
        call.id
    )

    bot.send_message(
        call.message.chat.id,
        "вЏі РџРѕР»СѓС‡Р°СЋ С„РѕСЂРјСѓ РґР»СЏ РѕС„РѕСЂРјР»РµРЅРёСЏ Р·Р°РєР°Р·Р°..."
    )

    forms_data = get_forms()

    if not forms_data:

        bot.send_message(
            call.message.chat.id,
            "вќЊ РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ С„РѕСЂРјСѓ Vendoria.\n\n"
            "РџРѕРїСЂРѕР±СѓР№ РµС‰С‘ СЂР°Р· С‡РµСЂРµР· РЅРµСЃРєРѕР»СЊРєРѕ СЃРµРєСѓРЅРґ."
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
            "вќЊ РќРµ СѓРґР°Р»РѕСЃСЊ РѕРїСЂРµРґРµР»РёС‚СЊ С„РѕСЂРјСѓ "
            "РґР»СЏ СЌС‚РѕРіРѕ С‚РѕРІР°СЂР°.\n\n"
            "РЇ РІС‹РІРµР» РѕС‚РІРµС‚ Vendoria РІ Р»РѕРі Render."
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
            "вљ пёЏ Vendoria РІРµСЂРЅСѓР»Р° С„РѕСЂРјСѓ Р±РµР· РїРѕР»РµР№.\n\n"
            "РџСЂРѕРІРµСЂРёРј РѕС‚РІРµС‚ API РїРµСЂРµРґ СЃР»РµРґСѓСЋС‰РёРј СЌС‚Р°РїРѕРј."
        )

        return

    # РЎРѕС…СЂР°РЅСЏРµРј СЃРѕСЃС‚РѕСЏРЅРёРµ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
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
# Р—РђРџР РћРЎ РЎР›Р•Р”РЈР®Р©Р•Р“Рћ РџРћР›РЇ
# =========================================================

def ask_next_form_field(chat_id):

    state = user_states.get(
        chat_id
    )

    if not state:
        return

    fields = state["fields"]
    index = state["current_field"]

    # Р’СЃРµ РїРѕР»СЏ Р·Р°РїРѕР»РЅРµРЅС‹
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
                f"рџ“ќ <b>{name}</b>\n\n"
                "Р’С‹Р±РµСЂРё РІР°СЂРёР°РЅС‚:",
                parse_mode="HTML",
                reply_markup=markup
            )

            return

    # РћСЃС‚Р°Р»СЊРЅС‹Рµ С‚РёРїС‹ РїРѕРєР° РІРІРѕРґРёРј С‚РµРєСЃС‚РѕРј
    bot.send_message(
        chat_id,
        f"рџ“ќ <b>{name}</b>\n\n"
        "РћС‚РїСЂР°РІСЊ Р·РЅР°С‡РµРЅРёРµ СЃРѕРѕР±С‰РµРЅРёРµРј.",
        parse_mode="HTML"
    )


# =========================================================
# SELECT Р’ Р¤РћР РњР•
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
            "РћС€РёР±РєР° РІС‹Р±РѕСЂР°",
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
            "РЎРµСЃСЃРёСЏ СѓСЃС‚Р°СЂРµР»Р°",
            show_alert=True
        )

        return

    fields = state["fields"]

    if index >= len(fields):

        bot.answer_callback_query(
            call.id,
            "РџРѕР»Рµ РЅРµ РЅР°Р№РґРµРЅРѕ",
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
        "Р’С‹Р±СЂР°РЅРѕ"
    )

    ask_next_form_field(
        chat_id
    )


# =========================================================
# РўР•РљРЎРўРћР’Р«Р• РџРћР›РЇ Р¤РћР РњР«
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

    # SELECT РѕР±СЂР°Р±Р°С‚С‹РІР°РµС‚СЃСЏ РєРЅРѕРїРєР°РјРё
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
# Р—РђР’Р•Р РЁР•РќРР• Р¤РћР РњР«
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
        "вњ… <b>Р”Р°РЅРЅС‹Рµ РїРѕР»СѓС‡РµРЅС‹</b>\n\n"
        f"рџ›’ РўРѕРІР°СЂ: <b>{name}</b>\n"
        f"рџ’° Р¦РµРЅР°: <b>{retail_price} в‚Ѕ</b>\n\n"
        "рџ“‹ Р”Р°РЅРЅС‹Рµ РґР»СЏ РІС‹РґР°С‡Рё СЃРѕС…СЂР°РЅРµРЅС‹.\n\n"
        "вљ пёЏ РћРїР»Р°С‚Р° РїРѕРєР° РЅРµ РїРѕРґРєР»СЋС‡РµРЅР°, "
        "РїРѕСЌС‚РѕРјСѓ Р·Р°РєР°Р· РІ Vendoria РµС‰С‘ "
        "РќР• СЃРѕР·РґР°С‘С‚СЃСЏ.\n\n"
        "РЎР»РµРґСѓСЋС‰РёРј СЌС‚Р°РїРѕРј РїРѕРґРєР»СЋС‡РёРј "
        "РѕРїР»Р°С‚Сѓ Рё СЃРѕР·РґР°РЅРёРµ СЂРµР°Р»СЊРЅРѕРіРѕ Р·Р°РєР°Р·Р°."
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

    # РЎРѕСЃС‚РѕСЏРЅРёРµ РїРѕРєР° СЃРѕС…СЂР°РЅСЏРµРј РґР»СЏ С‚РµСЃС‚РёСЂРѕРІР°РЅРёСЏ
    state["completed"] = True


# =========================================================
# РњРћР Р—РђРљРђР—Р«
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.text == "рџ“¦ РњРѕРё Р·Р°РєР°Р·С‹"
)
def my_orders(message):

    bot.send_message(
        message.chat.id,
        "рџ“¦ <b>РњРѕРё Р·Р°РєР°Р·С‹</b>\n\n"
        "Р Р°Р·РґРµР» РЅР°С…РѕРґРёС‚СЃСЏ РІ СЂР°Р·СЂР°Р±РѕС‚РєРµ.\n\n"
        "РџРѕСЃР»Рµ РїРѕРґРєР»СЋС‡РµРЅРёСЏ РѕРїР»Р°С‚С‹ Р·РґРµСЃСЊ "
        "Р±СѓРґРµС‚ РёСЃС‚РѕСЂРёСЏ Р·Р°РєР°Р·РѕРІ.",
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# =========================================================
# РџРћР”Р”Р•Р Р–РљРђ
# =========================================================

@bot.message_handler(
    func=lambda message:
    message.text == "рџ’¬ РџРѕРґРґРµСЂР¶РєР°"
)
def support(message):

    markup = types.InlineKeyboardMarkup()

    markup.add(
        types.InlineKeyboardButton(
            "рџ’¬ РќР°РїРёСЃР°С‚СЊ РІ РїРѕРґРґРµСЂР¶РєСѓ",
            url="https://t.me/Darkwolfan"
        )
    )

    bot.send_message(
        message.chat.id,
        "рџ’¬ <b>РџРѕРґРґРµСЂР¶РєР° ARES SHOP</b>\n\n"
        "Р•СЃР»Рё РІРѕР·РЅРёРє РІРѕРїСЂРѕСЃ РїРѕ С‚РѕРІР°СЂСѓ "
        "РёР»Рё Р·Р°РєР°Р·Сѓ, РЅР°РїРёС€Рё РЅР°С€РµР№ РїРѕРґРґРµСЂР¶РєРµ.",
        parse_mode="HTML",
        reply_markup=markup
    )


# =========================================================
# РџР РћР§РР• РЎРћРћР‘Р©Р•РќРРЇ
# =========================================================

@bot.message_handler(
    func=lambda message: True
)
def other_message(message):

    bot.send_message(
        message.chat.id,
        "Р’С‹Р±РµСЂРё РЅСѓР¶РЅС‹Р№ СЂР°Р·РґРµР» РІ РјРµРЅСЋ рџ‘‡",
        reply_markup=main_menu()
    )


# =========================================================
# RENDER WEBSITE
# =========================================================

class HealthHandler(
    BaseHTTPRequestHandler
):

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
                "Content-type",
                "text/html; charset=utf-8"
            )
            self.end_headers()
            self.wfile.write(
                "<h1>404</h1><p>Page not found</p>".encode("utf-8")
            )
            return

        try:

            file_path = os.path.join("site", filename)

            with open(file_path, "rb") as f:
                content = f.read()

            self.send_response(200)
            self.send_header(
                "Content-type",
                "text/html; charset=utf-8"
            )
            self.send_header(
                "Content-Length",
                str(len(content))
            )
            self.end_headers()
            self.wfile.write(content)

        except Exception as e:

            print("SITE ERROR:", e)
            self.send_response(500)
            self.send_header(
                "Content-type",
                "text/plain; charset=utf-8"
            )
            self.end_headers()
            self.wfile.write(
                b"Internal server error"
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
        f"рџЊђ Render server started "
        f"on port {PORT}"
    )

    server.serve_forever()


# =========================================================
# Р—РђРџРЈРЎРљ
# =========================================================

if __name__ == "__main__":

    print(
        "рџ”Ґ ARES SHOP Р·Р°РїСѓСЃРєР°РµС‚СЃСЏ..."
    )

    web_thread = threading.Thread(
        target=start_web_server,
        daemon=True
    )

    web_thread.start()

    print(
        "рџ¤– Telegram bot Р·Р°РїСѓСЃРєР°РµС‚СЃСЏ..."
    )

    bot.infinity_polling(
        skip_pending=True,
        timeout=30,
        long_polling_timeout=30
    )
