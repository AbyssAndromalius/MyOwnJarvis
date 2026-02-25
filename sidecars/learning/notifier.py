"""
Desktop notification wrapper using notify-send.
"""
import subprocess
import logging
from config import get_config

logger = logging.getLogger(__name__)


class Notifier:
    """Handles desktop notifications using notify-send."""
    
    def __init__(self):
        """Initialize notifier with config."""
        config = get_config()
        self.enabled = config.notification.enabled
        self.command = config.notification.command
    
    def _check_available(self) -> bool:
        """
        Check if notify-send is available on the system.
        
        Returns:
            True if notify-send is available, False otherwise
        """
        try:
            result = subprocess.run(
                ["which", self.command],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning(f"Failed to check for {self.command}: {e}")
            return False
    
    def send(self, title: str, message: str) -> bool:
        """
        Send a desktop notification.
        
        Args:
            title: Notification title
            message: Notification message
            
        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("Notifications disabled in config")
            return False
        
        if not self._check_available():
            logger.warning(f"{self.command} not available, skipping notification")
            return False
        
        try:
            subprocess.run(
                [self.command, title, message],
                check=False,
                timeout=5,
                capture_output=True
            )
            logger.info(f"Notification sent: {title}")
            return True
        except Exception as e:
            logger.warning(f"Failed to send notification: {e}")
            return False
    
    def notify_learning_review(self, count: int = 1):
        """
        Send notification for learning review.
        
        Args:
            count: Number of corrections pending review
        """
        title = "Jarvis — Learning Review"
        message = f"{count} correction{'s' if count > 1 else ''} en attente d'approbation. Run: python scripts/review_learning.py list"
        self.send(title, message)
