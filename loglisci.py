from bs4 import BeautifulSoup
import requests
import time
import re
import psycopg2

med_name = 'hydrochlorothiazide'
url = 'https://www.webmd.com/drugs/drugreview-5310-hydrochlorothiazide-oral?conditionid=&sortval=1&page='
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
        illness_query = '''SELECT * FROM illnesses WHERE name = '{}'
        '''.format(data[5])
        cur.execute(illness_query)
        exists = cur.fetchone()
        if not exists:
            insert_illness(cur, con, data)
            con.commit()
        
        last_id = insert_patient(cur, con, data)
        insert_review(cur, con, data, last_id)
        
    return (name, age, gender, time_on_med, kind, condition, text)

def page_soup(url, headers):
    """Estrae l'oggetto soup a partire da una pagina"""
    r = requests.get(url, headers = headers)
    return BeautifulSoup(r.content, features = 'html.parser')

def init_postgres():
    con = psycopg2.connect("user=postgres password=admin")
    con.autocommit=True
    cur = con.cursor()
    cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'user_reviews'")
    exists = cur.fetchone()
    if not exists:
        cur.execute('CREATE DATABASE user_reviews')
        con.commit()
    cur.close()
    con.close()
    con = psycopg2.connect("dbname=user_reviews user=postgres password=admin")
    cur = con.cursor()

    return cur,con

def create_types(cur, con):
    query = '''drop type if exists drug cascade;
create type drug as(
	name varchar(255)
);

drop type if exists illness cascade;
create type illness as(
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
    return 'francesco sei un coglione perchè dici le stesse cazzate di domenico'

def create_tables(cur, con):
    query = '''drop table if exists drugs cascade;
create table drugs of drug;
alter table drugs
	add primary key (name);

drop table if exists illnesses cascade;
create table illnesses of illness;
alter table illnesses add primary key(name);

drop table if exists patients cascade;
CREATE TABLE if not exists patients (
	id serial primary key,
	data patient_data,
	drug VARCHAR(255),
	illness VARCHAR(100),
	time_on_medication float array[2],
	foreign key(drug) references drugs,
	foreign key(illness) references illnesses(name)
	);


drop table if exists reviews cascade;
create table reviews (
    ID serial,
	review_data review_text,
	drug VARCHAR(255),
	patient_id int,
	foreign key(drug) references drugs,
	foreign key(patient_id) references patients(id));'''
    cur.execute(query)
    con.commit()
    return 'domenico sei un coglione'

def insert_patient(cur, con, data):
    query = '''INSERT INTO patients(data, drug, illness, time_on_medication) values
    ( (%s, %s, %s, %s), %s, %s, %s)
    RETURNING id
    '''
    cur.execute(query, (data[0], data[1], data[4], data[2], med_name, data[5], data[3]))
    id = cur.fetchone()[0] # è l'id del paziente appena inserito
    con.commit()
    return id

def insert_drug(cur, con, med_name):
    query = '''INSERT INTO drugs VALUES('{}')
    '''.format(med_name)
    cur.execute(query)
    con.commit()
    return 1

def insert_illness(cur, con, data):
    query = '''INSERT INTO illnesses VALUES('{}')'''.format(data[5])
    cur.execute(query)
    con.commit()
    return 1

def insert_review(cur, con, data, last_id):
    query = '''INSERT INTO reviews(review_data.text, drug, patient_id) VALUES(%s, %s, %s)'''
    cur.execute(query, (data[-1], med_name, last_id))
    con.commit()
    return 1

def main():
    #Inizializzazione database ed inserimento medicina
    cur, con = init_postgres()
    create_types(cur,con)
    create_tables(cur,con)
    drug_query = '''SELECT * FROM drugs WHERE name = '{}' '''.format(med_name)
    cur.execute(drug_query)
    exists = cur.fetchone()
    if not exists:
        insert_drug(cur, con, med_name)


    # Estrazione della prima pagina
    soup = page_soup(url, headers)

    # Estraggo la parte con le recensioni
    reviews_container = soup.find("div", class_ = "shared-reviews-container")
    # In fondo alla pagina c'è un elemento grafico con i numeri delle pagine. Estraggo l'ultima pagina
    lastpage_container = reviews_container.find_all('a',class_="page-link")[-1]
    lastpage = int(lastpage_container.string)

    for page_number in range(1, lastpage + 1):
        page_url = url + str(page_number)
        soup = page_soup(page_url, headers)
        reviews_container = soup.find("div", class_ = "shared-reviews-container") # Questo elemento della pagina contiene tutte le recensioni
        reviews_soup = reviews_container.find_all("div", class_ = "review-details-holder") # Questi sono i contenitori delle recensioni
        extract_reviews(reviews_soup, cur, con)

        print('La pagina %d è stata inserita' % page_number)
        time.sleep(20) # Timer aggiunto per evitare il ban
    cur.close()
    con.close()


if __name__== '__main__': main()