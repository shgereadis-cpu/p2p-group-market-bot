import logging
import sqlite3
import os
from telegram import Update, ForceReply
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters

# --- Global Configurations ---
# ⚠️ Heroku ላይ ዳታውን ከሚያስወግድ SQLite ይልቅ MongoDB (ወይም PostgreSQL) መጠቀም ይመከራል!
DB_NAME = 'group_market.db'
VERIFICATION_CODE = "P2P_PAY_2025"

# State Management (ለጊዜው Memory ውስጥ ነው - ቦቱ ሲዘጋ ይረሳል)
USER_STATES = {}
STATE_WAITING_FOR_PAYMENT = 1
STATE_READY_TO_POST = 2

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 1. ዳታቤዝ ማዋቀር ተግባር ---
def init_db():
    """የግሩፕ ማስታወቂያዎችን ሰንጠረዥ (Ads Table) ይፈጥራል።"""
    # Heroku ላይ Worker ሲጀምር በየጊዜው ይሰራል
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
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
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

# --- 2. COMMAND እና MESSAGE HANDLERS (ከቀድሞው ኮድ የተቀዱ) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_message = (
        f"ሰላም {user.first_name}! 👋\n\n"
        "ወደ P2P የድሮ ግሩፖች ማርኬት እንኳን ደህና መጡ።\n"
        "/post_ad - አዲስ ማስታወቂያ ለመለጠፍ (ክፍያ ይጠይቃል)\n"
        "/browse_ads - የሚገኙ ማስታወቂያዎችን ለማየት"
    )
    await update.message.reply_text(welcome_message)

async def post_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if USER_STATES.get(user_id) == STATE_READY_TO_POST:
        await update.message.reply_text("✅ ክፍያዎ ተረጋግጧል። እባክዎ የማስታወቂያዎን ዝርዝር ያስገቡ:")
        return

    message = ("⚠️ ማስታወቂያ ለመለጠፍ ክፍያ መፈጸም ያስፈልጋል።...\n"
                "ክፍያ ከፈጸሙ በኋላ ኮዱን ያስገቡ:")
    USER_STATES[user_id] = STATE_WAITING_FOR_PAYMENT
    await update.message.reply_text(message, reply_markup=ForceReply(selective=True))

async def handle_ad_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        parts = text.split()
        if len(parts) != 6:
            await update.message.reply_text("ማስታወቂያው ትክክለኛ ቅርጽ የለውም። ምሳሌ: `SELL GroupName 15000 2020-01-01 5000 @Contact`")
            return
        
        ad_type, group_name, member_count, start_date, price, contact = parts
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT INTO group_ads (user_id, username, ad_type, group_name, member_count, start_date, price, contact)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            update.effective_user.id, update.effective_user.username, ad_type.upper(),
            group_name, int(member_count), start_date, float(price), contact
        ))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ ማስታወቂያዎ ተመዝግቧል:\n🏷️ ግሩፕ ስም: {group_name}\n💰 ዋጋ: {price} ብር")
        
    except ValueError:
        await update.message.reply_text("የአባላት ብዛት ወይም ዋጋ ቁጥር መሆን አለበት። እባክዎ በትክክል ያስገቡ።")
    except Exception as e:
        await update.message.reply_text(f"የመመዝገብ ስህተት ተፈጥሯል: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if USER_STATES.get(user_id) == STATE_WAITING_FOR_PAYMENT:
        if text == VERIFICATION_CODE:
            USER_STATES[user_id] = STATE_READY_TO_POST
            await update.message.reply_text("🎉 እንኳን ደስ አለዎት! የክፍያ ኮዱ ትክክል ነው።\nአሁን ማስታወቂያዎን ማስገባት ይችላሉ።")
        else:
            await update.message.reply_text("❌ ያስገቡት የክፍያ ኮድ ትክክል አይደለም። እባክዎ እንደገና ይሞክሩ።")
        return
    
    elif USER_STATES.get(user_id) == STATE_READY_TO_POST:
        await handle_ad_submission(update, context)
        del USER_STATES[user_id] # ማስታወቂያ ከተለጠፈ በኋላ ሁኔታውን ማጥፋት
        return
        
    else:
        # መልዕክቱ የማስታወቂያ ማስገቢያ ካልሆነ እና ኮማንድ ካልሆነ
        pass

async def browse_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                f"---"
            )
        await update.message.reply_text(response)

    except Exception as e:
        await update.message.reply_text(f"ማስታወቂያዎችን የማውጣት ስህተት ተፈጠረ: {e}")


# --- 3. የ Heroku Worker ዋና ተግባር ---

def main():
    """ቦቱን በ Long Polling ያስጀምራል። ለ Heroku Worker ተስማሚ ነው።"""
    
    init_db() # ዳታቤዝ ይፈጥራል
    
    BOT_TOKEN = os.environ.get("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set. Please set it in Heroku Config Vars.")
        raise EnvironmentError("BOT_TOKEN is missing!")
        
    # Application መፍጠር
    application = Application.builder().token(BOT_TOKEN).build()

    # Handlers መጨመር
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("post_ad", post_ad))
    application.add_handler(CommandHandler("browse_ads", browse_ads))
    
    # ኮማንድ ያልሆኑ ጽሑፎችን በሙሉ ማስተናገድ
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    logger.info("P2P Group Market Bot Started (Long Polling).")
    
    # ቦቱን በ Long Polling ማስኬድ (ይህ ለ Heroku Worker ምርጥ ነው)
    application.run_polling(poll_interval=3)

if __name__ == '__main__':
    main()
