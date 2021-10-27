import discord
from discord.ext import commands, tasks
import requests
import os
from itertools import combinations
import sqlite3
from dateutil.parser import parse
import logging
import json
import trueskill
import sys
import math
import random
import csv
import datetime

import params

# discord_related
logger = logging.getLogger('discord')
logging.basicConfig(filename='elobot.log', level=logging.INFO, format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))

# db_related
conn = sqlite3.connect('battleships.db')
my_db = conn
valid_mapfile_checksums = [
    2602508443
]

# invite url = https://discord.com/api/oauth2/authorize?client_id=777897409161723964&permissions=8&scope=bot
with open('token.txt') as f:
    token = f.read()

intents = discord.Intents.all()
client = discord.ext.commands.Bot(command_prefix='?', case_insensitive=True, intents=intents)
client.remove_command("help")

GUILD_NAME = params.GUILD_NAME
leaderboard_channel_id = params.leaderboard_channel_id
upload_channel_id = params.upload_channel_id
admin_role_id = params.admin_role_id
big_decision_admin_count = params.big_decision_admin_count
elo_bot_voicechat_id = params.elo_bot_voicechat_id
admin_channel_id = params.admin_channel_id

_guild = None
baseurl = "https://api.wc3stats.com"
upload_channel = None
 # test channel 698548028591570994 // bscf 461111074523971584
NO_POWER_MSG = "You do not have enough power to perform such an action."

start_elo = 25
start_elo_convergence = 25 / 3
decay_value = 6 #in minus elo per game
trueenv = trueskill.TrueSkill(mu=start_elo, sigma=start_elo_convergence, beta=4, tau=1 / 2, draw_probability=0.01)
trueenv.make_as_global()


# TODO update roles
@client.command()
async def help(ctx, *command):
    if len(command) > 0:
        command = command[0].lower()
        if command == "add":
            add_text = "**?add** <Battle.net tag> <Alias>\n\n" \
                       "If you need help with your Battle.net tag type !help bnet\n" \
                       "**<Battle.net tag>** - Example: User#1234\n" \
                       "**<Alias>** - Can be used for commands, can be freely chosen"
            embed = discord.Embed(title="Help: add", description=add_text, color=0x00ffad)
            await ctx.send(embed=embed)
        if command == "bnet":
            bnet_text = "1. Open the Battle.net app on your computer\n" \
                        "2. Click on your profile\n"
            embed = discord.Embed(title="Help: bnet", description=bnet_text, color=0x00ffad)
            embed.set_image(url="https://i.imgur.com/lm3fCSI.png")
            await ctx.send(embed=embed)
        if command == "add_map":
            add_text = "**?add_map** <wc3stats_map_checksum> <official_filename> <map_hash>\n"
            embed = discord.Embed(title="Help: add_map", description=add_text, color=0x00ffad)
            await ctx.send(embed=embed)
        if command == "remove_map":
            add_text = "**?remove_map** <wc3stats_map_checksum>\n"
            embed = discord.Embed(title="Help: remove_map", description=add_text, color=0x00ffad)
            await ctx.send(embed=embed)
        if command == "balance":
            add_text = "**?balance** <Battle.net Tag> <...> <...> <Battle.net Tag>\n\n" \
                       "Balances the given players into two teams according to their elo\n" \
                       "**<Battle.net Tag>** - Has to be a even number, can also be the alias of the player"
            embed = discord.Embed(title="Help: balance", description=add_text, color=0x00ffad)
            await ctx.send(embed=embed)
        if command == "change_alias":
            add_text = "**?change_alias** <Alias>\n\n" \
                       "Replace your alias with a new alias"
            embed = discord.Embed(title="Help: change_alias", description=add_text, color=0x00ffad)
            await ctx.send(embed=embed)
        if command == "delete_account":
            add_text = "**?delete_account**\n\n" \
                       "**Careful!** Will delete your account"
            embed = discord.Embed(title="Help: delete_account", description=add_text, color=0x00ffad)
            await ctx.send(embed=embed)
        if command == "stats":
            add_text = "**?stats** <player>\n\n" \
                       "Display the stats from the  current ranked season\n" \
                       "**<player>** (optional) - picked player"
            embed = discord.Embed(title="Help: stats", description=add_text, color=0x00ffad)
            await ctx.send(embed=embed)
        if command == "allstats":
            add_text = "**?allstats** <player>\n\n" \
                       "Display all the stats for the given player from elo-eligible replays\n" \
                       "**<player>** (optional) - Picked player"
            embed = discord.Embed(title="Help: allstats", description=add_text, color=0x00ffad)
            await ctx.send(embed=embed)

    else:
        command_text = "**help**: gives info about commands\n**add**: connect your wc3 and discord account\n" \
                       "**elo**: displays the elo\n**balance**: makes two teams\n**change_alias** updates alias\n" \
                       "**delete_account**: remove your account\n**stats**: display stats of the current season\n" \
                       "**allstats**: shows full stats\n\n(*admin only*)\n**new_season**: starts a new season\n" \
                       "**maps**: returns info about the map file\n**add_map**: updates the current map file"
        # TODO edit (wip) stats balance draft"
        embed = discord.Embed(title="Commands", description=command_text, color=0x00ffad)
        await ctx.send(embed=embed)


async def def_elo(ctx, value):
    new_elo = value
    cursor = my_db.cursor()
    query = "UPDATE player SET elo = " + str(new_elo) + " WHERE discord_id = " + str(ctx.author.id)
    cursor.execute(query)
    my_db.commit()

    
@client.command()
async def list_bans(ctx):
    if await not_admin(ctx):
        return
    cursor = my_db.cursor()
    query = "SELECT wc3_name FROM player WHERE suspended = 1"
    cursor.execute(query)
    row = cursor.fetchone()
    if row is not None:
        msg = "These players are currently suspended : \n"
        while row is not None:
            msg = msg + row[0] + "\n"
            row = cursor.fetchone()
    else :
        msg = "Nobody is banned atm ! awesome community =]"
    
    await ctx.channel.send(msg)
    
