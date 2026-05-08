import json
from app import app
from database import db, Recipe

with app.app_context():
    recipes = Recipe.query.all()
    print(f"Total recipes: {len(recipes)}")
    for r in recipes[:5]:
        print(f"ID: {r.id}, Title: {r.title}")
        print(f"Ingredients JSON: {r.ingredients_json[:100]}...")
        try:
            ings = json.loads(r.ingredients_json)
            print(f"Parsed ingredients count: {len(ings)}")
        except:
            print("Failed to parse JSON")
        print("-" * 20)
