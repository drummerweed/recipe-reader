import os
import re
from ingredient_parser import parse_ingredient
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from scraper import scrape_recipe
from database import db, Recipe, Ingredient, SearchWord

app = Flask(__name__, static_folder="/frontend", static_url_path="")
CORS(app)

# Use absolute path for DB to ensure it mounts safely if we add volumes later
# We'll just put it in /app/recipes.db for now
import os
import re
from ingredient_parser import parse_ingredient
os.makedirs('/app/data', exist_ok=True)
db_path = '/app/data/recipes.db'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

# ── Helpers

STOP_WORDS = {
    'cup', 'cups', 'teaspoon', 'teaspoons', 'tablespoon', 'tablespoons', 'ounce', 'ounces',
    'pound', 'pounds', 'gram', 'grams', 'clove', 'cloves', 'pinch', 'dash', 'slice', 'slices',
    'chopped', 'diced', 'minced', 'sliced', 'peeled', 'fresh', 'dried', 'ground', 'crushed',
    'large', 'medium', 'small', 'whole', 'half', 'quarter', 'taste', 'optional', 'divided',
    'package', 'can', 'jar', 'bottle', 'dash', 'sprig', 'sprigs', 'piece', 'pieces', 'head',
    'bunch', 'bunches', 'packed', 'garnish', 'fluid', 'dry', 'red', 'green', 'yellow', 'white',
    'black', 'brown', 'sweet', 'hot', 'cold', 'warm', 'boiling', 'water', 'salt', 'pepper', 'black pepper',
    'and', 'or', 'with', 'for', 'the', 'a', 'an', 'to', 'of', 'in', 'on', 'at', 'by', 'as', 'into',
    'yield', 'yields', 'servings', 'serving', 'leaves', 'leaf', 'cut', 'thinly', 'thickly',
    'carton', 'cartons', 'fat', 'free', 'low', 'sodium', 'fat-free', 'low-sodium', 'box', 'boxes',
    'bag', 'bags', 'container', 'containers', 'frozen', 'prepared', 'cooked', 'uncooked', 'raw',
    'shredded', 'grated', 'melted', 'beaten', 'extra', 'virgin', 'spray', 'cooking', 'kosher', 'sea',
    'table', 'universal', 'purpose', 'all-purpose', 'bleached', 'unbleached', 'enriched', 'about',
    'plus', 'more', 'less', 'to', 'taste'
}

def to_singular(word):
    w = word.lower().strip()
    if len(w) <= 2: return w
    
    # Specific exceptions
    if w == 'potatoes': return 'potato'
    if w == 'tomatoes': return 'tomato'
    
    if w[-3:] == 'ies':
        return w[:-3] + 'y'
    if w[-2:] == 'es' and w[-3] in ['s', 'x', 'z', 'h']:
        return w[:-2]
    if w[-1] == 's' and w[-2] != 's':
        return w[:-1]
    return w


def guess_category(title, tags=""):
    """Heuristic to guess Breakfast, Lunch, Dinner, or Snacks."""
    text = f"{title} {tags}".lower()
    
    if "breakfast" in text or "pancake" in text or "waffle" in text or "omelet" in text or "eggs" in text or "muffin" in text:
        return "Breakfast"
    if "snack" in text or "dip" in text or "cookie" in text or "bar " in text or "bites" in text:
        return "Snacks"
    if "lunch" in text or "sandwich" in text or "wrap" in text or "salad" in text:
        return "Lunch"
    # Default to Dinner
    return "Dinner"

