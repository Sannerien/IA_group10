import json
from owlready2 import *
from pprint import pprint
import numpy as np
import operator

class RecommendationState:

    def __init__(self, activity=[], transportation=[], restaurant=[], food=[], clothing_store=[], clothing_item=[], time_of_activity=[]):
        activity = activity
        transportation = transportation
        restaurant = restaurant
        food = food
        clothing_store = clothing_store
        clothing_item = clothing_item
        time_of_activity = time_of_activity

    def calculate_utility(self, strict_prefs, loose_prefs, CO2_scores_per_domain, n_domains, completed_pref=0):
        utility = 0
        x = len(set(loose_prefs)) + len(set(strict_prefs))
        if x == 0:
            percent_match = 1
        else:
        # by intersecting their set with users's prefs set
            percent_match = np.divide(int(completed_pref), int(x))
        #print("percent match is {}".format(percent_match))
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

        # Run the reasoner to obtain the inferences; TODO: gives an error when run
        with self.ontology:
            sync_reasoner(infer_property_values=True)

        # Reference dictionaries between IRIs and given labels that might be useful
        self.label_to_class = {ent.label[0]: ent for ent in self.ontology.classes() if len(ent.label) > 0}
        self.label_to_prop = {prop.label[0]: prop for prop in self.ontology.properties()if len(prop.label) > 0}

        self.class_to_label = {ent:ent.label[0] for ent in self.ontology.classes() if len(ent.label) > 0}
        self.prop_to_label = {prop:prop.label[0] for prop in self.ontology.properties()if len(prop.label) > 0}

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

    def find_options(self, preferences):

        options = []

        if "Energy" in preferences["query"]:
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
            #options_domains["Energy"] = selected_energy

        if "Activity" in preferences["query"]:
            possible_activities = self.ontology.search(label="Activity")
            selected_activities = possible_activities[0].instances()

            options = [[x,y] for x in selected_activities for y in selected_energy]

        return options

    def check_preferences(self, preference):
        preference["strict_prefs"]

    def choose_actions(self, options):
        recommender = RecommendationState()
        d = {}

        for idx, option in enumerate(options):
            CO2_scores_per_domain = [item.hasCO2score[0] for item in option]
            len_domain = len(option)
            #completed_pref = self.check_preferences(preferences)
            utility = recommender.calculate_utility(preferences["strict_prefs"], preferences["loose_prefs"],
                                          CO2_scores_per_domain, len_domain)
            d[(option[0].name, option[0].name)] = utility
        sorted_options = dict(sorted(d.items(), key=operator.itemgetter(1), reverse=True))
        return sorted_options

    def explain_actions(self, preferences, sorted_options, options):
        print("Dear", preferences["name"])
        x = list(list(sorted_options.keys())[0])[0]
        print('The first advise for selection of {} would be {} with utility score {}.'.format(preferences["query"][0], x, list(sorted_options.values())[0]))

        if preferences["time_of_activity"] >= 20 and "Activity" in preferences["query"]:
            self.rushhour = True
            sorted_options = self.choose_actions(options)
            print("An alternative option is to wait {} hour. In that case another option would be {}".format(21-preferences["time_of_activity"], list(list(sorted_options.keys())[1])[0]))

    def find_preferences(self, preferences):
        query = preferences["query"]

        self.rushhour = preferences["time_of_activity"] > 16 and preferences["time_of_activity"] < 22
        options = self.find_options(preferences)
        sorted_options = self.choose_actions(options)
        self.explain_actions(preferences, sorted_options, options)


        print(options)



if __name__ == "__main__":
    with open('dennis.json', 'r') as openfile:
        # Reading from json file
        preferences = json.load(openfile)
    agent = Agent("IAG_Group10_Ontology.owl")
   # agent.sanity_check()
    agent.find_preferences(preferences)
    print(preferences)