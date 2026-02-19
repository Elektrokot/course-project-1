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
    # Используем формат даты 'DD.MM.YYYY HH:MM:SS'
    # В DataFrame 'transactions' столбец 'Дата операции' уже типа datetime
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

    # Преобразуем дату в строку в нужном формате, если необходимо (pandas обычно делает это автоматически)
    # for record in result_list:
    #     if isinstance(record['Дата операции'], pd.Timestamp):
    #         record['Дата операции'] = record['Дата операции'].strftime("%d.%m.%Y %H:%M:%S")

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

    # Фильтрация по дате и типу операции (предполагаем, что отрицательная сумма - трата)
    # Используем формат даты 'DD.MM.YYYY HH:MM:SS'
    # Предполагаем, что в DataFrame 'transactions' столбец 'Дата операции' уже типа datetime
    # Также учитываем статус 'OK'
    expense_transactions = transactions[
        (transactions["Дата операции"] >= three_months_ago)
        & (transactions["Дата операции"] <= target_date)
        & (transactions["Сумма операции"] < 0)  # Предполагаем, что трата - отрицательная сумма
        & (transactions["Статус"] == "OK")  # Только успешные транзакции
    ].copy()  # copy(), чтобы избежать SettingWithCopyWarning при дальнейших операциях

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
    Возвращает траты по рабочим дням за последние три месяца от переданной даты.

    :param transactions: DataFrame с транзакциями.
    :param date: Опциональная дата в формате 'DD.MM.YYYY'. Если не указана, используется текущая дата.
    :return: JSON-строка с агрегированными тратами по рабочим дням.
    """
    logger.info(f"Формирование отчета 'Траты по рабочим дням' до даты {date}.")

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
    # Используем формат даты 'DD.MM.YYYY HH:MM:SS'
    # Предполагаем, что в DataFrame 'transactions' столбец 'Дата операции' уже типа datetime
    # Рабочие дни: 0-4 (Пн-Пт). Выходные: 5-6 (Сб-Вс).
    expense_transactions = transactions[
        (transactions["Дата операции"] >= three_months_ago)
        & (transactions["Дата операции"] <= target_date)
        & (transactions["Сумма операции"] < 0)  # трата - отрицательная сумма
        & (transactions["Статус"] == "OK")  # Только успешные транзакции
        & (transactions["Дата операции"].dt.dayofweek < 5)  # Только рабочие дни
    ].copy()  # copy(), чтобы избежать SettingWithCopyWarning при дальнейших операциях

    # Агрегируем сумму по датам (по модулю, чтобы получить положительную сумму расходов)
    daily_spending = (
        expense_transactions.groupby(expense_transactions["Дата операции"].dt.date)["Сумма операции"].sum().abs()
    )

    # Создаем словарь с датами и суммами, округленными до 2 знаков
    result_dict = {str(date): round(amount, 2) for date, amount in daily_spending.items()}

    logger.info(f"Отчет 'Траты по рабочим дням' сформирован. Найдено {len(result_dict)} рабочих дней с тратами.")

    # Возвращаем JSON-строку
    return json.dumps(result_dict, ensure_ascii=False, indent=2)
