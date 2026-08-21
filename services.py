import csv
from datetime import datetime
from tabulate import tabulate
from passlib.context import CryptContext
from connection import get_connection

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

async def register(username, password, email):
    hashed_pwd = pwd_context.hash(password)
    query = "INSERT INTO customers (username, password, email, balance) VALUES ($1, $2, $3, 0);"
    async with get_connection() as conn:
        try:
            await conn.execute(query, username, hashed_pwd, email)
            print("Success: User registered successfully!")
        except Exception as er:
            print(f"Registration Error: {er}")

async def login(username, password):
    query = "SELECT * FROM customers WHERE username = $1"
    async with get_connection() as conn:
        try:
            user = await conn.fetchrow(query, username)
            if user and pwd_context.verify(password, user["password"]):
                print(f"Welcome back, {user['username']}!")
                return user
            print("Error: Invalid username or password!")
            return None
        except Exception as er:
            print(er)
            return None

async def set_currency(user_id, new_currency):
    query = "UPDATE customers SET currency = $1 WHERE id = $2"
    async with get_connection() as conn:
        try:
            await conn.execute(query, new_currency.upper(), user_id)
            print(f"Success: Preferred currency set to {new_currency.upper()}")
        except Exception as er:
            print(f"Error updating currency: {er}")

async def check_budget_limit(user_id, category, amount):
    query = """
        SELECT b.monthly_limit, COALESCE(SUM(t.amount), 0) AS current_spent
        FROM budgets b
        LEFT JOIN transaction t ON b.category = t.category 
            AND t.user_id = b.user_id 
            AND t.type = 'expense'
            AND t.created_at >= date_trunc('month', CURRENT_DATE)
        WHERE b.user_id = $1 AND b.category = $2
        GROUP BY b.monthly_limit;
    """
    async with get_connection() as conn:
        budget = await conn.fetchrow(query, user_id, category)
        if budget:
            limit = budget['monthly_limit']
            spent = budget['current_spent'] + amount
            if spent > limit:
                print(f"\n[WARNING] You have exceeded your monthly limit for '{category}'! (Spent: {spent}/{limit})")
            else:
                print(f"[BUDGET INFO] Spent {spent} out of {limit} for '{category}' this month.")

async def add_transaction(user_id, amount, trans_type, category, description, created_at):
    query_trans = """
        INSERT INTO transaction (user_id, amount, type, category, description, created_at) 
        VALUES ($1, $2, $3, $4, $5, $6)
    """
    balance_change = amount if trans_type == 'income' else -amount
    query_balance = "UPDATE customers SET balance = balance + $1 WHERE id = $2"

    async with get_connection() as conn:
        async with conn.transaction():
            try:
                await conn.execute(query_trans, user_id, amount, trans_type, category, description, created_at)
                await conn.execute(query_balance, balance_change, user_id)
                print("Success: Transaction recorded!")
                if trans_type == 'expense':
                    await check_budget_limit(user_id, category, amount)
            except Exception as er:
                print(f"Transaction Error: {er}")

async def get_user_transactions(user_id, trans_type=None, period='all'):
    base_query = "SELECT id, amount, type, category, description, created_at FROM transaction WHERE user_id = $1"
    args = [user_id]
    
    if trans_type:
        args.append(trans_type)
        base_query += f" AND type = ${len(args)}"
        
    if period == 'today':
        base_query += " AND created_at >= CURRENT_DATE"
    elif period == 'month':
        base_query += " AND created_at >= date_trunc('month', CURRENT_DATE)"
        
    base_query += " ORDER BY created_at DESC;"

    async with get_connection() as conn:
        try:
            records = await conn.fetch(base_query, *args)
            if not records:
                print("No transactions found.")
                return
            
            table = [[r['id'], r['type'], r['amount'], r['category'], r['created_at'].strftime("%Y-%m-%d %H:%M"), r['description']] for r in records]
            print("\n" + tabulate(table, headers=["ID", "Type", "Amount", "Category", "Date", "Description"], tablefmt="grid"))
        except Exception as er:
            print(f"Fetch Error: {er}")

