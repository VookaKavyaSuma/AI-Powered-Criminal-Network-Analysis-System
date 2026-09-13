import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENTITIES_FILE = os.path.join(BASE_DIR, "Entities.xlsx")
RELATIONSHIPS_FILE = os.path.join(BASE_DIR, "Relationships.xlsx")
EVENTS_FILE = os.path.join(BASE_DIR, "Events.xlsx")

ALL_ENTITIES = []
ALL_RELATIONSHIPS = []
ALL_EVENTS = []

def load_data():
    global ALL_ENTITIES, ALL_RELATIONSHIPS, ALL_EVENTS
    
    if os.path.exists(ENTITIES_FILE):
        df_ent = pd.read_excel(ENTITIES_FILE, engine='openpyxl')
        for _, row in df_ent.iterrows():
            ent = row.to_dict()
            phone = ent.get('phone')
            if pd.notna(phone) and phone != '—':
                ent['phone'] = str(int(float(phone))) if type(phone) in (float, int) else str(phone)
            else:
                ent['phone'] = None
                
            veh = ent.get('vehicle_reg')
            if veh == '—' or pd.isna(veh):
                ent['vehicle_reg'] = None
            
            ALL_ENTITIES.append(ent)
            
    if os.path.exists(RELATIONSHIPS_FILE):
        df_rel = pd.read_excel(RELATIONSHIPS_FILE, engine='openpyxl')
        for _, row in df_rel.iterrows():
            rel = row.to_dict()
            ALL_RELATIONSHIPS.append(rel)
            
    if os.path.exists(EVENTS_FILE):
        df_ev = pd.read_excel(EVENTS_FILE, engine='openpyxl')
        for _, row in df_ev.iterrows():
            ev = row.to_dict()
            ALL_EVENTS.append(ev)

load_data()

def get_entity(entity_id):
    for ent in ALL_ENTITIES:
        if ent.get('entity_id') == entity_id:
            return ent
    return None

def get_relationships_for(entity_id):
    rels = []
    for rel in ALL_RELATIONSHIPS:
        if rel.get('subject_id') == entity_id or rel.get('object_id') == entity_id:
            rels.append(rel)
    return rels

def get_events():
    return ALL_EVENTS
