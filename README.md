# Elo-bot

This is a discord bot, written for the [Battleships Crossfire server](https://discord.gg/Vzyq5nG). 

## Description

This bot was written to have a competetive scoring system. It takes uploads for Battleship Crossfire replays in the form of w3g files. It has a matchmaking command and displays the rank and stats of players. 

### Features

- Leaderboard
- Balance
- Captain's Draft
- Elo System
- ?help: shows all the commands

### Built with

- [Discord.py](https://discordpy.readthedocs.io/en/stable/api.html)
- [Trueskill](https://trueskill.org/)

### Configure

Configuration ist mostly done in the code at the moment.

#### Admin commands

- ?new_season: starts a new season
- ?maps: returns info about the map file
- ?add_map: add a new elo eligible map file
- ?remove_map: remove a previously elo eligible map file
- ?ban
- ?unban
- ?list_bans
- ?get_players_data : retrieve current player data from the homonymous table
- ?get_players_history : get players data (specific one if you provide btag)
- ?get_games_history : get every uploaded games history
- ?new_season (2 admins needed to ask for this) smart elo reset

### Acknowledgements

Thanks to all who helped with this project.
- Archi - [github.com/Archimonde666](https://github.com/Archimonde666)
- Ziadoma - [github.com/Ziadoma](https://github.com/Ziadoma)
