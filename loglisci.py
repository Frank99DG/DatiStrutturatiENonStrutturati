from bs4 import BeautifulSoup
import requests
import time
import re

url = 'https://www.webmd.com/drugs/drugreview-5310-hydrochlorothiazide-oral?conditionid=&sortval=1&page='
headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}

def extract_reviews(soup):
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
        print(clean_data)

        #user_data = [data.string.replace('|', '').strip() for data in user_data if data else ''] # Il numero di elementi non è noto a priori perchè alcuni campi possono essere vuoti

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

def page_soup(url, headers):
    """Estrae l'oggetto soup a partire da una pagina"""
    r = requests.get(url, headers = headers)
    return BeautifulSoup(r.content, features = 'html.parser')

def main():
    # Estrazione della prima pagina
    soup = page_soup(url, headers)

    # Estraggo la parte con le recensioni
    reviews_container = soup.find("div", class_ = "shared-reviews-container")
    # In fondo alla pagina c'è un elemento grafico con i numeri delle pagine. Estraggo l'ultima pagina
    lastpage_container = reviews_container.find_all('a',class_="page-link")[-1]
    lastpage = int(lastpage_container.string)

    for page_number in range(9, lastpage + 1):
        page_url = url + str(page_number)
        soup = page_soup(page_url, headers)
        reviews_container = soup.find("div", class_ = "shared-reviews-container") # Questo elemento della pagina contiene tutte le recensioni
        reviews_soup = reviews_container.find_all("div", class_ = "review-details-holder") # Questi sono i contenitori delle recensioni
        extract_reviews(reviews_soup)
        time.sleep(60) # Timer aggiunto per evitare il ban


if __name__== '__main__': main()