#crucial preferences fulfilled by the agent; provided as a list
strict_prefs1 = ["Shellfish"]
strict_prefs2 = ["notShellfish"]
#other preferences fulfilled by the agent; provided as a list
prefs = ["not containsIngredient 'Grain'"] 
# user's preferences. [0] refers to strict preferences, [1] to other preferences, both provided as lists
story = [["notShellfish"],["not containsIngredient 'Grain'", "containsIngredient 'Carrot'"]] 
# we will obtain the number of domains by getting the class of each object in the query 
# and mapping it to a top-level doming, then converting to a set to remove duplicates 
domains = {"Food"}
# CO2 values for each domain provided as a list
CO2_value = [2]

def CO2_utility(story, strict_prefs, prefs, CO2_value):
    score = 0

    #we only count the actual score if all crucial conditions are met
    if set(strict_prefs) == set(story[0]):

        #we calculate the percentage of unstrict conditions
        #by intersecting their set with users's prefs set
        percent_match = len(set(prefs).intersection(story[1])) / len(set(story[1]))
        print("percent match is {}".format(percent_match))
        #we calculate the score; CO2 value is summed over the list
        score = percent_match * len(domains) / sum(CO2_value)
        
    else:
        print("critical unmatch")
        
    return score

if __name__ == "__main__":
    print("score is {}".format(CO2_utility(story, strict_prefs2, prefs, CO2_value)))
