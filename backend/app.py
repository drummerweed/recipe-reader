import os
import re
import json
from ingredient_parser import parse_ingredient
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from scraper import scrape_recipe
from database import db, Recipe, Ingredient, SearchWord
from urllib.parse import urlparse, urlunparse, parse_qsl

app = Flask(__name__, static_folder="/frontend", static_url_path="")
CORS(app)

# ── Helpers

def normalize_url(url):
    """Remove tracking parameters from URL for consistent database lookups."""
    if not url: return url
    parsed = urlparse(url)
    # List of common tracking parameters to remove
    tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'grow-social-pro', 'ref', 'source'}
    
    query = parse_qsl(parsed.query)
    clean_query = [(k, v) for k, v in query if k.lower() not in tracking_params]
    
    # Reconstruct URL without tracking params
    return urlunparse(parsed._replace(query="&".join([f"{k}={v}" for k, v in clean_query])))
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
    if "dinner" in text or "roast" in text or "casserole" in text or "pasta" in text or "pizza" in text or "steak" in text or "chicken" in text or "beef" in text or "pork" in text or "fish" in text:
        return "Dinner"

    # Default to Lunch
    return "Lunch"

def save_recipe_to_db(data):
    """Takes the scrape dict and saves it to DB, including normalizing ingredients."""
    source_url = normalize_url(data.get('source_url'))
    
    # Check if already exists by normalized URL
    existing = Recipe.query.filter_by(source_url=source_url).first()
    if existing:
        return existing

    title = data.get('title', 'Untitled Recipe')
    
    # Use provided category if present, else attempt to pull tags or guess
    category = data.get('category') or guess_category(title, "")


    def to_str(val):
        if not val: return None
        if isinstance(val, list): return ", ".join([str(v) for v in val])
        return str(val)

    r = Recipe(
        source_url=source_url,
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

    
    db.session.add(r)
    
    # Process normalized ingredients (deduplicated)
    ing_texts = data.get('ingredients', [])
    seen_ingredients = set()
    
    for text in ing_texts:
        ing_text_clean = text.strip().lower()
        if not ing_text_clean or ing_text_clean in seen_ingredients: 
            continue
        
        ingredient = Ingredient.query.filter_by(raw_text=ing_text_clean).first()
        if not ingredient:
            ingredient = Ingredient(raw_text=ing_text_clean)
            db.session.add(ingredient)
        
        # Now r is in session, appending works cleanly
        r.normalized_ingredients.append(ingredient)
        seen_ingredients.add(ing_text_clean)

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

    url = normalize_url(body["url"].strip())
    if not url.startswith(("http://", "https://")):
        return jsonify({"success": False, "error": "URL must start with http:// or https://"}), 400

    result = scrape_recipe(url)
    if result.get("success") and "title" in result:
        result["category"] = guess_category(result["title"], "")
    status_code = 200 if result.get("success") else 422
    return jsonify(result), status_code

@app.route("/api/recipes", methods=["GET"])
def list_recipes():
    """List all saved recipes from the database, grouped by category."""
    q = request.args.get("q", "").strip()
    
    if q:
        recipes = Recipe.query.filter(
            (Recipe.title.ilike(f"%{q}%")) | 
            (Recipe.ingredients_json.ilike(f"%{q}%"))
        ).order_by(Recipe.created_at.desc()).all()
    else:
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

@app.route("/api/recipes/<int:recipe_id>", methods=["GET", "DELETE", "PATCH"])
def get_or_delete_recipe(recipe_id):
    r = Recipe.query.get(recipe_id)
    if not r:
        return jsonify({"success": False, "error": "Recipe not found"}), 404
        
    if request.method == "DELETE":
        db.session.delete(r)
        db.session.commit()
        return jsonify({"success": True})
        
    if request.method == "PATCH":
        body = request.get_json(silent=True) or {}
        if "category" in body:
            r.category = body["category"]
            db.session.commit()
        return jsonify({"success": True, "recipe": r.to_dict()})
        
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
    url = normalize_url(body.get("url", "").strip())
    
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
        
    ings = Ingredient.query.filter(Ingredient.raw_text.ilike(f"%{q}%")).limit(50).all()
    suggestions = set()
    
    for ing in ings:
        # Each ing.raw_text is something like "2 cups all-purpose flour"
        # Instead of parsing everything, let's just look for the query word 
        # but try to keep it meaningful. 
        # We can use a simpler regex for suggestion variety if parsing is too slow.
        try:
            parsed = parse_ingredient(ing.raw_text)
            if parsed.name:
                for obj in parsed.name:
                    if hasattr(obj, 'text'):
                        name_val = obj.text.lower()
                        # Tokenize and filter
                        words = re.findall(r'[a-z0-9-]+', name_val)
                        clean_words = [w for w in words if w not in STOP_WORDS]
                        if not clean_words: continue
                        
                        phrase = " ".join(clean_words).strip()
                        phrase_sing = to_singular(phrase)
                        if q in phrase_sing and len(phrase_sing) > 2:
                            suggestions.add(phrase_sing)
        except:
            pass
                
    # Sort by length and return top 10
    sug_list = sorted(list(suggestions), key=len)[:10]
    return jsonify({"success": True, "suggestions": sug_list})


@app.route("/api/pantry/cloud", methods=["GET"])
def pantry_cloud():
    cloud_frequencies = {}

    # Use already normalized ingredients from the database
    # This is 100x faster than re-parsing everything on every request
    all_ingredients = Ingredient.query.all()
    for ing in all_ingredients:
        try:
            # Check how many recipes use this ingredient
            usage_count = len(ing.recipes)
            if usage_count == 0: continue

            parsed = parse_ingredient(ing.raw_text)
            if parsed.name:
                for obj in parsed.name:
                    if hasattr(obj, 'text'):
                        name_val = obj.text.lower()
                        words = re.findall(r'[a-z0-9-]+', name_val)
                        clean_words = [w for w in words if w not in STOP_WORDS]
                        if not clean_words: continue
                        
                        phrase = " ".join(clean_words).strip()
                        phrase_sing = to_singular(phrase)
                        
                        if len(phrase_sing) > 2:
                            cloud_frequencies[phrase_sing] = cloud_frequencies.get(phrase_sing, 0) + usage_count
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
    
    # Pre-tokenize pantry items for faster matching
    pantry_token_sets = []
    for item in pantry_items:
        tokens = set(re.findall(r'[a-z0-9-]+', item))
        if tokens:
            pantry_token_sets.append(tokens)

    # Log manual queries
    for item in pantry_items:
        try:
            sw = SearchWord.query.filter_by(word=item).first()
            if sw:
                sw.count += 1
            else:
                sw = SearchWord(word=item, count=1)
                db.session.add(sw)
        except:
            pass
    db.session.commit()

    recipes_db = Recipe.query.all()
    results = []
    
    for r in recipes_db:
        try:
            raw_ingredients = json.loads(r.ingredients_json)
        except:
            raw_ingredients = []
            
        missing_count = 0
        missing_ingredients = []
        matched_ingredients_count = 0
        
        for raw_ing in raw_ingredients:
            raw_ing_clean = raw_ing.lower()
            ing_tokens = set(re.findall(r'[a-z0-9-]+', raw_ing_clean))
            
            found = False
            for p_tokens in pantry_token_sets:
                # Check if ALL tokens of a pantry item are present in the ingredient
                # e.g. if pantry has {"garlic", "powder"}, does the ingredient have both?
                if p_tokens.issubset(ing_tokens):
                    found = True
                    break
                # Fallback to simple substring for edge cases (like "all-purpose")
                p_phrase = " ".join(p_tokens)
                if p_phrase in raw_ing_clean:
                    found = True
                    break
            
            if found:
                matched_ingredients_count += 1
            else:
                missing_count += 1
                missing_ingredients.append(raw_ing)
                
        if matched_ingredients_count > 0:
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
