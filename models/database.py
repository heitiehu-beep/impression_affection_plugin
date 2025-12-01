"""
数据库连接管理
"""

import os
from peewee import SqliteDatabase

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PLUGIN_DIR, "impression_affection_data.db")

db = SqliteDatabase(DB_PATH)
