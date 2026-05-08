import json
import re
from app import app, STOP_WORDS, to_singular
from database import db, Recipe
from ingredient_parser import parse_ingredient

with app.app_context():
    cloud_frequencies = {}
    recipes = Recipe.query.all()
    print(f"Checking {len(recipes)} recipes...")
    for r in recipes:
        try:
            raw_ingredients = json.loads(r.ingredients_json)
        except:
            raw_ingredients = []
            
        print(f"Recipe: {r.title} ({len(raw_ingredients)} ingredients)")
        for raw_ing in raw_ingredients:
            try:
                parsed = parse_ingredient(raw_ing)
                if parsed.name:
                    for obj in parsed.name:
                        if hasattr(obj, 'text'):
                            name_val = obj.text.lower()
                            words = re.findall(r'[a-z0-9-]+', name_val)
                            clean_words = [w for w in words if w not in STOP_WORDS]
                            
                            phrase = " ".join(clean_words).strip()
                            phrase_sing = to_singular(phrase)
                            
                            if len(phrase_sing) > 2:
                                cloud_frequencies[phrase_sing] = cloud_frequencies.get(phrase_sing, 0) + 1
                                # print(f"  Word: {phrase_sing}")
                            else:
                                # print(f"  Skipped (too short): {phrase_sing}")
                                pass
                else:
                    # print(f"  No name found for: {raw_ing}")
                    pass
            except Exception as e:
                print(f"  Error parsing {raw_ing}: {e}")

    print(f"Cloud frequencies count: {len(cloud_frequencies)}")
    sorted_words = sorted(cloud_frequencies.keys(), key=lambda x: cloud_frequencies[x], reverse=True)
    print(f"Top 10 words: {sorted_words[:10]}")
