# IA_group10: Myrthe Hemker (6007457), Alec Flesher-Clark (1625985), Sannerien van der Toorn (6222773), Thomas Wessels (5054435), Ivan Kondyurin (9086765)

---READ ME---:
For running our agent, please run the group_10_agent.py file. This requires a certain .json file as input, the standard .json file being sophie.json.
We have provided other .json files for the different user stories mentioned as scenario's in the paper:
- sophie.json for a restaurant recommendation user story
- dennis.json for an activity recommendation in the energy domain
- alex.json for the clothing recommendation user story
- bob.json for a transport recommendation for a user with COVID


To change the user preferences, please overwrite this file:
with open('./Users/sophie.json', 'r') as openfile:

To one of the other user stories mentioned above. So to run the agent for a clothing recommendation please change the line to:
with open('./Users/alex.json', 'r') as openfile:
