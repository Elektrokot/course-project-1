import json
from datetime import datetime

import pandas as pd

from config import PATH_TO_OPERATIONS
from src.utils import (
    calculate_cards_data,
    filter_transactions_by_date_range,
    get_currency_rates,
    get_date_range,
    get_greeting,
    get_stock_prices,
    get_top_transactions,
    load_transactions_from_xlsx,
)


def main(date_str: str) -> str:
    """
    Главная функция для страницы "Главная".
    Принимает строку даты и возвращает JSON-ответ.
    """
    # 1. Приветствие
    current_hour = datetime.now().hour
    greeting = get_greeting(current_hour)

    # 2. Загрузка транзакций
    df = load_transactions_from_xlsx(str(PATH_TO_OPERATIONS))

    # 3. Фильтрация транзакций по дате (с начала месяца по заданную дату)
    filtered_df_for_main = filter_transactions_by_date_range(df, date_str)

    # 4. Рассчет данных по картам
    cards_data = calculate_cards_data(filtered_df_for_main)

    # 5. Получение топ-5 транзакций
    top_transactions = get_top_transactions(filtered_df_for_main, n=5)

    # investment_bank_result = investment_bank(date_str.split('-')[1], df.to_dict('records'))  # передаёт list[dict]
    #
    # cashback_result = analyze_cashback_categories(df.to_dict('records'), year, month)  # передаёт list[dict]

    # 6. Получение курсов валют
    currency_rates = get_currency_rates()

    # 7. Получение цен на акции
    stock_prices = get_stock_prices()

    # 8. Формирование JSON-ответа
    response = {
        "greeting": greeting,
        "cards": cards_data,
        "top_transactions": top_transactions,
        "currency_rates": currency_rates,
        "stock_prices": stock_prices,
    }

    return json.dumps(response, ensure_ascii=False, indent=2)


def events_page_data(df: pd.DataFrame, date_str: str, period: str = "M") -> str:
    """
    Функция для страницы "События".
    Принимает DataFrame, строку даты и период, возвращает JSON-ответ.
    """
    # 1. Фильтрация по дате и периоду
    target_date = datetime.strptime(date_str, "%d.%m.%Y %H:%M:%S")
    start_dt, end_dt = get_date_range(target_date, period)
    # Формат даты 'DD.MM.YYYY HH:MM:SS'
    # Колонка 'Дата операции' в df уже типа datetime благодаря load_transactions_from_xlsx
    filtered_df = df[(df["Дата операции"] >= start_dt) & (df["Дата операции"] <= end_dt)]

    # 2. Подготовка данных о расходах и поступлениях
    # Фильтруем по статусу 'OK' и типу операции (трата/доход)
    valid_transactions = filtered_df[filtered_df["Статус"] == "OK"]

    expenses_df = valid_transactions[valid_transactions["Сумма операции"] < 0].copy()
    income_df = valid_transactions[valid_transactions["Сумма операции"] > 0].copy()

    # --- Расходы ---
    # Суммируем отрицательные значения и умножаем на -1, чтобы получить положительную сумму
    total_expenses = int(expenses_df["Сумма операции"].sum() * -1)

    # Основные расходы по категориям
    # Используем 'Категория', которая может быть NaN. groupby автоматически исключает NaN.
    main_expense_summary = (
        expenses_df.groupby("Категория")["Сумма операции"].sum().abs().astype(int).sort_values(ascending=False)
    )
    top_7_categories = main_expense_summary.head(7)
    rest_sum = main_expense_summary.iloc[7:].sum()
    main_expense_list = [{"category": cat, "amount": amt} for cat, amt in top_7_categories.items()]
    if rest_sum > 0:
        main_expense_list.append({"category": "Остальное", "amount": int(rest_sum)})

    # Расходы на Наличные и Переводы
    transfers_and_cash_df = expenses_df[expenses_df["Категория"].isin(["Наличные", "Переводы"])]
    transfers_and_cash_summary = (
        transfers_and_cash_df.groupby("Категория")["Сумма операции"]
        .sum()
        .abs()
        .astype(int)
        .sort_values(ascending=False)
    )
    transfers_and_cash_list = [{"category": cat, "amount": amt} for cat, amt in transfers_and_cash_summary.items()]

    # --- Поступления ---
    total_income = int(income_df["Сумма операции"].sum())

    # Основные поступления по категории (если категория есть)
    # Используем 'Категория', которая может быть NaN. groupby автоматически исключает NaN.
    main_income_summary = (
        income_df.groupby("Категория")["Сумма операции"].sum().astype(int).sort_values(ascending=False)
    )
    main_income_list = [{"category": cat, "amount": amt} for cat, amt in main_income_summary.items()]

    # 3. Получение курсов и акций
    currency_rates = get_currency_rates()
    stock_prices = get_stock_prices()

    # 4. Формирование JSON-ответа
    response = {
        "expenses": {
            "total_amount": total_expenses,
            "main": main_expense_list,
            "transfers_and_cash": transfers_and_cash_list,
        },
        "income": {"total_amount": total_income, "main": main_income_list},
        "currency_rates": currency_rates,
        "stock_prices": stock_prices,
    }

    return json.dumps(response, ensure_ascii=False, indent=2)