async def get_balance_and_summary(user_id):
    query_cust = "SELECT balance, currency FROM customers WHERE id = $1"
    query_stats = """
        SELECT 
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0) as total_income,
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0) as total_expense
        FROM transaction 
        WHERE user_id = $1;
    """
    async with get_connection() as conn:
        try:
            user = await conn.fetchrow(query_cust, user_id)
            stats = await conn.fetchrow(query_stats, user_id)
            c = user['currency']
            print(f"\n--- FINANCIAL SUMMARY ({c}) ---")
            print(f"Current Balance: {user['balance']} {c}")
            print(f"Total Incomes:  +{stats['total_income']} {c}")
            print(f"Total Expenses: -{stats['total_expense']} {c}")
            print(f"Net Profit:      {stats['total_income'] - stats['total_expense']} {c}")
        except Exception as er:
            print(er)

async def set_budget(user_id, category, limit):
    query = """
        INSERT INTO budgets (user_id, category, monthly_limit)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id, category) 
        DO UPDATE SET monthly_limit = EXCLUDED.monthly_limit;
    """
    async with get_connection() as conn:
        try:
            await conn.execute(query, user_id, category, limit)
            print(f"Success: Budget for '{category}' set to {limit}.")
        except Exception as er:
            print(f"Budget Error: {er}")

async def show_analytics(user_id):
    query = """
        SELECT category, SUM(amount) as total
        FROM transaction
        WHERE user_id = $1 AND type = 'expense'
        GROUP BY category
        ORDER BY total DESC;
    """
    async with get_connection() as conn:
        try:
            records = await conn.fetch(query, user_id)
            if not records:
                print("No expenses recorded for analytics.")
                return
            
            max_val = max(r['total'] for r in records)
            print("\n--- EXPENSE BREAKDOWN BY CATEGORY ---")
            for r in records:
                bar_length = int((r['total'] / max_val) * 20)
                bar = "█" * bar_length
                print(f"{r['category']:<15} | {bar:<20} | {r['total']}")
        except Exception as er:
            print(f"Analytics Error: {er}")

async def export_to_csv(user_id, filename="transactions_export.csv"):
    query = "SELECT id, amount, type, category, description, created_at FROM transaction WHERE user_id = $1 ORDER BY created_at DESC"
    async with get_connection() as conn:
        try:
            records = await conn.fetch(query, user_id)
            if not records:
                print("No data to export.")
                return
            
            with open(filename, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(["ID", "Amount", "Type", "Category", "Description", "Date"])
                for r in records:
                    writer.writerow([r['id'], r['amount'], r['type'], r['category'], r['description'], r['created_at']])
            print(f"Success: Exported {len(records)} records to '{filename}'.")
        except Exception as er:
            print(f"Export Error: {er}")

async def edit_transaction(transaction_id, user_id, new_amount, new_category, new_description):
    query_select = "SELECT amount, type FROM transaction WHERE id = $1 AND user_id = $2"
    query_update = "UPDATE transaction SET amount = $1, category = $2, description = $3 WHERE id = $4 AND user_id = $5"
    query_balance = "UPDATE customers SET balance = balance + $1 WHERE id = $2"

    async with get_connection() as conn:
        async with conn.transaction():
            try:
                old_trans = await conn.fetchrow(query_select, transaction_id, user_id)
                if not old_trans:
                    print("Error: Transaction not found!")
                    return
                
                diff = new_amount - old_trans['amount']
                balance_diff = diff if old_trans['type'] == 'income' else -diff
                
                await conn.execute(query_update, new_amount, new_category, new_description, transaction_id, user_id)
                await conn.execute(query_balance, balance_diff, user_id)
                print("Success: Transaction updated!")
            except Exception as er:
                print(f"Edit Error: {er}")

async def delete_transaction(transaction_id, user_id):
    query_select = "SELECT amount, type FROM transaction WHERE id = $1 AND user_id = $2"
    query_delete = "DELETE FROM transaction WHERE id = $1 AND user_id = $2"
    query_balance = "UPDATE customers SET balance = balance + $1 WHERE id = $2"

    async with get_connection() as conn:
        async with conn.transaction():
            try:
                trans = await conn.fetchrow(query_select, transaction_id, user_id)
                if not trans:
                    print("Error: Transaction not found!")
                    return
                
                revert_amount = -trans['amount'] if trans['type'] == 'income' else trans['amount']
                await conn.execute(query_delete, transaction_id, user_id)
                await conn.execute(query_balance, revert_amount, user_id)
                print("Success: Transaction deleted!")
            except Exception as er:
                print(er)