import logging
import sqlite3
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters
from flask import Flask
from threading import Thread

# --- Global Configurations ---
DB_NAME = 'group_market.db'
# 📌 የተጠቃሚው የቴሌግራም መታወቂያ (User ID) እዚህ ገብቷል
ADMIN_ID = 7716902802

# --- State Management (የተጠቃሚን ሁኔታ ለመያዝ) ---
USER_DATA = {} # የአንድ ተጠቃሚ ጊዜያዊ ማስታወቂያ ውሂብ
USER_STEPS = {} # ተጠቃሚው ማስታወቂያ የማስገቢያ ሂደት የትኛው ደረጃ ላይ እንዳለ ለመያዝ

# --- የማስገቢያ ደረጃዎች (Steps) ---
STEP_TYPE = 1       # የማስታወቂያ አይነት (SELL/BUY)
STEP_NAME = 2       # የግሩፕ ስም
STEP_MEMBERS = 3    # የአባላት ብዛት
STEP_DATE = 4       # የተቋቋመበት ቀን
STEP_PRICE = 5      # ዋጋ
STEP_CONTACT = 6    # የእውቂያ አድራሻ (@username)

# --- የአድሚን ደረጃዎች (Admin Steps) ---
ADMIN_STEP_DELETE = 10
ADMIN_STEP_BROADCAST = 11

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ----------------------------------------------------
# 📌 KEEP-ALIVE ተግባራት (Replit እንዳይቆም የሚያደርግ)
# ----------------------------------------------------

app = Flask('')

@app.route('/')
def home():
    return "Bot is running and kept alive!"

