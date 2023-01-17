import cv2
import time


import numpy as np


import Card_detector_classes

'''
static variables
'''
#adaptive threshold
BKG_TRESHOLD = 60
CARD_THRESHOLD = 30

#size of cards
CARD_AREA_MIN = 120000
CARD_AREA_MAX = 25000

#width and height of corner, where importatnt data are
CORNER_WIDTH = 32
CORNER_HEIGHT = 84

def load_ranks(path):
    train_ranks = []
    i = 0
    
    card_to_get = ["Ace", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Jack", "Queen", "King"]
    
    for name in card_to_get:
        #append array by class object
        train_ranks.append(Card_detector_classes.Train_ranks())
        train_ranks[i].name = name
        
        filename = name + '.jpg' #define namefile to be downloaded
        
        train_ranks[i].image = cv2.imread(path + filename, cv2.IMREAD_GRAYSCALE)
        i += 1
    return train_ranks        
    
def load_suits(path):
    train_suits = []
    i = 0
    
    card_to_get = ["Clubs", "Hearts", "Spades", "Diamonds"]
    
    for name in card_to_get:
        #append array by class object
        train_suits.append(Card_detector_classes.Train_suits())
        train_suits[i].name = name
        
        filename = name + '.jpg' #define namefile to be downloaded
        
        train_suits[i].image = cv2.imread(path + filename, cv2.IMREAD_GRAYSCALE)
        i += 1
    return train_suits  

def preprocess_frame(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    
    #adaptive treshold
    img_weight, img_height = np.shape(frame)[:2]
    bkg_level = gray[int(img_height/100)][int(img_weight/2)]
    threshold_level = bkg_level + BKG_TRESHOLD
    
    retval, threshold = cv2.threshold(blur, threshold_level, 255, cv2.THRESH_BINARY)
    
    return threshold

def flattener(img, points, width, height):
    temp_rectangle = np.zeros((4, 2), dtype= 'float32')
    
    points_sum = np.sum(points, axis= 2)
    tl = points[np.argmin(points_sum)]
    br = points[np.argmax(points_sum)]
    
    points_diff = np.diff(points, axis= -1)
    tr = points[np.argmin(points_diff)]
    bl = points[np.argmax(points_diff)]
    
    if(width <= 0.8*height):        #if card oriented vertically
        temp_rectangle[0] = tl
        temp_rectangle[1] = tr
        temp_rectangle[2] = br
        temp_rectangle[3] = bl  
    elif(width >= 1.2*height):      #if card oriented horizontally
        temp_rectangle[0] = bl
        temp_rectangle[1] = tl
        temp_rectangle[2] = tr
        temp_rectangle[3] = br
    else:                           #else if card is oriented diamon, we need to identyficate which point is which
        if points[1][0][1] <= points[3][0][1]:
            temp_rectangle[0] = points[1][0]    #top left
            temp_rectangle[1] = points[0][0]    #top right
            temp_rectangle[2] = points[3][0]    #bottom left
            temp_rectangle[3] = points[2][0]    #bottom right
        else:
            temp_rectangle[0] = points[0][0]    #top left
            temp_rectangle[1] = points[3][0]    #top right
            temp_rectangle[2] = points[2][0]    #bottom left
            temp_rectangle[3] = points[1][0]    #bottom right
            
    max_width = 200
    max_height = 300
    
    #create destination array, calculate perspective to transform matrix
    
    destination = np.array([[0, 0], 
                            [max_width - 1, 0], 
                            [max_width - 1 ,max_height - 1], 
                            [0, max_height - 1]], np.float32)
    
    M = cv2.getPerspectiveTransform(temp_rectangle, destination)

    #create wrapped card image
    wrap = cv2.wrapPerspective(img, M, (max_width, max_height))
    wrap = cv2.cvtColor(wrap, cv2.COLOR_BGR2GRAY)
    
    return wrap

def find_card(pre_processed_frame):
    
    contours, hierarchy = cv2.findContours(pre_processed_frame, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    sort = sorted(range(len(contours)), key= lambda i : cv2.contourArea(contours[i]), reverse = True)     #sort finded contours
    
    #if there is no countours finded, do nothing
    if len(contours) == 0:
        return [],[]
    
    #otherwise, process finded contours
    contours_sort = []
    hierarchy_sort = []
    
    contours_is_card = np.zeros(len(contours))
    
    #now insert sorted list into free table
    for i in sort:
        contours_sort.append(contours[i])
        hierarchy_sort.append(hierarchy[0, i])
        
    '''now determine which contour is card by criteria
        1) smaller area than max card size
        2) bigger area than min card size
        3) have no parents
        4) have 4 corners
    '''
    for i in range(len(contours_sort)):
        size = cv2.contourArea(contours_sort[i])
        retval = cv2.arcLength(contours_sort[i], True)
        approxima = cv2.approxPolyDP(contours_sort[i], 0.01*retval, True)
        
        if((size > CARD_AREA_MIN) and (size < CARD_AREA_MAX) and (hierarchy_sort[i][3] == -1) and (len(approxima) == 4)):
            contours_is_card[i] = 1
    
    return contours_sort, contours_is_card

def process_card(contour, cur_image):
    
    #inicjalize new instance of Query_card
    querry_card = Card_detector_classes.Query_card()
    
    querry_card.contour = contour
    
    #find perimeter if card, use it to approximate corner points
    retval = cv2.arcLength(contour, True)
    approxima = cv2.approxPolyDP(contour, 0.01*retval, True)
    points = np.float32(approxima)
    querry_card.corner_pts = points
    
    #detect width and height
    x, y, width, height = cv2.boundingRect(contour)
    querry_card.width = width
    querry_card.height = height
    
    
    #find center of card by takink x, y and 4 corners
    average = np.sum(points, axis=0)/len(points)
    center_x = int(average[0][0])
    center_y = int(average[0][1])
    querry_card.center = [center_x, center_y]
    
    
    #wrap card into 200x300 flat image using perspective transform
    querry_card.wrap = flattener(image, points, width, height)