from owlready2 import *
from pprint import pprint
import json

# Ignore useless warnings
#warnings.filterwarnings("ignore")

class Agent:

    def __init__(self, path, reasoner=False):
        # Load the desired ontology using the path file
        self.ontology = get_ontology(path)
        self.ontology.load()

        # Run the reasoner to obtain the inferences; TODO: gives an error when run
        if reasoner:
            with self.ontology:
                sync_reasoner(infer_property_values=True)

        # Additional
        # Reference dictionaries between IRIs and given labels that might be useful
        self.label_to_class = {ent.label[0]: ent for ent in self.ontology.classes()}
        self.label_to_prop = {prop.label[0]: prop for prop in self.ontology.properties()}

        self.class_to_label = {ent:ent.label[0] for ent in self.ontology.classes()}
        self.prop_to_label = {prop:prop.label[0] for prop in self.ontology.properties()}

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
        results = self.ontology.search(label="*_topping")
        class_results = [self.class_to_label[result] for result in results if type(result) == self.class_type]
        pprint(class_results)

        print("-" * 75)

        # Get all the classes that have "Vegetarian" as a superclass
        results2 = self.ontology.search(subclass_of=self.ontology.search_one(label="Vegetarian"))
        subclasses = [self.class_to_label[result] for result in results2 if type(result) == self.class_type]
        pprint(subclasses)

        print("-" * 75)

        # Get all the classes with a label containing "Pizza"
        results = self.ontology.search(label="*Pizza*")
        class_results = [self.class_to_label[result] for result in results if type(result) == self.class_type]
        pprint(class_results)

        print("-" * 75)

        # Get all the properties with a label containing "has"
        results = self.ontology.search(label="*has*")
        class_results = [self.prop_to_label[result] for result in results if type(result) == self.property_type]
        pprint(class_results)

def main(data_path):

    data = json.load(open(data_path))



'''
Run program
'''

# data_path = ""
# main(data_path)

# Initialize agent and run some simple queries
agent = Agent("onto_pizza.owl")
agent.sanity_check()
agent.simple_queries()



# Old code still kept for referencing
'''
for c in list(agent.ontology.classes()):
    print(c.label)
    print(c.iri)
    print(c.name)
    print('\n')

t = agent.ontology.search(label = "*Pizza*")
print(t)
print(type(t) == agent.class_type)
print(type(t) == agent.property_type)
for x in t:
    print(agent.class_to_label[x])
'''





