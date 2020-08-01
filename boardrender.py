from PIL import Image

def coordinate_to_pixel(x, y):
    
    #Necessary so that stones are drawn on intersections
    x = ((x + 1) * 2 - 3) * 10 + 22 
    y = ((y + 1) * 2 - 3) * 10 + 21

    return (x, y)
    
def set_pieces(occupied_points = [ ], one_colour = False, blind = False, last_move = ()):

    #Open the empty board image
    with Image.open('baseboard.png') as board: 

        #Load stone image files
        white = Image.open('white.png')
        black = Image.open('black.png')

        if blind:

            #No need to update board for pass
            if last_move == 'pass':
                return
            
            pixel_coords = coordinate_to_pixel(last_move[0], last_move[1])

            #Only update the board with the last move
            board.paste(black, pixel_coords, mask = black)

        else:
            
            for point in occupied_points:
                
                pixel_coords = coordinate_to_pixel(point[1][0], point[1][1])

                if one_colour: 
                    board.paste(white, pixel_coords, mask = white) #One colour only :)
                    
                elif point[0] == "w":
                    board.paste(white, pixel_coords, mask = white) #Paste white stone png at correct coordinate
                        
                elif point[0] == "b":
                    board.paste(black, pixel_coords, mask = black) #Paste black stone png at correct coordinate

        white.close()
        black.close()

        return board #Return the PIL Image object of the board with all of the stones added


def save_board(board, guild_id, filename): #Save a board image as PNG using the ID number
    board.save(f'data/{guild_id}/boards/{filename}.png', "PNG")
