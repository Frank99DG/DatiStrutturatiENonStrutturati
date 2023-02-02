import Prova as pr
import sqlite3


def init_sqlite():
    con = sqlite3.connect('Scraping.db')
    cur = con.cursor()
    cur.execute("PRAGMA foreign_keys = 1")

    query_node = '''CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY,
                tag TEXT NOT NULL,
                attributes TEXT,
                value TEXT,
                parent_id INTEGER,
                FOREIGN KEY (parent_id) REFERENCES nodes(id) ON DELETE CASCADE)'''

    cur.execute(query_node)
    con.commit()
    return cur, con

def insert_node(parent_id,childs, cur, con):
    for child in childs:
        query =  '''INSERT INTO nodes (tag, attributes, value, parent_id) VALUES (?,?,?,?)'''
        cur.execute(query,(child["tagName"],child["attrs"],child["content"],parent_id))
        con.commit()
        node_id = cur.lastrowid
        insert_node(node_id, child["childs"], cur, con )

        chan