from bs4 import BeautifulSoup
import psycopg2
import requests
import re
import nltk
from nltk.corpus import wordnet as wn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics.pairwise import linear_kernel
import spacy
import matplotlib.pyplot as plt
import pandas as pd
en=spacy.load("en_core_web_sm")

def init_postgres():
    con = psycopg2.connect("user=postgres password=admin")
    con.autocommit=True
    cur = con.cursor()
    cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'scraping'")
    exists = cur.fetchone()
    if not exists:
        cur.execute('CREATE DATABASE scraping')
        con.commit()
    cur.close()
    con.close()
    con = psycopg2.connect("dbname=scraping user=postgres password=admin")
    cur = con.cursor()
#     query = '''CREATE TABLE IF NOT EXISTS documents (
#                 url TEXT PRIMARY KEY,
#                 title TEXT,
#                 created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                 content TEXT NOT NULL)'''

    #create pages table
    query_pages = '''CREATE TABLE IF NOT EXISTS pages (
                id SERIAL PRIMARY KEY,
                url TEXT NOT NULL,
                created_date DATE DEFAULT CURRENT_TIMESTAMP,
                id_node INTEGER NOT NULL,
                FOREIGN KEY (id_node) REFERENCES nodes(id) ON DELETE CASCADE)'''

    query_node = '''CREATE TABLE IF NOT EXISTS nodes (
                id SERIAL PRIMARY KEY,
                tag TEXT NOT NULL,
                attributes TEXT,
                value TEXT,
                parent_id INTEGER,
                FOREIGN KEY (parent_id) REFERENCES nodes(id) ON DELETE CASCADE)'''
    
    query_medicine = '''CREATE TABLE IF NOT EXISTS drug(
                name text primary key,
                uses text,
                side_effects text,
                precautions text,
                interactions text,
                overdose text
    )
    '''

    #cur.execute(query)
    cur.execute(query_node)
    cur.execute(query_pages)
    cur.execute(query_medicine)
    con.commit()
    return cur, con

def check_nltk():
    nltk.download('stopwords')
    nltk.download('wordnet')
    nltk.download('omw-1.4')

def remove_stopwords(text):
    # Probabilmente conviene cambiare dizionario di stopwords perchè restano troppe parole inutili
    sw = nltk.corpus.stopwords.words('english')
    return ' '.join(word for word in text.split() if word not in sw)

def lemmatize_text(text):
    lemmatizer = nltk.WordNetLemmatizer()
    return " ".join(lemmatizer.lemmatize(word) for word in text.split())

def select_all_drugs(cur, con):
    query = '''select name from drug'''
    cur.execute(query)
    return map(lambda t: t[0],
        cur.fetchall())

def uses_query(cur, con, user_query):
    ''' Genera il tf_idf per tutte le recensioni presenti nel database; in seguito, calcola la cosine similarity
    tra la user query e le recensioni di ciascun medicinale; in questo modo, è possibile 'ricercare' un medicinale
    sulla base di sintomi e/o controindicazioni.
    user_query è il testo che si vuole ricercare nelle diverse recensioni dei diversi medicinali (e.g. 'infection', 'bacteria', etc.)
    Memento: siccome il vocabolario potrebbe essere ampliato quando viene visitato un nuovo set di recensioni,
    il prodotto scalare potrebbe essere calcolato tra vettori di lunghezze diverse. In pratica, questo prodotto
    può essere calcolato sui primi k elementi, dove k=min{len(v1), len(v2)}. Questo è vero perchè gli elementi 'extra'
    del vettore più lungo sono parole che non esistevano nei documenti precedenti, e quindi corrispodnerebbero a valori
    nulli se si fosse usato il dizionario ampliato anche per i vettori più corti.'''
    review_corpus = [] # Lista in cui ciascun elemento è la stringa di tutte le recensioni relative ad un singolo medicinale

    # Per ciascun medicinale, costruisco il tf_idf per l'intero corpus delle recensioni
    drug_list = list(select_all_drugs(cur, con))
    for med_name in drug_list:
        print('Sto estraendo le recensioni di {}'.format(med_name))

        # seleziono tutte le recensioni e ne elaboro il contenuto con nlp
        results = select_review(cur, con, med_name)
        ids = [result[0] for result in results]
        contents = [lemmatize_text(remove_stopwords(result[1])) for result in results]
        #print(contents[0:4])

        # Rimuovo le recensioni senza testo
        new_ids = []
        new_contents = []
        for id, content in zip(ids, contents):
            if content:
                new_ids.append(id)
                new_contents.append(content)
        #print(new_contents[0:4])

        # costruisco il tf_idf per il corpus delle recensioni
        all_reviews = '' # Stringa che contiene tutte le recensioni relative ad un singolo medicinale
        for review in new_contents:
            #print(review, '\n')
            all_reviews += review
        
        review_corpus.append(all_reviews)
        print('Il corpus contiene {} recensioni'.format(len(review_corpus)))
        #print(review_corpus[0:4])
        # tf-idf
    
    review_corpus.append(lemmatize_text(remove_stopwords(user_query))) # Aggiungo alla fine la richiesta utente.
    print('Il corpus contiene {} recensioni'.format(len(review_corpus)))
    TFIDF_vectorizer = TfidfVectorizer(lowercase = True)
    tfidf_vectors = TFIDF_vectorizer.fit_transform(review_corpus)

    # Calcolo la cosine similarity fra tutte le recensioni utente e la query.
    sim = cosine_similarity(tfidf_vectors[:-1], tfidf_vectors[-1])
    # Avendo calcolato la cosine similarity tra un corpus di documenti ed una sola riga di testo, la
    # cosine similarity è un vettore colonna.
    sim = sim[:, 0]
    print('cosine sim:', sim)

    # Ranking medicinali
    doc_ranking = sorted(list(zip(drug_list, sim)),
                         key = lambda e: e[1],
                         reverse = True) # ordino per cosine similarity
    print('Ranking medicinali per la query: {}'.format(user_query))
    for element in doc_ranking:
        print(f'Medicinale: {element[0]:80}    Similarità: {element[1]*100:.3f}%')
    


