from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

# Join table for many-to-many relationship
recipe_ingredients = db.Table('recipe_ingredients',
    db.Column('recipe_id', db.Integer, db.ForeignKey('recipes.id'), primary_key=True),
    db.Column('ingredient_id', db.Integer, db.ForeignKey('ingredients.id'), primary_key=True)
)

class Recipe(db.Model):
    __tablename__ = 'recipes'
    
    id = db.Column(db.Integer, primary_key=True)
    source_url = db.Column(db.String(1000), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    image = db.Column(db.String(1000), nullable=True)
    category = db.Column(db.String(50), nullable=False, default='Dinner') # Breakfast, Lunch, Dinner, Snacks
    
    # Meta
    yields = db.Column(db.String(100), nullable=True)
    prep_time = db.Column(db.String(100), nullable=True)
    cook_time = db.Column(db.String(100), nullable=True)
    total_time = db.Column(db.String(100), nullable=True)
    
    # Store the exact scraped strings for UI display
    ingredients_json = db.Column(db.Text, nullable=False, default="[]") 
    instructions_json = db.Column(db.Text, nullable=False, default="[]")
    nutrients_json = db.Column(db.Text, nullable=False, default="{}")
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Many-to-many relationship mapping this recipe to normalized ingredient items
    normalized_ingredients = db.relationship('Ingredient', secondary=recipe_ingredients, lazy='subquery',
        backref=db.backref('recipes', lazy=True))

    def to_dict(self):
        try:
            ings = json.loads(self.ingredients_json)
        except:
            ings = []
        try:
            insts = json.loads(self.instructions_json)
        except:
            insts = []
        try:
            nuts = json.loads(self.nutrients_json)
        except:
            nuts = {}
            
        return {
            "id": self.id,
            "source_url": self.source_url,
            "title": self.title,
            "image": self.image,
            "category": self.category,
            "yields": self.yields,
            "prep_time": self.prep_time,
            "cook_time": self.cook_time,
            "total_time": self.total_time,
            "ingredients": ings,
            "instructions": insts,
            "nutrients": nuts,
            "created_at": self.created_at.isoformat()
        }

class Ingredient(db.Model):
    __tablename__ = 'ingredients'
    
    id = db.Column(db.Integer, primary_key=True)
    raw_text = db.Column(db.String(500), nullable=False, unique=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "raw_text": self.raw_text
        }


class SearchWord(db.Model):
    __tablename__ = 'search_words'
    id = db.Column(db.Integer, primary_key=True)
    word = db.Column(db.String(100), nullable=False, unique=True)
    count = db.Column(db.Integer, default=1)
