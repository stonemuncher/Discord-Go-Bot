import discord
from boardrender import *
from sgfmill import boards
import json
import os
import argparse
import random

client = discord.Client()

parser = argparse.ArgumentParser()
parser.add_argument("token", help="Input bot token")
args = parser.parse_args()

GAME_ROOM_CMDS = {'!play [move]': 'Play your move in a game. The format is !play [Letter][Number] - e.g. !play A6, or !play B9.',
                  '!resign': 'Resign from the game.',
                  '!pass': 'Pass your turn.',
                  '!dead [coordinates]': 'Mark dead stones during scoring. You can mark one stone at a time, e.g. !dead A6, or multiple - !dead A6 B9 L4 M7 etc etc.',
                  '!resume': 'Resume the game from scoring to settle a dispute, or to reset the removed stones if a mistake was made.',
                  '!done': 'Agree upon the removed dead stones, and end the game.',
                  '!stop': 'Admin only command. Stop the game.'}

GO_LOBBY_CMDS = {'!help': 'Get a list of commands.',
                 '!game [type]': 'If [type] is left blank, a normal game is made. Other types include \'onecolour\' (One colour go) and \'blind\' (Blind go)',
                 '!cancel': 'Cancel your game active game requests.',
                 '!requests': 'Get a list of active game requests.',
                 '!stopallgames' : 'Admin only command. Stops all games on the discord server.'}

def load_requests(guild_id):
    
    with open(f'data/{guild_id}/requests.json', 'r') as f:
        return json.load(f)


def save_requests(requests, guild_id):
    
    with open(f'data/{guild_id}/requests.json', 'w') as f:
        json.dump(requests, f)


def load_game_info(guild_id, room_name):

    with open(f'data/{guild_id}/games/{room_name}.json', 'r') as f:
        return json.load(f)


def save_game_info(game_info, guild_id, room_name):
    
    with open(f'data/{guild_id}/games/{room_name}.json', 'w') as f:
        json.dump(game_info, f)

    
def create_guild_files(guild_id):

    #Check if folder exists already - this happens if user adds bot, kicks it then readds it!
    if not os.path.isdir(f'data/{guild_id}'):
        
        os.mkdir(f'data/{guild_id}')
        os.mkdir(f'data/{guild_id}/boards')
        os.mkdir(f'data/{guild_id}/games')
        
        save_requests({}, guild_id)


def add_go_lobby_cmds(GO_LOBBY_CMDS, embed):

    #Command description prefix to show where the command can be used
    desc_pfx = '(In go-lobby)'
    
    for cmd in GO_LOBBY_CMDS:

        embed.add_field(name = cmd, value = f'{desc_pfx} {GO_LOBBY_CMDS[cmd]}', inline = False)

    return embed


def add_game_room_cmds(GAME_ROOM_CMDS, embed):

    #Command description prefix to show where the command can be used
    desc_pfx = '(In game-room)'
    
    for cmd in GAME_ROOM_CMDS:

        embed.add_field(name = cmd, value = f'{desc_pfx} {GAME_ROOM_CMDS[cmd]}', inline = False)

    return embed


def delete_game_data(room_name, guild_id):
    
    os.remove(f'data/{guild_id}/games/{room_name}.json')

    #Since the initial board image isn't saved when the game is created
    #this is necessary incase of !stop or !resign on a game before a move is made
    if os.path.isfile(f'data/{guild_id}/boards/{room_name}.png'):
        
        os.remove(f'data/{guild_id}/boards/{room_name}.png')

def get_game_type_info(type):

    if type == 'onecolour':
        return 'One Colour Go - all stones appear white, it\'s down to you to remember which stone belongs to who!'

    elif type == 'blind':
        return 'Blind go - only the last move is shown! This is a real test of memory.'

    else:
        return 'A standard game of 19x19 go.'
        
