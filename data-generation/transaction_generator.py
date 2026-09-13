import os
import sys
import random
import math
from datetime import datetime, timedelta
import pandas as pd
import openpyxl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

ENTITIES_FILE = os.path.join(BASE_DIR, 'Entities.xlsx')
RELATIONS_FILE = os.path.join(BASE_DIR, 'Relationships.xlsx')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'transactions.csv')

START_DATE = datetime(2024, 8, 15)
END_DATE = datetime(2024, 9, 15)

BANKS = ['SBI', 'HDFC', 'ICICI', 'Federal Bank', 'South Indian Bank']
TXN_TYPES = ['NEFT', 'RTGS', 'UPI', 'CASH_DEPOSIT']

def random_date(start, end):
    return start + timedelta(seconds=random.randint(0, int((end - start).total_seconds())))

def generate_account(name, entity_id):
    prefix = str(name)[:4].upper() if pd.notna(name) else 'UNKN'
    prefix = prefix.ljust(4, 'X')
    num = str(random.randint(1000, 9999))
    return f"ACC_{prefix}_{num}"

def main():
    print("Loading ground truth for Transaction generation...")
    entities_df = pd.read_excel(ENTITIES_FILE)
    rels_df = pd.read_excel(RELATIONS_FILE)

    entity_accounts = {}
    all_accounts = []
    
    for _, row in entities_df.iterrows():
        eid = row['entity_id']
        acc = generate_account(row.get('name'), eid)
        entity_accounts[eid] = acc
        all_accounts.append(acc)

    if not all_accounts:
        all_accounts = [f"ACC_TEST_{random.randint(1000,9999)}" for _ in range(20)]
        
    records = []

    # Structuring flags and specific funds transfers
    for _, rel in rels_df.iterrows():
        sub = rel.get('subject_id')
        obj = rel.get('object_id')
        pred = rel.get('predicate')
        
        acc1 = entity_accounts.get(sub)
        acc2 = entity_accounts.get(obj)
        
        if pred == 'TRANSFERRED_FUNDS' and acc1 and acc2:
            num_txns = random.randint(3, 8)
            for _ in range(num_txns):
                amount = random.randint(50000, 500000)
                # Ensure E019 to E001 is inside this bound as per requirements
                records.append({
                    'sender_account': acc1,
                    'receiver_account': acc2,
                    'amount': amount,
                    'txn_timestamp': random_date(START_DATE, END_DATE).strftime('%Y-%m-%d %H:%M:%S'),
                    'txn_type': random.choice(TXN_TYPES),
                    'bank_name': random.choice(BANKS),
                    'flagged_structuring': False,
                    'source_name': 'FININT_BATCH_01'
                })
                
    # Clean revenue: E019 to E001
    acc_e019 = entity_accounts.get('E019')
    acc_e001 = entity_accounts.get('E001')
    if acc_e019 and acc_e001:
        for _ in range(random.randint(3, 8)):
            amount = random.randint(100000, 500000)
            records.append({
                'sender_account': acc_e019,
                'receiver_account': acc_e001,
                'amount': amount,
                'txn_timestamp': random_date(START_DATE, END_DATE).strftime('%Y-%m-%d %H:%M:%S'),
                'txn_type': random.choice(['NEFT', 'RTGS']),
                'bank_name': random.choice(BANKS),
                'flagged_structuring': False,
                'source_name': 'FININT_BATCH_01'
            })

    # Structuring patterns: E018/E019 sending just under 50k to different accounts
    struct_entities = ['E018', 'E019']
    for eid in struct_entities:
        sender_acc = entity_accounts.get(eid)
        if sender_acc:
            for _ in range(random.randint(5, 10)):
                receiver = random.choice(all_accounts)
                while receiver == sender_acc:
                    receiver = random.choice(all_accounts)
                amount = random.randint(45000, 49999)
                records.append({
                    'sender_account': sender_acc,
                    'receiver_account': receiver,
                    'amount': amount,
                    'txn_timestamp': random_date(START_DATE, END_DATE).strftime('%Y-%m-%d %H:%M:%S'),
                    'txn_type': random.choice(['NEFT', 'RTGS']),
                    'bank_name': random.choice(BANKS),
                    'flagged_structuring': True,
                    'source_name': 'FININT_BATCH_01'
                })

    # Noise Transactions
    num_noise = random.randint(200, 400) - len(records)
    if num_noise > 0:
        for _ in range(num_noise):
            acc1 = random.choice(all_accounts)
            acc2 = random.choice(all_accounts)
            while acc1 == acc2:
                acc2 = random.choice(all_accounts)
            
            records.append({
                'sender_account': acc1,
                'receiver_account': acc2,
                'amount': random.randint(500, 15000),
                'txn_timestamp': random_date(START_DATE, END_DATE).strftime('%Y-%m-%d %H:%M:%S'),
                'txn_type': random.choice(['UPI', 'UPI', 'NEFT']),
                'bank_name': random.choice(BANKS),
                'flagged_structuring': False,
                'source_name': 'FININT_BATCH_01'
            })

    df = pd.DataFrame(records)
    df = df.sample(frac=1).reset_index(drop=True)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Generated {len(df)} transaction records and saved to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
