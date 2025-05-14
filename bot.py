import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from datetime import datetime
import psycopg2
from decouple import config
import os
import asyncio
import pandas as pd
from io import BytesIO
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database connection configuration (Neon PostgreSQL)
def connect():
    return psycopg2.connect(config("DATABASE_URL"))

# Function to save an expense
def save_expense(user, amount, category, payment_method, date):
    try:
        with connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                INSERT INTO expenses (user, amount, category, payment_method, date)
                VALUES (%s, %s, %s, %s, %s)
                ''', (user, amount, category, payment_method, date))
                conn.commit()
        logger.info(f"Expense saved: ${amount} in {category} by {user}")
    except Exception as e:
        logger.error(f"Error saving expense: {e}")
        raise

# Function to save an income
def save_income(user, amount, description, date):
    try:
        with connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                INSERT INTO incomes (user, amount, description, date)
                VALUES (%s, %s, %s, %s)
                ''', (user, amount, description, date))
                conn.commit()
        logger.info(f"Income saved: ${amount} - {description} by {user}")
    except Exception as e:
        logger.error(f"Error saving income: {e}")
        raise

# Function to get monthly expenses (for summary and spreadsheet)
def get_monthly_expenses(user, month, year):
    try:
        with connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                SELECT category, SUM(amount) as total
                FROM expenses
                WHERE user = %s AND EXTRACT(MONTH FROM date) = %s AND EXTRACT(YEAR FROM date) = %s
                GROUP BY category
                ''', (user, month, year))
                return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error retrieving expenses: {e}")
        raise

# Function to get total monthly expenses
def get_total_monthly_expenses(user, month, year):
    try:
        with connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                SELECT SUM(amount) as total
                FROM expenses
                WHERE user = %s AND EXTRACT(MONTH FROM date) = %s AND EXTRACT(YEAR FROM date) = %s
                ''', (user, month, year))
                result = cursor.fetchone()
                return result[0] if result[0] is not None else 0
    except Exception as e:
        logger.error(f"Error retrieving total expenses: {e}")
        raise

# Function to get monthly incomes
def get_monthly_incomes(user, month, year):
    try:
        with connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                SELECT SUM(amount) as total
                FROM incomes
                WHERE user = %s AND EXTRACT(MONTH FROM date) = %s AND EXTRACT(YEAR FROM date) = %s
                ''', (user, month, year))
                result = cursor.fetchone()
                return result[0] if result[0] is not None else 0
    except Exception as e:
        logger.error(f"Error retrieving incomes: {e}")
        raise

# Function to list expenses for a specific month
def list_monthly_expenses(user, month, year):
    try:
        with connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                SELECT id, amount, category, payment_method, date
                FROM expenses
                WHERE user = %s AND EXTRACT(MONTH FROM date) = %s AND EXTRACT(YEAR FROM date) = %s
                ORDER BY date DESC
                ''', (user, month, year))
                return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error listing monthly expenses: {e}")
        raise

# Function to list incomes for a specific month
def list_monthly_incomes(user, month, year):
    try:
        with connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                SELECT id, amount, description, date
                FROM incomes
                WHERE user = %s AND EXTRACT(MONTH FROM date) = %s AND EXTRACT(YEAR FROM date) = %s
                ORDER BY date DESC
                ''', (user, month, year))
                return cursor.fetchall()
    except Exception as e:
        logger.error(f"Error listing monthly incomes: {e}")
        raise

# Function to edit an expense
def edit_expense(user, expense_id, amount=None, category=None, payment_method=None):
    try:
        with connect() as conn:
            with conn.cursor() as cursor:
                query = "UPDATE expenses SET "
                params = []
                if amount is not None:
                    query += "amount = %s, "
                    params.append(amount)
                if category is not None:
                    query += "category = %s, "
                    params.append(category)
                if payment_method is not None:
                    query += "payment_method = %s, "
                    params.append(payment_method)
                query = query.rstrip(", ") + " WHERE user = %s AND id = %s"
                params.extend([user, expense_id])
                cursor.execute(query, params)
                conn.commit()
        logger.info(f"Expense ID {expense_id} edited by {user}")
    except Exception as e:
        logger.error(f"Error editing expense: {e}")
        raise

# Function to edit an income
def edit_income(user, income_id, amount=None, description=None):
    try:
        with connect() as conn:
            with conn.cursor() as cursor:
                query = "UPDATE incomes SET "
                params = []
                if amount is not None:
                    query += "amount = %s, "
                    params.append(amount)
                if description is not None:
                    query += "description = %s, "
                    params.append(description)
                query = query.rstrip(", ") + " WHERE user = %s AND id = %s"
                params.extend([user, income_id])
                cursor.execute(query, params)
                conn.commit()
        logger.info(f"Income ID {income_id} edited by {user}")
    except Exception as e:
        logger.error(f"Error editing income: {e}")
        raise

# Function to remove an expense
def remove_expense(user, expense_id):
    try:
        with connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                DELETE FROM expenses
                WHERE user = %s AND id = %s
                ''', (user, expense_id))
                conn.commit()
        logger.info(f"Expense ID {expense_id} removed by {user}")
    except Exception as e:
        logger.error(f"Error removing expense: {e}")
        raise

# Function to remove an income
def remove_income(user, income_id):
    try:
        with connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                DELETE FROM incomes
                WHERE user = %s AND id = %s
                ''', (user, income_id))
                conn.commit()
        logger.info(f"Income ID {income_id} removed by {user}")
    except Exception as e:
        logger.error(f"Error removing income: {e}")
        raise

# Function to get user limit
def get_limit(user):
    try:
        with connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                SELECT limit
                FROM limits
                WHERE user = %s
                ''', (user,))
                result = cursor.fetchone()
                return result[0] if result else None
    except Exception as e:
        logger.error(f"Error retrieving limit: {e}")
        raise

