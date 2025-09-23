from config.settings import settings
from config import webhooks
from database.repository import SignalRepository
from services.queue_service import QueueManager
from services.webhook_service import WebhookClient

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