import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

# Настройка логгера
logger = logging.getLogger(__name__)


def report_to_file(filename: Optional[str] = None):
    """
    Декоратор для сохранения результата функции отчета в файл.
    Если filename не указан, генерируется имя на основе названия функции и даты.
    """

    def decorator(func):
        from typing import Any

        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result_json = func(*args, **kwargs)
            import os
            from datetime import datetime

            if not filename:
                func_name = func.__name__
                timestamp = datetime.now().strftime("%d%m%Y%H%M%S")
                safe_func_name = "".join(c for c in func_name if c.isalnum() or c in ("-", "_")).rstrip()
                file_path = f"reports/{safe_func_name}_{timestamp}.json"
            else:
                file_path = filename

            # Создаем директорию, если её нет
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(result_json)
            logger.info(f"Отчет сохранен в файл: {file_path}")
            return result_json

        return wrapper

    return decorator


@report_to_file()
def spending_by_category(transactions: pd.DataFrame, category: str, date: Optional[str] = None) -> str:
    """
    Возвращает траты по заданной категории за последние три месяца от переданной даты.

    :param transactions: DataFrame с транзакциями.
    :param category: Название категории для фильтрации.
    :param date: Опциональная дата в формате 'DD.MM.YYYY'. Если не указана, используется текущая дата.
    :return: JSON-строка с отфильтрованными транзакциями.
    """
    logger.info(f"Формирование отчета 'Траты по категории' для '{category}' до даты {date}.")

    if date is None:
        target_date = datetime.today()
    else:
        try:
            target_date = datetime.strptime(date, "%d.%m.%Y")
        except ValueError:
            logger.error(f"Неверный формат даты: {date}. Используется текущая дата.")
            target_date = datetime.today()

    three_months_ago = target_date - timedelta(days=90)

    # Фильтрация по дате, категории и типу операции
    filtered_df = transactions[
        (transactions["Дата операции"] >= three_months_ago)
        & (transactions["Дата операции"] <= target_date)
        & (transactions["Категория"].str.lower() == category.lower())
        & (transactions["Сумма операции"] < 0)  # трата - отрицательная сумма
    ]

    # Выбираем нужные столбцы и сбрасываем индекс
    result_df = filtered_df[["Дата операции", "Сумма операции", "Категория", "Описание"]].reset_index(drop=True)

    # Преобразуем DataFrame в список словарей для JSON
    result_list = result_df.to_dict(orient="records")

    logger.info(f"Найдено {len(result_list)} транзакций по категории '{category}'.")

    # Возвращаем JSON-строку
    return json.dumps(result_list, ensure_ascii=False, indent=2, default=str)  # default=str для обработки pd.Timestamp


@report_to_file()
def spending_by_weekday(transactions: pd.DataFrame, date: Optional[str] = None) -> str:
    """
    Возвращает траты по дням недели за последние три месяца от переданной даты.

    :param transactions: DataFrame с транзакциями.
    :param date: Опциональная дата в формате 'DD.MM.YYYY'. Если не указана, используется текущая дата.
    :return: JSON-строка с агрегированными тратами по дням недели.
    """
    logger.info(f"Формирование отчета 'Траты по дням недели' до даты {date}.")

    if date is None:
        target_date = datetime.today()
    else:
        try:
            target_date = datetime.strptime(date, "%d.%m.%Y")
        except ValueError:
            logger.error(f"Неверный формат даты: {date}. Используется текущая дата.")
            target_date = datetime.today()

    three_months_ago = target_date - timedelta(days=90)

    # Фильтрация по дате и типу операции, отрицательная сумма - трата
    # Используем формат даты 'DD.MM.YYYY HH:MM:SS'
    # Также учитываем статус 'OK'
    expense_transactions = transactions[
        (transactions["Дата операции"] >= three_months_ago)
        & (transactions["Дата операции"] <= target_date)
        & (transactions["Сумма операции"] < 0)
        & (transactions["Статус"] == "OK")
    ].copy()

    # Извлекаем день недели (понедельник = 0, воскресенье = 6)
    expense_transactions.loc[:, "DayOfWeek"] = expense_transactions["Дата операции"].dt.dayofweek

    # Агрегируем сумму по дням недели (по модулю, чтобы получить положительную сумму расходов)
    weekday_spending = expense_transactions.groupby("DayOfWeek")["Сумма операции"].sum().abs()

    # Создаем словарь с названиями дней недели и суммами, округленными до 2 знаков
    # 0 - Понедельник, ..., 6 - Воскресенье
    weekday_names = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    result_dict = {}
    for i in range(7):
        day_name = weekday_names[i]
        amount = round(weekday_spending.get(i, 0.0), 2)  # Если день не встречался, возвращаем 0.0
        result_dict[day_name] = amount

    logger.info("Отчет 'Траты по дням недели' сформирован.")

    # Возвращаем JSON-строку
    return json.dumps(result_dict, ensure_ascii=False, indent=2)


@report_to_file()
def spending_by_workday(transactions: pd.DataFrame, date: Optional[str] = None) -> str:
    """
    Возвращает средние траты в рабочий и в выходной день за последние три месяца от переданной даты.

    :param transactions: DataFrame с транзакциями.
    :param date: Опциональная дата в формате 'DD.MM.YYYY'. Если не указана, используется текущая дата.
    :return: JSON-строка со средними тратами по рабочим и выходным дням.
    """
    logger.info(f"Формирование отчета 'Траты по рабочим/выходным дням' до даты {date}.")

    if date is None:
        target_date = datetime.today()
    else:
        try:
            target_date = datetime.strptime(date, "%d.%m.%Y")
        except ValueError:
            logger.error(f"Неверный формат даты: {date}. Используется текущая дата.")
            target_date = datetime.today()

    three_months_ago = target_date - timedelta(days=90)

    # Фильтрация по дате, типу операции (трата) и статусу
    expense_transactions = transactions[
        (transactions["Дата операции"] >= three_months_ago)
        & (transactions["Дата операции"] <= target_date)
        & (transactions["Сумма операции"] < 0)  # трата - отрицательная сумма
        & (transactions["Статус"] == "OK")  # Только успешные транзакции
    ].copy()

    # Добавляем столбцы: день недели и признак выходного/рабочего дня
    expense_transactions.loc[:, "Weekday"] = expense_transactions["Дата операции"].dt.dayofweek
    expense_transactions.loc[:, "IsWorkday"] = expense_transactions["Weekday"] < 5

    # Агрегируем траты по типу дня (рабочий/выходной)
    daily_spending_by_type = expense_transactions.groupby("IsWorkday")["Сумма операции"].sum().abs()

    # Подсчитываем количество дней каждого типа
    days_count = expense_transactions.groupby("IsWorkday")["Дата операции"].nunique()  # уникальные дни с тратами

    # Формируем результат: средняя трата за один день (рабочий или выходной)
    result_dict = {}

    if True in daily_spending_by_type.index:
        workday_avg = round(daily_spending_by_type[True] / days_count[True], 2) if days_count[True] > 0 else 0.0
        result_dict["Рабочий день"] = workday_avg

    if False in daily_spending_by_type.index:
        weekend_avg = round(daily_spending_by_type[False] / days_count[False], 2) if days_count[False] > 0 else 0.0
        result_dict["Выходной день"] = weekend_avg

    logger.info("Отчет 'Траты по рабочим и выходным дням' сформирован.")
    # Возвращаем JSON-строку
    return json.dumps(result_dict, ensure_ascii=False, indent=2)
