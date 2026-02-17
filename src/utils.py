import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import requests
from environs import env

env.read_env()

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
    logger.info(f"Загрузка транзакций из файла: {filepath}")
    try:
        df = pd.read_excel(filepath)
        logger.info(f"Успешно загружено {len(df)} транзакций.")
    except FileNotFoundError:
        logger.error(f"Файл {filepath} не найден.")
        raise
    except Exception as e:
        logger.error(f"Ошибка при чтении файла {filepath}: {e}")
        raise

    # Приведение типов и обработка дат
    # Формат даты 'DD.MM.YYYY HH:MM:SS'
    df["Дата операции"] = pd.to_datetime(df["Дата операции"], format="%d.%m.%Y %H:%M:%S")
    df["Сумма операции"] = pd.to_numeric(df["Сумма операции"], errors="coerce")
    df["Округление на инвесткопилку"] = pd.to_numeric(df["Округление на инвесткопилку"], errors="coerce")
    # Заполняем NaN в 'Округление на инвесткопилку' значением 0, чтобы суммировать корректно
    df["Округление на инвесткопилку"] = df["Округление на инвесткопилку"].fillna(0)
    logger.debug("Типы данных в столбцах 'Дата операции', 'Сумма операции', 'Округление на инвесткопилку' приведены.")
    return df


def filter_transactions_by_date_range(transactions: pd.DataFrame, target_date_str: str) -> pd.DataFrame:
    """Фильтрует транзакции с начала месяца по заданную дату."""
    logger.debug(f"Фильтрация транзакций по дате: {target_date_str}")
    # Формат даты 'DD.MM.YYYY HH:MM:SS'
    target_date = datetime.strptime(target_date_str, "%d.%m.%Y %H:%M:%S")
    start_of_month = target_date.replace(day=1)
    filtered_df = transactions[
        (transactions["Дата операции"] >= start_of_month) & (transactions["Дата операции"] <= target_date)
    ].copy()
    logger.info(f"После фильтрации осталось {len(filtered_df)} транзакций.")
    return filtered_df


def calculate_cards_data(transactions: pd.DataFrame) -> List[Dict[str, Any]]:
    """Рассчитывает данные по картам: расходы и кешбэк."""
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
            total_cashback=("Кэшбэк", "sum"),  # Суммируем кэшбэк
        )
        .reset_index()
    )

    result = []
    for _, row in cards_summary.iterrows():
        # last_digits - это последние 4 цифры номера карты
        card_number = row["Номер карты"]
        last_digits = card_number[-4:] if pd.notna(card_number) else "N/A"  # Обработка случая, когда карта не указана

        result.append(
            {
                "last_digits": last_digits,
                "total_spent": round(row["total_spent"], 2),
                "cashback": round(row["total_cashback"], 2) if pd.notna(row["total_cashback"]) else 0.0,
                # Обработка NaN для кэшбэка
            }
        )
    logger.info(f"Обработаны данные для {len(result)} карт.")
    return result


def get_top_transactions(transactions: pd.DataFrame, n: int = 5) -> List[Dict[str, Any]]:
    """Возвращает топ-N транзакций по абсолютному значению суммы операции."""
    logger.debug(f"Поиск топ-{n} транзакций.")
    # Фильтруем успешные транзакции ('OK') и сортируем по абсолютной величине суммы
    valid_transactions = transactions[transactions["Статус"] == "OK"].copy()
    valid_transactions["abs_amount"] = valid_transactions["Сумма операции"].abs()
    top = valid_transactions.nlargest(n, "abs_amount")
    result = []
    for _, row in top.iterrows():
        result.append(
            {
                "date": row["Дата операции"].strftime("%d.%m.%Y"),
                "amount": row["Сумма операции"],  # Оставляем оригинальный знак
                "category": row["Категория"] if pd.notna(row["Категория"]) else "N/A",
                "description": row["Описание"],
            }
        )
    logger.debug(f"Найдено {len(result)} топ-транзакций.")
    return result


