import logging
import sqlite3
import os
from telegram import Update, ForceReply
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# 🔐 BOT_TOKENን ከ Render Environment Variables ላይ ያነባል
BOT_TOKEN = os.environ.get("BOT_TOKEN") 

# የዳታቤዝ ፋይል ስም
DB_NAME = 'group_market.db'

# --- ክፍያ መፈጸሚያ ኮድ (Mock Payment Code) ---
# ይህ ኮድ ተጠቃሚው ማስታወቂያ ከመለጠፉ በፊት እንዲያስገባው የሚጠበቀው ምሳሌ ኮድ ነው።
# በእውነተኛ ፕሮጀክት ይህ ኮድ በአድሚኑ ይላካል ወይም በክፍያ ስርአት ይፈጠራል።
VERIFICATION_CODE = "P2P_PAY_2025" 

# ለጊዜው የተጠቃሚውን ሁኔታ የምንመዘግብበት መዝገብ (Dictionary)
# Key: user_id, Value: current_state
USER_STATES = {} 
STATE_WAITING_FOR_PAYMENT = 1
STATE_READY_TO_POST = 2
# ---------------------------------------------


# ሎግግንግ ማዘጋጀት
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- 1. ዳታቤዝ ማዋቀር ተግባር ---
def init_db():
    # ... (ይህ ክፍል ሳይቀየር ይቀጥላል)
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS group_ads (
                ad_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                username TEXT,
                ad_type TEXT,  -- 'SELL' or 'BUY'
                group_name TEXT,
                member_count INTEGER,
                start_date TEXT, -- (Oldness)
                price REAL,
                contact TEXT, -- (የግዢ/ሽያጭ ስምምነት መገናኛ)
                status TEXT DEFAULT 'ACTIVE'
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

# --- 2. ኮማንድ ሃንድለሮች (Command Handlers) ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (ይህ ክፍል ሳይቀየር ይቀጥላል)
    user = update.effective_user
    welcome_message = (
        f"ሰላም {user.first_name}! 👋\n\n"
        "ወደ P2P የድሮ ግሩፖች ማርኬት እንኳን ደህና መጡ።\n"
        "የቴሌግራም ግሩፖችን መግዛት ወይም መሸጥ ይችላሉ።\n\n"
        "ዋና ኮማንዶች:\n"
        "/post_ad - አዲስ ማስታወቂያ ለመለጠፍ (ክፍያ ይጠይቃል)\n" # ማስታወሻ ተጨምሯል
        "/browse_ads - የሚገኙ ማስታወቂያዎችን ለማየት"
    )
    await update.message.reply_text(welcome_message)

async def post_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ማስታወቂያ ከመለጠፍ በፊት ክፍያ እንዲፈጸም ይጠይቃል።"""
    
    user_id = update.effective_user.id
    
    # ተጠቃሚው ቀድሞውኑ ለጥፎ ከሆነ መፈተሽ
    if USER_STATES.get(user_id) == STATE_READY_TO_POST:
        message = "✅ ክፍያዎ ተረጋግጧል። እባክዎ የማስታወቂያዎን ዝርዝር ያስገቡ:"
        await update.message.reply_text(message)
        return

    # ክፍያ አልተፈጸመም: ለክፍያ ይጠይቃል
    message = (
        "⚠️ ማስታወቂያ ለመለጠፍ ክፍያ መፈጸም ያስፈልጋል።\n"
        "እባክዎ መጀመሪያ ክፍያውን (ለምሳሌ 100 ብር) ለአድሚኑ ይፈጽሙና አድሚኑ የሰጠዎትን ልዩ የክፍያ ማረጋገጫ ኮድ እዚህ ያስገቡ።\n\n"
        "ክፍያ ከፈጸሙ በኋላ ኮዱን ያስገቡ:"
    )
    USER_STATES[user_id] = STATE_WAITING_FOR_PAYMENT # ሁኔታውን መቀየር
    await update.message.reply_text(message, reply_markup=ForceReply(selective=True))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """መልዕክቶችን በሁኔታ (State) መሰረት ያካሂዳል።"""
    
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # --- የክፍያ ማረጋገጫ ክፍል ---
    if USER_STATES.get(user_id) == STATE_WAITING_FOR_PAYMENT:
        if text == VERIFICATION_CODE:
            # ኮዱ ትክክል ከሆነ
            USER_STATES[user_id] = STATE_READY_TO_POST
            await update.message.reply_text(
                "🎉 እንኳን ደስ አለዎት! የክፍያ ኮዱ ትክክል ነው።\n"
                "አሁን ማስታወቂያዎን /post_ad የሚለውን ተጭነው ማስገባት ይችላሉ።"
            )
        else:
            # ኮዱ ትክክል ካልሆነ
            await update.message.reply_text("❌ ያስገቡት የክፍያ ኮድ ትክክል አይደለም። እባክዎ እንደገና ይሞክሩ።")
        
        return
    
    # --- የማስታወቂያ ማስገቢያ ክፍል ---
    elif USER_STATES.get(user_id) == STATE_READY_TO_POST:
        # እዚህ ጋር የማስታወቂያ ማስገቢያ ሎጂክ ይገባል
        await handle_ad_submission(update, context)
        # ማስታወቂያው ከተገባ በኋላ ሁኔታውን ወደ NULL መመለስ (አንድ ጊዜ ብቻ እንዲለጥፍ)
        del USER_STATES[user_id] 
        return
        
    # --- ሌላ ማንኛውም መልዕክት ---
    else:
        # ቀደም ሲል እንደነበረው የሲቪል ምላሽ
        response_message = "መልዕክትዎን ተቀብለናል። ✅ አስተዳዳሪው በቅርቡ ምላሽ ይሰጥዎታል።"
        await update.message.reply_text(response_message)


async def handle_ad_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """የማስታወቂያውን ዝርዝር ተቀብሎ በዳታቤዝ ያስቀምጣል።"""
    
    # ... (ይህ ክፍል የማስታወቂያ ማስገቢያ ሎጂክ ነው፤ ከመጀመሪያው ኮድህ ላይ ተወስዶ እዚህ ይገባል)
    # ማስታወቂያው ሲገባ፣ የክፍያ ሁኔታ STATE_READY_TO_POST መሆኑ ተረጋግጧል።
    
    text = update.message.text.strip()
    
    try:
        parts = text.split()
        
        if len(parts) != 6:
            await update.message.reply_text(
                "ማስታወቂያው ትክክለኛ ቅርጽ የለውም። አምስት ዝርዝሮች ያስፈልጉናል (SELL/BUY, GroupName, Count, Date, Price, Contact)."
            )
            return

        ad_type, group_name, member_count, start_date, price, contact = parts
        
        # ወደ ዳታቤዝ ማስገባት
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            INSERT INTO group_ads (user_id, username, ad_type, group_name, member_count, start_date, price, contact)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            update.effective_user.id,
            update.effective_user.username,
            ad_type.upper(),
            group_name,
            int(member_count),
            start_date,
            float(price),
            contact
        ))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(
            f"✅ ማስታወቂያዎ ተመዝግቧል:\n"
            f"የግሩፕ ስም: {group_name}\n"
            f"አባላት: {member_count}\n"
            f"ዋጋ: {price} ብር\n"
            f"ለሽያጭ/ግዢ: {ad_type}"
        )
        
    except ValueError:
        await update.message.reply_text("የአባላት ብዛት ወይም ዋጋ ቁጥር መሆን አለበት። እባክዎ በትክክል ያስገቡ።")
    except Exception as e:
        await update.message.reply_text(f"የመመዝገብ ስህተት ተፈጥሯል: {e}")
        
    # ማስታወቂያው ከተገባ በኋላ ሁኔታውን ወደ NULL መመለስ (በ handle_message ውስጥ ይከናወናል)


async def browse_ads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (ይህ ክፍል ሳይቀየር ይቀጥላል)
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


# --- 4. የ MAIN_RUN ተግባር (ለ Render Webhook) ---

async def post_init(application: ApplicationBuilder) -> None:
    """Sets up the Webhook URL when the application starts."""
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if url:
        await application.bot.set_webhook(url=url)


def main_run():
    """Initializes and runs the bot in Webhook mode for Render."""
    
    init_db() # ዳታቤዝ እዚህ ይፈጠራል!
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set. Check your Render Environment Variables.")
        return
        
    application = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # Handlers መጨመር
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("post_ad", post_ad))
    application.add_handler(CommandHandler("browse_ads", browse_ads))
    
    # የመልዕክት ሃንድለር (ለክፍያ ኮድ እና ማስታወቂያ ማስገቢያ)
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    
    logger.info("Starting P2P Group Market Bot Webhook Server...")
    
    port = int(os.environ.get("PORT", "8080"))
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    
    if not render_url:
        logger.error("RENDER_EXTERNAL_URL is not set. Cannot start webhook.")
        return
        
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="",
        webhook_url=render_url,
    )


if __name__ == '__main__':
    main_run()
