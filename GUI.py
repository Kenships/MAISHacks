from tkinter import *
from numpy import *
from pyaudio import *
from os import *
import cv2

# Define the window
root = Tk()
root.title("Song visualizer 1.0.0")
root.geometry("1200x800")

# Define images
shuffleImage = PhotoImage(file="shuffle.png")
prevImage = PhotoImage(file="previous_button.png")
playImage = PhotoImage(file="play_button.png")
nextImage = PhotoImage(file="next_button.png")
repeatImage = PhotoImage(file="repeat.png")


#Define all labels
nowPlayingLabel = Label(root, text="Now playing")
songTitle = Label(root, text="Song title", width=20, height=0)
authorTitle = Label(root, text="Author title", width=20, height=0)

# Define waveform display + webcam
webcam = cv2.VideoCapture(0)
while True:
    ret, frame = webcam.read()
    if not ret:
        break
    cv2.imshow('Webcam', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
# Define all buttons
slider = Scale(root, from_ = 0, to = 100, orient = "horizontal")
shuffleBtn = Button(root, image = shuffleImage)
prevBtn = Button(root, image = prevImage)
playBtn = Button(root, image = playImage)
nextBtn = Button(root, image = nextImage)
repeatBtn = Button(root, image = repeatImage)
soundBar = Scale(root, from_ = 0, to = 100, orient = "horizontal")

# Add the widgets to the GUI
nowPlayingLabel.pack()
songTitle.pack()
authorTitle.pack()

slider.pack()
shuffleBtn.pack()
prevBtn.pack()
playBtn.pack()
nextBtn.pack()
repeatBtn.pack()
soundBar.pack()

webcam.release()
cv2.destroyAllWindows()
root.mainloop()