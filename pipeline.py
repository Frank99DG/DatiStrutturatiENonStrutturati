from bs4 import BeautifulSoup
import requests
import re
import nltk
from nltk.corpus import wordnet as wn

#headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}

if __name__=="__main__":
    nltk.download('wordnet')
    symptoms = []
    with open("DatiStrutturatiENonStrutturati\dict_start.txt", "r") as text:
        for line in text.readlines():
            symptoms.append(line.strip())
    symptoms = list(map(lambda x: x.lower(), set(symptoms)))
    print(symptoms)
    n = len(symptoms)
    sinonimi =[]
    for word in symptoms:
        print("Cerco i sinonimi di " + word)
        print()
        if wn.synsets(word) != []:
            sinonimi += wn.synsets(word)[0].lemma_names()        
        print("--------------------------------------------------")
    symptoms += list(set(sinonimi))
    print(symptoms)
    