@client.command()
async def ban(ctx,wc3_name):
    if await not_admin(ctx):
        return
    cursor = my_db.cursor()
    test = "SELECT rowid FROM player WHERE wc3_name = '" + str(wc3_name)+"'"
    cursor.execute(test)
    row = cursor.fetchone()
    channel = await ctx.author.create_dm()
    if row is not None:
        query = "UPDATE player SET suspended = " + str(1) + " WHERE wc3_name = '" + str(wc3_name) + "'"
        cursor.execute(query)
        temp = my_db.commit()
        await channel.send("Successfully banned player " + str(wc3_name))
    else:
        await channel.send("Player not found")
    
    
    
@client.command()
async def unban(ctx,wc3_name):
    if await not_admin(ctx):
        return
    cursor = my_db.cursor()
    test = "SELECT rowid FROM player WHERE wc3_name = '" + str(wc3_name)+"'"
    cursor.execute(test)
    row = cursor.fetchone()
    channel = await ctx.author.create_dm()
    if row is not None:
        query = "UPDATE player SET suspended = " + str(0) + " WHERE wc3_name = '" + str(wc3_name) + "'"
        cursor.execute(query)
        temp = my_db.commit()
        await channel.send("Successfully unbanned player " + str(wc3_name))
    else:
        await channel.send("Player not found")


@client.command()
async def elo(ctx):
    query = f"SELECT wc3_name,elo,elo_convergence FROM `player` WHERE `discord_id` = {ctx.author.id}"
    cursor = my_db.cursor()
    cursor.execute(query)
    row = cursor.fetchone()
    if row is not None:
        if row[1] is None:
            await ctx.channel.send(f"User *{row[0]}* doesnt have an elo yet!"
                                   f" Play a game and upload the replay to get an elo attributed."
                                   " Only 3v3,4v4,5v5 and 6v6 games on the eligible map files will be parsed.")
            return
        current_elo = disp_elo(row[1], row[2])
        #  mmr = round(50 * row[1])  #  not displayed
        await ctx.channel.send(f"Player **{row[0]}** has a current elo of **{current_elo}**")
    else:
        await ctx.channel.send(f"Player **{ctx.author.name}** does not have a bnet account registered\ntry ?help add")


@client.command()
async def allstats(ctx):
    is_mention = False

    for _ in ctx.message.mentions:
        # get someone stats
        is_mention = True
        break
    if is_mention:
        player = ctx.message.mentions[0].name
        query = f"SELECT wc3_name,alias,games_played,K,D,A,dodosfound FROM `player` WHERE discord_id =" \
                f" {ctx.message.mentions[0].id}"
    else:
        player = ctx.author.nick
        query = f"SELECT wc3_name,alias,games_played,K,D,A,dodosfound FROM `player` WHERE discord_id =" \
                f" {ctx.author.id}"
    cursor = my_db.cursor()
    cursor.execute(query)
    result = cursor.fetchone()

    if result is not None:
        # update stats first
        query = "SELECT SUM(1),SUM(win),SUM(kills),SUM(deaths),SUM(assists),SUM(APM)," \
                "SUM(staypercent),SUM(creepkills),SUM(bounty),SUM(bountyfeed),SUM(goldgathered)," \
                "SUM(dodosfound),SUM(chatcounter),SUM(kickcounter) FROM crossfire_stats WHERE wc3_name = '" + \
                result[0] + "'"
        cursor.execute(query)
        row = cursor.fetchone()
        if row is not None:
            total_games = row[0]
            if total_games == 0 or total_games is None:
                await ctx.channel.send("Player is registered, but there is no data,"
                                       " play and upload an eligible game to get your stats!")
                return
            total_win = row[1]
            total_lose = total_games - total_win
            total_kills = row[2]
            total_death = row[3]
            total_assist = row[4]
            mean_APM = round(row[5] / total_games, 0)
            mean_staypercent = round(row[6] / total_games, 0)
            total_creepkill = row[7]
            total_bounty = row[8]
            total_bountyfeed = row[9]
            total_goldgathered = row[10]
            # total_dodosfound = row[11]
            total_chatcounter = row[12]
            # total_kickcounter = row[13]
            KD = round(total_kills / total_death, 2)
            # mean_assist = round(total_assist / total_games, 2)
            win_percentage = round(100 * total_win / total_games, 0)
            MGB = round((total_bounty - total_bountyfeed) / total_games, 0)
            
            stats_text = f"**Win/Lose/Games**: {total_win}/{total_lose}/{total_games}\n" \
                         f"**Winrate**: {win_percentage}%\n" \
                         f"**Kills/Deaths/Assists**: {total_kills}/{total_death}/{total_assist}\n" \
                         f"**KDA**: {KD}\n**Stay rate**: {mean_staypercent}%\n" \
                         f"**Mean APM**: {mean_APM}\n**Average loot**: {MGB}\n" \
                         f"**Chat Counter**: {total_chatcounter}\n**Creep Kills**: {total_creepkill}"

            embed = discord.Embed(title=player, description=stats_text, color=0x00ffad)
            embed.set_author(name="All Stats")
            await ctx.send(embed=embed)
    else:
        # player is not registered
        await ctx.send("Player was not found")


