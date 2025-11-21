import logging
import sqlite3
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, ContextTypes, CommandHandler, MessageHandler, filters

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

# HELPER FUNCTIONS
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
        c.execute('''
            INSERT OR IGNORE INTO users (user_id, first_name, username)
            VALUES (?, ?, ?)
        ''', (user.id, user.first_name, user.username))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"User tracking failed: {e}")

# DATABASE SETUP
def init_db():
    """የግሩፕ ማስታወቂያዎችን እና የተጠቃሚዎችን ሰንጠረዦች ይፈጥራል።"""
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()

        # 1. Group Ads Table
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

        # 2. Users Table
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
