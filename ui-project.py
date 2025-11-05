import tkinter as tk
from pynput.keyboard import Key, Controller
import cv2  # OpenCV
from PIL import Image, ImageTk  # Pillow
import sys
import time

class HandGestureApp:
    def __init__(self, root):
        self.root = root
        self.root.title("App GUI")
        self.root.geometry("500x600")
 

        title = tk.Label(text="AI Layout")
        title.pack()


if __name__ == "__main__":
    root = tk.Tk()
    app = HandGestureApp(root)
    root.mainloop()