def tf_idf_plot(cur, con, med_name):
    '''Questa funzione seleziona tutte le recensioni relative ad un medicinale e applica una pipeline di nlp.
    In seguito, calcola il tfidf per l'unione di tutte le recensioni e fa un grafico delle parole più significative
    (ovvero con tf-idf maggiore di 0.01).'''
    results = select_review(cur, con, med_name)
    contents = [lemmatize_text(remove_stopwords(result[1])) for result in results]
    ids = [result[0] for result in results]

    
    new_ids = []
    new_contents = []
    for id, content in zip(ids, contents):
        if content:
            new_ids.append(id)
            new_contents.append(content)

    all_reviews = ' '.join(new_contents)

    #tokenizzazione per parola 
    TFIDF_vectorizer = TfidfVectorizer(lowercase = True)
    tfidf_vectors = TFIDF_vectorizer.fit_transform(contents)
    words = TFIDF_vectorizer.get_feature_names_out()
    print(len(tfidf_vectors.toarray()))
    
    # Grafico unico per l'intero set di recensioni
    # Grafico realizzato utilizzando tutti i dati
    tfidf_vectors = TFIDF_vectorizer.fit_transform(new_contents)
    words = TFIDF_vectorizer.get_feature_names_out()
    #print(len(tfidf_vectors.toarray()))

    # Generazione grafico
    fig, ax = plt.subplots()
    plt.title('TF-IDF di tutte le recensioni di {}'.format(med_name))
    data = pd.DataFrame({"words":words,
                          "weight":tfidf_vectors.toarray()[0,:]},
                           index=words)
    graph = data.plot(grid = True, style = 'r.', ax=ax)
    plt.show()

    # Seleziono solamente i dati più significativi
    select_data = data[data['weight'] > 0.01]
    fig, ax = plt.subplots()
    plt.title('TF-IDF di tutte le recensioni di {} con TF-IDF>0.01'.format(med_name))
    ax.set_xticks(range(len(select_data)))
    ax.set_xticklabels(select_data['words'], rotation=90)
    graph = select_data.plot(grid= True, style = 'r.', ax=ax)
    plt.show()

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

    query = '''update review
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
    query = '''SELECT id, (review_data).text from review where drug =%(content)s'''
    cur.execute(query, {"content":med_name})
    results = cur.fetchall()
    return results

def main():
    med_name = 'Celexa'
    sinonimi = find_symptoms()
    cur, con = init_postgres()
    review_list = select_review(cur, con, med_name)
    #get_tf_idf(cur, con, map(lambda x: x[0], review_list), map(lambda x: x[1], review_list), sinonimi)
    #tf_idf_plot(cur, con, med_name)
    uses_query(cur, con, 'heart disease')
    cur.close()
    con.close()

if __name__=="__main__":
    main()    