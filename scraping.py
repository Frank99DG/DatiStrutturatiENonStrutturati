from bs4 import BeautifulSoup
from urllib.request import urlopen
import requests
import time
import re
import psycopg2

headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
# Dizionari dati
kind_dict = {"Patient": 'P',
        "Caregiver": 'C'
}

gender_dict = {
    "Male" : 'M',
    "Female" : 'F',
    "Transgender" : 'T',
    "Nonbinary" : 'N',
    "Other" : 'O'
}

age_dict = {
    '0-2' : [0,2],
    '3-6': [3,6],
    '7-12': [7,12],
    '13-18': [13,18],
    '19-24': [19,24],
    '25-34': [25,34],
    '35-44': [35,44],
    '45-54': [45,54],
    '55-64': [55,64],
    '65-74': [65,74],
    '75 or over': [75,100] # 100 è scelto arbitrariamente.
}

# 0.n rappresenta n mesi in un anno.
time_on_med_dict = {
    'On medication for less than 1 month' : [0,0.1],
    'On medication for 1 to 6 months': [0.1, 0.6],
    'On medication for 6 months to less than 1 year': [0.6,1],
    'On medication for 1 to less than 2 years': [1,2],
    'On medication for 2 to less than 5 years': [2,5],
    'On medication for 5 to less than 10 years': [5,10],
    'On medication for 10 years or more': [10,100] # 100 è scelto arbitrariamente.
}

def parse_user_data(data):
    """Data una lista che codifica i dati utente, ritorna i dati singoli come tupla di dimensione fissa.
    I dati utente consistono di nome utente, età, genere, tempo di utilizzo, tipo di paziente."""
    name = data.pop(0) # Il nome è sempre presente, al più Anonymous.
    kind = gender = time = age = time_on_med = None

    for element in data:
        if element in kind_dict:
            kind = kind_dict[element]
        elif element in gender_dict:
            gender = gender_dict[element]
        elif element in age_dict:
            age = age_dict[element]
        elif element in time_on_med_dict:
            time_on_med = time_on_med_dict[element]
    return name, age, gender, time_on_med, kind

def extract_reviews(soup, cur, con):
    """Dato l'oggetto beautifulsoup che contiene tutte le recensioni (tag div con attributo class = review-details-holder, inserisce in postgres i dettagli relativi all'utente e la sua recensione"""

    for review in soup:
        # Estrazione dati utente
        user_data = review.find("div", class_ = 'details')
        # Siccome il numero e il tipo di dati non è noto a priori, estraiamo il dato come stringa per lavorarlo
        # Rimuovo il tag più esterno, che è noto
        data_list = user_data.contents
        # Rimuovo i tag span, le sbarrette verticali e gli spazi vuoti
        clean_data = list(map(
            lambda tag: re.sub('</?span>', '', str(tag)).replace('|','').strip(),
            data_list
        ))
        #print(clean_data)
        name, age, gender, time_on_med, kind = parse_user_data(clean_data)

        condition = review.find("strong", class_ = 'condition').string.lstrip('Condition: ')
        
        # Estrazione recensione testuale
        node = review.find("p", class_ = 'description-text')

        # Alcune recensioni non hanno testo. In questo caso, node è di tipo None.
        if node == None: text = ''
        # Se la recensione è troppo lunga, viene spezzettata in due paragrafi; altrimenti tutto il testo viene incluso in un solo tag. Distinguo i due casi
        elif len(list(node.children)) == 1 : text = node.string # Caso recensione corta
        else:
            shown_text = node.find("span", class_="showSec")
            hidden_text = node.find("span", class_="hiddenSec")
            text = shown_text.string + hidden_text.string

        data = (name, age, gender, time_on_med, kind, condition, text)

        # Popolamento database
        #print('sto inserendo {}'.format(data))
        illness_query = '''SELECT * FROM illness WHERE name = '{}'
        '''.format(data[5])
        cur.execute(illness_query)
        exists = cur.fetchone()
        if not exists:
            insert_illness(cur, con, data)
            con.commit()
        
        last_id = insert_patient(cur, con, data)
        insert_review(cur, con, data, last_id, )
        
    return (name, age, gender, time_on_med, kind, condition, text)

def page_soup(url, headers):
    """Estrae l'oggetto soup a partire da una pagina"""
    r = requests.get(url, headers = headers)
    return BeautifulSoup(r.content, features = 'html.parser')

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

    return cur,con

