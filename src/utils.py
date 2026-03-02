import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import requests

from config import API_KEY

# Настройка логгера
logger = logging.getLogger(__name__)


def get_greeting(hour: int) -> str:
    """Возвращает приветствие в зависимости от времени суток."""
    if 6 <= hour < 12:
        return "Доброе утро"
    elif 12 <= hour < 18:
        return "Добрый день"
    elif 18 <= hour < 23:
        return "Добрый вечер"
    else:
        return "Доброй ночи"


def load_transactions_from_xlsx(filepath: str) -> pd.DataFrame:
    """Загружает транзакции из Excel-файла."""
    logger.info("Загрузка транзакций из файла: %s", filepath)
    try:
        df = pd.read_excel(filepath)
        logger.info("Успешно загружено %d транзакций.", len(df))
    except FileNotFoundError:
        logger.error("Файл %s не найден.", filepath)
        raise
    except Exception as e:
        logger.error("Ошибка при чтении файла %s: %s", filepath, e)
        raise

    # Приведение типов и обработка дат
    # Формат даты 'DD.MM.YYYY HH:MM:SS'
    df["Дата операции"] = pd.to_datetime(df["Дата операции"], format="%d.%m.%Y %H:%M:%S", errors="coerce")
    df["Сумма операции"] = pd.to_numeric(df["Сумма операции"], errors="coerce")
    df["Округление на инвесткопилку"] = pd.to_numeric(df["Округление на инвесткопилку"], errors="coerce")
    # Заполняем NaN в 'Округление на инвесткопилку' значением 0, чтобы суммировать корректно
    df["Округление на инвесткопилку"] = df["Округление на инвесткопилку"].fillna(0)
    # Обработка текстовых полей: заменяем NaN/None на пустые строки
    text_columns = ["Описание", "Категория", "Статус", "Номер карты"]
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    logger.debug("Типы данных в столбцах приведены.")
    return df


def filter_transactions_by_date_range(transactions: pd.DataFrame, target_date_str: str) -> pd.DataFrame:
    """Фильтрует транзакции с начала месяца по заданную дату."""
    logger.debug("Фильтрация транзакций по дате: %s", target_date_str)
    # Формат даты 'DD.MM.YYYY HH:MM:SS'
    target_date = datetime.strptime(target_date_str, "%d.%m.%Y %H:%M:%S")
    start_of_month = target_date.replace(day=1)
    filtered_df = transactions[
        (transactions["Дата операции"] >= start_of_month) & (transactions["Дата операции"] <= target_date)
    ].copy()
    logger.info("После фильтрации осталось %d транзакций.", len(filtered_df))
    return filtered_df


def calculate_cards_data(transactions: pd.DataFrame) -> List[Dict[str, Any]]:
    """Рассчитывает данные по картам: расходы и кэшбэк."""
    logger.debug("Расчёт данных по картам.")
    # Оставляем только успешные расходы (Статус = 'OK' и Сумма операции < 0)
    expense_transactions = transactions[(transactions["Статус"] == "OK") & (transactions["Сумма операции"] < 0)]

    # Группировка по номеру карты
    # Используем 'Номер карты', который может быть NaN. Группировка автоматически исключает NaN.
    cards_summary = (
        expense_transactions.groupby("Номер карты")
        .agg(
            total_spent=("Сумма операции", lambda x: x.sum() * -1),
            # Умножаем на -1, чтобы получить положительную сумму расходов
        )
        .reset_index()
    )

    result = []
    for _, row in cards_summary.iterrows():
        # last_digits - это последние 4 цифры номера карты
        card_number = row["Номер карты"]
        last_digits = card_number[-4:] if pd.notna(card_number) else "N/A"  # Обработка случая, когда карта не указана

        total_spent = row["total_spent"]
        # Расчёт кэшбэка: 1% от суммы расходов (1 рубль на каждые 100 рублей)
        calculated_cashback = round(total_spent / 100, 2) if pd.notna(total_spent) else 0.0

        result.append(
            {
                "last_digits": last_digits,
                "total_spent": round(total_spent, 2),
                "cashback": float(calculated_cashback),  # Кэшбэк рассчитывается автоматически
            }
        )
    logger.info("Обработаны данные для %d карт.", len(result))
    return result


