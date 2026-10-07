# AresZRouteBot
# Telegram shop bot for Z Route: Redemption
import telebot
from telebot import types

TOKEN = "ТВОЙ_НОВЫЙ_ТОКЕН_ОТ_BOTFATHER"

bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=['start'])
def start(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

    btn1 = types.KeyboardButton("💎 Diamonds")
    btn2 = types.KeyboardButton("🎟 Vouchers")
    btn3 = types.KeyboardButton("⭐ Monthly Pass")
    btn4 = types.KeyboardButton("📦 Мои заказы")
    btn5 = types.KeyboardButton("💬 Поддержка")

    keyboard.add(btn1, btn2)
    keyboard.add(btn3)
    keyboard.add(btn4, btn5)

    bot.send_message(
        message.chat.id,
        "🔥 ARES SHOP\n\nZ Route: Redemption\n\nВыберите раздел:",
        reply_markup=keyboard
    )


@bot.message_handler(func=lambda message: True)
def menu(message):

    if message.text == "💎 Diamonds":
        bot.send_message(
            message.chat.id,
            "💎 Diamonds\n\nКаталог скоро загрузится из Vendoria."
        )

    elif message.text == "🎟 Vouchers":
        bot.send_message(
            message.chat.id,
            "🎟 Vouchers\n\nКаталог скоро загрузится из Vendoria."
        )

    elif message.text == "⭐ Monthly Pass":
        bot.send_message(
            message.chat.id,
            "⭐ Monthly Pass\n\nКаталог скоро загрузится из Vendoria."
        )

    elif message.text == "📦 Мои заказы":
        bot.send_message(
            message.chat.id,
            "📦 У вас пока нет заказов."
        )

    elif message.text == "💬 Поддержка":
        bot.send_message(
            message.chat.id,
            "💬 Поддержка ARES SHOP"
        )


bot.infinity_polling()
⚠️ Важный момент: строку

TOKEN = "ТВОЙ_НОВЫЙ_ТОКЕН_ОТ_BOTFATHER"
ты заменяешь на свой новый токен от BotFather.

Токен сюда не отправляй.

После этого:

Нажми Commit changes

Напиши мне:
"bot.py добавил"

Следом создадим requirements.txt и запустим бота.


# AresZRouteBot
Telegram shop bot for Z Route: Redemption
import telebot
from telebot import types

TOKEN = "ТВОЙ_НОВЫЙ_ТОКЕН_ОТ_BOTFATHER"

bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=['start'])
def start(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)

    btn1 = types.KeyboardButton("💎 Diamonds")
    btn2 = types.KeyboardButton("🎟 Vouchers")
    btn3 = types.KeyboardButton("⭐ Monthly Pass")
    btn4 = types.KeyboardButton("📦 Мои заказы")
    btn5 = types.KeyboardButton("💬 Поддержка")

    keyboard.add(btn1, btn2)
    keyboard.add(btn3)
    keyboard.add(btn4, btn5)

    bot.send_message(
        message.chat.id,
        "🔥 ARES SHOP\n\nZ Route: Redemption\n\nВыберите раздел:",
        reply_markup=keyboard
    )


@bot.message_handler(func=lambda message: True)
def menu(message):

    if message.text == "💎 Diamonds":
        bot.send_message(
            message.chat.id,
            "💎 Diamonds\n\nКаталог скоро загрузится из Vendoria."
        )

    elif message.text == "🎟 Vouchers":
        bot.send_message(
            message.chat.id,
            "🎟 Vouchers\n\nКаталог скоро загрузится из Vendoria."
        )

    elif message.text == "⭐ Monthly Pass":
        bot.send_message(
            message.chat.id,
            "⭐ Monthly Pass\n\nКаталог скоро загрузится из Vendoria."
        )

    elif message.text == "📦 Мои заказы":
        bot.send_message(
            message.chat.id,
            "📦 У вас пока нет заказов."
        )

    elif message.text == "💬 Поддержка":
        bot.send_message(
            message.chat.id,
            "💬 Поддержка ARES SHOP"
        )


bot.infinity_polling()
