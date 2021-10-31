    def infer_forbidden_materials(self, health_conditions):
        list_forbidden_materials = []
        #print('Health conditions to consider: ', health_conditions)
        if len(health_conditions) > 0:
            for health_cond in health_conditions:
                forbidden_materials = list(self.ontology.search(isForbiddenBy=self.label_to_indiv[health_cond]))
                list_forbidden_materials = list(set(list_forbidden_materials + forbidden_materials))
        return list_forbidden_materials

    def infer_stores(self, items):
        stores = ['Online stores']
        if len(items) > 0:
            for item in items:
                #print(item)
                possible_stores = list(self.ontology.search(selling=item))
                #print(possible_stores)
                stores = list(set(stores + possible_stores))
        else:
            stores = self.ontology.ClothingStore.instances()
        return stores

    def filter_stores_on_location(self, pref_locations, stores):
        stores_in_pref_locations = []
        #print(86878, stores)
        stores.remove('Online stores')
        if len(stores) > 0:
            if len(pref_locations) > 0:
                for store in stores:
                    for location in pref_locations:
                        if self.label_to_indiv[location] in list(store.isLocatedIn) and store not in stores_in_pref_locations:
                            stores_in_pref_locations.append(store)
                return stores_in_pref_locations
            else:
                return stores
        else:
            stores = ['Online stores only']
            return stores

    def infer_clothes(self, pref_clothing, health_cond):
        health_prevented_materials = self.infer_forbidden_materials(health_cond)
        health_prevented_clothing = []
        for material in health_prevented_materials:
            health_prevented_clothing = list(set(health_prevented_clothing + list(self.ontology.search(containsMaterial=material))))
        #print("Prevented by health problems: ", health_prevented_clothing)

        all_clothing = []
        clothing = self.ontology.search(label="Clothing")
        for c in clothing:
            for i in c.instances():
                all_clothing.append(i)

        clothing_list = all_clothing

        maxprice = 0
        fairness = False
        union = False
        or_found = False
        negation = False

        #print("All clothing items from ontology: ", all_clothing)
        print("Clothing preferences for user: ", pref_clothing)

        for pref in pref_clothing:
            #print(pref)
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
                            #print(found_materials)
                            found_clothing = []
                            for material in found_materials:
                                found_clothing = list(set(found_clothing + list(self.ontology.search(containsMaterial=material))))
                            print("FOUND CLOTHING: ", found_clothing)
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
        #print("BEFORE PRICE FILTER", clothing_list, maxprice)
        if maxprice > 0:
            #print("FOUND PRICE CONDITION: ", maxprice)
            for cloth in clothing_list:
                print("PRICE: ", cloth.hasPriceEur)
                if cloth.hasPriceEur:
                    if cloth.hasPriceEur[0] <= maxprice:
                        print("ADD: ", cloth)
                        clothing_list_price.append(cloth)
        else:
            #print("NO PRICE FILTER")
            clothing_list_price = clothing_list

        clothing_list_fair = []
        #print("BEFORE ETHICAL FILTER", clothing_list_filter, isFairTrade)
        if fairness:
            for cloth in clothing_list_price:
                if cloth.isFairTrade and str(cloth.isFairTrade[0]).lower() == isFairTrade:
                    #print("ADD MATCHING FAIRNESS: ", cloth)
                    clothing_list_fair.append(cloth)
        else:
            clothing_list_fair == clothing_list_price


        #print("Selected clothing after parsing but with prevented: ", clothing_list)
        preferred_clothing = list(set(clothing_list_fair) - set(health_prevented_clothing))
        print('Clothing found based on preferences and health conditions: ', preferred_clothing)

        clothing_stores = self.infer_stores(preferred_clothing)
        print(1000088, clothing_stores)
        print('Stores found that offer matching items: ', clothing_stores)
        stores_by_location = self.filter_stores_on_location(preferences['pref_location'], clothing_stores)
        print('Are these items available in physical stores in ', preferences['pref_location'], ' : ', stores_by_location)
        #return preferred_recipes, restaurants, restaurants_by_cuisines, restaurants_by_location, restaurants_by_cuisines_location