def get_top_transactions(transactions: pd.DataFrame, n: int = 5) -> List[Dict[str, Any]]:
    """Возвращает топ-N транзакций по абсолютному значению суммы операции."""
    logger.debug("Поиск топ-%d транзакций.", n)
    # Фильтруем успешные транзакции ('OK') и сортируем по абсолютной величине суммы
    valid_transactions = transactions[transactions["Статус"] == "OK"].copy()
    if not pd.api.types.is_datetime64_any_dtype(valid_transactions["Дата операции"]):
        valid_transactions["Дата операции"] = pd.to_datetime(
            valid_transactions["Дата операции"], format="%d.%m.%Y %H:%M:%S"
        )

    valid_transactions["abs_amount"] = valid_transactions["Сумма операции"].abs()
    top = valid_transactions.nlargest(n, "abs_amount")
    result = []
    for _, row in top.iterrows():
        # Форматируем дату только если это datetime объект
        if pd.api.types.is_datetime64_any_dtype(row["Дата операции"]):
            date_str = row["Дата операции"].strftime("%d.%m.%Y")
        else:
            # Если это строка, пытаемся распарсить
            try:
                date_obj = datetime.strptime(str(row["Дата операции"]), "%d.%m.%Y %H:%M:%S")
                date_str = date_obj.strftime("%d.%m.%Y")
            except ValueError:
                date_str = str(row["Дата операции"])
        result.append(
            {
                "date": date_str,
                "amount": row["Сумма операции"],
                "category": row["Категория"] if pd.notna(row["Категория"]) else "N/A",
                "description": row["Описание"],
            }
        )
    logger.debug("Найдено %d топ-транзакций.", len(result))
    return result


def load_user_settings(filepath: str = "user_settings.json") -> Any:
    """Загружает настройки пользователя (валюты, акции)."""
    logger.info("Загрузка пользовательских настроек из %s", filepath)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Настройки успешно загружены.")
        return data
    except FileNotFoundError:
        logger.warning("Файл %s не найден. Используются настройки по умолчанию.", filepath)
        return {"user_currencies": ["USD", "EUR"], "user_stocks": ["AAPL", "AMZN", "GOOGL", "MSFT", "TSLA"]}
    except json.JSONDecodeError:
        logger.error("Файл %s содержит некорректный JSON. Используются настройки по умолчанию.", filepath)
        return {"user_currencies": ["USD", "EUR"], "user_stocks": ["AAPL", "AMZN", "GOOGL", "MSFT", "TSLA"]}


def get_currency_rates() -> List[Dict[str, Any]]:
    """
    Получает курсы валют от ЦБ РФ в соответствии с настройками пользователя.
    :return: Список словарей с кодом валюты и её курсом.
    """
    logger.info("Получение курсов валют от ЦБ РФ")
    settings = load_user_settings()
    user_currencies = settings.get("user_currencies", [])

    url = "https://www.cbr-xml-daily.ru/daily_json.js"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Проверка на HTTP ошибки
        data = response.json()

        rates = []
        for code in user_currencies:
            if code in data.get("Valute", {}):
                rate_info = data["Valute"][code]
                rate = {"currency": code, "rate": rate_info["Value"]}
                rates.append(rate)
            else:
                logger.warning("Валюта %s не найдена в ответе ЦБ РФ.", code)
        logger.info("Получены курсы для %d валют.", len(rates))
        return rates
    except requests.exceptions.RequestException as e:
        logger.error("Ошибка при запросе к API ЦБ РФ: %s", e)
        return []  # Возвращаем пустой список в случае ошибки
    except KeyError:
        logger.error("Непредвиденная структура ответа от API ЦБ РФ.")
        return []


