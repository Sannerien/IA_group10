import json
from owlready2 import *
from pprint import pprint
import numpy as np
import operator


class RecommendationState:

    def __init__(self, activity=[], transportation=[], restaurant=[], food=[], clothing_store=[], clothing_item=[],
                 time_of_activity=[]):
        self.activity = activity
        self.transportation = transportation
        self.restaurant = restaurant
        self.food = food
        self.clothing_store = clothing_store
        self.clothing_item = clothing_item
        self.time_of_activity = time_of_activity

    def calculate_utility(self, strict_prefs, loose_prefs, CO2_scores_per_domain, n_domains, completed_pref=0):
        utility = 0
        x = len(set(loose_prefs)) + len(set(strict_prefs))
        if x == 0:
            percent_match = 1
        else:
            # by intersecting their set with users's prefs set
            percent_match = np.divide(int(completed_pref), int(x))
        # print("percent match is {}".format(percent_match))
        # we calculate the score; CO2 value is summed over the list
        utility = (percent_match * n_domains) / sum(CO2_scores_per_domain)

        return utility



class Agent:
    def __init__(self, path):
        # Load the desired ontology using the path file
        self.ontology = get_ontology(path)
        self.ontology.load()
        self.recommendations = []
        self.query = []
        self.rushhour = False
        self.graph = default_world.as_rdflib_graph()

        # Run the reasoner to obtain the inferences;
        with self.ontology:
            sync_reasoner(infer_property_values=True)

        # Additional
        print(self.ontology.name)
        print("IA Ontology".startswith(self.ontology.name))
        for i in self.ontology.classes():
            print(i, len(i.label))
        # Reference dictionaries between IRIs and given labels that might be useful
        self.label_to_class = {ent.label[0]: ent for ent in self.ontology.classes() if len(ent.label) > 0}
        self.label_to_prop = {prop.label[0]: prop for prop in self.ontology.properties() if len(prop.label) > 0}
        self.individuals = []
        for c in self.ontology.classes():
            for indiv in c.instances():
                self.individuals.append(indiv)
        self.label_to_indiv = {ent.label[0]: ent for ent in self.individuals if len(ent.label) > 0}

        self.class_to_label = {ent: ent.label[0] for ent in self.ontology.classes() if len(ent.label) > 0}
        self.prop_to_label = {prop: prop.label[0] for prop in self.ontology.properties() if len(prop.label) > 0}

        # Save types to help differentiate between classes and properties later on
        self.class_type = type(list(self.ontology.classes())[0])
        self.property_type = type(list(self.ontology.properties())[0])

    def sanity_check(self):
        # Base iri of the ontology
        print("Ontology name:\n{}".format(self.ontology.base_iri))
        # Count number of different classes and properties
        print("# of classes: {}".format(len(list(self.ontology.classes()))))
        print("# of properties: {}".format(len(list(self.ontology.properties()))))
        # Display the labels (the names given in Protege) of all the classes & properties present in the ontology
        pprint(self.label_to_class)
        pprint(self.label_to_prop)

    def infer_health_cond(self, symptoms, user):
        symptom_instances = []
        user = self.label_to_indiv[user]
        health_conditions = list(user.hasHealthCondition)
        if len(symptoms) > 0:
            for symptom in symptoms:
                symptom_instances.append(self.label_to_indiv[symptom])
            results = list(self.ontology.search(hasSymptom=symptom_instances))
            return list(set(health_conditions + results))
        else:
            return health_conditions

    def infer_recipes_for_cuisines(self, preferred_recipes, cuisines):
        cuisine_meals = []
        if len(cuisines) > 0:
            for cuisine in cuisines:
                cuisine_meals = list(set(cuisine_meals + self.label_to_indiv[cuisine].containsMeal))
            return preferred_recipes & cuisine_meals
        return preferred_recipes

    def filter_restaurants_on_location(self, pref_locations, restaurants):
        restaurants_in_pref_locations = []
        if len(restaurants) > 0 and len(pref_locations) > 0:
            for restaurant in restaurants:
                for location in pref_locations:
                    if self.label_to_indiv[location] in list(
                            restaurant.isLocatedIn) and restaurant not in restaurants_in_pref_locations:
                        restaurants_in_pref_locations.append(restaurant)
            return restaurants_in_pref_locations
        else:
            return restaurants

    def infer_forbidden_ingredients(self, health_conditions):
        list_forbidden_ingredients = []
        if len(health_conditions) > 0:
            for health_cond in health_conditions:
                forbidden_ingredients = list(self.ontology.search(isForbiddenBy=health_cond))
                list_forbidden_ingredients = list(set(list_forbidden_ingredients + forbidden_ingredients))
        return list_forbidden_ingredients

    def infer_restaurants(self, recipes):
        restaurants = {}
        if len(recipes) > 0:
            for recipe in recipes:
                possible_restaurants = list(self.ontology.search(serves=recipe))
                restaurants[recipe] = list(possible_restaurants)
        else:
            restaurants = self.ontology.Restaurant.instances()
        return restaurants

    def get_user_location(self, current_location, user):
        if current_location:
            return self.label_to_indiv[current_location]
        else:
            return self.label_to_indiv[user].livesIn[0]

    def check_user_transport_options(self, owned_transport, current_neighborhood):
        available_transport = []
        for vehicle in owned_transport:
            extra_travel_time = 0
            if vehicle.isLocatedIn[0] in list(current_neighborhood.adjacentTo) or \
                    vehicle.isLocatedIn[0] == current_neighborhood:
                if vehicle.is_a[0] == self.ontology.ElectricCar:  # Check if electric battery is charged
                    if not vehicle.isBatteryCharged[0]:
                        extra_travel_time = int(vehicle.timeToChargeElectricCar[0])
                available_transport.append([vehicle, extra_travel_time])
        return available_transport

    def determine_travel_options(self, current_location, destinations, user):
        city = current_location.isLocatedIn[0]
        owned_transport = list(self.label_to_indiv[user].owns)
        available_transport = self.check_user_transport_options(owned_transport, current_location)
        destination_dict = {}

        for destination in destinations:
            destination_dict[destination] = available_transport
            destination_neighborhood = destination.isLocatedIn[0]
            if city == destination.isLocatedIn[1]:  # Check if current location is in the same city as the destination
                if current_location in list(destination_neighborhood.adjacentTo) or \
                        current_location == destination_neighborhood:  # check if neighborhoods adjacent
                    if current_location in list(destination_neighborhood.adjacentTo):
                        for i in destination_dict[destination]:
                            if i[0].is_a[0] == self.ontology.Bike:
                                i[1] += 10
                            if i[0].is_a[0] == self.ontology.Car:
                                i[1] += 5
                        destination_dict[destination].append(['Walk', 30])
                    else:
                        for i in destination_dict[destination]:
                            if i[0].is_a[0] == self.ontology.Bike:
                                i[1] += 5
                            if i[0].is_a[0] == self.ontology.Car:
                                i[1] += 2
                        destination_dict[destination].append(['Walk', 10])
                else:  # neighborhoods not adjacent
                    for i in destination_dict[destination]:
                        if i[0].is_a[0] == self.ontology.Bike:
                            i[1] += 15
                        if i[0].is_a[0] == self.ontology.Car:
                            i[1] += 15
                        destination_dict[destination].append(['Public Transport', 15])

            else:  # Not in the same city
                for i in destination_dict[destination]: # Can no longer bike to destination
                    if i[0].is_a[0] == self.ontology.Bike:
                        destination_dict[destination].remove(i)
                if city == self.ontology.Amsterdam and destination.isLocatedIn[1] == self.ontology.Utrecht:
                    train = self.ontology.TrainFromAmsterdamToUtrecht
                else:
                    train = self.ontology.TrainFromUtrechtToAmsterdam
                public_transport_time = 27  # Duration of train in minutes
                extra_co2score = 0 # If user has to take a tram or a bus in the other city, CO2 score becomes worse
                if current_location.hasPopulation[0] > 20000:  # Check if current neighborhood has train station
                    public_transport_time += 5  # User needs to walk about 5 minutes
                else:
                    if self.ontology.Bike in destination_dict[destination]:  # Check if user has bike
                        for i in destination_dict[destination]:
                            if i[0] == self.ontology.Bike:
                                public_transport_time += int(i[0].travelTimeToNearestTrainStation[0])
                if destination_neighborhood.hasPopulation[0] > 20000:  # Check if destination neighborhood
                    # has train station
                    public_transport_time += 5
                else:  # User needs to use public transport (bus/tram) to get to destination
                    public_transport_time += 15
                    extra_co2score += 1
                destination_dict[destination].append([train, public_transport_time, extra_co2score])
                for i in destination_dict[destination]:
                    if i[0].is_a[0] == self.ontology.Car:
                        i[1] += 55
        return destination_dict

    def infer_recipes(self, cuisines, pref_food, health_cond):
        # Find what recipes aren't allowed due to health conditions
        health_prevented_ingredients = self.infer_forbidden_ingredients(health_cond)
        health_prevented_recipes = []
        for ingredient in health_prevented_ingredients:
            health_prevented_recipes = list(
                set(health_prevented_recipes + list(self.ontology.search(containsIngredient=ingredient))))


        # Keep track of all recipes and initialize logic operators
        all_recipes = []
        recipes = self.ontology.search(label="Recipe")
        for c in recipes:
            for i in c.instances():
                all_recipes.append(i)
        food_list = all_recipes
        union = False
        or_found = False
        negation = False

        # Search in ontology based on preferred food and ingredients
        for food in pref_food:
            containsIngredient = False
            some_clause = False
            for word in food.split(' '):
                if word == 'not':
                    negation = True
                elif word == 'ingredient':
                    containsIngredient = True
                elif word == 'some':
                    some_clause = True
                elif word == 'or':
                    or_found = True
                    union = True
                    break
                else:
                    if containsIngredient:
                        if some_clause:
                            found_ingredients = list(self.label_to_class[word].instances())
                            found_recipes = []
                            for ingredient in found_ingredients:
                                found_recipes = list(
                                    set(found_recipes + list(self.ontology.search(containsIngredient=ingredient))))
                        else:
                            found_recipes = list(self.ontology.search(containsIngredient=self.label_to_indiv[word]))
                    elif some_clause:
                        found_recipes = list(self.label_to_class[word].instances())
                        some_clause = False
                    else:
                        found_recipes = list(self.ontology.search(self.label_to_class[word]))
            if negation:
                if union:
                    included_food = list(set(all_recipes) - set(found_recipes))
                    food_list = list(set(food_list + included_food))
                    union = False
                else:
                    food_list = list(set(food_list) - set(found_recipes))
                negation = False
                continue
            if union:
                food_list = list(set(food_list + found_recipes))
                if or_found:
                    or_found = False
                    continue
                union = False
            else:
                food_list = list(set(food_list) & set(found_recipes))
            print(food_list)

        preferred_recipes = list(set(food_list) - set(health_prevented_recipes))

        prefered_recipes_cuisines = self.infer_recipes_for_cuisines(preferred_recipes, cuisines)
        print('Recipes found based on preferences and health conditions: ', preferred_recipes)
        print('Recipes that match cuisine preferences: ', prefered_recipes_cuisines, '\n')

        recipe_with_restaurants = self.infer_restaurants(preferred_recipes)
        recipes_restaurants_cuisines = self.infer_restaurants(prefered_recipes_cuisines)
        recipes_restaurants_by_cuisines_loc = {}
        recipe_with_restaurants_by_loc ={}
        # recipe_with_restaurants = self.infer_restaurants(preferred_recipes)
        for recipe, restaurants in recipe_with_restaurants.items():
            print('Ignoring the cuisine wishes, found the following restaurants that serve:', recipe.label[0])
            print(restaurants)
            recipe_with_restaurants_by_loc[recipe] = self.filter_restaurants_on_location(preferences['pref_location'], restaurants)
            print('Of these restaurants, the following are available in',preferences['pref_location'][0])
            print(recipe_with_restaurants_by_loc[recipe],'\n')

        for recipe, restaurants in recipes_restaurants_cuisines.items():
            print('Found the following', preferences['pref_cuisines'],'restaurants that serve:', recipe.label[0])
            print(restaurants)
            recipes_restaurants_by_cuisines_loc[recipe] = self.filter_restaurants_on_location(preferences['pref_location'], restaurants)
            print('Of these restaurants, the following are available in',preferences['pref_location'][0])
            print(recipes_restaurants_by_cuisines_loc[recipe],'\n')
        return recipe_with_restaurants, recipe_with_restaurants_by_loc, recipes_restaurants_cuisines, recipes_restaurants_by_cuisines_loc

    def simple_queries(self):
        print("Query responses:")

        # Get all the classes with the label ending in "_topping"
        results = self.ontology.search(label="Transportation")
        class_results = [self.class_to_label[result] for result in results if type(result) == self.class_type]
        pprint(class_results)

        print("-" * 75)

        # Get all the classes that have "Vegetarian" as a superclass
        results2 = self.ontology.search(subclass_of=self.ontology.search_one(label="Public Transportation"))
        subclasses = [self.class_to_label[result] for result in results2 if type(result) == self.class_type]
        pprint(subclasses)

        print("-" * 75)

        # Get all the classes with a label containing "Pizza"
        results = self.ontology.search(label="Recipe")
        class_results = [self.class_to_label[result] for result in results if type(result) == self.class_type]

        for c in results:
            for i in c.instances():
                pprint(i)

        for c in results:
            for i in c.instances():
                for prop in i.get_properties():
                    for value in prop[i]:
                        print(".%s == %s" % (prop.python_name, value))
                    # pprint(p)
            # pprint(list(c.instances()))

        results2 = self.ontology.search(label="Ingredient")
        for c in results2:
            pprint(list(c.instances()))

        pprint(class_results)

        print("-" * 75)

        # Get all the properties with a label containing "has"
        results = self.ontology.search(label="*has*")
        class_results = [self.prop_to_label[result] for result in results if type(result) == self.property_type]
        pprint(class_results)

    def find_options(self, preferences):

        options = []

        if "Activity" in preferences["activity"]:
            selected_energy = {}
            if self.rushhour:
                energy = self.ontology.search(label="Unsustainable Energy")
                selected_energy = energy[0].instances()

            else:
                energy = self.ontology.search(label="Energy")
                selected_energy = []
                for i in energy[0].instances():
                    for prop in i.get_properties():
                        if prop.python_name == "requiresWeather":
                            for value in prop[i]:
                                for weather in preferences["weather_condition"]:
                                    if str(value).endswith(weather):
                                        selected_energy = i
            # options_domains["Energy"] = selected_energy

            possible_activities = self.ontology.search(label="Activity")
            selected_activities = possible_activities[0].instances()

            options = [[x, y] for x in selected_activities for y in selected_energy]
        if "Restaurant" in preferences["activity"]:
            current_location = agent.get_user_location(preferences['current_location'], preferences['user'])
            health_conditions = agent.infer_health_cond(preferences['symptoms'], preferences['user'])
            restaurants, restaurants_by_loc, restaurants_cuisines, restaurants_by_cuisines_loc = \
                agent.infer_recipes(preferences['pref_cuisines'], preferences['pref_food'], health_conditions)

            if agent.ontology.COVID in health_conditions:  # Agent believes user has COVID
                print('From either your specified health conditions or inferred through your symptoms, '
                      'it has been concluded that you might have COVID-19.\n'
                      'Therefore the agent recommends not travelling and staying inside.')
                return
            if len(restaurants_by_cuisines_loc) == 0:
                print('Unfortunately, no restaurants were found in that location. '
                      'The agent will recommend other restaurants which are not located in your specified location.\n')
                agent.create_recommendations(restaurants_cuisines, current_location)
            else:
                options = agent.create_recommendations(restaurants_by_cuisines_loc, current_location)
        return options

    def check_preferences(self, preference):
        preference["strict_prefs"]

    def choose_actions(self, options):
        recommender = RecommendationState()
        d = {}

        for idx, option in enumerate(options):
            CO2_scores_per_domain = [item.hasCO2score[0] for item in option]
            len_domain = len(option)
            # completed_pref = self.check_preferences(preferences)
            utility = recommender.calculate_utility(preferences["strict_prefs"], preferences["loose_prefs"],
                                                    CO2_scores_per_domain, len_domain)
            d[(option[0].name, option[0].name)] = utility
        sorted_options = dict(sorted(d.items(), key=operator.itemgetter(1), reverse=True))
        return sorted_options

    def explain_actions(self, preferences, sorted_options, options):
        print("Dear", preferences["user"])
        x = list(list(sorted_options.keys())[0])[0]
        print(
            'The first advise for selection of {} would be {} with utility score {}.'.format(preferences["activity"][0],
                                                                                             x, list(
                    sorted_options.values())[0]))

        if preferences["time_of_activity"] >= 20 and "Activity" in preferences["activity"]:
            self.rushhour = True
            sorted_options = self.choose_actions(options)
            print("An alternative option is to wait {} hour. In that case another option would be {}".format(
                21 - preferences["time_of_activity"], list(list(sorted_options.keys())[1])[0]))

    def find_preferences(self, preferences):
        self.rushhour = preferences["time_of_activity"] > 16 and preferences["time_of_activity"] < 22
        options = self.find_options(preferences)
        sorted_options = self.choose_actions(options)
        self.explain_actions(preferences, sorted_options, options)

    def create_recommendations(self, recipe_restaurants, current_location):
        recommendations = []
        for recipe, restaurants in recipe_restaurants.items():
            CO2_scores_per_domain = []
            CO2_scores_per_domain.append(recipe.hasCO2score[0])
            travel_options = agent.determine_travel_options(current_location, restaurants,
                                                            preferences['user'])
            for restaurant, travel_options in travel_options.items():
                for travel_option in travel_options:
                    del CO2_scores_per_domain[1:]
                    if travel_option[0] == 'Walk':
                        CO2_scores_per_domain.append(1)
                    if len(travel_option) == 3:
                        CO2_scores_per_domain.append(travel_option[0].hasCO2score[0] + travel_option[2])
                    else:
                        CO2_scores_per_domain.append(travel_option[0].hasCO2score[0])
                    n_domains = len(CO2_scores_per_domain)
                    recommendation = RecommendationState('Restaurant', travel_option[0], restaurant, recipe, [],
                                                         [], preferences['time_of_activity'])
                    utility = recommendation.calculate_utility(preferences["strict_prefs"], preferences["loose_prefs"],
                                                        CO2_scores_per_domain, n_domains)
                    recommendations.append([recommendation,utility])
        recommendations.sort(key=lambda x: x[1], reverse=True)
        return recommendations

if __name__ == "__main__":
    with open('./Users/sophie.json', 'r') as openfile:
        # Reading from json file
        preferences = json.load(openfile)
    agent = Agent("IAG_Group10_Ontology.owl")
    agent.sanity_check()
    options = agent.find_options(preferences)