# Function to set or update user limit
def set_limit(user, limit):
    try:
        with connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                INSERT INTO limits (user, limit)
                VALUES (%s, %s)
                ON CONFLICT (user)
                DO UPDATE SET limit = EXCLUDED.limit
                ''', (user, limit))
                conn.commit()
        logger.info(f"Limit of ${limit} set for user {user}")
    except Exception as e:
        logger.error(f"Error setting limit: {e}")
        raise

# Function to check if limit is exceeded
async def check_limit(update: Update, user, month, year):
    try:
        limit = get_limit(user)
        if limit is None:
            return
        
        total_expenses = get_total_monthly_expenses(user, month, year)
        if total_expenses > limit:
            await update.message.reply_text(
                f"⚠️ Alert: You have exceeded your monthly spending limit of ${limit:.2f}! "
                f"Your total expenses in {month:02d}/{year} are ${total_expenses:.2f}."
            )
    except Exception as e:
        logger.error(f"Error checking limit: {e}")

# Function to generate recommendations
def generate_recommendation(expenses):
    total_expenses = sum(total for _, total in expenses)
    for category, total in expenses:
        if total > 1000 and category.lower() in ['leisure', 'shopping', 'entertainment']:
            return f"Consider reducing expenses in '{category}' (${total:.2f})."
    if total_expenses > 3000:
        return "You are spending too much! Reduce overall expenses."
    elif total_expenses > 1500:
        return "Your expenses are moderate. Try to save a bit more."
    return "Your expenses are under control. Well done!"

# /start command (interactive menu)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("EXPENSE", callback_data="start_expense")],
        [InlineKeyboardButton("INCOME", callback_data="start_income")],
        [InlineKeyboardButton("SUMMARY", callback_data="start_summary")],
        [InlineKeyboardButton("EXCEL SPREADSHEET", callback_data="start_excel")],
        [InlineKeyboardButton("POWER BI", callback_data="start_powerbi")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Choose an option:", reply_markup=reply_markup)
    context.user_data['navigation_stack'] = []

# Handler for initial menu
async def button_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "start_expense":
        keyboard = [
            [InlineKeyboardButton("REGULAR EXPENSE", callback_data="expense_regular")],
            [InlineKeyboardButton("FIXED EXPENSE", callback_data="expense_fixed")],
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Choose the expense type:", reply_markup=reply_markup)
        context.user_data['navigation_stack'].append("start")
    elif query.data == "start_income":
        keyboard = [
            [InlineKeyboardButton("ADD INCOME", callback_data="income_add")],
            [InlineKeyboardButton("EDIT INCOME", callback_data="edit_income")],
            [InlineKeyboardButton("REMOVE INCOME", callback_data="remove_income")],
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Choose an action for Income:", reply_markup=reply_markup)
        context.user_data['navigation_stack'].append("start")
    elif query.data == "start_powerbi":
        await send_powerbi_link(update, context)
        context.user_data['navigation_stack'].append("start")
    elif query.data == "start_summary":
        await summary(update, context)
    elif query.data == "start_excel":
        month = datetime.now().month
        year = datetime.now().year
        context.user_data['excel_month'] = month
        context.user_data['excel_year'] = year
        context.user_data['navigation_stack'].append("start")
        await show_excel_selection(update, context, month, year)

# Function to show month/year selection for Excel spreadsheet
async def show_excel_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, month, year):
    user = str(update.callback_query.message.chat.id)
    try:
        message = f"Select the month and year to generate the spreadsheet:\n\nCurrent month: {month:02d}/{year}"
        keyboard = [
            [
                InlineKeyboardButton("⬅️ Previous Month", callback_data="excel_prev"),
                InlineKeyboardButton("Generate Spreadsheet", callback_data="excel_generate"),
                InlineKeyboardButton("Next Month ➡️", callback_data="excel_next")
            ],
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.edit_text(message, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error showing month selection for Excel: {e}")
        keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.edit_text("Error showing month selection.", reply_markup=reply_markup)

# Handler for Excel selection navigation buttons
async def button_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back":
        await handle_back(update, context)
        return

    month = context.user_data.get('excel_month', datetime.now().month)
    year = context.user_data.get('excel_year', datetime.now().year)

    if query.data == "excel_prev":
        month -= 1
        if month < 1:
            month = 12
            year -= 1
    elif query.data == "excel_next":
        month += 1
        if month > 12:
            month = 1
            year += 1
    elif query.data == "excel_generate":
        await generate_excel_spreadsheet(update, context, month, year)
        return

    context.user_data['excel_month'] = month
    context.user_data['excel_year'] = year
    await show_excel_selection(update, context, month, year)

# Handler to process text messages (interactive flow)
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    if not state:
        return

    user = str(update.message.chat.id)
    month = datetime.now().month
    year = datetime.now().year

    if state == 'awaiting_expense_amount':
        try:
            amount = float(update.message.text)
            if amount <= 0:
                keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("The amount must be positive. Try again.", reply_markup=reply_markup)
                return
            context.user_data['expense_amount'] = amount
            categories = ["Food", "Leisure", "Transportation", "Health", "Others", "Write Category"]
            keyboard = [
                [InlineKeyboardButton(cat, callback_data=f"expense_category_{cat}") for cat in categories[i:i+2]]
                for i in range(0, len(categories), 2)
            ]
            keyboard.append([InlineKeyboardButton("Back", callback_data="back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Choose the expense category or write a custom one:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_expense_category'
            context.user_data['navigation_stack'].append("awaiting_expense_amount")
        except ValueError:
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Invalid amount. Enter a number (e.g., 100).", reply_markup=reply_markup)
    elif state == 'awaiting_expense_category':
        if update.message.text:
            context.user_data['expense_category'] = update.message.text
            payment_methods = ["Credit Card", "Debit Card", "Pix", "Cash"]
            keyboard = [
                [InlineKeyboardButton(pm, callback_data=f"expense_payment_{pm}") for pm in payment_methods[i:i+2]]
                for i in range(0, len(payment_methods), 2)
            ]
            keyboard.append([InlineKeyboardButton("Back", callback_data="back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Choose the payment method:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_expense_payment'
            context.user_data['navigation_stack'].append("awaiting_expense_category")
        else:
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Please write a category or choose one of the options.", reply_markup=reply_markup)
    elif state == 'awaiting_income':
        try:
            parts = update.message.text.split(maxsplit=1)
            if len(parts) != 2:
                keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("Invalid format. Use: AMOUNT DESCRIPTION (e.g., 100 Salary).", reply_markup=reply_markup)
                return
            amount = float(parts[0])
            if amount <= 0:
                keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("The amount must be positive. Try again.", reply_markup=reply_markup)
                return
            description = parts[1]
            date = datetime.now().strftime('%Y-%m-%d')
            save_income(user, amount, description, date)
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Income of ${amount:.2f} - {description} saved!", reply_markup=reply_markup)
            context.user_data.pop('state', None)
            await check_limit(update, user, month, year)
        except ValueError:
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Invalid amount. Enter a number (e.g., 100 Salary).", reply_markup=reply_markup)
    elif state == 'awaiting_fixed_expense_amount':
        try:
            amount = float(update.message.text)
            if amount <= 0:
                keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("The amount must be positive. Try again.", reply_markup=reply_markup)
                return
            context.user_data['fixed_expense_amount'] = amount
            categories = ["Food", "Leisure", "Transportation", "Health", "Others", "Write Category"]
            keyboard = [
                [InlineKeyboardButton(cat, callback_data=f"fixed_expense_category_{cat}") for cat in categories[i:i+2]]
                for i in range(0, len(categories), 2)
            ]
            keyboard.append([InlineKeyboardButton("Back", callback_data="back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Choose the fixed expense category or write a custom one:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_fixed_expense_category'
            context.user_data['navigation_stack'].append("awaiting_fixed_expense_amount")
        except ValueError:
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Invalid amount. Enter a number (e.g., 100).", reply_markup=reply_markup)
    elif state == 'awaiting_fixed_expense_category':
        if update.message.text:
            context.user_data['fixed_expense_category'] = update.message.text
            payment_methods = ["Credit Card", "Debit Card", "Pix", "Cash"]
            keyboard = [
                [InlineKeyboardButton(pm, callback_data=f"fixed_expense_payment_{pm}") for pm in payment_methods[i:i+2]]
                for i in range(0, len(payment_methods), 2)
            ]
            keyboard.append([InlineKeyboardButton("Back", callback_data="back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Choose the payment method for the fixed expense:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_fixed_expense_payment'
            context.user_data['navigation_stack'].append("awaiting_fixed_expense_category")
        else:
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Please write a category or choose one of the options.", reply_markup=reply_markup)
    elif state == 'awaiting_edit_expense_data':
        try:
            parts = update.message.text.split(maxsplit=3)
            amount = float(parts[0]) if len(parts) > 0 and parts[0] else None
            category = parts[1] if len(parts) > 1 and parts[1] else None
            payment_method = parts[2] if len(parts) > 2 and parts[2] else None
            if amount is not None and amount <= 0:
                keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("The amount must be positive.", reply_markup=reply_markup)
                return
            expense_id = context.user_data['edit_id']
            edit_expense(user, expense_id, amount, category, payment_method)
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Expense ID {expense_id} edited successfully!", reply_markup=reply_markup)
            context.user_data.pop('state', None)
            context.user_data.pop('edit_id', None)
        except ValueError:
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Invalid data. Use: AMOUNT CATEGORY PAYMENT (e.g., 200 Food Card).", reply_markup=reply_markup)
        except Exception:
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Error editing expense or ID not found.", reply_markup=reply_markup)
    elif state == 'awaiting_edit_income_data':
        try:
            parts = update.message.text.split(maxsplit=2)
            amount = float(parts[0]) if len(parts) > 0 and parts[0] else None
            description = parts[1] if len(parts) > 1 and parts[1] else None
            if amount is not None and amount <= 0:
                keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("The amount must be positive.", reply_markup=reply_markup)
                return
            income_id = context.user_data['edit_id']
            edit_income(user, income_id, amount, description)
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Income ID {income_id} edited successfully!", reply_markup=reply_markup)
            context.user_data.pop('state', None)
            context.user_data.pop('edit_id', None)
        except ValueError:
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Invalid data. Use: AMOUNT DESCRIPTION (e.g., 200 Salary).", reply_markup=reply_markup)
        except Exception:
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Error editing income or ID not found.", reply_markup=reply_markup)
    elif state == 'awaiting_set_limit':
        try:
            limit = float(update.message.text)
            if limit <= 0:
                keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("The limit must be positive. Try again.", reply_markup=reply_markup)
                return
            set_limit(user, limit)
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Limit of ${limit:.2f} set successfully!", reply_markup=reply_markup)
            context.user_data.pop('state', None)
        except ValueError:
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Invalid value. Enter a number (e.g., 1000).", reply_markup=reply_markup)

# Handler for expense buttons
async def button_expense(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back":
        await handle_back(update, context)
        return

    if query.data == "expense_regular":
        keyboard = [
            [InlineKeyboardButton("ADD REGULAR EXPENSE", callback_data="expense_regular_add")],
            [InlineKeyboardButton("EDIT REGULAR EXPENSE", callback_data="edit_expense")],
            [InlineKeyboardButton("REMOVE REGULAR EXPENSE", callback_data="remove_expense_regular")],
            [InlineKeyboardButton("SET EXPENSE LIMIT", callback_data="set_limit")],
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Choose an action for Regular Expense:", reply_markup=reply_markup)
        context.user_data['navigation_stack'].append("start_expense")
    elif query.data == "expense_fixed":
        keyboard = [
            [InlineKeyboardButton("ADD FIXED EXPENSE", callback_data="expense_fixed_add")],
            [InlineKeyboardButton("EDIT FIXED EXPENSE", callback_data="edit_expense_fixed")],
            [InlineKeyboardButton("REMOVE FIXED EXPENSE", callback_data="remove_expense_fixed")],
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Choose an action for Fixed Expense:", reply_markup=reply_markup)
        context.user_data['navigation_stack'].append("start_expense")
    elif query.data == "expense_regular_add":
        keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Please enter the amount spent (e.g., 100):", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_expense_amount'
        context.user_data['navigation_stack'].append("expense_regular")
    elif query.data == "expense_fixed_add":
        keyboard = [
            [InlineKeyboardButton("DAILY", callback_data="expense_fixed_daily")],
            [InlineKeyboardButton("WEEKLY", callback_data="expense_fixed_weekly")],
            [InlineKeyboardButton("MONTHLY", callback_data="expense_fixed_monthly")],
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Choose the fixed expense frequency:", reply_markup=reply_markup)
        context.user_data['navigation_stack'].append("expense_fixed")
    elif query.data.startswith("expense_fixed_"):
        frequency = query.data[len("expense_fixed_"):]
        context.user_data['fixed_expense_frequency'] = frequency.upper()
        keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"Enter the amount for the {frequency} fixed expense (e.g., 100):", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_fixed_expense_amount'
        context.user_data['navigation_stack'].append("awaiting_fixed_expense_frequency")
    elif query.data.startswith("expense_category_"):
        category = query.data[len("expense_category_"):]
        if category == "Write Category":
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Please write the custom category:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_expense_category'
        else:
            context.user_data['expense_category'] = category
            payment_methods = ["Credit Card", "Debit Card", "Pix", "Cash"]
            keyboard = [
                [InlineKeyboardButton(pm, callback_data=f"expense_payment_{pm}") for pm in payment_methods[i:i+2]]
                for i in range(0, len(payment_methods), 2)
            ]
            keyboard.append([InlineKeyboardButton("Back", callback_data="back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Choose the payment method:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_expense_payment'
            context.user_data['navigation_stack'].append("awaiting_expense_category")
    elif query.data.startswith("expense_payment_"):
        payment_method = query.data[len("expense_payment_"):]
        amount = context.user_data.get('expense_amount')
        category = context.user_data.get('expense_category')
        date = datetime.now().strftime('%Y-%m-%d')
        try:
            user = str(query.message.chat.id)
            save_expense(user, amount, category, payment_method, date)
            msg = f"Regular expense of ${amount:.2f} in category '{category}' ({payment_method}) saved successfully!"
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(msg, reply_markup=reply_markup)
            context.user_data.pop('state', None)
            context.user_data.pop('expense_amount', None)
            context.user_data.pop('expense_category', None)
            month = datetime.now().month
            year = datetime.now().year
            await check_limit(query, user, month, year)
        except Exception as e:
            logger.error(f"Error saving regular expense: {str(e)} - Data: user={user}, amount={amount}, category={category}, payment_method={payment_method}, date={date}")
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(f"Error saving regular expense: {str(e)}", reply_markup=reply_markup)
    elif query.data.startswith("fixed_expense_category_"):
        category = query.data[len("fixed_expense_category_"):]
        if category == "Write Category":
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Please write the custom category for the fixed expense:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_fixed_expense_category'
        else:
            context.user_data['fixed_expense_category'] = category
            payment_methods = ["Credit Card", "Debit Card", "Pix", "Cash"]
            keyboard = [
                [InlineKeyboardButton(pm, callback_data=f"fixed_expense_payment_{pm}") for pm in payment_methods[i:i+2]]
                for i in range(0, len(payment_methods), 2)
            ]
            keyboard.append([InlineKeyboardButton("Back", callback_data="back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Choose the payment method for the fixed expense:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_fixed_expense_payment'
            context.user_data['navigation_stack'].append("awaiting_fixed_expense_payment")
    elif query.data.startswith("fixed_expense_payment_"):
        payment_method = query.data[len("fixed_expense_payment_"):]
        amount = context.user_data.get('fixed_expense_amount')
        category = context.user_data.get('fixed_expense_category')
        frequency = context.user_data.get('fixed_expense_frequency')
        date = datetime.now().strftime('%Y-%m-%d')
        try:
            user = str(query.message.chat.id)
            save_expense(user, amount, f"{category} ({frequency})", payment_method, date)
            msg = f"Fixed expense of ${amount:.2f} in category '{category}' ({frequency}, {payment_method}) saved successfully!"
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(msg, reply_markup=reply_markup)
            context.user_data.pop('state', None)
            context.user_data.pop('fixed_expense_amount', None)
            context.user_data.pop('fixed_expense_category', None)
            context.user_data.pop('fixed_expense_frequency', None)
            month = datetime.now().month
            year = datetime.now().year
            await check_limit(query, user, month, year)
        except Exception as e:
            logger.error(f"Error saving fixed expense: {str(e)}")
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(f"Error saving fixed expense: {str(e)}", reply_markup=reply_markup)
    elif query.data == "set_limit":
        keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Please enter the limit amount (e.g., 1000):", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_set_limit'
        context.user_data['navigation_stack'].append("expense_regular")

# Handler for income buttons
async def button_income(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "income_add":
        keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Please enter the income amount (e.g., 100) and description (e.g., 'Salary'):", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_income'
        context.user_data['navigation_stack'].append("start_income")

# Handler for edit and remove buttons
async def button_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = str(query.message.chat.id)

    if query.data == "back":
        await handle_back(update, context)
        return

    if query.data == "edit_expense":  # For Regular Expense
        try:
            expenses = list_monthly_expenses(user, datetime.now().month, datetime.now().year)
            regular_expenses = [e for e in expenses if not any(p in e[2] for p in ["(DAILY)", "(WEEKLY)", "(MONTHLY)"])]
            if not regular_expenses:
                keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.edit_text("No regular expenses recorded to edit.", reply_markup=reply_markup)
                return
            keyboard = [
                [InlineKeyboardButton(f"ID {expense[0]} - ${expense[1]:.2f} - {expense[2]} - {expense[3]}", callback_data=f"edit_expense_select_{expense[0]}")]
                for expense in regular_expenses
            ]
            keyboard.append([InlineKeyboardButton("Back", callback_data="back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Select the regular expense to edit:", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("expense_regular")
        except Exception as e:
            logger.error(f"Error loading expenses for editing: {str(e)}")
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Error loading expenses for editing.", reply_markup=reply_markup)
    elif query.data == "edit_expense_fixed":
        try:
            expenses = list_monthly_expenses(user, datetime.now().month, datetime.now().year)
            fixed_expenses = [e for e in expenses if any(p in e[2] for p in ["(DAILY)", "(WEEKLY)", "(MONTHLY)"])]
            if not fixed_expenses:
                keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.edit_text("No fixed expenses recorded to edit.", reply_markup=reply_markup)
                return
            keyboard = [
                [InlineKeyboardButton(f"ID {expense[0]} - ${expense[1]:.2f} - {exercise[2]} - {expense[3]}", callback_data=f"edit_expense_select_{expense[0]}")]
                for expense in fixed_expenses
            ]
            keyboard.append([InlineKeyboardButton("Back", callback_data="back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Select the fixed expense to edit:", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("expense_fixed")
        except Exception as e:
            logger.error(f"Error loading fixed expenses for editing: {str(e)}")
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Error loading fixed expenses for editing.", reply_markup=reply_markup)
    elif query.data == "edit_income":
        try:
            incomes = list_monthly_incomes(user, datetime.now().month, datetime.now().year)
            if not incomes:
                keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.edit_text("No incomes recorded to edit.", reply_markup=reply_markup)
                return
            keyboard = [
                [InlineKeyboardButton(f"ID {income[0]} - ${income[1]:.2f} - {income[2]}", callback_data=f"edit_income_select_{income[0]}")]
                for income in incomes
            ]
            keyboard.append([InlineKeyboardButton("Back", callback_data="back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Select the income to edit:", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("start_income")
        except Exception as e:
            logger.error(f"Error loading incomes for editing: {str(e)}")
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Error loading incomes for editing.", reply_markup=reply_markup)
    elif query.data.startswith("edit_expense_select_"):
        expense_id = int(query.data[len("edit_expense_select_"):])
        context.user_data['edit_id'] = expense_id
        keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Enter the new amount (optional), category (optional), and payment method (optional), separated by space (e.g., 200 Food Card):", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_edit_expense_data'
        context.user_data['navigation_stack'].append("edit_expense")
    elif query.data.startswith("edit_income_select_"):
        income_id = int(query.data[len("edit_income_select_"):])
        context.user_data['edit_id'] = income_id
        keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Enter the new amount (optional) and description (optional), separated by space (e.g., 200 Salary):", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_edit_income_data'
        context.user_data['navigation_stack'].append("edit_income")
    elif query.data == "remove_expense_regular":
        try:
            expenses = list_monthly_expenses(user, datetime.now().month, datetime.now().year)
            regular_expenses = [e for e in expenses if not any(p in e[2] for p in ["(DAILY)", "(WEEKLY)", "(MONTHLY)"])]
            if not regular_expenses:
                keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.edit_text("No regular expenses recorded to remove.", reply_markup=reply_markup)
                return
            keyboard = [
                [InlineKeyboardButton(f"ID {expense[0]} - ${expense[1]:.2f} - {expense[2]} - {expense[3]}", callback_data=f"remove_expense_regular_select_{expense[0]}")]
                for expense in regular_expenses
            ]
            keyboard.append([InlineKeyboardButton("Back", callback_data="back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Select the regular expense to remove:", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("expense_regular")
        except Exception as e:
            logger.error(f"Error loading regular expenses for removal: {str(e)}")
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Error loading regular expenses for removal.", reply_markup=reply_markup)
    elif query.data == "remove_expense_fixed":
        try:
            expenses = list_monthly_expenses(user, datetime.now().month, datetime.now().year)
            fixed_expenses = [e for e in expenses if any(p in e[2] for p in ["(DAILY)", "(WEEKLY)", "(MONTHLY)"])]
            if not fixed_expenses:
                keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.edit_text("No fixed expenses recorded to remove.", reply_markup=reply_markup)
                return
            keyboard = [
                [InlineKeyboardButton(f"ID {expense[0]} - ${expense[1]:.2f} - {expense[2]} - {expense[3]}", callback_data=f"remove_expense_fixed_select_{expense[0]}")]
                for expense in fixed_expenses
            ]
            keyboard.append([InlineKeyboardButton("Back", callback_data="back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Select the fixed expense to remove:", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("expense_fixed")
        except Exception as e:
            logger.error(f"Error loading fixed expenses for removal: {str(e)}")
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Error loading fixed expenses for removal.", reply_markup=reply_markup)
    elif query.data == "remove_income":
        try:
            incomes = list_monthly_incomes(user, datetime.now().month, datetime.now().year)
            if not incomes:
                keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.edit_text("No incomes recorded to remove.", reply_markup=reply_markup)
                return
            keyboard = [
                [InlineKeyboardButton(f"ID {income[0]} - ${income[1]:.2f} - {income[2]}", callback_data=f"remove_income_select_{income[0]}")]
                for income in incomes
            ]
            keyboard.append([InlineKeyboardButton("Back", callback_data="back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Select the income to remove:", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("start_income")
        except Exception as e:
            logger.error(f"Error loading incomes for removal: {str(e)}")
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Error loading incomes for removal.", reply_markup=reply_markup)
    elif query.data.startswith("remove_expense_regular_select_"):
        expense_id = query.data[len("remove_expense_regular_select_"):]
        context.user_data['remove_id'] = expense_id
        context.user_data['remove_type'] = 'expense_regular'
        expenses = list_monthly_expenses(user, datetime.now().month, datetime.now().year)
        expense = next((e for e in expenses if str(e[0]) == expense_id), None)
        if expense:
            option = f"the regular expense ID {expense[0]} - ${expense[1]:.2f} - {expense[2]} - {expense[3]}"
            keyboard = [
                [
                    InlineKeyboardButton("YES", callback_data="confirm_remove_yes"),
                    InlineKeyboardButton("NO", callback_data="confirm_remove_no")
                ],
                [InlineKeyboardButton("Back", callback_data="back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(f"Are you sure you want to remove {option}?", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("remove_expense_regular")
    elif query.data.startswith("remove_expense_fixed_select_"):
        expense_id = query.data[len("remove_expense_fixed_select_"):]
        context.user_data['remove_id'] = expense_id
        context.user_data['remove_type'] = 'expense_fixed'
        expenses = list_monthly_expenses(user, datetime.now().month, datetime.now().year)
        expense = next((e for e in expenses if str(e[0]) == expense_id), None)
        if expense:
            option = f"the fixed expense ID {expense[0]} - ${expense[1]:.2f} - {expense[2]} - {expense[3]}"
            keyboard = [
                [
                    InlineKeyboardButton("YES", callback_data="confirm_remove_yes"),
                    InlineKeyboardButton("NO", callback_data="confirm_remove_no")
                ],
                [InlineKeyboardButton("Back", callback_data="back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(f"Are you sure you want to remove {option}?", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("remove_expense_fixed")
    elif query.data.startswith("remove_income_select_"):
        income_id = query.data[len("remove_income_select_"):]
        context.user_data['remove_id'] = income_id
        context.user_data['remove_type'] = 'income'
        incomes = list_monthly_incomes(user, datetime.now().month, datetime.now().year)
        income = next((i for i in incomes if str(i[0]) == income_id), None)
        if income:
            option = f"the income ID {income[0]} - ${income[1]:.2f} - {income[2]}"
            keyboard = [
                [
                    InlineKeyboardButton("YES", callback_data="confirm_remove_yes"),
                    InlineKeyboardButton("NO", callback_data="confirm_remove_no")
                ],
                [InlineKeyboardButton("Back", callback_data="back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(f"Are you sure you want to remove {option}?", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("remove_income")
    elif query.data == "confirm_remove_yes":
        try:
            remove_id = context.user_data.get('remove_id')
            remove_type = context.user_data.get('remove_type')
            if remove_type == 'expense_regular':
                remove_expense(user, int(remove_id))
                msg = f"Regular expense ID {remove_id} removed successfully!"
            elif remove_type == 'expense_fixed':
                remove_expense(user, int(remove_id))
                msg = f"Fixed expense ID {remove_id} removed successfully!"
            elif remove_type == 'income':
                remove_income(user, int(remove_id))
                msg = f"Income ID {remove_id} removed successfully!"
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(msg, reply_markup=reply_markup)
            context.user_data.pop('remove_id', None)
            context.user_data.pop('remove_type', None)
        except Exception as e:
            logger.error(f"Error removing: {str(e)}")
            keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Error removing the item.", reply_markup=reply_markup)
    elif query.data == "confirm_remove_no":
        keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Removal canceled.", reply_markup=reply_markup)

# Function to handle the "Back" button
async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not context.user_data.get('navigation_stack') or len(context.user_data['navigation_stack']) == 0:
        await start(query, context)  # Always return to the main menu if the stack is empty
        context.user_data['state'] = None  # Clear the state
        return

    previous_state = context.user_data['navigation_stack'].pop()

    if previous_state == "start":
        await start(query, context)
    elif previous_state == "start_expense":
        keyboard = [
            [InlineKeyboardButton("REGULAR EXPENSE", callback_data="expense_regular")],
            [InlineKeyboardButton("FIXED EXPENSE", callback_data="expense_fixed")],
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Choose the expense type:", reply_markup=reply_markup)
    elif previous_state == "start_income":
        keyboard = [
            [InlineKeyboardButton("ADD INCOME", callback_data="income_add")],
            [InlineKeyboardButton("EDIT INCOME", callback_data="edit_income")],
            [InlineKeyboardButton("REMOVE INCOME", callback_data="remove_income")],
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Choose an action for Income:", reply_markup=reply_markup)
    elif previous_state == "expense_regular":
        keyboard = [
            [InlineKeyboardButton("ADD REGULAR EXPENSE", callback_data="expense_regular_add")],
            [InlineKeyboardButton("EDIT REGULAR EXPENSE", callback_data="edit_expense")],
            [InlineKeyboardButton("REMOVE REGULAR EXPENSE", callback_data="remove_expense_regular")],
            [InlineKeyboardButton("SET EXPENSE LIMIT", callback_data="set_limit")],
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Choose an action for Regular Expense:", reply_markup=reply_markup)
    elif previous_state == "expense_fixed":
        keyboard = [
            [InlineKeyboardButton("ADD FIXED EXPENSE", callback_data="expense_fixed_add")],
            [InlineKeyboardButton("EDIT FIXED EXPENSE", callback_data="edit_expense_fixed")],
            [InlineKeyboardButton("REMOVE FIXED EXPENSE", callback_data="remove_expense_fixed")],
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Choose an action for Fixed Expense:", reply_markup=reply_markup)
    elif previous_state == "edit_expense":
        await button_action(Update(0, query.message), context, "edit_expense")
    elif previous_state == "edit_expense_fixed":
        await button_action(Update(0, query.message), context, "edit_expense_fixed")
    elif previous_state == "edit_income":
        await button_action(Update(0, query.message), context, "edit_income")
    elif previous_state == "remove_expense_regular":
        await button_action(Update(0, query.message), context, "remove_expense_regular")
    elif previous_state == "remove_expense_fixed":
        await button_action(Update(0, query.message), context, "remove_expense_fixed")
    elif previous_state == "remove_income":
        await button_action(Update(0, query.message), context, "remove_income")
    elif previous_state == "awaiting_expense_amount":
        keyboard = [
            [InlineKeyboardButton("ADD REGULAR EXPENSE", callback_data="expense_regular_add")],
            [InlineKeyboardButton("EDIT REGULAR EXPENSE", callback_data="edit_expense")],
            [InlineKeyboardButton("REMOVE REGULAR EXPENSE", callback_data="remove_expense_regular")],
            [InlineKeyboardButton("SET EXPENSE LIMIT", callback_data="set_limit")],
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Choose an action for Regular Expense:", reply_markup=reply_markup)
        context.user_data['state'] = None
    elif previous_state == "awaiting_expense_category":
        categories = ["Food", "Leisure", "Transportation", "Health", "Others", "Write Category"]
        keyboard = [
            [InlineKeyboardButton(cat, callback_data=f"expense_category_{cat}") for cat in categories[i:i+2]]
            for i in range(0, len(categories), 2)
        ]
        keyboard.append([InlineKeyboardButton("Back", callback_data="back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Choose the expense category or write a custom one:", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_expense_category'
    elif previous_state == "awaiting_fixed_expense_frequency":
        keyboard = [
            [InlineKeyboardButton("DAILY", callback_data="expense_fixed_daily")],
            [InlineKeyboardButton("WEEKLY", callback_data="expense_fixed_weekly")],
            [InlineKeyboardButton("MONTHLY", callback_data="expense_fixed_monthly")],
            [InlineKeyboardButton("Back", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Choose the fixed expense frequency:", reply_markup=reply_markup)
    elif previous_state == "awaiting_fixed_expense_amount":
        frequency = context.user_data.get('fixed_expense_frequency', '').lower()
        keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"Enter the amount for the {frequency} fixed expense (e.g., 100):", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_fixed_expense_amount'
    elif previous_state == "awaiting_fixed_expense_category":
        categories = ["Food", "Leisure", "Transportation", "Health", "Others", "Write Category"]
        keyboard = [
            [InlineKeyboardButton(cat, callback_data=f"fixed_expense_category_{cat}") for cat in categories[i:i+2]]
            for i in range(0, len(categories), 2)
        ]
        keyboard.append([InlineKeyboardButton("Back", callback_data="back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Choose the fixed expense category or write a custom one:", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_fixed_expense_category'
    elif previous_state == "awaiting_fixed_expense_payment":
        payment_methods = ["Credit Card", "Debit Card", "Pix", "Cash"]
        keyboard = [
            [InlineKeyboardButton(pm, callback_data=f"fixed_expense_payment_{pm}") for pm in payment_methods[i:i+2]]
            for i in range(0, len(payment_methods), 2)
        ]
        keyboard.append([InlineKeyboardButton("Back", callback_data="back")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Choose the payment method for the fixed expense:", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_fixed_expense_payment'
    elif previous_state == "start_summary":
        await start(query, context)
    elif previous_state == "start_excel":
        month = context.user_data.get('excel_month', datetime.now().month)
        year = context.user_data.get('excel_year', datetime.now().year)
        await show_excel_selection(update, context, month, year)

# /summary command
async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    month = datetime.now().month
    year = datetime.now().year
    context.user_data['summary_month'] = month
    context.user_data['summary_year'] = year
    context.user_data['navigation_stack'].append("start")
    await show_summary(update, context, month, year)

# Function to show summary with buttons
async def show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE, month, year):
    user = str(update.message.chat.id) if update.message else str(update.callback_query.message.chat.id)
    try:
        expenses = get_monthly_expenses(user, month, year)
        incomes = get_monthly_incomes(user, month, year)
        summary_text = f"Summary for {month:02d}/{year}:\n"
        
        if expenses:
            summary_text += "Expenses:\n"
            emojis = ["🟦", "🟩", "🟪", "🟥", "🟧"]
            max_amount = max(total for _, total in expenses)
            for i, (category, total) in enumerate(expenses):
                emoji = emojis[i % len(emojis)]
                bar_length = int((total / max_amount) * 10) if max_amount > 0 else 0
                bar = "▬" * bar_length
                summary_text += f"{emoji} {category}: ${total:.2f} {bar}\n"
            total_expenses = sum(total for _, total in expenses)
            summary_text += f"Total Expenses: ${total_expenses:.2f}\n"
        else:
            summary_text += "No expenses recorded.\n"
            total_expenses = 0
        
        summary_text += f"\nIncomes: ${incomes:.2f}\n"
        balance = incomes - total_expenses
        summary_text += f"Balance: ${balance:.2f}\n"
        
        if expenses:
            recommendation = generate_recommendation(expenses)
            summary_text += f"\nRecommendation: {recommendation}"

        keyboard = [
            [
                InlineKeyboardButton("⬅️ Previous Month", callback_data="summary_prev"),
                InlineKeyboardButton("Back", callback_data="back"),
                InlineKeyboardButton("Next Month ➡️", callback_data="summary_next")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.message:
            await update.message.reply_text(summary_text, reply_markup=reply_markup)
        else:
            await update.callback_query.message.edit_text(summary_text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.message:
            await update.message.reply_text("Error generating summary.", reply_markup=reply_markup)
        else:
            await update.callback_query.message.edit_text("Error generating summary.", reply_markup=reply_markup)

# Handler for /summary navigation buttons
async def button_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "back":
        await handle_back(update, context)
        return

    month = context.user_data.get('summary_month', datetime.now().month)
    year = context.user_data.get('summary_year', datetime.now().year)

    if query.data == "summary_prev":
        month -= 1
        if month < 1:
            month = 12
            year -= 1
    elif query.data == "summary_next":
        month += 1
        if month > 12:
            month = 1
            year += 1

    context.user_data['summary_month'] = month
    context.user_data['summary_year'] = year

    await show_summary(update, context, month, year)

# /powerbi command
POWER_BI_BASE_LINK = "https://app.powerbi.com/links/vv8SkpDKaL?filter=public%20expenses/user%20eq%20'"
async def send_powerbi_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        user_id = str(query.from_user.id)
        filtered_link = f"{POWER_BI_BASE_LINK}'{user_id}'"
        keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"View your report (log in to Power BI): {filtered_link}", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error generating Power BI link: {str(e)}")
        keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Error generating Power BI link.", reply_markup=reply_markup)

# Function to generate and send Excel spreadsheet with charts and summary
async def generate_excel_spreadsheet(update: Update, context: ContextTypes.DEFAULT_TYPE, month, year):
    query = update.callback_query
    await query.answer()

    user = str(query.message.chat.id)
    try:
        expenses = list_monthly_expenses(user, month, year)
        incomes = list_monthly_incomes(user, month, year)
        expenses_summary = get_monthly_expenses(user, month, year)
        total_incomes = get_monthly_incomes(user, month, year)
        total_expenses = get_total_monthly_expenses(user, month, year)

        if expenses:
            df_expenses = pd.DataFrame(expenses, columns=['ID', 'Amount', 'Category', 'Payment Method', 'Date'])
        else:
            df_expenses = pd.DataFrame(columns=['ID', 'Amount', 'Category', 'Payment Method', 'Date'])

        if incomes:
            df_incomes = pd.DataFrame(incomes, columns=['ID', 'Amount', 'Description', 'Date'])
        else:
            df_incomes = pd.DataFrame(columns=['ID', 'Amount', 'Description', 'Date'])

        if expenses_summary:
            df_expenses_summary = pd.DataFrame(expenses_summary, columns=['Category', 'Total'])
        else:
            df_expenses_summary = pd.DataFrame(columns=['Category', 'Total'])

        df_summary = pd.DataFrame({
            'Description': ['Total Expenses', 'Total Incomes', 'Balance'],
            'Amount': [total_expenses, total_incomes, total_incomes - total_expenses]
        })

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_expenses.to_excel(writer, sheet_name='Expenses', index=False)
            df_incomes.to_excel(writer, sheet_name='Incomes', index=False)
            df_expenses_summary.to_excel(writer, sheet_name='Expenses by Category', index=False)
            df_summary.to_excel(writer, sheet_name='Summary', index=False)

            workbook = writer.book
            worksheet = workbook['Expenses by Category']

            chart = BarChart()
            chart.title = f"Expenses by Category - {month:02d}/{year}"
            chart.x_axis.title = "Category"
            chart.y_axis.title = "Amount ($)"

            data = Reference(worksheet, min_col=2, min_row=1, max_row=len(expenses_summary) + 1, max_col=2)
            categories = Reference(worksheet, min_col=1, min_row=2, max_row=len(expenses_summary) + 1)
            chart.add_data(data, titles_from_data=True)
            chart.set_categories(categories)

            chart.datalabels = DataLabelList()
            chart.datalabels.showVal = True

            worksheet.add_chart(chart, "D2")

        output.seek(0)

        await query.message.reply_document(
            document=output,
            filename=f"financial_report_{user}_{month:02d}_{year}.xlsx",
            caption=f"Spreadsheet for {month:02d}/{year} generated successfully!"
        )
        output.close()

        keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Spreadsheet generated successfully!", reply_markup=reply_markup)
        context.user_data['navigation_stack'].append("start")

    except Exception as e:
        logger.error(f"Error generating Excel spreadsheet: {e}")
        keyboard = [[InlineKeyboardButton("Back", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"Error generating spreadsheet: {str(e)}", reply_markup=reply_markup)

# Main asynchronous function with webhooks
async def main():
    try:
        application = Application.builder().token("7585573573:AAHC-v1EwpHHiBCJ5JSINejrMTdKJRIbqr4").build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_start, pattern="^start_"))
        application.add_handler(CallbackQueryHandler(button_expense, pattern="^(expense_|set_limit|back)"))
        application.add_handler(CallbackQueryHandler(button_income, pattern="^income_"))
        application.add_handler(CallbackQueryHandler(button_action, pattern="^(edit_|remove_|confirm_|back)"))
        application.add_handler(CallbackQueryHandler(button_summary, pattern="^(summary_|back)"))
        application.add_handler(CallbackQueryHandler(button_excel, pattern="^(excel_|back)"))
        application.add_handler(CommandHandler("summary", summary))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

        port = int(os.environ.get("PORT", 8443))
        hostname = "smartmoneyiabot.onrender.com"
        webhook_url = f"https://{hostname}/webhook"
        logger.info(f"Setting webhook URL: {webhook_url} on port {port}")

        await application.bot.set_webhook(url=webhook_url)
        await application.initialize()
        await application.start()
        await application.updater.start_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="/webhook",
            webhook_url=webhook_url
        )

        logger.info(f"Bot started successfully via webhook on port {port}.")
        
        while True:
            await asyncio.sleep(3600)

    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        if 'application' in locals():
            if application.updater:
                await application.updater.stop()
            await application.stop()
            await application.shutdown()
        raise

if __name__ == "__main__":
    asyncio.run(main())
