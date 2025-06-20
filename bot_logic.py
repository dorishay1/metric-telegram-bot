# bot_logic.py

import logging
import json
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
import google.generativeai as genai

# We need to get the AI model, which will be passed from main.py
# This is a placeholder that will be set by the main script.
model = None

# Define the states for our conversations
GATHERING_NAME, GATHERING_GOAL, PLAN_APPROVAL = range(3)
NEW_GOAL, NEW_PLAN_APPROVAL = range(3, 5)

# --- Onboarding Conversation Functions ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation and asks for the user's name if they are new."""
    if context.user_data and context.user_data.get('onboarding_complete'):
        await update.message.reply_text(f"Welcome back, {context.user_data['profile']['name']}! I'm ready for your updates. Use /addhabit to add a new goal.")
        return ConversationHandler.END

    await update.message.reply_text("Hello! I'm Metric, your new AI accountability coach. To get started, what should I call you?")
    return GATHERING_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the name, saves it, and asks for the first habit."""
    context.user_data['profile'] = {'name': update.message.text, 'language': 'English'} # Default language
    await context.application.persistence.flush()
    logging.info(f"Saved profile for user {update.effective_user.id}")
    await update.message.reply_text(f"Got it, {update.message.text}. Now, what is the first habit you want to build? Tell me in one sentence.")
    return GATHERING_GOAL

async def get_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Takes the goal, generates a blueprint and a plan, and asks for approval."""
    user_goal = update.message.text
    await update.message.reply_text("Okay, analyzing that goal and creating a plan...")

    blueprint_prompt = f"Analyze this goal: '{user_goal}'. Extract components into a JSON with keys: 'habit_name', 'core_action', 'trigger_condition'. Respond ONLY with the JSON object."
    blueprint_response = model.generate_content(blueprint_prompt)
    context.user_data['new_habit_blueprint'] = blueprint_response.text.strip()
    
    plan_prompt = f"""You are Metric, an AI assistant. Create a "Bot Action Plan" for the habit defined by this blueprint: {context.user_data['new_habit_blueprint']}. The plan must state what YOU, the bot, will do. Ask for the user's approval."""
    plan_response = model.generate_content(plan_prompt)
    context.user_data['new_habit_plan'] = plan_response.text
    
    await update.message.reply_text("Here is the plan I've devised:\n\n" + plan_response.text)
    return PLAN_APPROVAL

async def get_plan_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user's feedback on the plan and concludes onboarding."""
    feedback = update.message.text.lower()
    if 'yes' in feedback:
        context.user_data['active_habits'] = [{"blueprint": context.user_data['new_habit_blueprint'], "plan": context.user_data['new_habit_plan']}]
        context.user_data['onboarding_complete'] = True
        await update.message.reply_text("Excellent. Plan accepted. I've saved everything to my permanent memory. You can now chat with me normally or use /addhabit.")
        await context.application.persistence.flush()
        return ConversationHandler.END
    else:
        await update.message.reply_text("Understood. Let's scrap that plan. You can start over by typing /start.")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Action cancelled.")
    return ConversationHandler.END

# --- Add New Habit Functions ---
async def add_habit_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for adding a new habit."""
    await update.message.reply_text("Okay, let's build a new habit. What's the goal?")
    return NEW_GOAL

async def get_new_goal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # This function is very similar to get_goal, so we reuse the logic
    # In a larger app, we would make this a single shared function
    user_goal = update.message.text
    await update.message.reply_text("Analyzing goal and creating a new Bot Action Plan...")
    blueprint_json = f'{{"habit_name": "{user_goal[:30]}", "core_action": "{user_goal}"}}'
    plan = f"Okay, my action plan for '{user_goal}' is to ask you about it daily. Does this work?"
    context.user_data['new_habit_blueprint'] = blueprint_json
    context.user_data['new_habit_plan'] = plan
    await update.message.reply_text("Here is the new plan I've devised:\n\n" + plan)
    return NEW_PLAN_APPROVAL

async def get_new_plan_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the newly approved habit."""
    if 'yes' in update.message.text.lower():
        new_habit = {"blueprint": context.user_data['new_habit_blueprint'], "plan": context.user_data['new_habit_plan']}
        context.user_data['active_habits'].append(new_habit)
        await context.application.persistence.flush()
        await update.message.reply_text("Done. I've added the new habit to your profile.")
    else:
        await update.message.reply_text("Okay, I've scrapped that plan.")
    return ConversationHandler.END

# --- General Message Handler ---
async def handle_general_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The main handler for all other messages."""
    user_input = update.message.text
    user_name = context.user_data.get('profile', {}).get('name', 'User')
    response_prompt = f"You are Metric, a sarcastic AI coach talking to {user_name}. Their message is: '{user_input}'. Provide a short, witty, in-character response."
    ai_response = model.generate_content(response_prompt)
    await update.message.reply_text(ai_response.text)