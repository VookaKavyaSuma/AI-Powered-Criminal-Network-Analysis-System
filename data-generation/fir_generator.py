import os
import sys
import time
import random
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ground_truth import ALL_ENTITIES, ALL_RELATIONSHIPS, ALL_EVENTS, get_entity

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

try:
    from groq import Groq
    if GROQ_API_KEY:
        client = Groq(api_key=GROQ_API_KEY)
    else:
        client = None
except ImportError:
    client = None

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "fir_reports")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def generate_fir_fallback(fir_no, entities, event):
    names = [e.get('name', 'Unknown') for e in entities]
    phones = [e.get('phone') for e in entities if e.get('phone')]
    vehicles = [e.get('vehicle_reg') for e in entities if e.get('vehicle_reg')]
    
    desc = event.get('description', 'An incident occurred')
    loc = event.get('location', 'Unknown location')
    date = event.get('date', 'Unknown date')
    
    fir_text = f"FIR No: {fir_no}\nPolice Station: Central Police Station\nDate: {date}\nOfficer: Insp. Sharma\n\n"
    fir_text += f"Report: On {date} at {loc}, it was reported that {desc}. "
    fir_text += f"Individuals involved may include {', '.join(names)}. "
    if phones:
        fir_text += f"Contact numbers associated with the incident: {', '.join(phones)}. "
    if vehicles:
        fir_text += f"Vehicles spotted at the scene: {', '.join(vehicles)}. "
    fir_text += "Investigation is ongoing."
    return fir_text

def generate_fir_groq(fir_no, entities, event, relationships):
    if not client:
        return generate_fir_fallback(fir_no, entities, event)
        
    facts = []
    for e in entities:
        # Deliberately vary names
        name = e.get('name', '')
        if random.random() < 0.3:
            name_parts = name.split()
            if len(name_parts) > 1:
                name = name_parts[0] + " " + name_parts[1][0] + "."
        elif random.random() < 0.3:
            name_parts = name.split()
            if name_parts:
                name = name_parts[0]
                
        fact = f"Entity: {name}, Role: {e.get('role', 'Unknown')}"
        if e.get('phone'): fact += f", Phone: {e.get('phone')}"
        if e.get('vehicle_reg'): fact += f", Vehicle: {e.get('vehicle_reg')}"
        facts.append(fact)
        
    for r in relationships:
        s = get_entity(r.get('subject_id', ''))
        o = get_entity(r.get('object_id', ''))
        if s and o:
            facts.append(f"Relationship: {s.get('name')} {r.get('predicate')} {o.get('name')}")
            
    prompt = f"""You are generating a realistic Indian police FIR (First Information Report) for a synthetic crime dataset.

Facts to include (do NOT invent additional facts):
Entities: {'; '.join(facts)}
Event: {event.get('description', '')} at {event.get('location', '')} on {event.get('date', '')}

Generate a realistic FIR narrative that naturally mentions these people, phone numbers, vehicle registrations, and locations.
Whenever transactions, cash deposits, or money laundering activities are mentioned, explicitly state realistic currency amounts formatted with Rupee symbols (e.g. ₹48,000, ₹2,50,000, ₹5,00,000, ₹15,00,000).
Include a header with: FIR No: {fir_no}, Police Station, Date, Complainant/Officer name.
Write 200-400 words in formal police report style.
"""
    retries = 3
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=600,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            err_str = str(e)
            if '429' in err_str or 'rate' in err_str.lower():
                wait = (2 ** attempt) * 2
                print(f"Rate limited. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"Error calling Groq: {e}")
                break
    return generate_fir_fallback(fir_no, entities, event)

def generate_all_firs():
    print(f"Generating FIRs to {OUTPUT_DIR}")
    events = ALL_EVENTS if ALL_EVENTS else [{'description': 'Default event', 'location': 'Delhi', 'date': '2023-01-01'}]
    
    num_firs = min(25, max(20, len(events) * 3))
    
    for i in range(1, num_firs + 1):
        fir_no = f"FIR_{i:03d}"
        
        event = random.choice(events)
        
        # Select 2-4 entities
        if len(ALL_ENTITIES) >= 4:
            num_entities = random.randint(2, 4)
            entities = random.sample(ALL_ENTITIES, num_entities)
        else:
            entities = ALL_ENTITIES
            
        # Get relevant relationships for selected entities
        entity_ids = [e.get('entity_id') for e in entities]
        relevant_rels = [r for r in ALL_RELATIONSHIPS if r.get('subject_id') in entity_ids or r.get('object_id') in entity_ids]
        # Keep only a subset to fragment info
        if relevant_rels:
            relevant_rels = random.sample(relevant_rels, min(2, len(relevant_rels)))
            
        print(f"Generating {fir_no}...")
        fir_content = generate_fir_groq(fir_no, entities, event, relevant_rels)
        
        out_path = os.path.join(OUTPUT_DIR, f"{fir_no}.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(fir_content)
            
        print(f"Saved {fir_no}.txt")
        time.sleep(2.5) # Rate limiting

if __name__ == "__main__":
    generate_all_firs()
