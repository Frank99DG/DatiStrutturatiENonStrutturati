from bs4 import BeautifulSoup
import requests
import re
import nltk
from nltk.corpus import wordnet as wn
from sklearn.feature_extraction.text import TfidfVectorizer

#headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}

def find_symptoms():
    nltk.download('wordnet')
    symptoms = []
    with open("DatiStrutturatiENonStrutturati\dict_start.txt", "r") as text:
        for line in text.readlines():
            symptoms.append(line.strip())
    symptoms = list(map(lambda x: x.lower(), set(symptoms)))
    #print(symptoms)
    #n = len(symptoms)
    sinonimi = []
    for word in symptoms:
        #print("Cerco i sinonimi di " + word)
        #print()
        if wn.synsets(word) != []:
            sinonimi += wn.synsets(word)[0].lemma_names()        
        #print("--------------------------------------------------")
    symptoms += list(set(sinonimi))
    return list(set(symptoms))

def get_tf_idf(recensioni, vocabolario):
    TFIDF_vectorizer = TfidfVectorizer(vocabulary = vocabolario)
    tfidf_vectors = TFIDF_vectorizer.fit_transform(recensioni)
    print(TFIDF_vectorizer.get_feature_names_out())
    print(tfidf_vectors)
    for i in range (len(tfidf_vectors.toarray())):
        print(tfidf_vectors.toarray()[i,:])

def main():
    sinonimi = find_symptoms()
    get_tf_idf(["urticaria urticaria", "urticaria urticaria burping suca cazzp palle"], sinonimi)
    

def list_drug_names (cur,con):
    query = '''SELECT name from drugs'''
    cur.execute(query)
    results = cur.fetchall()
    return list(map(lambda x: x[0], results))

def select_review (cur,con,med_name):
    query = '''SELECT review_data from reviews where drug =%(content)s'''
    cur.execute(query, {"content":med_name})
    results = cur.fetchall()
    return list(map(lambda x: x[0], results))

if __name__=="__main__":
    main()    