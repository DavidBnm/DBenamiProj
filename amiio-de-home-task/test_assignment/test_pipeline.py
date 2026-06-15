import pandas as pd
import sqlite3

# Poor practice: Hardcoded DB path and global connections
conn = sqlite3.connect('my_data.db')

def load_data():
    # Poor practice: No error handling, hardcoded path, printing instead of logging
    print("Loading data...")
    df = pd.read_csv("data.csv")
    return df

def clean_data(df):
    # Poor practice: Inefficient loops and string formatting
    print("Cleaning data...")
    for index, row in df.iterrows():
        df.at[index, 'email'] = str(row['email']).strip().lower()
    return df

def save_to_db(df):
    # Poor practice: No transaction management, no error handling
    print("Saving to DB...")
    df.to_sql('users', conn, if_exists='replace', index=False)

def main():
    # Poor practice: Global logic run inside main without try-except blocks
    data = load_data()
    clean_data = clean_data(data)
    save_to_db(clean_data)
    print("Done!")

if __name__ == "__main__":
    main()
