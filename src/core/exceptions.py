class WebhookException(Exception):
    """Базовое исключение для вебхуков"""
    pass

class SymbolNotFoundException(WebhookException):
    """Исключение для неизвестных символов"""
    pass

class WebhookSendException(WebhookException):
    """Исключение при отправке вебхука"""
    pass

class QueueNotFoundException(WebhookException):
    """Исключение для отсутствующих очередей"""
    pass