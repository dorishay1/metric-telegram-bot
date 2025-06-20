# main.py

import os
import logging
import nest_asyncio
import google.generativeai as genai
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ConversationHandler, PicklePersistence
)

# Import all our handler functions from the other file
from bot_logic import *

# Apply the patch for the event loop
nest_asyncio.apply()

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

def main():
    """The main function to set up and run the bot."""
    
    # --- Get secret keys from environment variables ---
    # On Render, we will set these variables in the dashboard.
    TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

    if not TELEGRAM_TOKEN or not GOOGLE_API_KEY:
        logging.error("Missing required environment variables for API keys.")
        return
        
    # --- Configure AI Model ---
    genai.configure(api_key=GOOGLE_API_KEY)
    # Give the AI model to our bot_logic file so the functions there can use it.
    bot_logic.model = genai.GenerativeModel('gemini-1.5-flash-latest')
    logging.info("AI Model Configured.")

    # --- Set up Persistence ---
    # We will save the memory file in a 'data' subfolder.
    if not os.path.exists('data'):
        os.makedirs('data')
    persistence = PicklePersistence(filepath="data/metric_persistence")

    # --- Create the Telegram Application ---
    application = Application.builder().token(TELEGRAM_TOKEN).persistence(persistence).build()

    # --- Define Conversation Handlers (the "flowcharts") ---
    onboarding_conv = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            GATHERING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            GATHERING_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_goal)],
            PLAN_APPROVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_plan_feedback)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        persistent=True, name="onboarding_v1"
    )
    
    add_habit_conv = ConversationHandler(
        entry_points=[CommandHandler('addhabit', add_habit_start)],
        states={
            NEW_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_goal)],
            NEW_PLAN_APPROVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_plan_feedback)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        persistent=True, name="add_habit_v1"
    )

    # --- Add all handlers to the application ---
    application.add_handler(onboarding_conv)
    application.add_handler(add_habit_conv)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_general_message))

    # --- Run the bot ---
    logging.info("Bot is starting...")
    application.run_polling()


if __name__ == '__main__':
    main()