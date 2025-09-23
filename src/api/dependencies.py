from src.config.settings import settings
from src.config import webhooks
from src.database import SignalRepository
from src.services import QueueManager
from src.services import WebhookClient

# Dependency injections
def get_settings():
    return settings

def get_webhook_config():
    return webhooks

def get_repository():
    return SignalRepository(settings.db_path)

def get_queue_manager():
    return QueueManager()

def get_webhook_client():
    return WebhookClient()