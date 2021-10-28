import json
from owlready2 import *
from pprint import pprint

class RecommendationState:

    def __init__(self, activity, transportation, restaurant, food, clothing_store, clothing_item, time_of_activity):
        activity = activity
        transportation = transportation
        restaurant = restaurant
        food = food
        clothing_store = clothing_store
        clothing_item = clothing_item
        time_of_activity = time_of_activity

    def calculate_utility(self, story, strict_prefs, prefs, CO2_scores_per_domain, domains):
        utility = 0

        # we only count the actual score if all crucial conditions are met
        if set(strict_prefs) == set(story[0]):
            # we calculate the percentage of unstrict conditions
            # by intersecting their set with users's prefs set
            percent_match = len(set(prefs).intersection(story[1])) / len(set(story[1]))
            print("percent match is {}".format(percent_match))
            # we calculate the score; CO2 value is summed over the list
            utility = percent_match * len(domains) / sum(CO2_scores_per_domain)

        else:
            print("critical unmatch")

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

        # Run the reasoner to obtain the inferences; TODO: gives an error when run
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

    def infer_health_cond(self, symptoms):
        symptom_instances = []
        if len(symptoms) > 0:
            for symptom in symptoms:
                symptom_instances.append(self.label_to_indiv[symptom])
            results = self.ontology.search(hasSymptom=symptom_instances)
            print(results)

    def infer_recipes_for_cuisines(self, cuisines):
        cuisine_meals = []
        if len(cuisines) > 0:
            for cuisine in cuisines:
                cuisine_meals =  list(set(cuisine_meals + self.label_to_indiv[cuisine].containsMeal))
        return cuisine_meals

    #def filter_restaurants_on_location(self, pref_locations, restaurants):
        #cuisine_meals = []
        #if len(restaurants) > 0:
        ##    for restaurant in restaurants:
        #        cuisine_meals =  list(set(cuisine_meals + self.label_to_indiv[restaurants].isLocatedIn pref_locations))
        #return cuisine_meals

    def infer_forbidden_ingredients(self, health_conditions):
        list_forbidden_ingredients = []
        if len(health_conditions) > 0:
            for health_cond in health_conditions:
                forbidden_ingredients = list(self.ontology.search(isForbiddenBy=self.label_to_indiv[health_cond]))
                list_forbidden_ingredients = list(set(list_forbidden_ingredients + forbidden_ingredients))
        return list_forbidden_ingredients

    def infer_restaurants(self, recipes):
        restaurants = []
        if len(recipes) > 0:
            for recipe in recipes:
                possible_restaurants = list(self.ontology.search(serves=recipe))
                restaurants = list(set(restaurants + possible_restaurants))
        else:
            restaurants = self.ontology.Restaurant.instances()
        return restaurants

    def infer_recipes(self, cuisines, pref_food, health_cond):
        # Find what recipes aren't allowed due to health conditions
        health_prevented_ingredients = self.infer_forbidden_ingredients(health_cond)
        health_prevented_recipes = []
        for ingredient in health_prevented_ingredients:
            health_prevented_recipes = list(set(health_prevented_recipes + list(self.ontology.search(containsIngredient=ingredient))))

        cuisine_recipes = self.infer_recipes_for_cuisines(cuisines)
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
                                found_recipes = list(set(found_recipes + list(self.ontology.search(containsIngredient=ingredient))))
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
        prefered_recipes_cuisines = list(set(preferred_recipes) & set(cuisine_recipes))
        print('Recipes found based on preferences and health conditions: ', preferred_recipes)
        print('Recipes that match cuisine preferences: ', prefered_recipes_cuisines)

        restaurants = self.infer_restaurants([])
        print('Restaurants found that serve this food: ', restaurants)
        return preferred_recipes

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


if __name__ == "__main__":
    with open('./Users/dennis.json', 'r') as openfile:
        # Reading from json file
        preferences = json.load(openfile)
    agent = Agent("IAG_Group10_Ontology.owl")
    agent.sanity_check()
    agent.infer_health_cond(preferences['symptoms'])
    agent.infer_recipes(preferences['pref_cuisines'], preferences['pref_food'], preferences['health_conditions'])
    # agent.simple_queries()
    print(preferences)
