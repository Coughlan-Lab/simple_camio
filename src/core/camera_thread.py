"""
Threaded camera capture for non-blocking frame reading.

This module provides a background thread that continuously reads frames
from the camera, eliminating the blocking wait in the main loop.
"""

import threading
import cv2 as cv
import logging

logger = logging.getLogger(__name__)


class ThreadedCamera:
    """
    Background thread for continuous camera frame capture.
    
    Eliminates blocking cap.read() calls by reading frames in a separate thread.
    """
    
    def __init__(self, cap):
        """
        Initialize threaded camera capture.
        
        Args:
            cap: OpenCV VideoCapture object
        """
        self.cap = cap
        self.ret = False
        self.frame = None
        self.stopped = False
        self.lock = threading.Lock()
        
        # FPS tracking for camera capture rate
        import time
        self.frame_count = 0
        self.fps_start_time = time.time()
        self.camera_fps = 0.0
        
        # Start the background thread
        self.thread = threading.Thread(target=self._read_frames, daemon=True)
        self.thread.start()
        
        # Wait for first frame to be captured
        timeout = 2.0  # Wait up to 2 seconds
        start_time = time.time()
        while self.frame is None and (time.time() - start_time) < timeout:
            time.sleep(0.01)
        
        if self.frame is None:
            logger.warning("ThreadedCamera started but no frame captured yet")
        else:
            logger.info("ThreadedCamera started and ready")
    
    def _read_frames(self):
        """Background thread that continuously reads frames."""
        import time
        while not self.stopped:
            ret, frame = self.cap.read()
            
            with self.lock:
                self.ret = ret
                self.frame = frame
                
                # Update FPS tracking
                self.frame_count += 1
                elapsed = time.time() - self.fps_start_time
                if elapsed >= 1.0:
                    self.camera_fps = self.frame_count / elapsed
                    self.frame_count = 0
                    self.fps_start_time = time.time()
    
    def read(self):
        """
        Get the latest frame (non-blocking).
        
        Returns:
            tuple: (ret, frame) same as cap.read()
        """
        with self.lock:
            # If no frame captured yet, return False and None
            if self.frame is None:
                return False, None
            return self.ret, self.frame.copy()  # Return a copy to avoid race conditions
    
    def stop(self):
        """Stop the background thread."""
        self.stopped = True
        self.thread.join(timeout=1.0)
        logger.info("ThreadedCamera stopped")
    
    def release(self):
        """Release the camera (stops thread and releases VideoCapture)."""
        self.stop()
        self.cap.release()
    
    def isOpened(self):
        """Check if camera is still open."""
        return self.cap.isOpened()
    
    def get_fps(self):
        """
        Get the current camera capture FPS.
        
        Returns:
            float: Camera capture FPS
        """
        with self.lock:
            return self.camera_fps
    
    def get(self, prop):
        """
        Get camera property (pass-through to underlying VideoCapture).
        
        Args:
            prop: OpenCV property constant
            
        Returns:
            Property value
        """
        return self.cap.get(prop)
    
    def set(self, prop, value):
        """
        Set camera property (pass-through to underlying VideoCapture).
        
        Args:
            prop: OpenCV property constant
            value: Value to set
            
        Returns:
            bool: Success status
        """
        return self.cap.set(prop, value)