def get_stock_prices() -> List[Dict[str, Any]]:
    """
    Получает цены на акции из Alpha Vantage, используя кеширование.
    При обнаружении 0.0 в кэше — принудительно запрашивает актуальную цену.
    Возвращает полный список, всегда обновляя недостающие или «битые» позиции.
    """
    logger.info("Получение цен на акции (с принудительным обновлением 0.0)")

    settings = load_user_settings()
    user_stocks: List[str] = settings.get("user_stocks", [])
    cache_file_path = Path("stock_cache.json")

    today = datetime.today().strftime("%d.%m.%Y")

    cached_data: Dict[str, Any] = {}
    existing_prices_by_symbol: Dict[str, float] = {}

    # Загружаем кэш
    if cache_file_path.exists():
        try:
            with open(cache_file_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)

            if isinstance(cached_data.get("date"), str) and cached_data["date"] == today:
                stocks_list = cached_data.get("stocks", [])
                if isinstance(stocks_list, list):
                    for item in stocks_list:
                        symbol = item.get("stock")
                        price = float(item.get("price", 0.0)) if isinstance(item.get("price"), (int, float)) else 0.0
                        existing_prices_by_symbol[symbol] = price
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Файл кэша поврежден или нечитаем: %s. Будет создан новый.", e)

    # Определяем недостающие или неактуальные (0.0 или отсутствуют)
    missing_or_broken = [
        symbol
        for symbol in user_stocks
        if symbol not in existing_prices_by_symbol or existing_prices_by_symbol[symbol] == 0.0
    ]

    updated_symbols: Dict[str, float] = {}

    # Обновляем "битые" и недостающие акции (сразу обновляем словарь)
    if missing_or_broken:
        logger.info("Запрашиваем актуальные данные для проблемных/отсутствующих акций: %s", missing_or_broken)

        for symbol in missing_or_broken:
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={API_KEY}"
            try:
                response = requests.get(url, timeout=500)
                response.raise_for_status()
                data = response.json()

                global_quote = data.get("Global Quote", {})
                price_str = global_quote.get("05. price")

                if price_str:
                    try:
                        price = float(price_str)
                        updated_symbols[symbol] = price
                        logger.debug("Цена для %s получена и сохранена: %f", symbol, price)
                    except ValueError:
                        logger.warning("Некорректная строка цены '%s' для %s, устанавливаем 0.0.", price_str, symbol)
                        updated_symbols[symbol] = 0.0
                else:
                    logger.warning("Цена отсутствует в ответе API для акции %s. Устанавливаем 0.0.", symbol)
                    updated_symbols[symbol] = 0.0

            except requests.exceptions.Timeout:
                logger.error("Таймаут при запросе цены для %s", symbol)
                updated_symbols[symbol] = 0.0
            except requests.exceptions.RequestException as e:
                logger.error("Ошибка сети при запросе цены для %s: %s", symbol, e)
                updated_symbols[symbol] = 0.0
            except (KeyError, ValueError) as e:
                logger.error("Ошибка при обработке данных для %s: %s", symbol, e)
                updated_symbols[symbol] = 0.0

    # Обновляем существующие позиции, сохраняя неизменные
    for symbol in user_stocks:
        if symbol not in existing_prices_by_symbol or symbol in updated_symbols:
            continue
        # Если акция есть в кэше и не помечена как "битая", оставляем старую цену
        if existing_prices_by_symbol[symbol] != 0.0 and symbol not in missing_or_broken:
            updated_symbols[symbol] = existing_prices_by_symbol[symbol]

    # Формируем финальный список в порядке user_stocks
    final_stocks_list = [{"stock": symbol, "price": updated_symbols.get(symbol, 0.0)} for symbol in user_stocks]

    # Сохраняем кэш с актуальными данными
    cache_content: Dict[str, Any] = {"date": today, "stocks": final_stocks_list}

    try:
        with open(cache_file_path, "w", encoding="utf-8") as f:
            json.dump(cache_content, f, ensure_ascii=False, indent=2)
        logger.info("Кэш обновлён и сохранён (%d акций).", len(final_stocks_list))
    except IOError as e:
        logger.error("Ошибка при записи кэша: %s", e)

    return final_stocks_list


def get_date_range(start_date: datetime, period: str) -> tuple[datetime, datetime]:
    """Возвращает начальную и конечную дату для заданного периода относительно start_date."""
    # Формат даты 'DD.MM.YYYY HH:MM:SS'
    if period == "W":
        start = start_date - pd.DateOffset(days=start_date.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "M":
        start = start_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "Y":
        start = start_date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "ALL":
        # Возвращаем очень раннюю дату, чтобы включить всё
        start = datetime.min
    else:  # 'D' или по умолчанию - один день
        start = start_date

    return start, start_date