@client.command()
async def stats(ctx,season=None):
    if season is None:
        season =  get_current_season()
    is_mention = False

    for _ in ctx.message.mentions:
        # get someone stats
        is_mention = True
        player = ctx.message.mentions[0].name
        break

    if is_mention:
        query = "SELECT wc3_name,alias,games_played,K,D,A,dodosfound FROM `player` WHERE discord_id = " + str(
            ctx.message.mentions[0].id)
    else:
        if ctx.author.nick is not None:
            player = ctx.author.nick
        else:
            player = ctx.author.name
        query = "SELECT wc3_name,alias,games_played,K,D,A,dodosfound FROM `player` WHERE discord_id = " + str(
            ctx.author.id)
    cursor = my_db.cursor()
    cursor.execute(query)
    result = cursor.fetchone()

    if result is not None:
        # update stats first
        query = "SELECT SUM(1),SUM(win),SUM(kills),SUM(deaths),SUM(assists),SUM(APM)," \
                "SUM(staypercent),SUM(creepkills),SUM(bounty),SUM(bountyfeed),SUM(goldgathered)," \
                "SUM(dodosfound),SUM(chatcounter),SUM(kickcounter) FROM crossfire_stats WHERE game_id IN " \
                "(SELECT game_id FROM crossfire_games WHERE valid = 1 AND season = " + season + ") AND wc3_name = '" + \
                result[0] + "'"
        cursor.execute(query)
        row = cursor.fetchone()
        if row is not None:
            total_games = row[0]
            if total_games == 0 or total_games is None:
                await ctx.channel.send("Player is registered, but there is no data,"
                                       " play and upload an eligible game to get your stats!")
                return
            total_win = row[1]
            total_lose = total_games - total_win
            total_kills = row[2]
            total_death = row[3]
            total_assist = row[4]
            mean_APM = round(row[5] / total_games, 0)
            mean_staypercent = round(row[6] / total_games, 0)
            total_creepkill = row[7]
            total_bounty = row[8]
            total_bountyfeed = row[9]
            total_goldgathered = row[10]
            # total_dodosfound = row[11]
            total_chatcounter = row[12]
            # total_kickcounter = row[13]
            KD = round(total_kills / total_death, 2)
            # mean_assist = round(total_assist / total_games, 2)
            win_percentage = round(100 * total_win / total_games, 0)
            MGB = round((total_bounty - total_bountyfeed) / total_games, 0)

            stats_text = f"**Win/Lose/Games**: {total_win}/{total_lose}/{total_games}\n" \
                         f"**Winrate**: {win_percentage}%\n" \
                         f"**Kills/Deaths/Assists**: {total_kills}/{total_death}/{total_assist}\n" \
                         f"**KDA**: {KD}\n**Stay rate**: {mean_staypercent}%\n" \
                         f"**Mean APM**: {mean_APM}\n**Average loot**: {MGB}\n" \
                         f"**Chat Counter**: {total_chatcounter}\n**Creep Kills**: {total_creepkill}"

            embed = discord.Embed(title="Stats for this season", description=stats_text, color=0x00ffad)
            await ctx.send(embed=embed)
    else:
        # player isnt registered
        await ctx.send("Player not found (maybe he hasn't registered yet)")


@client.command()
async def add(ctx, wc3_name, alias=""):
    global my_db
    name = ctx.message.author
    discord_id = ctx.message.author.id
    wc3_name = wc3_name.lower()
    alias = alias.lower()
    # check of database entry
    query = f"SELECT * FROM `player` WHERE `discord_id` = '{discord_id}'"
    cursor = my_db.cursor()
    cursor.execute(query)
    result = cursor.fetchall()
    if len(result) > 0:
        await ctx.send("You already added an account.")
        return
    # check wc3name containing #
    if "#" not in wc3_name:
        await ctx.send("Warcraft Account needs to contain '#'")
        return
    # check of wc3name
    query = f"SELECT * FROM `player` WHERE `wc3_name` = '{wc3_name}' AND discord_id IS NOT NULL"
    cursor = my_db.cursor()
    cursor.execute(query)
    result = cursor.fetchall()
    if len(result) > 0:
        await ctx.send(f"Warcraft Account: **{wc3_name}** is already added.")
        return
    # check for alias
    query = f"SELECT * FROM `player` WHERE `alias` = '{alias}'"
    cursor = my_db.cursor()
    cursor.execute(query)
    result = cursor.fetchall()
    if len(result) > 0:
        await ctx.send(f"Alias: **{alias}** is already added.")
        return
    if len(alias) > 0:
        query = f"INSERT INTO player (discord_id, wc3_name, alias) VALUES ({discord_id}, '{wc3_name}', '{alias}')" \
                f" ON CONFLICT(wc3_name) DO" \
                f" UPDATE SET discord_id = {discord_id}, wc3_name = '{wc3_name}', alias = '{alias}'"
        success_message = f"Discord User: **{name}** added Warcraft Account: **{wc3_name}** and alias: **{alias}**"
    else:
        query = f"INSERT INTO player (discord_id, wc3_name) VALUES ({discord_id}, '{wc3_name}')" \
                f" ON CONFLICT(wc3_name) DO UPDATE SET discord_id = {discord_id}, wc3_name = '{wc3_name}'"
        success_message = f"Discord User: **{name}** added Warcraft Account: **{wc3_name}**"
    try:
        cursor = my_db.cursor()
        cursor.execute(query)
        my_db.commit()
        await ctx.send(success_message)
    except Exception as e:
        print(e)
        await ctx.send("Add was not successful")


@client.command()
async def change_alias(ctx, al):
    if "#" not in al and "@" not in al:
        al = al.lower()
        cursor = my_db.cursor()

        # check for duplicates
        # TODO make query being used
        query = "SELECT alias from player WHERE alias = " + al
        cursor.execute(query)
        row = cursor.fetchone()

        if row is None:
            # updates it
            query = "UPDATE player SET alias = '" + al + "' WHERE discord_id = " + str(ctx.author.id)
            cursor.execute(query)
            my_db.commit()
            await ctx.send("Alias changed")
        else:
            await ctx.send("Duplicate found for alias : " + al + " \nNo changes were performed")


@client.command()
async def delete_account(ctx):
    cursor = my_db.cursor()
    query = "UPDATE player SET discord_id = NULL, alias = NULL WHERE discord_id = " + str(ctx.author.id)
    cursor.execute(query)
    my_db.commit()
    await ctx.channel.send("Account removed")


