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
                    #pprint(p)
            #pprint(list(c.instances()))

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
    with open('charly.json', 'r') as openfile:
        # Reading from json file
        preferences = json.load(openfile)
    agent = Agent("ont.owl")
    agent.sanity_check()
    agent.simple_queries()
    print(preferences)
