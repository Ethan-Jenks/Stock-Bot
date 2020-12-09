# Needed for basic discord functionality
import discord
from discord.ext import tasks,commands
# Used for the database connection
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
# Used for polling websites TODO: Update to an async package for optimization
import requests
from bs4 import BeautifulSoup
# Unused?
from datetime import timedelta
# Used for timestamping cooldowns
import time
# Used for the 'Cog' which runs an independant clock, and othe async functions
import asyncio
# Used for wildcard matching in lists and strings
import fnmatch
# Used for RNG
import random


# CONSTANTS
STONK_CD = 60;
BONK_CD = 5*60;

# CONFIDENTIAL CONSTANTS
with open('private.txt') as f:
    private_data = f.read().split()

GUILD_ID = private_data[0]
TOKEN = private_data[1];

# Bot initialization
description = 'stonkBot'
#Request basic permissions
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix='!', description = description, intents = intents)


class MyCog(commands.Cog):
    def __init__(self):
        self.saving.start()
        self.adjust_price.start()

    def cog_unload(self):
        self.printer.cancel()
     
    """
    This cog runs continuous loops on a timer. To create a persistent loop, define a function:
    @tasks.loop(time of loop)
    async def name_of_loop(self):

    and then add:
    self.name_of_loop.start()
    to __init__ above

    See commands.Cog documentation for more intricacies
    """

    @tasks.loop(seconds=15.0) # Occurs every 15 seconds
    async def adjust_price(self):
        # Adjusts the locally stored price
        global prices
        prices = prices + ((random.random()-0.5)*2)
        prices = max(0.001, prices)

    @tasks.loop(minutes=15.0) # Occurs every 15 minutes
    async def saving(self):
        # Save the locally stored price to the database
        global prices
        db.collection(u'Prices').document(GUILD_ID).update({u'CurrentPrice' : prices})

@bot.event
async def on_ready():
    # Do not actually initialize things here unless you know what you are doing. This runs every time the bot reconnects
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')


# TODO: !help

# TODO: Diversify number of investment options

@bot.command()
async def cap(ctx):
    """
    Command: !cap
    Checks the capacity of the Nick by polling the website. =
    TODO: Command uses requests which is not async. Change to be compatable with async, or not, it isn't that slow on a low scale
    """
    response = requests.get('https://services.recwell.wisc.edu/FacilityOccupancy')
    soup = BeautifulSoup(response.text, 'html.parser')
    parent = soup.find(id='occupancy-65cc2f42-1ca8-4afe-bf5a-990b1a9e4111')
    reply = parent.select(".occupancy-count")[0].getText()
    await ctx.send(reply)
    if(reply == '100%'):
        await message.add_reaction('<:spongeF:758177609808478238>')

@bot.command()
async def check(ctx):
    """
    Command: !check
    Checks the current investment price and the users inventory
    READS: 2, WRITES: 1
    """
    # Update user
    user_id = update_user(ctx.message.author)

    # Get inventory information
    inventory = get_dict(u'Inventory', user_id)
    invests = default_dict(inventory, u'Invests', 0)
    stonks = default_dict(inventory, u'Stonk', 0)

    # TODO: Write the current prices to the database when checked?

    global prices # Get the prices data from the Cog
    await ctx.send('Current investment price is **' + '{:.3f}'.format(prices) + '** stonks \
    \nYou currently hold **' + '{:.3f}'.format(invests) + '** invests \
    \nYou currently hold **' + '{:.3f}'.format(stonks) + '** stonks')
    return

@bot.command()
async def invest(ctx, amount:int):
    """
    Command: !invest <amount>
    Buys investments with the users stonks
    READS: 2, WRITES: 1
    TODO: Change from an integer argument?
    TODO: Upgrade infrastructure to chose multiple stonk options
    """

    if amount < 1: # No negative inputs
        await ctx.send('Don\'t even think about it')
        return

    # Update User
    user_id = update_user(ctx.message.author)

    # Get inventory information
    inventory = get_dict(u'Inventory', user_id)
    stonks = default_dict(inventory, u'Stonk', 0)
    invests = default_dict(inventory, u'Invests', 0)

    global prices # Get the prices data from the cog

    if stonks < (amount*prices):
        await ctx.send('You do not have enough stonk to make this investment')
        return
    else:
        # Change local values
        stonks = stonks - (amount*prices)
        invests = invests + amount
        # Write to the database
        db.collection(u'Inventory').document(user_id).update({u'Stonk' : stonks})
        db.collection(u'Inventory').document(user_id).update({u'Invests' : invests})
        await ctx.send('You now have **' + '{:.3f}'.format(invests) + '** invests')
        return

