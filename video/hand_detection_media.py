import cv2
import hand_detection_media as mp

# Initialize MediaPipe Hands
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

# Initialize the Hands model
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=2,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Capture video from webcam
cap = cv2.VideoCapture(0)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        print("Failed to grab frame")
        break
    
    # Convert BGR to RGB
    image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    image.flags.writeable = False
    
    # Process the frame
    results = hands.process(image)
    
    # Convert back to BGR for display
    image.flags.writeable = True
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    
    # Get bounding box if hands are detected
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            # Get image dimensions
            h, w, c = image.shape
            
            # Extract x and y coordinates from all landmarks
            x_coords = [lm.x for lm in hand_landmarks.landmark]
            y_coords = [lm.y for lm in hand_landmarks.landmark]
            
            # Calculate bounding box (normalized coordinates 0-1)
            x_min = min(x_coords)
            x_max = max(x_coords)
            y_min = min(y_coords)
            y_max = max(y_coords)
            
            # Add padding (10% on each side)
            padding = 0.1
            width = x_max - x_min
            height = y_max - y_min
            
            x_min = max(0, x_min - padding * width)
            x_max = min(1, x_max + padding * width)
            y_min = max(0, y_min - padding * height)
            y_max = min(1, y_max + padding * height)
            
            # Convert to pixel coordinates
            x_min_px = int(x_min * w)
            x_max_px = int(x_max * w)
            y_min_px = int(y_min * h)
            y_max_px = int(y_max * h)
            
            # Draw bounding box (green rectangle)
            cv2.rectangle(image, (x_min_px, y_min_px), 
                         (x_max_px, y_max_px), (0, 255, 0), 2)
            
            # Optional: Add label with box dimensions
            label = f"Hand: {x_max_px - x_min_px}x{y_max_px - y_min_px}"
            cv2.putText(image, label, (x_min_px, y_min_px - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Draw hand landmarks
            mp_drawing.draw_landmarks(
                image, hand_landmarks, mp_hands.HAND_CONNECTIONS)
    
    # Display the frame
    cv2.imshow('Hand Bounding Box Detection', image)
    
    # Press 'q' to quit
    if cv2.waitKey(5) & 0xFF == ord('q'):
        break

# Cleanup
cap.release()
cv2.destroyAllWindows()
hands.close()