def run():
    app.run(host='0.0.0.0',port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
    logger.info("Keep-Alive Web Server started on a separate thread.")

# ----------------------------------------------------
# 📌 HELPER FUNCTIONS (ረዳት ተግባራት)
# ----------------------------------------------------

def get_main_keyboard():
    """ሁልጊዜ የሚታየውን ዋናውን የቁልፍ ሰሌዳ ይመልሳል።"""
    keyboard = [
        ["ማስታወቂያ መለጠፍ 📝", "ማስታወቂያዎችን መመልከት 🔍"],
        ["የቦት ስታተስቲክስ 📊"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def track_user(user):
    """አዲስ ተጠቃሚ ወደ ዳታቤዝ ያስመዘግባል ወይም ያለውን ያድሳል።"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        # INSERT OR IGNORE አዲስ user ሲሆን ያስገባል፣ ከዚህ በፊት ካለ ዝም ይላል።
        c.execute('''
            INSERT OR IGNORE INTO users (user_id, first_name, username)
            VALUES (?, ?, ?)
        ''', (user.id, user.first_name, user.username))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"User tracking failed: {e}")

# ----------------------------------------------------
# 📌 CORE LOGIC - DATABASE SETUP
# ----------------------------------------------------

def init_db():
    """የግሩፕ ማስታወቂያዎችን እና የተጠቃሚዎችን ሰንጠረዦች ይፈጥራል።"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()

        # 1. Group Ads Table (ማስታወቂያዎች)
        c.execute('''
            CREATE TABLE IF NOT EXISTS group_ads (
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
            )
        ''')

        # 2. Users Table (የተጠቃሚዎች ዝርዝር ለስታትስ እና ብሮድካስት)
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT,
                username TEXT,
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

# ----------------------------------------------------
# 📌 COMMAND HANDLERS
# ----------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ቦቱን የሚጀምር እና ዋናውን ሜኑ የሚልክ ተግባር ነው።"""
    user = update.effective_user
    track_user(user) # ተጠቃሚውን መመዝገብ ወይም ማዘመን

    welcome_message = (
        f"ሰላም {user.first_name}! 👋\n\n"
        "ወደ P2P የድሮ ግሩፖች ማርኬት እንኳን ደህና መጡ።\n"
        "ከታች ያሉትን ቋሚ በተኖች በመጠቀም ማስታወቂያ ይለጥፉ፣ ያሉትን ይመልከቱ ወይም የቦቱን ስታተስቲክስ ይመልከቱ።"
    )

    # መልዕክቱን በቋሚው የButtons መልኩ መላክ
    await update.message.reply_text(welcome_message, reply_markup=get_main_keyboard())


async def final_ad_submission(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """የተሰበሰበውን ውሂብ ወደ ዳታቤዝ ያስቀምጣል።"""

    data = USER_DATA[user_id]
    
    # ሂደቱን ማጽዳት
    del USER_DATA[user_id]
    del USER_STEPS[user_id]

    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT INTO group_ads (user_id, username, ad_type, group_name, member_count, start_date, price, contact)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            update.effective_user.id, update.effective_user.username, data['ad_type'],
            data['group_name'], data['member_count'], data['start_date'], data['price'], data['contact']
        ))
        conn.commit()
        conn.close()

        # ስኬታማ መልእክት እና ወደ ዋናው ማውጫ መመለስ
        await update.message.reply_text(
            f"✅ ማስታወቂያዎ በተሳካ ሁኔታ ተመዝግቧል።\n\n"
            f"🏷️ ግሩፕ ስም: {data['group_name']}\n"
            f"💰 ዋጋ: {data['price']} ብር\n"
            f"👍 አሁን ወደ ዋናው ማውጫ ተመልሰዋል።",
            reply_markup=get_main_keyboard()
        )

    except Exception as e:
        logger.error(f"Ad submission failed: {e}")
        await update.message.reply_text(
            f"⚠️ የመመዝገብ ስህተት ተፈጥሯል: {e}\n\n"
            "ሂደቱ ተሰርዟል እና ወደ ዋናው ማውጫ ተመልሰዋል።",
            reply_markup=get_main_keyboard()
        )


async def post_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ማስታወቂያ ማስገባት ለመጀመር የመጀመሪያውን እርምጃ ይጠይቃል።"""
    user_id = update.effective_user.id

    # የድሮ ውሂብን ማጽዳት እና የመጀመሪያውን እርምጃ መጀመር
    USER_DATA[user_id] = {}
    USER_STEPS[user_id] = STEP_TYPE

    # የማስገቢያውን ሂደት የሚሰርዝበት አዝራር
    cancel_keyboard = ReplyKeyboardMarkup([["❌ መሰረዝ"]], resize_keyboard=True, one_time_keyboard=True)

    message = (
        "✅ ማስታወቂያ ማስገባት ተጀምሯል።\n"
        "**1/6:** ማስታወቂያዎ **'SELL' (መሸጥ)** ነው ወይስ **'BUY' (መግዛት)**? (ለምሳሌ፡ SELL) "
    )
    await update.message.reply_text(message, reply_markup=cancel_keyboard)


async def browse_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ሁሉንም ንቁ ማስታወቂያዎች ከዳታቤዝ አውጥቶ ያሳያል።"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('SELECT ad_id, ad_type, group_name, member_count, start_date, price, contact FROM group_ads WHERE status = ?', ('ACTIVE',))
        ads = c.fetchall()
        conn.close()

        if not ads:
            await update.message.reply_text("በአሁኑ ጊዜ ምንም ንቁ ማስታወቂያዎች የሉም።")
            return

        response = "📢 ንቁ የግሩፕ ማስታወቂያዎች:\n\n"
        for ad in ads:
            ad_id, ad_type, group_name, member_count, start_date, price, contact = ad
            response += (
                f"**#{ad_id} | {ad_type}**\n"
                f"🏷️ ግሩፕ ስም: {group_name}\n"
                f"👥 አባላት: {member_count}\n"
                f"⏳ የተመሠረተበት ቀን: {start_date}\n"
                f"💰 ዋጋ: {price} ብር\n"
                f"📞 ለመግዛት/ለመሸጥ: {contact}\n"
                f"--------------------------------------\n"
            )
        await update.message.reply_text(response)
    
    except Exception as e:
        logger.error(f"Error browsing ads: {e}")
        await update.message.reply_text(f"ማስታወቂያዎችን የማውጣት ስህተት ተፈጠረ።")


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """የቦቱን ስታተስቲክስ አውጥቶ ያሳያል።"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()

        # ጠቅላላ ተጠቃሚዎች
        c.execute('SELECT COUNT(user_id) FROM users')
        total_users = c.fetchone()[0]

        # ጠቅላላ ንቁ ማስታወቂያዎች
        c.execute("SELECT COUNT(ad_id) FROM group_ads WHERE status = 'ACTIVE'")
        total_ads = c.fetchone()[0]

        # የBUY ማስታወቂያዎች
        c.execute("SELECT COUNT(ad_id) FROM group_ads WHERE status = 'ACTIVE' AND ad_type = 'BUY'")
        buy_ads = c.fetchone()[0]

        # የSELL ማስታወቂያዎች
        c.execute("SELECT COUNT(ad_id) FROM group_ads WHERE status = 'ACTIVE' AND ad_type = 'SELL'")
        sell_ads = c.fetchone()[0]

        conn.close()

        response = (
            "📊 **የቦት ስታተስቲክስ:**\n"
            "-----------------------------\n"
            f"👤 ጠቅላላ ተጠቃሚዎች: **{total_users}**\n"
            f"📢 ጠቅላላ ንቁ ማስታወቂያዎች: **{total_ads}**\n"
            f"🛒 የገዢ (BUY) ማስታወቂያዎች: **{buy_ads}**\n"
            f"💸 የሻጭ (SELL) ማስታወቂያዎች: **{sell_ads}**\n"
            "-----------------------------"
        )
        await update.message.reply_text(response, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        await update.message.reply_text("ስታተስቲክስን የማውጣት ስህተት ተፈጠረ።")

# ----------------------------------------------------
# 📌 ADMIN PANEL HANDLERS
# ----------------------------------------------------

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """የአድሚን ፓነልን ያሳያል።"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("ይህ ኮማንድ ለአድሚኖች ብቻ የተፈቀደ ነው።")
        return

    # የአድሚን ፓናል buttons
    keyboard = [
        ["ማስታወቂያ ሰርዝ 🗑️", "መልዕክት አስተላልፍ 📣"],
        ["ወደ ዋናው ማውጫ 🏠"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "👑 የአድሚን መቆጣጠሪያ ፓናል 👑\n"
        "እባክዎ የሚፈልጉትን ተግባር ይምረጡ:",
        reply_markup=reply_markup
    )

async def admin_delete_ad_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """የማስታወቂያ መሰረዝ ሂደትን ይጀምራል።"""
    if update.effective_user.id != ADMIN_ID: return

    # Admin state set
    USER_STEPS[update.effective_user.id] = ADMIN_STEP_DELETE
    
    await update.message.reply_text(
        "🗑️ ለመሰረዝ የሚፈልጉትን ማስታወቂያ **Ad ID (ቁጥር)** ያስገቡ።\n"
        "የማስታወቂያዎችን ዝርዝር ለማየት /browse_ads ኮማንድ ይጠቀሙ።",
        reply_markup=ReplyKeyboardMarkup([["❌ መሰረዝ"]], resize_keyboard=True, one_time_keyboard=True)
    )

async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """መልዕክት የማስተላለፍ ሂደትን ይጀምራል።"""
    if update.effective_user.id != ADMIN_ID: return
    
    # Admin state set
    USER_STEPS[update.effective_user.id] = ADMIN_STEP_BROADCAST

    await update.message.reply_text(
        "📣 ለሁሉም የቦቱ ተጠቃሚዎች ሊያስተላልፉት የሚፈልጉትን መልዕክት አሁን ያስገቡ።",
        reply_markup=ReplyKeyboardMarkup([["❌ መሰረዝ"]], resize_keyboard=True, one_time_keyboard=True)
    )

# ----------------------------------------------------
# 📌 CORE LOGIC - MESSAGE HANDLER
# ----------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """በደረጃ በደረጃ የማስታወቂያ ማስገቢያ ሂደቱን እና የአድሚን ትዕዛዞችን ይቆጣጠራል።"""
    user_id = update.effective_user.id
    text = update.message.text.strip()

    current_step = USER_STEPS.get(user_id)
    
    # --- 1. 'Cancel' and 'Main Menu' Logic (የመሰረዝ ተግባር) ---
    if text in ["❌ መሰረዝ", "ወደ ዋናው ማውጫ 🏠"]:
        if user_id in USER_STEPS:
            del USER_STEPS[user_id]
        if user_id in USER_DATA:
            del USER_DATA[user_id]
        
        # ለአድሚን ፓናል የነበረውን ጊዜያዊ ኪቦርድ ማስወገድ
        if user_id == ADMIN_ID and text == "ወደ ዋናው ማውጫ 🏠":
            await start(update, context) # ወደ ዋናው ሜኑ መመለስ
            return
            
        await update.message.reply_text(
            "🛑 ሂደቱ ተሰርዟል። ወደ ዋናው ማውጫ ተመልሰዋል።",
            reply_markup=get_main_keyboard()
        )
        return

    # ማስታወቂያ ማስገቢያ ሂደት ላይ ካልሆነ ዝም ይላል
    if not current_step:
        return

    # --- 2. ADMIN HANDLER LOGIC (ለአድሚን ብቻ) ---
    if user_id == ADMIN_ID:
        if current_step == ADMIN_STEP_DELETE:
            try:
                ad_id = int(text)
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("UPDATE group_ads SET status = ? WHERE ad_id = ? AND status = 'ACTIVE'", ('DELETED', ad_id))
                rows_affected = c.rowcount
                conn.commit()
                conn.close()

                if rows_affected > 0:
                    await update.message.reply_text(
                        f"✅ ማስታወቂያ #{ad_id} በተሳካ ሁኔታ ተሰርዟል።",
                        reply_markup=get_main_keyboard()
                    )
                else:
                    await update.message.reply_text(f"ማስታወቂያ #{ad_id} አልተገኘም ወይም አስቀድሞ ተሰርዟል።")

            except ValueError:
                await update.message.reply_text("እባክዎ ትክክለኛውን የማስታወቂያ ቁጥር (Ad ID) ብቻ ያስገቡ።")
            finally:
                if user_id in USER_STEPS:
                    del USER_STEPS[user_id]

        elif current_step == ADMIN_STEP_BROADCAST:
            message_to_send = text
            
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            # የአድሚኑን user_id ሳያካትት መላክ
            c.execute('SELECT user_id FROM users WHERE user_id != ?', (ADMIN_ID,))
            all_users = [row[0] for row in c.fetchall()]
            conn.close()
            
            sent_count = 0
            for uid in all_users:
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"📣 **ከአድሚን መልዕክት:**\n\n{message_to_send}",
                        parse_mode='Markdown'
                    )
                    sent_count += 1
                except Exception:
                    # መልዕክት መላክ ያልተቻለባቸው ተጠቃሚዎች (ብዙውን ጊዜ ቦቱን አቁመዋል)
                    logger.warning(f"Failed to send broadcast to user {uid}.")

            await update.message.reply_text(
                f"✅ መልዕክቱ ለ**{sent_count}** ተጠቃሚዎች ተልኳል።\n"
                f"({len(all_users) - sent_count} አልተላከም - ምናልባት ቦቱን አቁመው ይሆናል።)",
                reply_markup=get_main_keyboard()
            )
            # Clear state
            if user_id in USER_STEPS:
                del USER_STEPS[user_id]
        
        return # አድሚን ከሆነ ከዚህ በላይ አይቀጥልም

    # --- 3. AD POSTING FLOW LOGIC (ማስታወቂያ መለጠፍ) ---
    
    # የማስገቢያውን ሂደት የሚሰርዝበት አዝራር
    cancel_keyboard = ReplyKeyboardMarkup([["❌ መሰረዝ"]], resize_keyboard=True, one_time_keyboard=True)
    
    if current_step == STEP_TYPE:
        ad_type = text.upper()
        if ad_type not in ['SELL', 'BUY']:
            await update.message.reply_text("የማስታወቂያው አይነት **SELL** ወይም **BUY** መሆን አለበት። እንደገና ያስገቡ።")
            return
        USER_DATA[user_id]['ad_type'] = ad_type
        USER_STEPS[user_id] = STEP_NAME
        await update.message.reply_text("2/6: የግሩፕ ስም ያስገቡ (ለምሳሌ: EthioTechMarket)", reply_markup=cancel_keyboard)

    elif current_step == STEP_NAME:
        USER_DATA[user_id]['group_name'] = text
        USER_STEPS[user_id] = STEP_MEMBERS
        await update.message.reply_text("3/6: የአባላት ብዛት ያስገቡ (በቁጥር ብቻ)", reply_markup=cancel_keyboard)

    elif current_step == STEP_MEMBERS:
        try:
            member_count = int(text)
            if member_count <= 0: raise ValueError
            USER_DATA[user_id]['member_count'] = member_count
            USER_STEPS[user_id] = STEP_DATE
            await update.message.reply_text("4/6: ግሩፑ የተቋቋመበትን ቀን ያስገቡ (ቅርጽ: YYYY-MM-DD)", reply_markup=cancel_keyboard)
        except ValueError:
            await update.message.reply_text("የአባላት ብዛት ትክክለኛ ቁጥር መሆን አለበት። እንደገና ያስገቡ።")

    elif current_step == STEP_DATE:
        USER_DATA[user_id]['start_date'] = text
        USER_STEPS[user_id] = STEP_PRICE
        await update.message.reply_text("5/6: የሚፈለገውን ዋጋ ያስገቡ (ለምሳሌ፡ 5000)", reply_markup=cancel_keyboard)

    elif current_step == STEP_PRICE:
        try:
            price = float(text)
            if price < 0: raise ValueError
            USER_DATA[user_id]['price'] = price
            USER_STEPS[user_id] = STEP_CONTACT
            await update.message.reply_text("6/6: እውቂያዎትን ያስገቡ (@username ወይም ስልክ ቁጥር)", reply_markup=cancel_keyboard)
        except ValueError:
            await update.message.reply_text("ዋጋው ትክክለኛ ቁጥር መሆን አለበት። እንደገና ያስገቡ።")

    elif current_step == STEP_CONTACT:
        USER_DATA[user_id]['contact'] = text
        
        # ሁሉንም ውሂብ ስላገኘን ማስታወቂያውን ወደ ዳታቤዝ እንልካለን
        await final_ad_submission(update, context, user_id)


# ----------------------------------------------------
# 📌 MAIN FUNCTION
# ----------------------------------------------------

def main():
    """ቦቱን በ Long Polling ያስጀምራል።"""

    init_db() # ዳታቤዝ ይፈጥራል

    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set. Please set it in Replit Secrets.")
        raise EnvironmentError("BOT_TOKEN is missing!")

    application = Application.builder().token(BOT_TOKEN).build()

    # --- 1. COMMAND HANDLERS ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("post_ad", post_ad))
    application.add_handler(CommandHandler("browse_ads", browse_ads))
    
    # --- 2. MAIN MENU BUTTON HANDLERS (ከቋሚው ኪቦርድ) ---
    application.add_handler(MessageHandler(filters.Regex('^ማስታወቂያ መለጠፍ 📝$'), post_ad))
    application.add_handler(MessageHandler(filters.Regex('^ማስታወቂያዎችን መመልከት 🔍$'), browse_ads))
    application.add_handler(MessageHandler(filters.Regex('^የቦት ስታተስቲክስ 📊$'), show_stats))

    # --- 3. ADMIN PANEL BUTTON HANDLERS ---
    application.add_handler(MessageHandler(filters.Regex('^ማስታወቂያ ሰርዝ 🗑️$'), admin_delete_ad_start))
    application.add_handler(MessageHandler(filters.Regex('^መልዕክት አስተላልፍ 📣$'), admin_broadcast_start))
    # 'ወደ ዋናው ማውጫ 🏠' በ handle_message ውስጥ ይያዛል

    # --- 4. CORE MESSAGE HANDLER (የማስታወቂያ ሂደት እና ሌሎች መልዕክቶችን ይይዛል) ---
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    logger.info("P2P Group Market Bot Started (Long Polling).")

    # ቦቱን በ Long Polling ማስኬድ
    application.run_polling(poll_interval=3)

if __name__ == '__main__':
    keep_alive() # ዌብሰርቨሩን ለብቻው በክር ይጀምራል (Keep-Alive)
    main() # ቦቱ በዋናው ክር ላይ መስራቱን ይቀጥላል
