import sqlite3
import os
def create_database():
    # Connect to the database file (create it if it doesn't exist)
    conn = sqlite3.connect('senate_tracker.db')
    c = conn.cursor()

    # Define the structure of the reports and transactions tables
    c.execute('''CREATE TABLE IF NOT EXISTS reports
                 (reportID TEXT PRIMARY KEY,
                  first_name TEXT,
                  last_name TEXT,
                  full_name TEXT,
                  report_title TEXT,
                  filed_date DATE,
                  ptr_link TEXT,
                  transactions_processed INTEGER DEFAULT 0)''')

    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (reportID TEXT,
                  number INTEGER,
                  date DATE,
                  owner TEXT,
                  ticker TEXT,
                  asset_name TEXT,
                  asset_type TEXT,
                  type TEXT,
                  amount TEXT,
                  comment TEXT,
                  FOREIGN KEY(reportID) REFERENCES reports(reportID))''')

    conn.commit()
    return conn

def save_report_to_database(conn, report_data):
    c = conn.cursor()
    # Insert the report data into the `reports` table
    c.execute('''INSERT INTO reports (reportID, first_name, last_name, full_name, report_title, filed_date, ptr_link)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (report_data['reportID'], report_data['first_name'], report_data['last_name'], 
               report_data['full_name'], report_data['report_title'], 
               report_data['filed_date'], report_data['ptr_link']))
    conn.commit()

def save_transactions_to_database(conn, transactions):
    c = conn.cursor()
    # Insert each transaction into the `transactions` table
    for transaction in transactions:
        c.execute('''INSERT INTO transactions
                     (reportID, number, date, owner, ticker, asset_name, asset_type, type, amount, comment)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (transaction['reportID'], transaction['number'], transaction['date'], transaction['owner'],
                   transaction['ticker'], transaction['asset_name'], transaction['asset_type'],
                   transaction['type'], transaction['amount'], transaction['comment']))
    conn.commit()


def clear_db():
    file_path = "senate_tracker.db"

    # Check if the file exists before attempting to delete it
    if os.path.exists(file_path):
        os.remove(file_path)
        print("File deleted successfully.")
    else:
        print("File does not exist.")