@client.command()
async def balance(ctx, *players):
    ELO = []

    # If all players are in the Elobot Voice channel
    if len(players) == 0:
        print(client.get_channel(elo_bot_voicechat_id).members)
        return

    if len(players) % 2 == 0:
        if len(list(players)) != len(set(players)):
            await ctx.send("Duplicate found")
            return
        for player in players:
            # player is alias
            if "#" in player:
                # player is wc3name
                player = player.lower()
                query = f"SELECT elo,elo_convergence,suspended FROM `player` WHERE wc3_name = '{player}'"
                cursor = my_db.cursor()
                cursor.execute(query)
                result = cursor.fetchone()
                if result is not None:
                    if result[2] != 0:
                        await ctx.channel.send("Cannot balance this game : account " + player + " has been suspended")
                        return
                    ELO.append([player, trueenv.Rating(result[0], result[1])])
                else:
                    # using default ELO
                    await ctx.send(f"**{player}** was not found, using fresh new player elo for that player")
                    ELO.append([player, trueenv.Rating(start_elo, start_elo_convergence)])
            elif "<@!" in player:
                # mention
                pass
            else:
                # alias
                player = player.lower()
                query = f"SELECT wc3_name,elo,elo_convergence,suspended FROM `player` WHERE `alias` = '{player}'"
                cursor = my_db.cursor()
                cursor.execute(query)
                result = cursor.fetchone()
                if result is None:
                    await ctx.send(f"**{player}** was not found, using fresh new player elo for that player")

                    ELO.append([player, trueenv.Rating(start_elo, start_elo_convergence)])
                else:
                    if result[3] != 0:
                        await ctx.channel.send("Cannot balance this game : account " + result[0] + " has been suspended")
                        return
                    print(result)
                    ELO.append([result[0], trueenv.Rating(result[1], result[2])])

        for mention in ctx.message.mentions:
            query = "SELECT elo,elo_convergence,wc3_name,suspended FROM `player` WHERE discord_id = " + str(mention.id)
            cursor = my_db.cursor()
            cursor.execute(query)
            row = cursor.fetchone()
            print(row)
            if row is not None:
                if row[3] != 0:
                    await ctx.channel.send("Cannot balance this game : account " + row[2] + " has been suspended")
                    return
                ELO.append([row[2], trueenv.Rating(row[0], row[1])])
            else:
                await ctx.send(
                    "player " + mention.display_name + " was not found, using fresh new player elo for that player")
                ELO.append([mention.display_name, trueenv.Rating(start_elo, start_elo_convergence)])

        # NOW BALANCE IT PROPERLY

        score = []
        nit = sum(1 for _ in combinations(ELO, int(len(ELO) / 2)))
        i = 0
        for team_a in combinations(ELO, int(len(ELO) / 2)):
            i = i + 1
            if i > nit / 2:
                break
            team_b = remove_from(ELO.copy(), team_a)
            score.append([trueenv.quality([[item[1] for item in team_a], [item[1] for item in team_b]]),
                          [item[0] for item in team_a], [item[0] for item in team_b], [item[1] for item in team_a],
                          [item[1] for item in team_b]])

        sorted_teams_by_score = sorted(score, key=balance_sorting_key, reverse=True)
        best_team_a = sorted_teams_by_score[0][1]
        best_team_b = sorted_teams_by_score[0][2]
        elo_a = sorted_teams_by_score[0][3]
        elo_b = sorted_teams_by_score[0][4]
        northplayers = ""
        southplayers = ""
        i = 0
        for player in best_team_a:
            northplayers += f'- {player} (' + str(disp_elo(elo_a[i].mu, elo_a[i].sigma)) + ') -'
            i = i + 1
        i = 0
        for player in best_team_b:
            southplayers += f'- {player} (' + str(disp_elo(elo_b[i].mu, elo_b[i].sigma)) + ') -'
            i = i + 1
        NS = bool(random.randint(0, 1))
        if NS:
            await ctx.send(
                f"```md\n<North>\n{northplayers}\n\n<South> \n{southplayers}\n\n"
                f"Match quality indicator : {sorted_teams_by_score[0][0]}```")
        else:
            await ctx.send(
                f"```md\n<North>\n{southplayers}\n\n<South> \n{northplayers}\n\n"
                f"Match quality indicator : {sorted_teams_by_score[0][0]}```")
    else:
        await ctx.send("Enter a even number of players")


def balance_sorting_key(elem):
    return elem[0]


def remove_from(b, a):
    for x in a:
        b.remove(x)
    return b


@client.command()
async def draft(ctx, *players):
    cursor = my_db.cursor()
    players = list(players)

    if len(players) > 3:
        if len(players) % 2 == 0:
            north_captain = players[0]
            south_captain = players[1]

            # get captain id
            query = f"SELECT `discord_id` FROM `player` WHERE `alias` = '{north_captain}'" \
                    f" OR `wc3_name` = '{north_captain}'"
            cursor.execute(query)

            north_captain_id = cursor.fetchone()
            if north_captain_id is not None:
                north_captain_id = north_captain_id[0]
            else:
                await ctx.send(f"{north_captain} not found. Both captains need to be added.")
                return
            query = f"SELECT `discord_id` FROM `player` WHERE `alias` = '{south_captain}'" \
                    f" OR `wc3_name` = '{south_captain}'"
            cursor = my_db.cursor()
            cursor.execute(query)
            south_captain_id = cursor.fetchone()
            if south_captain_id is not None:
                south_captain_id = south_captain_id[0]
            else:
                await ctx.send(f"{south_captain} not found. Both captains need to be added.")
                return
            north_team = []
            south_team = []
            drafter_id = None
            del players[:2]
            description = "**Players**: "
            for player in players:
                description += player + " "
            next_choice = north_captain
            embed = discord.Embed(title="Captain's Mode", description=description, color=0x00ffad)
            embed.add_field(name=":blue_square: North Captain: " + north_captain, value="-", inline=True)
            embed.add_field(name=":red_square: South Captain: " + south_captain, value="-", inline=True)
            embed.add_field(name="Next choice:", value=next_choice, inline=False)
            embed.set_thumbnail(url="https://dodo-project.eu/bscf/img/ships.png")
            draft_message = await ctx.send(embed=embed)
            for x in range(len(players) - 1):
                if drafter_id is None or drafter_id == south_captain_id:
                    drafter_id = north_captain_id
                else:
                    drafter_id = south_captain_id
                msg = await client.wait_for('message', check=lambda message: message.author.id == drafter_id)
                while msg.content not in players:
                    msg = await client.wait_for('message', check=lambda message: message.author.id == drafter_id)
                await msg.delete()
                if x % 2 == 0:
                    north_team.append(msg.content)
                    next_choice = south_captain
                else:
                    south_team.append(msg.content)
                    next_choice = north_captain
                players.remove(msg.content)
                await update_draft(draft_message, players, north_team, south_team, north_captain, south_captain,
                                   next_choice)
            # last draft
            south_team.append(players[0])
            next_choice = "-"
            await update_draft(draft_message, players, north_team, south_team, north_captain, south_captain,
                               next_choice, True)

        else:
            await ctx.send("Enter a even number of players")
    else:
        await ctx.send("Enter more players")


