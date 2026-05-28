import os
import asyncio
import json
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Получаем переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
API_KEY = os.environ.get("API_KEY")
API_URL = os.environ.get("API_URL", "https://api.freemodel.dev/v1/chat/completions")
API_MODEL = os.environ.get("API_MODEL", "gpt-3.5-turbo")

# Проверка токена
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных окружения")

if not API_KEY:
    print("⚠️ ВНИМАНИЕ: API_KEY не задан! Бот будет работать, но AI не ответит.")

# Хранилище истории диалогов (в памяти)
user_histories = {}

# Клавиатура
def get_main_keyboard():
    keyboard = [
        [InlineKeyboardButton("🗑 Очистить историю", callback_data="clear")],
        [InlineKeyboardButton("🔄 Новая тема", callback_data="new_topic")],
        [InlineKeyboardButton("ℹ️ Инфо", callback_data="info")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    
    welcome_text = (
        f"🤖 *Привет, {update.effective_user.first_name}!*\n\n"
        f"Я AI-ассистент. Задавай любые вопросы!\n\n"
        f"📌 *Информация:*\n"
        f"• Модель: `{API_MODEL}`\n"
        f"• API: `{API_URL.split('/')[2] if API_URL else 'не указан'}`\n\n"
        f"Нажми на кнопки внизу, чтобы управлять диалогом."
    )
    
    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *Помощь*\n\n"
        "• Просто напиши сообщение - я отвечу\n"
        "• /clear - очистить историю диалога\n"
        "• /new - начать новую тему\n"
        "• /info - информация о боте\n"
        "• /help - это сообщение"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# Очистка истории
async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text("🗑 История диалога очищена!")

# Новая тема
async def new_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text(
        "🔄 Начинаем новую тему! Предыдущий контекст очищен.",
        reply_markup=get_main_keyboard()
    )

# Информация
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    history_len = len(user_histories.get(user_id, []))
    
    info_text = (
        f"ℹ️ *Информация*\n\n"
        f"• Ваш ID: `{user_id}`\n"
        f"• Сообщений в истории: `{history_len}`\n"
        f"• Модель: `{API_MODEL}`\n"
        f"• API: `{API_URL.split('/')[2] if API_URL else 'не указан'}`\n\n"
        f"✅ Бот работает исправно!"
    )
    
    await update.message.reply_text(info_text, parse_mode="Markdown")

# Обработка кнопок
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if query.data == "clear":
        user_histories[user_id] = []
        await query.edit_message_text("🗑 История очищена!", reply_markup=get_main_keyboard())
    elif query.data == "new_topic":
        user_histories[user_id] = []
        await query.edit_message_text("🔄 Новая тема! Контекст очищен.", reply_markup=get_main_keyboard())
    elif query.data == "info":
        history_len = len(user_histories.get(user_id, []))
        info_text = f"ℹ️ В истории {history_len} сообщений. Модель: {API_MODEL}"
        await query.edit_message_text(info_text, reply_markup=get_main_keyboard())

# Отправка запроса к AI
async def ask_ai(user_message: str, history: list) -> str:
    if not API_KEY:
        return "❌ API ключ не задан. Добавь переменную API_KEY в Railway."
    
    if not API_URL:
        return "❌ API URL не задан. Добавь переменную API_URL в Railway."
    
    # Формируем сообщения для API
    messages = []
    
    # Добавляем системный промпт
    messages.append({
        "role": "system",
        "content": "Ты полезный, дружелюбный AI-ассистент. Отвечай кратко и по делу."
    })
    
    # Добавляем историю (последние 10 сообщений)
    for msg in history[-10:]:
        messages.append(msg)
    
    # Добавляем текущее сообщение
    messages.append({"role": "user", "content": user_message})
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {API_KEY}"
                },
                json={
                    "model": API_MODEL,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 1000
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"]
                elif "response" in data:
                    return data["response"]
                else:
                    return json.dumps(data, ensure_ascii=False)[:500]
            else:
                error_text = f"Ошибка API: {response.status_code}\n{response.text[:200]}"
                print(error_text)
                return f"❌ Ошибка API: {response.status_code}"
                
    except httpx.TimeoutException:
        return "⏰ Таймаут. API отвечает слишком долго, попробуй позже."
    except Exception as e:
        print(f"Ошибка: {e}")
        return f"❌ Ошибка: {str(e)[:100]}"

# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
    if not API_KEY:
        await update.message.reply_text(
            "❌ API ключ не настроен!\n\n"
            "Добавь переменную `API_KEY` в Railway.",
            parse_mode="Markdown"
        )
        return
    
    # Отправляем статус "печатает"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # Сохраняем историю
    if user_id not in user_histories:
        user_histories[user_id] = []
    
    # Добавляем сообщение пользователя в историю
    user_histories[user_id].append({"role": "user", "content": user_message})
    
    # Получаем ответ от AI
    ai_response = await ask_ai(user_message, user_histories[user_id][:-1])
    
    # Сохраняем ответ в историю
    user_histories[user_id].append({"role": "assistant", "content": ai_response})
    
    # Отправляем ответ
    await update.message.reply_text(
        ai_response,
        reply_markup=get_main_keyboard()
    )

# Обработка ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"Ошибка: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("⚠️ Произошла ошибка. Попробуй позже.")

# Главная функция
def main():
    # Создаём приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clear", clear_history))
    application.add_handler(CommandHandler("new", new_topic))
    application.add_handler(CommandHandler("info", info))
    
    # Кнопки
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Сообщения
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Ошибки
    application.add_error_handler(error_handler)
    
    # Запуск
    print("🚀 Бот запущен и готов к работе!")
    print(f"📡 API URL: {API_URL}")
    print(f"🤖 Модель: {API_MODEL}")
    print(f"🔑 API Key: {'✅ задан' if API_KEY else '❌ не задан'}")
    print(f"🎮 Bot Token: {'✅ задан' if BOT_TOKEN else '❌ не задан'}")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
