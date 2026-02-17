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
    logger.info(f"Поиск транзакций по запросу '{query}', всего транзакций: {len(transactions)}")
    results = []
    query_lower = query.lower()
    for i, transaction in enumerate(transactions):
        description = transaction.get("Описание", "").lower()
        category = transaction.get("Категория", "").lower()
        if query_lower in description or query_lower in category:
            results.append(transaction)
            logger.debug(f"Транзакция {i}: совпадение по запросу '{query}'.")
    logger.info(f"Найдено {len(results)} транзакций по запросу '{query}'.")
    return json.dumps(results, ensure_ascii=False, indent=2)


def investment_bank(
    month: str, transactions: List[Dict[str, Any]], limit: int = None
) -> str:  # limit может быть не нужен, если используем готовый столбец
    """
    Рассчитывает сумму, которую можно было бы отложить в 'Инвесткопилку'
    через округление трат в заданном месяце, используя готовый столбец 'Округление на инвесткопилку'.

    :param month: Месяц для расчета в формате 'MM.YYYY'.
    :param transactions: Список транзакций (словарей).
    :param limit: (Опционально) Предел округления, если нужно рассчитать заново
     (не используется, если округление уже в столбце).
    :return: JSON-строка с результатом (ключ 'total_savings').
    """
    logger.info(
        f"Расчет 'Инвесткопилки' для месяца {month} из столбца 'Округление на инвесткопилку',"
        f" всего транзакций: {len(transactions)}"
    )

    total_savings = 0.0
    target_month = datetime.strptime(month, "%m.%Y")

    for i, transaction in enumerate(transactions):
        trans_date_str = transaction.get("Дата операции")
        status = transaction.get("Статус")
        amount = transaction.get("Сумма операции", 0)
        rounding_amount = transaction.get("Округление на инвесткопилку", 0)

        try:
            trans_date = datetime.strptime(trans_date_str, "%d.%m.%Y %H:%M:%S")
        except (ValueError, TypeError) as e:
            logger.debug(f"Транзакция {i}: невозможно распознать дату '{trans_date_str}'. Ошибка: {e}. Пропуск.")
            continue

        # Проверяем, подходит ли транзакция: дата, статус и тип операции (трата)
        # Статус 'OK' и отрицательная сумма операции означают успешную трату
        if (
            trans_date.month == target_month.month
            and trans_date.year == target_month.year
            and status == "OK"
            and amount < 0
        ):

            # Суммируем значение из столбца 'Округление на инвесткопилку'
            total_savings += rounding_amount
            logger.debug(
                f"Транзакция {i}: статус OK, трата ({amount}), округление {rounding_amount},"
                f" сбережено {rounding_amount}."
            )

    result = {"total_savings": round(total_savings, 2)}
    logger.info(f"Расчет 'Инвесткопилки' завершен. Итого сбережено: {result['total_savings']}.")

    return json.dumps(result, ensure_ascii=False, indent=2)


def analyze_cashback_categories(data: List[Dict[str, Any]], year: int, month: int) -> str:
    """
    Анализирует, сколько можно было заработать кешбэка в каждой категории
    за указанный месяц и год, при условии, что она была выбрана как категория повышенного кешбэка.

    :param data: Список транзакций.
    :param year: Год для анализа.
    :param month: Месяц для анализа.
    :return: JSON-строка с результатами анализа.
    """
    logger.info(f"Анализ выгодных категорий кешбэка для {month:02d}.{year}, всего транзакций: {len(data)}")

    cashback_per_category = {}

    for i, transaction in enumerate(data):
        trans_date_str = transaction.get("Дата операции")
        category = transaction.get("Категория")
        amount = abs(transaction.get("Сумма операции", 0))  # Берем модуль, так как трата может быть отрицательной
        status = transaction.get("Статус")

        # Проверяем формат даты и конвертируем
        try:
            # Формат из example-operations.csv: 'DD.MM.YYYY HH:MM:SS'
            trans_date = datetime.strptime(trans_date_str, "%d.%m.%Y %H:%M:%S")
        except (ValueError, TypeError) as e:
            logger.debug(f"Транзакция {i}: невозможно распознать дату '{trans_date_str}'. Ошибка: {e}. Пропуск.")
            continue

        # Проверяем, подходит ли транзакция: дата, статус (только OK), и категория не пуста
        if (
            trans_date.year == year and trans_date.month == month and status == "OK" and category
        ):  # Проверка на пустую строку/None

            # Условно предположим, что повышенный кешбэк - 10%, стандартный - 1%.
            # Для расчета "выгодности" считаем потенциальный кешбэк по 10% от суммы в категории.
            potential_high_cashback = amount * 0.10
            if category in cashback_per_category:
                cashback_per_category[category] += potential_high_cashback
            else:
                cashback_per_category[category] = potential_high_cashback
            logger.debug(f"Транзакция {i}: добавлено {potential_high_cashback:.2f} к кешбэку категории '{category}'.")

        # Сортируем категории по потенциальному кешбэку (убывание) и формируем словарь
    sorted_categories = dict(sorted(cashback_per_category.items(), key=lambda item: item[1], reverse=True))

    # Округляем значения
    final_result = {cat: round(val, 2) for cat, val in sorted_categories.items()}

    logger.info(f"Анализ завершен. Найдено {len(final_result)} категорий.")
    return json.dumps(final_result, ensure_ascii=False, indent=2)


def search_transfers_to_individuals(transactions: List[Dict[str, Any]]) -> str:
    """
    Ищет транзакции, являющиеся переводами физическим лицам.

    Критерии: Категория 'Переводы' и в описании имя и первая буква фамилии с точкой (например, 'Иван И.').

    :param transactions: Список словарей с транзакциями.
    :return: JSON-строка с найденными транзакциями.
    """
    logger.info(f"Поиск переводов физическим лицам, всего транзакций: {len(transactions)}")

    # Регулярное выражение для поиска паттерна "Имя Б."
    # [А-ЯЁ][а-яё]+ - имя с заглавной буквы
    # \s+ - один или несколько пробелов
    # [А-ЯЁ]\. - одна заглавная буква и точка
    pattern = re.compile(r"[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.")

    results = []
    for i, transaction in enumerate(transactions):
        category = transaction.get("Категория", "")
        description = transaction.get("Описание", "")

        # Проверяем категорию и наличие паттерна в описании
        if category.strip().lower() == "переводы" and pattern.search(description):
            results.append(transaction)
            logger.debug(f"Транзакция {i}: совпадение по критериям перевода физ.лицу - '{description}'.")

    logger.info(f"Найдено {len(results)} переводов физическим лицам.")
    return json.dumps(results, ensure_ascii=False, indent=2)


def search_transactions_by_phone_numbers(transactions: List[Dict[str, Any]]) -> str:
    """
    Ищет транзакции, содержащие мобильные номера в описании.

    Ищет номера в формате +7 XXX XXX-XX-XX или +7 XXX XXX XX XX.

    :param transactions: Список словарей с транзакциями.
    :return: JSON-строка с найденными транзакциями.
    """
    logger.info(f"Поиск транзакций по телефонным номерам, всего транзакций: {len(transactions)}")

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
            logger.debug(f"Транзакция {i}: совпадение по телефонному номеру в описании - '{description}'.")

    logger.info(f"Найдено {len(results)} транзакций по телефонным номерам.")
    return json.dumps(results, ensure_ascii=False, indent=2)
