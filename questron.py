import os
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from dotenv import load_dotenv
from telegram.error import BadRequest
import asyncio

# Load Environment Variables
load_dotenv()

# API Credentials
TOKEN = os.getenv("TOKEN")
SEGMIND_API_KEY = os.getenv("SEGMIND_API_KEY")

if not TOKEN or not SEGMIND_API_KEY:
    raise ValueError("Missing API credentials. Check your .env file.")

# Segmind API URL
SEGMIND_API_URL = "https://api.segmind.com/v1/gpt-4o"

# Global variable to track ongoing requests
ongoing_requests = {}

# Function to handle Segmind API request
def segmind_chat(messages):
    headers = {'x-api-key': SEGMIND_API_KEY}
    data = {"messages": messages}
    response = requests.post(SEGMIND_API_URL, json=data, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Segmind API Error: {response.status_code} - {response.text}")

# Command Handlers
async def start(update: Update, context: CallbackContext):
    await update.message.reply_text("Hello! I'm an AI-powered bot. Send me a message and I'll respond!")

async def help_command(update: Update, context: CallbackContext):
    await update.message.reply_text("Just send me any message and I'll generate a response using AI!")

async def stop_command(update: Update, context: CallbackContext):
    chat_id = update.message.chat_id
    if chat_id in ongoing_requests:
        ongoing_requests[chat_id].cancel()
        del ongoing_requests[chat_id]
        await update.message.reply_text("Response generation stopped.")
    else:
        await update.message.reply_text("No ongoing request to stop.")

# Message Handler
async def chat(update: Update, context: CallbackContext):
    user_message = update.message.text
    chat_id = update.message.chat_id
    initial_message = None

    try:
        initial_message = await update.message.reply_text("Generating response...")
        
        # Prepare messages for Segmind API
        messages = [
            {"role": "user", "content": user_message}
        ]
        
        # Create a task for the API call
        task = asyncio.create_task(fetch_segmind_response(chat_id, messages, initial_message, context))
        ongoing_requests[chat_id] = task
        await task

    except asyncio.CancelledError:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=initial_message.message_id,
            text="Response generation stopped."
        )
    except Exception as e:
        error_msg = "⚠️ An unexpected error occurred. Please try again."
        if initial_message:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=initial_message.message_id,
                    text=error_msg
                )
            except BadRequest:
                await update.message.reply_text(error_msg)
        else:
            await update.message.reply_text(error_msg)
        print(f"Unexpected Error: {e}")
    finally:
        if chat_id in ongoing_requests:
            del ongoing_requests[chat_id]

# Helper function to fetch Segmind response
async def fetch_segmind_response(chat_id, messages, initial_message, context):
    try:
        response = await asyncio.to_thread(segmind_chat, messages)
        bot_reply = response.get("choices", [{}])[0].get("message", {}).get("content", "Sorry, I didn't get a response from the AI.")
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=initial_message.message_id,
            text=bot_reply
        )
    except Exception as e:
        raise e

# Main Application
def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
