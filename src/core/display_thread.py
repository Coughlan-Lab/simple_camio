"""
Display thread module for non-blocking frame rendering.

This module implements a background thread that handles cv.imshow() calls
without blocking the main processing loop. Frames are queued and displayed
asynchronously, allowing the main loop to run at full speed.
"""

import cv2 as cv
import threading
import queue
import logging
import time

logger = logging.getLogger(__name__)


class DisplayThread:
    """
    Background thread for non-blocking frame display.
    
    This thread continuously pulls frames from a queue and displays them
    using cv.imshow(). The main loop can continue processing at full speed
    while this thread handles the slower display operations.
    
    Attributes:
        window_name (str): Name of the OpenCV window
        queue (queue.Queue): Thread-safe queue for frame data
        thread (threading.Thread): Background display thread
        stop_event (threading.Event): Signal to stop the thread
        running (bool): Thread running state
    """
    
    def __init__(self, window_name='Simple CamIO', max_queue_size=2):
        """
        Initialize the display thread.
        
        Args:
            window_name (str): Name for the OpenCV window
            max_queue_size (int): Maximum frames to queue (drop older frames if full)
        """
        self.window_name = window_name
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.stop_event = threading.Event()
        self.thread = None
        self.running = False
        self.last_waitkey = 255  # Store last key press
        self.key_consumed = True  # Track if key has been consumed by main loop
        self.key_lock = threading.Lock()
        
        logger.info(f"DisplayThread initialized with window '{window_name}'")
    
    def start(self):
        """Start the display thread."""
        if self.running:
            logger.warning("DisplayThread already running")
            return
        
        self.running = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._display_loop, daemon=True)
        self.thread.start()
        logger.info("DisplayThread started")
    
    def stop(self):
        """Stop the display thread and close window."""
        if not self.running:
            return
        
        logger.info("Stopping DisplayThread...")
        self.stop_event.set()
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
        
        self.running = False
        cv.destroyWindow(self.window_name)
        logger.info("DisplayThread stopped")
    
    def show(self, frame):
        """
        Queue a frame for display (non-blocking).
        
        Args:
            frame: Image frame to display
            
        Returns:
            bool: True if frame was queued, False if queue was full
        """
        if not self.running:
            logger.warning("DisplayThread not running, call start() first")
            return False
        
        try:
            # Try to put frame without blocking
            # If queue is full, drop the oldest frame and try again
            try:
                self.queue.put_nowait(frame)
                return True
            except queue.Full:
                # Drop oldest frame
                try:
                    _ = self.queue.get_nowait()
                except queue.Empty:
                    pass
                # Try again
                self.queue.put_nowait(frame)
                return True
        except Exception as e:
            logger.error(f"Error queuing frame for display: {e}")
            return False
    
    def get_last_key(self):
        """
        Get the last key pressed (non-blocking).
        Clears the stored key after reading to prevent duplicate processing.
        
        Returns:
            int: Last key code (255 if no key pressed)
        """
        with self.key_lock:
            key = self.last_waitkey
            self.last_waitkey = 255  # Always reset after reading
            return key
    
    def _display_loop(self):
        """
        Background thread loop that displays frames.
        
        This runs continuously, pulling frames from the queue and
        displaying them with cv.imshow(). It also handles keyboard
        input via cv.waitKey().
        """
        logger.info("Display loop started")
        
        # Create window
        cv.namedWindow(self.window_name, cv.WINDOW_NORMAL)
        
        while not self.stop_event.is_set():
            try:
                # Get frame with timeout (don't block forever)
                frame = self.queue.get(timeout=0.1)
                
                # Display the frame
                cv.imshow(self.window_name, frame)
                
                # Check for keyboard input (1ms wait)
                # This is what makes cv.imshow() actually update
                key = cv.waitKey(1) & 0xFF
                
                # Store key if pressed
                if key != 255:
                    with self.key_lock:
                        # Always update to capture the latest key press
                        # Critical keys like 'q' should not be missed
                        self.last_waitkey = key
                        logger.debug(f"Key pressed: {key} ({chr(key) if 32 <= key < 127 else 'special'})")
                
            except queue.Empty:
                # No frame available, just check for keys
                key = cv.waitKey(1) & 0xFF
                if key != 255:
                    with self.key_lock:
                        # Always update to capture the latest key press
                        self.last_waitkey = key
                        logger.debug(f"Key pressed: {key} ({chr(key) if 32 <= key < 127 else 'special'})")
            except Exception as e:
                logger.error(f"Error in display loop: {e}", exc_info=True)
                time.sleep(0.01)  # Avoid tight loop on error
        
        logger.info("Display loop exiting")
