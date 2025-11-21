import logging
import sqlite3
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters

DB_NAME = 'group_market.db'
ADMIN_ID = 7716902802

USER_DATA = {}
USER_STEPS = {}

STEP_TYPE = 1
STEP_NAME = 2
STEP_MEMBERS = 3
STEP_DATE = 4
STEP_PRICE = 5
STEP_CONTACT = 6

ADMIN_STEP_DELETE = 10
ADMIN_STEP_BROADCAST = 11

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def get_main_keyboard():
    keyboard = [
        ["ማስታወቂያ መለጠፍ 📝", "ማስታወቂያዎችን መመልከት 🔍"],
        ["የቦት ስታተስቲክስ 📊"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def track_user(user):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO users (user_id, first_name, username) VALUES (?, ?, ?)',
                  (user.id, user.first_name, user.username))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"User tracking failed: {e}")

def init_db():
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS group_ads (
            ad_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            username TEXT,
            ad_type TEXT,
            group_name TEXT,
            member_count INTEGER,
            start_date TEXT,
            price REAL,
            contact TEXT,
            status TEXT DEFAULT 'ACTIVE'
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    track_user(user)
    welcome_message = f"ሰላም {user.first_name}! 👋\n\nወደ P2P የድሮ ግሩፖች ማርኬት እንኳን ደህና መጡ።\nከታች ያሉትን ቋሚ በተኖች በመጠቀም ማስታወቂያ ይለጥፉ።"
    await update.message.reply_text(welcome_message, reply_markup=get_main_keyboard())

async def final_ad_submission(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    data = USER_DATA[user_id]
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''INSERT INTO group_ads (user_id, username, ad_type, group_name, member_count, start_date, price, contact, status)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')''',
                  (user_id, update.effective_user.username or "Unknown", data['type'], data['name'], 
                   data['members'], data['start_date'], data['price'], data['contact']))
        conn.commit()
        ad_id = c.lastrowid
        conn.close()
        await update.message.reply_text(f"✅ ማስታወቂያዎ በስኬት ተለጠፈ!\nID: {ad_id}\nታይ: {data['type']}\nስሙ: {data['name']}\nዋጋ: {data['price']}", 
                                        reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Ad submission failed: {e}")
        await update.message.reply_text("❌ ስህተት! እንደገና ሞክሩ።", reply_markup=get_main_keyboard())
    
    if user_id in USER_DATA:
        del USER_DATA[user_id]
    if user_id in USER_STEPS:
        del USER_STEPS[user_id]

async def post_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    USER_DATA[user_id] = {}
    USER_STEPS[user_id] = STEP_TYPE
    keyboard = [["SELL", "BUY"], ["Cancel"]]
    await update.message.reply_text("1/6: ማስታወቂያ አይነት ይምረጡ:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def browse_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT ad_id, ad_type, group_name, member_count, price, contact FROM group_ads WHERE status='ACTIVE'")
        ads = c.fetchall()
        conn.close()
        if not ads:
            await update.message.reply_text("📭 ምንም ማስታወቂያ የለም።", reply_markup=get_main_keyboard())
            return
        message = "📋 ንቅ ያሉ ማስታወቂያዎች:\n\n"
        for ad in ads:
            message += f"🔹 ID: {ad[0]}\n   አይነት: {ad[1]}\n   ስም: {ad[2]}\n   አባላት: {ad[3]}\n   ዋጋ: {ad[4]}\n   ውጤት: {ad[5]}\n\n"
        await update.message.reply_text(message, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Browse ads failed: {e}")
        await update.message.reply_text("❌ ስህተት!", reply_markup=get_main_keyboard())

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM group_ads WHERE status='ACTIVE'")
        ad_count = c.fetchone()[0]
        conn.close()
        stats_message = f"📊 የቦት ስታትስቲክስ:\n\n👥 ጠቅላላ ተጠቃሚዎች: {user_count}\n📝 ንቅ ማስታወቂያዎች: {ad_count}"
        await update.message.reply_text(stats_message, reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"Stats failed: {e}")
        await update.message.reply_text("❌ ስህተት!", reply_markup=get_main_keyboard())

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ አንተ አድሚን አይደለህም።")
        return
    keyboard = [["ማስታወቂያ ሰርዝ 🗑️", "መልዕክት አስተላልፍ 📣"], ["ወደ ዋናው ማውጫ 🏠"]]
    await update.message.reply_text("🔐 አድሚን ፓነል", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def admin_delete_ad_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    USER_STEPS[update.effective_user.id] = ADMIN_STEP_DELETE
    await update.message.reply_text("ለመሰረዝ ማስታወቂያ ID ያስገቡ:", reply_markup=ReplyKeyboardRemove())

async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    USER_STEPS[update.effective_user.id] = ADMIN_STEP_BROADCAST
    await update.message.reply_text("ለተጠቃሚዎች መላክ የሚፈልጉትን መልዕክት ያስገቡ:", reply_markup=ReplyKeyboardRemove())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if text == "ወደ ዋናው ማውጫ 🏠":
        await update.message.reply_text("ወደ ዋናው ሜኑ ተመልሱ።", reply_markup=get_main_keyboard())
        if user_id in USER_STEPS:
            del USER_STEPS[user_id]
        return
    
    if text == "Cancel":
        await update.message.reply_text("ተወዳደርዋል።", reply_markup=get_main_keyboard())
        if user_id in USER_DATA:
            del USER_DATA[user_id]
        if user_id in USER_STEPS:
            del USER_STEPS[user_id]
        return
    
    if user_id not in USER_STEPS:
        return
    
    current_step = USER_STEPS.get(user_id)
    cancel_keyboard = ReplyKeyboardMarkup([["Cancel"]], resize_keyboard=True)
    
    if current_step == ADMIN_STEP_DELETE:
        try:
            ad_id = int(text)
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE group_ads SET status='DELETED' WHERE ad_id=?", (ad_id,))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"✅ ማስታወቂያ {ad_id} ተሰርዟል።", reply_markup=get_main_keyboard())
        except Exception:
            await update.message.reply_text("❌ ይህ ሃይ ማስታወቂያ ID አይደለም።")
        del USER_STEPS[user_id]
        return
    
    if current_step == ADMIN_STEP_BROADCAST:
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("SELECT user_id FROM users")
            users = c.fetchall()
            conn.close()
            await update.message.reply_text(f"✅ መልዕክት ለ {len(users)} ተጠቃሚዎች ተላከ።", reply_markup=get_main_keyboard())
        except Exception:
            await update.message.reply_text("❌ ብሮድካስት ስህተት።")
        del USER_STEPS[user_id]
        return
    
    if current_step == STEP_TYPE:
        if text in ["SELL", "BUY"]:
            USER_DATA[user_id]['type'] = text
            USER_STEPS[user_id] = STEP_NAME
            await update.message.reply_text("2/6: የግሩፕ ስም ያስገቡ", reply_markup=cancel_keyboard)
        else:
            await update.message.reply_text("SELL ወይም BUY ይምረጡ።")
    elif current_step == STEP_NAME:
        USER_DATA[user_id]['name'] = text
        USER_STEPS[user_id] = STEP_MEMBERS
        await update.message.reply_text("3/6: አባላት ብዛት ያስገቡ", reply_markup=cancel_keyboard)
    elif current_step == STEP_MEMBERS:
        try:
            members = int(text)
            USER_DATA[user_id]['members'] = members
            USER_STEPS[user_id] = STEP_DATE
            await update.message.reply_text("4/6: የተቋቋመበት ቀን ያስገቡ", reply_markup=cancel_keyboard)
        except ValueError:
            await update.message.reply_text("የአባላት ብዛት ቁጥር መሆን አለበት።")
    elif current_step == STEP_DATE:
        USER_DATA[user_id]['start_date'] = text
        USER_STEPS[user_id] = STEP_PRICE
        await update.message.reply_text("5/6: ዋጋ ያስገቡ", reply_markup=cancel_keyboard)
    elif current_step == STEP_PRICE:
        try:
            price = float(text)
            if price < 0:
                raise ValueError
            USER_DATA[user_id]['price'] = price
            USER_STEPS[user_id] = STEP_CONTACT
            await update.message.reply_text("6/6: ውጤትዎን ያስገቡ (@username ወይም ስልክ)", reply_markup=cancel_keyboard)
        except ValueError:
            await update.message.reply_text("ዋጋ ትክክለኛ ቁጥር መሆን አለበት።")
    elif current_step == STEP_CONTACT:
        USER_DATA[user_id]['contact'] = text
        await final_ad_submission(update, context, user_id)

def main():
    global application
    init_db()
    
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set.")
        raise EnvironmentError("BOT_TOKEN is missing!")
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("post_ad", post_ad))
    application.add_handler(CommandHandler("browse_ads", browse_ads))
    
    application.add_handler(MessageHandler(filters.Regex("^ማስታወቂያ መለጠፍ 📝$"), post_ad))
    application.add_handler(MessageHandler(filters.Regex("^ማስታወቂያዎችን መመልከት 🔍$"), browse_ads))
    application.add_handler(MessageHandler(filters.Regex("^የቦት ስታተስቲክስ 📊$"), show_stats))
    
    application.add_handler(MessageHandler(filters.Regex("^ማስታወቂያ ሰርዝ 🗑️$"), admin_delete_ad_start))
    application.add_handler(MessageHandler(filters.Regex("^መልዕክት አስተላልፍ 📣$"), admin_broadcast_start))
    
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    webhook_url = os.environ.get("WEBHOOK_URL", "").strip()
    port = int(os.environ.get("PORT", 8000))
    
    if webhook_url and len(webhook_url) > 10:
        logger.info("✅ Webhook Mode - Render.com 24/7")
        application.run_webhook(listen="0.0.0.0", port=port, url_path="/webhook", webhook_url=webhook_url)
    else:
        logger.info("✅ Polling Mode - Local Development (Replit)")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.error(f"Bot error: {e}")
        raise
