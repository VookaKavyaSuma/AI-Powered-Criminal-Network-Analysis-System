import os
import sys
import pandas as pd
import random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_GEN_DIR = os.path.join(PROJECT_ROOT, 'data-generation')
OUTPUT_DIR = os.path.join(DATA_GEN_DIR, 'output')

os.makedirs(OUTPUT_DIR, exist_ok=True)

VEHICLE_TYPES = ['SUV', 'Sedan', 'Hatchback', 'Motorcycle', 'Auto Rickshaw', 'Truck']

def main():
    try:
        entities_path = os.path.join(DATA_GEN_DIR, 'Entities.xlsx')
        entities_df = pd.read_excel(entities_path)
        
        output_data = []
        for _, row in entities_df.iterrows():
            veh_reg = str(row.get('vehicle_reg', '—')).strip()
            
            if veh_reg and veh_reg != '—' and veh_reg.lower() != 'nan':
                output_data.append({
                    "registration_number": veh_reg,
                    "owner_name": str(row.get('name', '')),
                    "vehicle_type": random.choice(VEHICLE_TYPES),
                    "registered_address": str(row.get('address', ''))
                })
        
        out_df = pd.DataFrame(output_data)
        out_path = os.path.join(OUTPUT_DIR, 'vehicle_registry_seed.csv')
        out_df.to_csv(out_path, index=False)
        print(f"Generated {len(out_df)} vehicle records in {out_path}")
        
    except Exception as e:
        print(f"Error generating vehicle registry: {e}")

if __name__ == "__main__":
    main()
