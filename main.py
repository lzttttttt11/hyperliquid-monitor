import requests
import time
import os
from datetime import datetime

# ============ НАСТРОЙКИ ============

WALLET_ADDRESS = "0xb317d2bc2d3d2df5fa441b5bae0ab9d8b07283ae"

TELEGRAM_BOT_TOKEN = os.environ.get("telegram_bot_token")
TELEGRAM_CHAT_ID = os.environ.get("telegram_chat_id")

CHECK_INTERVAL = 15 * 60  # 15 минут

HYPERLIQUID_API = "https://api.hyperliquid.xyz/info"

# ==================================


def get_positions(wallet: str) -> list:
    """Получает открытые позиции пользователя"""
    payload = {
        "type": "clearinghouseState",
        "user": wallet
    }
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(HYPERLIQUID_API, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        positions = data.get("assetPositions", [])
        
        open_positions = []
        for pos in positions:
            position_data = pos.get("position", {})
            size = float(position_data.get("szi", 0))
            if size != 0:
                open_positions.append({
                    "coin": position_data.get("coin"),
                    "size": size,
                    "entry_price": position_data.get("entryPx"),
                    "unrealized_pnl": position_data.get("unrealizedPnl"),
                    "leverage": position_data.get("leverage", {}).get("value"),
                    "side": "LONG" if size > 0 else "SHORT"
                })
        
        return open_positions
    
    except Exception as e:
        print(f"[ERROR] Ошибка при получении позиций: {e}")
        return None


def send_telegram_message(message: str):
    """Отправляет сообщение в Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print(f"[OK] Сообщение отправлено в Telegram")
        else:
            print(f"[ERROR] Ошибка Telegram: {response.text}")
    except Exception as e:
        print(f"[ERROR] Не удалось отправить в Telegram: {e}")


def format_positions(positions: list) -> str:
    """Форматирует позиции для вывода"""
    if not positions:
        return "Нет открытых позиций"
    
    result = []
    for pos in positions:
        result.append(
            f"• {pos['coin']} {pos['side']}\n"
            f"  Size: {pos['size']}\n"
            f"  Entry: ${pos['entry_price']}\n"
            f"  PnL: ${pos['unrealized_pnl']}"
        )
    return "\n".join(result)


def main():
    print(f"🚀 Запуск мониторинга позиций")
    print(f"📍 Кошелёк: {WALLET_ADDRESS}")
    print(f"⏱️  Интервал: {CHECK_INTERVAL // 60} минут")
    print("-" * 50)
    
    # Проверяем наличие переменных окружения
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[ERROR] Не заданы TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID")
        return
    
    # Получаем начальное состояние
    previous_positions = get_positions(WALLET_ADDRESS)
    
    if previous_positions is None:
        print("[ERROR] Не удалось получить начальные данные")
        send_telegram_message("❌ Ошибка запуска мониторинга: не удалось получить данные с Hyperliquid")
        return
    
    if not previous_positions:
        print("[INFO] У пользователя нет открытых позиций")
        send_telegram_message(
            f"⚠️ <b>Мониторинг запущен</b>\n\n"
            f"Кошелёк: <code>{WALLET_ADDRESS[:10]}...{WALLET_ADDRESS[-6:]}</code>\n"
            f"Статус: Нет открытых позиций\n\n"
            f"Буду проверять каждые 15 минут на появление новых позиций."
        )
    else:
        send_telegram_message(
            f"✅ <b>Мониторинг запущен</b>\n\n"
            f"Кошелёк: <code>{WALLET_ADDRESS[:10]}...{WALLET_ADDRESS[-6:]}</code>\n\n"
            f"<b>Текущие позиции:</b>\n{format_positions(previous_positions)}"
        )
        
        print(f"[INFO] Найдено позиций: {len(previous_positions)}")
        for pos in previous_positions:
            print(f"  → {pos['coin']} {pos['side']} | Size: {pos['size']}")
    
    # Основной цикл мониторинга
    while True:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Ожидание {CHECK_INTERVAL // 60} минут...")
        time.sleep(CHECK_INTERVAL)
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Проверка позиций...")
        
        current_positions = get_positions(WALLET_ADDRESS)
        
        if current_positions is None:
            print("[WARNING] Ошибка API, пропускаем итерацию")
            continue
        
        # Сравниваем с предыдущим состоянием
        prev_coins = {p['coin'] for p in previous_positions} if previous_positions else set()
        curr_coins = {p['coin'] for p in current_positions} if current_positions else set()
        
        # Проверяем закрытые позиции
        closed_coins = prev_coins - curr_coins
        
        if closed_coins:
            closed_positions = [p for p in previous_positions if p['coin'] in closed_coins]
            
            message = f"🔴 <b>ПОЗИЦИЯ ЗАКРЫТА!</b>\n\n"
            for pos in closed_positions:
                message += (
                    f"Монета: <b>{pos['coin']}</b>\n"
                    f"Тип: {pos['side']}\n"
                    f"Размер: {pos['size']}\n"
                    f"Entry: ${pos['entry_price']}\n\n"
                )
            message += f"Кошелёк: <code>{WALLET_ADDRESS[:10]}...{WALLET_ADDRESS[-6:]}</code>"
            
            send_telegram_message(message)
            print(f"[ALERT] Закрыты позиции: {closed_coins}")
        
        # Проверяем новые позиции
        new_coins = curr_coins - prev_coins
        if new_coins:
            new_positions = [p for p in current_positions if p['coin'] in new_coins]
            
            message = f"🟢 <b>НОВАЯ ПОЗИЦИЯ!</b>\n\n"
            for pos in new_positions:
                message += (
                    f"Монета: <b>{pos['coin']}</b>\n"
                    f"Тип: {pos['side']}\n"
                    f"Размер: {pos['size']}\n"
                    f"Entry: ${pos['entry_price']}\n\n"
                )
            message += f"Кошелёк: <code>{WALLET_ADDRESS[:10]}...{WALLET_ADDRESS[-6:]}</code>"
            
            send_telegram_message(message)
            print(f"[ALERT] Новые позиции: {new_coins}")
        
        # Обновляем состояние
        previous_positions = current_positions
        print(f"[OK] Активных позиций: {len(current_positions)}")


if __name__ == "__main__":
    main()
