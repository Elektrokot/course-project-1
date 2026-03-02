import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List

# Настройка логгера
logger = logging.getLogger(__name__)


def simple_search(query: str, transactions: List[Dict[str, Any]]) -> str:
    """
    Ищет транзакции, содержащие строку запроса в описании или категории.

    :param query: Строка для поиска.
    :param transactions: Список словарей с транзакциями.
    :return: JSON-строка с найденными транзакциями.
    """
    logger.info("Поиск транзакций по запросу '%s', всего транзакций: %d", query, len(transactions))
    results = []
    query_lower = query.lower()
    for i, transaction in enumerate(transactions):
        if transaction is None or not isinstance(transaction, dict):
            logger.debug("Транзакция %d: пропущена, так как не является словарем.", i)
            continue
        description = transaction.get("Описание", "").lower()
        category = transaction.get("Категория", "").lower()
        if query_lower in description or query_lower in category:
            results.append(transaction)
            logger.debug("Транзакция %d: совпадение по запросу '%s'.", i, query)
    logger.info(f"Найдено %d транзакций по запросу '%s'.", len(results), query)
    return json.dumps(results, ensure_ascii=False, indent=2)


def investment_bank(month: str, transactions: List[Dict[str, Any]], limit: int) -> str:
    logger.info("Расчет 'Инвесткопилки' для месяца %s с шагом округления %d,"
                " всего транзакций: %d", month, limit, len(transactions))

    total_savings = 0.0
    try:
        target_month, target_year = map(int, month.split("."))
    except ValueError:
        logger.error("Некорректный формат месяца '%s'. Ожидается 'MM.YYYY'.", month)
        return "0.0"

    for i, transaction in enumerate(transactions):
        trans_date_obj = transaction.get("Дата операции")
        amount = transaction.get("Сумма операции", 0)

        # Проверка на корректность даты
        if trans_date_obj is None:
            logger.debug("Транзакция %d: отсутствует дата. Пропуск.", i)
            continue

        if isinstance(trans_date_obj, str):
            try:
                # Пробуем разные возможные форматы
                for fmt in ["%Y-%m-%dT%H:%M:%S", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y"]:
                    try:
                        trans_date = datetime.strptime(trans_date_obj, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    raise ValueError("Ни один формат не подошел")
            except ValueError as e:
                logger.debug("Транзакция %d: невозможно распознать дату '%s'."
                             " Ошибка: %s. Пропуск.", i, trans_date_obj, e)
                continue
        elif isinstance(trans_date_obj, datetime):
            trans_date = trans_date_obj
        else:
            logger.debug("Транзакция %d: некорректный тип даты '%s'. Пропуск.", i, type(trans_date_obj))
            continue

        # Проверка: транзакция в нужном месяце и является расходом (отрицательная сумма)
        if trans_date.month == target_month and trans_date.year == target_year and amount < 0:
            # Округляем сумму до ближайшего большего кратного limit
            abs_amount = abs(amount)
            rounded_up = ((abs_amount + limit - 1) // limit) * limit
            savings = round(rounded_up - abs_amount, 2)

            total_savings += savings
            logger.debug("Транзакция %d: сумма %s, округлено до %d,"
                         " в инвесткопилку добавлено: %s.", i, amount, rounded_up, savings)

    result = round(total_savings, 2)
    logger.info("Расчет 'Инвесткопилки' завершен. Итого сбережено: %f.", result)

    return str(result)


def analyze_cashback_categories(data: List[Dict[str, Any]], year: int, month: int) -> str:
    """
    Анализирует, сколько можно было заработать кешбэка в каждой категории
    за указанный месяц и год, при условии, что она была выбрана как категория повышенного кешбэка.

    :param data: Список транзакций.
    :param year: Год для анализа.
    :param month: Месяц для анализа.
    :return: JSON-строка с результатами анализа.
    """
    logger.info("Анализ выгодных категорий кешбэка для %02d.%d, всего транзакций: %d", month, year, len(data))

    cashback_per_category: dict[str, float] = {}

    for i, transaction in enumerate(data):
        trans_date_obj = transaction.get("Дата операции")
        category = transaction.get("Категория")
        amount = abs(transaction.get("Сумма операции", 0))  # Берем модуль, так как трата может быть отрицательной
        status = transaction.get("Статус")

        # Обработка разных форматов даты
        if trans_date_obj is None:
            logger.debug("Транзакция %d: отсутствует дата. Пропуск.", i)
            continue

        if isinstance(trans_date_obj, str):
            try:
                trans_date = datetime.strptime(trans_date_obj, "%d.%m.%Y %H:%M:%S")
            except (ValueError, TypeError) as e:
                logger.debug("Транзакция %d: невозможно распознать дату '%s'. Ошибка: %s. Пропуск.", i, trans_date_obj, e)
                continue
        elif isinstance(trans_date_obj, datetime):
            trans_date = trans_date_obj
        else:
            logger.debug("Транзакция %d: некорректный тип даты '%s'. Пропуск.", i, type(trans_date_obj))
            continue

        # Проверяем, подходит ли транзакция
        if trans_date.year == year and trans_date.month == month and status == "OK" and category:
            potential_high_cashback = amount * 0.10
            if category in cashback_per_category:
                cashback_per_category[category] += potential_high_cashback
            else:
                cashback_per_category[category] = potential_high_cashback
            logger.debug("Транзакция %d: добавлено %.2f к кешбэку категории '%s'.", i, potential_high_cashback, category)

        # Сортируем категории по потенциальному кешбэку (убывание) и формируем словарь
    sorted_categories = dict(sorted(cashback_per_category.items(), key=lambda item: item[1], reverse=True))

    # Округляем значения
    final_result = {cat: round(val, 2) for cat, val in sorted_categories.items()}

    logger.info("Анализ завершен. Найдено %d категорий.", len(final_result))
    return json.dumps(final_result, ensure_ascii=False, indent=2)


def search_transfers_to_individuals(transactions: List[Dict[str, Any]]) -> str:
    """
    Ищет транзакции, являющиеся переводами физическим лицам.

    Критерии: Категория 'Переводы' и в описании имя и первая буква фамилии с точкой (например, 'Иван И.').

    :param transactions: Список словарей с транзакциями.
    :return: JSON-строка с найденными транзакциями.
    """
    logger.info("Поиск переводов физическим лицам, всего транзакций: %d", len(transactions))

    # Регулярное выражение для поиска паттерна "Имя Б.":
    # - Имя: заглавная кириллическая буква и далее строчные
    # - Затем один пробел
    # - Фамилия: одна заглавная буква и точка
    pattern = re.compile(r"[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.")

    results = []
    for i, transaction in enumerate(transactions):
        category = transaction.get("Категория", "")
        description = transaction.get("Описание", "")

        # Проверяем категорию и наличие паттерна в описании
        if isinstance(category, str) and category.strip().lower() == "переводы" and pattern.search(description):
            results.append(transaction)
            logger.debug("Транзакция %d: совпадение по критериям перевода физ.лицу - '%s'.", i, description)

    logger.info("Найдено %d переводов физическим лицам.", len(results))
    return json.dumps(results, ensure_ascii=False, indent=2)


def search_transactions_by_phone_numbers(transactions: List[Dict[str, Any]]) -> str:
    """
    Ищет транзакции, содержащие мобильные номера в описании.

    Ищет номера в формате +7 XXX XXX-XX-XX или +7 XXX XXX XX XX.

    :param transactions: Список словарей с транзакциями.
    :return: JSON-строка с найденными транзакциями.
    """
    logger.info("Поиск транзакций по телефонным номерам, всего транзакций: %d", len(transactions))

    # Регулярное выражение для поиска паттерна "+7 XXX XXX-XX-XX" или "+7 XXX XXX XX XX"
    # \+7\s+\d{3}\s+\d{3}[\s-]\d{2}[\s-]\d{2}
    # \+7 - литерал "+7"
    # \s+ - один или несколько пробелов
    # \d{3} - три цифры
    # \s+ - один или несколько пробелов
    # \d{3} - три цифры
    # [\s-] - один пробел или дефис
    # \d{2} - две цифры
    # [\s-] - один пробел или дефис
    # \d{2} - две цифры
    pattern = re.compile(r"\+7\s+\d{3}\s+\d{3}[\s\-]\d{2}[\s\-]\d{2}")

    results = []
    for i, transaction in enumerate(transactions):
        description = transaction.get("Описание", "")

        # Проверяем наличие паттерна в описании
        if pattern.search(description):
            results.append(transaction)
            logger.debug("Транзакция %d: совпадение по телефонному номеру в описании - '%s'.", i, description)

    logger.info("Найдено %d транзакций по телефонным номерам.", len(results))
    return json.dumps(results, ensure_ascii=False, indent=2)
