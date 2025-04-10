import datetime
import logging
import re
import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_serializer, field_validator

from errorscraper.enums import EventPriority

LOG_LEVEL_MAP = {
    logging.INFO: EventPriority.INFO,
    logging.WARNING: EventPriority.WARNING,
    logging.ERROR: EventPriority.ERROR,
    logging.CRITICAL: EventPriority.CRITICAL,
    logging.FATAL: EventPriority.CRITICAL,
}


class Event(BaseModel):
    """Base event class"""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    reporter: str = "ERROR_SCRAPER"
    category: str
    description: str
    data: dict = Field(default_factory=dict)
    priority: EventPriority
    system_id: Optional[str] = None

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, timestamp: datetime.datetime) -> datetime.datetime:
        """validate timestamp, will convert to utc timezone as long as input is timezone aware
        Args:
            timestamp (datetime): datetime object
        Raises:
            ValueError: if value is not a datetime object
            ValueError: if value is not timezone aware
        Returns:
            datetime: validated datetime
        """

        if timestamp.tzinfo is None or timestamp.tzinfo.utcoffset(timestamp) is None:
            raise ValueError("datetime must be timezone aware")

        if timestamp.utcoffset().total_seconds() != 0:
            timestamp = timestamp.astimezone(datetime.timezone.utc)

        return timestamp

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, category: str | Enum) -> str:
        """ensure category is has consistent formatting
        Args:
            category (str | Enum): category string
        Returns:
            str: formatted category string
        """
        if isinstance(category, Enum):
            category = category.value

        category = category.strip().upper()
        category = re.sub(r"[\s-]", "_", category)
        return category

    @field_validator("priority", mode="before")
    @classmethod
    def validate_priority(cls, priority: str | EventPriority) -> EventPriority:
        """Allow priority to be set via string priority name
        Args:
            priority (str | EventPriority): event priority string or enum
        Raises:
            ValueError: if priority string is an invalid value
        Returns:
            EventPriority: priority enum
        """

        if isinstance(priority, str):
            try:
                return getattr(EventPriority, priority.upper())
            except AttributeError as e:
                raise ValueError(
                    f"priority must be one of {[priority_enum.name for priority_enum in EventPriority]}"
                ) from e

        return priority

    @field_serializer("priority")
    def serialize_priority(self, priority: EventPriority, _info) -> str:
        """Use priority name when serializing events
        Args:
            priority (EventPriority): priority enum
        Returns:
            str: priority name string
        """
        return priority.name

    @field_validator("data")
    @classmethod
    def validate_data(cls, data: dict) -> dict:
        """Ensure data is below 100KB
        Args:
            data (dict): data input
        Raises:
            ValueError: When data is above 100KB in size
        Returns:
            dict: data output
        """
        if len(str(data).encode("utf-8")) >= (1024 * 100):
            raise ValueError("Data must be below 100KB in size")
        return data

    @field_validator("description")
    @classmethod
    def validate_description(cls, desc: str) -> str:
        """Ensure description is below 2KB
        Args:
            desc (str): description input
        Raises:
            ValueError: When desc is above 2KB in size
        Returns:
            str: desc output
        """
        if len(desc.encode("utf-8")) >= 1024 * 2:
            raise ValueError("Description must be below 2KB in size")
        return desc
