import asyncio
from datetime import datetime
from connection import init_db
from services import (
    register, login, add_transaction, 
    get_user_transactions, get_balance_and_summary, 
    edit_transaction, delete_transaction,
    set_currency, set_budget, show_analytics, export_to_csv
)

def prompt_int(message):
    while True:
        try:
            return int(input(message))
        except ValueError:
            print("Error: Please enter a valid integer!")

def prompt_date():
    raw = input('Date (YYYY-MM-DD HH:MM) or press Enter for CURRENT: ').strip()
    if not raw:
        return datetime.now()
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M")
    except ValueError:
        print("Invalid format! Defaulting to current timestamp.")
        return datetime.now()

async def main():
    await init_db()
    
    while True:
        choice = input("\n1. Register\n2. Log in\n3. Exit\nChoose action: ").strip()
        match choice:
            case '1':
                username = input('Username: ').strip()
                password = input('Password: ').strip()
                email = input('Email: ').strip()
                if username and password:
                    await register(username, password, email)
                else:
                    print("Username and password cannot be empty!")
            case '2':
                username = input('Username: ').strip()
                password = input('Password: ').strip()
                user = await login(username, password)
                
                if not user:
                    continue

                logged_in_user = user
                while True:
                    print(f"\n=== DASHBOARD ({logged_in_user['username']}) ===")
                    print("1. Add Income")
                    print("2. Add Expense")
                    print("3. View Transactions")
                    print("4. Balance & Summary")
                    print("5. Set Category Budget")
                    print("6. View Expense Analytics (Chart)")
                    print("7. Export Data to CSV")
                    print("8. Edit Transaction")
                    print("9. Delete Transaction")
                    print("10. Change Settings (Currency)")
                    print("11. Log Out")
                    
                    sub_choice = input("Select option: ").strip()
                    
                    match sub_choice:
                        case '1' | '2':
                            trans_type = 'income' if sub_choice == '1' else 'expense'
                            amount = prompt_int('Amount: ')
                            category = input('Category (e.g., Food, Salary, Transport): ').strip() or 'General'
                            description = input('Description: ').strip()
                            date = prompt_date()
                            
                            await add_transaction(logged_in_user['id'], amount, trans_type, category, description, date)

                        case '3':
                            print("\nFilters:")
                            t_type = input("Type (1. Incomes, 2. Expenses, Enter: All): ").strip()
                            trans_filter = 'income' if t_type == '1' else ('expense' if t_type == '2' else None)
                            
                            p_type = input("Period (1. Today, 2. This Month, Enter: All Time): ").strip()
                            period_filter = 'today' if p_type == '1' else ('month' if p_type == '2' else 'all')
                            
                            await get_user_transactions(logged_in_user['id'], trans_filter, period_filter)

                        case '4':
                            await get_balance_and_summary(logged_in_user['id'])

                        case '5':
                            cat = input('Category name: ').strip()
                            limit = prompt_int('Monthly spending limit: ')
                            await set_budget(logged_in_user['id'], cat, limit)

                        case '6':
                            await show_analytics(logged_in_user['id'])

                        case '7':
                            file_name = input("Enter file name (default: export.csv): ").strip() or "export.csv"
                            await export_to_csv(logged_in_user['id'], file_name)

                        case '8':
                            t_id = prompt_int('Transaction ID to edit: ')
                            new_amount = prompt_int('New Amount: ')
                            new_cat = input('New Category: ').strip() or 'General'
                            new_desc = input('New Description: ').strip()
                            await edit_transaction(t_id, logged_in_user['id'], new_amount, new_cat, new_desc)

                        case '9':
                            t_id = prompt_int('Transaction ID to delete: ')
                            await delete_transaction(t_id, logged_in_user['id'])

                        case '10':
                            curr = input("Enter currency sign/code (e.g., USD, EUR, TJS, $): ").strip()
                            if curr:
                                await set_currency(logged_in_user['id'], curr)

                        case '11':
                            print("Logging out...")
                            break
            case '3':
                print('Exiting application...')
                break

if __name__ == "__main__":
    asyncio.run(main())