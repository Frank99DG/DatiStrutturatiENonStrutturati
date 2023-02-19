#!/usr/bin/env python

import sys
import json
import struct
import psycopg2
from datetime import datetime
from bs4 import BeautifulSoup
import requests
import re

headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}

def getMessage():
    """Intercetta qualunque cosa sia inviato dall'estensione JS e la interpreta come json."""
    rawLength = sys.stdin.buffer.read(4)
    if len(rawLength) == 0:
        sys.exit(0)
    messageLength = struct.unpack('@I', rawLength)[0]
    message = sys.stdin.buffer.read(messageLength).decode('utf-8')
    return json.loads(message)

# Questa funzione serve solamente per il debugging.
def encodeMessage(messageContent):
    """Codifica un messaggio in un formato che possa essere nuovamente inviato all'estensione."""
    encodedContent = json.dumps(messageContent).encode('utf-8')
    encodedLength = struct.pack('@I', len(encodedContent))
    return {'length': encodedLength, 'content': encodedContent}

# Send an encoded message to stdout
def sendMessage(encodedMessage):
    """Manda un messaggio a stdout, per poterlo visualizzare nell'estensione. Si assume che encodedMessage sia nel formato corretto, i.e. quello
    specificato da encodeMessage"""
    sys.stdout.buffer.write(encodedMessage['length'])
    sys.stdout.buffer.write(encodedMessage['content'])
    sys.stdout.buffer.flush()

def insert_node(parent_id, childs, cur, con):
    """ Per ciascuno dei tag figli del nodo con id 'parent_id', viene inserita una riga nella tabella nodes. La funzione è ricorsiva."""
    for child in childs:
        query =  '''INSERT INTO nodes (tag, attributes, value, parent_id) VALUES (%s, %s, %s, %s)
        returning id'''
        cur.execute(query,
                    (child["tagName"], child["attrs"], child["content"], parent_id))
        con.commit()
        
        node_id = cur.fetchone()[0]
        # La funzione viene invocata nuovamente su ciascuno dei figli.
        insert_node(node_id, child["childs"], cur, con )


def delete_if_exists(cur, con, url):
    query_control = '''SELECT id_node FROM pages WHERE url = (%s)'''
    cur.execute(query_control, [url])
    # fetchone() restituisce la prossima riga nei risultati della query. Restituisce un oggetto None se la lista è esaurita (o vuota)
    result = cur.fetchone()
    if result:
        query_delete2 = '''DELETE FROM nodes WHERE id = (%s)'''
        cur.execute(query_delete2, [result[0]]) # result[0] dovrebbe essere il valore di id_node
        con.commit()

def insert_page(cur, con, first_node, url):
    """Inserisce una pagina con dato url nella tabella delle pagine e inserisce il primo nodo nella tabella nodes. Restituisce il node_id del nodo principale della pagina."""
    # PROBABILMENTE ID VIENE INSERITO CON INCREMENTO AUTOMATICO
    query =  '''INSERT INTO nodes (tag, attributes, value) VALUES (%s, %s, %s)
    returning id'''
    cur.execute(query,
                (first_node["tagName"], first_node["attrs"], first_node["content"]))
    con.commit()
    node_id = cur.fetchone()[0] # Read-only attribute that provides the row id of the last inserted row
    page_query = '''INSERT INTO pages (url, id_node) VALUES (%s, %s)'''
    cur.execute(page_query,
                (url, node_id))
    con.commit()
    return node_id

def get_page_content(cur, first_node_id):
    """ boh """
    querycontrol = '''WITH RECURSIVE padre_figli (id, id_padre, tag_padre, value)
                    AS (
                        SELECT id, parent_id, tag, value
                        FROM nodes
                        WHERE id = (%s)
                        
                        union
                        
                        SELECT nodes.id, nodes.parent_id,
                        		(SELECT n.tag FROM nodes as n WHERE id = nodes.parent_id),
                        		nodes.value
                        FROM nodes, padre_figli
                        WHERE nodes.parent_id = padre_figli.id
                    )
                    SELECT string_agg(value, '') as text_content
                    FROM padre_figli
                    WHERE tag_padre!='SCRIPT'and tag_padre!='STYLE' and tag_padre!='META' and tag_padre!='LINK'
                    '''
    console_log(' Ho iniziato la query strana per il contenuto')
    cur.execute(querycontrol,
                (first_node_id, ))
    console_log(' Ho finito la query strana per il contenuto')
    # restuisce l'id (spero)
    return cur.fetchone()[0]

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