def save_recipe_to_db(data):
    """Takes the scrape dict and saves it to DB, including normalizing ingredients."""
    # Check if already exists by URL
    existing = Recipe.query.filter_by(source_url=data.get('source_url')).first()
    if existing:
        return existing

    title = data.get('title', 'Untitled Recipe')
    
    # Attempt to pull tags if our scraper caught them eventually, else just title
    category = guess_category(title, "")


    def to_str(val):
        if not val: return None
        if isinstance(val, list): return ", ".join([str(v) for v in val])
        return str(val)

    r = Recipe(
        source_url=data.get('source_url'),
        title=title,
        image=data.get('image'),
        category=category,
        yields=to_str(data.get('yields')),
        prep_time=to_str(data.get('prep_time')),
        cook_time=to_str(data.get('cook_time')),
        total_time=to_str(data.get('total_time')),
        ingredients_json=json.dumps(data.get('ingredients', [])),
        instructions_json=json.dumps(data.get('instructions', [])),
        nutrients_json=json.dumps(data.get('nutrients', {}))
    )

    
    # Process normalized ingredients
    ing_texts = data.get('ingredients', [])
    for text in ing_texts:
        ing_text_clean = text.strip().lower()
        if not ing_text_clean: continue
        
        ingredient = Ingredient.query.filter_by(raw_text=ing_text_clean).first()
        if not ingredient:
            ingredient = Ingredient(raw_text=ing_text_clean)
            db.session.add(ingredient)
        r.normalized_ingredients.append(ingredient)

    db.session.add(r)
    db.session.commit()
    return r

# ── Frontend ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("/frontend", "index.html")



# ── API────

@app.route("/api/scrape", methods=["POST"])
def scrape():
    """Scrapes a recipe and returns JSON, but DOES NOT save it."""
    body = request.get_json(silent=True)
    if not body or not body.get("url"):
        return jsonify({"success": False, "error": "Missing 'url' in request body."}), 400

    url = body["url"].strip()
    if not url.startswith(("http://", "https://")):
        return jsonify({"success": False, "error": "URL must start with http:// or https://"}), 400

    result = scrape_recipe(url)
    status_code = 200 if result.get("success") else 422
    return jsonify(result), status_code

@app.route("/api/recipes", methods=["GET"])
def list_recipes():
    """List all saved recipes from the database, grouped by category."""
    recipes = Recipe.query.order_by(Recipe.created_at.desc()).all()
    grouped = {
        "Breakfast": [],
        "Lunch": [],
        "Dinner": [],
        "Snacks": []
    }
    for r in recipes:
        cat = r.category if r.category in grouped else "Dinner"
        grouped[cat].append({
            "id": r.id,
            "title": r.title,
            "image": r.image,
            "total_time": r.total_time,
            "source_url": r.source_url
        })
    return jsonify({"success": True, "categories": grouped})

@app.route("/api/recipes/<int:recipe_id>", methods=["GET", "DELETE"])
def get_or_delete_recipe(recipe_id):
    r = Recipe.query.get(recipe_id)
    if not r:
        return jsonify({"success": False, "error": "Recipe not found"}), 404
        
    if request.method == "DELETE":
        db.session.delete(r)
        db.session.commit()
        return jsonify({"success": True})
        
    return jsonify({"success": True, "recipe": r.to_dict()})

@app.route("/api/recipes", methods=["POST"])
def save_recipe():
    """Takes a scraped recipe payload and saves it to the database."""
    body = request.get_json(silent=True)
    if not body or not body.get("source_url"):
        return jsonify({"success": False, "error": "Invalid full recipe payload."}), 400
    
    r = save_recipe_to_db(body)
    return jsonify({"success": True, "id": r.id, "message": "Saved successfully!"})

@app.route("/api/webhook", methods=["POST"])
def webhook():
    """
    Intended for iOS Shortcuts. 
    Accepts: { "url": "https://..." }
    Kicks off scrape synchronously and saves it to DB immediately.
    """
    body = request.get_json(silent=True) or {}
    url = body.get("url", "").strip()
    
    if not url:
        return jsonify({"success": False, "error": "Missing url."}), 400
        
    result = scrape_recipe(url)
    if not result.get("success"):
        return jsonify({"success": False, "error": result.get("error")}), 422
        
    r = save_recipe_to_db(result)
    return jsonify({"success": True, "id": r.id, "title": r.title, "message": "Scraped and saved!"})






