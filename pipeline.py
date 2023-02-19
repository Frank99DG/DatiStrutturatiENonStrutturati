from bs4 import BeautifulSoup
import requests
import re
import nltk
from nltk.corpus import wordnet as wn
from sklearn.feature_extraction.text import TfidfVectorizer
from ping_pong import init_postgres

#headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}

def find_symptoms():
    '''Individua tutti i sinonimi di una lista di sintomi passata in input
    Per ora i dizionari dei sintomi e dei sinonimi sono separati.'''

    nltk.download('wordnet')

    # Carico i sintomi presenti nel file in una lista
    symptoms = []
    with open("dict_start.txt", "r") as text:
        for line in text.readlines():
            symptoms.append(line.strip())

    # Rimuovo i duplicati e metto tutto minuscolo
    symptoms = list(map(lambda x: x.lower(), set(symptoms)))
    #print(symptoms)
    #n = len(symptoms)

    # Ricerco i sinonimi in wordnet
    sinonimi = []
    for word in symptoms:
        #print("Cerco i sinonimi di " + word)
        #print()
        if wn.synsets(word) != []:
            sinonimi += wn.synsets(word)[0].lemma_names()        
        #print("--------------------------------------------------")
    symptoms += list(set(sinonimi))
    return list(set(symptoms))

def get_tf_idf(cur, con, id_recensioni, testo_recensioni, vocabolario):
    '''Data la lista delle recensioni, crea il surrogato usando il modello vettoriale (tfidf) con il dizionario dei sintomi.
    Inoltre, popola il database delle recensioni con il vettore appena creato'''
    TFIDF_vectorizer = TfidfVectorizer(vocabulary = vocabolario)
    tfidf_vectors = TFIDF_vectorizer.fit_transform(testo_recensioni)
    #print(TFIDF_vectorizer.get_feature_names_out())
    #print(tfidf_vectors)
    #for i in range (len(tfidf_vectors.toarray())):
        #print(tfidf_vectors.toarray()[i,:])

    query = '''update reviews
	set review_data.vector = %s
	where id = %s;'''
    for id, vector in zip(id_recensioni, tfidf_vectors.toarray().tolist()):
        cur.execute(query, (vector, id))
    con.commit()
        
def list_drug_names (cur, con):
    query = '''SELECT name from drugs'''
    cur.execute(query)
    results = cur.fetchall()
    return list(map(lambda x: x[0], results))

def select_review (cur, con, med_name):
    '''Restituisce le coppie (id, review_text) dal database delle recensioni'''
    query = '''SELECT id, (review_data).text from reviews where drug =%(content)s'''
    cur.execute(query, {"content":med_name})
    results = cur.fetchall()
    return results

def main():
    sinonimi = find_symptoms()
    cur, con = init_postgres()
    review_list = select_review(cur, con, 'amoxicillin')
    get_tf_idf(cur, con, map(lambda x: x[0], review_list), map(lambda x: x[1], review_list), sinonimi)
    cur.close()
    con.close()

if __name__=="__main__":
    main()    