async def send_board(guild_id, room_name, message, title, desc):

    #Get the channel using id of a spam channel for sending images, to grab url to be used when editing embeds' images because discord.py == poopy and you can't edit an embed's image with a local image
    spam_channel = discord.utils.get(message.guild.channels, name='go-bot-spam')

    new_board = await spam_channel.send(file=discord.File(f'data/{guild_id}/boards/{room_name}.png'))
    
    #Set up the embed
    embed = discord.Embed(colour = discord.Colour.dark_orange(),
                            title = title,
                            description = desc,
                            url = new_board.attachments[0].url)

    #Again, scrape URL from spam channel in order to be able to update initial embed with the new image
    embed.set_image(url=new_board.attachments[0].url) 
    
    #Set footer
    embed.set_footer(text='Click the title for zoomable board!')
    
    #Get the last message in the channel, e.g. the initial embed sent by the bot
    last_msg = await message.channel.history(limit=1).flatten()
    
    #Edit with new image url and title
    await last_msg[0].edit(embed = embed)


def get_next_turn(turn, p1_info, p2_info):

    #Add a note as to whose turn it is now
    if p1_info[2] == turn:
        
        return f'\n\nIt\'s now {p1_info[0]}\'s turn to play.'

    else:
        return f'\n\nIt\'s now {p2_info[0]}\'s turn to play.'


def check_and_convert_move(move, board_size = 19):

    TOP_ROW_LETTERS = {19: 'abcdefghjklmnopqrst'}

    if (move[0].lower() not in TOP_ROW_LETTERS[board_size]) or (not move[1:].isdigit()):
        return 'invalid', 'invalid'

    elif int(move[1:]) < 1 or int(move[1:]) > board_size:                      
        return 'invalid', 'invalid'

    else:

        x = TOP_ROW_LETTERS[board_size].index(move[0].lower())
        y = board_size - int(move[1:]) 
        return x, y

#This is used to avoid using sgfmill's board.list_occupied_points() when game logic is not needed to update
#the black or white stone coordinates - such as during scoring where stones are removed manually if they 
#are dead.
def make_points(black_pts, white_pts):

    occupied_points = [ ]

    for point in black_pts:
        occupied_points.append(('b', point))
    for point in white_pts:
        occupied_points.append(('w', point)) 

    return occupied_points

def get_dead_cmd_help():

    return 'Use !dead followed by the coordinates of dead stones to remove them from the board, e.g. !dead A6 B8.\n\n \
            If you made a mistake and want to reset the dead stones, or want to resume the game, type !resume.\n\n \
            Otherwise if all dead stones have been marked, type !done.'


@client.event
async def on_ready():
    print("Go Bot is activated")


@client.event
async def on_guild_join(guild):

    #DEBUG
    print(f'Joined guild: {guild.name}')
    
    #Create necessary categories and text channels
    go_category = await guild.create_category('go-games')
    go_lobby = await guild.create_text_channel('go-lobby', category = go_category, position = 1)

    #Create hidden channel for uploading images for embed edits
    overwrites = {
    guild.default_role: discord.PermissionOverwrite(read_messages=False),
    guild.me: discord.PermissionOverwrite(read_messages=True)
    }

    await guild.create_text_channel('go-bot-spam', overwrites=overwrites)

    #Grab guild ID
    guild_id_str = str(guild.id)

    #Attempt to create necessary folders for data storage
    try:
        create_guild_files(guild_id_str)
        await go_lobby.send('Setup successfull')
        
    except Exception as e:
        await go_lobby.send('Failed to setup correctly. Error: {}'.format(str(e)))
        