@client.event
async def on_ready():
    global upload_channel
    global baseurl, leaderboard_channel_id
    global _guild

    print('Logged in as: "' + client.user.name + '" with user id: "' + str(client.user.id) + '"')

    for guild in client.guilds:
        if guild.name == GUILD_NAME:
            _guild = guild

    game = discord.Game("Battleships Crossfire")
    await client.change_presence(status=discord.Status.online, activity=game)
    upload_channel = client.get_channel(upload_channel_id)


@client.event
async def on_message(message):
    global upload_channel_id

    if message.author == client.user:
        return
    if message.channel.id == upload_channel.id:
        if message.attachments:
            if message.attachments[0].filename.split(".")[1] == "w3g":
                replay = await message.attachments[0].read()
                code, disp_mess = await post_replay(replay)
                if code == 200:
                    await message.channel.send(disp_mess)
                    await update_leaderboard()
                else:
                    await message.channel.send("Upload failed : error " + str(code))
                # GET /results/{replayId}
    await client.process_commands(message)


@client.event
async def clear_channel(channel_id):
    channel = client.get_channel(channel_id)

    await channel.purge(limit=100)


async def update_leaderboard():
    await clear_channel(leaderboard_channel_id)
    await leaderboard()


@client.command()
async def up_leaderboard(ctx):
    print(ctx)
    await update_leaderboard()


async def leaderboard():
    channel = client.get_channel(leaderboard_channel_id)
    msg = "```{:<9}{:<10}{:<40}{:<11}{:<8}{:<8}{:<8}{:<8}".format(
                "Place", "Elo", "Player", "Winrate", "Games", "Wins", "Loses","Dodosfound")

    cursor = my_db.cursor()
    query = "SELECT discord_id,wc3_name,elo,elo_convergence,alias " \
            "FROM player WHERE suspended = 0 ORDER BY (elo-3*elo_convergence) DESC LIMIT 31"
    cursor.execute(query)
    row = cursor.fetchone()
    i = 0
    while row is not None:
        i = i + 1
        if row[1] is not None and row[2] is not None:
            win_lose_cursor = my_db.cursor()
            win_lose_query = "SELECT wins, games_played,dodosfound FROM player WHERE wc3_name = \"" + str(row[1]) + "\""
            win_lose_cursor.execute(win_lose_query)
            win, games_played,dodosfound = win_lose_cursor.fetchone()
            lose = games_played-win
            if games_played <= 0 :
                winrate = 0
            else:
                winrate = (win/(win + lose)*100)
            msg += "\n#{:<8}{:<10}{:<40}{:<11}{:<8}{:<8}{:<8}{:<8}".format(
                str(i), str(disp_elo(row[2], row[3])), row[1] + " (" + str(row[4]) + ")", str("%.2f" % winrate) + "%", str(win + lose), str(win), str(lose),str(dodosfound))
        row = cursor.fetchone()
        if i % 5 == 0:
            msg += "```"
            await channel.send(msg)
            msg = "```"


def disp_elo(player_elo, convergence):
    R = round(50 * (player_elo - 3 * convergence))
    if R > 0:
        return R
    else:
        return 0


# ==============================================================================archi
# ==============================================================================archi
# ==============================================================================archi
# ==============================================================================archi

# TODO there is a decorator for this @role=admin or so
async def not_admin(ctx):
    if ctx.message.author.roles[-1] < _guild.get_role(admin_role_id) and ctx.message.author.id != 230018748491235339:
        await ctx.channel.send(NO_POWER_MSG)
        return True


@client.command()
async def get_players_data(ctx):
    if ctx.channel.id != admin_channel_id:
        return
    if await not_admin(ctx):
        return
    cursor = my_db.cursor()
    query = "SELECT * FROM player"
    cursor.execute(query)
    with open('output.csv', 'w', encoding='utf-8') as out_csv_file:
        csv_out = csv.writer(out_csv_file)
        # write header
        csv_out.writerow([d[0] for d in cursor.description])
        # write data
        for result in cursor:
            csv_out.writerow(result)
    with open('output.csv', 'r', encoding='utf-8') as player_data_file:
        await ctx.channel.send("here you are", file=discord.File(player_data_file.name))
        os.remove("output.csv")
        # str(datetime.datetime.now()) + "_bscf-elo-players"


        
@client.command()
async def get_players_history(ctx,wc3_tag = None):
    if ctx.channel.id != admin_channel_id:
        return
    if await not_admin(ctx):
        return
    cursor = my_db.cursor()
    if wc3_tag is None:
        query = "SELECT * FROM crossfire_stats"
    else:
        query = "SELECT * FROM crossfire_stats WHERE wc3_name ='" + wc3_tag +"'"
    cursor.execute(query)
    with open('output.csv', 'w', encoding='utf-8') as out_csv_file:
        csv_out = csv.writer(out_csv_file)
        # write header
        csv_out.writerow([d[0] for d in cursor.description])
        # write data
        for result in cursor:
            csv_out.writerow(result)
    with open('output.csv', 'r', encoding='utf-8') as player_history_file:
        await ctx.channel.send("here you are", file=discord.File(player_history_file.name))
        os.remove("output.csv")
        # str(datetime.datetime.now()) + "_bscf-elo-players"


