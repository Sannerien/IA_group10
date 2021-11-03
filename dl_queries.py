import json
from owlready2 import *
from pprint import pprint
import numpy as np
import operator
import random_agent
import random


def count_upper_case_letters(str_obj):
    count = 0
    for elem in str_obj:
        if elem.isupper():
            count += 1
    return count


class RecommendationState:

    def __init__(self, activity=[], transportation=[], restaurant=[], food=[], clothing_store=[], clothing_item=[],
                 time_of_activity=[], pref_not_adhered_to=[], charging_spot='', energy=[]):
        self.activity = activity
        self.transportation = transportation
        self.restaurant = restaurant
        self.food = food
        self.clothing_store = clothing_store
        self.clothing_item = clothing_item
        self.time_of_activity = time_of_activity
        self.pref_not_adhered_to = pref_not_adhered_to
        self.duration = 0
        self.charging_spot = charging_spot
        self.energy = energy

    def calculate_utility(self, per_loose_prefs, CO2_scores_per_domain, n_domains):
        utility = (per_loose_prefs * n_domains) / sum(CO2_scores_per_domain)

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
        self.charging_spot = ''

        # Run the reasoner to obtain the inferences;
        with self.ontology:
            sync_reasoner(infer_property_values=True, debug=0)

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

    def infer_stores(self, items):
        stores = {}
        if len(items) > 0:
            for item in items:
                possible_stores = list(self.ontology.search(selling=item))
                stores[item] = list(possible_stores) if possible_stores else ['Online store']
                # print(stores[item])
        return stores

    def filter_stores_on_location(self, pref_locations, stores):
        stores_in_pref_locations = []
        if 'Online store' in stores:
            stores.remove('Online store')
        if len(stores) > 0:  # and 'Online store' not in stores:
            if len(pref_locations) > 0:
                for store in stores:
                    for location in pref_locations:
                        if self.label_to_indiv[location] in list(
                                store.isLocatedIn) and store not in stores_in_pref_locations:
                            stores_in_pref_locations.append(store)
                        else: 
                            stores_in_pref_locations.append('Online store only')
                return stores_in_pref_locations
            else:
                return stores
        else:
            stores = ['Online store only']
            return stores

    def infer_clothes(self, pref_clothing, health_cond):
        health_prevented_materials = self.infer_forbidden_ingredients(health_cond)
        health_prevented_clothing = []
        for material in health_prevented_materials:
            health_prevented_clothing = list(
                set(health_prevented_clothing + list(self.ontology.search(containsMaterial=material))))
        # print("Prevented by health problems: ", health_prevented_clothing)

        all_clothing = []
        clothing = self.ontology.search(label="Clothing")
        for c in clothing:
            for i in c.instances():
                all_clothing.append(i)

        clothing_list = all_clothing

        maxprice = 0
        price = False
        fairness = False
        union = False
        or_found = False
        negation = False

        # print("All clothing items from ontology: ", all_clothing)
        # print("Clothing preferences for user: ", pref_clothing)

        for pref in pref_clothing:
            # print(pref)
            containsMaterial = False
            some_clause = False
            for word in pref.split(' '):
                if word == 'not':
                    negation = True
                elif word == 'material':
                    containsMaterial = True
                elif word == 'some':
                    some_clause = True
                elif word == 'maxprice':
                    price = True
                elif word == "isFairTrade":
                    fairness = True
                elif word == 'or':
                    or_found = True
                    union = True
                    break
                else:
                    if containsMaterial:
                        if some_clause:
                            found_materials = list(self.label_to_class[word].instances())
                            # print(found_materials)
                            found_clothing = []
                            for material in found_materials:
                                found_clothing = list(
                                    set(found_clothing + list(self.ontology.search(containsMaterial=material))))
                            # print("FOUND CLOTHING: ", found_clothing)
                        else:
                            found_clothing = list(self.ontology.search(containsMaterial=self.label_to_indiv[word]))
                    elif some_clause:
                        found_clothing = list(self.label_to_class[word].instances())
                        some_clause = False
                    elif price:
                        maxprice = int(word)
                        price = False
                    elif fairness:
                        isFairTrade = word.lower()
                    else:
                        found_clothing = list(self.ontology.search(self.label_to_class[word]))

            if negation:
                if union:
                    included_clothing = list(set(all_clothing) - set(found_clothing))
                    clothing_list = list(set(clothing_list + included_clothing))
                    union = False
                else:
                    clothing_list = list(set(clothing_list) - set(found_clothing))
                negation = False
                continue
            if union:
                clothing_list = list(set(clothing_list + found_clothing))
                if or_found:
                    or_found = False
                    continue
                union = False
            else:
                clothing_list = list(set(clothing_list) & set(found_clothing))

        clothing_list_price = []
        # print("BEFORE PRICE FILTER", clothing_list, maxprice)
        if maxprice > 0:
            # print("FOUND PRICE CONDITION: ", maxprice)
            for cloth in clothing_list:
                # print("PRICE: ", cloth.hasPriceEur)
                if cloth.hasPriceEur:
                    if cloth.hasPriceEur[0] <= maxprice:
                        # print("ADD: ", cloth)
                        clothing_list_price.append(cloth)
        else:
            # print("NO PRICE FILTER")
            clothing_list_price = clothing_list

        clothing_list_fair = []
        # print("BEFORE ETHICAL FILTER", clothing_list_price, fairness)
        if fairness:
            for cloth in clothing_list_price:
                if cloth.isFairTrade and str(cloth.isFairTrade[0]).lower() == isFairTrade:
                    # print("ADD MATCHING FAIRNESS: ", cloth)
                    clothing_list_fair.append(cloth)
        else:
            clothing_list_fair = clothing_list_price

        # print("Selected clothing after parsing but with prevented: ", clothing_list_fair)
        preferred_clothing = list(set(clothing_list_fair) - set(health_prevented_clothing))
        # print('Clothing found based on preferences and health conditions: ', preferred_clothing)

        items_with_clothing_stores = self.infer_stores(preferred_clothing)
        # print('Stores found that offer matching items: ', items_with_clothing_stores)

        items_with_stores_by_location = {}
        for item, clothing_store in items_with_clothing_stores.items():
            items_with_stores_by_location[item] = self.filter_stores_on_location(preferences['pref_location'],
                                                                                 clothing_store)

        return preferred_clothing, items_with_clothing_stores, items_with_stores_by_location

    def create_clothing_recommendations(self, preferred_clothing, items_with_stores_by_location, current_location, pref_len, loosened_prefs=[]):

        recommendations = []
        #print("INPUT DICTIONARY: ", items_with_stores_by_location)
        for item, clothing_store in items_with_stores_by_location.items():
            n_domains = 1
            CO2_scores_per_domain = [item.hasCO2score[0]]
            #print(100, item, CO2_scores_per_domain)
            if item.hasOrigin[0]:
                origin = item.hasOrigin[0]
                n_domains +=1
                CO2_scores_per_domain.append(origin.hasCO2score[0])
            #print(200, item, CO2_scores_per_domain)
            if clothing_store[0] != 'Online store only':
                #print("REAL STORE")
                travel_options = agent.determine_travel_options(current_location, clothing_store,
                                                            preferences['user'])
                for clothing_store, travel_options in travel_options.items():
                    for travel_option in travel_options:
                        #print(300, item, CO2_scores_per_domain)
                        del CO2_scores_per_domain[2:] #make sure that all items have origin for this not to remove useful information
                        #print(400, item, CO2_scores_per_domain)
                        charging_spot = ''
                        if len(travel_option) == 3:
                            CO2_scores_per_domain.append(travel_option[0].hasCO2score[0] + travel_option[2])
                        elif travel_option[0] == 'Walking':
                            CO2_scores_per_domain.append(1)
                        elif travel_option[0] == 'Public Transport':
                            CO2_scores_per_domain.append(2)
                        elif self.charging_spot and travel_option[0].is_a[0] == self.ontology.ElectricCar:
                            charging_spot = self.charging_spot
                        else:
                            CO2_scores_per_domain.append(travel_option[0].hasCO2score[0])
                        n_domains = len(CO2_scores_per_domain)
                        for pref in preferences['loose_prefs']:
                            if 'duration' in pref:
                                max_duration = int(pref.split('duration<')[1])
                                if travel_option[1] > max_duration - 1:
                                    loosened_prefs.append('Duration')
                                    pref_len += 1
                            if 'transport' in pref:
                                list_pref_transport = list(
                                    self.label_to_class[str(pref.split('transport=')[1])].instances())
                                if not travel_option[0] in list_pref_transport:
                                    loosened_prefs.append('Transport')
                                    pref_len += 1

                        recommendation = RecommendationState('Clothing', travel_option[0], [], [], clothing_store,
                                                         item, preferences['time_of_activity'], loosened_prefs
                                                         , charging_spot)

                        adhered_prefs = pref_len - len(loosened_prefs)
                        percentage_loose = adhered_prefs / pref_len
                        #print("REAL STORE ITEM FINAL: ", CO2_scores_per_domain)
                        #print(1989, adhered_prefs, loosened_prefs, pref_len, percentage_loose)
                        #print("DOMAINS: ", n_domains)
                        utility = recommendation.calculate_utility(percentage_loose,
                                                                    CO2_scores_per_domain, n_domains)
                        #print("UTILITY: ", utility)
                        recommendations.append([recommendation, utility, travel_option[1], adhered_prefs])

            else:
                n_domains +=1
                CO2_scores_per_domain.append(1)

                recommendation = RecommendationState('Clothing', [], [], [], clothing_store, item, [], loosened_prefs)

                adhered_prefs = pref_len - len(loosened_prefs)
                percentage_loose = adhered_prefs / pref_len
                #print("ONLINE STORE ITEM FINAL: ", CO2_scores_per_domain)
                #print(1979, adhered_prefs, loosened_prefs, pref_len, percentage_loose)
                #print("DOMAINS: ", n_domains)
                utility = recommendation.calculate_utility(percentage_loose,
                                                                    CO2_scores_per_domain, n_domains)
                #print("UTILITY: ", utility)
                recommendations.append([recommendation, utility, [], adhered_prefs])

        return recommendations

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
            return list(set(preferred_recipes) & set(cuisine_meals))
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
            restaurants = ''
        return restaurants

    def get_user_location(self, current_location, user):
        if current_location:
            return self.label_to_indiv[current_location]
        else:
            return self.label_to_indiv[user].livesIn[0]

    def check_user_transport_options(self, owned_transport, current_neighborhood):
        available_transport = []
        for vehicle in owned_transport:
            location_of_vehicle = vehicle.isLocatedIn[0]
            extra_travel_time = 0
            if location_of_vehicle in list(current_neighborhood.adjacentTo) or \
                    location_of_vehicle == current_neighborhood:
                if vehicle.is_a[0] == self.ontology.ElectricCar:  # Check if electric battery is charged
                    if not vehicle.isBatteryCharged[0]:
                        self.charging_spot = random.choice(list(location_of_vehicle.hasChargingSpot))
                        extra_travel_time = int(vehicle.timeToChargeElectricCar[0])
                available_transport.append([vehicle, extra_travel_time])
        return available_transport

    def determine_travel_options(self, current_location, destinations, user):
        city = current_location.isLocatedIn[0]
        owned_transport = list(self.label_to_indiv[user].owns)
        destination_dict = {}

        for destination in destinations:
            destination_dict[destination] = self.check_user_transport_options(owned_transport, current_location)

            # In the normal situation the destination object contains location already
            try:
                destination_neighborhood = destination.isLocatedIn[0]
                destination_city = destination.isLocatedIn[1]
            # Exceptional case where we want travel options to a direct neighborhood
            except AttributeError:
                destination_neighborhood = destination
                d_ins = self.ontology.search(label=destination_neighborhood)
                for n in self.ontology.Neighborhood.instances():
                    if n == d_ins[0]:
                        destination_neighborhood = d_ins[0]
                        destination_city = n

            if city == destination_city:  # Check if current location is in the same city as the destination
                if current_location in list(destination_neighborhood.adjacentTo) or \
                        current_location == destination_neighborhood:  # check if neighborhoods adjacent
                    if current_location in list(destination_neighborhood.adjacentTo):
                        for i in destination_dict[destination]:
                            if i[0].is_a[0] == self.ontology.Bike:
                                i[1] += 10
                            if i[0].is_a[0].is_a[0] == self.ontology.Car:
                                i[1] += 5
                        destination_dict[destination].append(['Walking', 30])
                    else:
                        for i in destination_dict[destination]:
                            if i[0].is_a[0] == self.ontology.Bike:
                                i[1] += 5
                            if i[0].is_a[0].is_a[0] == self.ontology.Car:
                                i[1] += 2
                        destination_dict[destination].append(['Walking', 10])
                else:  # neighborhoods not adjacent
                    for i in destination_dict[destination]:
                        if i[0].is_a[0] == self.ontology.Bike:
                            i[1] += 15
                        if i[0].is_a[0].is_a[0] == self.ontology.Car:
                            i[1] += 15
                    destination_dict[destination].append(['Public Transport', 15])

            else:  # Not in the same city
                if city == self.ontology.Amsterdam and destination_city == self.ontology.Utrecht:
                    train = self.ontology.TrainFromAmsterdamToUtrecht
                else:
                    train = self.ontology.TrainFromUtrechtToAmsterdam
                public_transport_time = 27  # Duration of train in minutes
                extra_co2score = 0  # If user has to take a tram or a bus in the other city, CO2 score becomes worse

                if current_location.hasPopulation[0] > 20000:  # Check if current neighborhood has train station
                    public_transport_time += 5  # User needs to walk about 5 minutes
                else:
                    for i in destination_dict[destination]:  # Check if user has bike
                        if i[0].is_a[0] == self.ontology.Bike:
                            public_transport_time += int(i[0].travelTimeToNearestTrainStation[0])
                if destination_neighborhood.hasPopulation[0] > 20000:  # Check if destination neighborhood
                    # has train station
                    public_transport_time += 5
                else:  # User needs to use public transport (bus/tram) to get to destination
                    public_transport_time += 15
                    extra_co2score += 1
                destination_dict[destination].append([train, public_transport_time, extra_co2score])
                for i in destination_dict[destination]:
                    if i[0].is_a[0].is_a[0] == self.ontology.Car:
                        i[1] += 55
                for i in destination_dict[destination]:  # Can no longer bike to destination
                    if i[0].is_a[0] == self.ontology.Bike:
                        destination_dict[destination].remove(i)
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
                if count_upper_case_letters(word) > 1:  # Need to split label with space
                    old_word = word
                    word = ''
                    for i, letter in enumerate(old_word):
                        if i and letter.isupper() and i != 0:
                            word += ' '
                        word += letter
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

        preferred_recipes = list(set(food_list) - set(health_prevented_recipes))

        prefered_recipes_cuisines = self.infer_recipes_for_cuisines(preferred_recipes, cuisines)
        # print('Recipes found based on preferences and health conditions: ', preferred_recipes)
        # print('Recipes that match cuisine preferences: ', prefered_recipes_cuisines, '\n')

        recipe_with_restaurants = self.infer_restaurants(preferred_recipes)
        recipes_restaurants_cuisines = self.infer_restaurants(prefered_recipes_cuisines)
        recipes_restaurants_by_cuisines_loc = {}
        recipe_with_restaurants_by_loc = {}
        if recipe_with_restaurants != '':
            for recipe, restaurants in recipe_with_restaurants.items():
                # print('Ignoring the cuisine wishes, found the following restaurants that serve:', recipe.label[0])
                # print(restaurants)
                recipe_with_restaurants_by_loc[recipe] = self.filter_restaurants_on_location(preferences['pref_location'],
                                                                                             restaurants)
                # print('Of these restaurants, the following are available in', preferences['pref_location'][0])
                # print(recipe_with_restaurants_by_loc[recipe], '\n')

            for recipe, restaurants in recipes_restaurants_cuisines.items():
                # print('Found the following', preferences['pref_cuisines'], 'restaurants that serve:', recipe.label[0])
                # print(restaurants)
                recipes_restaurants_by_cuisines_loc[recipe] = self.filter_restaurants_on_location(
                    preferences['pref_location'], restaurants)
                # print('Of these restaurants, the following are available in', preferences['pref_location'][0])
                # print(recipes_restaurants_by_cuisines_loc[recipe], '\n')
        else:
            recipe_with_restaurants_by_loc = recipe_with_restaurants_by_loc = []
        return recipe_with_restaurants, recipe_with_restaurants_by_loc, recipes_restaurants_cuisines, recipes_restaurants_by_cuisines_loc

    def find_states(self, preferences):

        if "Activity" in preferences["activity"]:
            self.rushhour = preferences["time_of_activity"] > 16 and preferences["time_of_activity"] < 22

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

            possible_activities = self.ontology.search(label="Activity")
            selected_activities = possible_activities[0].instances()
            selected_activities_pref = self.infer_activity(preferences, selected_activities)
            options = [[x, y] for x in selected_activities_pref for y in selected_energy]
            sorted_options = self.recommend_activity(options)
            self.explain_actions(preferences, sorted_options, options)

        if "Restaurant" in preferences["activity"]:
            current_location = agent.get_user_location(preferences['current_location'], preferences['user'])
            health_conditions = agent.infer_health_cond(preferences['symptoms'], preferences['user'])
            restaurants, restaurants_loc, restaurants_cuisines, restaurants_by_cuisines_loc = \
                agent.infer_recipes(preferences['pref_cuisines'], preferences['pref_food'], health_conditions)

            if agent.ontology.COVID in health_conditions:  # Agent believes user has COVID
                print('From either your specified health conditions or inferred through your symptoms, '
                      'it has been concluded that you might have COVID-19.\n'
                      'Therefore the agent recommends not travelling and staying inside.')
                return
            if len(restaurants_by_cuisines_loc) == 0 and len(restaurants_loc) == 0:
                print('Unfortunately, no restaurants were found in that location.')
                print('Please input other preferences to the agent')
                return
            elif len(restaurants_by_cuisines_loc) == 0 :
                print('Unfortunately, no restaurants were found in that location. '
                      'The agent will recommend other restaurants which are not located in your specified location.\n')
                agent.create_recommendations(restaurants_cuisines, current_location)
            else:
                options = agent.create_recommendations(restaurants, restaurants_loc, restaurants_cuisines,
                                                       current_location, preferences['loose_prefs'])
                # options.append(agent.create_recommendations(restaurants_cuisines, current_location))
                # options.append(agent.create_recommendations(restaurants, current_location))
                options.sort(key=operator.itemgetter(3, 1), reverse=True)
                agent.offer_restaurant_recommendations(options, preferences)

        if "Clothing" in preferences["activity"]:
            total_pref_len = len(preferences['pref_clothing'])
            loosened_prefs = []
            current_location = agent.get_user_location(preferences['current_location'], preferences['user'])
            health_conditions = agent.infer_health_cond(preferences['symptoms'], preferences['user'])
            #agent.infer_clothes(preferences['pref_clothing'], preferences['health_conditions'])
            preferred_clothing, items_with_clothing_stores, items_with_stores_by_location = \
                (agent.infer_clothes(preferences['pref_clothing'], health_conditions))

            if len(preferred_clothing) == 0:

                while len(preferred_clothing) == 0:
                    print('Unfortunately, no clothes with all matching preferences were found. We will now try to broaden the request.')
                    if len(preferences['pref_clothing']) > 0:
                        print('Removing preference: {}'.format(preferences['pref_clothing'][-1]))
                    #print(preferences['pref_clothing'])
                    loosened_prefs.append(preferences['pref_clothing'].pop(-1))
                    #print(preferences['pref_clothing'])
                    preferred_clothing, items_with_clothing_stores, items_with_stores_by_location = \
                    (agent.infer_clothes(preferences['pref_clothing'], health_conditions))
                options = agent.create_clothing_recommendations(preferred_clothing, items_with_stores_by_location, current_location, total_pref_len, loosened_prefs)
                options.sort(key = operator.itemgetter(3, 1), reverse=True)
                agent.offer_clothing_recommendations(options, preferences)

            else:
                options = agent.create_clothing_recommendations(preferred_clothing, items_with_stores_by_location, current_location, total_pref_len)
                options.sort(key = operator.itemgetter(3, 1), reverse=True)
                agent.offer_clothing_recommendations(options, preferences)
                # commented code for checking all recommendations
                #while options:
                    #print("OPTIONS: ", options[0][0].clothing_item.label[0])
                    #agent.offer_clothing_recommendations(options, preferences)
                    #del options[0]

        if "Transportation" in preferences["activity"]:
            # Get current location, health conditions and available travel options
            current_location = agent.get_user_location(preferences['current_location'], preferences['user'])
            health_conditions = agent.infer_health_cond(preferences['symptoms'], preferences['user'])
            travel_options = agent.determine_travel_options(current_location, preferences['pref_location'],
                                                            preferences['user'])
            # Create travel recommendations
            options = agent.create_travel_recommendations(travel_options, preferences['loose_prefs'])
            # Check for Covid
            restricted = False
            if agent.ontology.COVID19 in health_conditions:
                restricted = True
            # Offer travel recommendations
            options.sort(key=operator.itemgetter(3, 1), reverse=True)
            agent.offer_travel_recommendations(options, restricted, preferences)

        return options

    def filter_activities(self, activities, user):
        filter_activities =[]
        owned_households = list(self.label_to_indiv[user].ownsAtHome)
        for activity in activities:
            for prop in activity.get_properties():
                if prop.python_name == "requiresHouseHold":
                    for value in prop[activity]:
                        if not value in owned_households:
                            filter_activities.append(activity)

        return list(set(activities) - set(filter_activities))

        # health_prevented_recipes = list(
        #     set(list(self.ontology.search(ownsAtHome=owned_households))))

    def infer_activity(self, preferences, selected_activities):

        selected_activities = self.filter_activities(selected_activities, preferences["user"])
        activities_pref = []
        selected_activities_names = [item.name for item in selected_activities]
        for preference in preferences["loose_prefs"]:
            pref = preference.split(" ")
            for item in pref:
                if item.startswith("activity="):
                    if item.split("=")[1] in selected_activities_names:
                        activities_pref.append(item.split("=")[1])
        return [[activity, 0] if activity.name not in activities_pref else [activity, 1] for activity in
                selected_activities]

    def recommend_activity(self, options):
        d = {}

        for idx, option in enumerate(options):
            CO2_scores_per_domain = [item[0].hasCO2score[0] if type(item) == list else item.hasCO2score[0] for item in
                                     option]
            len_domain = len(option[0])
            adhered_prefs = option[0][1]
            percentage_loose = adhered_prefs / len(preferences["loose_prefs"])

            recommendation = RecommendationState(activity=option[0][0], energy=option[1])
            utility = recommendation.calculate_utility(percentage_loose, CO2_scores_per_domain, len_domain)
            d[(option[0][0].label[0].lower(), option[0][0].label[0].lower())] = utility
        sorted_options = dict(sorted(d.items(), key=operator.itemgetter(1), reverse=True))

        return sorted_options

    def explain_actions(self, preferences, sorted_options, options):
        print("Dear {},".format(preferences["user"]))
        x = list(list(sorted_options.keys())[0])[0]
        print(
            'If you want to do an {} right now the {} we recommend to do is {} as it is the most environmentally friendly option.'.format(
                preferences["activity"], preferences["activity"], x))
        # list(sorted_options.values())[0]))

        if preferences["time_of_activity"] >= 20 and "Activity" in preferences["activity"]:
            self.rushhour = True
            sorted_options = self.recommend_activity(options)
            print("An alternative option is to wait {} hour. In that case, you use sustainable energy if it is still {}.\n"
                  "In that case you could also {} or {} in which you only use sustainable energy.".format(
                21 - preferences["time_of_activity"], preferences["weather_condition"][0].lower(), list(list(sorted_options.keys())[1])[0], list(list(sorted_options.keys())[2])[0]))

    def create_transport_string(self, options):
        transport1 = transport2 = 'No transport'
        if len(options) > 0:
            if options[0][0].transportation:
                if isinstance(options[0][0].transportation, str):
                    transport1 = options[0][0].transportation
                else:
                    transport1 = options[0][0].transportation.is_a[0].label[0]
        if len(options) > 1:
            if options[1][0].transportation:
                if isinstance(options[1][0].transportation, str):
                    transport2 = options[1][0].transportation
                else:
                    transport2 = options[1][0].transportation.is_a[0].label[0]
        return transport1, transport2

    def offer_clothing_recommendations(self, options, preferences):
        print('Dear {},'.format(preferences["user"]))

        if len(options[0][0].pref_not_adhered_to) == 0:
            print(
            'For your entered preferences, we found {}'.format(len(options)), 'recommendation(s).')

            if not isinstance(options[0][0].clothing_store, list):
                transport1, transport2 = self.create_transport_string(options)
                print('Of these recommendations, the most environmentally friendly choice which completely pertains to all your '
                  'preferences is the following garment: {0}, which can be obtained in {1}.'.format(options[0][0].clothing_item.label[0], options[0][0].clothing_store.label[0]))
                print('{}'.format(options[0][0].clothing_store.label[0]), 'is located in the neighborhood of {}'.format(options[0][0].clothing_store.isLocatedIn[0].label[0]),
                'in {}.'.format(options[0][0].clothing_store.isLocatedIn[1].label[0]))
                print( 'It is recommended to travel to this clothing store '
                  'by {}'.format(transport1), 'which is estimated to take {}'.format(options[0][2]),'minutes of travel time.\n')
                if options[0][0].charging_spot:
                    print('It seems your electric car needs charging, which will take around {}'.format(options[0][0].transportation.timeToChargeElectricCar[0]),
                      ' minutes. The nearest car charging spot can be found on {}'.format(options[0][0].charging_spot.label[0].split('Charging')[1]))
            else:
                print('Of these recommendations, the most environmentally friendly choice which completely pertains to all your '
                  'preferences is the following garment: {}, which can be purchased in an online store.'.format(options[0][0].clothing_item.label[0]))

            if len(options) > 1:
                if options[1][1] > options[0][1]:
                    print('However, a more environmentally friendly option was found when we ignored your preference of '
                    '{}.'.format(options[1][0].pref_not_adhered_to), ' If you are able to loosen this preference, '
                    'we would recommend the following:\n')
                    print(
                    'The recommendation with the best environmental score is to get the following item:'
                    ' {}.'.format(options[1][0].clothing_item.label[0]))

        else:

            options.sort(key = operator.itemgetter(1), reverse=True)
            print('No options could be found that adhere to all of your preferences. However, we found {0} recommendation(s) '
            'when we ignored the following condition: {1}'.format(len(options), options[0][0].pref_not_adhered_to))
            print('The most environmentally friendly option our agent discovered is the following garment: {}.'.format(options[0][0].clothing_item.label[0]))
                  
            if not isinstance(options[0][0].clothing_store, list):
                transport1, transport2 = self.create_transport_string(options)
                print('It can be obtained in {}.'.format(options[0][0].clothing_store.label[0]))
                print('{}'.format(options[0][0].clothing_store.label[0]), 'is located in the neighborhood of {}'.format(options[0][0].clothing_store.isLocatedIn[0].label[0]),
                'in {}.'.format(options[0][0].clothing_store.isLocatedIn[1].label[0]))
                print( 'It is recommended to travel to this clothing store '
                  'by {}'.format(transport1), 'which is estimated to take {}'.format(options[0][2]),'minutes of travel time.\n')
                if options[0][0].charging_spot:
                    print('It seems your electric car needs charging, which will take around {}'.format(options[0][0].transportation.timeToChargeElectricCar[0]),
                      ' minutes. The nearest car charging spot can be found on {}'.format(options[0][0].charging_spot.label[0].split('Charging')[1]))
            else:
                print('For these recommendation, the only possible option is to purchase the item online.')

    def offer_restaurant_recommendations(self, options, preferences):
        transport1, transport2 = self.create_transport_string(options)
        print('Dear {},'.format(preferences["user"]))
        print(
            'For your entered preferences, {}'.format(len(options)), 'recommendations were found.')
        if len(options[0][0].pref_not_adhered_to) == 0:
            print(
                'Of these recommendations, the most environmentally friendly option which completely pertains to all your '
                'preferences is to eat at the following restaurant: {}.'.format(options[0][0].restaurant.label[0]))
            print('This restaurant offers {}'.format(options[0][0].food.label[0]),
                  'which matches your food preferences.'
                  ' {}'.format(options[0][0].restaurant.label[0]),
                  'is located in the neighborhood of {}'.format(options[0][0].restaurant.isLocatedIn[0].label[0]),
                  'in {}.'.format(options[0][0].restaurant.isLocatedIn[1].label[0]))
            print('It is recommended to travel to the restaurant '
                  'by {}'.format(options[0][0].transportation.is_a[0].label[0]),
                  'which is estimated to take {}'.format(options[0][2]), 'minutes of travel time.\n')
            if options[0][0].charging_spot:
                print('It seems your electric car needs charging, which will take around {}'.format(
                    options[0][0].transportation.timeToChargeElectricCar[0]),
                      ' minutes. The nearest car charging spot can be found on {}'.format(
                          options[0][0].charging_spot.label[0].split('Charging')[1]))

            if options[1][1] > options[0][1]:
                print('However, a more environmentally friendly option was found when we ignore your preference of '
                      '{}.'.format(options[1][0].pref_not_adhered_to), ' If you are able to loosen this preference, '
                                                                       'we would recommend the following:\n')
                print(
                    'The recommendation with the best environmental score is to eat at the following restaurant:'
                    ' {}.'.format(options[1][0].restaurant.label[0]))
                print('This restaurant offers {}'.format(options[1][0].food.label[0]),
                      'which matches your food preferences.'
                      ' The restaurant {}'.format(options[1][0].restaurant.label[0]),
                      'is located in the neighborhood of {}'.format(options[1][0].restaurant.isLocatedIn[0].label[0]),
                      'in {}.'.format(options[1][0].restaurant.isLocatedIn[1].label[0]))
                print('It is recommended to travel to the restaurant '
                      'by {}'.format(transport2),
                      'which is estimated to take {}'.format(options[1][2]), 'minutes of travel time.\n')
        else:
            options.sort(key=operator.itemgetter(1), reverse=True)
            print('No options could be found that adhere to all your preferences. The most environmentally friendly '
                  'option the agent could find is when your preference of {}'.format(
                options[0][0].pref_not_adhered_to),
                  ' is ignored.\n This recommends to eat at the following restaurant: {}.'.format(
                      options[0][0].restaurant.label[0]))
            print('This restaurant offers {}'.format(options[0][0].food.label[0]),
                  'which matches your food preferences.'
                  ' {}'.format(options[0][0].restaurant.label[0]),
                  'is located in the neighborhood of {}'.format(options[0][0].restaurant.isLocatedIn[0].label[0]),
                  'in {}.'.format(options[0][0].restaurant.isLocatedIn[1].label[0]))
            print('It is recommended to travel to the restaurant '
                  'by {}'.format(transport1),
                  'which is estimated to take {}'.format(options[0][2]), 'minutes of travel time.\n')

    def offer_travel_recommendations(self, options, restricted, preferences):
        print('Dear {},'.format(preferences["user"]))
        print(
            'For your entered preferences, {}'.format(len(options)), 'recommendations were found.')
        if len(options[0][0].pref_not_adhered_to) == 0:

            print(
                'Of these recommendations, the most environmentally friendly option which completely pertains to all your '
                'preferences is to travel by {}, which is estimated to take {} minutes of travel time.\n'.format(
                    options[0][0].transportation.is_a[0].label[0], options[0][2]))

            if options[0][0].charging_spot:
                print('It seems your electric car needs charging, which will take around {}'.format(
                    options[0][0].transportation.timeToChargeElectricCar[0]),
                      ' minutes. The nearest car charging spot can be found on {}'.format(
                          options[0][0].charging_spot.label[0].split('Charging')[1]))

            if options[1][1] > options[0][1]:
                print('However, a more environmentally friendly option was found when we ignore your preference of '
                      '{}.'.format(options[1][0].pref_not_adhered_to), ' If you are able to loosen this preference, '
                                                                       'we would recommend the following:\n')
                print(
                    'The most environmentally friendly option is to travel by {}, which is estimated to take {} minutes of travel time.\n'.format(
                        options[1][0].transportation.is_a[0].label[0], options[1][2]))

            if restricted:
                print(
                    'However, due to symptoms applicable to a COVID-19 infection the use of public transportation cannot be recommended.'
                    ' We recommend the following:')
                print(
                    'The best option is to travel by {}, which is estimated to take {} minutes of travel time.'.format(
                        options[1][0].transportation.is_a[0].label[0], options[1][2]))


        else:
            options.sort(key=operator.itemgetter(1), reverse=True)
            print('No options could be found that adheres to all your preferences. The most environmentally friendly '
                  'option the agent could find, is when your preference of {}'.format(
                options[0][0].pref_not_adhered_to),
                  ' is ignored.\n.')
            print('This recommends to travel by {}, which is estimated to take {} minutes of travel time.\n'.format(
                options[0][0].transportation.is_a[0].label[0], options[0][2]))

    def create_recommendations(self, recipe_restaurants, restaurants_loc, restaurants_cuisines,
                               current_location, loose_prefs):
        restaurants_loc = [item for sublist in restaurants_loc.values() for item in sublist]
        restaurants_cuisines = [item for sublist in restaurants_cuisines.values() for item in sublist]
        recommendations = []
        for recipe, restaurants in recipe_restaurants.items():
            CO2_scores_per_domain = [recipe.hasCO2score[0]]
            travel_options = agent.determine_travel_options(current_location, restaurants,
                                                            preferences['user'])
            for restaurant, travel_options in travel_options.items():

                for travel_option in travel_options:
                    adhered_prefs = len(loose_prefs)
                    del CO2_scores_per_domain[1:]
                    pref_not_adhered_to = []
                    charging_spot = ''
                    if not restaurant in restaurants_loc:  # Location preference not adhered to
                        pref_not_adhered_to.append('Location')
                    if not restaurant in restaurants_cuisines:  # Cuisine preferences not adhered to
                        pref_not_adhered_to.append('Cuisine')
                    if len(travel_option) == 3:
                        CO2_scores_per_domain.append(travel_option[0].hasCO2score[0] + travel_option[2])
                    elif travel_option[0] == 'Walking':
                        CO2_scores_per_domain.append(1)
                    elif travel_option[0] == 'Public Transport':
                        CO2_scores_per_domain.append(2)
                    elif self.charging_spot and travel_option[0].is_a[0] == self.ontology.ElectricCar:
                        charging_spot = self.charging_spot
                    else:
                        CO2_scores_per_domain.append(travel_option[0].hasCO2score[0])
                    n_domains = len(CO2_scores_per_domain)
                    for pref in preferences['loose_prefs']:
                        if 'transport' in pref:
                            list_pref_transport = list(
                                self.label_to_class[str(pref.split('transport=')[1])].instances())
                            if not travel_option[0] in list_pref_transport:
                                pref_not_adhered_to.append('Transport')
                        if 'duration' in pref:
                            max_duration = int(pref.split('duration<')[1])
                            if travel_option[1] > max_duration - 1:
                                pref_not_adhered_to.append('Duration')

                    recommendation = RecommendationState('Restaurant', travel_option[0], restaurant, recipe, [],
                                                         [], preferences['time_of_activity'], pref_not_adhered_to
                                                         , charging_spot)
                    adhered_prefs = adhered_prefs - len(pref_not_adhered_to)
                    percentage_loose = adhered_prefs / len(loose_prefs)
                    utility = recommendation.calculate_utility(percentage_loose,
                                                               CO2_scores_per_domain, n_domains)
                    recommendations.append([recommendation, utility, travel_option[1], adhered_prefs])
        return recommendations

    def create_travel_recommendations(self, travel_options, loose_prefs):

        recommendations = []
        CO2_scores_per_domain = []

        for neighborhood, travel_options in travel_options.items():
            for travel_option in travel_options:
                adhered_prefs = len(loose_prefs)
                del CO2_scores_per_domain[1:]
                pref_not_adhered_to = []
                charging_spot = ''

                if len(travel_option) == 3:
                    CO2_scores_per_domain.append(travel_option[0].hasCO2score[0] + travel_option[2])
                elif travel_option[0] == 'Walk':
                    CO2_scores_per_domain.append(1)
                elif travel_option[0] == 'Public Transport':
                    CO2_scores_per_domain.append(2)
                # elif self.charging_spot and travel_option[0].is_a[0] == self.ontology.ElectricCar:
                # charging_spot = self.charging_spot
                else:
                    CO2_scores_per_domain.append(travel_option[0].hasCO2score[0])
                n_domains = len(CO2_scores_per_domain)
                for pref in preferences['loose_prefs']:
                    if 'duration' in pref:
                        max_duration = int(pref.split('duration<')[1])
                        if travel_option[1] > max_duration - 1:
                            pref_not_adhered_to.append('Duration')

                recommendation = RecommendationState('Restaurant', travel_option[0], neighborhood, neighborhood, [],
                                                     [], preferences['time_of_activity'], pref_not_adhered_to
                                                     , charging_spot)
                adhered_prefs = adhered_prefs - len(pref_not_adhered_to)
                percentage_loose = adhered_prefs / len(loose_prefs)
                utility = recommendation.calculate_utility(percentage_loose,
                                                           CO2_scores_per_domain, n_domains)
                recommendations.append([recommendation, utility, travel_option[1], adhered_prefs])
        return recommendations


