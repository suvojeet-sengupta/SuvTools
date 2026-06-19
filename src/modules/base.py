from abc import ABC, abstractmethod
from telegram.ext import Application

class BaseModule(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the module."""
        pass

    @abstractmethod
    def register_handlers(self, application: Application) -> None:
        """Register the telegram handlers for this module."""
        pass
