import os
import typing
from dotenv import load_dotenv
import sqlite3
from nextcord.ext import commands
from nextcord.ext.commands.context import Context
from nextcord.mentions import A
from nextcord.message import Message
import markovify
import emoji
import time

TRIES = 1000
MIN_MESSAGES = 25
LOG_DIR = "logs"

bot = commands.Bot(command_prefix='$')
con = sqlite3.connect("database.db")
cur = con.cursor()


def log(message: str, type: str = "INFO") -> None:
    day = time.strftime('%m-%d-%Y')
    current_time = time.strftime('%m-%d-%Y %H:%M:%S')
    result = f'[{current_time}] {type}: {message}'
    print(result)
    with open(f'{LOG_DIR}/{day}.log', 'a') as f:
        f.write(result + '\n')


def add_message(id: int, message: str) -> None:
    cur.execute(
        'INSERT INTO messages (user_id, message) VALUES (?, ?);', (id, message))
    con.commit()


def toggle_permission(id: int) -> bool:
    cur.execute(
        "SELECT user_id, permission FROM permission WHERE user_id = (?);", (id,))
    data = cur.fetchone()
    if data is None:
        cur.execute(
            "INSERT INTO permission(user_id, permission) VALUES (?, 1);", (id,))
        con.commit()
        return True
    else:
        permission = not data[1]
        cur.execute(
            "UPDATE permission SET permission = (?) WHERE user_id = (?);", (permission, data[0]))
        con.commit()
        return permission


@bot.event
async def on_ready():
    log("Bot is ready.")


@bot.event
async def on_message(message: Message) -> None:
    if message.content.startswith('$'):
        await bot.process_commands(message)
        return
    cur.execute(
        "SELECT permission FROM permission WHERE user_id = (?)", (message.author.id,))
    data = cur.fetchone()
    if data is not None and data[0] != 0:
        parsed_content = emoji.demojize(message.content)
        cur.execute(
            "SELECT rowid FROM messages WHERE user_id = (?) AND message = (?);", (message.content, message.author.id))
        data = cur.fetchone()
        if data is None:
            cur.execute("INSERT INTO messages (user_id, message) VALUES (?, ?);",
                        (message.author.id, parsed_content))
            con.commit()
            log(
                f'New message added user_id: {message.author.id}, message: "{parsed_content}"')


@bot.command()
async def permission(ctx: Context) -> None:
    result = toggle_permission(ctx.author.id)
    if result:
        await ctx.reply('All your messages will be saved to be analyzed from now on. Run this command again to toggle it.')
        log(f'User {ctx.author.id} gave permission to store data.')
    else:
        await ctx.reply('Your messages will no longer be saved. Run this command again to toggle it.')
        log(f'User {ctx.author.id} removed permission to store data.')


@bot.command()
async def purge(ctx: Context) -> None:
    cur.execute("DELETE FROM messages where user_id = (?);", (ctx.author.id,))
    con.commit()
    await ctx.reply('All your messages have been purged from our database.')
    log(f'User {ctx.author.id} requested to remove all their data.')


@bot.command()
async def simulate(ctx: Context, id: typing.Optional[int] = None) -> None:
    target_id = ctx.author.id if id is None else id
    cur.execute("SELECT message FROM messages WHERE user_id = (?);",
                (target_id,))
    data = cur.fetchall()

    if len(data) < MIN_MESSAGES:
        await ctx.reply(f'I don\'t have enough data to simulate this user. I need at least {MIN_MESSAGES} messages.')
        return

    text = ""
    for row in data:
        text += row[0] + '\n'
    model = markovify.NewlineText(text)
    result = model.make_sentence(tries=TRIES)
    log(f'User {ctx.author.id} requested a simulation got "{result}".')
    await ctx.reply("Unable to make a sentence." if result is None else result)


def main() -> None:
    load_dotenv()

    if not os.path.exists("logs"):
        os.makedirs("logs")

    cur.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            user_id UNSIGNED LONG INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
        );
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS permission  (
            user_id UNSIGNED LONG INTEGER NOT NULL,
            permission INTEGER NOT NULL
        );
    ''')

    bot.run(os.getenv("DISCORD_BOT_TOKEN"))
    con.commit()
    con.close()


if __name__ == "__main__":
    main()
