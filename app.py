from flask import Flask, request, render_template, redirect, url_for, session, flash
import requests

app = Flask(__name__)
app.secret_key = 'your_secret_key'

API_ID = 'e8d4c685'
API_KEY = '34127c26e678747edfe1c39e8046ba21'

def fetch_recipes(query, cook_time=None, meal_type=None, diet=None, cuisine=None, dishType=None):
    print("inside fetch recipes")
    print(query, cook_time, meal_type, diet)
    
    # Base URL for the Edamam API
    url = 'https://api.edamam.com/api/recipes/v2'
    
    # Parameters for the API request
    params = {
        'q': query,
        'app_id': API_ID,
        'app_key': API_KEY,
        'type': 'public', 
        'from': 0,
        'to': 4  # Limit results to 10 recipes
    }
    
    if cook_time:
        params['time'] = f"1-{cook_time}"
    if meal_type:
        params['mealType'] = meal_type
    #if diet:
    #    params['health'] = diet
    if cuisine:
        params['cuisineType'] = cuisine
    if dishType:
        params['dishType'] = dishType
    
    response = requests.get(url, params=params)
    
    try:
        data = response.json()
    except ValueError as e:
        # Log the error and return None or an empty list
        print(f"Error parsing JSON: {e}")
        return None

    # Add a debug print to inspect the data structure
    print("API response data:", data)

    return data

def extract_recipe_info(recipe):
    try:
        recipe_info = {
            'name': recipe['label'],
            'image': recipe.get('image', ''),
            'source': recipe.get('source', 'Unknown'),
            'url': recipe.get('url', '#'),
            'servings': recipe.get('yield', 'N/A'),
            'time': recipe.get('totalTime', 'N/A'),
            'dietLabels': recipe.get('dietLabels', []),
            'ingredients': recipe.get('ingredientLines', []),
            'nutritional_info': {
                'calories': recipe['totalNutrients'].get('ENERC_KCAL', {}).get('quantity', 'N/A'),
                'carbohydrates': recipe['totalNutrients'].get('CHOCDF', {}).get('quantity', 'N/A'),
                'protein': recipe['totalNutrients'].get('PROCNT', {}).get('quantity', 'N/A'),
                'fat': recipe['totalNutrients'].get('FAT', {}).get('quantity', 'N/A'),
            },
            'caution': recipe.get('cautions', [])
        }
    except KeyError as e:
        # Handle missing keys gracefully
        print(f"KeyError while extracting recipe info: {e}")
        recipe_info = {
            'name': 'Unknown',
            'image': '',
            'source': 'Unknown',
            'url': '#',
            'servings': 'N/A',
            'time': 'N/A',
            'dietLabels': [],
            'ingredients': [],
            'nutritional_info': {},
            'caution': []
        }
    return recipe_info

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        query = request.form.get('query')
        cook_time = request.form.get('cookTime')
        meal_type = request.form.get('mealType')
        diet = request.form.get('diet')
        cuisine = request.form.get('cuisineType')
        dishType = request.form.get('dishType')
        print("in index")
        print(query, cook_time, meal_type, diet, cuisine, dishType)

        if query:
            data = fetch_recipes(query, cook_time, meal_type, diet, cuisine, dishType)
            if data and 'hits' in data:
                recipes = [extract_recipe_info(hit['recipe']) for hit in data['hits'][:3]]
                session['recipes'] = recipes[:10]  # Limit to 10 recipes
                return redirect(url_for('recipes'))
            else:
                flash('No recipes found or an error occurred with the API.')
                return redirect(url_for('index'))
    
    return render_template('index.html')

@app.route('/get_recipes')
def recipes():
    recipes = session.get('recipes', [])
    return render_template('recipes.html', recipes=recipes)

if __name__ == '__main__':
    app.run(debug=True)