@client.event
async def on_message(message):

    global GAME_ROOM_CMDS
    global GO_LOBBY_CMDS
    
    #If the message was sent by the bot, i.e. a reply then ignore it    
    if message.author.id == client.user.id: 
        return

    if isinstance(message.channel, discord.channel.DMChannel):
        await message.channel.send('Please talk to me in a server!')
        return
        
    #Log guild id for usage later
    guild_id_str = str(message.guild.id)

    #If the channel was go-lobby
    if message.channel.name == 'go-lobby':

        #Command to view all commands
        if message.content.startswith('!help'):
            embed = discord.Embed(colour = discord.Colour.purple(),
                                  title = 'Go Bot',
                                  description = 'Play go inside discord! The following commands are availiable:')

            embed = add_go_lobby_cmds(GO_LOBBY_CMDS, embed)
            embed = add_game_room_cmds(GAME_ROOM_CMDS, embed)

            embed.set_footer(text = f'!help requested by {message.author.name}')
            
            await message.channel.send(embed=embed)

            
        #Command to create a game request
        if message.content.startswith('!game'):

            #Load current requests
            requests = load_requests(guild_id_str)

            #Grab args
            args = message.content.split()

            #Set default game type
            game_type = 'normal'

            #Check arguments for different type
            if len(args) > 1:

                if args[1] == 'onecolour':
                    game_type = 'onecolour'

                elif args[1] == 'blind':
                    game_type = 'blind'

            #If the sender already has a request open, tell them and don't make a new one
            if str(message.author.id) in requests:

                await message.channel.send(f'You already have a game request open! Cancel it with !cancel before making another. {message.author.mention}')

            else:
                #Set up the request embed
                embed = discord.Embed(colour = discord.Colour.purple(),
                                      title = f'Game request from {message.author.name}',
                                      description = f'Type !accept {message.author.mention} to accept the request!')

                #Create some info on the game request depending on the type
                req_info = get_game_type_info(game_type)
                
                #Add info to embed
                embed.add_field(name='Game type', value = req_info, inline = False)

                try:
                    #Send the request embed
                    request_msg = await message.channel.send(embed=embed)
                    
                    #Add the message id of the request to the requests dict and save in the file
                    requests[message.author.id] = {'msg_id': request_msg.id,
                                                   'type': game_type}
                    
                    save_requests(requests, guild_id_str)

                except:
                    await message.channel.send(f'{message.author.mention}, there was a problem creating the game request :(')
                    

        #Command to cancel a game request
        if message.content.startswith('!cancel'):
            
            requests = load_requests(guild_id_str)

            if str(message.author.id) in requests:

                try:
                    old_req = await message.channel.fetch_message(requests[str(message.author.id)]['msg_id'])
                    await old_req.delete()
                    del requests[str(message.author.id)]
                    
                    save_requests(requests, guild_id_str)
                        
                    await message.channel.send(f'{message.author.mention}, your game request was cancelled successfully')
                    
                except:
                    await message.channel.send(f'{message.author.mention}, there was a problem cancelling the game request :(')

            else:
                await message.channel.send(f'{message.author.mention}, you don\'t have any active game requests to cancel!')


        #Command to view all active requests
        if message.content.startswith('!requests'):

            requests = load_requests(guild_id_str)
            
            count = 1

            #Set up embed
            embed = discord.Embed(colour = discord.Colour.purple(),
                                  title = 'Showing all active game requests')

            #Generate list of requests and format, and add to embed
            for request in requests:

                game_type = requests[str(request)]['type']
                type_info = get_game_type_info(game_type)

                embed.add_field(name = f'Game request #{count}', value = f'Creator: <@{request}>\nGame type: {type_info}')
                count += 1

            if count == 1:
                embed.add_field(name = 'Oh... it seems there aren\'t any.', value = 'Why not open one yourself with !game?')  
            
            embed.set_footer(text = 'Type !accept @user to accept a game!')
            await message.channel.send(embed=embed)
            
        #Command to accept a game request and start a game
        if message.content.startswith('!accept'):

            args = message.content.split()
            if len(args) != 2:
                await message.channel.send(f'{message.author.mention}, to accept a game request, please use !accept @user, where user is the creator of the request.')
                return

            #Load current requests
            requests = load_requests(guild_id_str)

            requester_id = args[1].strip('@<>!')

            if requester_id not in requests:
                await message.channel.send(f'{message.author.mention} that user doesn\'t have an active game request.')
                return

            #get player objects
            player1 = message.author
            player2 = await client.fetch_user(requester_id)

            if not player2:
                await message.channel.send('The player whose game request you accepted cannot be found. Perhaps they deleted their account.')
                return

            #save game type
            game_type = requests[str(requester_id)]['type']
            
            try:
                    old_req = await message.channel.fetch_message(requests[str(requester_id)]['msg_id'])
                    await old_req.delete()

                    #Remove the old request from the dictionary
                    del requests[str(requester_id)]
                    
                    save_requests(requests, guild_id_str)
                    
            except:
                await message.channel.send('The game request seems to have been lost. Please try again with a new request.')
                
            #Grab the go category of current guild
            go_category = discord.utils.get(message.guild.categories, name='go-games')

            try:
                directory = f'data/{guild_id_str}/games'

                used_ids = []
                
                #Loop through files in this guild's data folder
                for filename in os.listdir(directory):
                    
                    #Extract the room id number from the file name, e.g. if filename is game-room-69.json, then room_id will become 69.
                    room_id = ''.join(char for char in filename if char.isdigit())

                    used_ids.append(room_id)

                count = 0
                while str(count) in used_ids:
                    count += 1
                    
            except:
                await message.channel.send('Error creating game')
                return

            #Set up some variables for the new room
            room_id = count
            room_name = f'game-room-{room_id}'

            #Random turn
            p1_colour = random.choice((1, -1))
            p2_colour = p1_colour * -1
                
            #Create dictionary of game info, and save it in the respectively named json file
            game_info = {'turn': 1,
                          'b_moves': [],
                          'w_moves': [],
                          'empty_pts': [(x, y) for x in range(19) for y in range(19)],
                          'last_move': (),
                          'turn_info': '',
                          'p1_info': [player1.name, player1.id, p1_colour],
                          'p2_info': [player2.name, player2.id, p2_colour],
                          'room_id': room_id,
                          'move_count': 0,
                          'ko': (),
                          'type': game_type,
                          'scoring': False
                         }
            
            #Save info              
            save_game_info(game_info, guild_id_str, room_name)

            #Get the channel using id of a spam channel for sending images, to grab url to be used when editing embeds' images because discord.py poopy and you can't edit an embed's image with a local image
            spam_channel = discord.utils.get(message.guild.channels, name='go-bot-spam')

            #Send the default empty board to the spam channel
            default_board = await spam_channel.send(file=discord.File('baseboard.png')) 

            #Grab names of players based on colour 
            if game_info['p1_info'][2] == 1:
                black_player_name = game_info['p1_info'][0]
                white_player_name = game_info['p2_info'][0]
            else:
                black_player_name = game_info['p2_info'][0]
                white_player_name = game_info['p1_info'][0]
                
            #Set up the embed
            embed = discord.Embed(colour = discord.Colour.dark_orange(),
                                  title = f'{room_name.capitalize()} | Move {game_info["move_count"]}',
                                  description = f'Game started between {game_info["p1_info"][0]} and {game_info["p2_info"][0]}!\n\nBlack: {black_player_name}\nWhite: {white_player_name}\n\nIt\'s {black_player_name}\'s turn to play!',
                                  url = default_board.attachments[0].url)
            
            #Set the embed's image to the URL scraped from the image that was just sent to the spam channel
            embed.set_image(url=default_board.attachments[0].url) 

            #Set footer
            embed.set_footer(text='Click the title for zoomable board!')

            #Set permissions to allow only players in the game to message the channel
            overwrites = {
            message.guild.default_role: discord.PermissionOverwrite(send_messages=False),
            message.guild.me: discord.PermissionOverwrite(send_messages=True),
            player1: discord.PermissionOverwrite(send_messages=True),
            player2: discord.PermissionOverwrite(send_messages=True)
            }
            
            #Create new channel for the game in the correct position down the go-games category
            new_channel = await message.guild.create_text_channel(room_name, category = go_category, position=(room_id+3), overwrites=overwrites)
            
            #Send the embed to the newly created game room channel
            await new_channel.send(embed=embed)

            #Send confirmation that the game has stared to the lobby channel
            go_lobby = discord.utils.get(message.guild.text_channels, name='go-lobby')
            await go_lobby.send(f'A game has started in {room_name} between <@{game_info["p1_info"][1]}> and <@{game_info["p2_info"][1]}>!\nGame type: {get_game_type_info(game_type)}')



        #Command to stop all games and delete data from the server
        if message.content.startswith('!stopallgames'):

            #Check if sender is admin
            if message.author.guild_permissions.administrator:

                #Grab go category
                go_category = discord.utils.get(message.guild.categories, name='go-games')

                #Delete all channels within go category 
                for channel in message.guild.text_channels:
                    if channel.category_id == go_category.id and channel.name.startswith('game-room-'):
                        await channel.delete()

                #Attempt to delete all assosciated data from server 
                try:
                    
                    directory = f'data/{guild_id_str}/games'
                    for filename in os.listdir(directory):
                        if filename.endswith('.json'):
                            os.remove(f'{directory}/{filename}')
                            #print('Deleted file: {}'.format(filename))
                    directory = f'data/{guild_id_str}/boards'
                    for filename in os.listdir(directory):
                        if filename.endswith('.png'):
                            os.remove(f'{directory}/{filename}')
                            #print('Deleted image: {}'.format(filename))
                            
                    await message.channel.send(f'All games stopped successfully. Command ran by: {message.author.mention}')
                    
                except:
                    
                    await message.channel.send(f'All game room channels were deleted however the data was not deleted from the server.')
            else:
                
                await message.channel.send(f'{message.author.mention} you must be an admin to stop all ongoing go games.')


            
    #Check to see if message sent was in a game room
    elif message.channel.name.startswith('game-room-'):

        #Delete the last message
        await message.delete() 

        #Grab the room name
        room_name = message.channel.name

        #Load game info
        game_info = load_game_info(guild_id_str, room_name)
        
        #End game command for admins
        if message.content.startswith('!stop') and message.author.guild_permissions.administrator:

            #Delete the game room
            await message.channel.delete()

            #Grab the go lobby channel to send the response outcome to
            go_lobby = discord.utils.get(message.guild.text_channels, name='go-lobby')

            #Try to delete all assosciated server side files
            try:
                delete_game_data(room_name, guild_id_str)

                await go_lobby.send(f'The game in {room_name} was ended by {message.author.mention}.')
                                    
            except:
                await go_lobby.send(f'The channel \'{room_name}\' was deleted by {message.author.mention}, however the server failed to delete the data.')

            return

        
        #Resign command for players in the game
        if message.content.startswith('!resign'):
                
            #Check that the player is playing in that game
            if(message.author.id == game_info['p1_info'][1]) or (message.author.id == game_info['p2_info'][1]):

                #Check who the exact sender was, and set winner to the other player's name
                if message.author.id == game_info['p1_info'][1]:
                    winner = game_info['p2_info'][1]
                else:
                    winner = game_info['p1_info'][1]
                    
                #Grab the go lobby channel to send the response outcome to
                go_lobby = discord.utils.get(message.guild.text_channels, name='go-lobby')

                #Delete game room channel
                await message.channel.delete()

                try:
                    delete_game_data(room_name, guild_id_str)

                except:
                    print('Error files weren\'t deleted.')

                await go_lobby.send(f'The game in {room_name} has ended. <@{winner}> has won by resignation!')
                
            else:
                await message.author.send('You can\'t resign from a game that isn\'t your own! Start a game with !start!')
                
            return


        if game_info['scoring']:
            
            if not message.content.startswith('!dead'):
                
                if message.content.startswith('!resume'):

                    #Unset scoring check
                    game_info['scoring'] = False

                    save_game_info(game_info, guild_id_str, room_name)

                    #Grab the info of who's turn it is next, since the game resumed
                    next_turn_info = get_next_turn(game_info['turn'], game_info['p1_info'], game_info['p2_info'])

                    #Generate occupied points to be rendered onto the board
                    occupied_points = make_points(game_info['b_moves'], game_info['w_moves'])
                    
                    #Setup new Board_img object (render depending on type)
                    current_board_img = Board_img()
                    current_board_img.render_board(occupied_points, render_type=game_info['type'])
                    current_board_img.save_board(guild_id_str, room_name)

                    #Delete old board object
                    del current_board_img

                    title = f'{room_name.capitalize()} | Move {game_info["move_count"]}'
                    description = f'The game between {game_info["p1_info"][0]} and {game_info["p2_info"][0]} has resumed from scoring!{next_turn_info}'
                    await send_board(guild_id_str, room_name, message, title, description)

                    return

                    #Add !done command here

                return
    
            else:

                dead_stones = message.content.split()[1:]
                if dead_stones:

                    for stone in dead_stones:
                        
                        x, y = check_and_convert_move(stone)
                        move = [x, y]

                        if x == 'invalid' and y == 'invalid':

                            title = f'{room_name.capitalize()} | Remove the dead stones'
                            description = f'{game_info["p1_info"][0]} vs {game_info["p2_info"][0]}\n\n\
                                            {stone} is not a valid coordinate!\n\n{get_dead_cmd_help()}'

                            await send_board(guild_id_str, room_name, message, title, description)

                            return

                        elif move in game_info['b_alive']:
                            
                            #Remove the stone coordinates from the list of alive stones
                            game_info['b_alive'].remove(move)

                            #Append the stone coordinates to the list of empty intersections
                            game_info['empty_pts_scr'].append(move)

                        elif move in game_info['w_alive']:

                            #Remove the stone coordinates from the list of alive stones
                            game_info['w_alive'].remove(move)

                            #Append the stone coordinates to the list of empty intersections
                            game_info['empty_pts_scr'].append(move)

                        else:

                            title = f'{room_name.capitalize()} | Remove the dead stones'
                            description = f'{game_info["p1_info"][0]} vs {game_info["p2_info"][0]}\n\n\
                                            There isn\'t a stone at {stone}.\n\n{get_dead_cmd_help()}'

                            await send_board(guild_id_str, room_name, message, title, description)

                            return   

                    #Save game info
                    save_game_info(game_info, guild_id_str, room_name)

                    #generate occupied pts without using sgfmill (faster) - since no move is being inputted
                    occupied_points = make_points(game_info['b_alive'], game_info['w_alive'])

                    current_board_img = Board_img()
                    current_board_img.render_board(occupied_points, render_type='normal')
                    current_board_img.save_board(guild_id_str, room_name)

                    del current_board_img

                    title = f'{room_name.capitalize()} | Remove the dead stones'
                    description = f'{game_info["p1_info"][0]} vs {game_info["p2_info"][0]}\n\n\
                                    Removed selected dead stones. Continue to remove dead stones or or if you are finished type !done. \
                                    If you made a mistake and want to reset the dead stones, or want to resume the game, type !resume.'

                    await send_board(guild_id_str, room_name, message, title, description)
                    


                else:

                    #No stone coords were give
                    title = f'{room_name.capitalize()} | Remove the dead stones'
                    description = f'{game_info["p1_info"][0]} vs {game_info["p2_info"][0]}\n\n\
                                    You didn\'t list the coordinates of any stones!\n\n{get_dead_cmd_help()}'

                    await send_board(guild_id_str, room_name, message, title, description)


            return

        #Check if the sender is one of the players in the game and that it is their turn
        if (message.author.id == game_info['p1_info'][1] and game_info['p1_info'][2] == game_info['turn']) or (message.author.id == game_info['p2_info'][1] and game_info['p2_info'][2] == game_info['turn']):

            #The !play command appears as !play [move] in the GAME_ROOM_CMDS thus needs extra check
            if message.content.split()[0] not in GAME_ROOM_CMDS and message.content.split()[0] != '!play':

                embed = discord.Embed(colour = discord.Colour.purple(),
                      title = 'That command isn\'t recognised!',
                      description = 'Showing commands useable in game rooms:')

                embed = add_game_room_cmds(GAME_ROOM_CMDS, embed)

                await message.author.send(embed=embed)
                return
            
            #Setup sgfmill board object with data
            current_board = boards.Board(19)
            current_board.apply_setup(game_info['b_moves'], game_info['w_moves'], game_info['empty_pts'])

            #Play move command for players in the game
            if message.content.startswith('!play'):

                command_text = message.content.split()

                move = command_text[1].lower()

                x, y = check_and_convert_move(move)

                if x == 'invalid' and y == 'invalid':
                    #Setup a help message incase the command was incorrect
                    embed = discord.Embed(colour = discord.Colour.purple(),
                                          title = 'That wasn\'t a possible move!',
                                          description = 'Here is how you can play your move in a game:')

                    embed.add_field(name = '!play [move]', value = GAME_ROOM_CMDS['!play [move]'])
                    embed.set_footer(text = 'Good luck :)')
                    await message.author.send(embed=embed)
                    return


                game_info["last_move"] = (x, y)

                game_info["turn_info"] = f'{game_info["p1_info"][0]} vs {game_info["p2_info"][0]}\n\nLast move was {move.capitalize()}: '

                if [x, y] == game_info['ko']:
                    game_info['turn_info'] += 'Uhh it\'s a ko! That\'s an illegal move.'
                else:
                    try:
                        #If it's black's turn, play the move at the given coordinate
                        if game_info["turn"] == 1:

                            #Store the possible future ko coordinate in ko for checks
                            ko = current_board.play(x, y, 'b')

                        #Else if white's turn, do the same for white
                        elif game_info['turn'] == -1:

                            #Same as above
                            ko = current_board.play(x, y, 'w')

                        #If the ko variable is not None, i.e. there is a move which on the next go can break a ko rule, record it in game_info
                        if ko:
                            game_info['ko'] = ko
                        else:
                            game_info['ko'] = ()
                            
                        #If no error has been thrown at this point, the move was successful so record this to be sent in the embed update
                        game_info['turn_info'] += 'Move Successful!'

                        #Update turn and movecount
                        game_info['turn'] *= -1
                        game_info['move_count'] += 1

                        #Reset moves
                        game_info["b_moves"] = []
                        game_info["w_moves"] = []
                        game_info["empty_pts"] = []

                        #Add moves back in, after being updated by sgfmill
                        for x in range(19):
                            for y in range(19):
                                if current_board.get(x, y) == 'b':
                                    game_info['b_moves'].append((x, y))
                                elif current_board.get(x, y) == 'w':
                                    game_info['w_moves'].append((x, y))
                                else:
                                    game_info['empty_pts'].append((x, y))

                        current_board_img = Board_img()
                        current_board_img.render_board(current_board.list_occupied_points(), render_type=game_info['type'])
                        current_board_img.save_board(guild_id_str, room_name)

                        del current_board_img

                    #Called when a stone is placed in a spot already occupied
                    except ValueError: 
                        game_info['turn_info'] += 'Uh oh. This spot is already occupied by a stone!'

                    #Called when a stone is placed in a spot that doesn't exist, e.g. on a 19x19 board, at coordinate 69, 420
                    except IndexError: 
                        game_info['turn_info'] += 'Uh oh. This coordinate doesn\'t exist!'

                    #Eh wtf
                    except:
                        game_info['turn_info'] += 'Something went wrong. Please try again.'

                    embed_title =  f'{room_name.capitalize()} | Move {game_info["move_count"]}'

            #Command to pass
            elif message.content.startswith('!pass'):
                
                #Generate occupied points outside of sgfmill (faster) since no logic is involved
                occupied_points = make_points(game_info['b_moves'], game_info['w_moves'])

                if game_info['last_move'] == 'pass':

                    game_info['turn_info'] = f'{game_info["p1_info"][0]} vs {game_info["p2_info"][0]}\n\nBoth players passed! Game entering scoring phase. (Not yet finished)'
                    game_info['scoring'] = True
                    game_info['b_alive'] = game_info['b_moves']
                    game_info['w_alive'] = game_info['w_moves']
                    game_info['empty_pts_scr'] = game_info['empty_pts']

                    current_board_img = Board_img()
                    current_board_img.render_board(occupied_points, render_type = 'normal')

                    embed_title =  f'{room_name.capitalize()} | Remove the dead stones'

                else:
                    #Edit game info for a pass move
                    game_info["last_move"] = 'pass'
                    game_info["turn_info"] = f'{game_info["p1_info"][0]} vs {game_info["p2_info"][0]}\n\n{message.author.name} just passed!'

                    current_board_img = Board_img()
                    current_board_img.render_board(occupied_points, render_type = game_info['type'])

                    embed_title =  f'{room_name.capitalize()} | Move {game_info["move_count"]}'

                current_board_img.save_board(guild_id_str, room_name)

                del current_board_img

                game_info['turn'] *= -1
                game_info['move_count'] += 1
       
            if not game_info['scoring']:

                game_info['turn_info'] += get_next_turn(game_info['turn'], game_info['p1_info'], game_info['p2_info'])

            #Save game info
            save_game_info(game_info, guild_id_str, room_name)

            #Send the board state
            await send_board(guild_id_str, room_name, message, embed_title, game_info['turn_info'])

        else:
            await message.author.send('It\'s not your turn to make a move in that game!')


client.run(args.token)
