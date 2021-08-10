import discord
import time
from discord.ext import commands, tasks
from discord.ext.commands import MemberConverter
import numpy as np
from discord.utils import get
from bs4 import BeautifulSoup
from config import token
import re
import string
from datetime import datetime
import wikipedia
import pymongo
import json
import requests
import asyncio
import random
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='vort ', intents=intents)
bot.load_extension("cogs.main_commands")
bot.load_extension("cogs.currency")
bot.run(token)
