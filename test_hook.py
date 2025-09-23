import requests
import json

webhook_url = "https://hook.finandy.com/_QAms23yOJcA7fECrlUK"

data = {
    "name": "BOMEUSDTS",
    "secret": "iiulp5at4jn",
    "side": "buy",
    "symbol": "BOMEUSDT",
    "close": {
        "action": "decrease",
        "decrease": {
            "type": "posAmountPct",
            "amount": "1"
        },
        "checkProfit": True,
        "price": ""
    },
    "open": {
        "amountType": "sumUsd",
        "amount": "6",
        "enabled": True
    },
    "dca": {
        "amountType": "sumUsd",
        "amount": "6",
        "checkProfit": False
    },
    "tp": {
        "orders": [
            {"price": "", "piece": "50.0"},
            {"price": "", "piece": "23.0"},
            {"price": "", "piece": "27.0"},
            {"price": "", "piece": "45.0"}
        ],
        "update": False
    },
    "sl": {
        "price": "",
        "update": False
    }
}

response = requests.post(webhook_url, json=data)
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")