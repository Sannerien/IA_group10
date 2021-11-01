import random
from owlready2 import *
from dl_queries import RecommendationState


class RandomRecommendationAgent:
    def __init__(self, path):
        # Load the desired ontology using the path file
        self.ontology = get_ontology(path)
        self.ontology.load()
        # Run the reasoner to obtain the inferences;
        with self.ontology:
            sync_reasoner(infer_property_values=True)

        self.individuals = []
        for c in self.ontology.classes():
            for indiv in c.instances():
                self.individuals.append(indiv)
        self.label_to_indiv = {ent.label[0]: ent for ent in self.individuals if len(ent.label) > 0}

    def check_user_transport_options(self, owned_transport, current_neighborhood):
        available_transport = []
        for vehicle in owned_transport:
            extra_travel_time = 0
            if vehicle.isLocatedIn[0] in list(current_neighborhood.adjacentTo) or \
                    vehicle.isLocatedIn[0] == current_neighborhood:
                if vehicle.is_a[0] == self.ontology.ElectricCar:  # Check if electric battery is charged
                    if not vehicle.isBatteryCharged[0]:  # TODO add random charging spot in neighborhood
                        extra_travel_time = int(vehicle.timeToChargeElectricCar[0])
                available_transport.append([vehicle, extra_travel_time])
        return available_transport

    def determine_travel_options(self, current_location, destinations, user):
        city = current_location.isLocatedIn[0]
        owned_transport = list(self.label_to_indiv[user].owns)
        destination_dict = {}

        for destination in destinations:
            destination_dict[destination] = self.check_user_transport_options(owned_transport, current_location)
            destination_neighborhood = destination.isLocatedIn[0]
            if city == destination.isLocatedIn[1]:  # Check if current location is in the same city as the destination
                if current_location in list(destination_neighborhood.adjacentTo) or \
                        current_location == destination_neighborhood:  # check if neighborhoods adjacent
                    if current_location in list(destination_neighborhood.adjacentTo):
                        for i in destination_dict[destination]:
                            if i[0].is_a[0] == self.ontology.Bike:
                                i[1] += 10
                            if i[0].is_a[0].is_a[0] == self.ontology.Car:
                                i[1] += 5
                        destination_dict[destination].append(['Walk', 30])
                    else:
                        for i in destination_dict[destination]:
                            if i[0].is_a[0] == self.ontology.Bike:
                                i[1] += 5
                            if i[0].is_a[0].is_a[0] == self.ontology.Car:
                                i[1] += 2
                        destination_dict[destination].append(['Walk', 10])
                else:  # neighborhoods not adjacent
                    for i in destination_dict[destination]:
                        if i[0].is_a[0] == self.ontology.Bike:
                            i[1] += 15
                        if i[0].is_a[0].is_a[0] == self.ontology.Car:
                            i[1] += 15
                    destination_dict[destination].append(['Public Transport', 15])

            else:  # Not in the same city
                if city == self.ontology.Amsterdam and destination.isLocatedIn[1] == self.ontology.Utrecht:
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

    def infer_restaurants(self, recipe):
        possible_restaurants = list(self.ontology.search(serves=recipe))
        restaurant = random.choice(possible_restaurants)
        return restaurant

    def recommend_random_restaurant(self, preferences):
        class_recipes = list(self.ontology.search(subclass_of=self.ontology.search_one(label="Recipe")))
        recipes = []
        for c in class_recipes:
            recipes = list(set(recipes + list(c.instances())))
        random_recipe = random.choice(recipes)
        random_restaurant = self.infer_restaurants(random_recipe)
        current_location = preferences['current_location']

        if not preferences['current_location']:
            current_location = self.label_to_indiv[preferences['user']].livesIn[0]
        travel_for_restaurant = self.determine_travel_options(self.label_to_indiv[current_location],
                                                              [random_restaurant], preferences['user'])
        random_travel_option = random.choice(list(travel_for_restaurant[random_restaurant]))
        recommendation = RecommendationState('Restaurant', random_travel_option[0],
                                             random_restaurant, random_recipe, [],
                                             [], preferences['time_of_activity'], [])

        print(recommendation)

    def recommend_random_activity(self, preferences):

        self.rushhour = preferences["time_of_activity"] > 16 and preferences["time_of_activity"] < 22
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

        possible_activities = self.ontology.search(label="Activity")
        selected_activities = possible_activities[0].instances()

        options = [[x, y] for x in selected_activities for y in selected_energy]

        random_number = random.randint(0, len(options))

        select_option =  options[random_number][0].name
        print(random_number, select_option, "random")
        print("Dear", preferences["user"])

        print(
            'The first advise for selection of {} would be {}  as it is the most environmentally friendly option.'.format(
                preferences["activity"], select_option))