if __name__ == "__main__":
    """
    with open('./Users/sophie.json', 'r') as openfile:
        # Reading from json file
        preferences = json.load(openfile)
    agent = Agent("IAG_Group10_Ontology.owl")
    options = agent.find_states(preferences)
    # if preferences['activity'] == 'Restaurant':
    #    agent.recommend_restaurant(options)
    random_agent = random_agent.RandomRecommendationAgent("IAG_Group10_Ontology.owl")
    random_agent.recommend_random_restaurant(preferences)
    with open('./Users/dennis.json', 'r') as openfile:
        # Reading from json file
        preferences = json.load(openfile)
    options = agent.find_states(preferences)
    random_agent.recommend_random_activity(preferences)
    """
    with open('./Users/alex.json', 'r') as openfile:
        # Reading from json file
        preferences = json.load(openfile)
    agent = Agent("IAG_Group10_Ontology.owl")
    options = agent.find_states(preferences)
    random_agent = random_agent.RandomRecommendationAgent("IAG_Group10_Ontology.owl")
    random_agent.recommend_random_clothing(preferences)
    # for option in options:
    # print(option[0].clothing_item, option[1])
    # agent.find_preferences(preferences)
    # cloth = agent.label_to_indiv['Bershka Topcoat']
    # agent.infer_clothes(preferences['pref_clothing'], preferences['health_conditions'])
