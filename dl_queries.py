import json
from owlready2 import *
import operator
import random_agent
import random


def count_upper_case_letters(str_obj):
    """
    Counts the amount of upper case letters
    """
    count = 0
    for elem in str_obj:
        if elem.isupper():
            count += 1
    return count


class RecommendationState:
    """
    State for storing a certain recommendation
    """

    def __init__(self, activity='', transportation='', restaurant='', food='', clothing_store='', clothing_item='',
                 pref_not_adhered_to='', duration=0, charging_spot='', energy=''):
        self.activity = activity
        self.transportation = transportation
        self.restaurant = restaurant
        self.food = food
        self.clothing_store = clothing_store
        self.clothing_item = clothing_item
        self.pref_not_adhered_to = pref_not_adhered_to
        self.duration = duration
        self.charging_spot = charging_spot
        self.energy = energy

    def calculate_utility(self, per_loose_prefs, CO2_scores_per_domain, n_domains):
        """
        Calculate utility using percentage of loose preference fulfilled, the CO2 scores (1-5) per domain and
        the total amount of domains
        """
        utility = (per_loose_prefs * n_domains) / sum(CO2_scores_per_domain)

        return utility


class EnvironmentalAgent:
    """
    Group 10's environmental agent with functions for executing inferences using the ontology
    """

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
        """
        Infer what stores are selling certain items, returns dictionary with items as keys and stores as values
        """
        stores = {}
        if len(items) > 0:
            for item in items:
                possible_stores = list(self.ontology.search(selling=item))
                stores[item] = list(possible_stores) if possible_stores else ['Online store']
                # print(stores[item])
        return stores

    def filter_stores_on_location(self, pref_locations, stores):
        """
        Filters given stores on if they are located in the preferred location or not
        """
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
        """
        Infer what clothes the agent can recommend to the user, based on their clothing preferences and their health
        conditions. Health conditions forbid certain materials and therefore certain clothing items containing those
        materials.

        The function parses strings in the pref_clothing field of the json file where comma's are seen as and operators
        and ,"or", takes the union of the two queries on either end. Also handles negation and the some clause.
        """
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

        return preferred_clothing, items_with_stores_by_location

    def create_clothing_recommendations(self, items_with_stores_by_location, current_location, pref_len,
                                        loosened_prefs=[]):
        """
        Creates a list of clothing recommendations (represented as recommendation states) along with their utility
        based on the inferred clothing items, stores and travel options
        """
        recommendations = []
        # print("INPUT DICTIONARY: ", items_with_stores_by_location)
        for item, clothing_store in items_with_stores_by_location.items():
            n_domains = 1
            CO2_scores_per_domain = [item.hasCO2score[0]]
            # print(100, item, CO2_scores_per_domain)
            if item.hasOrigin[0]:
                origin = item.hasOrigin[0]
                n_domains += 1
                CO2_scores_per_domain.append(origin.hasCO2score[0])
            # print(200, item, CO2_scores_per_domain)
            if clothing_store[0] != 'Online store only':
                # print("REAL STORE")
                travel_options = agent.determine_travel_options(current_location, clothing_store,
                                                                preferences['user'])
                for clothing_store, travel_options in travel_options.items():
                    for travel_option in travel_options:
                        # print(300, item, CO2_scores_per_domain)
                        del CO2_scores_per_domain[
                            2:]  # make sure that all items have origin for this not to remove useful information
                        # print(400, item, CO2_scores_per_domain)
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
                                                             item, loosened_prefs, travel_option[1]
                                                             , charging_spot)

                        adhered_prefs = pref_len - len(loosened_prefs)
                        percentage_loose = adhered_prefs / pref_len
                        # print("REAL STORE ITEM FINAL: ", CO2_scores_per_domain)
                        # print(adhered_prefs, loosened_prefs, pref_len, percentage_loose)
                        # print("DOMAINS: ", n_domains)
                        utility = recommendation.calculate_utility(percentage_loose,
                                                                   CO2_scores_per_domain, n_domains)
                        # print("UTILITY: ", utility)
                        recommendations.append([recommendation, utility, adhered_prefs])

            else:
                n_domains += 1
                CO2_scores_per_domain.append(1)

                recommendation = RecommendationState('Clothing', [], [], [], clothing_store, item, loosened_prefs, 0)

                adhered_prefs = pref_len - len(loosened_prefs)
                percentage_loose = adhered_prefs / pref_len
                # print("ONLINE STORE ITEM FINAL: ", CO2_scores_per_domain)
                # print(adhered_prefs, loosened_prefs, pref_len, percentage_loose)
                # print("DOMAINS: ", n_domains)
                utility = recommendation.calculate_utility(percentage_loose,
                                                           CO2_scores_per_domain, n_domains)
                # print("UTILITY: ", utility)
                recommendations.append([recommendation, utility, adhered_prefs])

        return recommendations

    def infer_health_cond(self, symptoms, user):
        """
        Determines what health condition a user has based on their existing health conditions (from ontology) and infers
        other health conditions based on a user's provided symptoms. For example, if a user has a cough as a symptom,
        the agent will infer that the user might have COVID-19 and will forbid certain transport options.
        """
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

    def infer_forbidden_ingredients(self, health_conditions):
        """
        Infer what ingredients are forbidden by the user's health conditions. Returns a list of forbidden ingredients
        """
        list_forbidden_ingredients = []
        if len(health_conditions) > 0:
            for health_cond in health_conditions:
                forbidden_ingredients = list(self.ontology.search(isForbiddenBy=health_cond))
                list_forbidden_ingredients = list(set(list_forbidden_ingredients + forbidden_ingredients))
        return list_forbidden_ingredients

    def infer_restaurants(self, recipes):
        """
        Infers what restaurants serve the given recipes, returns a dictionary recipes as keys along with the restaurants
        that serve that recipe as values
        """
        restaurants = {}
        if len(recipes) > 0:
            for recipe in recipes:
                possible_restaurants = list(self.ontology.search(serves=recipe))
                restaurants[recipe] = list(possible_restaurants)
        else:
            restaurants = ''
        return restaurants

    def get_user_location(self, current_location, user):
        """
        Checks if the user has specified a current location in their input json file, otherwise the agent infers
        that the user is at their home location
        """
        if current_location:
            return self.label_to_indiv[current_location]
        else:
            return self.label_to_indiv[user].livesIn[0]

    def check_user_transport_options(self, owned_transport, current_neighborhood):
        """
        Determines what vehicles the user can use, depending on the user's proximity to their vehicle.
        Vehicles must be in either the current neighborhood of the user or in a neighborhood adjacent to the user's
        current location. Also checks if the user's electric car is charged or not and otherwise determines where
        to charge the car and how much longer it will take.
        """
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
        """
        Determines a user's travel options to their destinations (the restaurants or clothing stores),
        depending on their location, destination and owned vehicles. Also estimates how long each transportation option
        will take. Returns a dictionary of destinations and their available transportation options.
        """
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

    def infer_recipes(self, pref_food, health_cond):
        """
        Infers what recipes a user would like based on the user's preferences and what food is forbidden by their
        health conditions. Like infer_clothes, this function parses the pref_food fields in the json, where comma is an
        and operator, can also parse or, not and some operators and check for either ingredients or recipes.
        Returns a dictionary with the inferred recipes as keys and the restaurants that serve those recipes as values.
        """
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

        recipe_with_restaurants = self.infer_restaurants(preferred_recipes)
        return recipe_with_restaurants

    def find_states(self, preferences):
        """
        Main function for finding recommendations based on user's preferences. This function first distinguishes
        the three main problems our agent can help a user with: restaurant, activity and clothing recommendations.
        """
        if "Activity" in preferences["activity"]:
            self.rushhour = 16 < preferences["time_of_activity"] < 22

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
            restaurants = \
                agent.infer_recipes(preferences['pref_food'], health_conditions)

            if agent.ontology.COVID in health_conditions:  # Agent believes user has COVID
                print('From either your specified health conditions or inferred through your symptoms, '
                      'it has been concluded that you might have COVID-19.\n'
                      'Therefore the agent recommends not travelling and staying inside.')
                return
            if len(restaurants) == 0:
                print('Unfortunately, no restaurants were found for those preferences.')
                print('Please input other preferences to the agent')
                return
            else:
                options = agent.create_restaurant_recommendations(restaurants, current_location, preferences)
                options.sort(key=operator.itemgetter(2, 1), reverse=True)
                agent.offer_restaurant_recommendations(options, preferences)

        if "Clothing" in preferences["activity"]:
            total_pref_len = len(preferences['pref_clothing'])
            loosened_prefs = []
            current_location = agent.get_user_location(preferences['current_location'], preferences['user'])
            health_conditions = agent.infer_health_cond(preferences['symptoms'], preferences['user'])
            preferred_clothing, items_with_stores_by_location = \
                (agent.infer_clothes(preferences['pref_clothing'], health_conditions))

            if len(preferred_clothing) == 0:

                while len(preferred_clothing) == 0:
                    print(
                        'Unfortunately, no clothes with all matching preferences were found. We will now try to broaden the request.')
                    if len(preferences['pref_clothing']) > 0:
                        print('Removing preference: {}'.format(preferences['pref_clothing'][-1]))
                    # print(preferences['pref_clothing'])
                    loosened_prefs.append(preferences['pref_clothing'].pop(-1))
                    # print(preferences['pref_clothing'])
                    preferred_clothing, items_with_stores_by_location = \
                        (agent.infer_clothes(preferences['pref_clothing'], health_conditions))
                options = agent.create_clothing_recommendations(items_with_stores_by_location, current_location,
                                                                total_pref_len, loosened_prefs)
                options.sort(key=operator.itemgetter(2, 1), reverse=True)
                agent.offer_clothing_recommendations(options, preferences)

            else:
                options = agent.create_clothing_recommendations(items_with_stores_by_location, current_location,
                                                                total_pref_len)
                options.sort(key=operator.itemgetter(2, 1), reverse=True)
                agent.offer_clothing_recommendations(options, preferences)
                # commented code for checking all recommendations
                # while options:
                # print("OPTIONS: ", options[0][0].clothing_item.label[0])
                # agent.offer_clothing_recommendations(options, preferences)
                # del options[0]

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
        """
        Filters activities based on if they are household activities.
        """
        filter_activities = []
        owned_households = list(self.label_to_indiv[user].ownsAtHome)
        for activity in activities:
            for prop in activity.get_properties():
                if prop.python_name == "requiresHouseHold":
                    for value in prop[activity]:
                        if not value in owned_households:
                            filter_activities.append(activity)

        return list(set(activities) - set(filter_activities))

    def infer_activity(self, preferences, selected_activities):
        """
        Infers what activities the user can do an wants to do.
        """
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
        """
        Filters activities based on if they are household activities
        """
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
            print(
                "An alternative option is to wait {} hour. In that case, you use sustainable energy if it is still {}.\n"
                "In that case you could also {} or {} in which you only use sustainable energy.".format(
                    21 - preferences["time_of_activity"], preferences["weather_condition"][0].lower(),
                    list(list(sorted_options.keys())[1])[0], list(list(sorted_options.keys())[2])[0]))

    def create_transport_string(self, option):
        """
        Returns a transport string, depending on if the transport option is in the ontology or inferred like Walking.
        """
        transport = 'No transport'
        if option.transportation:
            if isinstance(option.transportation, str):
                transport = option.transportation
            else:
                transport = option.transportation.is_a[0].label[0]
        return transport

    def offer_clothing_recommendations(self, options, preferences):
        """
        Print function for offering the best clothing recommendation.
        """
        print('Dear {},'.format(preferences["user"]))

        if len(options[0][0].pref_not_adhered_to) == 0:
            print(
                'For your entered preferences, we found {}'.format(len(options)), 'recommendation(s).')

            if not isinstance(options[0][0].clothing_store, list):
                transport1, transport2 = self.create_transport_string(options[0][0])
                print(
                    'Of these recommendations, the most environmentally friendly choice which completely pertains to all your '
                    'preferences is the following garment: {0}, which can be obtained in {1}.'.format(
                        options[0][0].clothing_item.label[0], options[0][0].clothing_store.label[0]))
                print('{}'.format(options[0][0].clothing_store.label[0]), 'is located in the neighborhood of {}'.format(
                    options[0][0].clothing_store.isLocatedIn[0].label[0]),
                      'in {}.'.format(options[0][0].clothing_store.isLocatedIn[1].label[0]))
                print('It is recommended to travel to this clothing store '
                      'by {}'.format(transport1), 'which is estimated to take {}'.format(options[0][2]),
                      'minutes of travel time.\n')
                if options[0][0].charging_spot:
                    print('It seems your electric car needs charging, which will take around {}'.format(
                        options[0][0].transportation.timeToChargeElectricCar[0]),
                          ' minutes. The nearest car charging spot can be found on {}'.format(
                              options[0][0].charging_spot.label[0].split('Charging')[1]))
            else:
                print(
                    'Of these recommendations, the most environmentally friendly choice which completely pertains to all your '
                    'preferences is the following garment: {}, which can be purchased in an online store.'.format(
                        options[0][0].clothing_item.label[0]))

            if len(options) > 1:
                if options[1][1] > options[0][1]:
                    print(
                        'However, a more environmentally friendly option was found when we ignored your preference of '
                        '{}.'.format(options[1][0].pref_not_adhered_to), ' If you are able to loosen this preference, '
                                                                         'we would recommend the following:\n')
                    print(
                        'The recommendation with the best environmental score is to get the following item:'
                        ' {}.'.format(options[1][0].clothing_item.label[0]))

        else:

            options.sort(key=operator.itemgetter(1), reverse=True)
            print(
                'No options could be found that adhere to all of your preferences. However, we found {0} recommendation(s) '
                'when we ignored the following condition: {1}'.format(len(options), options[0][0].pref_not_adhered_to))
            print('The most environmentally friendly option our agent discovered is the following garment: {}.'.format(
                options[0][0].clothing_item.label[0]))

            if not isinstance(options[0][0].clothing_store, list):
                transport = self.create_transport_string(options[0][0])
                print('It can be obtained in {}.'.format(options[0][0].clothing_store.label[0]))
                print('{}'.format(options[0][0].clothing_store.label[0]), 'is located in the neighborhood of {}'.format(
                    options[0][0].clothing_store.isLocatedIn[0].label[0]),
                      'in {}.'.format(options[0][0].clothing_store.isLocatedIn[1].label[0]))
                print('It is recommended to travel to this clothing store '
                      'by {}'.format(transport), 'which is estimated to take {}'.format(options[0][0].duration),
                      'minutes of travel time.\n')
                if options[0][0].charging_spot:
                    print('It seems your electric car needs charging, which will take around {}'.format(
                        options[0][0].transportation.timeToChargeElectricCar[0]),
                          'minutes. The nearest car charging spot can be found on {}'.format(
                              options[0][0].charging_spot.label[0].split('Charging')[0]))
            else:
                print('For these recommendation, the only possible option is to purchase the item online.')

    def explain_restaurant_option(self, option, option_rank, transport):
        """
        Print function for explaining a certain restaurant option.
        """
        if option_rank == 0:
            if len(option.pref_not_adhered_to) > 0:
                print('Of these recommendations, the most environmentally friendly option is to eat'
                      'at the following restaurant: {}.'.format(option.restaurant.label[0]))
                print('However this recommendation does not satisfy the following preferences: {}'.format(
                    option.pref_not_adhered_to))
            else:
                print(
                    'Of these recommendations, the most environmentally friendly option which completely satisfies to all your '
                    'preferences is to eat at the following restaurant: {}.'.format(option.restaurant.label[0]))
        else:
            print(
                'Recommendation {}'.format(option_rank + 1), 'is to eat at '
                                                             'the following restaurant: {}.'.format(
                    option.restaurant.label[0]))
            if len(option.pref_not_adhered_to) > 0:
                print('However this recommendation does not satisfy the following preferences: {}'.format(
                    option.pref_not_adhered_to))
        print('This restaurant offers {}'.format(option.food.label[0]),
              'which matches your food preferences.'
              ' {}'.format(option.restaurant.label[0]),
              'is located in the neighborhood of {}'.format(option.restaurant.isLocatedIn[0].label[0]),
              'in {}.'.format(option.restaurant.isLocatedIn[1].label[0]))
        print('It is recommended to travel to the restaurant '
              'by {}'.format(transport),
              'which is estimated to take {}'.format(option.duration), 'minutes of travel time.')
        if option.charging_spot:
            print('It seems your electric car needs charging, which will take around {}'.format(
                option.transportation.timeToChargeElectricCar[0]),
                'minutes. The nearest car charging spot can be found on {}\n'.format(
                    option.charging_spot.label[0].split('Charging')[0]))
        else:
            print('')

    def offer_restaurant_recommendations(self, options, preferences):
        """
        Loops through options and offers the options with the top 5 utility
        """
        print('Dear {},'.format(preferences["user"]))
        print(
            'For your entered preferences, {}'.format(len(options)), 'recommendations were found. '
                                                                     'The agent will output the top recommendations for you.')
        print('The agent has ranked the recommendation based on their environmental impact.\n')
        if len(options) > 0:
            for index, option in enumerate(options[:]):
                if index == 5:
                    break
                transport = self.create_transport_string(option[0])
                self.explain_restaurant_option(option[0], index, transport)

    def offer_travel_recommendations(self, options, restricted, preferences):
        """
        Prints the top travel option based on utility
        """
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
                        options[0][0].charging_spot.label[0].split('Charging')[0]))

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

    def check_restaurant_location_cuisine(self, restaurant_city, restaurant_cuisine, preferences):
        """
        Determines if the user values their preferred cuisine and weighs the cuisine from first entered preferred
        cuisine to last, based on the cuisine weights. Also checks whether the user values their preferred location
        and penalizes when the restaurant is not in this location.
        """
        preferred_locations = [self.label_to_indiv[i] for i in preferences["pref_location"]]
        preferred_cuisines = [self.label_to_indiv[i] for i in preferences["pref_cuisines"]]
        cuisine_weights = [1, 0.7, 0.5, 0.3, 0.1]
        unsatisfied_prefs = []
        cuisine_importance = 0
        if "pref_cuisines" in preferences["loose_prefs"]:
            if restaurant_cuisine in preferred_cuisines:
                cuisine_importance = 1 - cuisine_weights[preferred_cuisines.index(restaurant_cuisine)]
            else:
                unsatisfied_prefs.append('Cuisine')
        if "pref_location" in preferences["loose_prefs"]:
            if len(preferred_locations) > 0:
                if not restaurant_city in preferred_locations:
                    unsatisfied_prefs.append('Location')
        return unsatisfied_prefs, cuisine_importance

    def create_restaurant_recommendations(self, recipe_restaurants, current_location, preferences):
        """
        Creates restaurant recommendations based on the inferred recipes the user would enjoy, what restaurants
        serve those recipes, the user's preferences and the user's current location. The loose preferences are counted
        and the amount of satisfied user preferences is calculated before entering this information in the utility
        function along with the CO2 scores (1-5) per domain (here: recipe and travel option).
        """
        recommendations = []
        for recipe, restaurants in recipe_restaurants.items():
            CO2_scores_per_domain = [recipe.hasCO2score[0]]
            travel_options = agent.determine_travel_options(current_location, restaurants,
                                                            preferences['user'])
            for restaurant, travel_options in travel_options.items():
                restaurant_cuisine = restaurant.hasCuisine[0]
                restaurant_city = restaurant.isLocatedIn[0].isLocatedIn[0]
                for travel_option in travel_options:
                    unsatisfied_prefs, cuisine_importance = \
                        self.check_restaurant_location_cuisine(restaurant_city, restaurant_cuisine, preferences)
                    adhered_prefs = len(preferences["loose_prefs"]) - cuisine_importance
                    del CO2_scores_per_domain[1:]
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
                        if 'transport' in pref:
                            list_pref_transport = list(
                                self.label_to_class[str(pref.split('transport=')[1])].instances())
                            if not travel_option[0] in list_pref_transport:
                                unsatisfied_prefs.append('Transport')
                        if 'duration' in pref:
                            max_duration = int(pref.split('duration<')[1])
                            if travel_option[1] > max_duration - 1:
                                unsatisfied_prefs.append('Duration')

                    recommendation = RecommendationState('Restaurant', travel_option[0], restaurant, recipe, [],
                                                         [], unsatisfied_prefs,
                                                         travel_option[1], charging_spot)
                    adhered_prefs = adhered_prefs - len(unsatisfied_prefs)
                    percentage_loose = adhered_prefs / len(preferences["loose_prefs"])
                    utility = recommendation.calculate_utility(percentage_loose,
                                                               CO2_scores_per_domain, n_domains)
                    recommendations.append([recommendation, utility, adhered_prefs])
        return recommendations

    def create_travel_recommendations(self, travel_options, loose_prefs):
        """
        Creates travel recommendation similarly to how restaurant recommendations are created, and calculates the
        utility for these travel options using the percentage of satisfied preferences and the CO2 scores of the travel
        options.
        """
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
                elif travel_option[0] == 'Walking':
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
                    if 'transport' in pref:
                        list_pref_transport = list(
                            self.label_to_class[str(pref.split('transport=')[1])].instances())
                        if not travel_option[0] in list_pref_transport:
                            pref_not_adhered_to.append('Transport')

                recommendation = RecommendationState('Restaurant', travel_option[0], [],
                                                     [], pref_not_adhered_to, travel_option[1], charging_spot)
                adhered_prefs = adhered_prefs - len(pref_not_adhered_to)
                percentage_loose = adhered_prefs / len(loose_prefs)
                utility = recommendation.calculate_utility(percentage_loose,
                                                           CO2_scores_per_domain, n_domains)
                recommendations.append([recommendation, utility, travel_option[1], adhered_prefs])
        return recommendations


if __name__ == "__main__":
    """
    Main function for creating the agent with the ontology and providing a json file as input
    """
    with open('./Users/alex.json', 'r') as openfile:
        # Reading from json file
        preferences = json.load(openfile)
    agent = EnvironmentalAgent("IAG_Group10_Ontology.owl")
    options = agent.find_states(preferences)
    # random_agent = random_agent.RandomRecommendationAgent("IAG_Group10_Ontology.owl")
    # random_agent.recommend_random_clothing(preferences)