@client.command()
async def get_games_history(ctx):
    if ctx.channel.id != admin_channel_id:
        return
    if await not_admin(ctx):
        return
    cursor = my_db.cursor()
    query = "SELECT * FROM crossfire_games"
    cursor.execute(query)
    with open('output.csv', 'w', encoding='utf-8') as out_csv_file:
        csv_out = csv.writer(out_csv_file)
        # write header
        csv_out.writerow([d[0] for d in cursor.description])
        # write data
        for result in cursor:
            csv_out.writerow(result)
    with open('output.csv', 'r', encoding='utf-8') as games_history_file:
        await ctx.channel.send("here you are", file=discord.File(games_history_file.name))
        os.remove("output.csv")
        # str(datetime.datetime.now()) + "_bscf-elo-players"


@client.command()
async def maps(ctx):
    if await not_admin(ctx):
        return
    cursor = my_db.cursor()
    query = "SELECT * FROM map_files WHERE elo_rated = 1"
    cursor.execute(query)
    row = cursor.fetchone()
    msg = ""
    while row is not None:
        msg = msg + f"**Map file**\nwc3stats_key = {row[0]}\nfilename = {row[1]}\nhash = {row[3]}"
        row = cursor.fetchone()

    await ctx.channel.send(msg)


@client.command()
async def add_map(ctx, wc3stats_map_checksum, official_filename, map_hash):
    if await not_admin(ctx):
        return
    cursor = my_db.cursor()
    query = "INSERT INTO map_files (wc3stats_checksum,official_filename,elo_rated,hash) " \
            "VALUES ('{}','{}',{},'{}') ON CONFLICT(wc3stats_checksum) DO UPDATE SET elo_rated={}"
    query = query.format(wc3stats_map_checksum, official_filename, 1, map_hash, 1)
    cursor.execute(query)
    my_db.commit()
    await ctx.channel.send("map now registered as elo eligible")


@client.command()
async def remove_map(ctx, wc3stats_map_checksum):
    if await not_admin(ctx):
        return
    cursor = my_db.cursor()
    query = "INSERT INTO map_files (wc3stats_checksum,elo_rated) " \
            "VALUES ('{}',{}) ON CONFLICT(wc3stats_checksum) DO UPDATE SET elo_rated={}"
    query = query.format(wc3stats_map_checksum, 0, 0)
    cursor.execute(query)
    my_db.commit()
    await ctx.channel.send("map now removed from the elo eligible map pool")


async def post_replay(replay):
    global baseurl

    file_dic = {
        "file": replay,
    }
    r = requests.post(baseurl + "/upload/4a7136cc", files=file_dic)
    replay_response = json.loads(r.text)
    print(replay_response)
    if r.status_code == 200:
        message = replay_parse(replay_response)
        return r.status_code, message
    return r.status_code, None


def is_this_valid(file_checksum, replay_hash, t0, t1, others, pcount, unregistered):
    # unregistered/pcount > 0.99
    if (len(t0) not in range(3, 6) or len(t1) not in range(3, 6)) or others or unregistered / pcount > 0.3:
        # TODO file_checksum not being used
        logging.info(f"File Checksum: {file_checksum}")
        # TODO replay_hash not being used
        logging.info(f"Replay Hash: {replay_hash}")

        # uneligible teams
        logging.info("uneligible teams")
        return False
    else:
        logging.info("valid teams for elo")
        return True


