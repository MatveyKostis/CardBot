from collections import Counter
import logging
import json
import random
import os
import sys
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, PicklePersistence, CallbackContext
from card_management import create_handlers, load_config

def find_file_with_extensions(base_path, extensions):
    for ext in extensions:
        file_path = f"{base_path}.{ext}"
        if os.path.isfile(file_path):
            return file_path
    return None

def load_user_data():
    try:
        with open('user_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            data["user_last_card_time"] = {k: datetime.fromisoformat(v) for k, v in data.get("user_last_card_time", {}).items()}
            data["promo_codes"] = {k: datetime.fromisoformat(v) for k, v in data.get("promo_codes", {}).items()}
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "user_points": {},
            "user_cards": {},
            "user_last_card_time": {},
            "promo_codes": {},
            "user_favorite_card": {}
        }

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

config = load_config()
user_data = load_user_data()

def save_user_data(data):
    data_to_save = {
        "user_points": data["user_points"],
        "user_cards": data["user_cards"],
        "user_last_card_time": {k: v.isoformat() for k, v in data["user_last_card_time"].items()},
        "promo_codes": {k: v.isoformat() for k, v in data["promo_codes"].items()},
        "user_favorite_card": data.get("user_favorite_card", {})  # Save favorite card data
    }
    with open('user_data.json', 'w', encoding='utf-8') as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=4)

async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Hello! Use the /addcard command to catch cards and /checkcard to view your cards.")

async def reload_all(update: Update, context):

    user_id = str(update.message.from_user.id)

    if user_id not in config["AUTHORIZED_USERS"]:
        await update.message.reply_text(config["PROMO_NOT_AUTHORIZED_TEXT"])
        return
        
    await update.message.reply_text("Restarting the bot...")

    os.execv(sys.executable, ['python'] + sys.argv)

