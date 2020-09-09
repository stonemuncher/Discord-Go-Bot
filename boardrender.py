from PIL import Image

class Board_img:
    def __init__(self):

        #Open image files
        self.white = Image.open('white.png')
        self.black = Image.open('black.png')
        self.board = Image.open('baseboard.png')

    def coordinate_to_pixel(self, x, y):
        
        #Necessary so that stones are drawn on intersections
        x = ((x + 1) * 2 - 3) * 10 + 22
        y = ((y + 1) * 2 - 3) * 10 + 21

        return (x, y)
    
    def render_board(self, occupied_points, render_type = 'normal', last_move = []):
        
            if not occupied_points:

                #Since no changes will be made to the image object, load the pixel data into memory so that it can be returned (otherwise will be NoneType object)
                #This is because PIL will not load data from a file when it is opened - only when it is loaded via load() or changed in some way such as with paste()
                self.board.load()

            else:
                if render_type == 'blind':
                    #No need to update board for pass
                    if last_move == 'pass':
                        return
                    
                    pixel_coords = self.coordinate_to_pixel(last_move[0], last_move[1])

                    #Only update the board with the last move
                    self.board.paste(self.black, pixel_coords, mask = self.black)

                else:
                    
                    for point in occupied_points:
                        
                        pixel_coords = self.coordinate_to_pixel(point[1][0], point[1][1])

                        if render_type == 'onecolour': 
                            self.board.paste(self.white, pixel_coords, mask = self.white) #One colour only :)
                            
                        elif point[0] == "w":
                            self.board.paste(self.white, pixel_coords, mask = self.white) #Paste white stone png at correct coordinate
                                
                        elif point[0] == "b":
                            self.board.paste(self.black, pixel_coords, mask = self.black) #Paste black stone png at correct coordinate
                
            return self.board

    def save_board(self, guild_id, room_name):

            #Save the PIL image
            self.board.save(f'data/{guild_id}/boards/{room_name}.png', "PNG")

    def __del__(self):

        #Close image files
        self.white.close()
        self.black.close()
        self.board.close()
