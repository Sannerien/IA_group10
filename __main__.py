import json


class RecommendationState:

    def __init__(self, activity, transportation, restaurant, food, clothing_store, clothing_item, time_of_activity):
        activity = activity
        transportation = transportation
        restaurant = restaurant
        food = food
        clothing_store = clothing_store
        clothing_item = clothing_item
        time_of_activity = time_of_activity


if __name__ == "__main__":
    with open('sophie.json', 'r') as openfile:
        # Reading from json file
        preferences = json.load(openfile)
    print(preferences)
