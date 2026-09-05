from uuid import uuid4

from flask import Flask, request, render_template, redirect, url_for, session, flash
import requests

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# TheMealDB free/test API. "1" is the public developer key.
API_BASE = 'https://www.themealdb.com/api/json/v1/1'

# Max recipes to show (each filtered result needs its own lookup call).
MAX_RECIPES = 6

# Results are kept server-side; the session only holds a short token so the
# cookie never overflows with full instructions/ingredients.
RECIPE_CACHE = {}

# Maps each cuisine option in the form to the TheMealDB "area" values worth
# trying. The dataset is mid-migration and mixes demonyms ("Italian") with
# country names ("India", "United States"), so we try every candidate and
# merge the results.
CUISINE_TO_AREAS = {
    'American': ['American', 'United States'],
    'British': ['British', 'United Kingdom'],
    'Canadian': ['Canadian', 'Canada'],
    'Chinese': ['Chinese', 'China'],
    'Croatian': ['Croatian', 'Croatia'],
    'Dutch': ['Dutch', 'Netherlands'],
    'Egyptian': ['Egyptian', 'Egypt'],
    'French': ['French', 'France'],
    'Greek': ['Greek', 'Greece'],
    'Indian': ['Indian', 'India'],
    'Irish': ['Irish', 'Ireland'],
    'Italian': ['Italian', 'Italy'],
    'Jamaican': ['Jamaican', 'Jamaica'],
    'Japanese': ['Japanese', 'Japan'],
    'Mexican': ['Mexican', 'Mexico'],
    'Moroccan': ['Moroccan', 'Morocco'],
    'Polish': ['Polish', 'Poland'],
    'Portuguese': ['Portuguese', 'Portugal'],
    'Russian': ['Russian', 'Russia'],
    'Spanish': ['Spanish', 'Spain'],
    'Thai': ['Thai', 'Thailand'],
    'Turkish': ['Turkish', 'Turkey'],
    'Vietnamese': ['Vietnamese', 'Vietnam'],
}


def _get(endpoint, params):
    """Call TheMealDB and return the parsed JSON, or None on failure."""
    try:
        response = requests.get(f'{API_BASE}/{endpoint}', params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as e:
        print(f'TheMealDB request failed ({endpoint} {params}): {e}')
        return None


def _lookup(meal_id):
    """Fetch the full meal record for an id returned by a filter call."""
    data = _get('lookup.php', {'i': meal_id})
    meals = (data or {}).get('meals') or []
    return meals[0] if meals else None


def _lookup_stubs(stubs):
    """Turn filter.php stubs into full meal records, de-duplicated by id."""
    meals = []
    seen = set()
    for stub in stubs:
        meal_id = stub.get('idMeal')
        if not meal_id or meal_id in seen:
            continue
        seen.add(meal_id)
        meal = _lookup(meal_id)
        if meal:
            meals.append(meal)
        if len(meals) >= MAX_RECIPES:
            break
    return meals


def _matches_area(meal, areas):
    """Loose area match against both strArea and strCountry."""
    haystack = f"{meal.get('strArea') or ''} {meal.get('strCountry') or ''}".lower()
    return any(a.lower() in haystack for a in areas)


def fetch_recipes(query, areas=None, category=None):
    """Return a list of full meal dicts from TheMealDB.

    TheMealDB can only filter on one field per call, so:
      * a text query is searched as a meal name, then falls back to a
        main-ingredient filter;
      * with no query we filter by area or category directly;
      * any remaining area/category selection is applied in Python.
    """
    print('fetch_recipes', query, areas, category)
    areas = areas or []
    meals = []

    if query:
        by_name = _get('search.php', {'s': query})
        meals = (by_name or {}).get('meals') or []

        if not meals:
            ingredient = query.strip().replace(' ', '_')
            by_ingredient = _get('filter.php', {'i': ingredient})
            meals = _lookup_stubs((by_ingredient or {}).get('meals') or [])
    elif areas:
        stubs = []
        for area in areas:
            data = _get('filter.php', {'a': area})
            stubs.extend((data or {}).get('meals') or [])
        meals = _lookup_stubs(stubs)
    elif category:
        by_category = _get('filter.php', {'c': category})
        meals = _lookup_stubs((by_category or {}).get('meals') or [])
    else:
        return []

    if areas:
        meals = [m for m in meals if _matches_area(m, areas)]
    if category:
        meals = [m for m in meals if (m.get('strCategory') or '').lower() == category.lower()]

    return meals[:MAX_RECIPES]


def extract_recipe_info(meal):
    """Flatten a TheMealDB meal into the shape the template expects."""
    ingredients = []
    for i in range(1, 21):
        name = (meal.get(f'strIngredient{i}') or '').strip()
        measure = (meal.get(f'strMeasure{i}') or '').strip()
        if name:
            ingredients.append(f'{measure} {name}'.strip())

    tags = [t.strip() for t in (meal.get('strTags') or '').split(',') if t.strip()]

    instructions = meal.get('strInstructions') or ''
    steps = [s.strip() for s in instructions.replace('\r\n', '\n').split('\n') if s.strip()]

    source = meal.get('strSource') or meal.get('strYoutube') or meal.get('strMealThumb') or '#'

    return {
        'id': meal.get('idMeal'),
        'name': meal.get('strMeal', 'Unknown'),
        'image': meal.get('strMealThumb', ''),
        'category': meal.get('strCategory', 'N/A'),
        'area': meal.get('strArea', 'N/A'),
        'tags': tags,
        'ingredients': ingredients,
        'steps': steps,
        'youtube': meal.get('strYoutube', ''),
        'source': source,
        'url': source,
    }


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        query = (request.form.get('query') or '').strip()
        cuisine = request.form.get('cuisineType') or ''
        category = request.form.get('category') or ''

        areas = CUISINE_TO_AREAS.get(cuisine, [])

        if not (query or areas or category):
            flash('Enter an ingredient or dish name, or pick a cuisine or category.')
            return redirect(url_for('index'))

        meals = fetch_recipes(query, areas=areas, category=category)
        if not meals:
            flash('No recipes found. Try a different ingredient, dish, or filter.')
            return redirect(url_for('index'))

        token = uuid4().hex
        RECIPE_CACHE[token] = [extract_recipe_info(m) for m in meals]
        session['recipes_token'] = token
        return redirect(url_for('recipes'))

    return render_template('index.html')


@app.route('/get_recipes')
def recipes():
    token = session.get('recipes_token')
    recipes = RECIPE_CACHE.get(token, [])
    return render_template('recipes.html', recipes=recipes)


if __name__ == '__main__':
    app.run(debug=True)
