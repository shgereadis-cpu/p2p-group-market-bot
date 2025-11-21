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
        ["ማስታወ