def replay_parse(replay_response):
    map_checksum = replay_response['body']['data']['game']['checksum']
    cursor = my_db.cursor()
    query = "SELECT wc3stats_checksum,elo_rated FROM map_files WHERE wc3stats_checksum = '" + str(map_checksum) + "'"
    cursor.execute(query)
    row = cursor.fetchone()
    if row is not None:
        print(row[1])
        if row[1] == 1:
            logging.info("valid map file for elo")
        else:
            logging.info("invalid map file")
            return "invalid map file"
    else:
        logging.info("unregistered map file")
        return "unregistered map file (wc3stats id = " + str(map_checksum) + ")"

    replay_hash = replay_response['body']['hash']
    player_info = replay_response['body']['data']['game']['players']
    wc3stats_id = replay_response['body']['id']
    timestamp = replay_response['body']['playedOn']
    gn = replay_response['body']['name']
    map_filename = replay_response['body']['data']['game']['map']

    cursor = my_db.cursor()
    query = "SELECT replay_hash FROM crossfire_games WHERE replay_hash = '" + replay_hash + "'"
    cursor.execute(query)
    row = cursor.fetchone()
    if row is not None:
        # replay already been uploaded
        logging.info("replay already uploaded")
        return "replay already uploaded"
    cursor.close()

    t0 = []
    t1 = []
    winning_names = []
    losing_names = []
    others = False
    cursor = my_db.cursor()
    pcount = 0
    unregistered = 0
    t0win = False
    t1win = False

    try:
        for i in range(len(player_info)):
            if player_info[i]['team'] == 0:

                query = "SELECT discord_id,suspended FROM player WHERE wc3_name = '" + player_info[i]['name'] + "'"
                cursor.execute(query)
                row = cursor.fetchone()
                if row is not None:
                    pcount = pcount + 1
                    if row[1] != 0:
                        return "This replay wont be parsed, it involve a suspended account : " + player_info[i]['name']
                else:
                    unregistered = unregistered + 1
                    pcount = pcount + 1

                t0.append(player_info[i]['name'])
                # n0.append(player_info[i]['name'])
                

                if player_info[i]['flags'][0] == 'winner':
                    winning_names.append(player_info[i]['name'])
                    t0win = True
                else:
                    losing_names.append(player_info[i]['name'])

            elif player_info[i]['team'] == 1:

                query = "SELECT discord_id,suspended FROM player WHERE wc3_name = '" + player_info[i]['name'] + "'"
                cursor.execute(query)
                row = cursor.fetchone()
                if row is not None:
                    pcount = pcount + 1
                    if row[1] != 0:
                        return "This replay wont be parsed, it involve a suspended account : " + player_info[i]['name']
                else:
                    unregistered = unregistered + 1
                    pcount = pcount + 1
                
                t1.append(player_info[i]['name'])
                # n1.append(player_info[i]['name'])

                if player_info[i]['flags'][0] == 'winner':
                    winning_names.append(player_info[i]['name'])
                    t1win = True
                else:
                    losing_names.append(player_info[i]['name'])
            else:
                logging.debug("gobs detected")
                others = True
    except Exception:
        # invalid replay (probably because it's incomplete : ie a leaver before victory screen)

        duration = 0
        season = 0
        valid = 0
        sql_query = "INSERT INTO crossfire_games" \
                    " (game_id,name,valid,timestamp,duration,season,filename,map_checksum,replay_hash) " \
                    "VALUES ({},'{}',{},{},'{}',{},'{}',{},'{}')"
        sql_query = sql_query.format(wc3stats_id, gn, valid, timestamp, duration,
                                     season, map_filename, map_checksum, replay_hash)
        cursor.execute(sql_query)
        my_db.commit()
        return "The replay looks incomplete"

    valid = int(is_this_valid(map_checksum, replay_hash, t0, t1, others, pcount, unregistered))

    if valid == 0 or timestamp < 1600000000 or (t0win == False and t1win == False):
        my_db.commit()
        # TODO INFORM
        return "Replay ineligible"

    # elo_change,elo_confidence_change,name = elo_calculus(winning_names,losing_names)
    if t0win:
        elo_change, elo_confidence_change, name = elo_calculus(t0, t1)
    else:
        elo_change, elo_confidence_change, name = elo_calculus(t1, t0)
    cursor = my_db.cursor()
    # by_player_parse
    for i in range(len(replay_response['body']['data']['game']['players'])):
        
        player_data = replay_response['body']['data']['game']['players'][i]
        wc3_name = player_data['name']
        
        if i == 0:
            players_string = "'" +  wc3_name + "'"
        else:
            players_string = players_string + ",'"  + wc3_name + "'"
            
        if player_data['flags'][0] == 'winner':
            win = 1
        else:
            win = 0
        staypercent = player_data['stayPercent']
        APM = player_data['apm']

        mmd = player_data['variables']

        goldgathered = mmd['goldgathered']
        creepkills = mmd['creepkills']
        lumbergathered = mmd['lumbergathered']
        deaths = mmd['deaths']
        kickcounter = mmd['kickcounter']
        bounty = mmd['bounty']
        bountyfeed = mmd['bountyfeed']
        kills = mmd['kills']
        assists = mmd['assists']
        dodosfound = mmd['dodosfound']
        chatcounter = mmd['chatcounter']
        shiplist = mmd['shiplist']

        # TODO why set sql_query twice here?
        # sql_query = "INSERT INTO crossfire_stats " \
        #             "(wc3_name,game_id,win,elo_change,elo_confidence_change,kills,deaths,assists,APM,staypercent," \
        #             "creepkills,bounty,bountyfeed,goldgathered,lumbergathered,dodosfound,chatcounter,kickcounter" \
        #             ",shiplist) VALUES ('{}',{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},'{}')"
        sql_query = "INSERT INTO crossfire_stats (wc3_name,game_id,win,elo_change,elo_confidence_change,kills,deaths,assists,APM,staypercent,creepkills,bounty,bountyfeed,goldgathered,lumbergathered,dodosfound,chatcounter,kickcounter,shiplist) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        params = [wc3_name, wc3stats_id, win, elo_change[name.index(wc3_name)],
                  elo_confidence_change[name.index(wc3_name)], kills, deaths, assists, APM, staypercent, creepkills,
                  bounty, bountyfeed, goldgathered, lumbergathered, dodosfound, chatcounter, kickcounter, shiplist]
        # sql_query = sql_query.format(wc3_name,wc3stats_id,win,elo_change[name.index(wc3_name)],elo_confidence_change[name.index(wc3_name)],kills,deaths,assists,APM,staypercent,creepkills,bounty,bountyfeed,goldgathered,lumbergathered,dodosfound,chatcounter,kickcounter,shiplist)
        logging.debug(sql_query)
        logging.debug(params)
        cursor.execute(sql_query, params)
        #fast stats update
        sql_query = "SELECT games_played,wins,bounty,bountyfeed,goldgathered,K,D,A,dodosfound,chatcounter,kickcounter FROM player WHERE wc3_name = ?"
        params = [wc3_name]
        print(sql_query)
        print(params)
        cursor.execute(sql_query, params)
        row = cursor.fetchone()
        sql_query = "UPDATE player SET games_played = ?,wins=?,bounty=?,bountyfeed=?,goldgathered=?,K=?,D=?,A=?,dodosfound=?,chatcounter=?,kickcounter=? WHERE wc3_name = ?"
        params = [row[0]+1, row[1]+win, row[2]+bounty, row[3]+bountyfeed, row[4]+goldgathered, row[5]+kills, row[6]+deaths, row[7]+assists, row[8] + dodosfound, row[9] + chatcounter, row[10] + kickcounter, wc3_name]
        cursor.execute(sql_query, params)
        
        logging.info(sql_query)
    duration = 0
    
    #get season
    season = get_current_season()
    
    sql_query = "INSERT INTO crossfire_games " \
                "(game_id,name,valid,timestamp,duration,season,filename,map_checksum,replay_hash) " \
                "VALUES ({},'{}',{},{},'{}',{},'{}','{}','{}')"
    sql_query = sql_query.format(wc3stats_id, gn, valid, timestamp, duration,
                                 season, map_filename, map_checksum, replay_hash)
    cursor.execute(sql_query)  
    #decay
    sql_query = "UPDATE player SET elo_convergence=elo_convergence+" + str(round(decay_value/150,3)) + " WHERE wc3_name NOT IN (" + players_string +")"
    print(sql_query)
    logging.debug(sql_query)
    cursor.execute(sql_query)
    my_db.commit()
    discord_message = f"Replay sent (map_id = {map_checksum}) => " \
                      f"https://wc3stats.com/games/{replay_response['body']['id']}"
    return discord_message


