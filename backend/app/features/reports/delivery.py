import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseDeliveryChannel(ABC):
    """Abstract Base Class defining the contract for deliverable channels (SOLID)."""

    @abstractmethod
    def deliver(self, report_path: str, recipient: str, report_title: str) -> bool:
        """Sends the compiled report file to the target recipient."""
        pass


class EmailDeliveryChannel(BaseDeliveryChannel):
    """Mock Email delivery channel logging delivery and preparing SMTP hooks."""

    def deliver(self, report_path: str, recipient: str, report_title: str) -> bool:
        logger.info(f"Delivering report '{report_title}' to email recipient: {recipient}")
        # Log details to demonstrate simulated delivery channel
        print(f"\n--- [SMTP EMAIL DELIVERY MOCK] ---")
        print(f"To: {recipient}")
        print(f"Subject: Business Intelligence Review: {report_title}")
        print(f"Attachment: {report_path}")
        print(f"Body: Dear Executive,\n\nYour scheduled business intelligence report is compiled and attached.\n\nBest regards,\nExecutive Intelligence Platform")
        print(f"-----------------------------------\n")
        return True