@app.route("/api/pantry/suggest", methods=["GET"])
def pantry_suggest():
    import re
    q = request.args.get("q", "").lower().strip()
    if not q or len(q) < 2:
        return jsonify({"success": True, "suggestions": []})
        
    ings = Ingredient.query.filter(Ingredient.raw_text.like(f"%{q}%")).limit(100).all()
    suggestions = set()
    
    for ing in ings:
        try:
            parsed = parse_ingredient(ing.raw_text)
            if parsed.name:
                for obj in parsed.name:
                    if hasattr(obj, 'text'):
                        name_val = obj.text.lower()
                        words = re.findall(r'[a-z0-9-]+', name_val.lower())
                        clean_words = [w for w in words if w not in STOP_WORDS]
                        if not clean_words: continue
                        
                        phrase = " ".join(clean_words).strip()
                        phrase_sing = to_singular(phrase)
                        if q in phrase_sing and len(phrase_sing) > 2:
                            suggestions.add(phrase_sing)
        except:
            pass
                
    # Sort by length. The shortest word containing the query is usually the most generic.
    sug_list = sorted(list(suggestions), key=len)[:10]
    return jsonify({"success": True, "suggestions": sug_list})


@app.route("/api/pantry/cloud", methods=["GET"])
def pantry_cloud():
    cloud_frequencies = {}

    # Gather automated counts from recipes
    recipes_db = Recipe.query.all()
    for r in recipes_db:
        try:
            raw_ingredients = json.loads(r.ingredients_json)
        except:
            raw_ingredients = []
            
        for raw_ing in raw_ingredients:
            try:
                parsed = parse_ingredient(raw_ing)
                if parsed.name:
                    for obj in parsed.name:
                        if hasattr(obj, 'text'):
                            name_val = obj.text.lower()
                            # Clean stop words out of the parsed phrase (e.g. "fresh bay leaf" -> "bay leaf")
                            words = re.findall(r'[a-z0-9-]+', name_val.lower())
                            clean_words = [w for w in words if w not in STOP_WORDS]
                            if not clean_words: continue
                            
                            phrase = " ".join(clean_words).strip()
                            phrase_sing = to_singular(phrase)
                            
                            if len(phrase_sing) > 2:
                                cloud_frequencies[phrase_sing] = cloud_frequencies.get(phrase_sing, 0) + 1
            except Exception as e:
                pass

    # Gather manual search additions (> 5 limit constraint set by user)
    manual_searches = SearchWord.query.filter(SearchWord.count > 5).all()
    for ms in manual_searches:
        w_sing = to_singular(ms.word)
        # We inject it forcefully and give it an artificial boost so it bubbles to cloud
        cloud_frequencies[w_sing] = cloud_frequencies.get(w_sing, 0) + ms.count

    # Sort descending
    sorted_words = sorted(cloud_frequencies.keys(), key=lambda x: cloud_frequencies[x], reverse=True)
    
    # Take top 50
    top_50 = sorted_words[:50]
    
    return jsonify({"success": True, "cloud": top_50})

@app.route("/api/pantry/search", methods=["POST"])
def pantry_search():
    body = request.get_json(silent=True)
    if not body or not body.get("pantry"):
        return jsonify({"success": False, "error": "Missing pantry items array."}), 400
        
    
    pantry_items = [to_singular(p.lower().strip()) for p in body["pantry"] if p.strip()]
    
    # Log manual queries
    for item in pantry_items:
        sw = SearchWord.query.filter_by(word=item).first()
        if sw:
            sw.count += 1
        else:
            sw = SearchWord(word=item, count=1)
            db.session.add(sw)
    db.session.commit()

    
    recipes_db = Recipe.query.all()
    results = []
    
    for r in recipes_db:
        # Load raw ingredients
        try:
            raw_ingredients = json.loads(r.ingredients_json)
        except:
            raw_ingredients = []
            
        missing_count = 0
        missing_ingredients = []
        
        for raw_ing in raw_ingredients:
            raw_ing_clean = raw_ing.lower()
            found = False
            for p_item in pantry_items:
                if p_item in raw_ing_clean:
                    found = True
                    break
            
            if not found:
                missing_count += 1
                missing_ingredients.append(raw_ing)
                
        matched_count = len(raw_ingredients) - missing_count
        if matched_count > 0:
            results.append({
                "id": r.id,
                "title": r.title,
                "image": r.image,
                "total_time": r.total_time,
                "missing_count": missing_count,
                "missing_ingredients": missing_ingredients
            })
            
    # Sort from least missing to most missing
    results.sort(key=lambda x: x["missing_count"])
    
    return jsonify({"success": True, "results": results})

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


# ── Entry point ───────────────────────────────────────────────────────────────

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory("/frontend", path)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
