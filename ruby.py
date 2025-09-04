import discord
from discord.ext import commands
import os
from dotenv import load_dotenv

load_dotenv()
bot = discord.Bot()

bot.load_extension('....')

bot.run(os.getenv('TOKEN'))