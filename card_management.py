import os
import json
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, filters, ConversationHandler
from telegram.ext import PicklePersistence

# Define states for ConversationHandler
NAME, DESCRIPTION, POINTS, PHOTO = range(4)

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Global variables
config = {}
user_data = {}

# Load configuration
def load_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        logging.info(f"Config loaded: {data}")
        return data

# Load card data
def load_card_data():
    try:
        with open('card_data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"CARDS_DESCRIPTION": {}, "CARDS_POINTS": {}}

# Save card data
def save_card_data(data):
    with open('card_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Load user data
def load_user_data():
    try:
        with open('user_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            data["user_last_card_time"] = {k: datetime.fromisoformat(v) for k, v in data["user_last_card_time"].items()}
            data["promo_codes"] = {k: datetime.fromisoformat(v) for k, v in data["promo_codes"].items()}
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"user_points": {}, "user_cards": {}, "user_last_card_time": {}, "promo_codes": {}}

# Save user data
def save_user_data(data):
    data_to_save = {
        "user_points": data["user_points"],
        "user_cards": data["user_cards"],
        "user_last_card_time": {k: v.isoformat() for k, v in data["user_last_card_time"].items()},
        "promo_codes": {k: v.isoformat() for k, v in data["promo_codes"].items()}
    }
    with open('user_data.json', 'w', encoding='utf-8') as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=4)

# Handle the /reload_cards command
async def reload_cards(update: Update, context: CallbackContext):
    global config
    user_id = str(update.message.from_user.id)
    if user_id not in config.get("AUTHORIZED_USERS", []):
        await update.message.reply_text(config.get("PROMO_NOT_AUTHORIZED_TEXT", "You are not authorized to use this command."))
        return

    # Reload card data
    config = load_config()
    card_data = load_card_data()

    await update.message.reply_text(config.get("CARDS_RELOADED_TEXT", "Cards and config have been reloaded successfully!"))

# Handle the /reload_save command
async def reload_save(update: Update, context: CallbackContext):
    global user_data
    user_id = str(update.message.from_user.id)
    if user_id not in config.get("AUTHORIZED_USERS", []):
        await update.message.reply_text(config.get("PROMO_NOT_AUTHORIZED_TEXT", "You are not authorized to use this command."))
        return

    # Reload user data
    user_data = load_user_data()

    await update.message.reply_text("User data has been reloaded successfully!")

def create_handlers():
    return [
        CommandHandler("reload_cards", reload_cards),
        CommandHandler("reload_save", reload_save)
    ]