def load_user_settings(filepath: str = "user_settings.json"):
    """Загружает настройки пользователя (валюты, акции)."""
    logger.info(f"Загрузка пользовательских настроек из {filepath}")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Настройки успешно загружены.")
        return data
    except FileNotFoundError:
        logger.warning(f"Файл {filepath} не найден. Используются настройки по умолчанию.")
        return {"user_currencies": ["USD", "EUR"], "user_stocks": ["AAPL", "AMZN", "GOOGL", "MSFT", "TSLA"]}
    except json.JSONDecodeError:
        logger.error(f"Файл {filepath} содержит некорректный JSON. Используются настройки по умолчанию.")
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
                logger.warning(f"Валюта {code} не найдена в ответе ЦБ РФ.")
        logger.info(f"Получены курсы для {len(rates)} валют.")
        return rates
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе к API ЦБ РФ: {e}")
        return []  # Возвращаем пустой список в случае ошибки
    except KeyError:
        logger.error("Непредвиденная структура ответа от API ЦБ РФ.")
        return []


def get_stock_prices() -> List[Dict[str, Any]]:
    """
    Получает цены на акции из Alpha Vantage, используя кеширование.
    :return: Список словарей с названием акции и её ценой.
    """
    logger.info("Получение цен на акции (с кешированием)")
    settings = load_user_settings()
    user_stocks = settings.get("user_stocks", [])
    cache_file_path = Path("stock_cache.json")

    today = datetime.today().strftime("%d.%m.%Y")

    # Проверяем кэш
    cached_data = {}
    if cache_file_path.exists():
        try:
            with open(cache_file_path, "r", encoding="utf-8") as f:
                cached_data = json.load(f)

            # Если дата кэша сегодняшняя, возвращаем закешированные данные
            if cached_data.get("date") == today:
                logger.info("Данные по акциям взяты из кэша.")
                return cached_data.get("stocks", [])
        except json.JSONDecodeError:
            logger.warning("Файл кэша поврежден, будет создан новый.")

    logger.info("Обновляем данные по акциям из API...")

    api_key = env("API_KEY_ALPHAVANTAGE")

    stocks_data = []
    for symbol in user_stocks:
        logger.debug(f"Запрос цены для акции {symbol}")
        url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={api_key}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            # Пример структуры ответа:
            # {"Global Quote": {"01. symbol": "TSLA", "05. price": "1007.0800", ...}}
            global_quote = data.get("Global Quote", {})
            price_str = global_quote.get("05. price")
            if price_str:
                price = float(price_str)
                stocks_data.append({"stock": symbol, "price": price})
            else:
                logger.warning(f"Цена для акции {symbol} не найдена в ответе API.")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе цены для {symbol}: {e}")
        except (KeyError, ValueError) as e:
            logger.error(f"Ошибка при обработке данных для {symbol}: {e}")

    # Сохраняем в кэш
    cache_content = {"date": today, "stocks": stocks_data}
    try:
        with open(cache_file_path, "w", encoding="utf-8") as f:
            json.dump(cache_content, f, ensure_ascii=False, indent=2)
        logger.info("Данные по акциям закешированы.")
    except IOError as e:
        logger.error(f"Ошибка при записи кэша: {e}")

    return stocks_data


def get_date_range(start_date: datetime, period: str):
    """Возвращает начальную и конечную дату для заданного периода относительно start_date."""
    # Формат даты 'DD.MM.YYYY HH:MM:SS'
    if period == "W":
        start = start_date - pd.DateOffset(days=start_date.weekday())
    elif period == "M":
        start = start_date.replace(day=1)
    elif period == "Y":
        start = start_date.replace(month=1, day=1)
    elif period == "ALL":
        # Возвращаем очень раннюю дату, чтобы включить всё
        start = datetime.min
    else:  # 'D' или по умолчанию - один день
        start = start_date

    return start, start_date
