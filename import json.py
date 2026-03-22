import json
from datetime import date, timedelta

def generate_tesla_fremont_json():
    grid_data = {}
    today = date.today().isoformat()
    one_year_later = (date.today() + timedelta(days=365)).isoformat()

    # Tesla Fremont Parameters
    # Columns are usually every 4-5 bays in a real factory grid
    COLUMN_SPACING_X = 5 
    COLUMN_SPACING_Y = 5

    for x in range(60):
        for y in range(30):
            bay_id = f"B{x}_{y}"
            
            # 1. Place Structural Columns (Blocked permanently)
            if x % COLUMN_SPACING_X == 0 and y % COLUMN_SPACING_Y == 0:
                grid_data[bay_id] = {
                    "status": "Blocked",
                    "start": today,
                    "end": one_year_later,
                    "note": "Structural Column / Load Bearing"
                }
            
            # 2. Pre-plan the Main Assembly Line (Occupied)
            # A long horizontal stretch in the middle
            elif y == 15 and 10 < x < 50:
                grid_data[bay_id] = {
                    "status": "Occupied",
                    "start": today,
                    "end": one_year_later,
                    "note": "General Assembly Line 1"
                }

    with open("factory_grid.json", "w") as f:
        json.dump(grid_data, f, indent=2)
    print("Successfully generated tesla_fremont_grid.json!")

generate_tesla_fremont_json()