import os
import sys
import pandas as pd
import random
import json
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_GEN_DIR = os.path.join(PROJECT_ROOT, 'data-generation')
OUTPUT_DIR = os.path.join(DATA_GEN_DIR, 'output', 'labeled_ner_data')

os.makedirs(OUTPUT_DIR, exist_ok=True)

def find_entities(text, entities_dict):
    """
    Find non-overlapping entities in the text based on exact string match.
    Returns list of [start, end, label]
    """
    found = []
    
    all_entities = []
    for label, strings in entities_dict.items():
        for s in strings:
            if s and str(s).strip() and str(s).lower() != 'nan':
                all_entities.append((s, label))
                
    all_entities.sort(key=lambda x: len(x[0]), reverse=True)
    
    occupied = []
    for ent_str, label in all_entities:
        pattern = re.compile(r'\b' + re.escape(str(ent_str)) + r'\b')
        for match in pattern.finditer(text):
            start, end = match.start(), match.end()
            overlap = False
            for (os, oe) in occupied:
                if not (end <= os or start >= oe):
                    overlap = True
                    break
            if not overlap:
                found.append([start, end, label])
                occupied.append((start, end))
                
    # Sort entities by start position to match typical NER format expectations
    found.sort(key=lambda x: x[0])
    return found

def main():
    try:
        entities_path = os.path.join(DATA_GEN_DIR, 'Entities.xlsx')
        entities_df = pd.read_excel(entities_path)
        
        persons = []
        organizations = []
        locations = ["Fort Kochi", "Ernakulam junction", "Marine Drive", "Kozhikode", "Aluva", "Mattancherry", "Vytilla", "Edappally"]
        vehicles = []
        phones = []
        
        for _, row in entities_df.iterrows():
            name = str(row.get('name', ''))
            etype = str(row.get('type', '')).lower()
            if etype == 'person' and name and name.lower() != 'nan':
                persons.append(name)
            elif etype == 'organization' and name and name.lower() != 'nan':
                organizations.append(name)
                
            veh = str(row.get('vehicle_reg', '—')).strip()
            if veh and veh != '—' and veh.lower() != 'nan':
                vehicles.append(veh)
                
            ph = row.get('phone', None)
            if not pd.isna(ph):
                try:
                    ph_str = str(int(float(ph)))
                    phones.append(ph_str)
                except:
                    pass
                    
            addr = str(row.get('address', ''))
            if addr and addr.lower() != 'nan':
                locations.append(addr)

        entities_dict = {
            "PERSON": persons,
            "ORGANIZATION": organizations,
            "LOCATION": locations,
            "VEHICLE": vehicles,
            "PHONE": phones
        }

        templates = [
            "{PERSON} was spotted near {LOCATION} on August 20.",
            "Vehicle {VEHICLE} was seen at {LOCATION}.",
            "A call from {PHONE} to {PERSON} lasted 5 minutes.",
            "{ORGANIZATION} transferred funds to a suspected account.",
            "{PERSON} met with {PERSON} near {LOCATION} to discuss logistics.",
            "Suspect used vehicle {VEHICLE} to travel to {LOCATION}.",
            "We intercepted a message from {PHONE} at midnight.",
            "The properties in {LOCATION} are owned by {ORGANIZATION}.",
            "It is believed that {PERSON} manages {ORGANIZATION}.",
            "Intelligence suggests {PERSON} will be in {LOCATION} tomorrow.",
            "The shipment arrived at {LOCATION} via {VEHICLE}.",
            "Contact was established using {PHONE} near {LOCATION}.",
            "{PERSON} was seen exiting {VEHICLE} at {LOCATION}."
        ]
        
        noise_sentences = [
            "The weather today is exceptionally sunny.",
            "Please bring the files to the meeting room.",
            "I will be late for the dinner tonight.",
            "There were no significant updates during the morning briefing.",
            "Can you verify the transaction details?",
            "The system is currently undergoing maintenance."
        ]
        
        generated_data = []
        
        for _ in range(160):
            template = random.choice(templates)
            
            text = template
            if "{PERSON}" in text and persons:
                for _ in range(text.count("{PERSON}")):
                    text = text.replace("{PERSON}", random.choice(persons), 1)
            if "{LOCATION}" in text and locations:
                for _ in range(text.count("{LOCATION}")):
                    text = text.replace("{LOCATION}", random.choice(locations), 1)
            if "{VEHICLE}" in text and vehicles:
                for _ in range(text.count("{VEHICLE}")):
                    text = text.replace("{VEHICLE}", random.choice(vehicles), 1)
            if "{PHONE}" in text and phones:
                for _ in range(text.count("{PHONE}")):
                    text = text.replace("{PHONE}", random.choice(phones), 1)
            if "{ORGANIZATION}" in text and organizations:
                for _ in range(text.count("{ORGANIZATION}")):
                    text = text.replace("{ORGANIZATION}", random.choice(organizations), 1)
            
            ents = find_entities(text, entities_dict)
            generated_data.append({"text": text, "entities": ents})
            
        for _ in range(40):
            text = random.choice(noise_sentences)
            ents = find_entities(text, entities_dict)
            generated_data.append({"text": text, "entities": ents})
            
        random.shuffle(generated_data)
        
        out_path = os.path.join(OUTPUT_DIR, 'ner_training.jsonl')
        with open(out_path, 'w', encoding='utf-8') as f:
            for item in generated_data:
                f.write(json.dumps(item) + '\n')
                
        print(f"Generated {len(generated_data)} NER labeled sentences in {out_path}")
        
    except Exception as e:
        print(f"Error generating NER labels: {e}")

if __name__ == "__main__":
    main()