def get_title_page(cur, url):
    query = '''WITH RECURSIVE padre_figli (id, id_padre, tag_padre, value)
                AS (
                    SELECT id, parent_id, tag, value
                    FROM nodes
                    WHERE id = (SELECT id_node FROM pages as p where url=(%s))
                    
                    UNION
                    
                    SELECT nodes.id, nodes.parent_id,
                        (SELECT n.tag from nodes as n where id=nodes.parent_id),
                        nodes.value
                    FROM nodes, padre_figli
                    WHERE nodes.parent_id = padre_figli.id 
                )
               SELECT string_agg(value, '') as text_content         
                      FROM padre_figli
                WHERE tag_padre = 'TITLE'
                '''
    console_log('Ho iniziato la query strana per il titolo')
    cur.execute(query, (url, ))
    console_log('Ho finito la query strana per il titolo')
    return cur.fetchone()[0]

def insert_medicine(cur, con, name):
    query = '''
            WITH RECURSIVE padre_figli (id, id_padre, tag_padre, value)
                    AS ( select id, parent_id, tag, value --Questa seleziona il nodo padre da cui esplorare
                        FROM nodes
                        WHERE id = (select n.id
                                    from nodes n
                                    where n.attributes like %s order by n.id desc limit 1)

                        union

                        SELECT nodes.id, nodes.parent_id,
                                (SELECT n.tag FROM nodes as n WHERE id = nodes.parent_id),
                                nodes.value
                        FROM nodes, padre_figli
                        WHERE nodes.parent_id = padre_figli.id)
                    SELECT string_agg(value, ' ' order by padre_figli.id asc) as text_content -- Si ordina per id per riordinare correttamente le stringhe
                    FROM padre_figli;
    '''
    attributes_list = ['%uses-container%', '%side-effects-container%', '%precautions-container%', '%interactions-container%', '%overdose-container%']
    result_list = []
    for attribute in attributes_list:
        console_log('Eseguo la query ' + attribute)
        cur.execute(query, (attribute, ) )
        console_log('Ho eseguito la query ' + attribute)
        result_list.append(cur.fetchone()[0]) # cur.fetchone()[0] è il valore delle stringhe concatenate (vedi select string_agg)
    
    pop_query = '''INSERT INTO drug(name, uses, interactions, precautions, side_effects, overdose) values (%s, %s, %s, %s, %s, %s)'''
    console_log('Eseguo la query di popolamento')
    cur.execute(pop_query, (name, *result_list))
    console_log('Ho eseguito la query di popolamento')
    return cur, con

def find_name_generic(link):
    r = requests.get(link, headers = headers)
    soup = BeautifulSoup(r.content, features = 'html.parser')
    pattern = r' Generic Name\(S\): (\w*) '
    for tag in soup.find_all("h3", class_="drug-generic-name"):
        if re.search(pattern, tag.string):
            return re.search(pattern, tag.string).group(1)

def find_name(link):
    r = requests.get(link, headers = headers)
    soup = BeautifulSoup(r.content, features = 'html.parser')
    for tag in soup.find_all("h1", class_="drug-name"):
        return tag.contents[0].strip()

def timestr():
    """ Restituisce un timestamp ben formattato per poterlo stampare nella console del browser. Serve per avere contezza del tempo di computazione indicativo delle operazioni del database"""
    t_format = '%H:%M:%S'
    return datetime.now().strftime(t_format)

def console_log(message): return sendMessage(encodeMessage(timestr() + ' ' + message))

while True:

    receivedMessage = getMessage()
    ## Questa istruzione non serve a niente. Serve solo per logging.
    #sendMessage(encodeMessage(receivedMessage))
    tree = json.loads(receivedMessage)
    link = tree["page"]
    first_node = tree["tree"]
    console_log('Ho caricato il json correttamente')
    
    console_log('Ho trovato come link della pagina ' + link)
    name = find_name(link)

    console_log('Ho trovato il nome della pagina correttamente')
    
    # Inizializzazione database postgres
    console_log('Inizializzo il database postgres')
    cur, con = init_postgres()
    console_log('Il database postgres è stato inizializzato correttamente')
    
    console_log('Popolo il database postgres')
    # tree['page'] è l'url della pagina. Se presente nel database, viene cancellata
    delete_if_exists(cur, con, tree["page"])
    console_log('Ho eseguito delete_if_exists')
    first_node_id = insert_page(cur, con , first_node, link)
    console_log('Ho inserito la pagina in pages')
    # insert_node viene chiamata con l'id del nodo principale della pagina e con first_node['childs'], che è una lista di dizionari, ciascuno dei quali rappresenta un tag html.
    insert_node(first_node_id, first_node["childs"], cur, con )
    console_log('Ho inserito il primo nodo')
    result = get_page_content(cur, first_node_id)
    title = get_title_page(cur, tree["page"])
    
    console_log('Inizio ad inserire ' + name)
    insert_medicine(cur, con, name)
    console_log('Ho inserito ' + name)
    
    con.commit()
    cur.close()
    con.close()
    console_log('Il database postgres è stato popolato correttamente')