@bot.command()
async def sell(ctx, amount:int):
    """
    Command: !sell <amount>
    Sells investments for the users stonks
    READS: 2, WRITES: 1
    TODO: Change from an integer argument?
    TODO: Upgrade infrastructure to chose multiple stonk options
    """
    if amount < 1: # No negative inputs
        await ctx.send('Don\'t even think about it')
        return

    # Update User
    user_id = update_user(ctx.message.author)

    # Get inventory information
    inventory = get_dict(u'Inventory', user_id)
    invests = default_dict(inventory, u'Invests', 0)
    stonks = default_dict(inventory, u'Stonk', 0)

    global prices # Get the prices data from the cog

    if invests < amount:
        await ctx.send('You do not have enough invests to sell')
        return
    else:
        # Change local values
        stonks = stonks + (amount*prices)
        invests = invests - amount
        # Write to the database
        db.collection(u'Inventory').document(user_id).update({u'Stonk' : stonks})
        db.collection(u'Inventory').document(user_id).update({u'Invests' : invests})
        await ctx.send('You now have **' + '{:.3f}'.format(stonks) + '** stonks')
        return


@bot.command()
async def stonk(ctx):
    """
    Command: !stonk
    Gives the user a stonk on a cooldown
    READS: 3, WRITES: 3
    """
    # Update User
    user_id = update_user(ctx.message.author)

    # Check Cooldown
    if not await check_cooldown(ctx.message, u'Stonk', STONK_CD):
        return

    # Get Inventory Info
    inventory = get_dict(u'Inventory', user_id)
    stonks = default_dict(inventory, u'Stonk', 0)
    stonks = stonks + 1
    # Update Database
    db.collection(u'Cooldowns').document(user_id).update({u'Stonk' : time.time()})
    db.collection(u'Inventory').document(user_id).update({u'Stonk' : stonks})

    reply = 'You have **' + '{:.3f}'.format(stonks) + '** stonk'
    await ctx.send(reply)
    await ctx.message.add_reaction('<:stonks:758156149093957644>')
    return

@bot.command()
async def bonk(ctx, * , target_string : str):
    """
    Command: !bonk <target>
    READS: 5, WRITES: 5
    """

    # Update User
    user_id = update_user(ctx.message.author)
    
    # Check Cooldown
    if not await check_cooldown(ctx.message, u'Bonk', BONK_CD):
        return
    
    # Gives a list of users that match the prefix given in 'target_string'
    user_list = list(map(lambda x: x.display_name, ctx.message.guild.members))
    matching_users = fnmatch.filter(user_list, target_string + '*')

    if len(matching_users) == 0: # No user found
        await ctx.send('**Error:** No user found')
        return

    if len(matching_users) > 1: # Too many users found

        # Display list of users
        reply = 'Found multiple users, please choose a target:\n'
        i = 1
        for option in matching_users:
            reply = reply + '**' + str(i) + ':** ' + option + '\n'
            i = i + 1
        await ctx.send(reply)


        global user_reply
        user_reply = '' # Will be filled with the content of the next user message ducring check()

        # The function that evaluates when to stop waiting
        def check(m):
            # m = any message sent that the bot can see
            global user_reply
            user_reply = m.content
            return ctx.message.author == m.author # Checks for any message from the user anywhere that the bot can see TODO: More specific?


        try:
            await bot.wait_for("message",check=check,timeout=30.0) # Wait 30 sec for any new message from the user
        except asyncio.TimeoutError: # TODO: asyncio.TimeoutError issues? look through documentation
            await ctx.send('**Error:** Command Timed Out')
            return
        else: # If response is recieved
            try:
                chosen_number = int(user_reply)
                if chosen_number < 1 or chosen_number > len(matching_users):
                    raise ValueError
            except ValueError: # Choice is outside of the list or NAN
                await ctx.send('**Error:** Invalid choice')
                return
            chosen_user = matching_users[chosen_number - 1]
    else: # Only 1 match
        chosen_user = matching_users[0]

    try: # Gets the target user id from the chosen string
        target = await commands.MemberConverter().convert(ctx, chosen_user)
    except commands.MemberNotFound:
        reply = '**Error:** Target could not be found'
        await ctx.send(reply)
        return

    # Update user for the target
    target_id = update_user(target)

    # Get and modify db data
    target_inventory = get_dict(u'Inventory', target_id)
    target_stonk = default_dict(target_inventory, u'Stonk', 0)
    target_stonk = target_stonk - 3
    if target_stonk < 0:
        target_stonk = 0
    # Write data back to the database
    db.collection(u'Cooldowns').document(user_id).update({u'Bonk' : time.time()})
    db.collection(u'Inventory').document(target_id).update({u'Stonk' : target_stonk})
                
    reply = '**' + target.display_name + '** now has **' + '{:.3f}'.format(target_stonk) + '** stonk'
    await ctx.send(reply)
    return