def get_current_season():
        #get season
    cursor = my_db.cursor()
    sql_query = "SELECT value FROM constants WHERE name = 'season'"
    cursor.execute(query)
    return cursor.fetchone()[0]

def elo_calculus(wn, ln):
    winning_team = []
    losing_team = []
    elo_change = []
    elo_confidence_change = []
    name = []

    cursor = my_db.cursor()
    for i in range(len(wn)):
        sql_query = "SELECT elo,elo_convergence FROM player WHERE wc3_name ='" + wn[i] + "'"
        cursor.execute(sql_query)
        row = cursor.fetchone()
        if row is None:
            winning_team.append(trueenv.Rating())
        else:
            winning_team.append(trueenv.Rating(row[0], row[1]))

    for i in range(len(ln)):
        sql_query = "SELECT elo,elo_convergence FROM player WHERE wc3_name ='" + ln[i] + "'"
        cursor.execute(sql_query)
        row = cursor.fetchone()
        if row is None:
            losing_team.append(trueenv.Rating())
        else:
            losing_team.append(trueenv.Rating(row[0], row[1]))

    # now faces the teams
    nt0, nt1 = trueenv.rate([winning_team, losing_team], ranks=[0, 1])

    print(winning_team)
    for i in range(len(wn)):
        elo_change.append(nt0[i].mu - winning_team[i].mu)
        elo_confidence_change.append(nt0[i].sigma - winning_team[i].sigma)
        name.append(wn[i])
        elo = nt0[i].mu
        elo_sigma = nt0[i].sigma * (19 / 20)
        sql_query = "INSERT INTO player (wc3_name,elo,elo_convergence) VALUES ('{}',{},{}) ON CONFLICT(wc3_name) DO UPDATE SET elo={}, elo_convergence={}"
        sql_query = sql_query.format(wn[i], elo, elo_sigma, elo, elo_sigma)
        cursor.execute(sql_query)
    print(wn)
    for i in range(len(ln)):
        elo_change.append(nt1[i].mu - losing_team[i].mu)
        elo_confidence_change.append(nt1[i].sigma - losing_team[i].sigma)
        name.append(ln[i])
        elo = nt1[i].mu
        elo_sigma = nt1[i].sigma * (19 / 20)
        sql_query = "INSERT INTO player (wc3_name,elo,elo_convergence) VALUES ('{}',{},{}) ON CONFLICT(wc3_name) DO UPDATE SET elo={}, elo_convergence={}"
        sql_query = sql_query.format(ln[i], elo, elo_sigma, elo, elo_sigma)
        cursor.execute(sql_query)

    my_db.commit()
    return elo_change, elo_confidence_change, name


@client.command()
async def new_season(ctx):
    if await not_admin(ctx):
        return
    global big_decision_admin_count
    big_decision_admin_count = big_decision_admin_count - 1

    if big_decision_admin_count <= 0:
        await new_season_flush()
        
        await ctx.channel.send("It starts !")
    else:
        await ctx.channel.send(
            "Admin <@!" + str(ctx.author.id) + "> is asking for a new ranked season to start ! \nat least " + str(
                big_decision_admin_count) + " other admin are needed to confirm this ! hurry ... winter is coming")


async def new_season_flush():
    cursor = my_db.cursor()
    query = "SELECT wc3_name,elo,elo_convergence FROM player "
    cursor.execute(query)
    row = cursor.fetchone()

    cursor2 = my_db.cursor()
    while row is not None:
        if row[1] is not None:
            # new_elo = start_elo
            new_elo = start_elo + (row[1] - start_elo) / 4
        else:
            new_elo = start_elo

        # TODO this if/else does nothing because it gets assigned later
        if row[2] is not None:
            new_elo_convergence = row[2]
        else:
            new_elo_convergence = start_elo_convergence
        new_elo_convergence = start_elo_convergence
        query = "UPDATE player SET elo = " + str(new_elo) + ",elo_convergence = " + str(
            new_elo_convergence) + ",games_played=0, wins=0, bounty=0, bountyfeed=0, goldgathered=0, K=0, D=0, A=0, dodosfound=0, chatcounter=0, kickcounter=0 WHERE wc3_name = '" + row[0] + "'"
        cursor2.execute(query)
        row = cursor.fetchone()
    query = "SELECT value FROM constants WHERE name = 'season'"
    cursor.execute(query)
    row = cursor.fetchone()
    query = "UPDATE constants SET value = " + str(int(row[0]) + 1) + " WHERE name = 'season'"
    cursor.execute(query)
    
    my_db.commit()


# =============================================================/archi
# =============================================================/archi
# =============================================================/archi
# =============================================================/archi


async def update_draft(draft_message, players, north_team, south_team, north_captain, south_captain,
                       next_choice, last=False):
    if last:
        description = "**Players**: "
    else:
        description = "**Players**: "
        for player in players:
            description += player + " "

    north_team = ", ".join(north_team)

    if len(south_team) > 0:
        south_team = ", ".join(south_team)
    else:
        south_team = "-"

    embed = discord.Embed(title="Captain's Mode", description=description, color=0x00ffad)
    embed.add_field(name=":blue_square: North Captain: " + north_captain, value=north_team, inline=True)
    embed.add_field(name=":red_square: South Captain: " + south_captain, value=south_team, inline=True)
    embed.set_thumbnail(url="https://dodo-project.eu/bscf/img/ships.png")
    if not last:
        embed.add_field(name="Next choice:", value=next_choice, inline=False)
    await draft_message.edit(embed=embed)


client.run(token)