def create_types(cur, con):
    query = '''drop type if exists t_drug cascade;
    create type t_drug as(
	name varchar(255)
    );

    drop type if exists t_illness cascade;
    create type t_illness as(
	name VARCHAR(100)
    );

    drop type if exists review_text cascade;
    create type review_text as(
	text text
    );
	
    drop type if exists patient_data cascade;
    CREATE TYPE patient_data AS(
	name VARCHAR(255),
	age int array[2],
	kind CHAR(1),
	gender CHAR(1)
    );'''
    cur.execute(query)
    con.commit()
    return 1

def create_tables(cur, con):
    query = '''--drop table if exists drug cascade;
    --create table if not exists drug of t_drug;
    --alter table drug
	--add primary key (name);

    drop table if exists illness cascade;
    create table if not exists illness of t_illness;
    alter table illness add primary key(name);

    drop table if exists candidate_patient cascade;
    CREATE TABLE if not exists candidate_patient (
	id serial primary key,
	data patient_data,
	drug VARCHAR(255),
	illness VARCHAR(100),
	time_on_medication float array[2],
	foreign key(drug) references drug,
	foreign key(illness) references illness(name)
	);


    drop table if exists review cascade;
    create table if not exists review (
    ID serial,
	review_data review_text,
	drug VARCHAR(255),
	patient_id int,
	foreign key(drug) references drug,
	foreign key(patient_id) references candidate_patient(id));'''
    
    cur.execute(query)
    con.commit()
    return 1

def insert_patient(cur, con, data):
    query = '''INSERT INTO candidate_patient(data, drug, illness, time_on_medication) values
    ( (%s, %s, %s, %s), %s, %s, %s)
    RETURNING id
    '''
    cur.execute(query, (data[0], data[1], data[4], data[2], med_name, data[5], data[3]))
    id = cur.fetchone()[0] # è l'id del paziente appena inserito
    con.commit()
    return id

def insert_drug(cur, con, med_name):
    query = '''INSERT INTO drug VALUES('{}')
    '''.format(med_name)
    cur.execute(query)
    con.commit()
    return 1

def insert_illness(cur, con, data):
    query = '''INSERT INTO illness VALUES('{}')'''.format(data[5])
    cur.execute(query)
    con.commit()
    return 1

def insert_review(cur, con, data, last_id, med_name):
    query = '''INSERT INTO review(review_data.text, drug, patient_id) VALUES(%s, %s, %s)'''
    cur.execute(query, (data[-1], med_name, last_id))
    con.commit()
    return 1

def timer(seconds):
    """Aspetta per (seconds) secondi, mostrando una barra a schermo."""
    with Bar('Waiting', suffix = '%(eta)ds') as bar:
        for _ in range(100):
            time.sleep(seconds / 100)
            bar.next()

##da qui in poi è il codice mio

def get_med_name(cur, con):
    return

def get_urls_reviews(cur, con):
    query = '''select n."attributes" 
                from nodes n
                where n."attributes" like '%href=%review%' ''' 
                #il risultato è ("href='/drugs...'",) , quindi devo rimuovere href=' e ' per ottenere l'url
    cur.execute(query)
    results = list(map(lambda x: x[0].lstrip("href='").rstrip("'"), cur.fetchall()))
    #aggiungo il dominio di webmd
    results = list(map(lambda x: 'https://www.webmd.com' + x, results))
    #aggiungo '&page=' per agevolare il parsing, in modo da avere sempre la stessa struttura
    results = list(map(lambda x: x + '&page=', results))
    #print(results)
    return results

def peppe(cur, con, urls):
    for url in urls:
        soup = page_soup(url, headers)
        reviews_container = soup.find("div", class_ = "shared-reviews-container")
        
        # In fondo alla pagina c'è un elemento grafico con i numeri delle pagine. Estraggo l'ultima pagina
        lastpage_container = reviews_container.find_all('a',class_="page-link")[-1]
        lastpage = int(lastpage_container.string)
        med_name = "" #nome del farmaco
        
        for page_number in range(1, lastpage + 1):
            page_url = url + str(page_number)
            soup = page_soup(page_url, headers)
            reviews_container = soup.find("div", class_ = "shared-reviews-container") # Questo elemento della pagina contiene tutte le recensioni
            reviews_soup = reviews_container.find_all("div", class_ = "review-details-holder") # Questi sono i contenitori delle recensioni
            extract_reviews(reviews_soup, cur, con)
            print('La pagina %d di %d è stata inserita' % (page_number, lastpage))
            timer(20) # Timer aggiunto per evitare il ban
    
    return 1

def main():
    cur, con = init_postgres()
    links = get_urls_reviews(cur, con)
    peppe(cur, con, links)
    cur.close()
    con.close()


if __name__ == '__main__':
    main()