@bot.command()
async def prefix(ctx, pref: str):
    """
    Command: !prefix <new prefix>
    Sets the prefix for the bot and updates the database.
    Prefix takes the first character of the argument, and cannot accept alphanumeric characters.
    READS: 0, WRITES: 1
    """
    if(pref[0].isalnum()): # Illegal Argument Error
        reply = '**Error:** Please do not set the prefix to an alpha-numeric character like **' + pref[0] + '**'
        await ctx.send(reply)
        return

    bot.command_prefix = pref[0]
    db.collection(u'Settings').document(GUILD_ID).update({'Prefix' : bot.command_prefix})

    reply = 'Prefix has been set to: ' + bot.command_prefix
    await ctx.send(reply)
    return


def update_user(user):
    """
    Returns the user ID from a user, like the command user.id.
    It also checks however if the user has metadata stored yet, and creates it if there is none.
    Use this function whenever a user account is referenced for the first time in a command to ensure that their data is updated and accurate.
    READS: 1, WRITES: 1
    """
    user_ref = db.collection(u'metadata').document(str(user.id))
    user_meta = user_ref.get()
    if not user_meta.exists:
        user_ref.set({
            u'ID' : user.id,
            u'Username' : user.display_name,
            u'Discriminator' : user.discriminator,
            u'Mention' : user.mention,
            u'AccountCreation' : time.time()
            })
    else:
        user_ref.update({
            u'Username' : user.display_name,
            u'Mention' : user.mention
            })
    return str(user.id)


async def check_cooldown(message, cd_name, cd_time):
    """
    Checks the cooldown of a user, sending a message displaying the remaining time if it does not pass.
    Will not update the cooldown regardless of success or failure, but returns True/False
    READS 1, WRITES: 0
    """
    user_id = str(message.author.id)
    cooldowns = get_dict(u'Cooldowns',user_id)
    prev_time = default_dict(cooldowns, cd_name, 0)
    delta_time = time.time() - prev_time
    if delta_time >= cd_time:
        return True
    else:
        reply = 'Your cooldown has **' + str((int)(cd_time - delta_time)) + '** seconds remaining'
        await message.channel.send(reply.format(message))
        return False


def get_dict(collection, document):
    """
    Gets the stored dictionary from a document within a collection of the connected firestore database.
    If the document does not exist, creates one and returns the basic placeholder dictionary.
    READS: 1, WRITES: 1
    """
    doc = db.collection(collection).document(document).get()
    if doc.exists:
        return doc.to_dict()
    else:
        db.collection(collection).document(document).set({u'Exists' : True})
        return {u'Exists' : True}


def default_dict(dictionary, key, default):
    """
    Accesses the dictionary with the key listed. If the key does not exist, creates and returns an entry with the default value.
    Safely allows checking of a dictionary with a key that you do not know exists.
    """
    try:
        val = dictionary[key]
        return val
    except KeyError:
        dictionary[key] = default
        return default


# ALL OTHER INITIALIZATION GOES HERE

# Debug option
force_reset = False

# Database Initialize
cred = credentials.Certificate(private_data[2])
firebase_admin.initialize_app(cred)
global db
db = firestore.client()

# Grab information from the database for local storage
settings_dict = get_dict(u'Settings', GUILD_ID)
bot.command_prefix = default_dict(settings_dict, u'Prefix', u'!')
price_dict = get_dict(u'Prices', GUILD_ID)
global prices
prices = default_dict(price_dict, u'CurrentPrice', 3)
db.collection(u'Prices').document(GUILD_ID).update({u'CurrentPrice' : prices})


# Run the background persistent clock
cog = MyCog()
# Start the bot (DO NOT SHARE TOKEN PUBLICALLY)
bot.run(TOKEN)

# COMMANDS AFTER THIS POINT WILL NOT BE REACHED