async def add_card(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    current_time = datetime.now()

    if user_id not in user_data["user_last_card_time"]:
        user_data["user_last_card_time"][user_id] = current_time - timedelta(seconds=config.get("WAIT_INTERVAL", 3600))

    last_card_time = user_data["user_last_card_time"][user_id]
    if (current_time - last_card_time).total_seconds() < config.get("WAIT_INTERVAL", 3600):
        wait_time = config["WAIT_INTERVAL"] - (current_time - last_card_time).total_seconds()
        await update.message.reply_text(config.get("WAIT_TIME_TEXT", "Please wait {time} seconds before catching another card").format(time=int(wait_time)))
        return

    if user_id not in user_data["user_cards"]:
        user_data["user_cards"][user_id] = []

    card_name = random.choice(list(config.get("CARDS_DESCRIPTION", {}).keys()))
    user_data["user_cards"][user_id].append(card_name)
    card_points = config["CARDS_POINTS"].get(card_name, 0)
    user_data["user_points"][user_id] = user_data["user_points"].get(user_id, 0) + card_points

    card_description = config["CARDS_DESCRIPTION"].get(card_name, "Description not found")
    card_path_base = f"{config.get('CARDS_PATH', '')}/{card_name}"
    
    file_path = find_file_with_extensions(card_path_base, ["jpg", "jpeg", "png"])

    duplicate_message = ""
    if user_data["user_cards"][user_id].count(card_name) > 1:
        duplicate_message = "\nYou already have this card; only points will be awarded."

    if file_path:
        with open(file_path, 'rb') as photo:
            await update.message.reply_photo(photo=photo, caption=f"{config.get('ADD_CARD_TEXT', 'You have received a new card!')}\n\n{card_description}{duplicate_message}")
    else:
        await update.message.reply_text("Image file not found.")

    await update.message.reply_text(config.get("POINTS_MESSAGE", "Your points: {points}").format(points=user_data["user_points"][user_id]))
    user_data["user_last_card_time"][user_id] = current_time
    save_user_data(user_data)

async def check_card(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    if user_id not in user_data["user_cards"] or not user_data["user_cards"][user_id]:
        await update.message.reply_text(config.get("NO_CARDS_TEXT", "You have no cards."))
        return

    card_counter = Counter(user_data["user_cards"][user_id])
    keyboard = []

    for card, count in card_counter.items():
        card_name = config["CARDS_DESCRIPTION"].get(card, card)
        card_points = config["CARDS_POINTS"].get(card, 0)
        if count > 1:
            card_name += f" ({count} duplicates)"
        keyboard.append([InlineKeyboardButton(f"{card_name} - {card_points} points", callback_data=card)])

    total_points = user_data["user_points"].get(user_id, 0)
    keyboard.append([InlineKeyboardButton(f"Total points: {total_points}", callback_data="total_points")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(config.get("CHOOSE_CARD_TEXT", "Choose a card:"), reply_markup=reply_markup)

async def show_photo(update: Update, context: CallbackContext):
    query = update.callback_query
    card_name = query.data

    card_path_base = f"{config.get('CARDS_PATH', '')}/{card_name}"
    file_path = find_file_with_extensions(card_path_base, ["jpg", "jpeg", "png"])

    card_description = config["CARDS_DESCRIPTION"].get(card_name, "Description not found")
    card_points = config["CARDS_POINTS"].get(card_name, 0)

    if file_path:
        with open(file_path, 'rb') as photo:
            await query.message.reply_photo(
                photo=photo,
                caption=f"{card_description}\n\nPoints: {card_points}"
            )
    else:
        await query.message.reply_text("Image file not found.")

    await query.answer()
    
async def handle_message(update: Update, context: CallbackContext):
    text = update.message.text.lower()
    trigger_texts = config.get("TRIGGER_TEXT", {})
    
    for command, phrases in trigger_texts.items():
        phrases_list = [phrase.strip().lower() for phrase in phrases.split(",")]
        if text in phrases_list:
            if command == "addcard":
                await add_card(update, context)
            elif command == "checkcard":
                await check_card(update, context)
            elif command == "account":
                await account(update, context)
            # You can add additional commands and their handling here
            return

async def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data

    if data == "total_points":
        user_id = str(query.from_user.id)
        total_points = user_data["user_points"].get(user_id, 0)
        await query.message.reply_text(f"Total points: {total_points}")
        await query.answer()
    else:
        # Handle cards
        card_name = data
        card_path_base = f"{config.get('CARDS_PATH', '')}/{card_name}"
        file_path = find_file_with_extensions(card_path_base, ["jpg", "jpeg", "png"])

        card_description = config["CARDS_DESCRIPTION"].get(card_name, "Description not found")
        card_points = config["CARDS_POINTS"].get(card_name, 0)

        if file_path:
            with open(file_path, 'rb') as photo:
                await query.message.reply_photo(
                    photo=photo,
                    caption=f"{card_description}\n\nPoints: {card_points}"
                )
        else:
            await query.message.reply_text("Image file not found.")

        await query.answer()

async def favorite_card(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    
    if user_id not in user_data["user_cards"] or not user_data["user_cards"][user_id]:
        await update.message.reply_text("You have no cards to choose from.")
        return

    card_counter = Counter(user_data["user_cards"][user_id])
    keyboard = []
    
    for card, count in card_counter.items():
        card_name = config["CARDS_DESCRIPTION"].get(card, card)
        keyboard.append([InlineKeyboardButton(card_name, callback_data=f"favorite_{card}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose your favorite card:", reply_markup=reply_markup)

async def set_favorite_card(update: Update, context: CallbackContext):
    query = update.callback_query
    data = query.data

    if data.startswith("favorite_"):
        user_id = str(query.from_user.id)
        card_name = data[len("favorite_"):]

        if card_name not in user_data["user_cards"].get(user_id, []):
            await query.message.reply_text("You can only set a favorite card if you own it.")
            return

        user_data["user_favorite_card"][user_id] = card_name
        save_user_data(user_data)

        await query.message.reply_text(f"Favorite card set to: {config['CARDS_DESCRIPTION'].get(card_name, card_name)}")
        await query.answer()

async def account(update: Update, context: CallbackContext):
    user_id = str(update.message.from_user.id)
    cards = user_data["user_cards"].get(user_id, [])
    points = user_data["user_points"].get(user_id, 0)
    
    card_count = len(cards)
    rank = "Beginner Collector"
    if card_count >= 60:
        rank = "King of collectors"
    elif card_count >= 30:
        rank = "Cool collector"
    elif card_count >= 20:
        rank = "Senior Collector"
    elif card_count >= 10:
        rank = "Collector"
    elif card_count >= 5:
        rank = "Novice"
    
    await update.message.reply_text(f"Hello {update.message.from_user.first_name}👋\n\nYou have: {card_count} cards🃏\nTotal points: {points}✨\nYour rank: {rank}")

def main():
    application = Application.builder().token(config.get("API_TOKEN")).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reload_all", reload_all))
    application.add_handler(CommandHandler("account", account))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CommandHandler("favorite", favorite_card))
    application.add_handler(CallbackQueryHandler(set_favorite_card))

    application.run_polling()

if __name__ == '__main__':
    main()
