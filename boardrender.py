from PIL import Image

def set_pieces(occupied_points):

    with Image.open('baseboard.png') as board: #Open the empty board image
        white = Image.open('white.png')
        black = Image.open('black.png')
        for point in occupied_points:
            
            x = ((point[1][0] + 1) * 2 - 3) * 10 + 22 #Convert point coordinates into pixel coordinates so that the stones are drawn on intersections
            y = ((point[1][1] + 1) * 2 - 3) * 10 + 21
            
            if point[0] == "w":
                #print('Rendering white stone at from coords {}, {} at {}, {}'.format(point[1][0], point[1][1], x, y))
                board.paste(white, (x, y), mask = white) #Paste white stone png at correct coordinate
                    
            elif point[0] == "b":
                board.paste(black, (x, y), mask = black) #Paste black stone png at correct coordinate

        white.close()
        black.close()

        return board #Return the PIL Image object of the board with all of the stones added

def save_board(board, guild_id, filename): #Save a board image as PNG using the ID number
    board.save(f'data/{guild_id}/boards/{filename}.png', "PNG")
