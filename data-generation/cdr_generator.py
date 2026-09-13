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
EVENTS_FILE = os.path.join(BASE_DIR, 'Events.xlsx')
OUTPUT_FILE = os.path.join(OUTPUT_DIR, 'cdr_records.csv')

START_DATE = datetime(2024, 8, 15)
END_DATE = datetime(2024, 9, 15)

TOWERS = [
    {'id': f'TWR_KL{str(i).zfill(2)}', 'lat': 9.9312 + random.uniform(-1, 1)*0.5, 'lng': 76.2673 + random.uniform(-1, 1)*0.5}
    for i in range(1, 16)
]

def random_date(start, end):
    return start + timedelta(seconds=random.randint(0, int((end - start).total_seconds())))

def get_phone(phone_val):
    if pd.isna(phone_val):
        return None
    try:
        return str(int(float(phone_val)))
    except:
        return str(phone_val).strip()

def main():
    print("Loading ground truth for CDR generation...")
    entities_df = pd.read_excel(ENTITIES_FILE)
    rels_df = pd.read_excel(RELATIONS_FILE)
    try:
        events_df = pd.read_excel(EVENTS_FILE)
    except:
        events_df = pd.DataFrame(columns=['event_id', 'description', 'date', 'location'])

    entity_phones = {}
    valid_phones = []
    
    for _, row in entities_df.iterrows():
        phone = get_phone(row.get('phone'))
        if phone and phone.lower() not in ['none', 'nan', '', '—', '-']:
            entity_phones[row['entity_id']] = phone
            valid_phones.append(phone)

    if not valid_phones:
        print("No valid phones found. Generating some dummy ones.")
        for i in range(20):
            valid_phones.append(f'98470{str(i).zfill(5)}')
            entity_phones[f'E{str(i).zfill(3)}'] = valid_phones[-1]

    records = []

    # Process Relationships
    for _, rel in rels_df.iterrows():
        sub = rel.get('subject_id')
        obj = rel.get('object_id')
        pred = rel.get('predicate')
        
        p1 = entity_phones.get(sub)
        p2 = entity_phones.get(obj)
        
        if p1 and p2:
            if pred == 'CALLED':
                num_calls = random.randint(5, 15)
                for _ in range(num_calls):
                    call_time = random_date(START_DATE, END_DATE)
                    duration = random.randint(60, 600)
                    twr = random.choice(TOWERS)
                    records.append({
                        'caller_number': p1,
                        'callee_number': p2,
                        'call_timestamp': call_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'duration_sec': duration,
                        'call_type': random.choices(['voice', 'sms'], weights=[0.8, 0.2])[0],
                        'tower_id': twr['id'],
                        'tower_lat': twr['lat'],
                        'tower_lng': twr['lng'],
                        'source_name': 'CDR_PROVIDER_ALPHA'
                    })
            elif pred == 'MET_WITH':
                num_calls = random.randint(1, 3)
                for _ in range(num_calls):
                    call_time = random_date(START_DATE, END_DATE)
                    duration = random.randint(10, 120)
                    twr = random.choice(TOWERS)
                    records.append({
                        'caller_number': p1,
                        'callee_number': p2,
                        'call_timestamp': call_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'duration_sec': duration,
                        'call_type': random.choices(['voice', 'sms'], weights=[0.9, 0.1])[0],
                        'tower_id': twr['id'],
                        'tower_lat': twr['lat'],
                        'tower_lng': twr['lng'],
                        'source_name': 'CDR_PROVIDER_ALPHA'
                    })

    # Event Spikes
    for _, event in events_df.iterrows():
        ev_date = pd.to_datetime(event['date']) if 'date' in event else None
        if not pd.isna(ev_date) and START_DATE <= ev_date <= END_DATE:
            spike_start = ev_date - timedelta(days=2)
            spike_end = ev_date
            
            # Select random pairs of entities to spike
            if len(valid_phones) >= 2:
                for _ in range(random.randint(10, 20)):
                    p1, p2 = random.sample(valid_phones, 2)
                    call_time = random_date(spike_start, spike_end)
                    twr = random.choice(TOWERS)
                    records.append({
                        'caller_number': p1,
                        'callee_number': p2,
                        'call_timestamp': call_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'duration_sec': random.randint(30, 300),
                        'call_type': random.choices(['voice', 'sms'], weights=[0.7, 0.3])[0],
                        'tower_id': twr['id'],
                        'tower_lat': twr['lat'],
                        'tower_lng': twr['lng'],
                        'source_name': 'CDR_PROVIDER_ALPHA'
                    })
    
    # Noise records
    current_count = len(records)
    target_count = random.randint(500, 800)
    num_noise = max(100, target_count - current_count)
    for _ in range(num_noise):
        p1, p2 = random.choices(valid_phones, k=2)
        while p1 == p2:
            p2 = random.choice(valid_phones)
        call_time = random_date(START_DATE, END_DATE)
        twr = random.choice(TOWERS)
        records.append({
            'caller_number': p1,
            'callee_number': p2,
            'call_timestamp': call_time.strftime('%Y-%m-%d %H:%M:%S'),
            'duration_sec': random.randint(5, 300),
            'call_type': random.choices(['voice', 'sms'], weights=[0.8, 0.2])[0],
            'tower_id': twr['id'],
            'tower_lat': twr['lat'],
            'tower_lng': twr['lng'],
            'source_name': 'CDR_PROVIDER_ALPHA'
        })
        
    df = pd.DataFrame(records)
    # Shuffle
    df = df.sample(frac=1).reset_index(drop=True)
    df.to_csv(OUTPUT_FILE, index=False)
    print(f"Generated {len(df)} CDR records and saved to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
