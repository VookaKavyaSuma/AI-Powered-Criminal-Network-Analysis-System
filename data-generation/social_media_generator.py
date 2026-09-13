import os
import sys
import time
import random
import json
import datetime
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ground_truth import ALL_ENTITIES, ALL_RELATIONSHIPS, ALL_EVENTS

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

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "social_media_posts")
os.makedirs(OUTPUT_DIR, exist_ok=True)

PLATFORMS = ['WhatsApp', 'Twitter', 'Facebook', 'Instagram']

def generate_social_media_fallback(entity, is_noise=False):
    name = entity.get('name', 'Unknown')
    username = name.lower().replace(" ", "") + str(random.randint(10, 99))
    
    if is_noise:
        contents = [
            "Had a great lunch today! The weather is amazing.",
            "Stuck in traffic again on MG Road. #pune #traffic",
            "Can't wait for the weekend!",
            "Anyone know a good mechanic nearby?"
        ]
        content = random.choice(contents)
    else:
        contents = [
            "Package delivered. Call me.",
            "Meeting at the usual spot tonight.",
            "Boss called, plans changed.",
            "Got the stuff. 5pm."
        ]
        content = random.choice(contents)
        
    return content, username

def generate_social_media_groq(entity, is_noise, platform):
    if not client:
        return generate_social_media_fallback(entity, is_noise)
        
    name = entity.get('name', 'Unknown')
    username = name.lower().replace(" ", "") + str(random.randint(10, 99))
    
    if is_noise:
        prompt = f"Write a short, casual {platform} post by a person named {name}. It should be about everyday normal life (food, traffic, weather, etc.). Do not mention crimes."
    else:
        prompt = f"Write a short, informal {platform} message or post by an operative named {name}. It should contain veiled references or coded language like 'package delivered', 'meeting at the usual spot', or mentioning a location vaguely. Keep it short and natural for {platform}."
        
    retries = 3
    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.8
            )
            content = response.choices[0].message.content.strip()
            # Remove quotes if generated
            if content.startswith('"') and content.endswith('"'):
                content = content[1:-1]
            return content, username
        except Exception as e:
            err_str = str(e)
            if '429' in err_str or 'rate' in err_str.lower():
                wait = (2 ** attempt) * 2
                print(f"Rate limited. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"Error calling Groq: {e}")
                break
                
    return generate_social_media_fallback(entity, is_noise)

def generate_all_posts():
    print(f"Generating Social Media Posts to {OUTPUT_DIR}")
    
    if not ALL_ENTITIES:
        print("No entities found. Please ensure ground truth data is loaded.")
        entities_to_use = [{'name': 'John Doe'}]
    else:
        entities_to_use = ALL_ENTITIES
        
    num_posts = random.randint(15, 20)
    
    for i in range(1, num_posts + 1):
        post_id = f"SM_{i:03d}"
        platform = random.choice(PLATFORMS)
        entity = random.choice(entities_to_use)
        
        # 40% chance of noise post
        is_noise = random.random() < 0.4
        
        print(f"Generating {post_id}...")
        content, username = generate_social_media_groq(entity, is_noise, platform)
        
        timestamp = (datetime.datetime.now() - datetime.timedelta(days=random.randint(1, 30))).isoformat()
        
        post_data = {
            "platform": platform,
            "username": username,
            "post_id": post_id,
            "timestamp": timestamp,
            "content": content,
            "metadata": {
                "is_suspicious": not is_noise,
                "original_entity_id": entity.get('entity_id')
            }
        }
        
        out_path = os.path.join(OUTPUT_DIR, f"{post_id}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(post_data, f, indent=4)
            
        print(f"Saved {post_id}.json")
        time.sleep(2.5) # Rate limiting

if __name__ == "__main__":
    generate_all_posts()
